// Runs a regression/claim file against fixtures/app1/index.html with a stub DOM. usage: node run_fixture.js <file.json>
const fs = require("fs"), path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "fixtures", "app1", "index.html"), "utf8");
const src = html.match(/<script>([\s\S]*)<\/script>/)[1];
const rows = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const list = Array.isArray(rows) ? rows : [...rows.good, ...rows.traps];
const out = {};
for (const r of list) {
  const els = {};
  const document = { getElementById: id => (els[id] ??= { innerText: id === "display" ? "0" : "" }) };
  new Function("document", src)(document);
  for (const st of r.steps) { const [k, sel] = st.split(":"); if (k === "click") els[sel.slice(1)].onclick(); }
  out[r.id] = els.display.innerText;
}
console.log(JSON.stringify(out));
