# Hướng dẫn chạy mã nguồn theo từng phần của báo cáo

Tài liệu này cho biết mỗi phần nội dung trong báo cáo (`latex-report/main.pdf`) được tạo bởi đoạn mã nào, chạy bằng lệnh gì, và sau khi chạy thì cần thấy kết quả gì. Mọi lệnh chạy từ **thư mục gốc của repo** (thư mục có `docker-compose.yml`).

## 0. Chuẩn bị một lần

| Cần có | Ghi chú |
|---|---|
| Docker Desktop đang chạy | Chạy PostgreSQL 16 trong container `olist_dw_postgres` |
| Python 3.11 trở lên | Đã chạy thử với 3.14 |
| MiKTeX hoặc TeX Live | Chỉ cần khi sinh lại biểu đồ (`pdflatex`, `pdftoppm`) hoặc biên dịch báo cáo |

```powershell
copy .env.example .env            # Linux/macOS: cp .env.example .env
# Sửa DB_PASSWORD trong .env. Nếu máy đã có PostgreSQL chiếm cổng 5432 thì đặt DB_PORT=5433.
docker compose up -d
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

**Kiểm tra:** `docker ps` thấy `olist_dw_postgres ... (healthy)`.

### Lỗi thường gặp trên Windows

Nếu Python báo `DLL load failed ... An Application Control policy has blocked this file` thì Smart App Control đang chặn thư viện `psycopg`. Không cần tắt Smart App Control; chỉ cần cho psycopg dùng `libpq.dll` của một bản PostgreSQL cài sẵn trên máy, chạy hai dòng sau trong cùng cửa sổ PowerShell trước các lệnh Python:

```powershell
$env:PSYCOPG_IMPL = "python"
$env:PATH = "C:\Program Files\PostgreSQL\18\bin;$env:PATH"   # đổi 18 theo phiên bản trên máy
```

Luôn chạy script từ thư mục repo, không chạy từ thư mục Temp (Smart App Control chặn nạp DLL của scikit-learn ở đó).

## Thứ tự chạy

```
ETL (mục 1)  ->  EDA (mục 2)  ->  OLAP (mục 3)  ->  DSS: evaluate_models -> score_delay (mục 4)  ->  biểu đồ (mục 5)  ->  báo cáo (mục 6)
```

ETL phải chạy trước vì mọi bước sau đều đọc từ cơ sở dữ liệu. `score_delay` phải chạy sau `evaluate_models` vì nó đọc tham số đã chọn trong `src/dss/results/best_config.json`.

---

## 1. ETL - Phần 3 (Thiết kế ETL) và mục 4.2 (Hiện thực ETL)

| Lệnh | Thời gian | Làm gì |
|---|---|---|
| `python -m src.etl.run_etl --init` | ~10-20 giây | Tạo 4 schema (`staging`, `dm`, `meta`, `dss`), các bảng, rồi nạp toàn bộ dữ liệu |
| `python -m src.etl.run_etl` | ~10-20 giây | Những lần nạp lại sau |
| `python -m src.etl.verify_rollback` | vài giây | Cố ý gây lỗi trong bước Load để chứng minh Data Mart không bị nạp dở dang |

Mã liên quan: `src/etl/` (điều phối), `src/sql/00-05` (tạo bảng), `10_transform.sql`, `20_load_dims.sql`, `30_load_fact.sql`, `40_dq_checks.sql`.

**Kiểm tra (khớp với Bảng tab:etlbuoc, tab:doisoat, tab:danhgiakho):**

```sql
SELECT COUNT(*) FROM dm.fact_sales;                       -- 112650
SELECT COUNT(*) FILTER (WHERE passed), COUNT(*) FROM meta.dq_result
WHERE run_id = (SELECT MAX(run_id) FROM meta.dq_result);  -- 20 | 20
```

`verify_rollback` phải in ra Data Mart trở lại đủ 112.650 dòng, tổng giá bán 13.591.643,70 BRL.

## 2. EDA - Phần 2 (Khám phá và tiền xử lý dữ liệu)

```powershell
python -m src.eda.run_eda
```

- Phần 1 đọc thẳng 9 file CSV trong `data/raw` (không phụ thuộc ETL): cấu trúc, giá trị thiếu, dòng trùng, ngoại lai.
- Phần 2 đọc staging và Data Mart (cần chạy ETL trước): số bản ghi trước/sau, tương quan, tỷ lệ trễ theo nhóm.

Kết quả ở `src/eda/results/`:

| File | Dùng cho |
|---|---|
| `raw_structure.csv` | Bảng tab:cautruc (9 file, 52 cột) |
| `missing.csv` | Hình fig-eda-gia-tri-thieu |
| `outliers.csv` | Hình fig-eda-ngoai-lai |
| `before_after.csv` | Bảng tab:truocsau |
| `correlation.csv` | Hình fig-eda-tuong-quan |
| `late_by_bin.csv` | Hình fig-eda-ty-le-tre-theo-nhom |

**Kiểm tra:** `orders` có 99.441 dòng; `geolocation` có 261.831 dòng trùng; tỷ lệ trễ chung 6,77%.

## 3. OLAP - mục 4.3 (Phân tích OLAP)

```powershell
python -m src.olap.run_olap          # mặc định chạy mỗi truy vấn 5 lần để đo thời gian
```

Chạy 14 truy vấn trong `src/sql/50_olap_queries.sql`, lưu kết quả vào `src/olap/results/q01...q14_*.csv` và thời gian vào `timings.csv` (Bảng tab:thoigiantruyvan).

| Truy vấn | Phép OLAP | Bảng/hình trong báo cáo |
|---|---|---|
| q01 | Roll-up | tab:rollup, fig-olap-rollup-thang |
| q02, q03 | Drill-down | tab:drilldown, fig-olap-drilldown-bang |
| q04 | Slice | tab:slice |
| q05 | Dice | fig-olap-dice |
| q06 | Pivot | fig-olap-pivot |
| q07 | Trễ và đánh giá | fig-tre-va-danh-gia |
| q08 | Ma trận tuyến | fig-olap-tuyen-giao |
| q09 | Thời gian từng công đoạn | fig-olap-cong-doan |
| q10, q11 | Người bán | fig-olap-nguoi-ban-khach-hang |
| q12 | Ngành hàng tăng trưởng | fig-olap-tang-truong-nganh |
| q13 | CUBE vùng và năm | (thời gian thực thi) |
| q14 | Black Friday | fig-olap-black-friday |

**Kiểm tra:** doanh thu toàn kỳ 13.494.400,74 BRL / 98.199 đơn; truy vấn chậm nhất (CUBE) dưới 1 giây.

## 4. DSS - Phần 5 (Hệ hỗ trợ quyết định)

### 4.1 Chọn và đánh giá mô hình

```powershell
python -m src.dss.evaluate_models            # lần đầu: tìm tham số, ~1 giờ trên máy 20 luồng
python -m src.dss.evaluate_models --reuse    # lần sau: dùng lại best_config.json, bỏ bước tìm kiếm
```

Cách làm (mục 5.3, 5.4 của báo cáo):

1. `features.py` dựng đặc trưng point-in-time từ Data Mart: chỉ dùng thông tin đã biết tại lúc người bán bàn giao đơn cho đơn vị vận chuyển.
2. Tìm ngẫu nhiên 60 bộ tham số Gradient Boosting cho mỗi bộ đặc trưng và 4 giá trị C cho Logistic Regression, **chỉ trên 5 tháng validation 01-05/2018**.
3. Chọn mô hình tốt nhất mỗi loại, ghép thành ensemble 3 mô hình (trung bình thứ hạng).
4. Walk-forward 07/2017-08/2018: mỗi tháng huấn luyện lại trên các đơn đã biết kết quả trước tháng đó. Ba tháng test 06-08/2018 được đánh giá ở bước này.
5. Ghi `best_config.json` gồm hai phần: `final` là **mô hình dùng thật** (Gradient Boosting v1, tham số `V1_PARAMS` trong `evaluate_models.py`), và `ensemble` là kết quả của đợt tìm kiếm mở rộng.

Vì sao mô hình dùng thật không phải ensemble (mục 5.4 của báo cáo): ensemble tốt hơn trên validation (34,3% so với 31,9%) nhưng trên test chỉ đạt 39,8% so với 41,7%; mọi chênh lệch đều trong khoảng sai số ±2 điểm, nên mô hình đơn giản được giữ lại.

Kết quả ở `src/dss/results/`:

| File | Nội dung |
|---|---|
| `best_config.json` | **Siêu tham số đã chọn** (đọc bởi `score_delay.py`) |
| `search.csv` | Kết quả của từng cấu hình trên validation |
| `walkforward.csv` | Kết quả từng tháng của từng phương án (Hình fig-dss-theo-thang) |
| `improved_summary.csv` | Trung bình theo giai đoạn test / validation / toàn kỳ (Bảng tab:dssketqua, Hình fig-dss-so-sanh-mo-hinh) |
| `improved_summary.json` | Số đơn có nhãn, số đơn test, số đơn "đã quá hạn khi bàn giao" |

### 4.2 Chấm điểm và chính sách quyết định

```powershell
python -m src.dss.score_delay     # ~3 phút
```

Đọc mô hình `final` trong `best_config.json`, huấn luyện lại cho từng tháng test, hiệu chỉnh xác suất (isotonic, 60 ngày gần nhất), gán mức ĐỎ/VÀNG/XANH theo ngày, sinh lý do và hành động, rồi backtest các chính sách.

| Đầu ra | Dùng cho |
|---|---|
| bảng `dss.delay_risk_score`, `dss.model_registry` | Dashboard trang DSS |
| `scores.csv` | Hình fig-dss-muc-rui-ro, Bảng tab:dssvidu |
| `capacity_curve.csv` | Hình fig-dss-nang-luc |
| `confusion.csv` | Hình fig-dss-ma-tran-nham-lan |
| `policy_backtest.csv` | Bảng tab:dsschinhsach |
| `importance.csv` | Hình fig-dss-dac-trung |

Giả định chi phí (what-if) nằm ở đầu `score_delay.py`, biến `COST`.

**Kiểm tra (khớp với Bảng tab:datchitieu, tab:dsschinhsach):**

| Chỉ số | Giá trị |
|---|---|
| Recall@10% của mô hình từng tháng test (in ra màn hình) | 0,405 / 0,426 / 0,421 |
| `dss.delay_risk_score` | 18.753 dòng, 925 đơn ĐỎ |
| Đơn ĐỎ trễ thật / đơn XANH trễ thật | 28,8% / 2,5% |
| Bắt được khi cảnh báo 10% (kèm luật đã quá hạn), `capacity_curve.csv` | 44,5% |
| Chính sách chi phí kỳ vọng, `policy_backtest.csv` | 190 đơn, precision 96,8%, +688 BRL |
| Kết quả test trong `improved_summary.csv`, dòng `hgb_v1` | ROC-AUC 0,736, recall@10 41,7% |

### Tài nguyên máy khi train

Toàn bộ chạy trên CPU, không cần GPU, không tải gì từ mạng. Dữ liệu huấn luyện khoảng 97 nghìn đơn, dùng dưới 2 GB RAM; các file kết quả chỉ vài MB (`scores.csv` lớn nhất, khoảng 3 MB). Thứ tốn nhất là thời gian CPU của bước tìm tham số.

## 5. Biểu đồ trong báo cáo

```powershell
python -m src.report.make_figures          # sinh lại toàn bộ 24 hình
python -m src.report.make_figures dss      # chỉ các hình có "dss" trong tên hàm (6 hình phần DSS)
python -m src.report.make_figures eda      # chỉ các hình có "eda" trong tên hàm
```

Hình được ghi vào `latex-report/Pictures/fig-*.png` (300 dpi). Cần chạy lại sau mỗi lần chạy ETL/EDA/OLAP/DSS.

| Phần báo cáo | Hàm trong `make_figures.py` | Đọc từ |
|---|---|---|
| 1.3 Dữ liệu nguồn | `fig_orders_by_month` | cơ sở dữ liệu |
| 2 EDA | `fig_eda_missing`, `fig_eda_outliers`, `fig_delivery_time`, `fig_review_distribution`, `fig_geolocation`, `fig_eda_correlation`, `fig_eda_late_by_bin` | `src/eda/results`, cơ sở dữ liệu |
| 4.3 OLAP | `fig_rollup_month`, `fig_drilldown_state`, `fig_dice`, `fig_pivot`, `fig_late_vs_review`, `fig_stage_durations`, `fig_route_heatmap`, `fig_black_friday`, `fig_category_growth`, `fig_seller_vs_orders` | cơ sở dữ liệu |
| 5 DSS | `fig_dss_model_compare`, `fig_dss_by_month`, `fig_dss_importance`, `fig_dss_confusion`, `fig_dss_risk_levels`, `fig_dss_capacity` | `src/dss/results` |

Các sơ đồ (kiến trúc, luồng ETL, lược đồ snowflake, vòng đời đơn hàng, luồng DSS) không sinh bằng Python mà vẽ bằng TikZ trong `latex-report/Sections/hinh/`.

## 6. Biên dịch báo cáo

```powershell
cd latex-report
latexmk -pdf main.tex
```

Không chạy lệnh này khi trình soạn thảo đang tự biên dịch, hai tiến trình ghi cùng file sẽ làm hỏng PDF.

## 7. Dashboard - mục 4.4 và mục 5.6

Streamlit, 7 trang (Tổng quan, Doanh thu, Giao hàng, Cảnh báo giao trễ, Mức độ hài lòng, Người bán, Giám sát ETL). Cần chạy ETL và `score_delay` trước.

```powershell
python -m src.dashboard.setup_role    # một lần: tạo tài khoản dashboard_app, in 2 dòng DASHBOARD_DB_* để thêm vào .env
streamlit run src/dashboard/app.py    # mở http://localhost:8501
```

Trên Linux/macOS có thể chạy cả chuỗi bằng `bash src/dashboard/run.sh` (tự bỏ qua bước đã làm; `--check` chỉ kiểm tra, không mở dashboard).

**Kiểm tra (Bảng tab:doichieu):** trang Tổng quan hiện doanh thu 13.494.400,74 BRL / 98.199 đơn và tỷ lệ trễ 6,77%; trang Cảnh báo giao trễ với tham số mặc định cho p* = 0,667, 190 đơn, lợi ích ròng 688 BRL. Chi tiết xem `src/dashboard/README.md`.

## Có cần Google Colab không?

Không. Hệ thống đọc/ghi PostgreSQL chạy trong Docker, mà Colab không chạy được Docker; train mô hình chỉ cần CPU của máy cá nhân. Chạy theo tài liệu này trên máy là đủ để dựng lại toàn bộ kết quả của báo cáo.
