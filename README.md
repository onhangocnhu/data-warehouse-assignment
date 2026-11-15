# E-commerce Marketplace Business Performance Data Warehouse

Course project for **CO4031 – Data Warehouses and Decision Support Systems**, semester 261, Ho Chi Minh City University of Technology (HCMUT).

The project covers the full assignment scope:

1. Business requirements analysis and problem definition.
2. Multidimensional data warehouse design (star / snowflake schema) and the ETL process.
3. System implementation: backend (database, ETL, OLAP) and frontend (dashboard / query interface).
4. A decision support system (DSS) component built on the data warehouse.

## Topic

Build a Data Mart that helps e-commerce marketplace managers track **revenue, delivery time, customer satisfaction, and seller performance by region and product category**.

Key design decisions:

- **Warehouse model:** an Independent Data Mart, built with the Bottom-up approach.
- **Architecture:** three tiers. ETL is written in Python; staging, the Data Mart, and metadata are stored in PostgreSQL; OLAP follows the ROLAP model.
- **Schema:** a snowflake schema with a single accumulating snapshot fact table. Each row represents one product in one order.

## Data

The [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle): 9 CSV files covering about 100,000 orders placed between 2016 and 2018. The files are in `data/raw/` (moved from `Dataset/` so the repository matches the submission layout `src/` + `data/` required by the assignment). Row counts and checksums are listed in [`data/README.md`](data/README.md).

> `data/raw/olist_geolocation_dataset.csv` is about 58 MB. GitHub shows a warning on push but accepts it because it is under 100 MB.

## Repository layout

```
.
├── report/                  Report (rule 5.1 item 1)
│   ├── main.tex, main.pdf   Cover page, section order, compiled report
│   ├── Pictures/            Images used in the report
│   ├── Sections/            LaTeX sections (phantich, eda, thietke, hienthuc, dss, ..., tailieuthamkhao = references, hinh/ = TikZ diagrams)
│   ├── drawio-files/        Diagram sources (draw.io, Mermaid)
│   ├── drawio-mcp/start.sh  Script that starts the draw.io MCP server
│   ├── CO4031_Assignment_HK261.pdf   Assignment rules
│   └── AGENTS.md            Instructions for AI agents working on the report
├── src/                     Source code (rule 5.1 item 2)
│   ├── sql/                 DDL (00-04) and ETL / OLAP SQL steps
│   ├── eda/ etl/ olap/      Exploratory analysis, Python ETL, OLAP queries
│   ├── dss/                 Decision support component
│   ├── dashboard/           Streamlit dashboard
│   ├── report/              Script that renders the report charts
│   ├── docker-compose.yml   PostgreSQL 16
│   ├── .env.example         Database settings template (copy to src/.env)
│   ├── requirements.txt     Python packages
│   ├── .streamlit/          Dashboard theme
│   └── HUONG_DAN_CHAY.md    Which command produces which part of the report
├── data/                    Sample data (rule 5.1 item 3)
│   ├── raw/                 Olist source data (9 CSV, read-only)
│   └── reference/           Lookup tables added by the team (state -> region, translation patch)
└── slides/                  Presentation slides (PDF, rule 5.1 item 4)
```


## Submission checklist (assignment rule 5.1)

