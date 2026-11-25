"""Analyse the collected Commons data and produce CSVs, statistics and charts.

Input : data/raw/files_raw.json, data/raw/discovery.json
Output: data/processed/files.csv, data/processed/stats.json, charts/*.png
Run   : ../.venv/bin/python analyze.py
"""
import csv
import json
import os
import re
import urllib.parse
from collections import Counter, defaultdict

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
RAW = os.path.join(ROOT, 'data', 'raw')
OUT = os.path.join(ROOT, 'data', 'processed')
CHARTS = os.path.join(ROOT, 'charts')

YEARS = list(range(2013, 2027))
# Kumbh years at Prayagraj: the Magh Mela of that season is held as part of
# (and documented as) the Kumbh / Ardh Kumbh / Maha Kumbh.
KUMBH_YEARS = {2013, 2019, 2025}
# Magh Mela runs roughly from Paush Purnima (Jan) to Mahashivratri (Feb/Mar).
SEASON = ((1, 1), (3, 15))

PHOTO_MIME = {'image/jpeg', 'image/tiff', 'image/webp', 'image/heif',
              'image/heic'}
MAGH_RE = re.compile(r'm[a]{1,2}gh(?:a)?[\s_-]*mela|माघ\s*मेल', re.I)
PRAYAGRAJ_RE = re.compile(r'prayag|allahabad|sangam|triveni|प्रयाग|इलाहाबाद|संगम', re.I)
# Scans, manuscripts, maps and artworks: about Magh Mela, but not photographs of it
DOCUMENT_RE = re.compile(r'manuscript|\bpdf\b|\bscan|\bbooks?\b|\bpage\b|illustrat|painting|'
                         r'engraving|postcard|lithograph|drawing|\bmaps?\b|gazetteer|'
                         r'newspaper|journal|magazine', re.I)
KUMBH_RE = re.compile(r'kumbh|कुंभ|कुम्भ', re.I)
SANGAM_CONTEXT_RE = re.compile(
    r'sangam|triveni|ghat|snan|holy dip|mela|kalpvas|sankranti|amavasya|'
    r'purnima|pontoon|akhara|sadhu|pilgrim|devotee|संगम|स्नान', re.I)

THEMES = {
    'Rituals and religious practices': r'snan|\bbath|holy dip|\bdip\b|puja|'
        r'pooja|aarti|arti\b|ritual|prayer|sadhu|saint|naga\b|akhara|kalpvas|'
        r'sankranti|amavasya|purnima|shahi|havan|yagya|priest|pandit|worship|'
        r'devotee|pilgrim|hindu|religio|godd?ess?|deity|mantra|stotra|स्नान',
    'Sangam and river activities': r'confluence of|river|ganga|ganges|'
        r'yamuna|saraswati|\bboats?\b|boatm|ghat|confluence|\bgulls?\b|'
        r'migratory|bird|संगम|गंगा',
    'Temporary settlements and infrastructure': r'\btents?\b|\bcamps?\b|'
        r'pontoon|bridge|\broads?\b|sector|police|toilet|lighting|signage|'
        r'infrastructure|tent city|barricad|ambulance|hospital|railway|station|'
        r'traffic|parking|drone|aerial|satellite',
    'Architecture and public spaces': r'\bfort\b|temple|mandir|building|'
        r'\bgate\b|hanuman|akshayavat|monument|architect|structure|ashram|'
        r'arch\b|pandal|mosque|church|square|park\b',
    'Cultural activities and traditions': r'procession|music|dance|cultur|'
        r'\bfair\b|market|\bshops?\b|\bfood\b|stall|perform|exhibition|'
        r'celebrat|tradition|light show|laser|kite|costume|ceremonial|'
        r'dye|colou?r powder|statue|idol|jhoola|swing|ride',
    'Everyday life and people': r'\bpeople\b|portrait|\bman\b|\bmen\b|woman|'
        r'women|child|\bkids?\b|vendor|\bboy\b|\bgirl\b|family|crowd|'
        r'visitor|tourist|beggar|seller|barber',
}
THEMES = {k: re.compile(v, re.I) for k, v in THEMES.items()}

# Place and event names say where a photo was taken, not what it shows. Strip
# them before theme matching (e.g. "... - Magh Mela Festival - Sangam Site -
# Allahabad"), and ignore location/event categories.
BOILERPLATE_RE = re.compile(
    r'magh\w*[\s_-]*mela(?:\s+festival)?|makar\s+sankranti(?:\s+hindu)?\s*'
    r'(?:festival)?|kumbh\w*(?:\s+mela)?|sangam\s+site|triveni\s+sangam|'
    r'prayaga?\s+sangam|prayagraj|prayag|allahabad|uttar\s+pradesh|india|'
    r'festival|\bmela\b|माघ\s*मेला|प्रयागराज|इलाहाबाद', re.I)
