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


def get_table_columns(db_path):
    """Returns dict of {table_name: [col1, col2, ...]}"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    result = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        result[t] = [c[1] for c in cur.fetchall()]
    conn.close()
    return result


def extract_sql_identifiers(sql):
    """Extract all word tokens from SQL that could be column/table names."""
    # Remove string literals and comments
    sql_clean = re.sub(r"'[^']*'", "", sql)
    sql_clean = re.sub(r"--[^\n]*", "", sql_clean)
    # Extract words (potential identifiers)
    keywords = {
        "select","from","where","group","by","order","having","limit","join",
        "left","right","inner","outer","on","as","and","or","not","in","like",
        "between","is","null","count","sum","avg","max","min","distinct",
        "case","when","then","else","end","strftime","asc","desc","int",
        "text","real","integer","varchar","true","false"
    }
    tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", sql_clean)
    return [t.lower() for t in tokens if t.lower() not in keywords]


def validate_sql_against_schema(sql, db_path):
    """
    Hard validation: run EXPLAIN QUERY PLAN in SQLite.
    If SQLite itself rejects it, the column/table names are wrong.
    Returns (is_valid: bool, error: str|None)
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(f"EXPLAIN QUERY PLAN {sql}")
        conn.close()
        return True, None
    except Exception as e:
        return False, str(e)


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


