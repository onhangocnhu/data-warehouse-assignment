# SKILLS.md: Guide for agents working in this repo

This repo holds the course project for **CO4031 – Data Warehouses and Decision Support Systems** (HCMUT, semester HK261), group 10, class L01.
Read this whole file before editing the report.

> **The report itself is written in Vietnamese.** This guide is in English, but every piece of report text you write must be Vietnamese (see section 4). Vietnamese strings below (section titles, column names, macro output) are quoted exactly as they appear in the report.

---

## 1. Project context

- **Topic:** "Xây dựng kho dữ liệu phân tích hiệu quả kinh doanh sàn thương mại điện tử" (building a data warehouse to analyze the business performance of an e-commerce marketplace).
  - The goal is to help marketplace managers track **revenue, delivery time, customer satisfaction, and seller performance by region and product category**.
- **The old title "DW phân tích doanh số bán hàng đa kênh" (multi-channel sales DW) was dropped.** The data has no sales-channel field.
- **Data:** `Dataset/`, the *Brazilian E-Commerce Public Dataset by Olist* (Kaggle), 9 CSV files.
- **Assignment rules:** `CO4031_Assignment_HK261.pdf`. Deadline 23:59 on 15/11/2026.
- **Team:**
  - Ôn Hà Ngọc Như (2312538): part 1 (requirements analysis) and part 2 (DW + ETL design).
  - Nguyễn Duy Thịnh (2313280): DSS.
  - Đặng Nguyên Bảo (2310211): backend/frontend implementation.
- **Lecturer:** ThS. Đỗ Thanh Thái.

## 2. Report structure (`latex-report/` is the main version)

```
latex-report/
├── main.tex                    cover page + \input order
├── Sections/
│   ├── preamp.tex              preamble (margins, font, header/footer, macros)
│   ├── workload.tex            task assignment table (written by the team, do not change its content)
│   ├── phantich.tex            \section 1, \inputs its child files
│   ├── phantich/{dongluc,nghiepvu,dulieu,yeucau}.tex
│   ├── thietke.tex             \section 2 + table of document abbreviations (Ch1, Ch2, Ch2-cont, Ch3)
│   ├── thietke/{khainiem,dachieu,logic,etl}.tex
│   └── tailieuthamkhao.tex     thebibliography
└── Pictures/hcmut.png
```
- **Every child file** starts with `% !TeX root = ../../main.tex`, or `../main.tex` if the file sits directly in `Sections/`.
- **Section numbering** uses default article style: 1, 1.1, 1.1.1, 1.1.1.1.
  - To refer to another section, always use `\label` / `\ref`; never hard-code numbers.
  - Existing section labels: `sec:phantich`, `sec:phamvi`, `sec:quanhe`, `sec:thietke`.
  - Table labels: `tab:quytrinh`, `tab:dactrung`, `tab:kpi`, `tab:quyetdinh`, `tab:nguon`, `tab:quanhe`, `tab:chatluong`, `tab:dapung`, `tab:tailieu`.

### Current status

- **Part 1:** finished.
- **The "Các câu hỏi phân tích nghiệp vụ" (business questions, BQ) subsection:** **removed** by the user (left commented out in `nghiepvu.tex`).
  - **Do not reuse the codes BQ01–BQ14** anywhere.
  - The KPI table has a "Mục đích sử dụng" (purpose) column and the decisions table has a "Thông tin cần theo dõi" (information to monitor) column. Both are written as prose.
- **Part 2:** 2.1.1 and 2.1.2 are written. All other subsections are still guidance skeletons.
  - **2.1.1 "Mô hình kho dữ liệu" (warehouse model):** chose an **Independent Data Mart**.
    - EDW was rejected: the data covers only one business area and comes from one source.
    - Virtual DW was rejected: the data needs cleansing and the assignment requires ETL.
    - The "data silo" weakness is addressed with conformed dimensions ("chiều đồng nhất (conformed dimensions)", cited to Kimball): time, geography, product. In the report, "dùng chung" means shared between customer and seller inside the Data Mart; "chiều đồng nhất" means reusable across Data Marts.
  - **2.1.2 "Hướng tiếp cận xây dựng mô hình" (build approach):** chose **Bottom-up**, to stay consistent with the Data Mart choice. Top-down and Hybrid were rejected.
  - **Remaining subsections** still use the skeleton macros: `\CacBuoc`, `\TaiLieu{}`, `\KetQua{}`, `\PhanNhom{}`, `\HinhCho{}{}`.
    - When the user settles a subsection, delete its skeleton block and replace it with prose.

## 3. Writing style (mandatory)