PLACE_EVENT_CAT_RE = re.compile(
    r'sangam|prayag|allahabad|magh|kumbh|sankranti|uttar pradesh|india|'
    r'\b(19|20)\d\d\b|events|festivals|hindu pilgrimage|visitor attractions|'
    r'culture of|geography of|taken with|photographs by|flickr', re.I)


def theme_text(title, desc, caption, cats_visible):
    """Two texts: 'strong' (title, caption, subject categories: written
    for this file) and 'desc' (the description, often a long generic text
    reused across a batch, so weaker evidence)."""
    subject_cats = [c for c in cats_visible if not PLACE_EVENT_CAT_RE.search(c)]
    strong = ' '.join([title[5:], caption, ' '.join(subject_cats)])
    return BOILERPLATE_RE.sub(' ', strong), BOILERPLATE_RE.sub(' ', desc)

# Default reference palette (dataviz skill), light mode
INK, INK2, GRID, SURFACE = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300',
          '#6250d6', '#e34948']


def strip_html(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or '')).strip()


def year_of(file, cats):
    """(year, source). Prefer the camera date, then a year in a dedicated
    or event category name, then the title. Falls back to upload year."""
    ext = (file['imageinfo'][0].get('extmetadata') or {}) if file['imageinfo'] else {}
    dto = strip_html((ext.get('DateTimeOriginal') or {}).get('value', ''))
    m = re.search(r'\b(19[89]\d|20[0-2]\d)\b', dto)
    title_year = re.search(r'\b(18\d\d|19\d\d|20[0-2]\d)\b', file['title'])
    if m:
        y = int(m.group(1))
        mm = re.search(rf'{y}[-:/.](\d{{1,2}})[-:/.](\d{{1,2}})', dto)
        month_day = (int(mm.group(1)), int(mm.group(2))) if mm else None
        if title_year and int(title_year.group(1)) != y:
            return (int(title_year.group(1)),
                    f'file title (date taken says {y})', None)
        return y, 'date taken (EXIF/description)', month_day
    for c in cats:
        if MAGH_RE.search(c) or KUMBH_RE.search(c):
            m = re.search(r'\b(20[0-2]\d)\b', c)
            if m:
                return int(m.group(1)), 'event category name', None
    if title_year:
        return int(title_year.group(1)), 'file title', None
    up = upload_info(file)[0]
    return int(up[:4]), 'upload year (fallback)', None


def upload_info(file):
    """(timestamp, user) of the first upload (oldest file version)."""
    versions = sorted(file['imageinfo'], key=lambda v: v.get('timestamp', ''))
    if not versions:
        return '', ''
    return versions[0].get('timestamp', ''), versions[0].get('user', '')


def in_season(month_day):
    if not month_day:
        return None
    return SEASON[0] <= month_day <= SEASON[1]


def classify(f, text, cats_all):
    layers = set(f['found_by']['layers'])
    magh_text = bool(MAGH_RE.search(text))
    prayagraj = bool(PRAYAGRAJ_RE.search(text)) or bool(layers & {'related', 'broader'})
    if magh_text or 'dedicated' in layers:
        if not prayagraj:
            return 'Magh Mela elsewhere in India (excluded)'
        if DOCUMENT_RE.search(f['title'] + ' ' + ' '.join(cats_all)):
            return 'Magh Mela scans, manuscripts, artwork (not photographs)'
        # Titled as Kumbh: documented as the Kumbh, which absorbs that year's
        # Magh Mela. Count with the Kumbh material, not as Magh Mela.
        if KUMBH_RE.search(f['title']):
            return 'Kumbh Mela at Prayagraj (related event)'
        return 'Magh Mela (confirmed)'
    if layers == {'search'}:
        return 'Search hit, Magh Mela not in visible text (excluded)'
    if 'related' in layers or KUMBH_RE.search(' '.join(cats_all)):
        return 'Kumbh Mela at Prayagraj (related event)'
    return 'Prayagraj / Sangam (broader context)'


def file_url(title):
    return 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(
        title.replace(' ', '_'))


def setup_axes(ax, title, xlabel=None, ylabel=None):
    ax.set_facecolor(SURFACE)
    # Title aligned to the figure's left edge, so long y-labels can't push it off
    ax.figure.suptitle(title, x=0.01, ha='left', fontsize=12, color=INK,
                       fontweight='bold')
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    ax.tick_params(colors=INK2, length=0, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2, fontsize=9)


