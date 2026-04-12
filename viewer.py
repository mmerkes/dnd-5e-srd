#!/usr/bin/env python3
"""
Monster stat block viewer for output/monsters.json.

Usage:  python3 viewer.py [port]
        Then open http://localhost:8080 in your browser.

No external dependencies — uses only Python stdlib.
"""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

MONSTERS_FILE = Path("output/monsters.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# ---------------------------------------------------------------------------
# HTML / JS / CSS — all in one string so there are no extra files to manage
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SRD 5.2.1 Monster Viewer</title>
<style>
/* ── Layout ─────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
body   { margin:0; font-family:sans-serif; background:#1c1c2e; color:#e0e0e0;
         display:flex; flex-direction:column; height:100vh; overflow:hidden; }
#hdr   { background:#12122a; padding:8px 16px; display:flex; align-items:center;
         gap:12px; border-bottom:1px solid #333; flex-shrink:0; }
#hdr h1 { margin:0; font-size:16px; color:#f0c040; }
#hdr .sub { font-size:12px; color:#888; }
#app   { display:flex; flex:1; overflow:hidden; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
#sidebar { width:230px; background:#12122a; display:flex; flex-direction:column;
           border-right:1px solid #333; flex-shrink:0; }
#sidebar input, #sidebar select {
  background:#1c1c3e; border:1px solid #444; color:#e0e0e0;
  padding:5px 8px; font-size:12px; border-radius:3px; outline:none; }
#sidebar input:focus, #sidebar select:focus { border-color:#f0c040; }
#sb-top   { padding:8px; display:flex; flex-direction:column; gap:5px; flex-shrink:0; }
#sb-top input { width:100%; }
.filter-row { display:flex; gap:5px; }
.filter-row select { flex:1; min-width:0; }
#sb-count  { font-size:11px; color:#666; padding:0 8px 4px; flex-shrink:0; }
#monster-list { flex:1; overflow-y:auto; }
.mi { padding:4px 8px; cursor:pointer; font-size:13px; display:flex;
      align-items:baseline; gap:6px; line-height:1.4; }
.mi:hover  { background:#1c1c3e; }
.mi.active { background:#7A200D; color:#fff; }
.mi .cr-badge { font-size:10px; color:#999; margin-left:auto; flex-shrink:0; }
.mi.active .cr-badge { color:#ffd; }

/* ── Main ────────────────────────────────────────────────────────────────── */
#main { flex:1; overflow-y:auto; padding:20px; }
.empty { color:#555; font-style:italic; padding:60px; text-align:center; }

/* ── Stat block ──────────────────────────────────────────────────────────── */
.sb {
  background:#FDF1DC; color:#1a1a1a; max-width:680px;
  font-family:"Palatino Linotype","Book Antiqua",Palatino,serif;
  padding:14px 16px; box-shadow:3px 3px 12px rgba(0,0,0,.6);
  border:1px solid #c8b98a;
}
.sb h1 { color:#7A200D; font-size:22px; margin:0 0 2px; line-height:1.2; }
.sb .meta { font-style:italic; font-size:13px; margin-bottom:6px; }
.sb .flavor { font-style:italic; color:#555; font-size:13px; margin-bottom:6px; }
.hr  { border:none; border-top:2px solid #9C2B1B; margin:7px 0; }
.hr1 { border:none; border-top:1px solid #9C2B1B; margin:5px 0; }
.pl  { margin:3px 0; font-size:14px; line-height:1.4; }
.pl b { color:#7A200D; }
.pl em { font-style:normal; color:#555; font-size:12px; }

/* Ability score table */
.ast { width:100%; border-collapse:collapse; text-align:center; margin:6px 0; }
.ast th { color:#7A200D; font-size:12px; font-weight:bold; padding:0 2px; }
.ast td { font-size:13px; padding:1px 2px; }
.ast .save-row td { font-size:11px; color:#7A200D; text-align:left;
                    padding-top:3px; padding-left:0; }

/* Section headers */
.sh { color:#7A200D; font-size:14px; font-variant:small-caps; font-weight:bold;
      letter-spacing:1px; margin:8px 0 3px; }

/* Actions */
.act  { margin:4px 0; font-size:14px; line-height:1.45; }
.aname { font-weight:bold; font-style:italic; }
.la-desc { font-style:italic; font-size:13px; margin-bottom:5px; color:#333; }

/* Tags */
.tag { display:inline-block; background:#9C2B1B; color:#fff; font-size:10px;
       padding:1px 5px; border-radius:3px; font-family:sans-serif;
       vertical-align:middle; margin-left:4px; }

/* JSON panel */
.json-btn { margin-top:10px; cursor:pointer; color:#9C2B1B; font-family:sans-serif;
            font-size:12px; user-select:none; display:inline-flex;
            align-items:center; gap:4px; }
.json-btn:hover { text-decoration:underline; }
.json-box { display:none; margin-top:6px; background:#111; color:#7ec8a4;
            font-family:monospace; font-size:11px; padding:10px;
            overflow:auto; max-height:420px; white-space:pre; }
.json-box.open { display:block; }
</style>
</head>
<body>
<div id="hdr">
  <h1>⚔ SRD 5.2.1 Monster Viewer</h1>
  <span class="sub" id="total"></span>
</div>
<div id="app">
  <div id="sidebar">
    <div id="sb-top">
      <input id="search" placeholder="Search…" autocomplete="off">
      <div class="filter-row">
        <select id="ftype"><option value="">All types</option></select>
        <select id="fcr"><option value="">All CR</option></select>
      </div>
    </div>
    <div id="sb-count"></div>
    <div id="monster-list"></div>
  </div>
  <div id="main"><div class="empty">Select a monster.</div></div>
</div>

<script>
// ── Helpers (mirrors helpers.py) ────────────────────────────────────────────
const abilityMod = s => Math.floor((s - 10) / 2);
const fmtMod = n => n >= 0 ? `+${n}` : `${n}`;
const CR_PB = {"0":2,"1/8":2,"1/4":2,"1/2":2,"1":2,"2":2,"3":2,"4":2,
  "5":3,"6":3,"7":3,"8":3,"9":4,"10":4,"11":4,"12":4,
  "13":5,"14":5,"15":5,"16":5,"17":6,"18":6,"19":6,"20":6,
  "21":7,"22":7,"23":7,"24":7,"25":8,"26":8,"27":8,"28":8,"29":9,"30":9};
const profBonus = cr => CR_PB[String(cr)] ?? 2;
const initiativeScore = b => 10 + b;
const hpMod = (con, dc) => abilityMod(con) * dc;
const hpAvg = (dc, dt, con) => Math.floor(dc * (dt + 1) / 2) + hpMod(con, dc);
const hpFormula = (dc, dt, con) => {
  const m = hpMod(con, dc), base = `${dc}d${dt}`;
  return m > 0 ? `${base}+${m}` : m < 0 ? `${base}${m}` : base;
};
const savingThrow = (score, pb, prof) => {
  const m = abilityMod(score);
  return prof === "expert" ? m + 2*pb : prof === "proficient" ? m + pb : m;
};
const skillBonus = (score, pb, prof) => {
  const m = abilityMod(score);
  return prof === "expert" ? m + 2*pb : m + pb;
};
const passivePerc = (wis, pb, prof) => {
  const m = abilityMod(wis);
  return prof === "expert" ? 10+m+2*pb : prof === "proficient" ? 10+m+pb : 10+m;
};
const dmgAvg = (dc, dt, mod) => Math.floor(dc * (dt + 1) / 2) + mod;
const dmgFmt = (dc, dt, mod) => {
  if (dc === 0) return String(mod);
  const b = `${dc}d${dt}`;
  return mod > 0 ? `${b}+${mod}` : mod < 0 ? `${b}${mod}` : b;
};
const SKILL_STAT = {
  acrobatics:"dex",animal_handling:"wis",arcana:"int",athletics:"str",
  deception:"cha",history:"int",insight:"wis",intimidation:"cha",
  investigation:"int",medicine:"wis",nature:"int",perception:"wis",
  performance:"cha",persuasion:"cha",religion:"int",
  sleight_of_hand:"dex",stealth:"dex",survival:"wis"
};

// ── Rendering ────────────────────────────────────────────────────────────────
const esc = s => String(s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
  .replace(/"/g,"&quot;");

function renderAction(a) {
  let name = a.name;
  const u = a.uses_per_day;
  if (u) {
    name += ` (${u.uses}/Day`;
    if (u.uses_lair) name += `, or ${u.uses_lair}/Day in Lair`;
    if (u.each) name += " Each";
    name += ")";
  }
  const desc = a.description || "";
  return `<div class="act"><span class="aname">${esc(name)}.</span> ${esc(desc)}</div>`;
}

function renderMonster(m) {
  const cr = m.challenge?.rating ?? "?";
  const pb = profBonus(cr);
  const as_ = m.ability_scores || {};
  const STATS = ["str","dex","con","int","wis","cha"];
  const LABELS = ["STR","DEX","CON","INT","WIS","CHA"];
  const conScore = as_.con?.score ?? 10;

  let h = `<div class="sb">`;

  // ── Name
  let nameHtml = esc(m.name);
  if (m.variant_of) nameHtml += ` <span class="tag">variant of ${esc(m.variant_of)}</span>`;
  if (m.source)     nameHtml += ` <span class="tag">${esc(m.source)}</span>`;
  h += `<h1>${nameHtml}</h1>`;

  // ── Meta
  let meta = [m.size, m.type].filter(Boolean).join(" ");
  if (m.tags?.length) meta += ` (${m.tags.join(", ")})`;
  if (m.alignment) meta += `, ${m.alignment}`;
  h += `<div class="meta">${esc(meta)}</div>`;
  if (m.flavor_text) h += `<div class="flavor">${esc(m.flavor_text)}</div>`;

  h += `<hr class="hr">`;

  // ── AC / Init / HP / Speed
  const ac = m.armor_class || {};
  let acStr = `<b>AC</b> ${ac.value ?? "?"}`;
  if (ac.initiative_bonus !== undefined)
    acStr += ` &nbsp;·&nbsp; <b>Initiative</b> ${fmtMod(ac.initiative_bonus)} (${initiativeScore(ac.initiative_bonus)})`;
  h += `<div class="pl">${acStr}</div>`;

  const hp = m.hit_points || {};
  if (hp.dice_count) {
    h += `<div class="pl"><b>HP</b> ${hpAvg(hp.dice_count, hp.dice_type, conScore)} (${hpFormula(hp.dice_count, hp.dice_type, conScore)})</div>`;
  } else if (hp.average) {
    h += `<div class="pl"><b>HP</b> ${hp.average}</div>`;
  }

  if (m.speed) {
    const spd = m.speed, parts = [];
    if (spd.walk !== undefined) parts.push(`${spd.walk} ft.`);
    for (const [k,v] of Object.entries(spd))
      if (k !== "walk" && k !== "hover") parts.push(`${k[0].toUpperCase()+k.slice(1)} ${v} ft.`);
    if (spd.hover) parts.push("(hover)");
    h += `<div class="pl"><b>Speed</b> ${parts.join(", ")}</div>`;
  }

  h += `<hr class="hr">`;

  // ── Ability scores
  h += `<table class="ast"><tr>${LABELS.map(l=>`<th>${l}</th>`).join("")}</tr>`;
  h += `<tr>${STATS.map(s=>`<td>${as_[s]?.score ?? 10}</td>`).join("")}</tr>`;
  h += `<tr>${STATS.map(s=>`<td>${fmtMod(abilityMod(as_[s]?.score ?? 10))}</td>`).join("")}</tr>`;
  const profSaves = STATS.filter(s => as_[s]?.save_proficiency);
  if (profSaves.length) {
    const saveStr = profSaves.map(s => {
      const prof = as_[s].save_proficiency;
      const val = savingThrow(as_[s].score, pb, prof);
      return `${s.toUpperCase()} ${fmtMod(val)}${prof==="expert"?" ✦":""}`;
    }).join("&nbsp;&nbsp;");
    h += `<tr class="save-row"><td colspan="6"><b>Saves:</b> ${saveStr}</td></tr>`;
  }
  h += `</table><hr class="hr">`;

  // ── Skills
  const skills = m.skills || {};
  if (Object.keys(skills).length) {
    const sk = Object.entries(skills).map(([skill, prof]) => {
      const stat = SKILL_STAT[skill];
      const score = stat ? (as_[stat]?.score ?? 10) : 10;
      const bonus = skillBonus(score, pb, prof);
      const label = skill.replace(/_/g," ").replace(/\b\w/g, c=>c.toUpperCase());
      return `${label} ${fmtMod(bonus)}${prof==="expert"?' <em>(Expert)</em>':""}`;
    }).join(", ");
    h += `<div class="pl"><b>Skills</b> ${sk}</div>`;
  }

  // ── Resistances / Immunities / Vulnerabilities
  if (m.damage_vulnerabilities?.length)
    h += `<div class="pl"><b>Vulnerabilities</b> ${esc(m.damage_vulnerabilities.join(", "))}</div>`;
  if (m.damage_resistances?.length)
    h += `<div class="pl"><b>Resistances</b> ${esc(m.damage_resistances.join(", "))}</div>`;
  if (m.damage_immunities?.length)
    h += `<div class="pl"><b>Damage Immunities</b> ${esc(m.damage_immunities.join(", "))}</div>`;
  if (m.condition_immunities?.length)
    h += `<div class="pl"><b>Condition Immunities</b> ${esc(m.condition_immunities.join(", "))}</div>`;

  // ── Senses + Passive Perception
  const senses = m.senses || {};
  const senseList = Object.entries(senses)
    .map(([k,v]) => `${k[0].toUpperCase()+k.slice(1)} ${v} ft.`);
  const pp = passivePerc(as_.wis?.score ?? 10, pb, skills.perception ?? null);
  senseList.push(`Passive Perception ${pp}`);
  h += `<div class="pl"><b>Senses</b> ${senseList.join(", ")}</div>`;

  // ── Languages
  if (m.languages?.length)
    h += `<div class="pl"><b>Languages</b> ${esc(m.languages.join(", "))}</div>`;

  // ── CR / XP / PB
  const ch = m.challenge || {};
  let crStr = `<b>CR</b> ${cr}`;
  if (ch.xp !== undefined) {
    crStr += ` (XP ${ch.xp.toLocaleString()}`;
    if (ch.xp_lair) crStr += `, or ${ch.xp_lair.toLocaleString()} in lair`;
    crStr += ")";
  }
  crStr += ` &nbsp;·&nbsp; <b>PB</b> ${fmtMod(pb)}`;
  h += `<div class="pl">${crStr}</div>`;

  // ── Traits
  if (m.special_abilities?.length) {
    h += `<hr class="hr"><div class="sh">Traits</div>`;
    m.special_abilities.forEach(a => h += renderAction(a));
  }

  // ── Actions
  if (m.actions?.length) {
    h += `<hr class="hr"><div class="sh">Actions</div>`;
    m.actions.forEach(a => h += renderAction(a));
  }

  // ── Bonus Actions
  if (m.bonus_actions?.length) {
    h += `<hr class="hr"><div class="sh">Bonus Actions</div>`;
    m.bonus_actions.forEach(a => h += renderAction(a));
  }

  // ── Reactions
  if (m.reactions?.length) {
    h += `<hr class="hr"><div class="sh">Reactions</div>`;
    m.reactions.forEach(a => h += renderAction(a));
  }

  // ── Legendary Actions
  const la = m.legendary_actions;
  if (la && (la.description || la.actions?.length)) {
    h += `<hr class="hr"><div class="sh">Legendary Actions</div>`;
    if (la.description) h += `<div class="la-desc">${esc(la.description)}</div>`;
    la.actions?.forEach(a => h += renderAction(a));
  }

  // ── JSON viewer
  h += `<hr class="hr1" style="margin-top:14px;">
<div class="json-btn" onclick="
  const b=this.nextElementSibling;
  b.classList.toggle('open');
  this.textContent=b.classList.contains('open')?'▾ Hide JSON':'▸ Show JSON';
">▸ Show JSON</div>
<div class="json-box">${esc(JSON.stringify(m, null, 2))}</div>`;

  h += `</div>`;
  return h;
}

// ── State & list rendering ────────────────────────────────────────────────────
// all      — full array of monster objects from monsters.json (never modified)
// filtered — subset currently matching the active search + filters
// activeIdx — index into 'filtered' for the currently displayed monster
let all = [], filtered = [], activeIdx = -1;

// CR sort order: 0, 1/8, 1/4, 1/2, 1, 2, … 30.
// String comparison ("10" < "9") would mis-sort, so we use an explicit ordering.
const CR_ORDER = ["0","1/8","1/4","1/2",...Array.from({length:31},(_,i)=>String(i))];
const crSort = (a,b) => CR_ORDER.indexOf(a) - CR_ORDER.indexOf(b);

function buildList() {
  const q  = document.getElementById("search").value.trim().toLowerCase();
  const ft = document.getElementById("ftype").value;
  const fc = document.getElementById("fcr").value;
  // Remember the currently-displayed monster by name so we can try to keep
  // it selected after a filter change.
  const prevName = filtered[activeIdx]?.name;

  filtered = all.filter(m => {
    if (q && !m.name.toLowerCase().includes(q) && !m.type?.toLowerCase().includes(q)) return false;
    if (ft && (m.type ?? "").toLowerCase() !== ft.toLowerCase()) return false;
    if (fc && m.challenge?.rating !== fc) return false;
    return true;
  });

  document.getElementById("sb-count").textContent =
    `${filtered.length} of ${all.length} monsters`;

  activeIdx = prevName ? filtered.findIndex(m => m.name === prevName) : -1;

  document.getElementById("monster-list").innerHTML = filtered.map((m, i) =>
    `<div class="mi${i===activeIdx?" active":""}" onclick="pick(${i})">
      <span>${esc(m.name)}</span>
      <span class="cr-badge">CR ${m.challenge?.rating ?? "?"}</span>
    </div>`
  ).join("");
}

function pick(i) {
  activeIdx = i;
  // Update active class without full re-render
  document.querySelectorAll(".mi").forEach((el,j) =>
    el.classList.toggle("active", j === i));
  const m = filtered[i];
  document.getElementById("main").innerHTML = renderMonster(m);
  document.title = `${m.name} — SRD Viewer`;
}

// Keyboard navigation
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if (e.key === "ArrowDown" && activeIdx < filtered.length - 1) pick(activeIdx + 1);
  if (e.key === "ArrowUp"   && activeIdx > 0)                   pick(activeIdx - 1);
});

// ── Bootstrap ─────────────────────────────────────────────────────────────────
// Fetch monsters.json from the local server, populate the type + CR dropdowns
// with the values that actually appear in the data, then build the list and
// display the first monster.
fetch("/monsters.json")
  .then(r => r.json())
  .then(data => {
    all = data;
    document.getElementById("total").textContent = `${data.length} monsters`;

    // Populate type dropdown
    const types = [...new Set(data.map(m=>m.type).filter(Boolean))].sort();
    const ftEl = document.getElementById("ftype");
    types.forEach(t => { const o=document.createElement("option"); o.value=t; o.textContent=t; ftEl.appendChild(o); });

    // Populate CR dropdown (sorted by CR order)
    const crs = [...new Set(data.map(m=>m.challenge?.rating).filter(Boolean))].sort(crSort);
    const fcEl = document.getElementById("fcr");
    crs.forEach(c => { const o=document.createElement("option"); o.value=c; o.textContent=`CR ${c}`; fcEl.appendChild(o); });

    buildList();
    if (filtered.length) pick(0);

    document.getElementById("search").addEventListener("input", buildList);
    document.getElementById("ftype").addEventListener("change", buildList);
    document.getElementById("fcr").addEventListener("change", buildList);
  })
  .catch(() => {
    document.getElementById("main").innerHTML =
      '<div class="empty">Could not load monsters.json. Make sure the server is running from the project root.</div>';
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

        elif self.path == "/monsters.json":
            body = MONSTERS_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


def main():
    if not MONSTERS_FILE.exists():
        print(f"Error: {MONSTERS_FILE} not found. Run python3 parse_structured.py first.")
        sys.exit(1)

    server = HTTPServer(("", PORT), Handler)
    print(f"Monster viewer →  http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
