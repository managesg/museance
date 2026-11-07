// Turns a CaseBundle into the show: timed beats, each a pure step from one stage state to the next.
import type { Attack, CaseBundle, Claim, LedgerEvent, LockStatus, Verdict } from '../contracts';
import { betTotals, placeBets, settle, type Bet } from './bets';
import { line, type LineCtx } from './lines';
import { claimVerdicts, computeScores, credibilityDelta, deriveLock, fidelity } from './scoring';
import type { Beat, CardStatus, CardView, GuyKind, GuyState, Phase, Scores, StageState } from './types';

/** Fixture-mode exhibit pages; the stage may override the src fields when it renders. */
export const EXHIBIT_SRC = {
  original: '/exhibits/original/index.html',
  revival: '/revival-fixture/index.html',
  repaired: '/revival-fixture-repaired/index.html',
};

/** Bench runs submitted during the show; they land at the bench beat. */
export interface BenchRuns { verdicts: Verdict[]; events: LedgerEvent[]; }
const NO_BENCH: BenchRuns = { verdicts: [], events: [] };

const TAIL = 8;
const FAINT = 300;
const KEYCAPS: Record<string, string> = { add: '+', subtract: '-', multiply: '×', divide: '÷', clear: 'C' };
const CYCLE: GuyKind[] = ['calculator', 'brush', 'clock'];
const LOCKS: ReadonlySet<CardStatus> = new Set<CardStatus>(['LOCKED', 'STRUCK', 'UNSWORN', 'FABRICATED']);
const isLock = (st: CardStatus): st is LockStatus => LOCKS.has(st);

const RULING_MOODS: Record<LockStatus, Pick<StageState['moods'], 'mcclusky' | 'ghost' | 'faux' | 'hoot'>> = {
  STRUCK: { mcclusky: 'caught', ghost: 'flicker', faux: 'wave', hoot: 'satisfied' },
  LOCKED: { mcclusky: 'relieved', ghost: 'relieved', faux: 'hidden', hoot: 'unimpressed' },
  FABRICATED: { mcclusky: 'nervous', ghost: 'sad', faux: 'hidden', hoot: 'unimpressed' },
  UNSWORN: { mcclusky: 'nervous', ghost: 'sad', faux: 'hidden', hoot: 'unimpressed' },
};

interface Ctx { bundle: CaseBundle; claims: Map<string, Claim>; verdicts: Map<string, Verdict>; bets: Bet[]; bench: BenchRuns; }

const patchCards = (cards: CardView[], match: (k: CardView) => boolean, patch: Partial<CardView>): CardView[] =>
  cards.map((k) => (match(k) ? { ...k, ...patch } : k));

function guysFor(claims: Claim[]): StageState['guys'] {
  let other = 0;
  return [...new Set(claims.map((c) => c.screen))].map((screen): StageState['guys'][number] => {
    const glyph = KEYCAPS[screen.toLowerCase()];
    return glyph ? { screen, kind: 'keycap', glyph, state: 'idle' } : { screen, kind: CYCLE[other++ % CYCLE.length], state: 'idle' };
  });
}

// One screen can carry several claims; an unrepaired strike outranks everything but the claim under cross.
function guyState(screen: string, cards: CardView[]): GuyState {
  const mine = cards.filter((k) => k.claim.screen === screen);
  if (mine.some((k) => k.status === 'under-cross')) return 'nervous';
  if (mine.some((k) => k.status === 'STRUCK')) return 'glitch';
  if (mine.some((k) => k.repairedFrom && isLock(k.status))) return 'repaired';
  if (mine.some((k) => k.status === 'FABRICATED')) return 'fabricated';
  if (mine.some((k) => k.status === 'LOCKED')) return 'locked';
  return 'idle';
}

// A repaired card was STRUCK when ruled: the repair narrows the claim, it does not refund the bond.
function swornStatuses(cards: CardView[]): Record<string, LockStatus> {
  const out: Record<string, LockStatus> = {};
  for (const k of cards) {
    if (k.repairedFrom) out[k.repairedFrom] = 'STRUCK';
    else if (isLock(k.status)) out[k.claim.id] = k.status;
  }
  return out;
}

