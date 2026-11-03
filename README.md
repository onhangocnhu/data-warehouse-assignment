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

The [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle): 9 CSV files covering about 100,000 orders placed between 2016 and 2018. The files are in `Dataset/`.

> `Dataset/olist_geolocation_dataset.csv` is about 58 MB. GitHub shows a warning on push but accepts it because it is under 100 MB.

## Repository layout

```
.
├── latex-report/            LaTeX report (main version)
│   ├── main.tex             Cover page and section order
│   ├── main.pdf             Compiled report
│   ├── Pictures/            Images used in the report
│   └── Sections/
│       ├── preamp.tex       Preamble: margins, fonts, header/footer, macros
│       ├── workload.tex     Task assignment table
│       ├── phantich/        Part 1: business requirements analysis
│       ├── thietke/         Part 2: data warehouse and ETL design
│       └── tailieuthamkhao.tex   Bibliography
├── drawio-files/            Diagram sources (draw.io, Mermaid)
├── drawio-mcp/start.sh      Script that starts the draw.io MCP server
├── Dataset/                 Olist source data (CSV)
├── Documents/               Course lecture slides
├── sample written report/   Sample report used as a writing-style reference
├── CO4031_Assignment_HK261.pdf   Assignment rules
└── AGENTS.md                Instructions for AI agents working in this repo
```

## Building the report

Requirements: a TeX distribution with `pdflatex`, `latexmk`, and the `vntex` package (MiKTeX or TeX Live).

```bash
cd latex-report
latexmk -pdf main.tex
```

If your editor compiles automatically, do not run this command at the same time. Two processes writing the same output will corrupt the PDF.

## Diagrams

| Diagram | Source | Image used in the report |
|---|---|---|
| Three-tier architecture | `drawio-files/kien-truc.drawio` | `latex-report/Pictures/kien-truc.png` |
| Snowflake schema | `drawio-files/schema-snowflake.drawio` | `latex-report/Pictures/schema-snowflake.png` |
| ETL flow | `drawio-files/etl-flow.drawio` | `latex-report/Pictures/etl-flow.png` |

Open the `.drawio` files with [app.diagrams.net](https://app.diagrams.net) or draw.io Desktop. After editing, export the PNG again into `latex-report/Pictures/` under the same file name.

The draw.io MCP server requires Node.js:

```bash
./drawio-mcp/start.sh            # start the server at http://localhost:3000
pkill -f drawio-mcp-server       # stop the server
```

## Report writing conventions

The report is written in Vietnamese and follows the style of the sample report.

See [`AGENTS.md`](AGENTS.md) for the full conventions.
