import { describe, expect, it } from 'vitest';
import type { Attack, Builds, CaseBundle, Claim, Repair, Verdict } from '../contracts';
import attacksJson from '../../../../fixtures/attacks.json';
import claimsJson from '../../../../fixtures/claims.json';
import verdictsJson from '../../../../fixtures/verdicts.json';
import { loadFixtureBundle } from '../fixtures';
import { buildScript, foldStates, initialState, stateAt, type BenchRuns } from './director';
import { GENESIS, commitOf, sha256Hex, synthesizeLedger, verifyLedger } from './hash';
import { PHASES, type Beat, type StageState } from './types';

const claims = claimsJson as Claim[];
const c03 = claims[2];

const BUILDS: Builds = { original: '/o/', revival: '/r/v1.html', revivalAfter: '/r/v2.html', scale: 1.5 };
// The shape of cases/app1/repairs.jsonl: P4 patched the revival, so c03 stays STRUCK.
const PATCH: Repair = { claim_id: 'c03', decision: 'patched', reason: "claim test now gives '0.12'; regression score 18 -> 19" };
// The same claims judged on the repaired build: every claim's builds now agree.
const AFTER: NonNullable<CaseBundle['after']> = {
  verdicts: (verdictsJson as Verdict[]).map((v) => ({ ...v, revival: v.original, match: true })),
  locks: [],
  caseFile: null,
};

const bundle = (over: Partial<CaseBundle> = {}): CaseBundle => ({
  app: 'app1', appLabel: 'fixture-calc', source: 'fixture',
  evidence: [
    { id: 'shot-001', app: 'app1', tier: 'A', kind: 'screenshot', source: 'test', text: 'The display reads 15.' },
    { id: 'thread-003', app: 'app1', tier: 'C', kind: 'page', source: 'test', text: 'A user says it rounds.' },
  ],
  sheet: { app: 'app1', lines: [{ id: 'b001', screen: 'add', text: '7 + 8 shows 15', label: 'SEEN', citations: ['shot-001'], conflicts: [] }] },
  claims, attacks: attacksJson as Attack[], verdicts: verdictsJson as Verdict[],
  locks: [], ledger: [], caseFile: null, repairs: [PATCH], builds: BUILDS, after: AFTER, ...over,
});

const play = (b: CaseBundle, bench?: BenchRuns) => {
  const script = buildScript(b, bench);
  return { script, states: foldStates(b, script) };
};
const find = (script: Beat[], states: StageState[], kind: string, focus?: string) => {
  const i = script.findIndex((b, k) => b.kind === kind && (focus === undefined || states[k].focusId === focus));
  expect(i, `${kind} ${focus ?? ''}`).toBeGreaterThanOrEqual(0);
  return { i, s: states[i] };
};
const guy = (s: StageState, screen: string) => s.guys.find((g) => g.screen === screen)?.state;

