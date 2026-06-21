# SQL Analytics Dashboard

A small, self-contained web app for **data/analytics work where the dashboard
is driven entirely by SQL**. Every panel — KPIs, bar charts, line charts,
tables — is defined by a SQL query in a config file. There's also an ad-hoc
SQL console for exploring the data.

Built with the **Python standard library only** (no Flask, no pip installs) and
**vanilla JS with hand-rolled SVG charts** (no CDN, no Chart.js). It runs
anywhere Python 3 is installed and works fully offline.

![panels are KPIs, bar/line charts, and tables, all defined by SQL](https://img.shields.io/badge/deps-zero-brightgreen)

## Quick start

```bash
python3 seed.py     # create analytics.db with a sample e-commerce dataset
python3 app.py      # serve the dashboard
# open http://localhost:8000
```

## What's inside

| File              | Role                                                              |
| ----------------- | ----------------------------------------------------------------- |
| `seed.py`         | Builds `analytics.db` (customers, products, orders, order_items). |
| `dashboards.json` | **The dashboard, as SQL.** Each panel = a title, a type, a query. |
| `app.py`          | Stdlib HTTP server + read-only SQLite API.                        |
| `static/`         | Single-page UI and self-contained SVG charts.                     |

## Add a panel without touching code

The whole dashboard is data. To add a chart, append an entry to the `panels`
array in `dashboards.json` — no Python or JS changes required:

```json
{
  "id": "refund_rate",
  "title": "Refund Rate by Month",
  "type": "line",
  "sql": "SELECT strftime('%Y-%m', order_date) AS label, ROUND(100.0 * SUM(status='refunded') / COUNT(*), 2) AS value FROM orders GROUP BY label ORDER BY label"
}
```

Panel `type` values:

- `kpi` — first column of the first row, shown as a big number. Add
  `"format": "currency"` to render as money.
- `bar` — query returns `(label, value)` rows; rendered as a horizontal bar chart.
- `line` — query returns `(label, value)` rows in order; rendered as a time series.
- `table` — any number of columns; rendered as a sortable-looking data table.

The convention is that charts read a `label` column and a `value` column, so
your `SELECT` should alias accordingly (or just return them in that order).

## The SQL console

The **SQL Console** tab runs ad-hoc queries against the same database. The
schema sidebar lists every table and column — click a table name to drop it
into the editor. Run with the button or **Ctrl/Cmd + Enter**.

If a result has exactly two columns and the second is numeric, a
**"View as chart"** toggle appears to render it as a bar chart on the fly.

## Exporting

Every table panel on the dashboard, and every console result, has an
**Export CSV** button — generated client-side, no server round-trip.

## Date-range filter

The dashboard has a **From / To** filter bar. It applies to any panel whose
SQL references the `:start_date` / `:end_date` named parameters (everything
backed by `orders.order_date` in the sample queries); panels that don't use
those placeholders, like "Acquisition Channel," are unaffected.

To make a panel filterable, add this to its `WHERE` clause:

```sql
AND o.order_date >= COALESCE(:start_date, '0000-01-01')
AND o.order_date <= COALESCE(:end_date, '9999-12-31')
```

The server validates both dates (`YYYY-MM-DD`) and binds them as SQL
parameters — never string-interpolated — before running every panel's query.

## Safety

Queries are **read-only**, enforced two ways:

1. The database connection is opened with SQLite's `mode=ro` URI, so no
   statement can ever modify the data.
2. The console additionally rejects anything that isn't a single `SELECT`/`WITH`
   statement (no `INSERT`, `UPDATE`, `DELETE`, `DROP`, `PRAGMA`, multi-statement
   batches, etc.).

Result sets are capped at 1,000 rows so a careless `SELECT *` can't flood the
browser.

## Using your own data

Point it at a real database by replacing `seed.py` / `analytics.db` with your
own SQLite file (or adapt `open_readonly()` in `app.py` to your engine), then
rewrite the queries in `dashboards.json` against your schema. The app doesn't
care what the data is — it just runs the SQL you give it.

## Deploying

The app has no dependencies, so deployment is just "get Python 3 onto a
machine and run it."

**Docker:**

```bash
docker build -t sql-dashboard .
docker run -p 8000:8000 sql-dashboard
```

The image seeds `analytics.db` at build time (see `Dockerfile`). Mount your
own database over `/app/analytics.db` to serve real data instead.

**systemd (bare server):**

```bash
sudo mkdir -p /opt/sql-dashboard
sudo cp -r * /opt/sql-dashboard/
sudo cp deploy/sql-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sql-dashboard
```

`deploy/sql-dashboard.service` seeds the database only if `analytics.db`
doesn't already exist, runs as `www-data`, and restarts on failure.

**Behind a reverse proxy:** the app only binds plain HTTP on port 8000.
For a public/HTTPS deployment, put `nginx` or `caddy` in front to terminate
TLS and proxy to `localhost:8000`.

**Concurrency note:** `http.server`'s `ThreadingHTTPServer` is fine for an
internal team dashboard. For heavier concurrent load, front it with a proper
WSGI server, or treat this as a reference implementation to port to one.
