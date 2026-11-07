import { describe, expect, it } from 'vitest';
import type { Attack, CaseBundle, Claim, Repair, Verdict } from '../contracts';
import attacksJson from '../../../../fixtures/attacks.json';
import claimsJson from '../../../../fixtures/claims.json';
import verdictsJson from '../../../../fixtures/verdicts.json';
import { loadFixtureBundle } from '../fixtures';
import { EXHIBIT_SRC, buildScript, foldStates, initialState, stateAt, type BenchRuns } from './director';
import { GENESIS, commitOf, sha256Hex, synthesizeLedger, verifyLedger } from './hash';
import { PHASES, type Beat, type StageState } from './types';

const claims = claimsJson as Claim[];
const c03 = claims[2];

const REPAIR: Repair = {
  struck_id: 'c03',
  claim: { ...c03, id: 'c03r', text: '1 / 8 truncates to 0.12', test: { ...c03.test, expect: '0.12' }, confidence: 0.74, bond: 50 },
  verdict: { ref: 'c03r', kind: 'claim', original: '0.12', revival: '0.12', claim_true: true, match: true, flaky: false, shrunk_steps: [] },
  rollback: true,
  note: 'rounds -> truncates',
};

const bundle = (over: Partial<CaseBundle> = {}): CaseBundle => ({
  app: 'app1', appLabel: 'fixture-calc', source: 'fixture',
  evidence: [
    { id: 'shot-001', app: 'app1', tier: 'A', kind: 'screenshot', source: 'test', text: 'The display reads 15.' },
    { id: 'thread-003', app: 'app1', tier: 'C', kind: 'page', source: 'test', text: 'A user says it rounds.' },
  ],
  sheet: { app: 'app1', lines: [{ id: 'b001', screen: 'add', text: '7 + 8 shows 15', label: 'SEEN', citations: ['shot-001'], conflicts: [] }] },
  claims, attacks: attacksJson as Attack[], verdicts: verdictsJson as Verdict[],
  locks: [], ledger: [], caseFile: null, repairs: [REPAIR], ...over,
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
    expect(ms('attack')).toEqual([900, 900, 900, 900, 900]);
    expect(script.filter((b) => b.kind === 'repair')).toHaveLength(1);
  });

  it('opens each attack after the first ruling on its screen', () => {
    const { script, states } = play(bundle());
    const opened = script.flatMap((b, i) => (b.kind === 'attack' ? states[i].attacks.filter((a) => a.opened).length : []));
    expect(opened).toEqual([1, 2, 3, 4, 5]);
    const last = states.at(-1);
    expect(last?.attacks.map((a) => a.opened)).toEqual([true, true, true, true, true]);
    const firstAttack = (id: string) => script.findIndex((b, i) => b.kind === 'attack' && states[i].attacks.some((a) => a.attack.id === id && a.opened));
    // claim order is add, multiply, divide, clear: a02 a03 (a01 a05) a04
    expect(['a02', 'a03', 'a01', 'a05', 'a04'].map(firstAttack)).toEqual(['a02', 'a03', 'a01', 'a05', 'a04'].map(firstAttack).sort((a, b) => a - b));
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

  it('repairs c03: narrowed claim re-ruled LOCKED, fidelity 60 to 80, no refund', () => {
    const boot = find(script, states, 'repair').s;
    expect(boot.exhibits).toMatchObject({ revival: 'booting', revivalSrc: EXHIBIT_SRC.repaired });
    expect(boot.scores.credibility).toBe(982);
    const { s } = find(script, states, 'repaired');
    expect(s.cards[2]).toMatchObject({ status: 'LOCKED', repairedFrom: 'c03', claim: { id: 'c03r' } });
    expect(s.scores).toMatchObject({ fidelity: 80, credibility: 982, rollbacks: 1, struck: 1 });
    expect(s.exhibits.revival).toBe('live');
    expect(guy(s, 'divide')).toBe('repaired');
    expect(s.moods.faux).toBe('hidden');
  });

  it('sentences: Faux bows at fidelity 80 with no strike standing; counsel nervous at 982', () => {
    const end = states.at(-1);
    expect(end?.phase).toBe('sentence');
    expect(end?.moods).toMatchObject({ faux: 'bow', mcclusky: 'nervous' });
    const sentence = find(script, states, 'sentence').s;
    expect(sentence.subtitle?.text).toBe('Fidelity 80. Credibility 982. Brier 0.173.');
    expect(end?.subtitle?.text).toBe('Down 18 credits. I\'ll appeal. To whom, unclear.');
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

describe('bench', () => {
  it('lands bench verdicts at the bench beat and counts them toward fidelity', () => {
    const v: Verdict = { ref: 'bench-1', kind: 'attack', original: '0.2', revival: '0.2', claim_true: null, match: true, flaky: false, shrunk_steps: [] };
    const { script, states } = play(bundle(), { verdicts: [v], events: [] });
    const { s } = find(script, states, 'bench');
    expect(s.bench).toEqual({ open: true, last: v, runs: 1 });
    // c01 c02 c03r c04 and the bench run match, c05 does not: 100 * 5 / 6 = 83.3
    expect(s.scores.fidelity).toBe(83);
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
      seq: 1, type: 'claim_committed', prev_hash: GENESIS,
      hash: 'aad36b1596125a99193202a27374c45ff105f8947d4fe95c42049bc4c048812c',
    });
    expect(ledger.map((e) => e.type)).toEqual([
      ...Array<string>(5).fill('claim_committed'), ...Array<string>(5).fill('attack_committed'),
      ...Array<string>(5).fill('verdict'), ...Array<string>(5).fill('lock'), 'repair', 'rollback',
    ]);
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
});
