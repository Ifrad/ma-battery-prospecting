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
  const state = { region: "metro_south", sort: "rank", dir: 1, settings: C.defaults(M) };

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

  function scored(region, settings) {
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
    }
    return "";
  }

  function render() {
    const rows = scored(state.region, state.settings);
    const col = COLUMNS.find((c) => c[0] === state.sort) || COLUMNS[0];
    rows.sort((a, b) => {
      const x = col[2](a), y = col[2](b);
      return (x < y ? -1 : x > y ? 1 : 0) * state.dir;
    });
    const head = COLUMNS.map(
      (c) => '<th class="' + (c[3] || "") + '" data-key="' + c[0] + '">' + c[1] +
        (state.sort === c[0] ? (state.dir > 0 ? " ▲" : " ▼") : "") + "</th>"
    ).join("") + "<th>Data quality</th>";
    const body = rows.map((r) =>
      "<tr>" + COLUMNS.map((c) => '<td class="' + (c[3] || "") + '">' + cell(c[0], r) + "</td>").join("") +
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
    renderSummary(rows);
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
    document.getElementById("count").textContent = rows.length + " scored sites";
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
  render();
})();
