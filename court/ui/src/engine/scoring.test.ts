import { describe, expect, it } from 'vitest';
import type { Attack, CaseBundle, CaseFile, Claim, LockStatus, Verdict } from '../contracts';
import attacksJson from '../../../../fixtures/attacks.json';
import claimsJson from '../../../../fixtures/claims.json';
import verdictsJson from '../../../../fixtures/verdicts.json';
import { BOTS, betTotals, placeBets, settle } from './bets';
import { brier, computeScores, deriveLock, fidelity, pyRound } from './scoring';

const claims = claimsJson as Claim[];
const verdicts = verdictsJson as Verdict[];
const verdictOf = (id: string) => verdicts.find((v) => v.ref === id);

const bundle = (over: Partial<CaseBundle> = {}): CaseBundle => ({
  app: 'app1', appLabel: 'fixture-calc', source: 'fixture', evidence: [], sheet: null,
  claims, attacks: attacksJson as Attack[], verdicts, locks: [], ledger: [], caseFile: null, repairs: [], ...over,
});
const derived = (): Record<string, LockStatus> => {
  const out: Record<string, LockStatus> = {};
  for (const c of claims) {
    const st = deriveLock(c, verdictOf(c.id));
    if (st) out[c.id] = st;
  }
  return out;
};
const claim = (over: Partial<Claim> = {}): Claim => ({
  id: 'x', app: 'app1', screen: 's', text: 't', test: { steps: [], observe: '#display', expect: '1' },
  tier: 'A', label: 'SEEN', confidence: 0.5, bond: 100, ...over,
});
const verdict = (over: Partial<Verdict> = {}): Verdict => ({
  ref: 'x', kind: 'claim', original: '1', revival: '1', claim_true: true, match: true, flaky: false, ...over,
});

describe('deriveLock', () => {
  it('rules the repo fixtures like court/bailiff.py and eval/score.py', () => {
    expect(derived()).toEqual({ c01: 'LOCKED', c02: 'LOCKED', c03: 'STRUCK', c04: 'LOCKED', c05: 'FABRICATED' });
  });

  it('makes a flaky verdict UNSWORN, never STRUCK', () => {
    expect(deriveLock(claim(), verdict({ flaky: true, claim_true: false, match: false }))).toBe('UNSWORN');
  });

  it('keeps a FABRICATED label through flaky runs but not through a strike', () => {
    const fab = claim({ label: 'FABRICATED' });
    expect(deriveLock(fab, verdict({ flaky: true }))).toBe('FABRICATED');
    expect(deriveLock(fab, verdict({ claim_true: false }))).toBe('STRUCK');
    expect(deriveLock(fab, verdict({ claim_true: true }))).toBe('FABRICATED');
  });

  it('returns null while there is no verdict', () => {
    expect(deriveLock(claim(), undefined)).toBeNull();
  });
});

describe('computeScores on the repo fixtures', () => {
  // By hand, from fixtures/claims.json and fixtures/verdicts.json:
  // credibility: c01 +round(200 * .05) = 10, c02 +round(180 * .10) = 18, c04 +round(220 * .03) = 7,
  //   c05 is FABRICATED but held, which eval/score.py credits like LOCKED: +round(10 * .70) = 7,
  //   c03 STRUCK -60  ->  1000 + 10 + 18 + 7 + 7 - 60 = 982 (cases/app1-fixture.case.yml says 982 too)
  // brier: (.95-1)^2 + (.9-1)^2 + (.6-0)^2 + (.97-1)^2 + (.3-1)^2 = .0025 + .01 + .36 + .0009 + .49 = .8634; / 5 = .17268
  // fidelity: c01 c02 c04 match, c03 c05 do not  ->  100 * 3 / 5 = 60
  it('matches the hand-computed numbers', () => {
    const s = computeScores(bundle(), derived());
    expect(s).toMatchObject({
      credibilityStart: 1000, credibility: 982, fidelity: 60, claimsMade: 5, claimsSurvived: 3,
      struck: 1, unsworn: 0, fabricated: 1, rollbacks: 0, falseStrikes: null, trapsCaught: null,
    });
    expect(s.brier).toBeCloseTo(0.17268, 12);
  });

  it('scores only the claims ruled so far', () => {
    const s = computeScores(bundle(), { c01: 'LOCKED', c03: 'STRUCK' });
    expect(s.credibility).toBe(1000 + 10 - 60);
    expect(s.brier).toBeCloseTo((0.0025 + 0.36) / 2, 12);
    expect(s.claimsSurvived).toBe(1);
  });

  it('takes the case file once every claim is ruled, and never invents regression numbers', () => {
    const caseFile: CaseFile = {
      app: 'app1', fidelity: 55, brier: 0.173, credibility_start: 1000, credibility_end: 975,
      locked: [], struck: [], fabricated: [], unsworn: [],
      counts: { claims: 5, locked: 3, struck: 1, fabricated: 1, unsworn: 0, false_strikes: 0, false_strikes_of: 12, traps_caught: 7, traps_of: 8 },
    };
    expect(computeScores(bundle({ caseFile }), derived(), { rollbacks: 1 })).toMatchObject({
      credibility: 975, brier: 0.173, fidelity: 55, rollbacks: 1,
      falseStrikes: { value: 0, of: 12 }, trapsCaught: { value: 7, of: 8 },
    });
    expect(computeScores(bundle({ caseFile }), { c01: 'LOCKED' }).credibility).toBe(1010);
    const bare = computeScores(bundle({ caseFile: { ...caseFile, counts: { claims: 5 } } }), derived());
    expect(bare.falseStrikes).toBeNull();
    expect(bare.trapsCaught).toBeNull();
  });
});

