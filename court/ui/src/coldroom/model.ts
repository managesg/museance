// Cold Room Court data: P1's Modbus sample run (origin/ics-lab court/ics/sample_run), read as is.
// Every number on the screen comes from these five files.
import type { LedgerEvent, Verdict } from '../contracts';
import attacksJson from './sample_run/attacks.json';
import claimsJson from './sample_run/claims.json';
import ledgerRaw from './sample_run/ledger.jsonl?raw';
import locksJson from './sample_run/locks.json';
import verdictsJson from './sample_run/verdicts.json';

export type Side = 'original' | 'revival';

export interface Item {
  id: string;
  kind: 'claim' | 'attack';
  text: string;
  steps: string[];
  verdict: Verdict | null;
  locked: boolean;
}

// Names only; the setpoint each one writes is read from its steps.
const ATTACK_NAMES: Record<string, string> = {
  'sec-setpoint': 'Unauthenticated write',
  'sec-setpoint-range': 'Out-of-range write, right PIN',
  'sec-wrong-pin': 'Write with a wrong PIN',
};

/** 'hr0=40,coil0=1' -> { hr0: 40, coil0: 1 } */
export function regs(observed: string): Record<string, number> {
  return Object.fromEntries(
    observed
      .split(',')
      .filter((kv) => kv.includes('='))
      .map((kv) => {
        const [k, v] = kv.split('=');
        return [k.trim(), Number(v)];
      }),
  );
}

/** Registers hold tenths of a degree. */
export const celsius = (tenths: number | undefined) => (tenths == null || Number.isNaN(tenths) ? '—' : (tenths / 10).toFixed(1));

/** Simulated seconds a test runs: the sum of its tick steps (each test starts a fresh controller at 0). */
export const simSeconds = (steps: string[]) =>
  steps.reduce((t, s) => (s.startsWith('tick:') ? t + Number(s.slice(5)) : t), 0);

export function hms(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  return [h && `${h} h`, m && `${m} min`, r && `${r} s`].filter(Boolean).join(' ') || '0 s';
}

/** The setpoint value the test writes (hr:1=<v>), or null when it writes none. */
export function writtenSetpoint(steps: string[]): number | null {
  const last = steps.filter((s) => /^hr:1=\d+$/.test(s)).at(-1);
  return last ? Number(last.slice(5)) : null;
}

/** Did this build take the setpoint write? null when the test writes no setpoint. */
export function writeTaken(item: Item, side: Side): boolean | null {
  const v = writtenSetpoint(item.steps);
  if (v == null || !item.verdict) return null;
  return regs(item.verdict[side]).hr1 === v;
}

export function buildItems(
  claims: { id: string; text: string; test: { steps: string[] } }[],
  attacks: { id: string; steps: string[] }[],
  verdicts: Verdict[],
  locks: { claim_id: string; status: string }[],
): Item[] {
  const byRef = new Map(verdicts.map((v) => [v.ref, v]));
  const locked = new Set(locks.filter((l) => l.status === 'LOCKED').map((l) => l.claim_id));
  return [
    ...claims.map((c) => ({
      id: c.id,
      kind: 'claim' as const,
      text: c.text,
      steps: c.test.steps,
      verdict: byRef.get(c.id) ?? null,
      locked: locked.has(c.id),
    })),
    ...attacks.map((a) => {
      const v = writtenSetpoint(a.steps);
      const name = ATTACK_NAMES[a.id] ?? a.id;
      return {
        id: a.id,
        kind: 'attack' as const,
        text: v == null ? name : `${name}: setpoint → ${celsius(v)}\u00a0°C`,
        steps: a.steps,
        verdict: byRef.get(a.id) ?? null,
        locked: false,
      };
    }),
  ];
}

export interface Summary {
  controls: number;
  identical: number;
  locked: number;
  attacks: number;
  blocked: number;
  flaky: number;
}

export function summarize(items: Item[]): Summary {
  const claims = items.filter((i) => i.kind === 'claim');
  const attacks = items.filter((i) => i.kind === 'attack');
  return {
    controls: claims.length,
    identical: claims.filter((i) => i.verdict?.match && !i.verdict.flaky).length,
    locked: claims.filter((i) => i.locked).length,
    attacks: attacks.length,
    // Blocked: the legacy build took the write, the patched build kept its setpoint, and the court saw them differ.
    blocked: attacks.filter((i) => i.verdict && !i.verdict.match && writeTaken(i, 'original') && writeTaken(i, 'revival') === false).length,
    flaky: items.filter((i) => i.verdict?.flaky).length,
  };
}

export const parseLedger = (raw: string): LedgerEvent[] =>
  raw
    .split('\n')
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l) as LedgerEvent);

/** The ref an event is about: commit/verdict payloads carry ref, lock payloads claim_id. */
export function refOf(e: LedgerEvent): string | null {
  const p = e.payload as { ref?: string; claim_id?: string } | null;
  return p?.ref ?? p?.claim_id ?? null;
}

export const ITEMS = buildItems(claimsJson, attacksJson, verdictsJson as unknown as Verdict[], locksJson);
export const EVENTS = parseLedger(ledgerRaw);
export const SUMMARY = summarize(ITEMS);
export const MAX_SIM = Math.max(...ITEMS.map((i) => simSeconds(i.steps)));