def note(fig, text):
    fig.text(0.01, 0.01, text, fontsize=7.5, color=INK2, ha='left',
             va='bottom', wrap=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(CHARTS, exist_ok=True)
    files = json.load(open(os.path.join(RAW, 'files_raw.json')))
    disc = json.load(open(os.path.join(RAW, 'discovery.json')))

    rows, seen = [], set()
    for f in files:
        if f['pageid'] in seen:
            continue
        seen.add(f['pageid'])
        if not f['imageinfo']:
            continue
        info = f['imageinfo'][0]
        ext = info.get('extmetadata') or {}
        desc = strip_html((ext.get('ImageDescription') or {}).get('value', ''))
        cats_visible = [c['title'][9:] for c in f['categories'] if not c['hidden']]
        cats_all = [c['title'][9:] for c in f['categories']]
        caption = ' | '.join(f.get('caption', {}).values())
        text = ' '.join([f['title'], desc, caption, ' '.join(cats_visible)])
        year, ysrc, md = year_of(f, cats_visible)
        up_ts, uploader = upload_info(f)
        cls = classify(f, text, cats_all)
        t_strong, t_desc = theme_text(f['title'], desc, caption, cats_visible)
        strong = [t for t, rx in THEMES.items() if rx.search(t_strong)]
        weak = [t for t, rx in THEMES.items()
                if t not in strong and rx.search(t_desc)]
        themes = strong + weak
        rows.append({
            'pageid': f['pageid'], 'title': f['title'], 'url': file_url(f['title']),
            'mime': info.get('mime', ''),
            'is_photo': info.get('mime', '') in PHOTO_MIME,
            'class': cls,
            'year': year, 'year_source': ysrc,
            'in_magh_season': in_season(md),
            'upload_date': up_ts[:10], 'upload_year': int(up_ts[:4]) if up_ts else '',
            'uploader': uploader,
            'themes': themes or ['Unclassified (no keyword match)'],
            'themes_strong': strong, 'themes_description_only': weak,
            'theme_basis': (('title/caption/subject category' if strong else '')
                            + (' + description only' if weak else '')).strip(' +')
                           if themes else 'none',
            'sangam_context': bool(SANGAM_CONTEXT_RE.search(text)),
            'layers': f['found_by']['layers'],
            'found_in_categories': [c[9:] for c in f['found_by']['categories']],
            'search_terms': f['found_by']['search_terms'],
            'visible_categories': cats_visible,
            'caption': caption, 'description': desc[:500],
        })

    # Possible-but-unconfirmed Magh Mela: broader-context photos taken in the
    # Magh Mela season of a non-Kumbh year, with a Sangam/mela context.
    for r in rows:
        r['possible_magh_mela'] = (
            r['class'] == 'Prayagraj / Sangam (broader context)' and r['is_photo']
            and r['in_magh_season'] is True and r['year'] not in KUMBH_YEARS
            and r['sangam_context'])

    with open(os.path.join(OUT, 'files.csv'), 'w', newline='', encoding='utf-8') as fh:
        cols = ['pageid', 'title', 'url', 'mime', 'is_photo', 'class',
                'possible_magh_mela', 'year', 'year_source', 'in_magh_season',
                'upload_date', 'upload_year', 'uploader', 'themes', 'themes_strong',
                'themes_description_only', 'theme_basis',
                'layers', 'found_in_categories', 'search_terms',
                'visible_categories', 'caption', 'description']
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r['class'], r['year'], r['title'])):
            w.writerow({k: '; '.join(v) if isinstance(v, list) else v
                        for k, v in r.items() if k in cols})

    photos = [r for r in rows if r['is_photo']]
    magh = [r for r in photos if r['class'] == 'Magh Mela (confirmed)']
    possible = [r for r in photos if r['possible_magh_mela']]
    by_class = Counter(r['class'] for r in photos)

    def year_counts(rs):
        c = Counter(r['year'] for r in rs)
        return {y: c.get(y, 0) for y in YEARS}

    stats = {
        'collected_at': disc['collected_at'],
        'unique_files_collected': len(rows),
        'unique_photographs': len(photos),
        'non_photo_files_excluded': dict(Counter(r['mime'] for r in rows
                                                 if not r['is_photo'])),
        'photos_by_class': dict(by_class),
        'magh_mela_confirmed': {
            'photos': len(magh),
            'by_year_documented': year_counts(magh),
            'outside_2013_2026': sum(1 for r in magh if r['year'] not in YEARS),
            'year_source': dict(Counter(r['year_source'] for r in magh)),
            'by_upload_year': dict(sorted(Counter(r['upload_year'] for r in magh).items())),
            'unique_uploaders': len({r['uploader'] for r in magh}),
            'uploader_counts': dict(Counter(r['uploader'] for r in magh).most_common()),
            'themes': dict(Counter(t for r in magh for t in r['themes']).most_common()),
            'themes_strong': dict(Counter(t for r in magh for t in r['themes_strong'])),
            'themes_description_only': dict(Counter(t for r in magh for t in r['themes_description_only'])),
            'found_by': {
                'dedicated_category_only': sum(1 for r in magh if r['layers'] == ['dedicated']),
                'search_only': sum(1 for r in magh if 'dedicated' not in r['layers']),
                'both': sum(1 for r in magh if 'dedicated' in r['layers'] and 'search' in r['layers']),
            },
        },
        'possible_magh_mela_unconfirmed': {
            'photos': len(possible),
            'by_year': year_counts(possible),
            'unique_uploaders': len({r['uploader'] for r in possible}),
        },
        'kumbh_related': {
            'photos': by_class.get('Kumbh Mela at Prayagraj (related event)', 0),
            'by_year_documented': year_counts([r for r in photos if r['class'] == 'Kumbh Mela at Prayagraj (related event)']),
        },
        'broader_context': {
            'photos': by_class.get('Prayagraj / Sangam (broader context)', 0),
            'by_year_documented': year_counts([r for r in photos if r['class'] == 'Prayagraj / Sangam (broader context)']),
        },
        'all_photos_unique_uploaders': len({r['uploader'] for r in photos}),
        'layer_counts_photos': {
            layer: sum(1 for r in photos if layer in r['layers'])
            for layer in ('dedicated', 'search', 'related', 'broader')},
        'dedicated_categories': disc['dedicated_categories'],
        'magh_categories_used_on_files': disc['magh_categories_used_on_files'],
    }
    json.dump(stats, open(os.path.join(OUT, 'stats.json'), 'w'), indent=1,
              ensure_ascii=False, default=str)

    make_charts(photos, magh, possible, stats)
    print(json.dumps({k: stats[k] for k in ('unique_files_collected',
          'unique_photographs', 'photos_by_class')}, indent=1))
    print('Magh Mela confirmed:', len(magh), '| possible:', len(possible))


