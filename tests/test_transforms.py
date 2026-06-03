"""Transform correctness: known inputs -> known mart aggregates."""

from __future__ import annotations


def test_daily_revenue_excludes_non_completed(fixture_con):
    rows = fixture_con.execute(
        "SELECT order_date, orders, units_sold, revenue, gross_profit "
        "FROM marts.daily_revenue ORDER BY order_date"
    ).fetchall()
    # Only the two completed orders contribute: Jan 10 and Feb 15.
    assert len(rows) == 2
    by_date = {str(r[0]): r for r in rows}

    # Jan 10: 2x Widget @100 = 200 revenue; profit = 2*(100-60)=80.
    jan = by_date["2024-01-10"]
    assert jan[1] == 1          # orders
    assert jan[2] == 2          # units
    assert float(jan[3]) == 200.00
    assert float(jan[4]) == 80.00

    # Feb 15: 1x Gadget @50 = 50 revenue; profit = 50-20 = 30.
    feb = by_date["2024-02-15"]
    assert float(feb[3]) == 50.00
    assert float(feb[4]) == 30.00


def test_refunded_orders_not_in_revenue(fixture_con):
    total = fixture_con.execute("SELECT sum(revenue) FROM marts.daily_revenue").fetchone()[0]
    # 200 + 50; the refunded 100 order is excluded.
    assert float(total) == 250.00


def test_top_products_ranking_and_units(fixture_con):
    rows = fixture_con.execute(
        "SELECT product_name, units_sold, revenue, revenue_rank "
        "FROM marts.top_products ORDER BY revenue_rank"
    ).fetchall()
    # Only completed-order items count: Widget 2 units / 200, Gadget 1 / 50.
    assert rows[0][0] == "Widget"
    assert rows[0][1] == 2
    assert float(rows[0][2]) == 200.00
    assert rows[0][3] == 1
    assert rows[1][0] == "Gadget"
    assert rows[1][3] == 2


def test_cohort_retention_bounds_and_month0(fixture_con):
    rows = fixture_con.execute(
        "SELECT cohort_month, month_number, cohort_customers, active_customers, retention_rate "
        "FROM marts.customer_cohort_retention ORDER BY cohort_month, month_number"
    ).fetchall()
    # Customer 1 (Jan cohort) is active in month 0 (Jan) and month 1 (Feb).
    jan_cohort = [r for r in rows if str(r[0]) == "2024-01-01"]
    months = {r[1]: r for r in jan_cohort}
    assert 0 in months and 1 in months
    # cohort has 2 customers (id 1 and 2), 1 active.
    assert months[0][2] == 2
    assert months[0][3] == 1
    assert 0.0 <= float(months[0][4]) <= 1.0


def test_funnel_is_monotonic_non_increasing(fixture_con):
    rows = fixture_con.execute(
        "SELECT step_name, sessions, pct_of_top FROM marts.funnel_conversion ORDER BY step_index"
    ).fetchall()
    sessions = [r[1] for r in rows]
    # view(2) >= add_to_cart(2) >= checkout(1) >= purchase(1)
    assert sessions == sorted(sessions, reverse=True)
    assert sessions[0] == 2   # two sessions viewed
    assert sessions[-1] == 1  # one purchased
    assert float(rows[0][2]) == 1.0  # top of funnel is 100%


def test_staging_normalises_text(fixture_con):
    # channel lowercased, country uppercased in staging.
    chans = {r[0] for r in fixture_con.execute("SELECT DISTINCT channel FROM staging.stg_customers").fetchall()}
    countries = {
        r[0] for r in fixture_con.execute("SELECT DISTINCT country FROM staging.stg_customers").fetchall()
    }
    assert chans == {"organic", "paid_search", "email"}
    assert countries == {"US", "GB", "DE"}
