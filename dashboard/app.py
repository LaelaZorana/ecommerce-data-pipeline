"""Streamlit dashboard for the CommercePipeline marts.

Reads the DuckDB warehouse produced by the pipeline (read-only) and presents it
as a polished analytics product: a branded header, headline data-quality proof
cards, business KPIs, and styled revenue / product / funnel / cohort views.

Run with::

    streamlit run dashboard/app.py

If the warehouse does not exist yet, the app explains how to build it rather
than crashing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

# Make the `pipeline` package importable when run via `streamlit run`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.config import get_settings  # noqa: E402

# --- Brand palette (matches the portfolio design language) --------------------
INDIGO = "#4f46e5"        # indigo-600 — primary
INDIGO_SOFT = "#a5b4fc"   # indigo-300 — area fill
VIOLET = "#8b5cf6"        # violet-500 — secondary accent
SLATE_900 = "#0f172a"
SLATE_500 = "#64748b"
# Ordered categorical scale used across charts for consistent colour identity.
CATEGORY_RANGE = ["#4f46e5", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899"]

st.set_page_config(
    page_title="CommercePipeline — Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"about": "CommercePipeline · trustworthy e-commerce analytics. Built by Laela Zorana."},
)

settings = get_settings()


# --- Global styling -----------------------------------------------------------
def inject_styles() -> None:
    """Load Inter, hide default Streamlit chrome, and style cards / headings."""
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
          html, body, [class*="css"], .stApp,
          button, input, textarea, select { font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }

          /* Remove default Streamlit clutter. */
          #MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; }
          .stDeployButton { display: none; }
          .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }

          /* Subtle page gradient, like the rest of the portfolio. */
          .stApp {
            background:
              radial-gradient(48rem 48rem at 108% -8%, rgba(139,92,246,0.10), transparent 55%),
              radial-gradient(42rem 42rem at -8% -6%, rgba(99,102,241,0.12), transparent 52%),
              #f8fafc;
          }

          /* Branded header. */
          .cp-header { display:flex; align-items:center; gap:0.85rem; margin-bottom:0.35rem; }
          .cp-logo {
            display:grid; place-items:center; width:44px; height:44px; border-radius:13px;
            background:linear-gradient(135deg,#4f46e5,#8b5cf6); color:#fff;
            box-shadow:0 8px 18px -6px rgba(79,70,229,0.55); flex:0 0 auto;
          }
          .cp-logo svg { width:24px; height:24px; }
          .cp-title { font-size:1.65rem; font-weight:800; letter-spacing:-0.02em; line-height:1.05; color:#0f172a; }
          .cp-title .grad {
            background:linear-gradient(100deg,#4f46e5,#8b5cf6);
            -webkit-background-clip:text; background-clip:text; color:transparent;
          }
          .cp-eyebrow { font-size:0.7rem; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:#94a3b8; }
          .cp-lede { color:#475569; font-size:1.02rem; line-height:1.6; max-width:48rem; margin:0.5rem 0 0.2rem; }
          .cp-lede b { color:#4338ca; font-weight:600; }

          /* Pill / badge row under the header. */
          .cp-pills { display:flex; flex-wrap:wrap; gap:0.5rem; margin-top:0.9rem; }
          .cp-pill {
            display:inline-flex; align-items:center; gap:0.4rem;
            font-size:0.78rem; font-weight:600; color:#3730a3;
            background:rgba(99,102,241,0.10); border:1px solid rgba(99,102,241,0.22);
            padding:0.28rem 0.65rem; border-radius:999px;
          }
          .cp-pill.ok { color:#047857; background:rgba(16,185,129,0.10); border-color:rgba(16,185,129,0.25); }
          .cp-dot { width:6px; height:6px; border-radius:999px; background:currentColor; }

          /* Section label. */
          .cp-section { font-size:1.12rem; font-weight:700; color:#0f172a; letter-spacing:-0.01em;
                        margin:0.2rem 0 0.1rem; }
          .cp-section .num { color:#6366f1; font-weight:800; margin-right:0.4rem; }
          .cp-sub { color:#64748b; font-size:0.88rem; margin:0 0 0.4rem; }

          /* KPI metric cards. */
          div[data-testid="stMetric"] {
            background:#ffffff; border:1px solid #e2e8f0; border-radius:16px;
            padding:1.05rem 1.15rem 0.95rem;
            box-shadow:0 1px 2px rgba(15,23,42,0.04), 0 10px 26px -16px rgba(15,23,42,0.18);
            transition:transform .12s ease, box-shadow .12s ease;
          }
          div[data-testid="stMetric"]:hover {
            transform:translateY(-2px);
            box-shadow:0 1px 2px rgba(15,23,42,0.05), 0 16px 34px -18px rgba(79,70,229,0.32);
          }
          div[data-testid="stMetricLabel"] p {
            font-size:0.72rem !important; font-weight:600 !important; letter-spacing:0.06em;
            text-transform:uppercase; color:#64748b !important;
          }
          div[data-testid="stMetricValue"] {
            font-size:1.72rem !important; font-weight:800 !important; color:#0f172a !important;
            letter-spacing:-0.02em;
          }
          div[data-testid="stMetricDelta"] { font-size:0.78rem !important; }

          /* Top "proof" cards get an indigo top accent. */
          .cp-proof div[data-testid="stMetric"] { border-top:3px solid #6366f1; }

          /* Tighten radio / slider chrome. */
          div[data-testid="stRadio"] label p, div[data-testid="stSlider"] label p { font-weight:600; color:#334155; }

          /* Footer. */
          .cp-footer { margin-top:2.4rem; padding-top:1.1rem; border-top:1px solid #e2e8f0;
                       display:flex; flex-wrap:wrap; gap:0.5rem 1.2rem; align-items:center;
                       justify-content:space-between; color:#64748b; font-size:0.82rem; }
          .cp-footer a { color:#4f46e5; text-decoration:none; font-weight:600; }
          .cp-footer a:hover { text-decoration:underline; }
          .cp-footer code { background:#eef2ff; color:#4338ca; padding:0.08rem 0.4rem; border-radius:6px; font-size:0.78rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_styles()


# --- Data access --------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_mart(query: str) -> pd.DataFrame:
    con = duckdb.connect(str(settings.db_path), read_only=True)
    try:
        return con.execute(query).df()
    finally:
        con.close()


@st.cache_data(show_spinner=False)
def pipeline_health() -> dict:
    """Headline pipeline proof, derived read-only from the warehouse.

    Returns raw rows ingested, mart count, and the data-quality gate result so
    the dashboard can show the same trust signals the build enforces.
    """
    from pipeline import quality  # local import keeps page load light

    con = duckdb.connect(str(settings.db_path), read_only=True)
    try:
        raw_tables = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'raw' ORDER BY table_name;"
            ).fetchall()
        ]
        raw_rows = sum(
            con.execute(f"SELECT count(*) FROM raw.{t}").fetchone()[0] for t in raw_tables
        )
        marts = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'marts' AND table_name NOT LIKE 'int\\_%' ESCAPE '\\' "
                "ORDER BY table_name;"
            ).fetchall()
        ]
        results = quality.run(con, settings, raise_on_fail=False)
        gates_passed = sum(1 for r in results if r.passed)
        gates_total = len(results)
    finally:
        con.close()
    return {
        "raw_rows": raw_rows,
        "raw_tables": len(raw_tables),
        "marts": marts,
        "gates_passed": gates_passed,
        "gates_total": gates_total,
    }


def warehouse_ready() -> bool:
    if not settings.db_path.exists():
        return False
    try:
        con = duckdb.connect(str(settings.db_path), read_only=True)
        try:
            con.execute("SELECT 1 FROM marts.daily_revenue LIMIT 1;")
            return True
        finally:
            con.close()
    except Exception:
        return False


# --- Branded header -----------------------------------------------------------
st.markdown(
    """
    <div class="cp-header">
      <span class="cp-logo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1"
             stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 3v18h18"/><path d="M7 14l3-4 3 3 5-7"/>
        </svg>
      </span>
      <div>
        <div class="cp-eyebrow">E-commerce analytics pipeline</div>
        <div class="cp-title">Commerce<span class="grad">Pipeline</span></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    "<p class='cp-lede'>Raw operational data &rarr; a DuckDB warehouse &rarr; "
    "layered SQL marts, behind a <b>data-quality gate that fails the build when the "
    "numbers can&rsquo;t be trusted</b>. Everything below is served read-only straight "
    "from the warehouse the pipeline produced.</p>",
    unsafe_allow_html=True,
)