describe('script', () => {
  it('plays every phase in docket order with the specified beats', () => {
    const { script } = play(bundle());
    const order = script.map((b) => PHASES.indexOf(b.phase));
    expect(order).toEqual([...order].sort((a, b) => a - b));
    expect([...new Set(script.map((b) => b.phase))]).toEqual([...PHASES]);
    const ms = (kind: string) => script.filter((b) => b.kind === kind).map((b) => b.ms);
    expect(ms('dig')).toEqual([700, 700]);
    expect(ms('read')).toEqual([600]);
    expect(ms('raise')).toEqual([2500]);
    expect(ms('swear')).toEqual([900, 900, 900, 900, 900]);
    expect(ms('cross')).toEqual([1200, 1200, 1200, 1200, 1200]);
    expect(ms('ruling')).toEqual([2200, 2200, 2200, 2200, 2200]);
    expect(ms('attack')).toEqual([900, 900, 900, 900]);
    expect(script.filter((b) => b.kind === 'tally')).toHaveLength(1);
    expect(script.filter((b) => ['repair', 'repaired', 'rerule'].includes(b.kind)).map((b) => b.kind)).toEqual(['repair', 'repaired', 'rerule']);
  });

  it('caps the dig and read phases at about 4 s each, 60 ms a beat at least', () => {
    const many = (n: number) => Array.from({ length: n }, (_, i) => ({ id: `e${i}`, app: 'app1', tier: 'A' as const, kind: 'page' as const, source: 'test' }));
    const sheet = (n: number) => ({ app: 'app1', lines: Array.from({ length: n }, (_, i) => ({ id: `b${i}`, screen: 'add', text: 't', label: 'SEEN' as const, citations: [], conflicts: [] })) });
    const total = (b: CaseBundle, kind: string) => buildScript(b).filter((x) => x.kind === kind).reduce((n, x) => n + x.ms, 0);
    expect(total(bundle({ evidence: many(55), sheet: sheet(24) }), 'dig')).toBeLessThanOrEqual(4100);
    expect(total(bundle({ evidence: many(55), sheet: sheet(24) }), 'read')).toBeLessThanOrEqual(4100);
    expect(buildScript(bundle({ evidence: many(500) })).find((x) => x.kind === 'dig')?.ms).toBe(60);
  });

  it('opens unjudged attacks after the first ruling on their screen, four at most, then tallies the rest', () => {
    const { script, states } = play(bundle());
    const opened = script.flatMap((b, i) => (b.kind === 'attack' || b.kind === 'tally' ? states[i].attacks.filter((a) => a.opened).length : []));
    expect(opened).toEqual([1, 2, 3, 4, 5]);
    const firstAttack = (id: string) => script.findIndex((b, i) => b.kind === 'attack' && states[i].attacks.some((a) => a.attack.id === id && a.opened));
    // the fixture attacks have no verdicts, so the first four play; claim order add, multiply, divide, clear: a02 a03 a01 a04
    expect(['a02', 'a03', 'a01', 'a04'].map(firstAttack)).toEqual(['a02', 'a03', 'a01', 'a04'].map(firstAttack).sort((a, b) => a - b));
    expect(find(script, states, 'tally').s.subtitle).toEqual({ who: 'DR. HOOT', text: '+1 more attacks: 0 diverge, 0 flaky' });
  });

  it('plays mismatches first and one match, tallies the rest, and glitches every screen with a mismatch', () => {
    const atk = (id: string, screen: string): Attack => ({ id, app: 'app1', screen, steps: ['click:#k1'], observe: '#display' });
    const attacks = [atk('m1', 'clear'), atk('ok1', 'add'), atk('m2', 'clear'), atk('ok2', 'add'), atk('m3', 'multiply'), atk('m4', 'multiply'), atk('f1', 'add'), atk('m5', 'multiply')];
    const av = (a: Attack): Verdict => ({
      ref: a.id, kind: 'attack', original: '1', revival: a.id.startsWith('m') ? '2' : '1',
      match: !a.id.startsWith('m'), flaky: a.id.startsWith('f'), claim_true: null,
    });
    const b = bundle({ attacks, verdicts: [...(verdictsJson as Verdict[]), ...attacks.map(av)], repairs: [], after: null });
    const { script, states } = play(b);
    const shown = script.flatMap((x, i) => (x.kind === 'attack' ? [states[i].subtitle?.text.split(':')[0]] : []));
    expect([...shown].sort()).toEqual(['m1', 'm2', 'm3', 'ok1']);
    const { s } = find(script, states, 'tally');
    expect(s.subtitle).toEqual({ who: 'DR. HOOT', text: '+4 more attacks: 2 diverge, 1 flaky' });
    expect(s.attacks.every((a) => a.opened)).toBe(true);
    expect(guy(s, 'multiply')).toBe('glitch');
    expect(guy(s, 'clear')).toBe('glitch');
    expect(guy(s, 'add')).toBe('locked');
  });

  it('gives one little guy per claim screen, keycaps for operators', () => {
    expect(initialState(bundle()).guys).toEqual([
      { screen: 'add', kind: 'keycap', glyph: '+', state: 'idle' },
      { screen: 'multiply', kind: 'keycap', glyph: '×', state: 'idle' },
      { screen: 'divide', kind: 'keycap', glyph: '÷', state: 'idle' },
      { screen: 'clear', kind: 'keycap', glyph: 'C', state: 'idle' },
    ]);
    const odd = ['history', 'theme', 'settings', 'about', 'history'].map((screen, i) => ({ ...c03, id: `o${i}`, screen }));
    expect(initialState(bundle({ claims: odd })).guys.map((g) => g.kind)).toEqual(['calculator', 'brush', 'clock', 'calculator']);
  });

  it('folds the todo screens into four guys: add, list, complete, remove', () => {
    const todo = ['add', 'todo', 'completed', 'list'].map((screen, i) => ({ ...c03, id: `t${i}`, screen }));
    const hits = ['complete', 'remove', 'add'].map((screen, i): Attack => ({ id: `h${i}`, app: 'todo', screen, steps: [], observe: '#todo' }));
    expect(initialState(bundle({ claims: todo, attacks: hits })).guys).toEqual([
      { screen: 'add', kind: 'keycap', glyph: '+', state: 'idle' },
      { screen: 'list', kind: 'listitem', state: 'idle' },
      { screen: 'complete', kind: 'checkbox', state: 'idle' },
      { screen: 'remove', kind: 'trash', state: 'idle' },
    ]);
  });

  it('takes the exhibit sources and scale from the bundle builds', () => {
    expect(initialState(bundle()).exhibits).toMatchObject({ originalSrc: '/o/', revivalSrc: '/r/v1.html', scale: 1.5 });
  });

  it('lets a mesh.* ledger caption speak as its agent', () => {
    const mesh = (agent?: string) => ({ seq: 1, ts: '', type: 'mesh.dig', payload: { caption: 'Found 3 pages.', agent }, prev_hash: '', hash: '' });
    const { states } = play(bundle({ ledger: [mesh('reader'), mesh()] }));
    expect(states[1].subtitle).toEqual({ who: 'READER', text: 'Found 3 pages.' });
    expect(states[2].subtitle).toEqual({ who: 'THE CLERK', text: 'Found 3 pages.' });
  });

  it('stateAt agrees with the fold', () => {
    const b = bundle();
    const { script, states } = play(b);
    expect(stateAt(b, script, 9)).toEqual(states[9]);
    expect(stateAt(b, script, script.length + 5)).toEqual(states.at(-1));
  });
});