describe('brier and fidelity', () => {
  it('leave flaky runs out and return null when nothing was measured', () => {
    expect(brier([claim()], [verdict({ flaky: true })])).toBeNull();
    expect(brier([claim()], [])).toBeNull();
    expect(brier([claim({ confidence: 0.8 })], [verdict({ claim_true: false })])).toBeCloseTo(0.64, 12);
    expect(fidelity([verdict({ flaky: true, match: false })])).toBeNull();
    expect(fidelity([verdict(), verdict({ match: false }), verdict({ flaky: true, match: false })])).toBe(50);
  });

  it('round halves to even like Python', () => {
    const eight = (matched: number) => Array.from({ length: 8 }, (_, i) => verdict({ match: i < matched }));
    expect(fidelity(eight(1))).toBe(12); // 12.5
    expect(fidelity(eight(3))).toBe(38); // 37.5
    expect([0.5, 1.5, 2.5, 2.6, -2.5, 7.000000000000001].map(pyRound)).toEqual([0, 2, 2, 3, -2, 7]);
  });
});

describe('bets', () => {
  const bets = placeBets(claims, 'app1');
  const side = (pastry: string, id: string) => bets.find((b) => b.pastry === pastry && b.claimId === id)?.onTrue;

  it('is deterministic per app and stakes 100 per bot per claim', () => {
    expect(placeBets(claims, 'app1')).toEqual(bets);
    expect(bets).toHaveLength(claims.length * BOTS.length);
    const t = betTotals(bets, 'c01');
    expect(t.trueCredits + t.falseCredits).toBe(600);
  });

  it('gives each bot its own policy', () => {
    expect(claims.map((c) => side('croissant', c.id))).toEqual([true, true, true, true, true]);
    expect(claims.map((c) => side('bagel', c.id))).toEqual([true, true, false, true, false]); // tiers A A C A D
    expect(claims.map((c) => side('pretzel', c.id))).toEqual([false, false, false, false, true]); // only c05 is under 50%
    for (const c of claims) {
      const yes = BOTS.slice(0, 5).filter((b) => side(b.pastry, c.id)).length;
      expect(side('kouign', c.id)).toBe(yes >= 3);
    }
  });

  it('settles 100 a claim once its verdict lands', () => {
    const board = settle(bets, verdicts);
    const row = (pastry: string) => board.find((r) => r.pastry === pastry);
    // Croissant backs all five; only c03 is false: 4 wins, 1 loss -> 1300
    expect(row('croissant')).toMatchObject({ credits: 1300, wins: 4, losses: 1 });
    // Bagel doubts c03 (false: win) and c05 (true: loss): 4-1 -> 1300
    expect(row('bagel')).toMatchObject({ credits: 1300, wins: 4, losses: 1 });
    // Pretzel doubts c01 c02 c03 c04 and backs c05: wins c03 and c05 -> 2-3 -> 900
    expect(row('pretzel')).toMatchObject({ credits: 900, wins: 2, losses: 3 });
    expect(board.map((r) => r.credits)).toEqual(board.map((r) => r.credits).sort((a, b) => b - a));
    expect(settle(bets, []).every((r) => r.credits === 1000 && r.wins === 0)).toBe(true);
    expect(settle(bets, [{ ...verdicts[0], flaky: true }]).every((r) => r.credits === 1000)).toBe(true);
  });
});
