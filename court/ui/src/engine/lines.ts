// Subtitles, keyed by beat kind and outcome. McClusky speaks only here; each joke leans on a number on screen.
import type { Claim, Verdict } from '../contracts';
import { prettyOutput } from './format';
import type { StageState } from './types';

export type Subtitle = NonNullable<StageState['subtitle']>;

export interface LineCtx {
  i?: number; n?: number; app?: string; id?: string; screen?: string; steps?: number; words?: number; bonds?: number;
  claim?: Claim; verdict?: Verdict | null; delta?: number; reason?: string; diverge?: number; flaky?: number;
  credibility?: number; start?: number; fidelity?: number | null; brier?: number | null; rollbacks?: number;
}

const mc = (text: string): Subtitle => ({ who: 'McCLUSKY', text });
const hoot = (text: string): Subtitle => ({ who: 'DR. HOOT', text });
const clerk = (text: string): Subtitle => ({ who: 'THE CLERK', text });
const pick = (i: number | undefined, ...xs: string[]) => xs[(i ?? 0) % xs.length];
const pct = (x = 0) => `${Math.round(x * 100)}%`;
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
// Observed text can be a whole paragraph and the subtitle bar holds one projector line.
const clip = (raw: string | undefined, n = 14) => {
  const s = raw === undefined ? undefined : prettyOutput(raw);
  return s === undefined ? '?' : s === '' ? 'blank' : s.length > n ? `${s.slice(0, n - 3)}...` : s;
};

const LINES: Record<string, (c: LineCtx) => Subtitle> = {
  open: (c) => clerk(`Court is in session. The case of ${c.app}.`),
  'dig:first': (c) => clerk(`The dig: ${c.n} exhibits recovered.`),
  'dig:quip': (c) => mc(`${c.n} exhibits. I've won cases on less. Not many.`),
  'read:first': (c) => clerk(`The reader takes in ${c.words} words.`),
  'read:quip': (c) => mc(`${c.n} lines from ${c.words} words. I read the first one.`),
  // No "this is the peak": a run of locks lifts credibility past the start (the fixture reaches 1028).
  raise: (c) => mc(`Credibility ${c.start}. Savor it.`),
  risen: () => clerk('The revival is live.'),

  // One oath for the whole deal: a 900 ms card is too short to read a line per claim.
  swear: (c) => mc(`${c.n} claims, ${c.bonds} credits. My accountant objects.`),
  seal: (c) => hoot(`${c.n} attacks. Sealed blind.`),
  cross: ({ claim, i }) => {
    const screen = cap(claim?.screen ?? 'this');
    return hoot(pick(i, `${screen}. Run it.`, `${screen}. Show me.`, `${screen}. Again. Slowly.`));
  },

  'ruling:LOCKED': ({ claim, delta, i }) => {
    const p = pct(claim?.confidence);
    return mc(pick(i, `Locked. Plus ${delta}. Being ${p} right pays poorly.`, `Locked at ${p}. ${delta} credits for stating the obvious.`, `Plus ${delta}. Certainty is cheap at ${p}.`));
  },
  'ruling:STRUCK': ({ claim, verdict, i }) => {
    const said = clip(claim?.test.expect);
    const was = clip(verdict?.original);
    const bond = claim?.bond ?? 0;
    return mc(pick(i, `I said ${said}. It says ${was}. Minus ${bond}.`, `${was}, not ${said}. Minus ${bond}. Strike that. They did.`));
  },
  'ruling:FABRICATED': ({ verdict, delta }) =>
    delta ? mc(`Made it up. It says ${clip(verdict?.original)} anyway. Plus ${delta}.`) : mc('Made it up. No credits move.'),
  // Flaky is one way to be unsworn; an original that never loaded, or no verdict at all, is another.
  'ruling:UNSWORN': ({ verdict }) =>
    clerk(verdict?.flaky ? 'Two runs, two answers. Unsworn. No credits move.' : 'The court could not rule. Unsworn. No credits move.'),
  'ruling:PENDING': (c) => clerk(`No verdict yet. Claim ${c.id} stays sealed.`),

  'attack:match': ({ id, verdict }) => hoot(`${id}: ${clip(verdict?.original)} and ${clip(verdict?.revival)}. Pity.`),
  'attack:mismatch': ({ id, verdict }) => hoot(`${id}: ${clip(verdict?.original)} against ${clip(verdict?.revival)}. Noted.`),
  'attack:flaky': (c) => hoot(`${c.id}: two answers. Discounted.`),
  // Nothing replays an attack on the exhibits, so there is nothing to watch.
  'attack:pending': (c) => hoot(`${c.id}: ${c.steps} steps. No verdict yet.`),

  'attack:tally': ({ n, diverge, flaky }) => hoot(`+${n} more attacks: ${diverge} diverge, ${flaky} flaky`),

  // P4's repair reason, verbatim: it carries P4's measured numbers.
  repair: ({ reason }) => clerk(reason ?? ''),
  'repaired:rollback': ({ id, rollbacks }) => clerk(`Rolled back. Claim ${id} is unsworn. Rollbacks: ${rollbacks}.`),
  'repaired:unsworn': ({ id }) => clerk(`Claim ${id} is unsworn. No credits move.`),
  repaired: () => clerk('The repaired revival is live.'),
  rerule: ({ fidelity }) => clerk(`Re-ruled on the repaired revival. Fidelity ${fidelity ?? 'unmeasured'}.`),

  bench: () => clerk('The bench is open. Propose a test.'),
  'bench:match': ({ n, verdict }) => clerk(`Bench run ${n}: ${clip(verdict?.original)} and ${clip(verdict?.revival)}. They match.`),
  'bench:mismatch': ({ n, verdict }) => clerk(`Bench run ${n}: ${clip(verdict?.original)} against ${clip(verdict?.revival)}.`),
  'bench:flaky': (c) => clerk(`Bench run ${c.n}: two answers. Unsworn.`),

  sentence: ({ fidelity, credibility, brier }) =>
    clerk(`Fidelity ${fidelity ?? 'unmeasured'}. Credibility ${credibility}. Brier ${brier === null || brier === undefined ? 'unmeasured' : brier.toFixed(3)}.`),
  'farewell:relieved': ({ credibility = 0, start = 0 }) => mc(`Up ${credibility - start} credits. I'd like to thank the deceased.`),
  'farewell:nervous': ({ credibility = 0, start = 0 }) => mc(`Down ${start - credibility} credits. I'll appeal. To whom, unclear.`),
  'farewell:fainted': (c) => clerk(`Credibility ${c.credibility}. Counsel has fainted. Adjourned.`),
};

/** A Fetch mesh.* ledger event's caption, spoken by its agent. */
export function meshLine(e: { type: string; payload: unknown }): Subtitle | null {
  const p = (e.payload && typeof e.payload === 'object' ? e.payload : {}) as { caption?: unknown; agent?: unknown };
  if (!e.type.startsWith('mesh.') || typeof p.caption !== 'string') return null;
  return { who: typeof p.agent === 'string' && p.agent ? p.agent.toUpperCase() : 'THE CLERK', text: p.caption };
}

/** The line for a beat, falling back from "kind:outcome" to "kind". */
export function line(kind: string, outcome: string | null, ctx: LineCtx): Subtitle | null {
  const f = (outcome !== null && LINES[`${kind}:${outcome}`]) || LINES[kind];
  return f ? f(ctx) : null;
}
