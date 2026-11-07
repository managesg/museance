// Fills runs/<app>/ from the committed case files, so the stage shows P4's numbers instead of a stale local run.
// Run from court/ui: `npm run seed -- todo`. runs/ is gitignored, so a hand-made run there silently outranks cases/.
// Before = cases/<app>/v1-16claims, after = v2-16claims; claims, evidence and sheet come from dig/out/<app>/.
import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';

const ROOT = resolve(import.meta.dirname, '../../..');
const app = process.argv[2] ?? '';
if (!/^[a-z0-9-]+$/.test(app) || !existsSync(join(ROOT, 'cases', app, 'v1-16claims'))) {
  console.error(`seed-runs: no committed v1/v2 case for "${app}" (cases/${app}/v1-16claims)`);
  process.exit(1);
}
const out = join(ROOT, 'runs', app);
rmSync(out, { recursive: true, force: true }); // a stale ledger.jsonl or 8-claim verdicts.json must not survive
mkdirSync(join(out, 'after'), { recursive: true });
const copy = (from: string, to: string) => cpSync(join(ROOT, from), join(out, to));
for (const f of ['claims', 'evidence', 'sheet']) copy(`dig/out/${app}/${f}.json`, `${f}.json`);
copy(`cases/${app}/attacks.json`, 'attacks.json');
for (const f of ['verdicts', 'locks']) {
  copy(`cases/${app}/v1-16claims/${f}.json`, `${f}.json`);
  copy(`cases/${app}/v2-16claims/${f}.json`, `after/${f}.json`);
}
console.log(`seed-runs: runs/${app} written from cases/${app}`);
