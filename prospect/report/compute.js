// Recompute value per block, expected blocks and the stream split from the
// export, in the browser and in Node. A line-for-line mirror of
// prospect/export/recompute.py; tests/js/compute.test.js checks the two agree.
// Values are simulated gross yearly revenue per battery block, before any host
// share: not profit, not accurate, unvalidated.
(function (root) {
  "use strict";

  function defaults(manifest) {
    const cs = manifest.connected_solutions;
    return {
      connected_solutions: true,
      realization_factor: manifest.realization_factor.value,
      performance_factor: cs.performance_factor.value,
      overlap_factor: cs.overlap_factor.value,
      site_exports: cs.site_exports,
      rates: JSON.parse(JSON.stringify(manifest.demand_rates_usd_per_kw_month)),
    };
  }

  function valueDraws(site, manifest, settings) {
    const d = site.draws;
    const n = d.kwm_g2.length;
    const rates = settings.rates[site.utility];
    const g3rate = rates["G-3"] === undefined ? 0 : rates["G-3"];
    const scale = settings.realization_factor / manifest.realization_factor.value;
    const cs = manifest.connected_solutions;
    const eligible =
      settings.connected_solutions && cs.eligible_utilities.indexOf(site.utility) >= 0;
    const power = manifest.battery_block.power_kw;
    const perf = settings.performance_factor;
    const keep = 1 - settings.overlap_factor;
    const ratio = site.event_window;
    const demand = new Float64Array(n);
    const grid = new Float64Array(n);
    const value = new Float64Array(n);
    const total = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      demand[i] = (d.kwm_g2[i] * rates["G-2"] + d.kwm_g3[i] * g3rate) * scale;
      if (eligible) {
        let counted;
        if (settings.site_exports) {
          const ref = d.peak_kw[i] * (d.g3[i] ? ratio.peak_over_peak : 1);
          const cap = (cs.export_cap_share_of_site_peak * ref) / d.blocks[i];
          counted = Math.min(power, cap) * perf;
        } else {
          counted = Math.min(power * perf, (ratio.mean_over_peak * d.peak_kw[i]) / d.blocks[i]);
        }
        grid[i] = counted * keep * cs.usd_per_kw_season;
      }
      value[i] = demand[i] + grid[i];
      total[i] = value[i] * d.blocks[i];
    }
    return { demand: demand, grid: grid, value: value, total: total };
  }

  // numpy.percentile with linear interpolation.
  function percentile(x, q) {
    const s = Float64Array.from(x).sort();
    const pos = (s.length - 1) * (q / 100);
    const lo = Math.floor(pos);
    const hi = Math.min(lo + 1, s.length - 1);
    return s[lo] + (s[hi] - s[lo]) * (pos - lo);
  }

  function percentiles(x) {
    return { p10: percentile(x, 10), p50: percentile(x, 50), p90: percentile(x, 90) };
  }

  function mean(x) {
    let t = 0;
    for (let i = 0; i < x.length; i++) t += x[i];
    return t / x.length;
  }

  function siteSummary(site, manifest, settings) {
    const x = valueDraws(site, manifest, settings);
    const demand = percentile(x.demand, 50);
    const grid = percentile(x.grid, 50);
    const sum = demand + grid;
    return {
      value_per_block: percentiles(x.value),
      total: percentiles(x.total),
      blocks: mean(site.draws.blocks),
      streams: {
        demand_savings: { p50: demand, share: sum > 0 ? demand / sum : 0 },
        connected_solutions: { p50: grid, share: sum > 0 ? grid / sum : 0 },
      },
    };
  }

  // Share of P50 value from ConnectedSolutions across sites: the sum of each
  // stream's P50, as docs/SCORES.md computes it.
  function connectedSolutionsShare(summaries) {
    let demand = 0;
    let grid = 0;
    for (const s of summaries) {
      demand += s.streams.demand_savings.p50;
      grid += s.streams.connected_solutions.p50;
    }
    return demand + grid > 0 ? grid / (demand + grid) : 0;
  }

  // The most ConnectedSolutions pays one block when nothing caps it.
  function fullGridValue(manifest, settings) {
    const cs = manifest.connected_solutions;
    return (
      manifest.battery_block.power_kw *
      settings.performance_factor *
      (1 - settings.overlap_factor) *
      cs.usd_per_kw_season
    );
  }

  // A customer status file row matches a site by owner name or address,
  // normalized as sites are grouped and LBER addresses matched: upper case,
  // punctuation removed, owner company words dropped, street words
  // abbreviated (STREET to ST). A town, if given, must match too.
  function normalize(text, dropWords, abbreviations) {
    const drop = new Set(dropWords || []);
    const abbr = abbreviations || {};
    return String(text || "")
      .toUpperCase()
      .replace(/[^A-Z0-9]+/g, " ")
      .trim()
      .split(/\s+/)
      .filter((w) => w && !drop.has(w))
      .map((w) => abbr[w] || w)
      .join(" ");
  }

  // Minimal CSV: header row, commas, double-quoted fields with "" escapes.
  function parseCsv(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field); field = "";
        if (row.some((x) => x.trim() !== "")) rows.push(row);
        row = [];
      } else field += c;
    }
    row.push(field);
    if (row.some((x) => x.trim() !== "")) rows.push(row);
    if (!rows.length) return [];
    const head = rows[0].map((h) => h.trim().toLowerCase());
    return rows.slice(1).map((r) => {
      const o = {};
      head.forEach((h, j) => { o[h] = (r[j] || "").trim(); });
      return o;
    });
  }

  const STATUSES = ["customer", "contacted", "declined"];

  // The status of each site matched by a customer file: site_id to status.
  function matchStatuses(sites, entries, dropWords, addressWords) {
    const out = {};
    for (const e of entries) {
      const status = (e.status || "").toLowerCase();
      if (STATUSES.indexOf(status) < 0) continue;
      const owner = normalize(e.owner, dropWords);
      const address = normalize(e.address, [], addressWords);
      const town = normalize(e.town, []);
      for (const s of sites) {
        if (town && normalize(s.town, []) !== town) continue;
        const addresses = [s.site_addr].concat((s.parcels || []).map((p) => p.site_addr));
        const byOwner = owner && normalize(s.owner, dropWords) === owner;
        const byAddress =
          address && addresses.some((a) => normalize(a, [], addressWords) === address);
        if (byOwner || byAddress) out[s.site_id] = status;
      }
    }
    return out;
  }

  const api = {
    normalize: normalize,
    parseCsv: parseCsv,
    matchStatuses: matchStatuses,
    STATUSES: STATUSES,
    defaults: defaults,
    valueDraws: valueDraws,
    percentile: percentile,
    siteSummary: siteSummary,
    connectedSolutionsShare: connectedSolutionsShare,
    fullGridValue: fullGridValue,
  };
  root.Compute = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
