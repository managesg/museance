// Same chain as court/ledger.py: hash = sha256(prev_hash + canon(payload)), genesis is 64 zeros.
import type { CaseBundle, LedgerEvent } from '../contracts';
import { claimVerdicts, deriveLock } from './scoring';

export const GENESIS = '0'.repeat(64);

export async function sha256Hex(text: string): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
}

/** CONTRACTS.md canon: sorted keys, no spaces, non-ASCII kept as is. */
// shortcut: a whole-number float prints as 1 here but 1.0 in Python; only matters if a synthesized chain is checked by court/ledger.py.
export function canon(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canon).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    const o = value as Record<string, unknown>;
    const keys = Object.keys(o).filter((k) => o[k] !== undefined).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canon(o[k])}`).join(',')}}`;
  }
  return JSON.stringify(value ?? null);
}

/** eval/commit.py: sha256 of the object without its commit field. */
export function commitOf(obj: object): Promise<string> {
  return sha256Hex(canon({ ...obj, commit: undefined }));
}

const nowTs = () => new Date().toISOString().replace(/\.\d{3}Z$/, '+00:00');

/** The next event on the chain. */
export async function appendEvent(chain: LedgerEvent[], type: string, payload: unknown, ts = nowTs()): Promise<LedgerEvent> {
  const last = chain.at(-1);
  const prev_hash = last?.hash ?? GENESIS;
  return { seq: (last?.seq ?? 0) + 1, ts, type, payload, prev_hash, hash: await sha256Hex(prev_hash + canon(payload)) };
}

export async function verifyLedger(events: LedgerEvent[]): Promise<boolean> {
  let prev = GENESIS;
  for (const [i, e] of events.entries()) {
    if (e.seq !== i + 1 || e.prev_hash !== prev || e.hash !== (await sha256Hex(prev + canon(e.payload)))) return false;
    prev = e.hash;
  }
  return true;
}

/** A real hash chain for a bundle that arrived without its ledger (fixture mode). */
export async function synthesizeLedger(bundle: CaseBundle): Promise<LedgerEvent[]> {
  if (bundle.ledger.length) return bundle.ledger;
  const byRef = claimVerdicts(bundle.verdicts);
  const locks = bundle.locks.length
    ? bundle.locks
    : bundle.claims.flatMap((c) => {
        const status = deriveLock(c, byRef.get(c.id));
        return status ? [{ claim_id: c.id, status }] : [];
      });
  const entries: [string, unknown][] = [];
  for (const c of bundle.claims) entries.push(['claim_committed', { kind: 'claim', ref: c.id, commit: await commitOf(c) }]);
  for (const a of bundle.attacks) entries.push(['attack_committed', { kind: 'attack', ref: a.id, commit: await commitOf(a) }]);
  for (const v of bundle.verdicts) entries.push(['verdict', v]);
  for (const l of locks) entries.push(['lock', l]);
  for (const r of bundle.repairs) {
    const ids = { struck_id: r.struck_id, claim_id: r.claim.id };
    entries.push(['repair', { ...ids, status: deriveLock(r.claim, r.verdict), note: r.note }]);
    if (r.rollback) entries.push(['rollback', { ...ids, note: r.note }]);
  }
  const ts = nowTs();
  const chain: LedgerEvent[] = [];
  for (const [type, payload] of entries) chain.push(await appendEvent(chain, type, payload, ts));
  return chain;
}