describe('the show on the fixture case', () => {
  const { script, states } = play(bundle());

  it('deals sworn cards with bets, then seals them with the attacks', () => {
    const { s } = find(script, states, 'swear', 'c01');
    expect(s.cards[0]).toMatchObject({ status: 'sworn', bets: { trueCredits: expect.any(Number), falseCredits: expect.any(Number) } });
    expect(s.cards[0].bets.trueCredits + s.cards[0].bets.falseCredits).toBe(600);
    expect(s.moods.mcclusky).toBe('swearing');
    // bonds 200 + 180 + 60 + 220 + 10 = 670
    expect(s.subtitle).toEqual({ who: 'McCLUSKY', text: '5 claims, 670 credits. My accountant objects.' });
    expect(find(script, states, 'swear', 'c05').s.subtitle).toEqual(s.subtitle);
    const seal = find(script, states, 'seal').s;
    expect(seal.cards.map((c) => c.status)).toEqual(['sealed', 'sealed', 'sealed', 'sealed', 'sealed']);
    expect(seal.attacks).toHaveLength(5);
    expect(seal.moods).toMatchObject({ hoot: 'writing', steno: 'sealing' });
  });

  it('locks c01: relieved counsel, locked guy, plus 10', () => {
    const { s } = find(script, states, 'ruling', 'c01');
    expect(s.cards[0].status).toBe('LOCKED');
    expect(s.moods.mcclusky).toBe('relieved');
    expect(guy(s, 'add')).toBe('locked');
    expect(s.scores.credibility).toBe(1010);
    expect(s.subtitle?.text).toBe('Locked. Plus 10. Being 95% right pays poorly.');
  });

  it('strikes c03: perjury, caught counsel, waving standee, glitching guy, divergence, stress spike', () => {
    const cross = find(script, states, 'cross', 'c03').s;
    expect(cross.cards[2].status).toBe('under-cross');
    expect(cross.moods.hoot).toBe('attacking');
    expect(cross.exhibits).toMatchObject({ original: 'cross', revival: 'cross' });
    expect(guy(cross, 'divide')).toBe('nervous');

    const { i, s } = find(script, states, 'ruling', 'c03');
    expect(s.cards[2].status).toBe('STRUCK');
    expect(s.moods).toMatchObject({ mcclusky: 'caught', faux: 'wave', ghost: 'flicker' });
    expect(guy(s, 'divide')).toBe('glitch');
    expect(s.divergence).toEqual({ ref: 'c03', original: '0.12', revival: '0.13', steps: ['click:#k1', 'click:#kdiv', 'click:#k8', 'click:#keq'] });
    expect(s.banner).toBe('PERJURY');
    expect(s.scores.credibility).toBe(1000 + 10 + 18 - 60);
    expect(s.stress).toBeGreaterThan(0.6);
    expect(states[i + 1].stress).toBeLessThan(s.stress);
    expect(states[i + 1].banner).toBeNull();
    expect(s.subtitle).toEqual({ who: 'McCLUSKY', text: 'I said 0.13. It says 0.12. Minus 60.' });
  });

  it('marks c05 FABRICATED without unbreaking the divide guy', () => {
    const { s } = find(script, states, 'ruling', 'c05');
    expect(s.cards[4].status).toBe('FABRICATED');
    expect(guy(s, 'divide')).toBe('glitch'); // c03 still stands struck on the same screen
    expect(s.moods.faux).toBe('hidden');
    expect(s.scores).toMatchObject({ credibility: 982, fidelity: 60, claimsSurvived: 3, struck: 1, fabricated: 1 });
  });

  it('repairs the revival: boots the after build under P4 reason, then re-rules fidelity 60 to 100, every status kept', () => {
    const boot = find(script, states, 'repair').s;
    expect(boot.exhibits).toMatchObject({ revival: 'booting', revivalSrc: '/r/v2.html' });
    expect(boot.subtitle).toEqual({ who: 'THE CLERK', text: PATCH.reason });
    expect(boot.scores).toMatchObject({ credibility: 982, fidelity: 60 });
    const live = find(script, states, 'repaired').s;
    expect(live.exhibits.revival).toBe('live');
    expect(live.subtitle).toEqual(boot.subtitle);
    expect(live.cards.map((k) => k.status)).toEqual(['LOCKED', 'LOCKED', 'STRUCK', 'LOCKED', 'FABRICATED']);
    const { s } = find(script, states, 'rerule');
    expect(s.cards.map((k) => k.status)).toEqual(['LOCKED', 'LOCKED', 'STRUCK', 'LOCKED', 'FABRICATED']);
    expect(s.scores).toMatchObject({ fidelity: 100, credibility: 982, rollbacks: 0, struck: 1 });
    expect(s.divergence).toBeNull();
    expect(guy(s, 'divide')).toBe('repaired'); // c03 and c05 diverged before the repair
    expect(guy(s, 'add')).toBe('locked');
    expect(guy(states.at(-1)!, 'divide')).toBe('repaired');
    expect(s.subtitle?.text).toBe('Re-ruled on the repaired revival. Fidelity 100.');
  });

  it('sentences: a strike still stands after the patch, so Faux is smug; counsel nervous at 982', () => {
    const end = states.at(-1);
    expect(end?.phase).toBe('sentence');
    expect(end?.moods).toMatchObject({ faux: 'smug', mcclusky: 'nervous' });
    const sentence = find(script, states, 'sentence').s;
    expect(sentence.subtitle?.text).toBe('Fidelity 100. Credibility 982. Brier 0.173.');
    expect(end?.subtitle?.text).toBe('Down 18 credits. I\'ll appeal. To whom, unclear.');
  });
});

