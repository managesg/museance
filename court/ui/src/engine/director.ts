// Turns a CaseBundle into the show: timed beats, each a pure step from one stage state to the next.
import type { Attack, CaseBundle, Claim, LedgerEvent, LockStatus, Verdict } from '../contracts';
import { betTotals, placeBets, settle, type Bet } from './bets';
import { line, meshLine, type LineCtx } from './lines';
import { claimVerdicts, computeScores, credibilityDelta, deriveLock, fidelity } from './scoring';
import type { Beat, CardStatus, CardView, GuyKind, GuyState, Phase, Scores, StageState } from './types';

/** Bench runs submitted during the show; they land at the bench beat. */
export interface BenchRuns { verdicts: Verdict[]; events: LedgerEvent[]; }
const NO_BENCH: BenchRuns = { verdicts: [], events: [] };

const TAIL = 8;
const FAINT = 300;
const KEYCAPS: Record<string, string> = { add: '+', subtract: '−', multiply: '×', divide: '÷', clear: 'C' };
const KINDS: Record<string, GuyKind> = { complete: 'checkbox', remove: 'trash', list: 'listitem' };
const SYNONYMS: Record<string, string> = { completed: 'complete', todo: 'list', delete: 'remove' };
const CYCLE: GuyKind[] = ['calculator', 'brush', 'clock'];
const MAX_GUYS = 4;
const MAX_ATTACKS = 4;
/** One little guy per screen, so the todo app's 'completed' and 'complete' share one. */
const norm = (screen: string) => {
  const s = screen.toLowerCase();
  return SYNONYMS[s] ?? s;
};
const mismatched = (v: Verdict | null | undefined) => !!v && !v.flaky && !v.match;
const outcomeOf = (v: Verdict | null | undefined) => (!v ? 'pending' : v.flaky ? 'flaky' : v.match ? 'match' : 'mismatch');
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

function guysFor(claims: Claim[], attacks: Attack[]): StageState['guys'] {
  let other = 0;
  const screens = [...new Set([...claims, ...attacks].map((c) => norm(c.screen)))].slice(0, MAX_GUYS);
  return screens.map((screen): StageState['guys'][number] => {
    const glyph = KEYCAPS[screen];
    if (glyph) return { screen, kind: 'keycap', glyph, state: 'idle' };
    return { screen, kind: KINDS[screen] ?? CYCLE[other++ % CYCLE.length], state: 'idle' };
  });
}

// One screen carries several claims and attacks. A mismatch in force glitches it; a guy the re-ruling repaired
// stays repaired; a strike with matching builds (the medium was wrong, not the revival) glitches it too.
function guyState(screen: string, s: StageState, prev: GuyState): GuyState {
  const mine = s.cards.filter((k) => norm(k.claim.screen) === screen);
  if (mine.some((k) => k.status === 'under-cross')) return 'nervous';
  if (mine.some((k) => mismatched(k.verdict)) || s.attacks.some((a) => a.opened && norm(a.attack.screen) === screen && mismatched(a.verdict))) return 'glitch';
  if (prev === 'repaired') return 'repaired';
  if (mine.some((k) => k.status === 'STRUCK')) return 'glitch';
  if (mine.some((k) => k.status === 'FABRICATED')) return 'fabricated';
  if (mine.some((k) => k.status === 'LOCKED')) return 'locked';
  return 'idle';
}

function swornStatuses(cards: CardView[]): Record<string, LockStatus> {
  const out: Record<string, LockStatus> = {};
  for (const k of cards) if (isLock(k.status)) out[k.claim.id] = k.status;
  return out;
}

/** The verdicts in force on stage: ruled cards and opened attacks (swapped for the repaired revival's after the re-ruling), plus bench runs. */
function inForce(x: Ctx, s: StageState): Verdict[] {
  const shown = s.cards.flatMap((k) => (isLock(k.status) && k.verdict ? [k.verdict] : []));
  const attacks = s.attacks.flatMap((a) => (a.opened && a.verdict ? [a.verdict] : []));
  return [...shown, ...attacks, ...x.bench.verdicts.slice(0, s.bench.runs)];
}