function rescore(x: Ctx, s: StageState, statuses: Record<string, LockStatus>, ruled: Verdict[]): Scores {
  const attacks = s.attacks.flatMap((a) => (a.opened && a.verdict ? [a.verdict] : []));
  const bench = x.bench.verdicts.slice(0, s.bench.runs);
  const sworn = s.cards.map((k) => x.claims.get(k.repairedFrom ?? k.claim.id) ?? k.claim);
  const scores = computeScores({ ...x.bundle, claims: sworn, verdicts: [...ruled, ...attacks, ...bench] }, statuses, { rollbacks: s.scores.rollbacks });
  if (!bench.length && !s.cards.some((k) => k.repairedFrom && isLock(k.status))) return scores;
  // The case file predates repairs and bench runs, so fidelity is re-measured over the verdicts the stage has shown.
  const shown = s.cards.flatMap((k) => (isLock(k.status) ? k.verdict : k.repairedFrom ? x.verdicts.get(k.repairedFrom) : null) ?? []);
  return { ...scores, fidelity: fidelity([...shown, ...attacks, ...bench]) };
}

function finish(x: Ctx, prev: StageState, next: StageState, kind: string): StageState {
  const statuses = swornStatuses(next.cards);
  const ruled = Object.keys(statuses).flatMap((id) => x.verdicts.get(id) ?? []);
  const scores = rescore(x, next, statuses, ruled);
  const base = Math.min(1, Math.max(0, (scores.credibilityStart - scores.credibility) / Math.max(1, scores.credibilityStart - FAINT)));
  const struck = kind === 'ruling' && next.cards.some((k) => k.claim.id === next.focusId && k.status === 'STRUCK');
  // Stress follows lost credibility (1 at the fainting line), jumps on a strike, then halves back toward that base.
  const stress = Math.min(1, struck ? base + 0.6 : Math.max(base, prev.stress / 2));
  return {
    ...next,
    scores,
    stress,
    guys: next.guys.map((g) => ({ ...g, state: guyState(g.screen, next.cards) })),
    leaderboard: settle(x.bets, ruled),
  };
}

function divergence(ref: string, v: Verdict | null, steps: string[], always: boolean): StageState['divergence'] {
  if (!v || v.flaky || (v.match && !always)) return null;
  return { ref, original: v.original, revival: v.revival, steps: v.shrunk_steps?.length ? v.shrunk_steps : steps };
}

function ruling(s: StageState, c: Claim, v: Verdict | null, status: LockStatus | null): StageState {
  const mine = (k: CardView) => k.claim.id === c.id;
  if (!status) {
    return { ...s, cards: patchCards(s.cards, mine, { status: 'sealed' }), moods: { ...s.moods, hoot: 'idle', mcclusky: 'nervous' }, subtitle: line('ruling', 'PENDING', { id: c.id }) };
  }
  const ctx: LineCtx = { claim: c, verdict: v, delta: credibilityDelta(c, status, v ?? undefined), i: s.cards.filter((k) => k.status === status).length };
  return {
    ...s,
    cards: patchCards(s.cards, mine, { status, verdict: v }),
    divergence: divergence(c.id, v, c.test.steps, status === 'STRUCK'),
    moods: { ...s.moods, ...RULING_MOODS[status], steno: 'scribbling' },
    subtitle: line('ruling', status, ctx),
    banner: status === 'STRUCK' ? 'PERJURY' : null,
  };
}

const payloadOf = (e: LedgerEvent): Record<string, unknown> => (e.payload && typeof e.payload === 'object' ? (e.payload as Record<string, unknown>) : {});
const hasRef = (e: LedgerEvent, id: string) => {
  const p = payloadOf(e);
  return p.ref === id || p.claim_id === id || p.struck_id === id;
};
// court/ledger.py writes type "commit" with payload.kind; the synthesized ledger puts the kind in the type.
const commitKind = (e: LedgerEvent) => (e.type === 'commit' ? payloadOf(e).kind : e.type.endsWith('_committed') ? e.type.slice(0, -'_committed'.length) : null);