describe('repair decisions (P4)', () => {
  const last = (r: Repair) => play(bundle({ repairs: [r] })).states.at(-1)!;

  it('a rollback unswears the claim it names and counts one rollback', () => {
    const s = last({ ...PATCH, decision: 'rollback', reason: 'regression 19 -> 17' });
    expect(s.cards[2].status).toBe('UNSWORN');
    expect(s.scores).toMatchObject({ rollbacks: 1, struck: 0, unsworn: 1, credibility: 1042 });
  });

  it('unsworn unswears without a rollback', () => {
    const s = last({ ...PATCH, decision: 'unsworn', reason: 'no build to test' });
    expect(s.cards[2].status).toBe('UNSWORN');
    expect(s.scores.rollbacks).toBe(0);
  });

  it('a whole-revival patch changes no claim, and no after build keeps the old revival', () => {
    const { script, states } = play(bundle({ repairs: [{ claim_id: 'attacks:app1', decision: 'patched', reason: 'attack mismatches 3->0' }], after: null, builds: { ...BUILDS, revivalAfter: null } }));
    expect(script.some((b) => b.kind === 'rerule')).toBe(false);
    const s = find(script, states, 'repair').s;
    expect(s).toMatchObject({ focusId: null, exhibits: { revivalSrc: '/r/v1.html', revival: 'booting' } });
    expect(states.at(-1)?.cards.map((k) => k.status)).toEqual(['LOCKED', 'LOCKED', 'STRUCK', 'LOCKED', 'FABRICATED']);
  });
});

