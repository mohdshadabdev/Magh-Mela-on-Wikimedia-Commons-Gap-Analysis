"""Collect Magh Mela-related files from Wikimedia Commons.

Layers (kept separate so they are never mixed up in the statistics):
  dedicated : categories whose name is about Magh Mela (incl. uncreated ones)
  search    : files whose title/description/categories mention Magh Mela
              (CirrusSearch full-text search, English and Hindi spellings)
  related   : Kumbh Mela at Prayagraj (same place and season, different event)
  broader   : Prayagraj Triveni Sangam and the "<year> in Prayagraj" categories

Every file is stored once (keyed by page ID) with the list of layers,
categories and search terms that found it.

Output: data/raw/discovery.json, data/raw/files_raw.json
Run:    ../.venv/bin/python collect.py
"""
import datetime as dt
import os
import re
from collections import defaultdict, deque

from commons_api import call, query_all, save_json

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'data', 'raw')

YEARS = range(2013, 2027)

# Category names about Magh Mela (not Magh Bihu or other Magh festivals)
MAGH_CAT_RE = re.compile(r'magh\w*[\s_-]*mela|माघ\s*मेल', re.I)

SEARCH_TERMS = [
    '"Magh Mela"', '"Magha Mela"', '"Maagh Mela"', '"Maghmela"',
    '"माघ मेला"', '"माघ मेले"',
]
CATEGORY_SEARCH_TERMS = ['Magh Mela', 'Magha Mela', 'Maagh Mela', 'माघ मेला']

# (layer, category, max depth)
SEED_CATEGORIES = [
    ('related', 'Category:Prayag Kumbh Mela', 3),
    ('related', 'Category:2013 Kumbh Mela', 2),
    ('related', 'Category:2019 Ardh Kumbh Mela', 2),
    ('related', 'Category:2025 Kumbh Mela', 3),
    ('broader', 'Category:Prayagraj Triveni Sangam', 2),
] + [('broader', f'Category:{y} in Prayagraj', 1) for y in YEARS]


def discover_dedicated_categories():
    """Category pages about Magh Mela, found by category search."""
    found = {}
    for term in CATEGORY_SEARCH_TERMS:
        for q in query_all(dict(list='search', srsearch=term, srnamespace=14,
                                srlimit='max')):
            for hit in q['search']:
                if MAGH_CAT_RE.search(hit['title']):
                    found[hit['title']] = term
    return found


def search_files():
    """Files (namespace 6) whose text mentions Magh Mela."""
    hits = defaultdict(set)
    for term in SEARCH_TERMS:
        n = 0
        for q in query_all(dict(list='search', srsearch=term, srnamespace=6,
                                srlimit='max', srprop='')):
            for hit in q['search']:
                hits[hit['pageid']].add(term)
                n += 1
        print(f'  search {term}: {n} files')
    return hits


def walk_category(root, max_depth):
    """BFS over a category tree. Returns {pageid: set(categories)} and the
    list of categories visited. Cycle-safe."""
    files = defaultdict(set)
    seen = {root}
    visited = []
    queue = deque([(root, 0)])
    while queue:
        cat, depth = queue.popleft()
        visited.append({'category': cat, 'depth': depth})
        for q in query_all(dict(list='categorymembers', cmtitle=cat,
                                cmtype='file|subcat', cmlimit='max',
                                cmprop='ids|title|type')):
            for m in q['categorymembers']:
                if m['type'] == 'file':
                    files[m['pageid']].add(cat)
                elif m['type'] == 'subcat' and depth < max_depth \
                        and m['title'] not in seen:
                    seen.add(m['title'])
                    queue.append((m['title'], depth + 1))
    return files, visited