Follow `sample written report/CO3103_L06_Nhom10_Report.pdf`:

- **Write in Vietnamese**, in an academic report voice, with complete sentences and no chat-style abbreviations.
- **Structure of a subsection:**
  - an opening paragraph;
  - a bullet list in the form **"Short title: content"**;
  - a closing paragraph.
- **Non-functional requirements** are titled in the form `Performance -- Hiệu năng`, `Security -- Tính bảo mật`, etc.
- **When the user says "just write the choice paragraph":** write prose and **do not add a comparison table**.
- **Do not use** use-case, activity, sequence, or class diagrams. This is a DW report, not a software project.
- **Do not number content with codes** such as BQ01 or UC01 unless the user asks.
- **Numbers:** Vietnamese format, with a dot for thousands and a comma for decimals (99.441; 12,6 ngày; 6,8%). Currency is BRL.
- **Dates:** a full date is `DD/M/YYYY`: the day keeps two digits, the month drops its leading zero (`04/9/2016`, `01/1/2016`, `31/9/2026`, `12/11/2018`). A month written on its own (month/year, month ranges) keeps two digits: `09/2018`, `09-10/2018`, `01/2017-08/2018`. Code formats such as `YYYYMMDD` (`date_key`) are not affected.
- **Ranges ("đến"):** use a single hyphen with no spaces: `09-10/2018`, `15-20 MB`, `1-2 sao`, `2016-2018`, `(1-5)`. Keep ` -- ` only where it does not mean "đến": bilingual titles (`Performance -- Hiệu năng`, `Extract -- Trích xuất dữ liệu`), relationship cardinality (`1 -- nhiều`), "Name -- MSSV" on the cover, empty table cells.
- **Schema names:** write **"snowflake schema"** and **"star schema"**, never "lược đồ snowflake" or "lược đồ bông tuyết".
- **Terminology:**
  - Use the Vietnamese terms **chiều**, **bảng chiều**, **phân cấp**, **thước đo**. The English name appears in parentheses only at the first mention in the whole report: "bảng chiều (dimension table)", "chiều phân tích (dimensions)", "thước đo (measures)" (all in `phantich/yeucau.tex`), "phân cấp (hierarchies)" (`thietke/dachieu.tex`, 2.2.3).
  - Keep the English terms **granularity**, **transformation**, **staging**, **surrogate key**, **snowflake schema**, **bảng fact** as they are.
  - Named Kimball techniques keep their English name in parentheses: role-playing dimension, degenerate dimension, Slowly Changing Dimension, accumulating snapshot.
- **Citations:**
  - **Do not name the author in the sentence.** No "Theo Han và cộng sự…", "Theo Kimball…", "theo định nghĩa của Inmon…", "phương pháp của Kimball…". Write the statement itself and put `\cite{...}` at the end of the cited sentence, e.g. "Bước này bao gồm làm sạch dữ liệu, ánh xạ dữ liệu và áp dụng các quy tắc nghiệp vụ \cite{han}."
  - **Never cite the course slides.** There is no `slides` entry. Cite the textbook the slide content comes from:
    - `\cite{han}` [6] (Han, Kamber, Pei) for the three DW models, three-tier architecture, star/snowflake/fact constellation, Data Cube and OLAP, data quality, transformation, metadata;
    - `\cite{inmon}` [1] for the four DW characteristics, granularity, derived data;
    - `\cite{kimball}` [2] for ETL and staging, incremental load, 4-step design, accumulating snapshot, surrogate key, SCD, role-playing/degenerate/conformed dimensions;
    - `\cite{tmq}` [8] for relational database concepts;
    - `\cite{olist}` [9] for the dataset.
  - The bibliography lists all 8 syllabus references in syllabus order, plus the Olist dataset as [9]. Keys `turban`, `elmasri`, `sharda`, `burstein` are available for the DSS parts.

## 5. LaTeX conventions

- **Font and margins** come from the template: vntex, 13pt body text, 1.5 line spacing.
  - Left margin 35 mm, right 20 mm, top/bottom 25 mm, A4 paper.
  - Do not change margins or font.
- **Tables:**
  - The caption goes **above** the table: put `\caption` then `\label` before `tabularx`/`longtable`.
  - Table content uses `\small\setstretch{1.1}`.
  - Wrap longtables in `\begingroup\small\setstretch{1.1} ... \endgroup`.
  - For narrow, text-heavy columns use the `P{width}` column type (left-aligned, defined in the preamble) to avoid stretched word spacing.
  - To break a line inside a cell use `\newline`, **not `\\`**.
