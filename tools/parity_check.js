// node tools/parity_check.js worlds.json fairslot.html  -> compares the page's JS engine with Python results
const fs = require("fs"), crypto = require("crypto");
const html = fs.readFileSync(process.argv[3], "utf8");
const src = html.slice(html.indexOf("/*ENGINE*/"), html.indexOf("/*END-ENGINE*/"));
const FS = new Function(src + "; return FS;")();
// sha256 against node's
for (const s of ["", "abc", "x".repeat(55), "y".repeat(56), "z".repeat(64), "кириллица|слот|a1", "q".repeat(1000)]) {
  const a = FS.hex(FS.sha256(FS.utf8(s))), b = crypto.createHash("sha256").update(s).digest("hex");
  if (a !== b) { console.error("SHA MISMATCH", s.slice(0, 10)); process.exit(1); }
}
const worlds = JSON.parse(fs.readFileSync(process.argv[2], "utf8")); let bad = 0, maxd = 0;
for (const [i, w] of worlds.entries()) {
  const r = FS.run(w.cfg, w.slots, w.apps, w.mem, w.hist, w.seed, w.now), p = w.res;
  const pick = x => JSON.stringify([x.allocations, x.waitlist, x.rejected, x.not_due]);
  if (pick(r) !== pick(p)) { bad++; if (bad < 4) console.error("DIFF world", i, "\nJS", pick(r).slice(0, 400), "\nPY", pick(p).slice(0, 400)); continue; }
  for (const [sid, rows] of Object.entries(p.audit.slots)) rows.forEach((row, j) => { const q = r.audit.slots[sid][j]; maxd = Math.max(maxd, Math.abs(q.key - row.key), Math.abs(q.weight - row.weight)); });
  if (!FS.verify(r)[0] || !FS.verify(p)[0]) { bad++; console.error("verify failed", i); }
}
console.log(`worlds=${worlds.length} mismatches=${bad} max|key diff|=${maxd}`);
process.exit(bad ? 1 : 0);