describe('sentence moods', () => {
  const end = (b: CaseBundle) => play(b).states.at(-1)?.moods;

  it('is smug while a strike stands', () => {
    expect(end(bundle({ repairs: [] }))).toMatchObject({ faux: 'smug', mcclusky: 'nervous' });
  });

  it('faints under 300 credibility', () => {
    // 1000 + 10 + 18 + 7 + 7 - 800 = 242
    const heavy = claims.map((c) => (c.id === 'c03' ? { ...c, bond: 800 } : c));
    expect(end(bundle({ claims: heavy, repairs: [] }))?.mcclusky).toBe('fainted');
  });

  it('is relieved at or above the start', () => {
    // without c03: 1000 + 10 + 18 + 7 + 7 = 1042
    expect(end(bundle({ claims: claims.filter((c) => c.id !== 'c03'), repairs: [] }))?.mcclusky).toBe('relieved');
  });
});

describe('no perjury without a ruling the court can stand on', () => {
  const withC03 = (patch: Partial<Verdict>) => (verdictsJson as Verdict[]).map((v) => (v.ref === 'c03' ? { ...v, ...patch } : v));
  const c03Ruling = (b: CaseBundle) => {
    const { script, states } = play(b);
    return find(script, states, 'ruling', 'c03').s;
  };

  it('keeps a flaky c03 UNSWORN even when a stale lock table says STRUCK', () => {
    const s = c03Ruling(bundle({ verdicts: withC03({ flaky: true }), locks: [{ claim_id: 'c03', status: 'STRUCK' }], repairs: [] }));
    expect(s.cards[2].status).toBe('UNSWORN');
    expect(s.banner).toBeNull();
    expect(s.moods.faux).toBe('hidden');
    expect(guy(s, 'divide')).not.toBe('glitch');
    expect(s.scores.credibility).toBe(1000 + 10 + 18);
    expect(s.subtitle?.text).toBe('Two runs, two answers. Unsworn. No credits move.');
  });

  it('makes a c03 the court could not judge (claim_true null) UNSWORN, and does not blame flakiness', () => {
    const s = c03Ruling(bundle({ verdicts: withC03({ claim_true: null }), repairs: [] }));
    expect(s.cards[2].status).toBe('UNSWORN');
    expect(s.banner).toBeNull();
    expect(s.subtitle?.text).toBe('The court could not rule. Unsworn. No credits move.');
  });
});

describe('bench', () => {
  it('lands bench verdicts at the bench beat and counts them toward fidelity', () => {
    const v: Verdict = { ref: 'bench-1', kind: 'attack', original: '0.2', revival: '0.2', claim_true: null, match: true, flaky: false, shrunk_steps: [] };
    const { script, states } = play(bundle({ repairs: [], after: null }), { verdicts: [v], events: [] });
    const { s } = find(script, states, 'bench');
    expect(s.bench).toEqual({ open: true, last: v, runs: 1 });
    // c01 c02 c04 and the bench run match, c03 c05 do not: 100 * 4 / 6 = 66.7
    expect(s.scores.fidelity).toBe(67);
    expect(states.at(-1)?.bench.open).toBe(false);
  });
});

