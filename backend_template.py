from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3, json, os, re, io, tempfile, traceback, math
import pandas as pd
import numpy as np
from groq import Groq
from typing import Optional, List

app = FastAPI(title="BI Dashboard API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "business.db")
_upload_db_path = None


def safe_val(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
    except Exception:
        pass
    return v


def get_schema(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    parts = []
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        n = cur.fetchone()[0]
        cur.execute(f"SELECT * FROM {t} LIMIT 2")
        rows = cur.fetchall()
        col_names = [c[1] for c in cols]
        col_defs = ", ".join([f"{c[1]} ({c[2]})" for c in cols])
        samples = " | ".join([str(dict(zip(col_names, r))) for r in rows])
        parts.append(f"Table: {t} ({n} rows)\n  Columns: {col_defs}\n  Sample: {samples}")
    conn.close()
    return "\n\n".join(parts)


def run_query(sql, db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description] if cur.description else []
    conn.close()
    return rows, cols


def clean_cols(df):
    seen = {}
    new_cols = []
    for c in df.columns:
        c2 = re.sub(r"[^a-zA-Z0-9]+", "_", str(c).strip()).strip("_").lower() or "col"
        base = c2
        if base in seen:
            seen[base] += 1
            c2 = f"{base}_{seen[base]}"
        else:
            seen[base] = 0
        new_cols.append(c2)
    df.columns = new_cols
    return df


def parse_csv(raw_bytes):
    encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
    separators = [",", ";", "\t", "|", "~", "^"]
    best_df = None
    best_cols = 0
    for enc in encodings:
        for sep in separators:
            try:
                trial = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, sep=sep, nrows=10, low_memory=False)
                if len(trial.columns) > best_cols:
                    best_cols = len(trial.columns)
                    best_df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, sep=sep, low_memory=False)
            except Exception:
                pass
    if best_df is None or best_cols <= 1:
        for enc in encodings:
            try:
                df2 = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, sep=None, engine="python", low_memory=False)
                if len(df2.columns) > best_cols:
                    best_cols = len(df2.columns)
                    best_df = df2
            except Exception:
                pass
    return best_df


SYSTEM_PROMPT = (
    "You are an expert BI analyst and SQL expert.\n"
    "RULES:\n"
    "- Use ONLY the exact column names shown in the schema. Never invent column names.\n"
    "- Only generate SELECT queries. Never INSERT/UPDATE/DELETE/DROP.\n"
    "- For monthly grouping use strftime('%Y-%m', date_col), for yearly strftime('%Y', date_col).\n"
    "- Always add LIMIT 200 to queries.\n"
    "- line=time-series | bar=categories | pie=part-of-whole max 8 slices | scatter=correlations | histogram=distribution\n"
    "- If data cannot answer the question, set cannot_answer=true.\n"
    "Respond ONLY with valid JSON, no markdown, no code fences:\n"
    '{"charts":[{"title":"...","chart_type":"bar","sql":"SELECT ...","x_column":"col","y_column":"col","color_column":null,"description":"...","insight":"..."}],"summary":"...","cannot_answer":false,"cannot_answer_reason":""}'
)


class QueryRequest(BaseModel):
    prompt: str
    conversation_history: Optional[List[dict]] = []
    use_uploaded_db: Optional[bool] = False


class QueryResponse(BaseModel):
    success: bool
    charts: List[dict]
    summary: str
    sql_queries: List[str]
    error: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/schema")
def schema_endpoint(use_uploaded: bool = False):
    db = _upload_db_path if (use_uploaded and _upload_db_path) else DB_PATH
    return {"schema": get_schema(db)}


@app.post("/inspect-file")
async def inspect_file(file: UploadFile = File(...)):
    raw = await file.read()
    text = ""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            text = raw[:600].decode(enc)
            break
        except Exception:
            text = repr(raw[:200])
    first_line = text.split("\n")[0][:300] if "\n" in text else text[:300]
    delim_counts = {d: first_line.count(d) for d in [",", ";", "\t", "|", "~"]}
    return {
        "file_size": len(raw),
        "first_500_chars": text[:500],
        "first_line": first_line,
        "delimiter_counts": delim_counts,
        "likely_delimiter": max(delim_counts, key=delim_counts.get),
    }


@app.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    global _upload_db_path
    try:
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty file")
        df = parse_csv(raw)
        if df is None or df.empty:
            raise HTTPException(status_code=400, detail="Could not parse CSV")
        df = clean_cols(df)
        print(f"[UPLOAD] columns={list(df.columns)}, shape={df.shape}")
        data_dir = os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        )
        os.makedirs(data_dir, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=data_dir)
        _upload_db_path = tmp.name
        tmp.close()
        tname = (
            re.sub(r"[^a-zA-Z0-9_]", "_", os.path.splitext(file.filename)[0])
            .strip("_")
            .lower()
            or "data"
        )
        conn = sqlite3.connect(_upload_db_path)
        df.to_sql(tname, conn, if_exists="replace", index=False)
        conn.close()
        preview = [
            {col: safe_val(val) for col, val in zip(df.columns, row)}
            for row in df.head(5).itertuples(index=False)
        ]
        return {
            "success": True,
            "table_name": tname,
            "rows": len(df),
            "columns": list(df.columns),
            "preview": preview,
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    try:
        db = _upload_db_path if (request.use_uploaded_db and _upload_db_path) else DB_PATH
        schema = get_schema(db)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in (request.conversation_history or [])[-6:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({
            "role": "user",
            "content": "DATABASE SCHEMA:\n" + schema + "\n\nQUESTION: " + request.prompt,
        })
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```json\s*|^```\s*|\s*```$", "", raw).strip()
        try:
            parsed = json.loads(raw)
        except Exception as e:
            return QueryResponse(
                success=False, charts=[], summary="", sql_queries=[],
                error=f"Parse error: {e}. Raw: {raw[:300]}"
            )
        if parsed.get("cannot_answer"):
            return QueryResponse(
                success=False, charts=[], summary="", sql_queries=[],
                error=parsed.get("cannot_answer_reason", "Cannot answer from available data."),
            )
        charts_out, sqls = [], []
        for spec in parsed.get("charts", []):
            sql = spec.get("sql", "").strip()
            if not sql:
                continue
            sqls.append(sql)
            try:
                rows, cols = run_query(sql, db)
                data = [{col: safe_val(val) for col, val in zip(cols, r)} for r in rows]
            except Exception as qe:
                data, cols = [], []
                spec["insight"] = f"Query error: {qe}"
            charts_out.append({**spec, "data": data, "columns": cols, "sql": sql})
        return QueryResponse(
            success=True,
            charts=charts_out,
            summary=parsed.get("summary", ""),
            sql_queries=sqls,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sample-queries")
def sample_queries():
    return {
        "queries": [
            "Show me monthly sales revenue for 2024 broken down by product category",
            "Which regions are performing best? Compare total revenue and profit",
            "Top 5 products by revenue and their profit margins",
            "Compare sales across channels: Online vs In-Store vs Partner",
            "Customer segment breakdown and revenue contribution",
            "Marketing campaign performance: budget vs revenue by channel",
            "Employee salary distribution by department",
        ]
    }
