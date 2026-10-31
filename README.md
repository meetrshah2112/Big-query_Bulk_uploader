# BigQuery Bulk Uploader

A small local web tool to upload **many CSV / Excel files at once** into a single BigQuery dataset
(instead of uploading one table at a time in BigQuery Studio). Built for people learning SQL in BigQuery.

**Features**
- Connection check (credentials + project + dataset)
- Select multiple `.csv` / `.xlsx` / `.xls` files and upload with one click
- Dataset is created automatically if it does not exist
- Each CSV becomes one table; each Excel **sheet** becomes its own table
- Column names and data types (INT, FLOAT, DATE...) are auto-detected
- Per-file status table (Success / Failed + reason) and a live list of tables in the dataset

---

## 1. Requirements
- Python 3.9+ (check: `python --version`)
- A Google account with a BigQuery project (the free **BigQuery sandbox** works)
- [Google Cloud CLI (gcloud)](https://cloud.google.com/sdk/docs/install)

## 2. Google Cloud setup (one time)
1. Open <https://console.cloud.google.com> and note your **Project ID** (not the project name).
2. Make sure the **BigQuery API** is enabled (it is by default in BigQuery Studio).
3. Log in so the tool can act as you:
   ```bash
   gcloud auth application-default login
   gcloud config set project YOUR_PROJECT_ID
   ```
   Your account needs the roles **BigQuery Data Editor** and **BigQuery Job User**
   (project owners already have these).

   *Alternative (service account):* create a service account with those two roles, download its JSON key, and set
   `GOOGLE_APPLICATION_CREDENTIALS` to the key's path before starting the app. Never commit the key to GitHub.

## 3. Install and run
```bash
git clone https://github.com/meetrshah2112/Big-query_Bulk_uploader.git
cd bq-bulk-uploader

python -m venv venv
# Windows:  venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

## 4. How to use
1. **Connection tab** - enter Project ID and Dataset name, pick a location, click **Check connection**.
   A green message means you are ready.
2. **Upload tab** - choose what happens if a table exists (replace / append / fail), click the file box,
   select all your files (Ctrl/Shift-click), press **Upload**. Each file shows Success or Failed.
3. **Tables tab** - lists every table now in the dataset with row and column counts.

Then open BigQuery Studio and run e.g. `SELECT * FROM \`project.dataset.table\` LIMIT 10;`

Try it first with the files in `sample_data/`.

## 5. Table naming rules
| File | Table name |
|---|---|
| `customers.csv` | `customers` |
| `Sales Data 2024.csv` | `Sales_Data_2024` |
| `products.xlsx` (1 sheet) | `products` |
| `products.xlsx` (sheets Items, Categories) | `products_Items`, `products_Categories` |

## 6. Troubleshooting
| Message | Fix |
|---|---|
| No Google credentials found | Run `gcloud auth application-default login` again |
| 403 Access Denied / Permission | Add *BigQuery Data Editor* + *BigQuery Job User* roles to your account |
| Project ID looks invalid | Use the Project ID (e.g. `my-project-123456`), not its display name |
| Dataset in different location | Use the same location as the existing dataset |
| Some columns look like STRING | Mixed values in a column (e.g. numbers and text) - clean in the file or `CAST` in SQL |

## 7. Notes
- Runs on your own machine only; files go straight from your computer to BigQuery.
- BigQuery sandbox tables expire after 60 days unless you enable billing.
- Max 500 MB per upload request (change `MAX_CONTENT_LENGTH` in `app.py`).

## Project structure
```
app.py              Flask backend (connection check, upload, list tables)
templates/index.html  Page with 3 tabs
static/app.js, style.css
sample_data/        Example CSV / Excel files
requirements.txt
```

## Publish to your GitHub
```bash
git init
git add .
git commit -m "BigQuery bulk uploader"
git branch -M main
git remote add origin https://github.com/<your-username>/bq-bulk-uploader.git
git push -u origin main
```
(Create an empty repository named `bq-bulk-uploader` on github.com first.)