def build_strict_prompt(schema, table_cols, question):
    """
    Build a prompt that makes hallucination structurally impossible:
    - Pastes the EXACT column list the model must choose from
    - Tells it to output cannot_answer if anything is unclear
    """
    col_block = "EXACT COLUMNS AVAILABLE (you may ONLY use these — no others exist):\n"
    for tname, cols in table_cols.items():
        col_block += f"  Table `{tname}`: {', '.join(cols)}\n"

    return (
        "You are a SQL expert connected to a SQLite database. "
        "Your job is to answer the user's question ONLY using the data that actually exists.\n\n"
        "=== STRICT RULES ===\n"
        "1. You may ONLY reference tables and columns listed below. Nothing else exists.\n"
        "2. If the question mentions concepts (e.g. 'sales', 'revenue', 'profit') that have NO matching column, "
        "you MUST set cannot_answer=true. Do NOT map them to unrelated columns.\n"
        "3. Never invent column names. Never guess. Never approximate.\n"
        "4. Your summary and insight must ONLY describe what the SQL query returns — no invented statistics.\n"
        "5. Only write SELECT queries. Never INSERT/UPDATE/DELETE/DROP.\n"
        "6. Always add LIMIT 200.\n\n"
        + col_block + "\n"
        "=== DATABASE SCHEMA (with sample rows) ===\n"
        + schema + "\n\n"
        "=== CHART TYPE GUIDE ===\n"
        "line=trends over time | bar=compare categories | pie=parts of whole (max 8) | "
        "scatter=correlation | histogram=distribution\n\n"
        "=== OUTPUT FORMAT ===\n"
        "Respond ONLY with valid JSON, no markdown:\n"
        '{"charts":[{"title":"...","chart_type":"bar","sql":"SELECT ...","x_column":"exact_col_name","y_column":"exact_col_name","color_column":null,"description":"...","insight":"describe pattern without inventing numbers"}],'
        '"summary":"factual summary of what the data shows","cannot_answer":false,"cannot_answer_reason":""}\n\n'
        "=== USER QUESTION ===\n"
        + question
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
    if not _upload_db_path:
        raise HTTPException(status_code=400, detail="No data uploaded yet.")
    return {"schema": get_schema(_upload_db_path)}


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
            .strip("_").lower() or "data"
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
        print(f"[QUERY] prompt={request.prompt!r}, use_uploaded={request.use_uploaded_db}, db={_upload_db_path}")

        if not _upload_db_path:
            return QueryResponse(success=False, charts=[], summary="", sql_queries=[],
                                 error="No data uploaded. Please upload a CSV file first.")

        db = _upload_db_path
        schema = get_schema(db)
        table_cols = get_table_columns(db)
        print(f"[QUERY] tables={list(table_cols.keys())}, cols={table_cols}")

        # Build the full prompt as a single user message
        full_prompt = build_strict_prompt(schema, table_cols, request.prompt)

        # Only pass clean non-empty history — never pass empty content to Groq
        messages = []
        for h in (request.conversation_history or [])[-4:]:
            role = h.get("role", "user")
            content = (h.get("content") or "").strip()
            if content and role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

        # Always append current question last
        messages.append({"role": "user", "content": full_prompt})

        print(f"[QUERY] sending {len(messages)} messages to Groq")

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.0,
            max_tokens=4096,
        )
        raw = resp.choices[0].message.content.strip()
        print(f"[QUERY] raw response (first 600):\n{raw[:600]}")

        # Extract JSON — handle any text before/after it
        json_match = re.search(r"[{][\s\S]*[}]", raw)
        if not json_match:
            return QueryResponse(success=False, charts=[], summary="", sql_queries=[],
                                 error=f"AI did not return valid JSON. Raw: {raw[:300]}")
        raw_json = json_match.group(0)

        try:
            parsed = json.loads(raw_json)
        except Exception as e:
            return QueryResponse(success=False, charts=[], summary="", sql_queries=[],
                                 error=f"JSON parse error: {e}. Raw: {raw_json[:300]}")

        print(f"[QUERY] parsed keys={list(parsed.keys())}, cannot_answer={parsed.get('cannot_answer')}, charts={len(parsed.get('charts',[]))}")

        if parsed.get("cannot_answer"):
            return QueryResponse(success=False, charts=[], summary="", sql_queries=[],
                                 error=f"Cannot answer: {parsed.get('cannot_answer_reason','No reason given.')}")

        charts_out, sqls = [], []
        all_empty = True

        for i, spec in enumerate(parsed.get("charts", [])):
            sql = (spec.get("sql") or "").strip()
            print(f"[QUERY] chart[{i}] type={spec.get('chart_type')} sql={sql[:120]}")
            if not sql:
                continue

            # Validate SQL with SQLite EXPLAIN
            is_valid, val_err = validate_sql_against_schema(sql, db)
            print(f"[QUERY] chart[{i}] valid={is_valid} err={val_err}")
            if not is_valid:
                return QueryResponse(
                    success=False, charts=[], summary="", sql_queries=[sql],
                    error=(
                        f"AI used a column/table that does not exist. SQLite says: {val_err}. "
                        f"Available: " + "; ".join([f"{t}({','.join(c)})" for t, c in table_cols.items()])
                    )
                )

            sqls.append(sql)
            try:
                rows, cols = run_query(sql, db)
                data = [{col: safe_val(val) for col, val in zip(cols, r)} for r in rows]
                print(f"[QUERY] chart[{i}] returned {len(data)} rows, cols={cols}")
                if data:
                    all_empty = False
            except Exception as qe:
                print(f"[QUERY] chart[{i}] query error: {qe}")
                data, cols = [], []
                spec["insight"] = f"Query error: {qe}"

            charts_out.append({**spec, "data": data, "columns": cols, "sql": sql})

        if not charts_out:
            return QueryResponse(success=False, charts=[], summary="", sql_queries=sqls,
                                 error="AI returned no charts. Try rephrasing your question.")

        if all_empty:
            return QueryResponse(success=False, charts=[], summary="", sql_queries=sqls,
                                 error="Query returned no data. Try a broader question.")

        return QueryResponse(
            success=True,
            charts=charts_out,
            summary=parsed.get("summary", "Here are your results:"),
            sql_queries=sqls,
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sample-queries")
def sample_queries():
    return {
        "queries": [
            "Show me the distribution of values in each column",
            "What are the top 10 rows by the most numeric column?",
            "Show a count breakdown of each unique category",
            "Which category appears most frequently?",
            "Show me trends over time if a date column exists",
            "Compare averages across different groups",
            "Show the correlation between two numeric columns",
        ]
    }


@app.post("/debug-csv")
async def debug_csv(file: UploadFile = File(...)):
    raw = await file.read()
    results = []
    separators = {"comma": ",", "semicolon": ";", "tab": chr(9), "pipe": "|", "tilde": "~"}
    for enc in ["utf-8", "latin-1", "cp1252"]:
        for sep_name, sep in separators.items():
            try:
                trial = pd.read_csv(io.BytesIO(raw), encoding=enc, sep=sep, nrows=3, low_memory=False)
                results.append({
                    "encoding": enc, "separator": sep_name,
                    "columns": list(trial.columns)[:10],
                    "num_cols": len(trial.columns),
                    "first_row": [str(v)[:50] for v in trial.iloc[0].tolist()[:5]] if len(trial) > 0 else []
                })
            except Exception as ex:
                results.append({"encoding": enc, "separator": sep_name, "error": str(ex)[:100]})
    raw_preview = ""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            raw_preview = raw[:800].decode(enc)
            break
        except Exception:
            pass
    successes = sorted([r for r in results if "num_cols" in r], key=lambda x: x["num_cols"], reverse=True)
    return {
        "file_size_bytes": len(raw),
        "top_parsings": successes[:5],
        "raw_first_800_chars": raw_preview,
        "first_line": raw_preview.split(chr(10))[0][:500] if chr(10) in raw_preview else raw_preview[:500],
    }