// Credibility and Brier come from the original ruling; fidelity is re-measured over the verdicts in force,
// since the case file's number predates repairs and bench runs.
function rescore(x: Ctx, s: StageState, statuses: Record<string, LockStatus>, ruled: Verdict[]): Scores {
  const scores = computeScores({ ...x.bundle, claims: s.cards.map((k) => k.claim), verdicts: ruled }, statuses, { rollbacks: s.scores.rollbacks });
  return { ...scores, fidelity: fidelity(inForce(x, s)) };
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
    guys: next.guys.map((g) => ({ ...g, state: guyState(g.screen, next, g.state) })),
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
  return p.ref === id || p.claim_id === id;
};
// court/ledger.py writes type "commit" with payload.kind (claim or attack).
const commitKind = (e: LedgerEvent) => (e.type === 'commit' ? payloadOf(e).kind : null);
const isMesh = (e: LedgerEvent) => meshLine(e) !== null;

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

// A revealed mesh.* event's caption takes the subtitle: the agent narrates its own step.
const reveal = (s: StageState, events: LedgerEvent[]): StageState => {
  if (!events.length) return s;
  const said = events.map(meshLine).filter((l) => l !== null).at(-1);
  return { ...s, ledgerTail: [...s.ledgerTail, ...events].slice(-TAIL), subtitle: said ?? s.subtitle };
};

// The quip lands mid-phase so it stays up for half the run instead of one short beat.
const phaseLine = (kind: string, i: number, n: number, ctx: LineCtx) =>
  i === 0 ? line(kind, 'first', ctx) : i === Math.floor(n / 2) ? line(kind, 'quip', ctx) : null;