if not warehouse_ready():
    st.markdown("<div class='cp-pills'><span class='cp-pill'>Warehouse not built yet</span></div>", unsafe_allow_html=True)
    st.warning(
        "No warehouse found yet. Build it first:\n\n"
        "```bash\nmake pipeline    # or: python -m pipeline run\n```\n\n"
        f"Expected database at `{settings.db_path}`."
    )
    st.stop()

health = pipeline_health()
gate_ok = health["gates_passed"] == health["gates_total"]
st.markdown(
    f"""
    <div class="cp-pills">
      <span class="cp-pill {'ok' if gate_ok else ''}">
        <span class="cp-dot"></span>
        {'Quality gate passing' if gate_ok else 'Quality gate FAILED'} ·
        {health['gates_passed']}/{health['gates_total']}
      </span>
      <span class="cp-pill">{health['raw_rows']:,} rows ingested · {health['raw_tables']} source tables</span>
      <span class="cp-pill">{len(health['marts'])} analytics marts</span>
      <span class="cp-pill">DuckDB · in-process warehouse</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# --- Headline proof KPIs ------------------------------------------------------
st.markdown(
    "<div class='cp-section'><span class='num'>01</span>Pipeline health</div>"
    "<div class='cp-sub'>The trust signals the build itself enforces, surfaced in the product.</div>",
    unsafe_allow_html=True,
)
st.markdown("<div class='cp-proof'>", unsafe_allow_html=True)
p1, p2, p3, p4 = st.columns(4)
p1.metric("Rows processed", f"{health['raw_rows']:,}", f"{health['raw_tables']} source tables")
p2.metric("Analytics marts", f"{len(health['marts'])}", "staging → marts")
p3.metric(
    "Data-quality gates",
    f"{health['gates_passed']}/{health['gates_total']}",
    "all passing" if gate_ok else "failing",
    delta_color="normal" if gate_ok else "inverse",
)
p4.metric("Warehouse", "DuckDB", "no server required")
st.markdown("</div>", unsafe_allow_html=True)

# --- Business KPIs ------------------------------------------------------------
daily = load_mart(
    "SELECT order_date, orders, customers, units_sold, revenue, gross_profit, "
    "avg_order_value, margin_pct FROM marts.daily_revenue ORDER BY order_date"
)
daily["order_date"] = pd.to_datetime(daily["order_date"])

total_rev = float(daily["revenue"].sum())
total_orders = int(daily["orders"].sum())
total_profit = float(daily["gross_profit"].sum())
total_units = int(daily["units_sold"].sum())
aov = total_rev / total_orders if total_orders else 0.0
margin = (total_profit / total_rev * 100) if total_rev else 0.0

st.write("")
st.markdown(
    "<div class='cp-section'><span class='num'>02</span>Business performance</div>"
    f"<div class='cp-sub'>Modelled from completed orders across {len(daily):,} active days.</div>",
    unsafe_allow_html=True,
)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Revenue", f"${total_rev:,.0f}", f"{total_units:,} units sold")
k2.metric("Completed orders", f"{total_orders:,}")
k3.metric("Avg order value", f"${aov:,.2f}")
k4.metric("Gross margin", f"{margin:.1f}%", f"${total_profit:,.0f} profit")

st.write("")

# --- Revenue trend ------------------------------------------------------------
st.markdown(
    "<div class='cp-section'><span class='num'>03</span>Revenue trend</div>",
    unsafe_allow_html=True,
)
granularity = st.radio(
    "Granularity", ["Daily", "Weekly", "Monthly"], horizontal=True, index=1, label_visibility="collapsed"
)
freq = {"Daily": "D", "Weekly": "W", "Monthly": "MS"}[granularity]
trend = (
    daily.set_index("order_date")
    .resample(freq)[["revenue", "gross_profit", "orders"]]
    .sum()
    .reset_index()
)
rev_chart = (
    alt.Chart(trend)
    .mark_area(
        opacity=0.9,
        line={"color": INDIGO, "strokeWidth": 2.2},
        color=alt.Gradient(
            gradient="linear",
            stops=[
                alt.GradientStop(color="#ffffff", offset=0),
                alt.GradientStop(color=INDIGO_SOFT, offset=1),
            ],
            x1=1, x2=1, y1=1, y2=0,
        ),
    )
    .encode(
        x=alt.X("order_date:T", title=None, axis=alt.Axis(grid=False)),
        y=alt.Y("revenue:Q", title="Revenue ($)", axis=alt.Axis(format="$~s", grid=True)),
        tooltip=[
            alt.Tooltip("order_date:T", title="Period"),
            alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
            alt.Tooltip("gross_profit:Q", title="Gross profit", format="$,.0f"),
            alt.Tooltip("orders:Q", title="Orders", format=",.0f"),
        ],
    )
    .properties(height=300)
)
st.altair_chart(rev_chart, use_container_width=True)

st.write("")

# --- Top products + funnel ----------------------------------------------------
left, right = st.columns([3, 2], gap="large")

with left:
    st.markdown(
        "<div class='cp-section'><span class='num'>04</span>Top products by revenue</div>",
        unsafe_allow_html=True,
    )
    top_n = st.slider("Show top N", 5, 25, 10, label_visibility="collapsed")
    top = load_mart(
        "SELECT product_name, category, units_sold, revenue, margin_pct, revenue_rank "
        f"FROM marts.top_products ORDER BY revenue_rank LIMIT {top_n}"
    )
    bar = (
        alt.Chart(top)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("revenue:Q", title="Revenue ($)", axis=alt.Axis(format="$~s")),
            y=alt.Y("product_name:N", sort="-x", title=None),
            color=alt.Color(
                "category:N",
                scale=alt.Scale(range=CATEGORY_RANGE),
                legend=alt.Legend(title="Category", orient="bottom", columns=3),
            ),
            tooltip=[
                alt.Tooltip("product_name:N", title="Product"),
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("units_sold:Q", title="Units", format=",.0f"),
                alt.Tooltip("revenue:Q", title="Revenue", format="$,.0f"),
                alt.Tooltip("margin_pct:Q", title="Margin", format=".1%"),
            ],
        )
        .properties(height=380)
    )
    st.altair_chart(bar, use_container_width=True)

with right:
    st.markdown(
        "<div class='cp-section'><span class='num'>05</span>Conversion funnel</div>",
        unsafe_allow_html=True,
    )
    funnel = load_mart(
        "SELECT step_name, step_index, sessions, pct_of_top, step_conversion "
        "FROM marts.funnel_conversion ORDER BY step_index"
    )
    funnel["label"] = funnel["step_name"].str.replace("_", " ").str.title()
    base = alt.Chart(funnel).encode(
        # Sort by the model's own step_index so order is data-driven, not list-driven.
        y=alt.Y("label:N", sort=alt.SortField(field="step_index", order="ascending"), title=None),
    )
    funnel_bars = base.mark_bar(color=INDIGO, cornerRadiusEnd=4).encode(
        x=alt.X("sessions:Q", title="Sessions", axis=alt.Axis(format="~s")),
        tooltip=[
            alt.Tooltip("label:N", title="Step"),
            alt.Tooltip("sessions:Q", title="Sessions", format=",.0f"),
            alt.Tooltip("pct_of_top:Q", title="% of top", format=".1%"),
            alt.Tooltip("step_conversion:Q", title="Step conversion", format=".1%"),
        ],
    )
    funnel_text = base.mark_text(align="left", dx=5, color=SLATE_500, fontWeight=600).encode(
        x=alt.X("sessions:Q"),
        text=alt.Text("pct_of_top:Q", format=".0%"),
    )
    st.altair_chart((funnel_bars + funnel_text).properties(height=210), use_container_width=True)
    overall = float(funnel.iloc[-1]["pct_of_top"]) if len(funnel) else 0.0
    st.metric("Overall view → purchase", f"{overall:.1%}")

st.write("")

# --- Cohort retention heatmap -------------------------------------------------
st.markdown(
    "<div class='cp-section'><span class='num'>06</span>Customer cohort retention</div>"
    "<div class='cp-sub'>Share of each signup cohort still ordering N months later.</div>",
    unsafe_allow_html=True,
)
cohort = load_mart(
    "SELECT strftime(cohort_month, '%Y-%m') AS cohort, month_number, retention_rate "
    "FROM marts.customer_cohort_retention "
    "WHERE month_number BETWEEN 0 AND 11 ORDER BY cohort_month, month_number"
)
heat = (
    alt.Chart(cohort)
    .mark_rect(stroke="#ffffff", strokeWidth=1.5, cornerRadius=2)
    .encode(
        x=alt.X("month_number:O", title="Months since signup", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("cohort:O", title="Signup cohort"),
        color=alt.Color(
            "retention_rate:Q",
            title="Retention",
            scale=alt.Scale(range=["#eef2ff", "#a5b4fc", "#6366f1", "#4338ca"]),
            legend=alt.Legend(format=".0%", orient="right"),
        ),
        tooltip=[
            alt.Tooltip("cohort:N", title="Cohort"),
            alt.Tooltip("month_number:O", title="Month #"),
            alt.Tooltip("retention_rate:Q", title="Retention", format=".1%"),
        ],
    )
    .properties(height=330)
)
st.altair_chart(heat, use_container_width=True)

# --- Lineage / architecture ---------------------------------------------------
st.write("")
st.markdown(
    "<div class='cp-section'><span class='num'>07</span>How the data gets here</div>",
    unsafe_allow_html=True,
)
with st.expander("Pipeline lineage — ingest → load → transform → quality gate", expanded=False):
    st.markdown(
        f"""
A dependency-free flow composes four stages; the dashboard you are looking at
reads the marts the **quality gate** signed off on.

| # | Stage | What runs | Output |
|---|-------|-----------|--------|
| **1** | **Ingest** | Seeded synthetic generator | {health['raw_rows']:,} raw rows across {health['raw_tables']} Parquet/CSV tables |
| **2** | **Load** | Register raw files into DuckDB | `raw` schema |
| **3** | **Transform** | Layered SQL: staging → intermediate → marts | {len(health['marts'])} marts ({", ".join(f"`{m}`" for m in health['marts'])}) |
| **4** | **Quality gate** | Declarative checks (not-null, unique, ranges, accepted values, referential integrity, mart sanity) | **{health['gates_passed']}/{health['gates_total']} passing** — a single failure exits non-zero and **halts the build** |

```text
ingest ─▶ load ─▶ transform ─▶ quality gate ─▶ dashboard
 (gen)   (DuckDB)  (SQL marts)   (fail-closed)   (you are here)
```

Rebuild any time with `make pipeline` (or `python -m pipeline run`). Stages are
addressable individually: `python -m pipeline {{ingest,load,transform,quality}}`.
        """
    )

# --- Footer -------------------------------------------------------------------
st.markdown(
    f"""
    <div class="cp-footer">
      <span>Built by <b>Laela Zorana</b> · CommercePipeline — trustworthy e-commerce analytics.</span>
      <span>Source: <code>{settings.db_path.name}</code> · {len(daily):,} active days ·
            rebuild with <code>make pipeline</code></span>
    </div>
    """,
    unsafe_allow_html=True,
)