def fetch_metadata(pageids):
    """Image info (all versions), non-hidden + hidden categories, extmetadata."""
    out = {}
    ids = sorted(pageids)
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        params = dict(pageids='|'.join(map(str, batch)),
                      prop='imageinfo|categories',
                      iiprop='timestamp|user|mime|size|extmetadata',
                      iilimit='50', iiextmetadatalanguage='en',
                      iiextmetadatafilter='DateTimeOriginal|ImageDescription|'
                                          'ObjectName|Artist|LicenseShortName',
                      clprop='hidden', cllimit='max')
        for q in query_all(params):
            for p in q.get('pages', []):
                rec = out.setdefault(p['pageid'], {
                    'pageid': p['pageid'], 'title': p['title'],
                    'imageinfo': [], 'categories': []})
                rec['imageinfo'].extend(p.get('imageinfo', []))
                rec['categories'].extend(
                    {'title': c['title'], 'hidden': c.get('hidden', False)}
                    for c in p.get('categories', []))
        print(f'  metadata {min(i + 50, len(ids))}/{len(ids)}')
    for rec in out.values():   # de-duplicate across continuation pages
        seen, cats = set(), []
        for c in rec['categories']:
            if c['title'] not in seen:
                seen.add(c['title'])
                cats.append(c)
        rec['categories'] = cats
    return out


def fetch_captions(pageids):
    """Structured-data captions (en, hi) via wbgetentities."""
    caps = {}
    ids = sorted(pageids)
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        d = call(dict(action='wbgetentities',
                      ids='|'.join(f'M{x}' for x in batch),
                      props='labels', languages='en|hi'))
        for eid, ent in d.get('entities', {}).items():
            labels = ent.get('labels') or {}
            if labels:
                caps[int(eid[1:])] = {k: v['value'] for k, v in labels.items()}
    return caps


def main():
    os.makedirs(RAW, exist_ok=True)
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    sources = defaultdict(lambda: {'layers': set(), 'categories': set(),
                                   'search_terms': set()})

    print('1. Dedicated categories (category search)')
    dedicated = discover_dedicated_categories()
    print('  ', sorted(dedicated))

    print('2. Full-text file search')
    for pid, terms in search_files().items():
        sources[pid]['layers'].add('search')
        sources[pid]['search_terms'] |= terms

    print('3. Category trees')
    seeds = [('dedicated', c, 3) for c in sorted(dedicated)] + SEED_CATEGORIES
    trees = []
    for layer, cat, depth in seeds:
        files, visited = walk_category(cat, depth)
        trees.append({'layer': layer, 'root': cat, 'max_depth': depth,
                      'categories_visited': visited, 'files': len(files)})
        print(f'  {layer:9} {cat}: {len(files)} files, '
              f'{len(visited)} categories')
        for pid, cats in files.items():
            sources[pid]['layers'].add(layer)
            sources[pid]['categories'] |= cats

    print(f'4. Metadata for {len(sources)} unique files')
    meta = fetch_metadata(sources.keys())

    # Magh Mela categories used on the files but not found by category
    # search (e.g. uncreated "red" categories). Walk them too, as dedicated.
    red = sorted({c['title'] for m in meta.values() for c in m['categories']
                  if MAGH_CAT_RE.search(c['title'])}
                 - set(dedicated))
    print(f'4b. Extra Magh Mela categories seen on files: {red}')
    new_ids = set()
    for cat in red:
        files, visited = walk_category(cat, 3)
        trees.append({'layer': 'dedicated', 'root': cat, 'max_depth': 3,
                      'categories_visited': visited, 'files': len(files),
                      'note': 'found on file pages, not by category search'})
        for pid, cats in files.items():
            sources[pid]['layers'].add('dedicated')
            sources[pid]['categories'] |= cats
            if pid not in meta:
                new_ids.add(pid)
    if new_ids:
        meta.update(fetch_metadata(new_ids))

    print('5. Captions')
    caps = fetch_captions(sources.keys())

    files = []
    for pid, src in sources.items():
        m = meta.get(pid)
        if not m:
            continue
        files.append({**m, 'caption': caps.get(pid, {}),
                      'found_by': {'layers': sorted(src['layers']),
                                   'categories': sorted(src['categories']),
                                   'search_terms': sorted(src['search_terms'])}})

    save_json(os.path.join(RAW, 'discovery.json'), {
        'collected_at': started,
        'api': 'https://commons.wikimedia.org/w/api.php',
        'search_terms_files': SEARCH_TERMS,
        'search_terms_categories': CATEGORY_SEARCH_TERMS,
        'dedicated_categories': dedicated,
        'magh_categories_used_on_files': red,
        'category_trees': trees,
    })
    save_json(os.path.join(RAW, 'files_raw.json'), files)
    print(f'Done: {len(files)} unique files saved. '
          f'Extra Magh categories seen on files: {red}')


if __name__ == '__main__':
    main()
