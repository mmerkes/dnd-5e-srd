#!/usr/bin/env python3
"""
Combined SRD 5.2.1 viewer — monsters and spells in one page.

Usage:  python3 viewer.py [port]
        Then open http://localhost:8080 in your browser.

No external dependencies — uses only Python stdlib.
"""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

MONSTERS_FILE = Path("output/monsters.json")
SPELLS_FILE   = Path("output/spells.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# Optional content files — served as [] when the file doesn't exist yet.
_OPTIONAL_FILES = {
    "/magic_items.json": Path("output/magic_items.json"),
    "/feats.json":       Path("output/feats.json"),
    "/classes.json":     Path("output/classes.json"),
    "/species.json":     Path("output/species.json"),
    "/origins.json":     Path("output/origins.json"),
}

# ---------------------------------------------------------------------------
# HTML / JS / CSS — all in one string so there are no extra files to manage
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SRD 5.2.1 Viewer</title>
<style>
/* ── Reset & layout ──────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
body { margin:0; font-family:sans-serif; background:#1a1a2e; color:#e0e0e0;
       display:flex; flex-direction:column; height:100vh; overflow:hidden; }

/* ── Header ──────────────────────────────────────────────────────────────── */
#hdr { background:#0f0f23; padding:0 16px;
       display:flex; align-items:stretch; gap:0;
       border-bottom:1px solid #333; flex-shrink:0; }
#hdr-title { display:flex; align-items:center; gap:10px;
             padding:8px 16px 8px 0; border-right:1px solid #333;
             margin-right:8px; }
#hdr-title h1 { margin:0; font-size:16px; color:#f0c040; white-space:nowrap; }
#hdr-title .sub { font-size:11px; color:#666; white-space:nowrap; }

/* Tab buttons in the header */
.tab-btn { background:none; border:none; color:#999; font-size:14px;
           padding:0 18px; cursor:pointer; border-bottom:3px solid transparent;
           margin-bottom:-1px; transition:color .15s, border-color .15s; }