| Required item | Location in this repo |
|---|---|
| Report (PDF) | `report/main.pdf` |
| Source code (`src/`) | `src/` (SQL, ETL, OLAP, DSS, dashboard) |
| Sample data (`data/`) | `data/` |
| Presentation slides (PDF) | `slides/BTL DATAWAREHOUSE.pdf` |
| Video link (on the report cover) | [Google Drive folder](https://drive.google.com/drive/folders/1U7ONwhEVuUqJkst1z5X8fvamymiwy6j7?usp=drive_link) |

## Running the system

Prerequisites: Docker Desktop running, Python 3.11+ (tested with 3.14), and for the charts a TeX
distribution with `pdflatex` and `pdftoppm` on PATH (MiKTeX or TeX Live).

```bash
copy src\.env.example src\.env               # Linux/macOS: cp src/.env.example src/.env; set DB_PASSWORD (DB_PORT=5433 if 5432 is taken)
docker compose -f src/docker-compose.yml up -d                 # PostgreSQL 16
python -m venv .venv && .venv\Scripts\activate   # Linux/macOS: source .venv/bin/activate
pip install -r src/requirements.txt
python -m src.etl.run_etl --init     # schemas, tables and a full ETL run (~10-20 s)
python -m src.eda.run_eda            # EDA before/after preprocessing -> src/eda/results/
python -m src.olap.run_olap          # 14 OLAP queries -> src/olap/results/
python -m src.dss.evaluate_models    # model selection on 01-05/2018 + walk-forward (~1-2 h); add --reuse to skip the search
python -m src.dss.score_delay        # needs results/best_config.json from the step above; scores + backtest -> dss.*
python -m src.report.make_figures    # report charts -> report/Pictures/fig-*.png (filter: make_figures dss)
```

What to check after each step:

| Step | Expected result |
|---|---|
| `run_etl --init` | `dm.fact_sales` has 112,650 rows; 20/20 checks pass in `meta.dq_result` |
| `run_olap` | 14 CSV files + `timings.csv` in `src/olap/results/` |
| `evaluate_models` | `src/dss/results/best_config.json` (chosen hyper-parameters), `search.csv`, `walkforward.csv`, `improved_summary.csv` |
| `score_delay` | `dss.delay_risk_score` has 18,753 rows (handover orders of 06-08/2018); `scores.csv`, `policy_backtest.csv` |

Windows note: if Python reports `DLL load failed ... An Application Control policy has blocked this file`
(Smart App Control blocking the `psycopg` binary), use psycopg's pure-Python mode with the libpq of a local
PostgreSQL install, for example in PowerShell:
`$env:PSYCOPG_IMPL="python"; $env:PATH="C:\Program Files\PostgreSQL\18\bin;$env:PATH"`.
Run scripts from the repository folder, not from a temporary folder.

Details of every entry point are in [`src/README.md`](src/README.md); the report appendix ("Phụ lục") has the same steps in Vietnamese.

## Building the report

Requirements: a TeX distribution with `pdflatex`, `latexmk`, and the `vntex` package (MiKTeX or TeX Live).

```bash
cd report
latexmk -pdf main.tex
```

If your editor compiles automatically, do not run this command at the same time. Two processes writing the same output will corrupt the PDF.

## Diagrams

All figures of the report share one visual style (same colours, fonts and line weights):

| Kind | Source | Notes |
|---|---|---|
| Diagrams (architecture, ETL flow, snowflake schema, order lifecycle, source relations, hierarchies, data cube, DSS flow) | TikZ files in `report/Sections/hinh/` | Common colours and styles (`dwbox`, `dwdb`, `\dwtable`, ...) are defined in `Sections/preamp.tex` |
| Data charts (`fig-*.png`) | `src/report/make_figures.py` | Built from the database with matplotlib's PGF backend (text in the report's own vntex font), then rasterised to PNG at 300 dpi with `pdftoppm` (ships with MiKTeX / TeX Live). Re-run after every ETL/DSS run |

The draw.io files in `report/drawio-files/` are the earlier versions of the architecture, ETL and schema diagrams (kept for reference; the report no longer uses their PNG exports). To export them without installing draw.io:

```bash
docker run --rm -v "$PWD/report/drawio-files:/data" rlespinasse/drawio-export:v4.5.0 --format png --scale 2 --border 10 --output export
```

The draw.io MCP server requires Node.js:

```bash
./report/drawio-mcp/start.sh            # start the server at http://localhost:3000
pkill -f drawio-mcp-server       # stop the server
```

## Report writing conventions

The report is written in Vietnamese and follows the style of the sample report.

See [`report/AGENTS.md`](report/AGENTS.md) for the full conventions.
