# Magh Mela, Prayagraj: Wikimedia Commons coverage analysis

This folder measures how well the Magh Mela at Prayagraj is documented on
Wikimedia Commons for the years 2013–2026. All data comes from public APIs, and
every number can be reproduced by running the scripts again.

The findings are in **[REPORT.md](REPORT.md)**.

## Folder layout

```
scripts/
  commons_api.py     polite Commons API client (throttling, maxlag, retries, continuation)
  collect.py         step 1: finds files (category search, full-text search, category trees)
  analyze.py         step 2: classifies, deduplicates, computes statistics, draws charts
  petscan_check.py   step 3 (optional): checks the dedicated category against PetScan
data/raw/
  discovery.json     categories found, search terms, every category tree walked
  files_raw.json     metadata for each unique file, exactly as the API returned it
  petscan_dedicated.json   PetScan result for the dedicated category
  collect.log        console log of the collection run
data/processed/
  files.csv          one row per unique file, with its class, year, uploader, themes and source
  stats.json         every number used in the report
charts/              5 PNG charts, each with its n and method in the footnote
```

## Run it

Requires Python 3.10 or later.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd scripts
../.venv/bin/python collect.py | tee ../data/raw/collect.log
../.venv/bin/python analyze.py
../.venv/bin/python petscan_check.py
```

`collect.py` sends API requests one at a time, with a 1-second pause between
requests and `maxlag=5`. On HTTP 429 or 5xx the client
waits for the time in `Retry-After`. The User-Agent names the project and a
Commons user page; it does not contain an email address.

Commons changes every day, so a later run will give slightly different counts.
The collection time is saved in `discovery.json` (`collected_at`), and every
chart footnote shows it.

## How to check a number

Each row in `files.csv` has the file's URL, its class, the categories and
search terms that found it, and the field the year was taken from
(`year_source`). To check a count, filter the CSV and open the file pages.
