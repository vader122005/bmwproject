import streamlit as st
import requests
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import time

st.set_page_config(page_title="BI Dashboard AI", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, .stApp { background: #f5f7fa !important; font-family: 'Inter', sans-serif; }
[data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #e2e8f0 !important; }
[data-testid="stSidebar"] * { color: #374151 !important; }
.block-container { padding-top: 1.5rem !important; }
.app-header { background: linear-gradient(135deg,#4f46e5,#7c3aed); padding:1.4rem 2rem; border-radius:16px; margin-bottom:1.5rem; display:flex; align-items:center; gap:1rem; box-shadow:0 4px 20px rgba(79,70,229,0.3); }
.app-header h1 { color:white; margin:0; font-size:1.6rem; font-weight:700; }
.app-header p  { color:rgba(255,255,255,0.85); margin:0; font-size:0.88rem; }
.bubble-user { display:flex; justify-content:flex-end; margin-bottom:1.2rem; }
.bubble-user .msg { background:linear-gradient(135deg,#4f46e5,#7c3aed); color:white; padding:0.9rem 1.2rem; border-radius:18px 18px 4px 18px; max-width:70%; font-size:0.93rem; line-height:1.5; box-shadow:0 2px 8px rgba(79,70,229,0.25); }
.bubble-user .avatar { width:36px; height:36px; border-radius:50%; background:linear-gradient(135deg,#4f46e5,#7c3aed); display:flex; align-items:center; justify-content:center; color:white; font-size:1rem; margin-left:0.6rem; flex-shrink:0; }
.bubble-ai { display:flex; justify-content:flex-start; margin-bottom:0.8rem; }
.bubble-ai .avatar { width:36px; height:36px; border-radius:50%; background:linear-gradient(135deg,#06b6d4,#3b82f6); display:flex; align-items:center; justify-content:center; color:white; font-size:1rem; margin-right:0.6rem; flex-shrink:0; }
.bubble-ai .msg { background:#f1f5f9; color:#1e293b; padding:0.9rem 1.2rem; border-radius:4px 18px 18px 18px; max-width:80%; font-size:0.93rem; line-height:1.6; border:1px solid #e2e8f0; }
.metric-card { background:white; border:1px solid #e2e8f0; border-radius:12px; padding:1rem; text-align:center; box-shadow:0 1px 4px rgba(0,0,0,0.04); }
.metric-value { font-size:1.5rem; font-weight:700; color:#4f46e5; }
.metric-label { font-size:0.72rem; color:#94a3b8; text-transform:uppercase; letter-spacing:0.06em; margin-top:0.2rem; }
.insight-pill { background:#eff6ff; border-left:3px solid #4f46e5; border-radius:0 8px 8px 0; padding:0.6rem 1rem; font-size:0.82rem; color:#3730a3; margin-top:0.4rem; line-height:1.5; }
.chart-summary { background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:0.8rem 1rem; font-size:0.83rem; color:#475569; margin-top:0.5rem; line-height:1.6; }
.chart-summary strong { color:#1e293b; }
.sql-block { background:#1e1e2e; border-radius:8px; padding:0.8rem 1rem; font-family:'Courier New',monospace; font-size:0.78rem; color:#a6e3a1; white-space:pre-wrap; overflow-x:auto; }
.stTextArea textarea { background:#f8fafc !important; color:#1e293b !important; border:1.5px solid #e2e8f0 !important; border-radius:10px !important; font-size:0.93rem !important; }
[data-testid="stFormSubmitButton"] > button { background:linear-gradient(135deg,#4f46e5,#7c3aed) !important; color:white !important; border:none !important; border-radius:10px !important; font-weight:600 !important; width:100% !important; }
.stButton > button { background:#f8fafc !important; color:#475569 !important; border:1px solid #e2e8f0 !important; border-radius:8px !important; font-size:0.8rem !important; text-align:left !important; width:100% !important; }
.stButton > button:hover { background:#ede9fe !important; border-color:#4f46e5 !important; color:#4f46e5 !important; }
.db-badge { display:inline-block; background:#eff6ff; color:#3730a3; border:1px solid #bfdbfe; border-radius:20px; padding:0.2rem 0.75rem; font-size:0.75rem; font-weight:500; margin-top:0.3rem; }
.upload-prompt { background:white; border:2px dashed #c7d2fe; border-radius:16px; padding:3rem 2rem; text-align:center; }
.upload-prompt h2 { color:#4f46e5; margin-bottom:0.5rem; font-size:1.3rem; }
.upload-prompt p { color:#64748b; font-size:0.9rem; line-height:1.6; margin:0; }
#MainMenu, footer { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

BACKEND = "http://localhost:8000"
PALETTE = ["#4f46e5","#7c3aed","#06b6d4","#10b981","#f59e0b","#ef4444","#ec4899","#8b5cf6"]

for k, v in [("messages",[]),("uploaded_table",None),("query_input",""),("last_uploaded_key",None),("uploaded_columns",[]),("uploaded_preview",[])]:
    if k not in st.session_state:
        st.session_state[k] = v

def fmt(val):
    try:
        v = float(val)
        if v >= 1e6: return f"${v/1e6:.2f}M"
        if v >= 1e3: return f"${v/1e3:.1f}K"
        if v == int(v): return f"{int(v):,}"
        return f"{v:,.2f}"
    except: return str(val)

def build_chart(cd):
    data = cd.get("data", [])
    if not data:
        fig = go.Figure()
        fig.add_annotation(text="No data returned", x=.5, y=.5, showarrow=False,
                           font={"color":"#94a3b8","size":13})
        fig.update_layout(paper_bgcolor="white", plot_bgcolor="white", height=280,
                          xaxis={"visible":False}, yaxis={"visible":False})
        return fig
    df = pd.DataFrame(data)
    ct = cd.get("chart_type","bar")
    xc = cd.get("x_column") or df.columns[0]
    yc = cd.get("y_column") or (df.columns[1] if len(df.columns)>1 else df.columns[0])
    cc = cd.get("color_column")
    if xc not in df.columns: xc = df.columns[0]
    if yc not in df.columns: yc = df.columns[1] if len(df.columns)>1 else df.columns[0]
    if cc and cc not in df.columns: cc = None
    try:
        df = df.dropna(subset=[c for c in [xc, yc] if c in df.columns])
    except Exception: pass
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No valid data", x=.5, y=.5, showarrow=False, font={"color":"#94a3b8","size":13})
        fig.update_layout(paper_bgcolor="white", plot_bgcolor="white", height=280,
                          xaxis={"visible":False}, yaxis={"visible":False})
        return fig
    layout = dict(
        paper_bgcolor="white", plot_bgcolor="#fafafa",
        font={"color":"#334155","family":"Inter,sans-serif","size":12},
        title={"text":cd.get("title",""),"font":{"color":"#1e293b","size":14},"x":0.02},
        margin={"l":50,"r":20,"t":45,"b":50}, height=340,
        legend={"bgcolor":"rgba(0,0,0,0)","font":{"color":"#475569","size":11}},
        xaxis={"gridcolor":"#f1f5f9","linecolor":"#e2e8f0","tickfont":{"color":"#64748b"},"tickangle":-30},
        yaxis={"gridcolor":"#f1f5f9","linecolor":"#e2e8f0","tickfont":{"color":"#64748b"}},
        hoverlabel={"bgcolor":"#1e293b","font_size":12,"font_color":"white"},
    )
    kw = dict(color_discrete_sequence=PALETTE)
    try:
        if ct == "bar":
            fig = px.bar(df,x=xc,y=yc,color=cc,barmode="group",**kw) if cc else px.bar(df,x=xc,y=yc,**kw)
            fig.update_traces(marker_line_width=0)
        elif ct == "line":
            fig = px.line(df,x=xc,y=yc,color=cc,markers=True,**kw) if cc else px.line(df,x=xc,y=yc,markers=True,color_discrete_sequence=["#4f46e5"])
            fig.update_traces(line_width=2.5,marker_size=6)
        elif ct == "area":
            fig = px.area(df,x=xc,y=yc,color=cc,**kw) if cc else px.area(df,x=xc,y=yc,color_discrete_sequence=["#4f46e5"])
        elif ct == "pie":
            fig = px.pie(df,names=xc,values=yc,color_discrete_sequence=PALETTE,hole=0.38)
            fig.update_traces(textposition="inside",textinfo="percent+label",
                              marker=dict(line=dict(color="white",width=2)))
        elif ct == "scatter":
            fig = px.scatter(df,x=xc,y=yc,color=cc,**kw)
            fig.update_traces(marker_size=9,marker_opacity=0.75)
        elif ct == "histogram":
            fig = px.histogram(df,x=xc,nbins=20,color_discrete_sequence=["#4f46e5"])
        else:
            fig = px.bar(df,x=xc,y=yc,**kw)
        fig.update_layout(**layout)
        return fig
    except Exception as e:
        fig = go.Figure()
        fig.add_annotation(text=f"Chart error: {e}",x=.5,y=.5,showarrow=False,font={"color":"#ef4444","size":11})
        fig.update_layout(paper_bgcolor="white",plot_bgcolor="white",height=280)
        return fig

def chart_data_summary(ch):
    """Generate a plain-English, non-technical summary from chart data."""
    data = ch.get("data", [])
    if not data:
        return None
    df = pd.DataFrame(data)
    xc = ch.get("x_column") or df.columns[0]
    yc = ch.get("y_column") or (df.columns[1] if len(df.columns) > 1 else df.columns[0])
    if xc not in df.columns or yc not in df.columns:
        return None
    ct = ch.get("chart_type", "bar")
    title = ch.get("title", "This chart")
    xc_label = xc.replace("_", " ").title()
    yc_label = yc.replace("_", " ").title()
    lines = []
    try:
        if ct in ["bar", "line", "area"] and pd.api.types.is_numeric_dtype(df[yc]):
            total = df[yc].sum()
            avg = df[yc].mean()
            max_row = df.loc[df[yc].idxmax()]
            min_row = df.loc[df[yc].idxmin()]
            n = len(df)
            lines.append(
                f"This chart compares **{yc_label}** across **{n} different {xc_label}s**."
            )
            lines.append(
                f"The combined total {yc_label} across all entries is **{fmt(total)}**, "
                f"with an average of **{fmt(avg)}** per {xc_label}."
            )
            lines.append(
                f"**{max_row[xc]}** stands out as the top performer with a {yc_label} of **{fmt(max_row[yc])}** — "
                f"the highest in this view."
            )
            lines.append(
                f"On the other end, **{min_row[xc]}** has the lowest {yc_label} at **{fmt(min_row[yc])}**."
            )
            # Gap insight
            gap = max_row[yc] - min_row[yc]
            if gap > 0:
                lines.append(
                    f"The gap between the highest and lowest is **{fmt(gap)}**, "
                    f"which indicates {'a wide spread' if gap > avg else 'relatively close values'} in the data."
                )

        elif ct == "pie" and pd.api.types.is_numeric_dtype(df[yc]):
            total = df[yc].sum()
            top = df.loc[df[yc].idxmax()]
            bottom = df.loc[df[yc].idxmin()]
            n = len(df)
            lines.append(
                f"This chart breaks down the total **{yc_label}** across **{n} categories of {xc_label}**."
            )
            lines.append(
                f"**{top[xc]}** is the largest category, making up **{top[yc]/total*100:.1f}%** "
                f"of the total ({fmt(top[yc])} out of {fmt(total)})."
            )
            lines.append(
                f"**{bottom[xc]}** is the smallest category at just **{bottom[yc]/total*100:.1f}%** ({fmt(bottom[yc])})."
            )
            # Top 3
            top3 = df.nlargest(min(3, n), yc)
            top3_names = ", ".join([f"**{r[xc]}** ({r[yc]/total*100:.0f}%)" for _, r in top3.iterrows()])
            if n > 3:
                lines.append(f"The top contributors are: {top3_names}.")

        elif ct == "histogram":
            num = pd.to_numeric(df[xc], errors="coerce").dropna()
            if len(num):
                lines.append(
                    f"This chart shows how **{xc_label}** values are distributed across **{len(num)} records**."
                )
                lines.append(
                    f"Values range from a minimum of **{fmt(num.min())}** to a maximum of **{fmt(num.max())}**."
                )
                lines.append(
                    f"The average (mean) is **{fmt(num.mean())}** and the midpoint (median) is **{fmt(num.median())}**, "
                    f"{'suggesting the data is fairly balanced' if abs(num.mean()-num.median()) < num.std()*0.3 else 'suggesting the data is skewed — a few very high or low values are pulling the average'}."
                )

        elif ct == "scatter":
            n = len(df)
            lines.append(
                f"This chart plots **{n} data points** to explore the relationship between "
                f"**{xc_label}** and **{yc_label}**."
            )
            if pd.api.types.is_numeric_dtype(df[xc]) and pd.api.types.is_numeric_dtype(df[yc]):
                corr = df[xc].corr(df[yc])
                pct = abs(corr) * 100
                if abs(corr) > 0.7:
                    strength = "a strong"
                    meaning = f"meaning as {xc_label} goes up, {yc_label} tends to {'go up' if corr > 0 else 'go down'} consistently"
                elif abs(corr) > 0.4:
                    strength = "a moderate"
                    meaning = f"there is a noticeable but not definitive trend between the two"
                else:
                    strength = "a weak"
                    meaning = f"the two variables do not appear strongly related"
                direction = "positive" if corr > 0 else "negative"
                lines.append(
                    f"The data shows **{strength} {direction} relationship** (correlation: {corr:.2f}, ~{pct:.0f}% aligned), "
                    f"{meaning}."
                )

        elif ct == "line" and pd.api.types.is_numeric_dtype(df[yc]):
            # Already handled above with bar/area but add trend context
            pass

    except Exception:
        pass

    return "<br>".join(lines) if lines else None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""<div style='text-align:center;padding:1rem 0'>
        <div style='font-size:2.4rem'>📊</div>
        <div style='color:#4f46e5;font-weight:700;font-size:1.05rem'>BI Dashboard AI</div>
        <div style='color:#94a3b8;font-size:0.73rem'>Groq x LLaMA 3.3</div></div>""",
        unsafe_allow_html=True)
    st.divider()

    st.markdown("**📁 Upload Your Data**")
    uf = st.file_uploader("Drop a CSV file", type=["csv"], label_visibility="collapsed")
    if uf:
        # Only upload if this is a NEW file (different name or size from last upload)
        file_key = f"{uf.name}_{len(uf.getvalue())}"
        if st.session_state.get("last_uploaded_key") != file_key:
            with st.spinner("Processing..."):
                try:
                    fb = uf.getvalue()
                    r = requests.post(f"{BACKEND}/upload-csv",
                                      files={"file": (uf.name, fb, "text/csv")}, timeout=30)
                    if r.status_code == 200:
                        res = r.json()
                        ncols = len(res["columns"])
                        nrows = res["rows"]
                        if ncols <= 1:
                            insp = requests.post(f"{BACKEND}/inspect-file",
                                                 files={"file": (uf.name, fb, "text/csv")}, timeout=10)
                            if insp.status_code == 200:
                                d = insp.json()
                                st.warning(f"Only {ncols} column found. Delimiter counts: {d['delimiter_counts']}")
                                with st.expander("Raw file preview"):
                                    st.code(d["first_500_chars"])
                            else:
                                st.warning(f"Only {ncols} column detected")
                        else:
                            st.success(f"✅ **{res['table_name']}** — {nrows:,} rows x {ncols} cols")
                        # Save state — clear chat only for genuinely new file
                        st.session_state.last_uploaded_key = file_key
                        st.session_state.uploaded_table = res["table_name"]
                        st.session_state.uploaded_columns = res["columns"]
                        st.session_state.uploaded_preview = res["preview"]
                        st.session_state.messages = []
                    else:
                        try: err = r.json().get("detail", r.text)
                        except Exception: err = r.text
                        st.error(f"Upload failed: {err}")
                except Exception as e:
                    st.error(f"Error: {e}")

        # Always show file info if we have it
        if st.session_state.get("uploaded_columns"):
            with st.expander("📋 Columns"):
                st.code(", ".join(st.session_state.uploaded_columns))
        if st.session_state.get("uploaded_preview"):
            with st.expander("Preview"):
                st.dataframe(pd.DataFrame(st.session_state.uploaded_preview), use_container_width=True)

    if st.session_state.uploaded_table:
        st.markdown(f"<div class='db-badge'>🗂️ {st.session_state.uploaded_table}</div>",
                    unsafe_allow_html=True)

    st.divider()

    if st.session_state.uploaded_table:
        st.markdown("**💡 Sample questions**")
        try:
            samples = requests.get(f"{BACKEND}/sample-queries", timeout=5).json().get("queries", [])
        except Exception:
            samples = ["Show the distribution of values", "Top 10 rows by numeric column"]
        for sq in samples:
            label = sq[:54] + "..." if len(sq) > 57 else sq
            if st.button(label, key=f"sq_{sq[:18]}", help=sq):
                st.session_state.query_input = sq
                st.rerun()
        st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Turns", len([m for m in st.session_state.messages if m["role"] == "user"]))
    with c2:
        st.metric("Charts", sum(len(m.get("charts", [])) for m in st.session_state.messages if m["role"] == "assistant"))
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("""<div class='app-header'>
    <div style='font-size:2rem'>📊</div>
    <div><h1>Conversational BI Dashboard</h1>
    <p>Upload your CSV and ask any question — get instant interactive charts</p></div>
</div>""", unsafe_allow_html=True)

# No data uploaded yet — show prominent upload prompt
if not st.session_state.uploaded_table:
    st.markdown("""<div class='upload-prompt'>
        <div style='font-size:3rem;margin-bottom:1rem'>📂</div>
        <h2>Upload your data to get started</h2>
        <p>Use the <strong>Upload Your Data</strong> panel on the left to upload a CSV file.<br>
        Once uploaded, you can ask any question about your data in plain English<br>
        and get instant interactive charts — no SQL knowledge needed.</p>
    </div>""", unsafe_allow_html=True)
    st.stop()

# Chat messages
if st.session_state.messages:
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""<div class='bubble-user'>
                <div class='msg'>{msg['content']}</div>
                <div class='avatar'>👤</div></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class='bubble-ai'>
                <div class='avatar'>🤖</div>
                <div class='msg'>{msg.get('summary', 'Here are your results:')}</div>
            </div>""", unsafe_allow_html=True)

            if msg.get("error"):
                err = msg["error"]
                if "cannot be answered" in err or "No data uploaded" in err or "cannot answer" in err.lower():
                    st.info(f"🤔 {err}")
                elif "does not exist" in err or "incorrect column" in err or "validation failed" in err or "Hallucination" in err:
                    st.warning(f"⚠️ **Hallucination blocked** — {err}")
                elif "returned no data" in err or "no results" in err.lower():
                    st.warning(f"📭 {err}")
                else:
                    st.error(f"❌ {err}")
                continue

            charts = msg.get("charts", [])
            if not charts:
                st.info("ℹ️ The AI responded but produced no charts. Try rephrasing your question.")
                continue



            def render(ch):
                data = ch.get("data", [])
                title = ch.get("title", "Result")
                insight = ch.get("insight", "")

                # ── Single value result → show as a stat card, not a chart ──
                if len(data) == 1 and len(data[0]) == 1:
                    val = list(data[0].values())[0]
                    label = list(data[0].keys())[0].replace("_", " ").title()
                    ins_style = "font-size:0.85rem;color:#3730a3;margin-top:0.8rem;padding:0.5rem 1rem;background:#eff6ff;border-radius:8px;"
                    ins_block = f"<div style='{ins_style}'>{insight}</div>" if insight else ""
                    st.markdown(f"""
                    <div style="background:white;border:1px solid #e2e8f0;border-radius:16px;
                                padding:2rem;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,0.06);
                                margin-bottom:1rem;">
                        <div style="font-size:0.85rem;color:#94a3b8;text-transform:uppercase;
                                    letter-spacing:0.08em;margin-bottom:0.5rem;">{title}</div>
                        <div style="font-size:3rem;font-weight:700;color:#4f46e5;line-height:1.1;">
                            {fmt(val)}
                        </div>
                        <div style="font-size:0.9rem;color:#64748b;margin-top:0.4rem;">{label}</div>
                        {ins_block}
                    </div>
                    """, unsafe_allow_html=True)

                # ── Single row, multiple columns → horizontal stat cards ──
                elif len(data) == 1 and len(data[0]) > 1:
                    st.markdown(f"<div style='font-weight:600;color:#1e293b;margin-bottom:0.6rem;'>{title}</div>",
                                unsafe_allow_html=True)
                    stat_cols = st.columns(min(len(data[0]), 4))
                    for i, (k, v) in enumerate(data[0].items()):
                        with stat_cols[i % len(stat_cols)]:
                            st.markdown(f"""
                            <div style="background:white;border:1px solid #e2e8f0;border-radius:12px;
                                        padding:1rem;text-align:center;">
                                <div style="font-size:1.6rem;font-weight:700;color:#4f46e5;">{fmt(v)}</div>
                                <div style="font-size:0.72rem;color:#94a3b8;text-transform:uppercase;
                                            letter-spacing:0.06em;margin-top:0.2rem;">
                                    {k.replace("_"," ").title()}
                                </div>
                            </div>""", unsafe_allow_html=True)
                    if insight:
                        st.markdown(f"<div class='insight-pill'>💡 {insight}</div>",
                                    unsafe_allow_html=True)

                # ── Multiple rows → render as chart ──
                else:
                    st.plotly_chart(build_chart(ch), use_container_width=True,
                                    config={"displayModeBar": True})
                    if insight:
                        st.markdown(f"<div class='insight-pill'>💡 {insight}</div>",
                                    unsafe_allow_html=True)
                    summary_html = chart_data_summary(ch)
                    if summary_html:
                        st.markdown(
                            f"<div class='chart-summary'><div style='font-size:0.8rem;font-weight:600;"
                            f"color:#4f46e5;margin-bottom:0.4rem;'>📊 Chart Summary</div>{summary_html}</div>",
                            unsafe_allow_html=True
                        )

                # SQL + data expanders always shown
                c1, c2 = st.columns(2)
                with c1:
                    with st.expander("🔍 View SQL"):
                        st.markdown(f"<div class='sql-block'>{ch.get('sql', '')}</div>",
                                    unsafe_allow_html=True)
                with c2:
                    with st.expander("📋 View data"):
                        if data:
                            df_show = pd.DataFrame(data)
                            st.dataframe(df_show, use_container_width=True, height=200)
                            csv_bytes = df_show.to_csv(index=False).encode()
                            st.download_button("⬇️ Download CSV", csv_bytes,
                                               file_name=f"{title}.csv",
                                               mime="text/csv")

            if len(charts) == 1:
                render(charts[0])
            else:
                for i in range(0, len(charts), 2):
                    pair = charts[i:i+2]
                    cols = st.columns(len(pair))
                    for ch, col in zip(pair, cols):
                        with col:
                            render(ch)
            st.write("")

else:
    # Data uploaded but no questions asked yet
    st.markdown(f"""<div class='upload-prompt' style='border-style:solid;border-color:#c7d2fe;'>
        <div style='font-size:2.5rem;margin-bottom:0.8rem'>💬</div>
        <h2>Your data is ready!</h2>
        <p>Ask any question about <strong>{st.session_state.uploaded_table}</strong> below.<br>
        Try: <em>"Show me the top 10 rows by [column name]"</em> or <em>"What is the distribution of [column]?"</em></p>
    </div>""", unsafe_allow_html=True)

# Input box
st.write("")
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_area(
        "Message", value=st.session_state.query_input,
        placeholder="Ask a question about your data...",
        height=75, label_visibility="collapsed")
    submitted = st.form_submit_button("Send ✈️", use_container_width=True)

if submitted and user_input.strip():
    st.session_state.query_input = ""
    q = user_input.strip()
    st.session_state.messages.append({"role": "user", "content": q})
    history = [
        {"role": m["role"], "content": m.get("content", m.get("summary", ""))}
        for m in st.session_state.messages[:-1]
    ]
    with st.spinner("🤖 Analyzing your data..."):
        try:
            resp = requests.post(
                f"{BACKEND}/query",
                json={"prompt": q, "conversation_history": history,
                      "use_uploaded_db": True},
                timeout=90,
            )
            if resp.status_code == 200:
                result = resp.json()
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result.get("summary", ""),
                    "summary": result.get("summary", "Here are your results:"),
                    "charts": result.get("charts", []),
                    "error": result.get("error") if not result.get("success") else None,
                })
            else:
                try: detail = resp.json().get("detail", resp.text)
                except Exception: detail = resp.text
                st.session_state.messages.append({
                    "role": "assistant", "content": "", "summary": "",
                    "charts": [], "error": f"Backend error: {detail}",
                })
        except requests.exceptions.ConnectionError:
            st.session_state.messages.append({
                "role": "assistant", "content": "", "summary": "",
                "charts": [], "error": "Cannot connect to backend on port 8000.",
            })
        except Exception as e:
            st.session_state.messages.append({
                "role": "assistant", "content": "", "summary": "",
                "charts": [], "error": str(e),
            })
    st.rerun()
