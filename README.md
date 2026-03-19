# 📊 BI Dashboard AI — Conversational Business Intelligence

> Ask any question about your data in plain English. Get instant, interactive charts — no SQL, no coding required.



---

## 🎯 What It Does

BI Dashboard AI lets non-technical users — executives, analysts, anyone — upload a CSV file and immediately start asking business questions in plain English. The system:

1. **Understands** your question using LLaMA 3.3 70B via Groq
2. **Generates** accurate SQL against your actual data
3. **Validates** the SQL before running it (no hallucinated columns)
4. **Visualizes** results as interactive Plotly charts
5. **Summarizes** findings in plain English — no jargon

---

## ✨ Features

| Feature | Description |
|---|---|
| 💬 Conversational UI | Chat-style interface with message history and follow-up questions |
| 📁 CSV Upload | Upload any CSV — auto-detects encoding and delimiter |
| 📊 Auto Chart Selection | Picks bar, line, pie, scatter, histogram based on data shape |
| 🔒 Hallucination Prevention | 3-layer validation — prompt injection, SQLite EXPLAIN, empty result detection |
| 📝 Plain-English Summaries | Non-technical summaries with real statistics from actual data |
| 🔢 Single Value Cards | Clean stat cards for single-value answers instead of broken charts |
| ❓ Vague Query Handling | Asks for clarification with suggested questions instead of guessing |
| ⬇️ Data Export | Download any chart's data as CSV |

---

## 🏗️ Architecture

```
User (Natural Language)
         │
         ▼
┌─────────────────────┐
│   Streamlit UI      │  ← Port 8501  (frontend_template.py)
│   Chat interface    │
│   Plotly charts     │
└──────────┬──────────┘
           │ HTTP POST /query
           ▼
┌─────────────────────┐
│   FastAPI Backend   │  ← Port 8000  (backend_template.py)
└────┬────────────────┘
     │
     ├──► Groq API (LLaMA 3.3 70B)
     │         └── Generates SQL + chart spec
     │
     ├──► SQLite EXPLAIN validation
     │         └── Rejects hallucinated column names
     │
     └──► SQLite Query Execution
               └── Returns real data → Plotly → User
```

**Pipeline:** `Text → Groq/LLaMA → SQL → Validate → SQLite → Plotly → Streamlit`

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- A Groq API key (free at [console.groq.com](https://console.groq.com))

### Run in one command

```bash
python run.py
```

That's it. The script will:
1. Install all dependencies automatically
2. Copy backend and frontend files
3. Start FastAPI on port 8000
4. Start Streamlit on port 8501
5. Open your browser to `http://localhost:8501`

### Files required (keep all three together)
```
your-folder/
├── run.py                  ← Entry point
├── backend_template.py     ← FastAPI backend
└── frontend_template.py    ← Streamlit frontend
```

---

## 📁 Project Structure

```
├── run.py                  # Single-command launcher
├── backend_template.py     # FastAPI app — /query, /upload-csv, /schema
├── frontend_template.py    # Streamlit chat UI with Plotly charts
├── backend/
│   └── main.py             # Auto-generated from backend_template.py
├── frontend/
│   └── app.py              # Auto-generated from frontend_template.py
└── data/
    └── *.db                # Uploaded CSV stored as SQLite
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| LLM | [Groq](https://groq.com) — LLaMA 3.3 70B Versatile |
| Backend | FastAPI + Uvicorn |
| Database | SQLite (auto-created from uploaded CSV) |
| Frontend | Streamlit |
| Charts | Plotly Express + Graph Objects |
| Data Processing | Pandas + NumPy |

---

## 💬 Example Queries

**Simple**
> "What is the average price of all vehicles?"

**Intermediate**
> "Show me prices of 3 Series vehicles in 2018 broken down by fuel type"

**Complex**
> "Show me the trend of average mileage and price over the years for diesel vehicles"

**Follow-up (Conversational)**
> "Now filter this to only show vehicles above 30 MPG"

**Hallucination test**
> "Show me total sales revenue by region" → blocked with explanation

**Vague query**
> "Show me something cool" → asks for clarification with suggestions

---

## 🔒 Hallucination Prevention

The system uses **3 hard gates** to prevent the AI from making up data:

1. **Prompt injection** — exact column names are injected into every prompt so the LLM sees the real schema
2. **SQLite EXPLAIN validation** — every generated SQL is validated by SQLite itself before execution; invalid column/table names are caught and blocked
3. **Empty result detection** — if a valid SQL returns zero rows, the user is informed rather than shown an empty chart

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/schema` | View current database schema |
| POST | `/upload-csv` | Upload CSV → SQLite |
| POST | `/query` | Natural language → charts |
| POST | `/inspect-file` | Debug file parsing |
| GET | `/sample-queries` | Get example questions |

### POST /query

```json
{
  "prompt": "Show me average price by model",
  "conversation_history": [],
  "use_uploaded_db": true
}
```

---

## ⚙️ Configuration

Update the Groq API key in `backend_template.py`:

```python
GROQ_API_KEY = "your-groq-api-key-here"
```

---

## 📊 Evaluation Criteria Coverage

| Criterion | Implementation |
|---|---|
| **Accuracy — Data Retrieval (40%)** | Schema-aware SQL with unique value injection and TRIM/LIKE for text matching |
| **Accuracy — Chart Selection** | LLM instructed with chart type rules; line for time-series, pie for part-of-whole, etc. |
| **Accuracy — Error Handling** | 3-layer hallucination prevention; vague queries trigger clarification |
| **Aesthetics — Design (30%)** | Clean light theme, gradient header, card-based layout |
| **Aesthetics — Interactivity** | Plotly tooltips, zoom, pan, legend toggle on every chart |
| **Aesthetics — User Flow** | Loading spinner, chat-style messages, instant feedback |
| **Architecture (30%)** | Full Text→LLM→SQL→SQLite→Plotly pipeline |
| **Prompt Engineering** | Schema injection, unique value listing, TRIM/LIKE rules, temperature=0 |
| **Hallucination Handling** | Explicitly reports when data is unavailable; never fabricates |
| **Bonus — Follow-ups (+10%)** | Full conversation history passed to LLM each turn |
| **Bonus — CSV Upload (+20%)** | Upload any CSV with auto encoding/delimiter detection |

---

## 🙏 Built With

- [Groq](https://groq.com) — blazing fast LLM inference
- [Meta LLaMA 3.3](https://ai.meta.com/blog/llama-3/) — open source LLM
- [Streamlit](https://streamlit.io) — rapid frontend
- [FastAPI](https://fastapi.tiangolo.com) — modern Python API
- [Plotly](https://plotly.com) — interactive charts

---

*Built for the Qualifier — Conversational AI for Instant Business Intelligence Dashboards*
