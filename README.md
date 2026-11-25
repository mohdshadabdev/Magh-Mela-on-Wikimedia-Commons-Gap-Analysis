# Magh Mela, Prayagraj: Wikimedia Commons Coverage Analysis

A script-assisted analysis of the visual documentation of **Magh Mela in Prayagraj** on Wikimedia Commons, covering the period **2013–2026**.

This project examines how Magh Mela is represented on Wikimedia Commons, using publicly accessible API data, category exploration and text-based searches. It aims to understand the existing coverage, identify documentation gaps and provide a reproducible workflow that may inform future documentation efforts.

The analysis includes data collection, metadata processing, classification, statistical analysis and visualisations.

 **[Read the detailed report](REPORT.md)**

---

## Project structure

```text
.
├── scripts/
│   ├── commons_api.py       # Commons API client with throttling, maxlag, retries and continuation
│   ├── collect.py           # Step 1: file discovery and metadata collection
│   ├── analyze.py           # Step 2: classification, deduplication, statistics and charts
│   └── petscan_check.py     # Step 3 (optional): checks the dedicated category against PetScan
│
├── data/
│   ├── raw/
│   │   ├── discovery.json         # Categories, search terms and category trees explored
│   │   ├── files_raw.json         # Raw metadata for discovered unique files
│   │   ├── petscan_dedicated.json # PetScan results for the dedicated category
│   │   └── collect.log            # Collection run log
│   │
│   └── processed/
│       ├── files.csv       # Processed dataset with classifications and metadata
│       └── stats.json      # Statistics used in the report
│
├── charts/                 # Generated visualisations
├── REPORT.md               # Detailed findings, methodology and limitations
├── requirements.txt         # Python dependencies
└── README.md
```

## Getting started

### Requirements

- Python 3.10 or later
- Internet connection for Wikimedia Commons API requests

### Setup

Clone the repository:

```bash
git clone https://github.com/USERNAME/magh-mela-commons-analysis.git
cd magh-mela-commons-analysis
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Install dependencies:

```bash
.venv/bin/pip install -r requirements.txt
```

### Run the analysis workflow

The workflow consists of data collection followed by analysis. An optional PetScan check can also be run.

```bash
cd scripts

# Step 1: Discover files and collect metadata
../.venv/bin/python collect.py | tee ../data/raw/collect.log

# Step 2: Process data, calculate statistics and generate charts
../.venv/bin/python analyze.py

# Step 3 (optional): Check the dedicated category using PetScan
../.venv/bin/python petscan_check.py
```

<details>
<summary>Windows users</summary>

Create and activate the virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Then run the scripts from the `scripts` directory:

```bash
python collect.py
python analyze.py
python petscan_check.py
```

</details>

## Data collection

The collection script discovers files through multiple approaches, including category exploration, text-based searches and category-tree traversal.

The API client (`commons_api.py`) is designed to make requests responsibly. It includes:

- Request throttling.
- `maxlag` support.
- API continuation handling.
- Retry handling for HTTP 429 and 5xx responses.
- Respect for the `Retry-After` header when available.

Requests are made sequentially, with a one-second pause between requests and `maxlag=5`.

The User-Agent identifies the project and includes a Commons user page for context. It does not include a personal email address.

## Data and reproducibility

The repository contains the collected data, processed dataset, statistics and generated visualisations.

- `discovery.json` records the categories, search terms and category trees explored.
- `files_raw.json` stores the metadata collected for discovered files.
- `files.csv` contains the processed records, including classification, year, uploader, themes and discovery sources.
- `stats.json` stores the statistical outputs used in the report.
- `charts/` contains the generated visualisations.

Wikimedia Commons is continuously updated, so subsequent runs may produce different results. The collection timestamp is recorded in `discovery.json` under `collected_at`, and the generated charts include collection-date information where applicable.

The repository provides both the collected data snapshot and scripts to reproduce the analysis workflow.

## How to verify a finding

The processed dataset (`data/processed/files.csv`) can be used to inspect individual records and verify findings.

Each row includes information such as:

- File URL.
- Classification.
- Categories.
- Search terms or discovery sources.
- Year.
- `year_source`, indicating the metadata field used to derive the year.

You can filter the dataset to examine specific classifications, years, contributors or discovery sources, then visit the corresponding Wikimedia Commons file pages to review the records.

For the methodology, classification criteria, findings and limitations, see **[REPORT.md](REPORT.md)**.

## Limitations

This analysis relies on metadata, category structures and text-based discovery. Files that lack relevant titles, descriptions, captions or categories may not have been identified.

The classification and thematic analysis are based on the collected metadata and the methodology described in the report. The results should therefore be interpreted as an analysis of the documentation discoverable through this workflow, rather than a complete inventory of every photograph of Magh Mela.

## Purpose

This project is intended to help understand the state of visual documentation of Magh Mela on Wikimedia Commons and identify potential areas for future photography, categorisation and community documentation efforts.

The workflow may also be adapted to analyse the documentation of other cultural events, festivals or geographical locations on Wikimedia Commons.

---

*Built using publicly accessible Wikimedia Commons data and APIs, with the aim of supporting more systematic and reproducible documentation research.*
