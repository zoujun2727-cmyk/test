"use strict";

// ---------- helpers ----------

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

function fmtNumber(v) {
  if (typeof v !== "number") return v;
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function fmtCurrency(v) {
  if (typeof v !== "number") return v;
  return "$" + v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function isNumeric(v) {
  return typeof v === "number";
}

// ---------- self-contained SVG charts (no external libs) ----------

const COLORS = ["#4c9aff", "#2dd4bf", "#f0883e", "#a371f7", "#f778ba", "#56d364"];

function barChart(rows) {
  // rows: [[label, value], ...]
  const W = 460, H = 240, padL = 12, padR = 12, padT = 10, padB = 28;
  const max = Math.max(...rows.map(r => r[1]), 0) || 1;
  const innerW = W - padL - padR;
  const barH = (H - padT - padB) / rows.length;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "xMidYMid meet" });

  rows.forEach((r, i) => {
    const [label, value] = r;
    const y = padT + i * barH;
    const w = Math.max((value / max) * (innerW * 0.62), 1);
    svg.appendChild(svgEl("rect", {
      x: padL, y: y + barH * 0.18, width: w, height: barH * 0.5,
      rx: 4, fill: COLORS[i % COLORS.length],
    }));
    const lab = svgEl("text", { x: padL + 4, y: y + barH * 0.15, class: "bar-label" });
    lab.textContent = label;
    svg.appendChild(lab);
    const val = svgEl("text", { x: padL + w + 6, y: y + barH * 0.55, class: "bar-value" });
    val.textContent = fmtNumber(value);
    svg.appendChild(val);
  });
  return svg;
}

function lineChart(rows) {
  // rows: [[label, value], ...] in order
  const W = 460, H = 240, padL = 44, padR = 14, padT = 14, padB = 30;
  const values = rows.map(r => r[1]);
  const max = Math.max(...values, 0) || 1;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const stepX = rows.length > 1 ? innerW / (rows.length - 1) : 0;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "xMidYMid meet" });

  // horizontal grid + y labels
  const ticks = 4;
  for (let t = 0; t <= ticks; t++) {
    const y = padT + (innerH / ticks) * t;
    svg.appendChild(svgEl("line", { x1: padL, y1: y, x2: W - padR, y2: y, class: "grid-line" }));
    const lab = svgEl("text", { x: 4, y: y + 3, class: "axis-text" });
    lab.textContent = fmtNumber(Math.round(max * (1 - t / ticks)));
    svg.appendChild(lab);
  }

  const pts = rows.map((r, i) => {
    const x = padL + i * stepX;
    const y = padT + innerH * (1 - r[1] / max);
    return [x, y];
  });

  // area + line
  const path = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0] + " " + p[1]).join(" ");
  svg.appendChild(svgEl("path", {
    d: `${path} L ${pts[pts.length - 1][0]} ${padT + innerH} L ${pts[0][0]} ${padT + innerH} Z`,
    fill: "rgba(76,154,255,0.12)",
  }));
  svg.appendChild(svgEl("path", { d: path, fill: "none", stroke: COLORS[0], "stroke-width": 2 }));

  pts.forEach((p, i) => {
    svg.appendChild(svgEl("circle", { cx: p[0], cy: p[1], r: 3, fill: COLORS[0] }));
    if (i % Math.ceil(rows.length / 6) === 0 || i === rows.length - 1) {
      const lab = svgEl("text", { x: p[0], y: H - 10, class: "axis-text", "text-anchor": "middle" });
      lab.textContent = rows[i][0];
      svg.appendChild(lab);
    }
  });
  return svg;
}

function dataTable(columns, rows) {
  const thead = el("thead", {}, el("tr", {}, columns.map((c, i) =>
    el("th", { class: rows.length && isNumeric(rows[0][i]) ? "num" : "" }, String(c)))));
  const tbody = el("tbody", {}, rows.map(r =>
    el("tr", {}, r.map(v =>
      el("td", { class: isNumeric(v) ? "num" : "" }, fmtNumber(v))))));
  return el("table", {}, [thead, tbody]);
}

// ---------- CSV export ----------

