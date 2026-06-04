"""Streamlit dashboard for the CommercePipeline marts.

Reads the DuckDB warehouse produced by the pipeline (read-only) and presents it
as a polished, data-forward BI product: a branded header, a bento-style KPI
grid, monospace numerals, one cohesive teal chart palette, and a clear
lineage / quality-gate section.

The visual identity is ANALYTICS / BI — a confident teal accent on cool slate
neutrals, distinct from the rest of the portfolio. Theme tokens live in
``.streamlit/config.toml``; this file mirrors the same tokens so the Altair
charts and custom CSS stay in lock-step.

Run with::

    streamlit run dashboard/app.py

If the warehouse does not exist yet, the app explains how to build it rather
than crashing.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

# Streamlit renders via markdown, which turns 4+ space-indented lines into a code
# block — that would print our inline HTML/CSS as visible text instead of applying
# it. Dedent every HTML string so tags start at column 0 and render as HTML.
_st_markdown = st.markdown


def _dedented_markdown(body, *args, **kwargs):
    if isinstance(body, str):
        body = textwrap.dedent(body).strip("\n")
    return _st_markdown(body, *args, **kwargs)


st.markdown = _dedented_markdown

# Make the `pipeline` package importable when run via `streamlit run`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.config import get_settings  # noqa: E402

# --- Brand palette — ANALYTICS / BI identity (teal on slate) ------------------
# Mirrors .streamlit/config.toml so charts + CSS share one language.
TEAL = "#0d9488"          # teal-600 — primary accent
TEAL_500 = "#14b8a6"      # teal-500 — line strokes
TEAL_SOFT = "#99f6e4"     # teal-200 — area fill
INK = "#0f1b2a"           # near slate-900 — body / values
SLATE_500 = "#64748b"     # muted labels
GRID = "#eef2f6"          # hairline chart grid
# Ordered categorical scale used across every chart for one colour identity.
CATEGORY_RANGE = ["#0d9488", "#2563eb", "#7c3aed", "#d97706", "#059669", "#db2777", "#0891b2"]
# Single-hue teal ramp for sequential / heatmap encodings.
TEAL_RAMP = ["#ecfeff", "#99f6e4", "#2dd4bf", "#0d9488", "#0f766e", "#115e59"]
# Monospace stack for tabular numerals (the data-tool hallmark).
MONO = "ui-monospace, 'SF Mono', 'JetBrains Mono', 'Roboto Mono', Menlo, monospace"

st.set_page_config(
    page_title="CommercePipeline, Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"about": "CommercePipeline · trustworthy e-commerce analytics. Built by Laela Zorana."},
)

settings = get_settings()


# --- One cohesive Altair theme for every chart -------------------------------
# A single config so all charts share one visual language: a clean sans body,
# hairline horizontal grid, no chart borders, and teal-led colour ranges.
_LABEL = {"labelColor": SLATE_500, "titleColor": SLATE_500,
          "labelFontSize": 11, "titleFontSize": 11, "labelFontWeight": 500}
_CHART_CONFIG = {
    "config": {
        "background": "transparent",
        "font": "Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        "view": {"stroke": "transparent"},
        "axis": {
            "domain": False, "ticks": False, "labelPadding": 8, "titlePadding": 12,
            "gridColor": GRID, "gridWidth": 1, **_LABEL,
        },
        "axisX": {"grid": False},
        "axisY": {"grid": True},
        "legend": {**_LABEL, "symbolType": "circle", "symbolSize": 90},
        "range": {"category": CATEGORY_RANGE, "heatmap": TEAL_RAMP, "ramp": TEAL_RAMP},
        "title": {"color": INK, "fontSize": 13, "fontWeight": 600, "anchor": "start", "dy": -4},
        "bar": {"color": TEAL},
        "rect": {"stroke": "#ffffff", "strokeWidth": 1.5},
    }
}

# Altair 5.5+ uses ``alt.theme``; fall back to the legacy registry on older 5.x.
try:  # pragma: no cover - thin shim around the charting lib
    alt.theme.register("commerce_bi", enable=True)(lambda: _CHART_CONFIG)
except AttributeError:  # pragma: no cover
    alt.themes.register("commerce_bi", lambda: _CHART_CONFIG)
    alt.themes.enable("commerce_bi")


# --- Global styling -----------------------------------------------------------
def inject_styles() -> None:
    """Hide default Streamlit chrome and apply the teal BI identity: branded
    header, bento KPI cards with an accent rail, and monospace numerals."""
    st.markdown(
        f"""
        <style>
          :root {{
            --teal:#0d9488; --teal-700:#0f766e; --teal-50:#f0fdfa;
            --ink:#0f1b2a; --muted:#64748b; --line:#e6ebf0; --mono:{MONO};
          }}
          html, body, [class*="css"], .stApp,
          button, input, textarea, select {{ font-family:'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }}

          /* Remove default Streamlit clutter. */
          #MainMenu, footer, header[data-testid="stHeader"] {{ visibility:hidden; }}
          .stDeployButton {{ display:none; }}
          .block-container {{ padding-top:2.1rem; padding-bottom:3rem; max-width:1200px; }}

          /* Restrained, BI-grade canvas: a single cool wash, no rainbow. */
          .stApp {{
            background:
              radial-gradient(46rem 40rem at 104% -10%, rgba(13,148,136,0.07), transparent 55%),
              radial-gradient(40rem 38rem at -6% -8%, rgba(37,99,235,0.05), transparent 52%),
              #f5f7f9;
          }}

          /* Branded header. */
          .cp-header {{ display:flex; align-items:center; gap:0.85rem; margin-bottom:0.3rem; }}
          .cp-logo {{
            display:grid; place-items:center; width:46px; height:46px; border-radius:13px;
            background:linear-gradient(135deg,#0d9488,#0f766e); color:#fff;
            box-shadow:0 8px 18px -7px rgba(13,148,136,0.6); flex:0 0 auto;
          }}
          .cp-logo svg {{ width:25px; height:25px; }}
          .cp-title {{ font-size:1.68rem; font-weight:800; letter-spacing:-0.022em; line-height:1.05; color:var(--ink); }}
          .cp-title .grad {{
            background:linear-gradient(100deg,#0d9488,#14b8a6);
            -webkit-background-clip:text; background-clip:text; color:transparent;
          }}
          .cp-eyebrow {{ font-size:0.7rem; font-weight:700; letter-spacing:0.15em; text-transform:uppercase; color:#94a3b8; }}
          .cp-lede {{ color:#475569; font-size:1.0rem; line-height:1.6; max-width:50rem; margin:0.55rem 0 0.2rem; }}
          .cp-lede b {{ color:var(--teal-700); font-weight:600; }}

          /* Pill / badge row under the header. */
          .cp-pills {{ display:flex; flex-wrap:wrap; gap:0.5rem; margin-top:0.95rem; }}
          .cp-pill {{
            display:inline-flex; align-items:center; gap:0.45rem;
            font-size:0.76rem; font-weight:600; color:#334e68;
            background:#fff; border:1px solid var(--line);
            padding:0.3rem 0.7rem; border-radius:999px;
            box-shadow:0 1px 2px rgba(15,27,42,0.04);
          }}
          .cp-pill b {{ font-family:var(--mono); font-weight:700; font-variant-numeric:tabular-nums; color:var(--ink); }}
          .cp-pill.ok {{ color:var(--teal-700); border-color:rgba(13,148,136,0.3); background:var(--teal-50); }}
          .cp-pill.bad {{ color:#b91c1c; border-color:rgba(220,38,38,0.3); background:#fef2f2; }}
          .cp-dot {{ width:7px; height:7px; border-radius:999px; background:currentColor;
                     box-shadow:0 0 0 3px color-mix(in srgb, currentColor 18%, transparent); }}

          /* Section label. */
          .cp-section {{ font-size:1.1rem; font-weight:700; color:var(--ink); letter-spacing:-0.01em;
                         margin:0.2rem 0 0.1rem; display:flex; align-items:baseline; gap:0.55rem; }}
          .cp-section .num {{ font-family:var(--mono); font-size:0.8rem; color:var(--teal);
                              font-weight:700; letter-spacing:0.04em; }}
          .cp-sub {{ color:var(--muted); font-size:0.88rem; margin:0 0 0.45rem; }}

          /* Bento KPI cards. */
          div[data-testid="stMetric"] {{
            background:#ffffff; border:1px solid var(--line); border-radius:16px;
            padding:1.0rem 1.15rem 0.9rem; position:relative; overflow:hidden;
            box-shadow:0 1px 2px rgba(15,27,42,0.04), 0 12px 28px -18px rgba(15,27,42,0.22);
            transition:transform .12s ease, box-shadow .12s ease, border-color .12s ease;
          }}
          div[data-testid="stMetric"]:hover {{
            transform:translateY(-2px); border-color:#d7e0e8;
            box-shadow:0 1px 2px rgba(15,27,42,0.05), 0 18px 36px -18px rgba(13,148,136,0.34);
          }}
          div[data-testid="stMetricLabel"] p {{
            font-size:0.7rem !important; font-weight:600 !important; letter-spacing:0.07em;
            text-transform:uppercase; color:var(--muted) !important;
          }}
          /* Monospace, tabular numerals — the data-tool hallmark. */
          div[data-testid="stMetricValue"] {{
            font-family:var(--mono) !important; font-size:1.7rem !important; font-weight:700 !important;
            color:var(--ink) !important; letter-spacing:-0.01em; font-variant-numeric:tabular-nums;
          }}
          div[data-testid="stMetricDelta"] {{ font-size:0.76rem !important; font-weight:600 !important; }}
          div[data-testid="stMetricDelta"] div {{ font-variant-numeric:tabular-nums; }}

          /* Top "proof" cards get a teal accent rail + tinted ground. */
          .cp-proof div[data-testid="stMetric"] {{ border-top:3px solid var(--teal); background:linear-gradient(180deg,#fbfffe,#ffffff); }}

          /* Quality-gate check grid. */
          .cp-gate {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(225px,1fr)); gap:0.5rem; margin:0.3rem 0 0.2rem; }}
          .cp-check {{ display:flex; align-items:center; gap:0.55rem; background:#fff; border:1px solid var(--line);
                       border-radius:11px; padding:0.55rem 0.75rem; font-size:0.8rem; }}
          .cp-check .ic {{ flex:0 0 auto; width:18px; height:18px; border-radius:6px; display:grid; place-items:center;
                           font-size:0.7rem; font-weight:800; color:#fff; }}
          .cp-check.pass .ic {{ background:var(--teal); }}
          .cp-check.fail .ic {{ background:#dc2626; }}
          .cp-check .nm {{ font-weight:600; color:#334e68; }}
          .cp-check .rel {{ margin-left:auto; font-family:var(--mono); font-size:0.7rem; color:#94a3b8; }}

          /* Lineage flow strip. */
          .cp-flow {{ display:flex; flex-wrap:wrap; align-items:stretch; gap:0.4rem; margin:0.2rem 0 0.4rem; }}
          .cp-stage {{ flex:1 1 150px; background:#fff; border:1px solid var(--line); border-radius:13px;
                       padding:0.7rem 0.85rem; box-shadow:0 1px 2px rgba(15,27,42,0.04); }}
          .cp-stage .st-n {{ font-family:var(--mono); font-size:0.68rem; font-weight:700; color:var(--teal); }}
          .cp-stage .st-t {{ font-size:0.9rem; font-weight:700; color:var(--ink); margin-top:0.1rem; }}
          .cp-stage .st-d {{ font-size:0.74rem; color:var(--muted); margin-top:0.15rem; line-height:1.4; }}
          .cp-stage .st-v {{ font-family:var(--mono); font-size:0.74rem; color:var(--teal-700); font-weight:600; margin-top:0.3rem; }}
          .cp-arrow {{ align-self:center; color:#cbd5e1; font-weight:700; }}
          .cp-stage.gate {{ border-color:rgba(13,148,136,0.35); background:var(--teal-50); }}

          /* Tighten radio / slider chrome. */
          div[data-testid="stRadio"] label p, div[data-testid="stSlider"] label p {{ font-weight:600; color:#334155; }}

          /* Footer. */
          .cp-footer {{ margin-top:2.4rem; padding-top:1.1rem; border-top:1px solid var(--line);
                        display:flex; flex-wrap:wrap; gap:0.5rem 1.2rem; align-items:center;
                        justify-content:space-between; color:var(--muted); font-size:0.82rem; }}
          .cp-footer a {{ color:var(--teal); text-decoration:none; font-weight:600; }}
          .cp-footer a:hover {{ text-decoration:underline; }}
          .cp-footer code {{ font-family:var(--mono); background:var(--teal-50); color:var(--teal-700);
                             padding:0.08rem 0.4rem; border-radius:6px; font-size:0.76rem; }}
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
        checks = [
            {"name": r.name, "relation": r.relation, "passed": r.passed, "failing": r.failing_rows}
            for r in results
        ]
    finally:
        con.close()
    return {
        "raw_rows": raw_rows,
        "raw_tables": len(raw_tables),
        "marts": marts,
        "gates_passed": gates_passed,
        "gates_total": gates_total,
        "checks": checks,
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
    "numbers can&rsquo;t be trusted</b>. Every figure below is served read-only straight "
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
      <span class="cp-pill {'ok' if gate_ok else 'bad'}">
        <span class="cp-dot"></span>
        {'Quality gate passing' if gate_ok else 'Quality gate FAILED'} ·
        <b>{health['gates_passed']}/{health['gates_total']}</b>
      </span>
      <span class="cp-pill"><b>{health['raw_rows']:,}</b>&nbsp;rows ingested · <b>{health['raw_tables']}</b>&nbsp;source tables</span>
      <span class="cp-pill"><b>{len(health['marts'])}</b>&nbsp;analytics marts</span>
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
        opacity=0.95,
        line={"color": TEAL_500, "strokeWidth": 2.4},
        color=alt.Gradient(
            gradient="linear",
            stops=[
                alt.GradientStop(color="#ffffff", offset=0),
                alt.GradientStop(color=TEAL_SOFT, offset=1),
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
    funnel_bars = base.mark_bar(color=TEAL, cornerRadiusEnd=4).encode(
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
            scale=alt.Scale(range=TEAL_RAMP),
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
    "<div class='cp-section'><span class='num'>07</span>Lineage &amp; quality gate</div>"
    "<div class='cp-sub'>A dependency-free flow composes four stages; this dashboard "
    "reads only the marts the gate signed off on.</div>",
    unsafe_allow_html=True,
)

# Visible lineage flow strip (bento stages → quality gate → dashboard).
marts_count = len(health["marts"])
st.markdown(
    f"""
    <div class="cp-flow">
      <div class="cp-stage">
        <div class="st-n">01 · INGEST</div><div class="st-t">Generate</div>
        <div class="st-d">Seeded synthetic generator</div>
        <div class="st-v">{health['raw_rows']:,} rows · {health['raw_tables']} tables</div>
      </div>
      <div class="cp-arrow">&rarr;</div>
      <div class="cp-stage">
        <div class="st-n">02 · LOAD</div><div class="st-t">Warehouse</div>
        <div class="st-d">Register raw files into DuckDB</div>
        <div class="st-v">schema: raw</div>
      </div>
      <div class="cp-arrow">&rarr;</div>
      <div class="cp-stage">
        <div class="st-n">03 · TRANSFORM</div><div class="st-t">SQL marts</div>
        <div class="st-d">staging &rarr; intermediate &rarr; marts</div>
        <div class="st-v">{marts_count} marts</div>
      </div>
      <div class="cp-arrow">&rarr;</div>
      <div class="cp-stage gate">
        <div class="st-n">04 · QUALITY GATE</div><div class="st-t">Fail-closed</div>
        <div class="st-d">A single failure exits non-zero &amp; halts the build</div>
        <div class="st-v">{health['gates_passed']}/{health['gates_total']} passing</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Per-check status grid — the gate, made legible.
_checks = sorted(health["checks"], key=lambda c: (c["passed"], c["name"]))
_rows = "".join(
    f"<div class='cp-check {'pass' if c['passed'] else 'fail'}'>"
    f"<span class='ic'>{'✓' if c['passed'] else '!'}</span>"
    f"<span class='nm'>{c['name']}</span>"
    f"<span class='rel'>{c['relation']}</span></div>"
    for c in _checks
)
st.markdown(f"<div class='cp-gate'>{_rows}</div>", unsafe_allow_html=True)

with st.expander("Stage-by-stage detail", expanded=False):
    st.markdown(
        f"""
A dependency-free flow composes four stages; the dashboard you are looking at
reads the marts the **quality gate** signed off on.

| # | Stage | What runs | Output |
|---|-------|-----------|--------|
| **1** | **Ingest** | Seeded synthetic generator | {health['raw_rows']:,} raw rows across {health['raw_tables']} Parquet/CSV tables |
| **2** | **Load** | Register raw files into DuckDB | `raw` schema |
| **3** | **Transform** | Layered SQL: staging → intermediate → marts | {len(health['marts'])} marts ({", ".join(f"`{m}`" for m in health['marts'])}) |
| **4** | **Quality gate** | Declarative checks (not-null, unique, ranges, accepted values, referential integrity, mart sanity) | **{health['gates_passed']}/{health['gates_total']} passing**: a single failure exits non-zero and **halts the build** |

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
      <span>Built by <b>Laela Zorana</b> · CommercePipeline, trustworthy e-commerce analytics.</span>
      <span>Source: <code>{settings.db_path.name}</code> · {len(daily):,} active days ·
            rebuild with <code>make pipeline</code></span>
    </div>
    """,
    unsafe_allow_html=True,
)