def bar_labels(ax, bars, values):
    for b, v in zip(bars, values):
        if v:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), str(v),
                    ha='center', va='bottom', fontsize=8, color=INK2)


def make_charts(photos, magh, possible, stats):
    plt.rcParams['font.family'] = ['DejaVu Sans', 'Kohinoor Devanagari', 'Devanagari Sangam MN']
    total_line = f'Data: Wikimedia Commons API, collected {stats["collected_at"][:10]}.'

    # 1. Year-wise: confirmed Magh Mela photos vs possible (unconfirmed)
    fig, ax = plt.subplots(figsize=(10, 4.8), facecolor=SURFACE)
    conf = [stats['magh_mela_confirmed']['by_year_documented'][y] for y in YEARS]
    poss = [stats['possible_magh_mela_unconfirmed']['by_year'][y] for y in YEARS]
    x = range(len(YEARS))
    w = 0.38
    b1 = ax.bar([i - w / 2 - 0.01 for i in x], conf, w, color=SERIES[0],
                label='Confirmed Magh Mela', zorder=3)
    b2 = ax.bar([i + w / 2 + 0.01 for i in x], poss, w, color=SERIES[1],
                label='Possible, unconfirmed (Sangam, Jan–mid-Mar, non-Kumbh year)',
                zorder=3)
    bar_labels(ax, b1, conf)
    bar_labels(ax, b2, poss)
    for i, y in enumerate(YEARS):
        if y in KUMBH_YEARS:
            ax.text(i, -0.12, 'Kumbh', transform=ax.get_xaxis_transform(),
                    ha='center', fontsize=7, color=INK2)
    ax.set_xticks(list(x))
    ax.set_xticklabels([str(y) for y in YEARS])
    setup_axes(ax, 'Magh Mela photographs on Commons by year taken, 2013–2026',
               ylabel='Unique photographs')
    ax.legend(frameon=False, fontsize=8.5, loc='upper right')
    ax.set_ylim(0, max(conf + poss) * 1.18)
    note(fig, f'{total_line} Confirmed = in a Magh Mela category or mentioning '
              f'"Magh Mela" in its text, plus a Prayagraj/Allahabad/Sangam '
              f'context (n={len(magh)}; {sum(1 for r in magh if r["year"] not in YEARS)} '
              f'are dated before 2013). Year = date taken where available, '
              f'else category/title, else upload year.')
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(os.path.join(CHARTS, '1_year_distribution.png'), dpi=160)
    plt.close(fig)

    # 2. Contributors for confirmed Magh Mela photos
    uc = stats['magh_mela_confirmed']['uploader_counts']
    items = list(uc.items())
    if len(items) > 12:
        items = items[:11] + [('Others (%d)' % (len(uc) - 11),
                               sum(v for _, v in items[11:]))]
    fig, ax = plt.subplots(figsize=(9, max(3, 0.42 * len(items) + 1.2)),
                           facecolor=SURFACE)
    names = [n for n, _ in items][::-1]
    vals = [v for _, v in items][::-1]
    bars = ax.barh(names, vals, color=SERIES[0], height=0.6, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f' {v}',
                va='center', fontsize=8.5, color=INK2)
    setup_axes(ax, f'Who uploaded the confirmed Magh Mela photographs '
                   f'({len(uc)} uploaders, {len(magh)} photos)')
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    note(fig, f'{total_line} Uploader = user of the first file version.')
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(os.path.join(CHARTS, '2_contributors.png'), dpi=160)
    plt.close(fig)

    # 3. Themes (multi-label, keyword based)
    th = stats['magh_mela_confirmed']['themes']
    fig, ax = plt.subplots(figsize=(9, 4.2), facecolor=SURFACE)
    names = list(th.keys())[::-1]
    vals = list(th.values())[::-1]
    st = stats['magh_mela_confirmed']['themes_strong']
    sv = [st.get(n, v if n.startswith('Unclassified') else 0)
          for n, v in zip(names, vals)]
    wv = [v - a for v, a in zip(vals, sv)]
    ax.barh(names, sv, color=SERIES[0], height=0.6, zorder=3,
            edgecolor=SURFACE, linewidth=1,
            label='Title, caption or subject category')
    bars = ax.barh(names, wv, left=sv, color=SERIES[0], alpha=0.35,
                   height=0.6, zorder=3, edgecolor=SURFACE, linewidth=1,
                   label='Description text only (weaker evidence)')
    ax.legend(loc='lower right', frameon=False, fontsize=8.5)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width(), b.get_y() + b.get_height() / 2,
                f' {v} ({v / max(len(magh), 1):.0%})', va='center',
                fontsize=8.5, color=INK2)
    setup_axes(ax, f'Themes in confirmed Magh Mela photographs (n={len(magh)})')
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    note(fig, f'{total_line} Keyword match on title, description, caption and '
              f'categories; a photo can have several themes, so bars add up to '
              f'more than n. Not verified by looking at the images.')
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    fig.savefig(os.path.join(CHARTS, '3_themes.png'), dpi=160)
    plt.close(fig)

    # 4. Dedicated vs related vs broader (unique photos per class)
    order = ['Magh Mela (confirmed)', 'Kumbh Mela at Prayagraj (related event)',
             'Prayagraj / Sangam (broader context)',
             'Magh Mela scans, manuscripts, artwork (not photographs)',
             'Magh Mela elsewhere in India (excluded)',
             'Search hit, Magh Mela not in visible text (excluded)']
    vals = [stats['photos_by_class'].get(k, 0) for k in order]
    fig, ax = plt.subplots(figsize=(9, 3.6), facecolor=SURFACE)
    bars = ax.barh(order[::-1], vals[::-1], color=SERIES[0], height=0.6, zorder=3)
    for b, v in zip(bars, vals[::-1]):
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f' {v}',
                va='center', fontsize=8.5, color=INK2)
    setup_axes(ax, f'Unique photographs by how they relate to Magh Mela '
                   f'(n={len(photos)}, each photo counted once)')
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    note(fig, f'{total_line} A photo in several categories is counted once, '
              f'in the most specific class.')
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    fig.savefig(os.path.join(CHARTS, '4_dedicated_vs_broader.png'), dpi=160)
    plt.close(fig)

    # 5. Upload year of confirmed Magh Mela photos
    ub = stats['magh_mela_confirmed']['by_upload_year']
    ys = sorted(ub)
    fig, ax = plt.subplots(figsize=(9, 3.8), facecolor=SURFACE)
    bars = ax.bar([str(y) for y in ys], [ub[y] for y in ys], color=SERIES[0],
                  width=0.6, zorder=3)
    bar_labels(ax, bars, [ub[y] for y in ys])
    setup_axes(ax, 'When the confirmed Magh Mela photographs were uploaded',
               ylabel='Photographs')
    note(fig, f'{total_line} Upload year = date of the first file version.')
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(os.path.join(CHARTS, '5_upload_years.png'), dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    main()