function csvEscape(v) {
  const s = v === null || v === undefined ? "" : String(v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function toCSV(columns, rows) {
  const lines = [columns.map(csvEscape).join(",")];
  for (const r of rows) lines.push(r.map(csvEscape).join(","));
  return lines.join("\n");
}

function downloadCSV(filename, columns, rows) {
  const blob = new Blob([toCSV(columns, rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function exportButton(filename, columns, rows) {
  const btn = el("button", { class: "export-btn" }, "Export CSV");
  btn.addEventListener("click", () => downloadCSV(filename, columns, rows));
  return btn;
}

// ---------- dashboard view ----------

async function loadDashboard() {
  const container = document.getElementById("panels");
  const res = await fetch("/api/dashboard");
  const spec = await res.json();
  if (spec.error) {
    container.innerHTML = `<p class="panel-error">${spec.error}</p>`;
    return;
  }
  document.getElementById("dash-title").textContent = spec.title;
  container.innerHTML = "";

  for (const panel of spec.panels) {
    const card = el("div", { class: `panel ${panel.type}` }, [el("h3", {}, panel.title)]);
    if (panel.error) {
      card.appendChild(el("div", { class: "panel-error" }, panel.error));
      container.appendChild(card);
      continue;
    }
    const { columns, rows } = panel.result;

    if (panel.type === "kpi") {
      const raw = rows.length ? rows[0][0] : 0;
      const text = panel.format === "currency" ? fmtCurrency(raw) : fmtNumber(raw);
      card.appendChild(el("div", { class: "kpi-value" }, text));
    } else if (panel.type === "bar") {
      card.appendChild(barChart(rows.map(r => [String(r[0]), r[1]])));
    } else if (panel.type === "line") {
      card.appendChild(lineChart(rows.map(r => [String(r[0]), r[1]])));
    } else if (panel.type === "table") {
      card.appendChild(dataTable(columns, rows));
      card.appendChild(exportButton(`${panel.id}.csv`, columns, rows));
    }
    container.appendChild(card);
  }
}

// ---------- SQL console view ----------

async function loadSchema() {
  const tree = document.getElementById("schema-tree");
  const res = await fetch("/api/schema");
  const data = await res.json();
  if (data.error) { tree.textContent = data.error; return; }
  tree.innerHTML = "";
  for (const [table, cols] of Object.entries(data.tables)) {
    const block = el("div", { class: "tbl" });
    const name = el("div", { class: "tbl-name" }, table);
    name.addEventListener("click", () => insertAtCursor(table));
    block.appendChild(name);
    for (const c of cols) {
      block.appendChild(el("div", { class: "col", html: `${c.name} <span class="type">${c.type}</span>` }));
    }
    tree.appendChild(block);
  }
}

function insertAtCursor(text) {
  const ta = document.getElementById("sql-input");
  const start = ta.selectionStart, end = ta.selectionEnd;
  ta.value = ta.value.slice(0, start) + text + ta.value.slice(end);
  ta.focus();
  ta.selectionStart = ta.selectionEnd = start + text.length;
}

async function runQuery() {
  const sql = document.getElementById("sql-input").value;
  const status = document.getElementById("query-status");
  const out = document.getElementById("query-result");
  status.className = "";
  status.textContent = "Running…";
  out.innerHTML = "";

  const t0 = performance.now();
  const res = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql }),
  });
  const data = await res.json();
  const ms = Math.round(performance.now() - t0);

  if (data.error) {
    status.className = "error";
    status.textContent = data.error;
    return;
  }
  status.textContent = `${data.rows.length} row(s) in ${ms} ms` +
    (data.truncated ? ` (truncated to first ${data.rows.length})` : "");
  if (data.columns.length === 0) {
    out.appendChild(el("p", { class: "note" }, "Query returned no columns."));
    return;
  }

  const toolbar = el("div", { class: "result-toolbar" });
  toolbar.appendChild(exportButton("query-result.csv", data.columns, data.rows));

  const canChart = data.columns.length === 2 && data.rows.length > 0 &&
    isNumeric(data.rows[0][1]);
  const body = el("div", { class: "result-body" });
  body.appendChild(dataTable(data.columns, data.rows));

  if (canChart) {
    const chartRows = data.rows.map(r => [String(r[0]), r[1]]);
    const toggle = el("button", { class: "chart-toggle" }, "View as chart");
    let showingChart = false;
    toggle.addEventListener("click", () => {
      showingChart = !showingChart;
      body.innerHTML = "";
      if (showingChart) {
        body.appendChild(barChart(chartRows));
        toggle.textContent = "View as table";
      } else {
        body.appendChild(dataTable(data.columns, data.rows));
        toggle.textContent = "View as chart";
      }
    });
    toolbar.appendChild(toggle);
  }

  out.appendChild(toolbar);
  out.appendChild(body);
}

// ---------- wiring ----------

function initTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.tab).classList.add("active");
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  loadDashboard();
  loadSchema();
  document.getElementById("run-btn").addEventListener("click", runQuery);
  document.getElementById("sql-input").addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); runQuery(); }
  });
});