/** Hands each ledger event to the first beat that asks for it, so the tail never repeats an event. */
function ledgerTaker(ledger: LedgerEvent[]) {
  const used = new Set<LedgerEvent>();
  return (pred: (e: LedgerEvent) => boolean, max = Infinity): LedgerEvent[] => {
    const out: LedgerEvent[] = [];
    for (const e of ledger) {
      if (out.length >= max) break;
      if (!used.has(e) && pred(e)) {
        used.add(e);
        out.push(e);
      }
    }
    return out;
  };
}

const reveal = (s: StageState, events: LedgerEvent[]): StageState => (events.length ? { ...s, ledgerTail: [...s.ledgerTail, ...events].slice(-TAIL) } : s);

// The quip lands mid-phase so it stays up for half the run instead of one short beat.
const phaseLine = (kind: string, i: number, n: number, ctx: LineCtx) =>
  i === 0 ? line(kind, 'first', ctx) : i === Math.floor(n / 2) ? line(kind, 'quip', ctx) : null;

export function buildScript(bundle: CaseBundle, bench: BenchRuns = NO_BENCH): Beat[] {
  const x: Ctx = {
    bundle,
    claims: new Map(bundle.claims.map((c) => [c.id, c])),
    verdicts: claimVerdicts(bundle.verdicts),
    bets: placeBets(bundle.claims, bundle.app),
    bench,
  };
  const take = ledgerTaker(bundle.ledger);
  const script: Beat[] = [];
  // The banner is cleared before every beat, so only the beat that raises it shows it.
  const add = (phase: Phase, kind: string, ms: number, f: (s: StageState) => StageState, events: LedgerEvent[] = []) =>
    script.push({ phase, kind, ms, apply: (s) => finish(x, s, reveal(f({ ...s, banner: null }), events), kind) });

  add('dig', 'open', 2000, (s) => ({ ...s, subtitle: line('open', null, { app: bundle.appLabel }) }));

  const evidence = bundle.evidence;
  evidence.forEach((e, i) =>
    add('dig', 'dig', 700, (s) => ({
      ...s,
      evidenceShown: [...s.evidenceShown, e],
      exhibits: { ...s.exhibits, original: 'evidence' },
      moods: { ...s.moods, steno: 'scribbling' },
      subtitle: phaseLine('dig', i, evidence.length, { n: evidence.length }) ?? s.subtitle,
    })),
  );

  const sheet = bundle.sheet?.lines ?? [];
  const words = evidence.reduce((n, e) => n + (e.text?.split(/\s+/).filter(Boolean).length ?? 0), 0);
  sheet.forEach((l, i) =>
    add('read', 'read', 600, (s) => ({
      ...s,
      sheetShown: [...s.sheetShown, l],
      wordCount: words,
      exhibits: { ...s.exhibits, revival: 'reading' },
      moods: { ...s.moods, steno: 'scribbling' },
      subtitle: phaseLine('read', i, sheet.length, { n: sheet.length, words }) ?? s.subtitle,
    })),
  );

  add('raise', 'raise', 2500, (s) => ({
    ...s,
    exhibits: { ...s.exhibits, original: 'live', revival: 'booting' },
    moods: { ...s.moods, ghost: 'hopeful', steno: 'idle' },
    subtitle: line('raise', null, { start: s.scores.credibilityStart }),
  }));
  add('raise', 'risen', 1200, (s) => ({ ...s, exhibits: { ...s.exhibits, revival: 'live' }, subtitle: line('risen', null, {}) }));

  const bonds = bundle.claims.reduce((n, c) => n + c.bond, 0);
  bundle.claims.forEach((c, i) => {
    add('swear', 'swear', 900, (s) => ({
      ...s,
      focusId: c.id,
      cards: [...s.cards, { claim: c, status: 'sworn', verdict: null, bets: betTotals(x.bets, c.id) }],
      moods: { ...s.moods, mcclusky: 'swearing', ghost: 'hopeful', steno: 'scribbling' },
      subtitle: i === 0 ? line('swear', null, { n: bundle.claims.length, bonds }) : s.subtitle,
    }), take((e) => commitKind(e) === 'claim' && hasRef(e, c.id)));
  });
  add('swear', 'seal', 1600, (s) => ({
    ...s,
    focusId: null,
    cards: patchCards(s.cards, () => true, { status: 'sealed' }),
    attacks: bundle.attacks.map((a) => ({ attack: a, opened: false, verdict: null })),
    moods: { ...s.moods, mcclusky: 'idle', hoot: 'writing', steno: 'sealing' },
    subtitle: line('seal', null, { n: bundle.attacks.length }),
  }), take((e) => commitKind(e) === 'attack'));

  const opened = new Set<string>();
  const openAttack = (a: Attack) => {
    opened.add(a.id);
    const v = bundle.verdicts.find((w) => w.kind === 'attack' && w.ref === a.id) ?? null;
    const outcome = !v ? 'pending' : v.flaky ? 'flaky' : v.match ? 'match' : 'mismatch';
    add('cross', 'attack', 900, (s) => ({
      ...s,
      attacks: s.attacks.map((r) => (r.attack.id === a.id ? { ...r, opened: true, verdict: v } : r)),
      divergence: divergence(a.id, v, a.steps, false) ?? s.divergence,
      moods: { ...s.moods, hoot: outcome === 'mismatch' ? 'satisfied' : outcome === 'pending' ? 'attacking' : 'unimpressed' },
      subtitle: line('attack', outcome, { id: a.id, verdict: v, screen: a.screen, steps: a.steps.length }),
    }), take((e) => e.type === 'verdict' && hasRef(e, a.id), 1));
  };

  bundle.claims.forEach((c, i) => {
    add('cross', 'cross', 1200, (s) => ({
      ...s,
      focusId: c.id,
      divergence: null,
      cards: patchCards(s.cards, (k) => k.claim.id === c.id, { status: 'under-cross' }),
      exhibits: { ...s.exhibits, original: 'cross', revival: 'cross' },
      moods: { ...s.moods, hoot: 'attacking', mcclusky: 'nervous', ghost: 'hopeful', faux: 'hidden', steno: 'idle' },
      subtitle: line('cross', null, { claim: c, i, n: bundle.claims.length }),
    }));
    const v = x.verdicts.get(c.id);
    // P1's lock table wins over a status derived here.
    const status = bundle.locks.find((l) => l.claim_id === c.id)?.status ?? deriveLock(c, v);
    add('cross', 'ruling', 2200, (s) => ruling(s, c, v ?? null, status), [
      ...take((e) => e.type === 'verdict' && hasRef(e, c.id), 1),
      ...take((e) => e.type === 'lock' && hasRef(e, c.id), 1),
    ]);
    // Hoot's sealed attacks on this screen open right after its first ruling.
    for (const a of bundle.attacks) if (a.screen === c.screen && !opened.has(a.id)) openAttack(a);
  });
  for (const a of bundle.attacks) if (!opened.has(a.id)) openAttack(a);

  for (const r of bundle.repairs) {
    const status = deriveLock(r.claim, r.verdict) ?? 'UNSWORN';
    const mine = (k: CardView) => (k.repairedFrom ?? k.claim.id) === r.struck_id;
    add('repair', 'repair', 2500, (s) => ({
      ...s,
      focusId: r.claim.id,
      divergence: null,
      cards: patchCards(s.cards, mine, { claim: r.claim, repairedFrom: r.struck_id, status: 'under-cross' }),
      exhibits: {
        ...s.exhibits,
        original: 'live',
        revival: 'booting',
        revivalSrc: bundle.source === 'fixture' ? EXHIBIT_SRC.repaired : s.exhibits.revivalSrc,
      },
      moods: { ...s.moods, mcclusky: 'nervous', hoot: 'idle', ghost: 'hopeful', faux: 'hidden', steno: 'idle' },
      subtitle: line('repair', null, { id: r.struck_id, claim: r.claim }),
    }));
    add('repair', 'repaired', 2200, (s) => {
      const rollbacks = s.scores.rollbacks + (r.rollback ? 1 : 0);
      const ok = status === 'LOCKED';
      return {
        ...s,
        cards: patchCards(s.cards, mine, { status, verdict: r.verdict }),
        exhibits: { ...s.exhibits, revival: 'live' },
        scores: { ...s.scores, rollbacks },
        moods: { ...s.moods, mcclusky: ok ? 'relieved' : 'nervous', ghost: ok ? 'relieved' : 'sad', faux: 'hidden', steno: 'scribbling' },
        subtitle: line('repaired', status, { claim: r.claim, struck: x.claims.get(r.struck_id), rollbacks }),
      };
    }, take((e) => ['repair', 'rollback', 'verdict', 'lock'].includes(e.type) && (hasRef(e, r.struck_id) || hasRef(e, r.claim.id))));
  }

  add('bench', 'bench', 6000, (s) => {
    const last = bench.verdicts.at(-1) ?? null;
    const outcome = !last ? null : last.flaky ? 'flaky' : last.match ? 'match' : 'mismatch';
    return {
      ...s,
      focusId: null,
      bench: { open: true, last, runs: bench.verdicts.length },
      exhibits: { ...s.exhibits, original: 'live', revival: 'live' },
      divergence: divergence(last?.ref ?? 'bench', last, [], false),
      moods: { ...s.moods, mcclusky: 'idle', hoot: 'idle', ghost: 'hopeful', faux: 'hidden', steno: 'idle' },
      subtitle: line('bench', outcome, { n: bench.verdicts.length, verdict: last }),
      ledgerTail: [...s.ledgerTail, ...bench.events].slice(-TAIL),
    };
  });

  add('sentence', 'sentence', 5000, (s) => {
    const { fidelity: f, credibility, credibilityStart, brier } = s.scores;
    const bow = f !== null && f >= 80 && !s.cards.some((k) => k.status === 'STRUCK');
    return {
      ...s,
      focusId: null,
      divergence: null,
      bench: { ...s.bench, open: false },
      moods: {
        ghost: bow ? 'relieved' : 'sad',
        mcclusky: credibility < FAINT ? 'fainted' : credibility >= credibilityStart ? 'relieved' : 'nervous',
        hoot: bow ? 'unimpressed' : 'satisfied',
        faux: bow ? 'bow' : 'smug',
        steno: 'sealing',
      },
      subtitle: line('sentence', null, { fidelity: f, credibility, brier }),
    };
  });
  add('sentence', 'farewell', 6000, (s) => ({
    ...s,
    subtitle: line('farewell', s.moods.mcclusky, { credibility: s.scores.credibility, start: s.scores.credibilityStart }),
  }));

  return script;
}