.tab-btn:hover  { color:#e0e0e0; }
.tab-btn.active { color:#f0c040; border-bottom-color:#f0c040; }

/* ── Body: sidebar + main ────────────────────────────────────────────────── */
#app { display:flex; flex:1; overflow:hidden; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
#sidebar { width:240px; background:#0f0f23; display:flex; flex-direction:column;
           border-right:1px solid #333; flex-shrink:0; }
#sidebar input, #sidebar select {
  background:#1a1a3e; border:1px solid #444; color:#e0e0e0;
  padding:5px 8px; font-size:12px; border-radius:3px; outline:none; }
#sidebar input:focus, #sidebar select:focus { border-color:#f0c040; }
#sb-top { padding:8px; display:flex; flex-direction:column; gap:5px; flex-shrink:0; }
#sb-top input { width:100%; }
.filter-row { display:flex; gap:5px; }
.filter-row select { flex:1; min-width:0; }
#sb-count { font-size:11px; color:#666; padding:0 8px 4px; flex-shrink:0; }
#item-list { flex:1; overflow-y:auto; }

/* List items */
.li { padding:4px 8px; cursor:pointer; font-size:13px; display:flex;
      align-items:baseline; gap:6px; line-height:1.4; }
.li:hover  { background:#1a1a3e; }
.li.active { background:#7A200D; color:#fff; }
.li.active.spell { background:#1a4a6e; }
.li .badge { font-size:10px; color:#999; margin-left:auto; flex-shrink:0; }
.li.active .badge { color:#ffd; }

/* ── Main panel ──────────────────────────────────────────────────────────── */
#main { flex:1; overflow-y:auto; padding:20px; }
.empty { color:#555; font-style:italic; padding:60px; text-align:center; }

/* ── Shared card chrome ──────────────────────────────────────────────────── */
.sb {
  max-width:680px;
  font-family:"Palatino Linotype","Book Antiqua",Palatino,serif;
  padding:14px 16px; box-shadow:3px 3px 12px rgba(0,0,0,.6);
}
.sb h1 { font-size:22px; margin:0 0 2px; line-height:1.2; }
.sb .meta { font-style:italic; font-size:13px; margin-bottom:6px; }
.pl { margin:3px 0; font-size:14px; line-height:1.4; }
.pl b { }
.pl em { font-style:normal; font-size:12px; }
.act { margin:4px 0; font-size:14px; line-height:1.45; }
.aname { font-weight:bold; font-style:italic; }
.desc  { margin:8px 0; font-size:14px; line-height:1.6; }
.section-hdr { font-size:14px; font-variant:small-caps; font-weight:bold;
               letter-spacing:1px; margin:8px 0 3px; }
.la-desc { font-style:italic; font-size:13px; margin-bottom:5px; }
.tag { display:inline-block; color:#fff; font-size:10px; padding:1px 5px;
       border-radius:3px; font-family:sans-serif; vertical-align:middle; margin-left:4px; }
.json-btn { margin-top:10px; cursor:pointer; font-family:sans-serif;
            font-size:12px; user-select:none; display:inline-flex; align-items:center; gap:4px; }
.json-btn:hover { text-decoration:underline; }
.json-box { display:none; margin-top:6px; background:#111; color:#7ec8a4;
            font-family:monospace; font-size:11px; padding:10px;
            overflow:auto; max-height:420px; white-space:pre; }
.json-box.open { display:block; }

/* ── Monster card ────────────────────────────────────────────────────────── */
.sb.monster { background:#FDF1DC; color:#1a1a1a; border:1px solid #c8b98a; }
.sb.monster h1 { color:#7A200D; }
.sb.monster .pl b { color:#7A200D; }
.sb.monster .la-desc { color:#333; }
.sb.monster .section-hdr { color:#7A200D; }
.sb.monster .hr  { border:none; border-top:2px solid #9C2B1B; margin:7px 0; }
.sb.monster .hr1 { border:none; border-top:1px solid #9C2B1B; margin:5px 0; }
.sb.monster .ast { width:100%; border-collapse:collapse; text-align:center; margin:6px 0; }
.sb.monster .ast th { color:#7A200D; font-size:12px; font-weight:bold; padding:0 2px; }
.sb.monster .ast td { font-size:13px; padding:1px 2px; }
.sb.monster .ast .save-row td { font-size:11px; color:#7A200D; text-align:left;
                                 padding-top:3px; padding-left:0; }
.sb.monster .tag { background:#9C2B1B; }
.sb.monster .json-btn { color:#9C2B1B; }
.sb.monster .flavor { font-style:italic; color:#555; font-size:13px; margin-bottom:6px; }

/* ── Spell card ──────────────────────────────────────────────────────────── */
.sb.spell { background:#FDF6E3; color:#1a1a1a; border:1px solid #c9b87a; }
.sb.spell h1 { color:#1a4a6e; }
.sb.spell .pl b { color:#1a4a6e; }
.sb.spell .section-hdr { color:#1a4a6e; }
.sb.spell .hr  { border:none; border-top:2px solid #1a4a6e; margin:8px 0; }
.sb.spell .hr1 { border:none; border-top:1px solid #1a4a6e; margin:5px 0; }
.sb.spell .tag { background:#1a4a6e; }
.sb.spell .tag.ritual { background:#5a1a6e; }
.sb.spell .tag.conc   { background:#1a5a2e; }
.sb.spell .json-btn { color:#1a4a6e; }
</style>
</head>
<body>

<div id="hdr">
  <div id="hdr-title">
    <h1>SRD 5.2.1</h1>
    <span class="sub" id="total"></span>
  </div>
  <button class="tab-btn active" id="tab-monsters"    onclick="switchTab('monsters')"   >⚔ Monsters</button>
  <button class="tab-btn"        id="tab-spells"      onclick="switchTab('spells')"     >✦ Spells</button>
  <button class="tab-btn"        id="tab-magic_items" onclick="switchTab('magic_items')" >✧ Magic Items</button>
  <button class="tab-btn"        id="tab-feats"       onclick="switchTab('feats')"      >✧ Feats</button>
  <button class="tab-btn"        id="tab-classes"     onclick="switchTab('classes')"    >✧ Classes</button>
  <button class="tab-btn"        id="tab-species"     onclick="switchTab('species')"    >✧ Species</button>
  <button class="tab-btn"        id="tab-origins"     onclick="switchTab('origins')"    >✧ Origins</button>
</div>

<div id="app">
  <!-- ── Sidebar ─────────────────────────────────────────────────────────── -->
  <div id="sidebar">
    <div id="sb-top">
      <input id="search" placeholder="Search…" autocomplete="off">

      <!-- Monster filters -->
      <div id="m-filters">
        <div class="filter-row">
          <select id="ftype"><option value="">All types</option></select>
          <select id="fcr"><option value="">All CR</option></select>
        </div>
      </div>

      <!-- Spell filters -->
      <div id="s-filters" style="display:none">
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
    </div>

    <div id="sb-count"></div>
    <div id="item-list"></div>
  </div>

  <!-- ── Main ──────────────────────────────────────────────────────────── -->
  <div id="main"><div class="empty">Select an entry.</div></div>
</div>

<script>
// ── Shared helpers ────────────────────────────────────────────────────────────
const esc = s => String(s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
  .replace(/"/g,"&quot;");

// ── Monster helpers (mirror helpers.py) ──────────────────────────────────────
const abilityMod = s => Math.floor((s - 10) / 2);
const fmtMod = n => n >= 0 ? `+${n}` : `${n}`;
const CR_PB = {"0":2,"1/8":2,"1/4":2,"1/2":2,"1":2,"2":2,"3":2,"4":2,
  "5":3,"6":3,"7":3,"8":3,"9":4,"10":4,"11":4,"12":4,
  "13":5,"14":5,"15":5,"16":5,"17":6,"18":6,"19":6,"20":6,
  "21":7,"22":7,"23":7,"24":7,"25":8,"26":8,"27":8,"28":8,"29":9,"30":9};
const profBonus = cr => CR_PB[String(cr)] ?? 2;
const hpMod = (con, dc) => abilityMod(con) * dc;
const hpAvg = (dc, dt, con) => Math.floor(dc * (dt + 1) / 2) + hpMod(con, dc);
const hpFormula = (dc, dt, con) => {
  const m = hpMod(con, dc), base = `${dc}d${dt}`;
  return m > 0 ? `${base}+${m}` : m < 0 ? `${base}${m}` : base;
};
const savingThrow = (score, pb, prof) => {
  const m = abilityMod(score);
  return prof === "expert" ? m+2*pb : prof === "proficient" ? m+pb : m;
};
const skillBonus = (score, pb, prof) => {
  const m = abilityMod(score);
  return prof === "expert" ? m+2*pb : m+pb;
};
const passivePerc = (wis, pb, prof) => {
  const m = abilityMod(wis);
  return prof === "expert" ? 10+m+2*pb : prof === "proficient" ? 10+m+pb : 10+m;
};
const SKILL_STAT = {
  acrobatics:"dex",animal_handling:"wis",arcana:"int",athletics:"str",
  deception:"cha",history:"int",insight:"wis",intimidation:"cha",
  investigation:"int",medicine:"wis",nature:"int",perception:"wis",
  performance:"cha",persuasion:"cha",religion:"int",
  sleight_of_hand:"dex",stealth:"dex",survival:"wis"
};
const CR_ORDER = ["0","1/8","1/4","1/2",...Array.from({length:31},(_,i)=>String(i))];
const crSort = (a,b) => CR_ORDER.indexOf(a) - CR_ORDER.indexOf(b);

// ── Monster rendering ─────────────────────────────────────────────────────────
function renderAction(a) {
  let name = a.name;
  const u = a.uses_per_day;
  if (u) {
    name += ` (${u.uses}/Day`;
    if (u.uses_lair) name += `, or ${u.uses_lair}/Day in Lair`;
    if (u.each) name += " Each";
    name += ")";
  }
  return `<div class="act"><span class="aname">${esc(name)}.</span> ${esc(a.description||"")}</div>`;
}

function renderMonster(m) {
  const cr = m.challenge?.rating ?? "?";
  const pb = profBonus(cr);
  const as_ = m.ability_scores || {};
  const STATS = ["str","dex","con","int","wis","cha"];
  const LABELS = ["STR","DEX","CON","INT","WIS","CHA"];
  const conScore = as_.con?.score ?? 10;

  let h = `<div class="sb monster">`;

  // Name
  let nameHtml = esc(m.name);
  if (m.variant_of) nameHtml += ` <span class="tag">variant of ${esc(m.variant_of)}</span>`;
  h += `<h1>${nameHtml}</h1>`;

  // Meta
  let meta = [m.size, m.type].filter(Boolean).join(" ");
  if (m.tags?.length) meta += ` (${m.tags.join(", ")})`;
  if (m.alignment) meta += `, ${m.alignment}`;
  h += `<div class="meta">${esc(meta)}</div>`;
  if (m.flavor_text) h += `<div class="flavor">${esc(m.flavor_text)}</div>`;
  h += `<hr class="hr">`;

  // AC / Init / HP / Speed
  const ac = m.armor_class || {};
  let acStr = `<b>AC</b> ${ac.value ?? "?"}`;
  if (ac.initiative_bonus !== undefined)
    acStr += ` &nbsp;·&nbsp; <b>Initiative</b> ${fmtMod(ac.initiative_bonus)} (${10+ac.initiative_bonus})`;
  h += `<div class="pl">${acStr}</div>`;

  const hp = m.hit_points || {};
  if (hp.dice_count)
    h += `<div class="pl"><b>HP</b> ${hpAvg(hp.dice_count, hp.dice_type, conScore)} (${hpFormula(hp.dice_count, hp.dice_type, conScore)})</div>`;
  else if (hp.average)
    h += `<div class="pl"><b>HP</b> ${hp.average}</div>`;

  if (m.speed) {
    const spd = m.speed, parts = [];
    if (spd.walk !== undefined) parts.push(`${spd.walk} ft.`);
    for (const [k,v] of Object.entries(spd))
      if (k !== "walk" && k !== "hover") parts.push(`${k[0].toUpperCase()+k.slice(1)} ${v} ft.`);
    if (spd.hover) parts.push("(hover)");
    h += `<div class="pl"><b>Speed</b> ${parts.join(", ")}</div>`;
  }
  h += `<hr class="hr">`;

  // Ability scores
  h += `<table class="ast"><tr>${LABELS.map(l=>`<th>${l}</th>`).join("")}</tr>`;
  h += `<tr>${STATS.map(s=>`<td>${as_[s]?.score ?? 10}</td>`).join("")}</tr>`;
  h += `<tr>${STATS.map(s=>`<td>${fmtMod(abilityMod(as_[s]?.score ?? 10))}</td>`).join("")}</tr>`;
  const profSaves = STATS.filter(s => as_[s]?.save_proficiency);
  if (profSaves.length) {
    const saveStr = profSaves.map(s => {
      const val = savingThrow(as_[s].score, pb, as_[s].save_proficiency);
      return `${s.toUpperCase()} ${fmtMod(val)}${as_[s].save_proficiency==="expert"?" ✦":""}`;
    }).join("&nbsp;&nbsp;");
    h += `<tr class="save-row"><td colspan="6"><b>Saves:</b> ${saveStr}</td></tr>`;
  }
  h += `</table><hr class="hr">`;

  // Skills
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

  if (m.damage_vulnerabilities?.length)
    h += `<div class="pl"><b>Vulnerabilities</b> ${esc(m.damage_vulnerabilities.join(", "))}</div>`;
  if (m.damage_resistances?.length)
    h += `<div class="pl"><b>Resistances</b> ${esc(m.damage_resistances.join(", "))}</div>`;
  if (m.damage_immunities?.length)
    h += `<div class="pl"><b>Damage Immunities</b> ${esc(m.damage_immunities.join(", "))}</div>`;
  if (m.condition_immunities?.length)
    h += `<div class="pl"><b>Condition Immunities</b> ${esc(m.condition_immunities.join(", "))}</div>`;

  // Senses
  const senses = m.senses || {};
  const senseList = Object.entries(senses).map(([k,v]) => `${k[0].toUpperCase()+k.slice(1)} ${v} ft.`);
  const pp = passivePerc(as_.wis?.score ?? 10, pb, skills.perception ?? null);
  senseList.push(`Passive Perception ${pp}`);
  h += `<div class="pl"><b>Senses</b> ${senseList.join(", ")}</div>`;

  if (m.languages?.length)
    h += `<div class="pl"><b>Languages</b> ${esc(m.languages.join(", "))}</div>`;

  // CR
  const ch = m.challenge || {};
  let crStr = `<b>CR</b> ${cr}`;
  if (ch.xp !== undefined) {
    crStr += ` (XP ${ch.xp.toLocaleString()}`;
    if (ch.xp_lair) crStr += `, or ${ch.xp_lair.toLocaleString()} in lair`;
    crStr += ")";
  }
  crStr += ` &nbsp;·&nbsp; <b>PB</b> ${fmtMod(pb)}`;
  h += `<div class="pl">${crStr}</div>`;

  // Sections
  if (m.special_abilities?.length) { h += `<hr class="hr"><div class="section-hdr">Traits</div>`; m.special_abilities.forEach(a => h += renderAction(a)); }
  if (m.actions?.length)           { h += `<hr class="hr"><div class="section-hdr">Actions</div>`; m.actions.forEach(a => h += renderAction(a)); }
  if (m.bonus_actions?.length)     { h += `<hr class="hr"><div class="section-hdr">Bonus Actions</div>`; m.bonus_actions.forEach(a => h += renderAction(a)); }
  if (m.reactions?.length)         { h += `<hr class="hr"><div class="section-hdr">Reactions</div>`; m.reactions.forEach(a => h += renderAction(a)); }

  const la = m.legendary_actions;
  if (la && (la.description || la.actions?.length)) {
    h += `<hr class="hr"><div class="section-hdr">Legendary Actions</div>`;
    if (la.description) h += `<div class="la-desc">${esc(la.description)}</div>`;
    la.actions?.forEach(a => h += renderAction(a));
  }

  // JSON
  h += `<hr class="hr1" style="margin-top:14px;">
<div class="json-btn" onclick="const b=this.nextElementSibling;b.classList.toggle('open');this.textContent=b.classList.contains('open')?'▾ Hide JSON':'▸ Show JSON';">▸ Show JSON</div>
<div class="json-box">${esc(JSON.stringify(m,null,2))}</div></div>`;
  return h;
}

// ── Spell rendering ───────────────────────────────────────────────────────────
const LEVEL_LABEL = ["Cantrip","1st","2nd","3rd","4th","5th","6th","7th","8th","9th"];
const levelLabel = l => LEVEL_LABEL[l] ?? `${l}th`;

function renderSpell(s) {
  let h = `<div class="sb spell">`;

  // Name + tags
  let nameHtml = esc(s.name);
  if (s.ritual)        nameHtml += ` <span class="tag ritual">Ritual</span>`;
  if (s.concentration) nameHtml += ` <span class="tag conc">Concentration</span>`;
  h += `<h1>${nameHtml}</h1>`;

  const lvl = s.level === 0 ? "Cantrip" : `Level ${s.level}`;
  h += `<div class="meta">${esc(lvl)} ${esc(s.school)} &nbsp;·&nbsp; ${esc((s.classes||[]).join(", "))}</div>`;
  h += `<hr class="hr">`;

  h += `<div class="pl"><b>Casting Time</b> ${esc(s.casting_time)}</div>`;
  h += `<div class="pl"><b>Range</b> ${esc(s.range)}</div>`;

  const compParts = [];
  if (s.verbal)   compParts.push("V");
  if (s.somatic)  compParts.push("S");
  if (s.material) compParts.push(s.material_desc ? `M (${esc(s.material_desc)})` : "M");
  h += `<div class="pl"><b>Components</b> ${compParts.join(", ") || "—"}</div>`;
  h += `<div class="pl"><b>Duration</b> ${esc(s.duration)}</div>`;
  h += `<hr class="hr">`;

  if (s.description) h += `<div class="desc">${esc(s.description)}</div>`;

  if (s.cantrip_upgrade) {
    h += `<div class="section-hdr">Cantrip Upgrade</div>`;
    h += `<div class="desc">${esc(s.cantrip_upgrade)}</div>`;
  }
  if (s.higher_level) {
    h += `<div class="section-hdr">Using a Higher-Level Spell Slot</div>`;
    h += `<div class="desc">${esc(s.higher_level)}</div>`;
  }
  if (s.embedded_stat_blocks?.length) {
    h += `<div class="section-hdr">Stat Block${s.embedded_stat_blocks.length>1?"s":""}</div>`;
    s.embedded_stat_blocks.forEach(b => {
      h += `<div class="json-btn" onclick="const b=this.nextElementSibling;b.classList.toggle('open');this.textContent=b.classList.contains('open')?'▾ Hide':'▸ Show';">▸ Show</div>`;
      h += `<div class="json-box">${esc(b)}</div>`;
    });
  }

  h += `<hr class="hr1" style="margin-top:14px;">
<div class="json-btn" onclick="const b=this.nextElementSibling;b.classList.toggle('open');this.textContent=b.classList.contains('open')?'▾ Hide JSON':'▸ Show JSON';">▸ Show JSON</div>
<div class="json-box">${esc(JSON.stringify(s,null,2))}</div></div>`;
  return h;
}

// ── State ─────────────────────────────────────────────────────────────────────
let allMonsters = [], allSpells = [];
let activeTab = "monsters";  // "monsters" | "spells" | "magic_items" | "feats" | "classes" | "species" | "origins"

// Tabs that are stubs — no data, show placeholder.
const STUB_TABS = new Set(["magic_items","feats","classes","species","origins"]);
const STUB_TAB_LABELS = { magic_items:"Magic Items", feats:"Feats", classes:"Classes", species:"Species", origins:"Origins" };
const ALL_TABS = ["monsters","spells","magic_items","feats","classes","species","origins"];

// Per-tab state: filtered list and selected index
const state = {
  monsters:    { filtered: [], idx: -1 },
  spells:      { filtered: [], idx: -1 },
  magic_items: { filtered: [], idx: -1 },
  feats:       { filtered: [], idx: -1 },
  classes:     { filtered: [], idx: -1 },
  species:     { filtered: [], idx: -1 },
  origins:     { filtered: [], idx: -1 },
};

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(tab) {
  activeTab = tab;
  ALL_TABS.forEach(t => document.getElementById("tab-"+t).classList.toggle("active", t===tab));
  document.getElementById("m-filters").style.display = tab==="monsters" ? "" : "none";
  document.getElementById("s-filters").style.display = tab==="spells"   ? "" : "none";
  document.getElementById("search").value = "";

  // Stub tabs: show placeholder immediately, no data to list.
  if (STUB_TABS.has(tab)) {
    const label = STUB_TAB_LABELS[tab];
    document.getElementById("search").placeholder = `Search ${label.toLowerCase()}…`;
    document.getElementById("sb-count").textContent = "0 items";
    document.getElementById("item-list").innerHTML = "";
    document.getElementById("main").innerHTML =
      `<div class="empty"><strong>${label}</strong> — not yet implemented.<br>` +
      `<small>Implement the pipeline phases and run <code>python3 run_all.py</code> to populate.</small></div>`;
    return;
  }

  document.getElementById("search").placeholder = tab==="monsters" ? "Search monsters…" : "Search spells…";
  buildList();
  // Re-select the previously active item for this tab, or show the first one.
  const s = state[tab];
  if (s.filtered.length) {
    if (s.idx >= 0 && s.idx < s.filtered.length) pick(s.idx);
    else pick(0);
  } else {
    document.getElementById("main").innerHTML = '<div class="empty">Select an entry.</div>';
  }
}

// ── List building ─────────────────────────────────────────────────────────────
function buildList() {
  if (STUB_TABS.has(activeTab)) return;  // handled by switchTab
  const q = document.getElementById("search").value.trim().toLowerCase();

  if (activeTab === "monsters") {
    const ft = document.getElementById("ftype").value;
    const fc = document.getElementById("fcr").value;
    const prevName = state.monsters.filtered[state.monsters.idx]?.name;

    state.monsters.filtered = allMonsters.filter(m => {
      if (q && !m.name.toLowerCase().includes(q) && !m.type?.toLowerCase().includes(q)) return false;
      if (ft && (m.type ?? "").toLowerCase() !== ft.toLowerCase()) return false;
      if (fc && m.challenge?.rating !== fc) return false;
      return true;
    });

    document.getElementById("sb-count").textContent =
      `${state.monsters.filtered.length} of ${allMonsters.length} monsters`;

    state.monsters.idx = prevName
      ? state.monsters.filtered.findIndex(m => m.name === prevName) : -1;

    document.getElementById("item-list").innerHTML =
      state.monsters.filtered.map((m, i) =>
        `<div class="li${i===state.monsters.idx?" active":""}" onclick="pick(${i})">
          <span>${esc(m.name)}</span>
          <span class="badge">CR ${m.challenge?.rating ?? "?"}</span>
        </div>`
      ).join("");

  } else {
    const fl  = document.getElementById("flevel").value;
    const fs  = document.getElementById("fschool").value;
    const fc  = document.getElementById("fclass").value;
    const fnc = document.getElementById("fconc").value;
    const prevName = state.spells.filtered[state.spells.idx]?.name;

    state.spells.filtered = allSpells.filter(s => {
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
      `${state.spells.filtered.length} of ${allSpells.length} spells`;

    state.spells.idx = prevName
      ? state.spells.filtered.findIndex(s => s.name === prevName) : -1;

    document.getElementById("item-list").innerHTML =
      state.spells.filtered.map((s, i) =>
        `<div class="li spell${i===state.spells.idx?" active":""}" onclick="pick(${i})">
          <span>${esc(s.name)}</span>
          <span class="badge">${levelLabel(s.level)}</span>
        </div>`
      ).join("");
  }
}

// ── Picking an item ───────────────────────────────────────────────────────────
function pick(i) {
  if (STUB_TABS.has(activeTab)) return;
  const s = state[activeTab];
  s.idx = i;
  document.querySelectorAll(".li").forEach((el,j) => el.classList.toggle("active", j===i));

  if (activeTab === "monsters") {
    const m = s.filtered[i];
    document.getElementById("main").innerHTML = renderMonster(m);
    document.title = `${m.name} — SRD Viewer`;
  } else {
    const sp = s.filtered[i];
    document.getElementById("main").innerHTML = renderSpell(sp);
    document.title = `${sp.name} — SRD Viewer`;
  }
  document.querySelectorAll(".li")[i]?.scrollIntoView({block:"nearest"});
}

// ── Keyboard navigation ───────────────────────────────────────────────────────
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  const s = state[activeTab];
  if (e.key === "ArrowDown" && s.idx < s.filtered.length - 1) pick(s.idx + 1);
  if (e.key === "ArrowUp"   && s.idx > 0)                     pick(s.idx - 1);
  // M / S to switch tabs with keyboard
  if (e.key === "m" || e.key === "M") switchTab("monsters");
  if (e.key === "s" || e.key === "S") switchTab("spells");
});

// ── Wire up filter inputs ─────────────────────────────────────────────────────
document.getElementById("search").addEventListener("input", buildList);
["ftype","fcr","flevel","fschool","fclass","fconc"].forEach(id =>
  document.getElementById(id).addEventListener("change", buildList));

// ── Bootstrap — load both datasets in parallel ────────────────────────────────
Promise.all([
  fetch("/monsters.json").then(r => r.json()),
  fetch("/spells.json").then(r => r.json()),
]).then(([monsters, spells]) => {
  allMonsters = monsters;
  allSpells   = spells;

  document.getElementById("total").textContent =
    `${monsters.length} monsters · ${spells.length} spells`;

  // Populate monster dropdowns
  const types = [...new Set(monsters.map(m=>m.type).filter(Boolean))].sort();
  const ftEl = document.getElementById("ftype");
  types.forEach(t => { const o=document.createElement("option"); o.value=t; o.textContent=t; ftEl.appendChild(o); });

  const crs = [...new Set(monsters.map(m=>m.challenge?.rating).filter(Boolean))].sort(crSort);
  const fcEl = document.getElementById("fcr");
  crs.forEach(c => { const o=document.createElement("option"); o.value=c; o.textContent=`CR ${c}`; fcEl.appendChild(o); });

  // Populate spell dropdowns
  const levels = [...new Set(spells.map(s=>s.level))].sort((a,b)=>a-b);
  const flEl = document.getElementById("flevel");
  levels.forEach(l => {
    const o=document.createElement("option"); o.value=l;
    o.textContent = l===0 ? "Cantrip" : `Level ${l}`;
    flEl.appendChild(o);
  });

  const schools = [...new Set(spells.map(s=>s.school).filter(Boolean))].sort();
  const fsEl = document.getElementById("fschool");
  schools.forEach(sc => { const o=document.createElement("option"); o.value=sc; o.textContent=sc; fsEl.appendChild(o); });

  const classes = [...new Set(spells.flatMap(s=>s.classes||[]))].sort();
  const fcSpEl = document.getElementById("fclass");
  classes.forEach(c => { const o=document.createElement("option"); o.value=c; o.textContent=c; fcSpEl.appendChild(o); });

  // Initial render — monsters tab
  buildList();
  if (state.monsters.filtered.length) pick(0);

}).catch(err => {
  document.getElementById("main").innerHTML =
    `<div class="empty">Failed to load data: ${esc(String(err))}<br>Make sure the server is running from the project root.</div>`;
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP handler — serves the app and both JSON files
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

        elif self.path == "/spells.json":
            body = SPELLS_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path in _OPTIONAL_FILES:
            # Return the file if it exists, or an empty array when not yet built.
            f = _OPTIONAL_FILES[self.path]
            body = f.read_bytes() if f.exists() else b"[]"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


def main():
    missing = [f for f in (MONSTERS_FILE, SPELLS_FILE) if not f.exists()]
    if missing:
        for f in missing:
            print(f"Error: {f} not found. Run python3 run_all.py first.")
        sys.exit(1)

    server = HTTPServer(("", PORT), Handler)
    print(f"SRD Viewer →  http://localhost:{PORT}")
    print("  ⚔ Monsters  |  ✦ Spells  (press M / S to switch tabs with keyboard)")
    print("  ✧ Magic Items  |  ✧ Feats  |  ✧ Classes  |  ✧ Species  |  ✧ Origins  (stubs — no data yet)")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
