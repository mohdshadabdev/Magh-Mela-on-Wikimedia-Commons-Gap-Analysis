"""Independent cross-check of the dedicated category with PetScan.

PetScan walks the category tree on its own servers. If its file count matches
the count our API walk found, the category walk in collect.py is not missing
files.

Output: data/raw/petscan_dedicated.json
Run:    ../.venv/bin/python petscan_check.py
"""
import json
import os

import requests

from commons_api import USER_AGENT

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'data', 'raw')
PETSCAN = 'https://petscan.wmcloud.org/'
CATEGORY = 'Magh Mela Festival Allahabad 2014'


def main():
    params = {'language': 'commons', 'project': 'wikimedia',
              'categories': CATEGORY, 'depth': 3, 'ns[6]': 1,
              'format': 'json', 'output_compatability': 'quick-intersection',
              'doit': 1}
    r = requests.get(PETSCAN, params=params, timeout=120,
                     headers={'User-Agent': USER_AGENT})
    r.raise_for_status()
    data = r.json()
    with open(os.path.join(RAW, 'petscan_dedicated.json'), 'w',
              encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    petscan_ids = {p['page_id'] for p in data['pages']}

    disc = json.load(open(os.path.join(RAW, 'discovery.json'), encoding='utf-8'))
    files = json.load(open(os.path.join(RAW, 'files_raw.json'), encoding='utf-8'))
    ours = {f['pageid'] for f in files
            if f'Category:{CATEGORY}' in f['found_by']['categories']}
    print(f'PetScan: {len(petscan_ids)} files | API walk: {len(ours)} files')
    print(f'Only in PetScan: {sorted(petscan_ids - ours)}')
    print(f'Only in API walk: {sorted(ours - petscan_ids)}')
    print(f'(API data collected {disc["collected_at"]})')


if __name__ == '__main__':
    main()
