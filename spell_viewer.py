#!/usr/bin/env python3
"""
Spell viewer for output/spells.json.

Usage:  python3 spell_viewer.py [port]
        Then open http://localhost:8081 in your browser.

No external dependencies — uses only Python stdlib.
"""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SPELLS_FILE = Path("output/spells.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8081

# ---------------------------------------------------------------------------
# HTML / JS / CSS
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SRD 5.2.1 Spell Viewer</title>
<style>
/* ── Layout ─────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
body   { margin:0; font-family:sans-serif; background:#1a1a2e; color:#e0e0e0;
         display:flex; flex-direction:column; height:100vh; overflow:hidden; }
#hdr   { background:#0f0f23; padding:8px 16px; display:flex; align-items:center;
         gap:12px; border-bottom:1px solid #333; flex-shrink:0; }
#hdr h1 { margin:0; font-size:16px; color:#7ec8e3; }
#hdr .sub { font-size:12px; color:#888; }
#app   { display:flex; flex:1; overflow:hidden; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
#sidebar { width:240px; background:#0f0f23; display:flex; flex-direction:column;
           border-right:1px solid #333; flex-shrink:0; }
#sidebar input, #sidebar select {
  background:#1a1a3e; border:1px solid #444; color:#e0e0e0;
  padding:5px 8px; font-size:12px; border-radius:3px; outline:none; }
#sidebar input:focus, #sidebar select:focus { border-color:#7ec8e3; }
#sb-top   { padding:8px; display:flex; flex-direction:column; gap:5px; flex-shrink:0; }
#sb-top input { width:100%; }
.filter-row { display:flex; gap:5px; }
.filter-row select { flex:1; min-width:0; }
#sb-count  { font-size:11px; color:#666; padding:0 8px 4px; flex-shrink:0; }
#spell-list { flex:1; overflow-y:auto; }
.si { padding:4px 8px; cursor:pointer; font-size:13px; display:flex;
      align-items:baseline; gap:6px; line-height:1.4; }
.si:hover  { background:#1a1a3e; }
.si.active { background:#1a4a6e; color:#fff; }
.si .lvl-badge { font-size:10px; color:#999; margin-left:auto; flex-shrink:0; }
.si.active .lvl-badge { color:#adf; }

/* ── Main ────────────────────────────────────────────────────────────────── */
#main { flex:1; overflow-y:auto; padding:20px; }
.empty { color:#555; font-style:italic; padding:60px; text-align:center; }

/* ── Spell card ──────────────────────────────────────────────────────────── */
.sb {
  background:#FDF6E3; color:#1a1a1a; max-width:640px;
  font-family:"Palatino Linotype","Book Antiqua",Palatino,serif;
  padding:16px 18px; box-shadow:3px 3px 14px rgba(0,0,0,.65);
  border:1px solid #c9b87a;
}
.sb h1 { color:#1a4a6e; font-size:22px; margin:0 0 2px; line-height:1.2; }
.sb .meta { font-style:italic; font-size:13px; margin-bottom:6px; color:#444; }
.hr  { border:none; border-top:2px solid #1a4a6e; margin:8px 0; }
.hr1 { border:none; border-top:1px solid #1a4a6e; margin:5px 0; }
.pl  { margin:3px 0; font-size:14px; line-height:1.45; }
.pl b { color:#1a4a6e; }
.pl em { font-style:normal; color:#555; font-size:12px; }
.desc  { margin:8px 0; font-size:14px; line-height:1.6; }
.section-hdr { color:#1a4a6e; font-size:13px; font-variant:small-caps;
               font-weight:bold; letter-spacing:1px; margin:10px 0 3px; }
.tag { display:inline-block; background:#1a4a6e; color:#fff; font-size:10px;
       padding:1px 5px; border-radius:3px; font-family:sans-serif;
       vertical-align:middle; margin-left:4px; }
.tag.ritual { background:#5a1a6e; }
.tag.conc   { background:#1a5a2e; }
.comp-icon  { font-family:sans-serif; font-size:11px; }

/* JSON panel */
.json-btn { margin-top:10px; cursor:pointer; color:#1a4a6e; font-family:sans-serif;
            font-size:12px; user-select:none; display:inline-flex;
            align-items:center; gap:4px; }
.json-btn:hover { text-decoration:underline; }
.json-box { display:none; margin-top:6px; background:#111; color:#7ec8a4;
            font-family:monospace; font-size:11px; padding:10px;
            overflow:auto; max-height:400px; white-space:pre; }
.json-box.open { display:block; }
</style>
</head>
<body>
<div id="hdr">
  <h1>✦ SRD 5.2.1 Spell Viewer</h1>
  <span class="sub" id="total"></span>
</div>
<div id="app">
  <div id="sidebar">
    <div id="sb-top">
      <input id="search" placeholder="Search…" autocomplete="off">
      <div class="filter-row">
        <select id="flevel"><option value="">All levels</option></select>
        <select id="fschool"><option value="">All schools</option></select>
      </div>
      <div class="filter-row">
        <select id="fclass"><option value="">All classes</option></select>
        <select id="fconc">
          <option value="">Any duration</option>
          <option value="1">Concentration</option>
          <option value="0">Non-conc</option>
        </select>
      </div>
    </div>
    <div id="sb-count"></div>
    <div id="spell-list"></div>
  </div>
  <div id="main"><div class="empty">Select a spell.</div></div>
</div>

<script>
const esc = s => String(s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
  .replace(/"/g,"&quot;");

const LEVEL_LABEL = ["Cantrip","1st","2nd","3rd","4th","5th","6th","7th","8th","9th"];
const levelLabel = l => LEVEL_LABEL[l] ?? `${l}th`;

function renderSpell(s) {
  let h = `<div class="sb">`;

  // Name + tags
  let nameHtml = esc(s.name);
  if (s.ritual)        nameHtml += ` <span class="tag ritual">Ritual</span>`;
  if (s.concentration) nameHtml += ` <span class="tag conc">Concentration</span>`;
  h += `<h1>${nameHtml}</h1>`;

  // Level / school / classes
  const lvl = s.level === 0 ? "Cantrip" : `Level ${s.level}`;
  h += `<div class="meta">${esc(lvl)} ${esc(s.school)} &nbsp;·&nbsp; ${esc((s.classes||[]).join(", "))}</div>`;

  h += `<hr class="hr">`;

  // Stat fields
  h += `<div class="pl"><b>Casting Time</b> ${esc(s.casting_time)}</div>`;
  h += `<div class="pl"><b>Range</b> ${esc(s.range)}</div>`;

  // Components
  const compParts = [];
  if (s.verbal)   compParts.push("V");
  if (s.somatic)  compParts.push("S");
  if (s.material) compParts.push(s.material_desc ? `M (${esc(s.material_desc)})` : "M");
  h += `<div class="pl"><b>Components</b> ${compParts.join(", ") || "—"}</div>`;

  h += `<div class="pl"><b>Duration</b> ${esc(s.duration)}</div>`;

  h += `<hr class="hr">`;

  // Description
  if (s.description) {
    h += `<div class="desc">${esc(s.description)}</div>`;
  }

  // Cantrip upgrade
  if (s.cantrip_upgrade) {
    h += `<div class="section-hdr">Cantrip Upgrade</div>`;
    h += `<div class="desc">${esc(s.cantrip_upgrade)}</div>`;
  }

  // Higher level
  if (s.higher_level) {
    h += `<div class="section-hdr">Using a Higher-Level Spell Slot</div>`;
    h += `<div class="desc">${esc(s.higher_level)}</div>`;
  }

  // Embedded stat blocks (raw, collapsed by default)
  if (s.embedded_stat_blocks?.length) {
    h += `<div class="section-hdr">Stat Block${s.embedded_stat_blocks.length>1?"s":""}</div>`;
    s.embedded_stat_blocks.forEach((b, i) => {
      h += `<div class="json-btn" onclick="
        const b=this.nextElementSibling;
        b.classList.toggle('open');
        this.textContent=b.classList.contains('open')?'▾ Hide':'▸ Show';
      ">▸ Show</div>`;
      h += `<div class="json-box">${esc(b)}</div>`;
    });
  }

  // JSON viewer
  h += `<hr class="hr1" style="margin-top:14px;">
<div class="json-btn" onclick="
  const b=this.nextElementSibling;
  b.classList.toggle('open');
  this.textContent=b.classList.contains('open')?'▾ Hide JSON':'▸ Show JSON';
">▸ Show JSON</div>
<div class="json-box">${esc(JSON.stringify(s, null, 2))}</div>`;

  h += `</div>`;
  return h;
}

// ── State ────────────────────────────────────────────────────────────────────
let all = [], filtered = [], activeIdx = -1;

function buildList() {
  const q   = document.getElementById("search").value.trim().toLowerCase();
  const fl  = document.getElementById("flevel").value;
  const fs  = document.getElementById("fschool").value;
  const fc  = document.getElementById("fclass").value;
  const fnc = document.getElementById("fconc").value;
  const prevName = filtered[activeIdx]?.name;

  filtered = all.filter(s => {
    if (q && !s.name.toLowerCase().includes(q) &&
             !(s.description||"").toLowerCase().includes(q) &&
             !(s.classes||[]).some(c=>c.toLowerCase().includes(q))) return false;
    if (fl !== "" && String(s.level) !== fl) return false;
    if (fs && (s.school||"").toLowerCase() !== fs.toLowerCase()) return false;
    if (fc && !(s.classes||[]).includes(fc)) return false;
    if (fnc === "1" && !s.concentration) return false;
    if (fnc === "0" && s.concentration) return false;
    return true;
  });

  document.getElementById("sb-count").textContent =
    `${filtered.length} of ${all.length} spells`;

  activeIdx = prevName ? filtered.findIndex(s => s.name === prevName) : -1;

  document.getElementById("spell-list").innerHTML = filtered.map((s, i) =>
    `<div class="si${i===activeIdx?" active":""}" onclick="pick(${i})">
      <span>${esc(s.name)}</span>
      <span class="lvl-badge">${levelLabel(s.level)}</span>
    </div>`
  ).join("");
}

function pick(i) {
  activeIdx = i;
  document.querySelectorAll(".si").forEach((el,j) =>
    el.classList.toggle("active", j === i));
  const s = filtered[i];
  document.getElementById("main").innerHTML = renderSpell(s);
  document.title = `${s.name} — SRD Spell Viewer`;
  // Scroll selected item into view
  document.querySelectorAll(".si")[i]?.scrollIntoView({block:"nearest"});
}

// Keyboard navigation
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if (e.key === "ArrowDown" && activeIdx < filtered.length - 1) pick(activeIdx + 1);
  if (e.key === "ArrowUp"   && activeIdx > 0)                   pick(activeIdx - 1);
});

// ── Bootstrap ─────────────────────────────────────────────────────────────────
fetch("/spells.json")
  .then(r => r.json())
  .then(data => {
    all = data;
    document.getElementById("total").textContent = `${data.length} spells`;

    // Level dropdown
    const levels = [...new Set(data.map(s=>s.level))].sort((a,b)=>a-b);
    const flEl = document.getElementById("flevel");
    levels.forEach(l => {
      const o = document.createElement("option");
      o.value = l;
      o.textContent = l === 0 ? "Cantrip" : `Level ${l}`;
      flEl.appendChild(o);
    });

    // School dropdown
    const schools = [...new Set(data.map(s=>s.school).filter(Boolean))].sort();
    const fsEl = document.getElementById("fschool");
    schools.forEach(sc => {
      const o = document.createElement("option");
      o.value = sc; o.textContent = sc;
      fsEl.appendChild(o);
    });

    // Class dropdown
    const classes = [...new Set(data.flatMap(s=>s.classes||[]))].sort();
    const fcEl = document.getElementById("fclass");
    classes.forEach(c => {
      const o = document.createElement("option");
      o.value = c; o.textContent = c;
      fcEl.appendChild(o);
    });

    buildList();
    if (filtered.length) pick(0);

    document.getElementById("search").addEventListener("input", buildList);
    document.getElementById("flevel").addEventListener("change", buildList);
    document.getElementById("fschool").addEventListener("change", buildList);
    document.getElementById("fclass").addEventListener("change", buildList);
    document.getElementById("fconc").addEventListener("change", buildList);
  })
  .catch(() => {
    document.getElementById("main").innerHTML =
      '<div class="empty">Could not load spells.json. Make sure the server is running from the project root.</div>';
  });
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress per-request noise

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/spells.json":
            body = SPELLS_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


def main():
    if not SPELLS_FILE.exists():
        print(f"Error: {SPELLS_FILE} not found. Run python3 -m spells.phases.structured first.")
        sys.exit(1)

    server = HTTPServer(("", PORT), Handler)
    print(f"Spell viewer →  http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
