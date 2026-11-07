import type { CaseFile, LedgerEvent, Lock, Repair, Verdict } from '../contracts.ts';

// Parsers for the files other lanes write. No runtime imports: server/feed.ts loads this file under plain Node.

/**
 * P4's case YAML (eval/case.py writes one value per line, JSON-quoted). Not a general YAML parser:
 * '  - x' appends to the current list key, '  k: v' sets counts[k], 'key: v' sets a top-level value.
 */
export function parseCase(text: string): CaseFile {
  const out: Record<string, unknown> = {};
  const counts: Record<string, number | null> = {};
  let key = '';
  for (const line of text.split('\n')) {
    if (!line.trim()) continue;
    if (line.startsWith('  - ')) {
      const prev = out[key];
      out[key] = [...(Array.isArray(prev) ? prev : []), JSON.parse(line.slice(4))];
      continue;
    }
    const m = /^(\s*)([^:]+):\s*(.*)$/.exec(line);
    if (!m) continue;
    const [, indent, k, v] = m;
    if (indent) {
      counts[k] = JSON.parse(v);
      out.counts = counts;
    } else {
      key = k;
      out[k] = v === '[]' ? [] : v === '' ? null : JSON.parse(v);
    }
  }
  if (out.counts === null) out.counts = counts;
  return out as unknown as CaseFile;
}

/** One JSON object per line; a half-written or blank line is skipped. */
export const jsonLines = (text: string | null): unknown[] =>
  (text ?? '').split('\n').flatMap((line) => {
    try {
      return line.trim() ? [JSON.parse(line) as unknown] : [];
    } catch {
      return [];
    }
  });

/** P4's repairs.jsonl, keeping only rows that name a claim and a decision. */
export const parseRepairs = (text: string | null): Repair[] =>
  jsonLines(text).filter((r): r is Repair =>
    typeof r === 'object' && r !== null && 'claim_id' in r && 'decision' in r) as Repair[];

/** Verdicts and locks from the court's ledger, latest per ref, for while verdicts.json and locks.json are not written yet. */
export function fromLedger(ledger: unknown[]): { verdicts: Verdict[]; locks: Lock[] } {
  const verdicts = new Map<string, Verdict>();
  const locks = new Map<string, Lock>();
  for (const e of ledger as Partial<LedgerEvent>[]) {
    const p = e?.payload as Record<string, unknown> | undefined;
    if (!p) continue;
    if (e.type === 'verdict' && typeof p.ref === 'string') verdicts.set(p.ref, p as unknown as Verdict);
    if (e.type === 'lock' && typeof p.claim_id === 'string') locks.set(p.claim_id, p as unknown as Lock);
  }
  return { verdicts: [...verdicts.values()], locks: [...locks.values()] };
}
