// The report UI. Reads the embedded export, recomputes with compute.js and
// renders the ranked table. No network calls. Values are simulated gross
// yearly revenue per battery block, before any host share, unvalidated.
(function () {
  "use strict";
  const DATA = JSON.parse(document.getElementById("export-data").textContent);
  const M = DATA.manifest;
  const C = window.Compute;
  const REGIONS = { metro_south: "Metro South", worcester: "Worcester" };
  const FLAG_WORDS = {
    capped: "one block's cut is at its power limit",
    rate_area_unconfirmed: "Eversource rate area unconfirmed",
    no_open_profile: "no open load profile, so a wide simulated range",
    eversource_all_hours: "Eversource billing approximated with the all-hours peak",
    placeholder_mix: "load profile is a pooled mix of types",
  };
  const state = {
    region: "metro_south",
    sort: "rank",
    dir: 1,
    settings: C.defaults(M),
    filters: { segment: "", utility: "", minValue: 0 },
  };
  const cache = {};

  const usd = (x) => "$" + Math.round(x).toLocaleString("en-US");
  const pct = (x) => Math.round(x * 100) + "%";
  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  function flagWords(site) {
    const out = [site.tier === 1 ? "measured electricity (LBER)" : "estimated electricity"];
    for (const f of site.flags) {
      if (FLAG_WORDS[f]) out.push(FLAG_WORDS[f]);
      else if (f.indexOf("intensity: ") === 0) out.push("energy use estimated from " + f.slice(11));
    }
    if (!site.passes_200kw) out.push("estimated peak under 200 kW");
    return out;
  }

  // Ranked rows for a region under some settings, cached by both.
  function scored(region, settings) {
    const key = region + JSON.stringify(settings);
    if (!cache[key]) cache[key] = rank(region, settings);
    return cache[key];
  }

  function rank(region, settings) {
    const sites = DATA.regions[region];
    const off = Object.assign({}, settings, { connected_solutions: false });
    const on = Object.assign({}, settings, { connected_solutions: true });
    const rows = sites.map((s) => ({
      site: s,
      demand_only: C.siteSummary(s, M, off),
      with_cs: C.siteSummary(s, M, on),
    }));
    const main = (r) => (settings.connected_solutions ? r.with_cs : r.demand_only);
    rows.sort(
      (a, b) =>
        main(b).value_per_block.p50 - main(a).value_per_block.p50 ||
        main(b).blocks - main(a).blocks ||
        main(b).total.p50 - main(a).total.p50 ||
        (a.site.site_id < b.site.site_id ? -1 : 1)
    );
    rows.forEach((r, i) => {
      r.rank = i + 1;
      r.main = main(r);
      r.percentile = rows.length > 1 ? (rows.length - 1 - i) / (rows.length - 1) : 1;
    });
    return rows;
  }

  const COLUMNS = [
    ["rank", "Rank", (r) => r.rank, "num"],
    ["owner", "Owner", (r) => r.site.owner || ""],
    ["town", "Town", (r) => r.site.town],
    ["segment", "Segment", (r) => r.site.segment],
    ["value", "Value per block, P50", (r) => r.main.value_per_block.p50, "num"],
    ["with_cs", "With ConnectedSolutions", (r) => r.with_cs.value_per_block.p50, "num"],
    ["demand_only", "Demand savings only", (r) => r.demand_only.value_per_block.p50, "num"],
    ["percentile", "Percentile in region", (r) => r.percentile, "num"],
    ["blocks", "Blocks", (r) => r.main.blocks, "num"],
    ["total", "Total, P50", (r) => r.main.total.p50, "num"],
    ["cs_share", "ConnectedSolutions share", (r) => r.main.streams.connected_solutions.share, "num"],
    ["size_rank", "Size-only rank", (r) => r.site.size_rank, "num"],
    ["moved", "Moved", (r) => r.moved, "num"],
  ];

  function cell(key, r) {
    const v = r.main.value_per_block;
    switch (key) {
      case "rank": return String(r.rank);
      case "owner": return esc(r.site.owner) + '<div class="band">' + esc(r.site.site_addr) + "</div>";
      case "town": return esc(r.site.town);
      case "segment": return esc(r.site.segment);
      case "value": return usd(v.p50) + '<div class="band">' + usd(v.p10) + " to " + usd(v.p90) + "</div>";
      case "with_cs": return usd(r.with_cs.value_per_block.p50);
      case "demand_only": return usd(r.demand_only.value_per_block.p50);
      case "percentile": return pct(r.percentile);
      case "blocks": return r.main.blocks.toFixed(1);
      case "total": return usd(r.main.total.p50);
      case "cs_share": return pct(r.main.streams.connected_solutions.share);
      case "size_rank": return String(r.site.size_rank);
      case "moved": return r.moved === 0 ? "" : (r.moved > 0 ? "up " : "down ") + Math.abs(r.moved);
    }
    return "";
  }

  function render() {
    const base = scored(state.region, C.defaults(M));
    const baseRank = {};
    base.forEach((r) => { baseRank[r.site.site_id] = r.rank; });
    const all = scored(state.region, state.settings);
    all.forEach((r) => { r.moved = baseRank[r.site.site_id] - r.rank; });
    const f = state.filters;
    const rows = all.filter((r) =>
      (!f.segment || r.site.segment === f.segment) &&
      (!f.utility || r.site.utility === f.utility) &&
      r.main.value_per_block.p50 >= f.minValue
    );
    const col = COLUMNS.find((c) => c[0] === state.sort) || COLUMNS[0];
    rows.sort((a, b) => {
      const x = col[2](a), y = col[2](b);
      return (x < y ? -1 : x > y ? 1 : 0) * state.dir;
    });
    const head = COLUMNS.map(
      (c) => '<th class="' + (c[3] || "") + '" data-key="' + c[0] + '">' + c[1] +
        (state.sort === c[0] ? (state.dir > 0 ? " ▲" : " ▼") : "") + "</th>"
    ).join("") + "<th>Data quality</th>";
    const body = rows.map((r, i) =>
      '<tr data-i="' + i + '" tabindex="0">' + COLUMNS.map((c) => '<td class="' + (c[3] || "") + '">' + cell(c[0], r) + "</td>").join("") +
      '<td class="flags">' + esc(flagWords(r.site).join("; ")) + "</td></tr>"
    ).join("");
    document.getElementById("table").innerHTML = "<thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody>";
    document.querySelectorAll("#table th[data-key]").forEach((th) =>
      th.addEventListener("click", () => {
        const k = th.dataset.key;
        state.dir = state.sort === k ? -state.dir : (k === "rank" || k === "size_rank" || k === "owner" || k === "town" || k === "segment" ? 1 : -1);
        state.sort = k;
        render();
      })
    );
    document.querySelectorAll("#table tbody tr").forEach((tr) => {
      const open = () => showDetail(rows[Number(tr.dataset.i)]);
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter") open(); });
    });
    renderSummary(all);
    document.getElementById("count").textContent =
      rows.length + " of " + all.length + " scored sites shown";
  }

  function settingsPanel() {
    const rates = state.settings.rates;
    const rateInputs = Object.keys(rates).map((u) =>
      Object.keys(rates[u]).map((sched) =>
        "<label>" + esc(u) + " " + sched + ' $<input type="number" step="0.01" min="0" data-utility="' +
        esc(u) + '" data-schedule="' + sched + '" value="' + rates[u][sched] + '"> per kW-month</label>'
      ).join("")
    ).join("");
    const opts = (vals) => '<option value="">all</option>' +
      vals.map((v) => '<option value="' + esc(v) + '">' + esc(v) + "</option>").join("");
    const every = Object.values(DATA.regions).flat();
    const segments = [...new Set(every.map((s) => s.segment))].sort();
    const utilities = [...new Set(every.map((s) => s.utility))].sort();
    document.getElementById("settings").innerHTML =
      "<h2>Settings</h2>" +
      '<p class="muted">Recomputed in your browser from the export. Defaults are the model\'s own inputs.</p>' +
      '<div class="controls"><label><input type="checkbox" id="cs"' +
      (state.settings.connected_solutions ? " checked" : "") + "> Include ConnectedSolutions</label>" +
      '<button type="button" id="reset">Reset to model defaults</button></div>' +
      '<div class="controls">' + rateInputs + "</div>" +
      "<h2>Filters</h2>" +
      '<div class="controls"><label>Segment <select id="f-segment">' + opts(segments) + "</select></label>" +
      '<label>Utility <select id="f-utility">' + opts(utilities) + "</select></label>" +
      '<label>Minimum value per block $<input type="number" id="f-min" min="0" step="1000" value="' +
      state.filters.minValue + '"></label></div>';
    document.getElementById("f-segment").value = state.filters.segment;
    document.getElementById("f-utility").value = state.filters.utility;
    document.getElementById("cs").addEventListener("change", (e) => {
      state.settings = Object.assign({}, state.settings, { connected_solutions: e.target.checked });
      render();
    });
    document.querySelectorAll("#settings input[data-utility]").forEach((el) =>
      el.addEventListener("change", () => {
        const v = Number(el.value);
        if (!(v >= 0)) return;
        const r = JSON.parse(JSON.stringify(state.settings.rates));
        r[el.dataset.utility][el.dataset.schedule] = v;
        state.settings = Object.assign({}, state.settings, { rates: r });
        render();
      })
    );
    document.getElementById("reset").addEventListener("click", () => {
      state.settings = C.defaults(M);
      settingsPanel();
      render();
    });
    document.getElementById("f-segment").addEventListener("change", (e) => { state.filters.segment = e.target.value; render(); });
    document.getElementById("f-utility").addEventListener("change", (e) => { state.filters.utility = e.target.value; render(); });
    document.getElementById("f-min").addEventListener("change", (e) => { state.filters.minValue = Number(e.target.value) || 0; render(); });
  }

  const DRIVER_WORDS = {
    reduction_share: "share of the peak one block cuts",
    load_factor: "load factor",
    peak_kw: "estimated peak",
    annual_kwh: "yearly electricity",
    blocks: "number of blocks",
  };

  function drivers(list) {
    return list.map((d) => {
      const m = d.match(/^(\S+) ([+-][\d.]+)$/);
      return m ? (DRIVER_WORDS[m[1]] || m[1]) + " (" + m[2] + ")" : d;
    });
  }

  function mapLink(site) {
    const lat = site.lat.toFixed(6), lon = site.lon.toFixed(6);
    return "https://www.openstreetmap.org/?mlat=" + lat + "&mlon=" + lon + "#map=18/" + lat + "/" + lon;
  }

  function showDetail(r) {
    const s = r.site;
    const list = (xs) => "<ul>" + xs.map((x) => "<li>" + esc(x) + "</li>").join("") + "</ul>";
    const parcels = s.parcels.map((p) =>
      "<tr><td>" + esc(p.loc_id) + "</td><td>" + esc(p.site_addr) + "</td><td>" + esc(p.use_code) +
      " " + esc(p.use_desc) + "</td><td>" + esc(p.owner) + "</td></tr>").join("");
    const buildings = s.buildings.map((b) =>
      "<tr><td>" + esc(b.building_id) + '</td><td class="num">' +
      (b.area_sqft == null ? "" : b.area_sqft.toLocaleString("en-US")) + "</td><td>" + esc(b.area_source) +
      "</td><td>" + esc(b.electricity_source) + '</td><td class="num">' +
      (b.grid_kwh == null ? "" : b.grid_kwh.toLocaleString("en-US")) + "</td></tr>").join("");
    const v = r.main.value_per_block;
    document.getElementById("detail").hidden = false;
    document.getElementById("detail").innerHTML =
      '<button id="close-detail" type="button">Close</button>' +
      "<h2>" + esc(s.owner) + ", " + esc(s.site_addr) + ", " + esc(s.town) + "</h2>" +
      "<p>Rank " + r.rank + " in " + REGIONS[state.region] + ". Value per block " + usd(v.p50) +
      " a year (P10 " + usd(v.p10) + " to P90 " + usd(v.p90) + "), " + r.main.blocks.toFixed(1) +
      " blocks expected. Segment " + esc(s.segment) + ", " + esc(s.utility) + ".</p>" +
      '<p><a href="' + mapLink(s) + '" target="_blank" rel="noopener noreferrer">Map of the site location</a>' +
      ' <span class="muted">(opens OpenStreetMap; nothing is loaded until you click)</span></p>' +
      "<h3>Evidence</h3>" + list(flagWords(s)) +
      "<h3>Top drivers of its value</h3>" +
      (r.site.scenarios.with_connected_solutions.top_drivers.length
        ? list(drivers(r.site.scenarios.with_connected_solutions.top_drivers))
        : "<p class=\"muted\">None stand out across its draws.</p>") +
      "<h3>Parcels (" + s.parcels.length + ")</h3>" +
      '<div class="table-wrap"><table><thead><tr><th>Parcel</th><th>Address</th><th>Use</th><th>Owner</th></tr></thead><tbody>' +
      parcels + "</tbody></table></div>" +
      "<h3>Candidate buildings (" + s.buildings.length + ")</h3>" +
      '<div class="table-wrap"><table><thead><tr><th>Building</th><th class="num">Floor area, sq ft</th>' +
      '<th>Area source</th><th>Electricity</th><th class="num">Measured kWh</th></tr></thead><tbody>' +
      buildings + "</tbody></table></div>";
    document.getElementById("close-detail").addEventListener("click", () => {
      document.getElementById("detail").hidden = true;
    });
    document.getElementById("detail").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderSummary(rows) {
    const withCs = rows.map((r) => r.with_cs);
    const share = C.connectedSolutionsShare(withCs);
    const full = C.fullGridValue(M, state.settings);
    const eligible = rows.filter((r) => M.connected_solutions.eligible_utilities.indexOf(r.site.utility) >= 0);
    const limited = eligible.filter((r) => r.with_cs.streams.connected_solutions.p50 < full - 1).length;
    document.getElementById("cs-note").innerHTML =
      "ConnectedSolutions pays every eligible site the same per block, " + usd(full) +
      " a year, unless something caps it. At " + limited + " of the " + eligible.length +
      " eligible sites in " + REGIONS[state.region] +
      " it is capped, because the building's own 3 to 8 pm load (or the program's export cap) limits what a block can deliver. " +
      "Across this region ConnectedSolutions is " + pct(share) + " of P50 value per block" +
      (share > 0.5 ? ", so more than half of the ranking rests on it." : ".");
  }

  function regionButtons() {
    const el = document.getElementById("regions");
    el.innerHTML = Object.keys(REGIONS).map(
      (k) => '<button class="region" data-region="' + k + '" aria-pressed="' + (k === state.region) + '">' + REGIONS[k] + "</button>"
    ).join("");
    el.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => {
        state.region = b.dataset.region;
        regionButtons();
        render();
      })
    );
  }

  regionButtons();
  settingsPanel();
  render();
})();