describe('ledger', () => {
  it('hashes exactly like court/ledger.py', async () => {
    expect(await sha256Hex('abc')).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
    // Reference values from eval/commit.py and court/ledger.py run on fixtures/claims.json.
    expect(await commitOf(claims[0])).toBe('cc867cfc14b056ec219ad0aa5fc3247fc230bc441483bf8996a178c5cc0dc14b');
    const ledger = await synthesizeLedger(bundle());
    expect(ledger[0]).toMatchObject({
      seq: 1, type: 'commit', payload: { kind: 'claim', ref: 'c01' }, prev_hash: GENESIS,
      hash: 'aad36b1596125a99193202a27374c45ff105f8947d4fe95c42049bc4c048812c',
    });
    // court/ledger.py names and order; repairs stay off the chain.
    expect(ledger.map((e) => e.type)).toEqual([
      ...Array<string>(10).fill('commit'), ...Array<string>(5).fill('verdict'), ...Array<string>(5).fill('lock'),
    ]);
    expect(ledger.slice(5, 10).map((e) => (e.payload as { kind: string }).kind)).toEqual(Array<string>(5).fill('attack'));
    expect(await verifyLedger(ledger)).toBe(true);
    expect(await verifyLedger(ledger.map((e, i) => (i === 3 ? { ...e, payload: { edited: true } } : e)))).toBe(false);
  });

  it('reveals every event once, at its beat', async () => {
    const b = bundle();
    const ledger = await synthesizeLedger(b);
    const { script, states } = play({ ...b, ledger });
    const ruling = find(script, states, 'ruling', 'c03').s;
    expect(ruling.ledgerTail.slice(-2).map((e) => e.type)).toEqual(['verdict', 'lock']);
    expect(ruling.ledgerTail.slice(-2).map((e) => (e.payload as { ref?: string; claim_id?: string }).ref ?? (e.payload as { claim_id?: string }).claim_id)).toEqual(['c03', 'c03']);
    const seen = new Set<number>();
    for (const s of states) for (const e of s.ledgerTail) seen.add(e.seq);
    expect(seen.size).toBe(ledger.length);
  });
});

describe('the shipped fixture bundle', () => {
  it('plays end to end', () => {
    const b = loadFixtureBundle();
    const { states } = play(b);
    const end = states.at(-1);
    expect(end?.phase).toBe('sentence');
    expect(end?.cards).toHaveLength(b.claims.length);
    expect(end?.scores.credibility).toBe(982);
    expect(end?.evidenceShown).toHaveLength(b.evidence.length);
  });

  it('shows the hand-computed numbers, P4 repair reasons verbatim, and the measured regression counts', () => {
    // credibility: 1000 + 10 (c01) + 18 (c02) - 60 (c03) + 7 (c04) + 7 (c05, fabricated but true) = 982; patches refund nothing.
    // fidelity: 3 of 5 claims match and the attacks are unjudged (60), the same as cases/app1-fixture.case.yml.
    const b = loadFixtureBundle();
    const { script, states } = play(b);
    expect(find(script, states, 'ruling', 'c05').s.scores).toMatchObject({ credibility: 982, fidelity: 60 });
    const reasons = script.flatMap((x, i) => (x.kind === 'repair' ? [states[i].subtitle?.text] : []));
    expect(reasons).toEqual(b.repairs.map((r) => r.reason));
    const end = states.at(-1);
    expect(end?.source).toBe('fixture');
    expect(end?.scores).toMatchObject({
      credibilityStart: 1000, credibility: 982, fidelity: 60, claimsMade: 5, claimsSurvived: 3,
      struck: 1, unsworn: 0, fabricated: 1, rollbacks: 0,
    });
    expect(end?.scores.brier).toBeCloseTo(0.173, 3);
    // Credibility peaks at 1028 after c02, so no line may call the opening 1000 the peak.
    expect(Math.max(...states.map((s) => s.scores.credibility))).toBe(1028);
  });
});
