// Parity of the report's JavaScript (prospect/report/compute.js, the file the
// page inlines) with the Python reference (prospect/export/recompute.py) and
// the Python model's exported values. Run by tests/test_report_node.py, which
// writes the Python expectations to PARITY_EXPECTED. No npm packages.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..", "..");
const C = require(path.join(ROOT, "prospect", "report", "compute.js"));
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "export", "manifest.json")));
const sites = ["metro_south", "worcester"].flatMap((r) =>
  JSON.parse(fs.readFileSync(path.join(ROOT, "export", r + ".geojson"))).features.map((f) => f.properties)
);
const expected = JSON.parse(fs.readFileSync(process.env.PARITY_EXPECTED));

function settingsFor(name) {
  const s = C.defaults(manifest);
  if (name === "cs_off") s.connected_solutions = false;
  if (name === "rate_up") {
    for (const u of Object.keys(s.rates)) for (const k of Object.keys(s.rates[u])) s.rates[u][k] *= 1.25;
  }
  return s;
}

function close(actual, want, tol, label) {
  assert.ok(Math.abs(actual - want) <= tol, label + ": " + actual + " vs " + want);
}

for (const name of Object.keys(expected.cases)) {
  test("matches the Python reference: " + name, () => {
    const settings = settingsFor(name);
    for (const site of sites) {
      const want = expected.cases[name][site.site_id];
      const got = C.siteSummary(site, manifest, settings);
      for (const q of ["p10", "p50", "p90"]) {
        close(got.value_per_block[q], want.value_per_block[q], 0.01, site.site_id + " " + name + " value " + q);
        close(got.total[q], want.total[q], 0.01, site.site_id + " " + name + " total " + q);
      }
      close(got.blocks, want.blocks, 1e-9, site.site_id + " blocks");
      close(got.streams.connected_solutions.share, want.cs_share, 1e-9, site.site_id + " share");
    }
  });
}

test("matches the Python model's exported values at default settings", () => {
  for (const [scenario, csOn] of [["demand_savings", false], ["with_connected_solutions", true]]) {
    const settings = Object.assign(C.defaults(manifest), { connected_solutions: csOn });
    for (const site of sites) {
      const got = C.siteSummary(site, manifest, settings);
      const e = site.scenarios[scenario];
      for (const q of ["p10", "p50", "p90"]) close(got.value_per_block[q], e.value_per_block[q], 10, site.site_id + " " + q);
      close(got.streams.connected_solutions.share, e.streams.connected_solutions.share, 0.01, site.site_id + " share");
    }
  }
});

test("the ConnectedSolutions share across sites matches Python", () => {
  const settings = C.defaults(manifest);
  const share = C.connectedSolutionsShare(sites.map((s) => C.siteSummary(s, manifest, settings)));
  close(share, expected.cs_share, 1e-9, "share");
});

test("customer status matching uses the manifest's words", () => {
  const rows = C.parseCsv('owner,address,town,status\n"Example, Inc.",,,customer\n,9 Main Street,Townsville,contacted\n');
  const fake = [
    { site_id: "a", owner: "EXAMPLE INC", site_addr: "1 ELM ST", town: "Other", parcels: [] },
    { site_id: "b", owner: "X", site_addr: "9 MAIN ST", town: "Townsville", parcels: [] },
    { site_id: "c", owner: "Y", site_addr: "9 MAIN ST", town: "Elsewhere", parcels: [] },
  ];
  assert.deepEqual(C.matchStatuses(fake, rows, manifest.owner_drop_words, manifest.address_words), {
    a: "customer",
    b: "contacted",
  });
});