// The dig and read phases take about 4 s each however many items there are; never under 60 ms a beat.
export const pace = (ms: number, n: number) => Math.max(60, Math.min(ms, Math.round(4000 / Math.max(1, n))));

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
    add('dig', 'dig', pace(700, evidence.length), (s) => ({
      ...s,
      evidenceShown: [...s.evidenceShown, e],
      exhibits: { ...s.exhibits, original: 'evidence' },
      moods: { ...s.moods, steno: 'scribbling' },
      subtitle: phaseLine('dig', i, evidence.length, { n: evidence.length }) ?? s.subtitle,
    }), take(isMesh, 1)),
  );

  const sheet = bundle.sheet?.lines ?? [];
  const words = evidence.reduce((n, e) => n + (e.text?.split(/\s+/).filter(Boolean).length ?? 0), 0);
  sheet.forEach((l, i) =>
    add('read', 'read', pace(600, sheet.length), (s) => ({
      ...s,
      sheetShown: [...s.sheetShown, l],
      wordCount: words,
      exhibits: { ...s.exhibits, revival: 'reading' },
      moods: { ...s.moods, steno: 'scribbling' },
      subtitle: phaseLine('read', i, sheet.length, { n: sheet.length, words }) ?? s.subtitle,
    }), take(isMesh, 1)),
  );

  // Mesh captions the dig and read beats had no room for land here.
  add('raise', 'raise', 2500, (s) => ({
    ...s,
    exhibits: { ...s.exhibits, original: 'live', revival: 'booting' },
    moods: { ...s.moods, ghost: 'hopeful', steno: 'idle' },
    subtitle: line('raise', null, { start: s.scores.credibilityStart }),
  }), take(isMesh));
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

  // A real case has a hundred attacks: a few play one by one (mismatches first, then one match), a tally lands the rest.
  const attackVerdicts = new Map(bundle.verdicts.filter((v) => v.kind === 'attack').map((v) => [v.ref, v]));
  const verdictOf = (a: Attack) => attackVerdicts.get(a.id) ?? null;
  const by = (o: string) => bundle.attacks.filter((a) => outcomeOf(verdictOf(a)) === o);
  const ranked = [...by('mismatch').slice(0, MAX_ATTACKS - 1), ...by('match').slice(0, 1)];
  // Unjudged attacks (the repo fixtures have no attack verdicts) still get their beats.
  const picks = ranked.length ? ranked : bundle.attacks.slice(0, MAX_ATTACKS);
  const opened = new Set<string>();
  const openAttack = (a: Attack) => {
    opened.add(a.id);
    const v = verdictOf(a);
    const outcome = outcomeOf(v);
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
    // P1's lock table wins over a status derived here, but a stale STRUCK never stamps PERJURY on a flaky or unjudged verdict.
    const derived = deriveLock(c, v);
    const locked = bundle.locks.find((l) => l.claim_id === c.id)?.status;
    const status = locked === 'STRUCK' && v && derived !== 'STRUCK' ? derived : (locked ?? derived);
    add('cross', 'ruling', 2200, (s) => ruling(s, c, v ?? null, status), [
      ...take((e) => e.type === 'verdict' && hasRef(e, c.id), 1),
      ...take((e) => e.type === 'lock' && hasRef(e, c.id), 1),
    ]);
    // Hoot's picked attacks on this screen open right after its first ruling.
    for (const a of picks) if (a.screen === c.screen && !opened.has(a.id)) openAttack(a);
  });
  for (const a of picks) if (!opened.has(a.id)) openAttack(a);

  const rest = bundle.attacks.filter((a) => !opened.has(a.id));
  if (rest.length) {
    const ids = new Set(rest.map((a) => a.id));
    const diverge = rest.filter((a) => outcomeOf(verdictOf(a)) === 'mismatch').length;
    const flaky = rest.filter((a) => outcomeOf(verdictOf(a)) === 'flaky').length;
    add('cross', 'tally', 2200, (s) => ({
      ...s,
      focusId: null,
      attacks: s.attacks.map((r) => (ids.has(r.attack.id) ? { ...r, opened: true, verdict: verdictOf(r.attack) } : r)),
      moods: { ...s.moods, hoot: diverge ? 'satisfied' : 'unimpressed' },
      subtitle: line('attack', 'tally', { n: rest.length, diverge, flaky }),
    }), take((e) => e.type === 'verdict' && ids.has(String(payloadOf(e).ref))));
  }

  // P4 patches the revival, never a claim: patched leaves every status as ruled; rollback or unsworn unswears the claim it names.
  const after = bundle.after;
  const afterClaims = claimVerdicts(after?.verdicts ?? []);
  const afterAttacks = new Map((after?.verdicts ?? []).filter((v) => v.kind === 'attack').map((v) => [v.ref, v]));
  for (const r of bundle.repairs) {
    const claim = x.claims.get(r.claim_id);
    add('repair', 'repair', 2500, (s) => ({
      ...s,
      focusId: claim?.id ?? null,
      divergence: null,
      exhibits: { ...s.exhibits, original: 'live', revival: 'booting', revivalSrc: bundle.builds.revivalAfter ?? s.exhibits.revivalSrc },
      moods: { ...s.moods, mcclusky: 'nervous', hoot: 'idle', ghost: 'hopeful', faux: 'hidden', steno: 'idle' },
      subtitle: line('repair', null, { reason: r.reason }),
    }));
    add('repair', 'repaired', 1500, (s) => {
      const unsworn = claim && r.decision !== 'patched';
      const rollbacks = s.scores.rollbacks + (r.decision === 'rollback' ? 1 : 0);
      return {
        ...s,
        cards: unsworn ? patchCards(s.cards, (k) => k.claim.id === claim.id, { status: 'UNSWORN' }) : s.cards,
        exhibits: { ...s.exhibits, revival: 'live' },
        scores: { ...s.scores, rollbacks },
        moods: { ...s.moods, steno: 'scribbling' },
        subtitle: r.decision === 'patched' ? s.subtitle : line('repaired', r.decision, { id: r.claim_id, rollbacks }),
      };
    });
    if (!after) continue;
    add('repair', 'rerule', 2500, (s) => {
      const screens = new Set([
        ...s.cards.filter((k) => mismatched(k.verdict)).map((k) => norm(k.claim.screen)),
        ...s.attacks.filter((a) => a.opened && mismatched(a.verdict)).map((a) => norm(a.attack.screen)),
      ]);
      const next: StageState = {
        ...s,
        focusId: null,
        divergence: null,
        cards: s.cards.map((k) => (k.verdict ? { ...k, verdict: afterClaims.get(k.claim.id) ?? k.verdict } : k)),
        attacks: s.attacks.map((a) => (a.verdict ? { ...a, verdict: afterAttacks.get(a.attack.id) ?? a.verdict } : a)),
        guys: s.guys.map((g) => (screens.has(g.screen) ? { ...g, state: 'repaired' } : g)),
        moods: { ...s.moods, mcclusky: 'relieved', ghost: 'relieved', hoot: 'unimpressed', faux: 'hidden', steno: 'sealing' },
      };
      return { ...next, subtitle: line('rerule', null, { fidelity: fidelity(inForce(x, next)) }) };
    });
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
    exhibits: { original: 'dark', revival: 'dark', originalSrc: bundle.builds.original, revivalSrc: bundle.builds.revival, scale: bundle.builds.scale },
    cards: [], focusId: null, attacks: [], divergence: null,
    scores: computeScores({ ...bundle, claims: [], verdicts: [] }, {}),
    stress: 0,
    moods: { ghost: 'idle', mcclusky: 'idle', hoot: 'idle', faux: 'hidden', steno: 'idle' },
    guys: guysFor(bundle.claims, bundle.attacks),
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
