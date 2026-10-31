"""BigQuery Bulk Uploader - upload many CSV / Excel files into one BigQuery dataset."""
import io
import re

import pandas as pd
from flask import Flask, jsonify, render_template, request
from google.api_core.exceptions import NotFound
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB per request

WRITE_MODES = {
    "replace": bigquery.WriteDisposition.WRITE_TRUNCATE,  # overwrite table if it exists
    "append": bigquery.WriteDisposition.WRITE_APPEND,     # add rows to existing table
    "fail": bigquery.WriteDisposition.WRITE_EMPTY,        # error if table already has data
}


# ---------- helpers ----------
def clean_name(text):
    """Turn a file/sheet name into a valid BigQuery table name."""
    name = re.sub(r"[^0-9a-zA-Z_]+", "_", text).strip("_")
    return (name or "table")[:200]


def get_client(project_id, location=None):
    if not project_id or not re.fullmatch(r"[a-z][a-z0-9\-]{4,28}[a-z0-9]", project_id):
        raise ValueError("Project ID looks invalid (use the ID, not the project name).")
    return bigquery.Client(project=project_id, location=location or None)


def check_dataset_name(dataset):
    if not dataset or not re.fullmatch(r"[A-Za-z0-9_]{1,1024}", dataset):
        raise ValueError("Dataset name may only contain letters, numbers and underscores.")


def friendly_error(exc):
    if isinstance(exc, DefaultCredentialsError):
        return ("No Google credentials found. Run 'gcloud auth application-default login' "
                "or set GOOGLE_APPLICATION_CREDENTIALS (see README).")
    return getattr(exc, "message", None) or str(exc)


def ensure_dataset(client, project_id, dataset, location):
    ref = f"{project_id}.{dataset}"
    try:
        client.get_dataset(ref)
    except NotFound:
        ds = bigquery.Dataset(ref)
        if location:
            ds.location = location
        client.create_dataset(ds)


def load_csv_bytes(client, data, table_id, mode):
    cfg = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        allow_quoted_newlines=True,
        write_disposition=WRITE_MODES.get(mode, WRITE_MODES["replace"]),
    )
    client.load_table_from_file(io.BytesIO(data), table_id, job_config=cfg).result()
    return client.get_table(table_id).num_rows


# ---------- routes ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/check-connection")
def check_connection():
    body = request.get_json(force=True)
    try:
        project, dataset = body.get("project_id", "").strip(), body.get("dataset", "").strip()
        location = body.get("location", "").strip()
        check_dataset_name(dataset)
        client = get_client(project, location)
        list(client.query("SELECT 1").result())  # proves credentials + permissions work
        try:
            client.get_dataset(f"{project}.{dataset}")
            msg, exists = f"Connected to project '{project}'. Dataset '{dataset}' exists.", True
        except NotFound:
            msg, exists = (f"Connected to project '{project}'. Dataset '{dataset}' does not exist "
                           "yet - it will be created on upload."), False
        return jsonify(ok=True, message=msg, dataset_exists=exists)
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, message=friendly_error(e)), 200


@app.post("/api/upload")
def upload():
    """Handles ONE file per request (the browser sends files one after another)."""
    f = request.files.get("file")
    project = request.form.get("project_id", "").strip()
    dataset = request.form.get("dataset", "").strip()
    location = request.form.get("location", "").strip()
    mode = request.form.get("mode", "replace")
    if not f or not f.filename:
        return jsonify(results=[dict(file="?", table="", rows=0, status="Failed", detail="No file")])

    results = []
    try:
        check_dataset_name(dataset)
        client = get_client(project, location)
        ensure_dataset(client, project, dataset, location)
        fname = f.filename.replace("\\", "/").split("/")[-1]
        base, ext = fname.rsplit(".", 1)[0], fname.rsplit(".", 1)[-1].lower()
        raw = f.read()

        # Build list of (table_name, csv_bytes)
        jobs = []
        if ext in ("csv", "txt"):
            jobs.append((clean_name(base), raw))
        elif ext in ("xlsx", "xlsm", "xls"):
            sheets = pd.read_excel(io.BytesIO(raw), sheet_name=None)
            sheets = {k: v for k, v in sheets.items() if not v.empty}
            for sheet, df in sheets.items():
                name = clean_name(base) if len(sheets) == 1 else clean_name(f"{base}_{sheet}")
                jobs.append((name, df.to_csv(index=False).encode("utf-8")))
            if not jobs:
                raise ValueError("Excel file has no non-empty sheets.")
        else:
            raise ValueError(f"Unsupported file type '.{ext}' (use .csv, .xlsx, .xls)")

        for name, data in jobs:
            try:
                rows = load_csv_bytes(client, data, f"{project}.{dataset}.{name}", mode)
                results.append(dict(file=f.filename, table=name, rows=rows, status="Success", detail=""))
            except Exception as e:  # noqa: BLE001
                results.append(dict(file=f.filename, table=name, rows=0, status="Failed",
                                    detail=friendly_error(e)))
    except Exception as e:  # noqa: BLE001
        results.append(dict(file=f.filename, table="", rows=0, status="Failed", detail=friendly_error(e)))
    return jsonify(results=results)


@app.get("/api/tables")
def list_tables():
    try:
        project = request.args.get("project_id", "").strip()
        dataset = request.args.get("dataset", "").strip()
        check_dataset_name(dataset)
        client = get_client(project, request.args.get("location", "").strip())
        out = []
        for t in client.list_tables(f"{project}.{dataset}"):
            full = client.get_table(t.reference)
            out.append(dict(table=t.table_id, rows=full.num_rows, columns=len(full.schema),
                            modified=full.modified.strftime("%Y-%m-%d %H:%M") if full.modified else ""))
        return jsonify(ok=True, tables=sorted(out, key=lambda x: x["table"]))
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, message=friendly_error(e), tables=[])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