- **Macros:**
  - `\code{}` for file and column names (remember to escape `\_`);
  - `\TODO{}` for red text that still needs filling in;
  - `\safeimg{}{}` to insert an image safely.
- **Cover page:** the video link is still a `\TODO`. The cover date is 11/2026.

### Build

- The user's editor **auto-compiles** inside `latex-report/`. Compiling at the same time corrupts the PDF.
- Agents build to a temporary folder and copy the PDF back:
  ```bash
  cd latex-report
  latexmk -g -pdf -outdir=<scratch>/build -interaction=nonstopmode -halt-on-error main.tex
  cp <scratch>/build/main.pdf main.pdf
  ```
- **Build after every edit** and check for:
  - no `^!` lines;
  - no `Overfull` warnings;
  - no `undefined` references;
  - no `Missing character`;
  - no `??` in the PDF.
- Render the edited pages (`pdftoppm`) and look at them.

## 6. Course documents (`Documents/`)

Abbreviations used in the report:

| Abbreviation | File name |
|---|---|
| Ch1 | `Chapter_1_Introduction of Datawarehouse and Decision Support System.pdf` |
| Ch2 | `Chapter_2_Basic issues in data warehousing.pdf` |
| Ch2-cont | `Chapter_2_Basic issues in data warehousing - continue.pdf` |
| Ch3 | `Chapter_3_Designing a Data warehouse.pdf` |

Page numbers are PDF page numbers. Quick lookup (pages verified):

| Topic | Pages |
|---|---|
| Three models: EDW / Data Mart / Virtual | Ch3 p.10–15; Ch1 p.10, 18 |
| Top-down / Bottom-up / Hybrid | Ch3 p.16–21, 39 |
| Three-tier architecture | Ch3 p.5–9; Ch2 p.18 |
| Grain | Ch2-cont p.5–9; Ch2 p.3 |
| Dimensions, hierarchies, measures | Ch3 p.22, 24–25; Ch2 p.11, 15 |
| Data Cube and OLAP | Ch3 p.26–30, 38, 42–44; Ch2 p.16, 23–24 |
| Star / Snowflake / Fact constellation | Ch3 p.31–37 |
| ETL, staging | Ch1 p.15–16; Ch2 p.6, 8–9 |
| Data transformation, derived data | Ch2-cont p.10–13 |
| Metadata | Ch2-cont p.14–15; Ch2 p.13 |
| Data quality | Ch1 p.9, 13, 32; Ch2-cont p.17 |

- **Not covered by the slides:** "business question", Kimball's 4-step process, surrogate key, SCD, conformed dimension.
  - When using these concepts, state that they come from Kimball [2].
- **When the user asks where some content came from:** answer honestly.
  - If the agent proposed it, say so; never attribute it to a document.

## 7. Verified data figures

Profile with the **Python standard library** (`python3 -I`, `csv` module), since pandas is not installed. Read in memory and **never write to `Dataset/`**.

| Metric | Value |
|---|---|
| Orders | 99,441 (96,478 delivered) |
| Order items | 112,650 |
| Real customers (`customer_unique_id`) | 96,096 (2,997 have several `customer_id`s) |
| Sellers | 3,095 |
| Products | 32,951 |
| Product categories | 73 (2 have no English translation) |
| States with customers / with sellers | 27 / 23 |
| Date range | 04/9/2016-17/10/2018; stable period 01/2017-08/2018 (349 orders fall outside it) |
| Item value / freight | ≈ 13.59 / 2.25 million BRL |
| Mean delivery time | 12.6 days (median 10.2; max 209.6) |
| Late delivery rate | 6.8% |
| Mean review score | 4.09 (1–2 star reviews: 14.7%) |
| Orders from state SP | 42.0% |
| Sellers in state SP | 59.7% |
| Multi-item / multi-seller orders | 9,803 / 1,278 |

The table uses English number format; write them in Vietnamese format in the report (section 4).

- **Data quality issues:** see table `tab:chatluong` in `dulieu.tex`. Any new figure must be recomputed from the CSVs, never guessed.
- **Design issues left for the user to decide:**
  - reviews and payments are recorded per order, while sellers and prices are recorded per order item;
  - `geolocation` has no unique key.

## 9. Git

- Remote: `git@github-personal.com:onhangocnhu/data-warehouse-assignment.git`, branch `main`.
- `.gitignore` excludes:
  - `.DS_Store`;
  - LaTeX build files;
  - `*.zip`;
- `Dataset/olist_geolocation_dataset.csv` is 58 MB. GitHub warns on push (over 50 MB) but still accepts it (under 100 MB).
- Commit or push only when the user asks.