export function initialState(bundle: CaseBundle): StageState {
  return {
    phase: 'dig', beat: 0, beats: 0, playing: false,
    app: bundle.app, appLabel: bundle.appLabel, source: bundle.source,
    evidenceShown: [], sheetShown: [], wordCount: 0,
    exhibits: { original: 'dark', revival: 'dark', originalSrc: EXHIBIT_SRC.original, revivalSrc: EXHIBIT_SRC.revival },
    cards: [], focusId: null, attacks: [], divergence: null,
    scores: computeScores({ ...bundle, claims: [], verdicts: [] }, {}),
    stress: 0,
    moods: { ghost: 'idle', mcclusky: 'idle', hoot: 'idle', faux: 'hidden', steno: 'idle' },
    guys: guysFor(bundle.claims),
    ledgerTail: [], subtitle: null, banner: null,
    bench: { open: false, last: null, runs: 0 },
    leaderboard: settle(placeBets(bundle.claims, bundle.app), []),
  };
}

/** Every state of the script, in order (state i has beats 0..i applied). */
export function foldStates(bundle: CaseBundle, script: Beat[]): StageState[] {
  const out: StageState[] = [];
  let s = initialState(bundle);
  for (const [i, b] of script.entries()) {
    s = { ...b.apply(s), phase: b.phase, beat: i, beats: script.length };
    out.push(s);
  }
  return out;
}

export function stateAt(bundle: CaseBundle, script: Beat[], index: number): StageState {
  const states = foldStates(bundle, script.slice(0, Math.max(0, index) + 1));
  return { ...(states.at(-1) ?? initialState(bundle)), beats: script.length };
}
