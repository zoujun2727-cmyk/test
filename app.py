"""SQL-driven analytics dashboard server (Python standard library only).

Serves a single-page dashboard whose panels are defined entirely by SQL in
dashboards.json, plus an ad-hoc read-only SQL console. No third-party
dependencies.

Endpoints:
    GET  /                  -> the dashboard UI
    GET  /api/dashboard     -> panel definitions + results for each panel's SQL
    POST /api/query         -> run an ad-hoc read-only SQL query  {"sql": "..."}
    GET  /api/schema        -> table/column metadata for the SQL console

Run:
    python3 seed.py     # once, to create analytics.db
    python3 app.py      # then open http://localhost:8000
"""

from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "analytics.db"
DASHBOARDS = BASE / "dashboards.json"
STATIC = BASE / "static"

# Statement prefixes we refuse outright on the ad-hoc console.
FORBIDDEN = (
    "insert", "update", "delete", "drop", "alter", "create",
    "replace", "attach", "detach", "pragma", "vacuum", "reindex",
)
MAX_ROWS = 1000


class QueryError(Exception):
    """A user-facing problem with a submitted query."""


def open_readonly() -> sqlite3.Connection:
    """Open analytics.db in read-only mode so queries can never mutate it."""
    if not DB_PATH.exists():
        raise QueryError("analytics.db not found - run `python3 seed.py` first.")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def run_sql(conn: sqlite3.Connection, sql: str, *, enforce_select: bool = False):
    """Execute SQL and return {columns, rows}. Optionally require a SELECT."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise QueryError("Empty query.")

    if enforce_select:
        if ";" in stripped:
            raise QueryError("Only a single statement is allowed.")
        first_word = stripped.split(None, 1)[0].lower()
        if first_word in FORBIDDEN or first_word not in ("select", "with"):
            raise QueryError("Only read-only SELECT queries are allowed here.")

    try:
        cur = conn.execute(stripped)
    except sqlite3.Error as exc:
        raise QueryError(f"SQL error: {exc}") from exc

    columns = [d[0] for d in cur.description] if cur.description else []
    rows = [list(r) for r in cur.fetchmany(MAX_ROWS)]
    truncated = len(cur.fetchmany(1)) > 0
    return {"columns": columns, "rows": rows, "truncated": truncated}


def load_dashboard():
    spec = json.loads(DASHBOARDS.read_text())
    conn = open_readonly()
    try:
        for panel in spec["panels"]:
            try:
                result = run_sql(conn, panel["sql"])
                panel["result"] = result
            except QueryError as exc:
                panel["error"] = str(exc)
    finally:
        conn.close()
    return spec


def get_schema():
    conn = open_readonly()
    try:
        tables = {}
        names = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        for name in names:
            cols = conn.execute(f"PRAGMA table_info({name})").fetchall()
            tables[name] = [{"name": c["name"], "type": c["type"]} for c in cols]
    finally:
        conn.close()
    return {"tables": tables}


class Handler(BaseHTTPRequestHandler):
    server_version = "SQLDashboard/1.0"

    def log_message(self, *args):  # quieter console
        pass

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str):
        if not path.is_file():
            self.send_error(404, "Not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_file(STATIC / "index.html", "text/html; charset=utf-8")
        elif self.path == "/app.js":
            self._send_file(STATIC / "app.js", "application/javascript")
        elif self.path == "/style.css":
            self._send_file(STATIC / "style.css", "text/css")
        elif self.path == "/api/dashboard":
            try:
                self._send_json(load_dashboard())
            except QueryError as exc:
                self._send_json({"error": str(exc)}, status=400)
        elif self.path == "/api/schema":
            try:
                self._send_json(get_schema())
            except QueryError as exc:
                self._send_json({"error": str(exc)}, status=400)
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        if self.path != "/api/query":
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            sql = json.loads(raw).get("sql", "")
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON body."}, status=400)
            return

        try:
            conn = open_readonly()
            try:
                result = run_sql(conn, sql, enforce_select=True)
            finally:
                conn.close()
            self._send_json(result)
        except QueryError as exc:
            self._send_json({"error": str(exc)}, status=400)


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"SQL dashboard running at http://localhost:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
