# data/

| Folder | Content | Who writes it |
|---|---|---|
| `raw/` | The 9 original CSV files of the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). **Read-only**: never edit these files. | Downloaded once from Kaggle |
| `reference/` | Small lookup tables the team adds during transformation: `state_region.csv` (27 states → 5 regions), `category_translation_patch.csv` (English names for the 2 untranslated categories). | Team |

## Verifying the raw files

Expected row counts (excluding the header) and the first 16 hex characters of each file's SHA-256 (checked on 07/11/2026):

| File | Rows | SHA-256 (prefix) |
|---|---:|---|
| `olist_orders_dataset.csv` | 99,441 | `1dca8c9a7a8d34f0` |
| `olist_order_items_dataset.csv` | 112,650 | `14e321c489a729b0` |
| `olist_order_payments_dataset.csv` | 103,886 | `6ca92718f7e0ac4a` |
| `olist_order_reviews_dataset.csv` | 99,224 | `012b61c7593e34f5` |
| `olist_customers_dataset.csv` | 99,441 | `8a80cdbd27b49a13` |
| `olist_sellers_dataset.csv` | 3,095 | `c877ee451aadbec3` |
| `olist_products_dataset.csv` | 32,951 | `66f99d0261196b7f` |
| `olist_geolocation_dataset.csv` | 1,000,163 | `3b7cf4f504ce3fbb` |
| `product_category_name_translation.csv` | 71 | `a81f0d1f27b27e72` |

Total: 1,550,922 rows.

To download again: `kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip`.

`olist_geolocation_dataset.csv` is about 59 MB. GitHub warns on push (over 50 MB) but accepts it (under 100 MB).
