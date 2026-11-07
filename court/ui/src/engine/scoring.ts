// Mirrors eval/score.py (P4) and court/bailiff.py (P1) so the stage never disagrees with the case file.
import type { CaseBundle, CaseFile, Claim, LockStatus, Verdict } from '../contracts';
import type { Measured, Scores } from './types';

export const CREDIBILITY_START = 1000;

/** Python's round(): an exact half goes to the even neighbour (round(2.5) == 2). */
export function pyRound(x: number): number {
  const f = Math.floor(x);
  return x - f === 0.5 ? (f % 2 === 0 ? f : f + 1) : Math.round(x);
}

/** Claim verdicts by ref. A verdict without a kind counts as a claim, as in eval/score.py. */
export function claimVerdicts(verdicts: Verdict[]): Map<string, Verdict> {
  return new Map(verdicts.filter((v) => v.kind !== 'attack').map((v) => [v.ref, v]));
}

/** null means the court has not ruled yet. */
export function deriveLock(claim: Claim, verdict: Verdict | undefined): LockStatus | null {
  if (!verdict) return null;
  // A FABRICATED label wins over every ruling except STRUCK. A flaky run, or no claim_true (the original never
  // loaded), is UNSWORN, never STRUCK (court/bailiff.py).
  if (verdict.flaky || typeof verdict.claim_true !== 'boolean') return claim.label === 'FABRICATED' ? 'FABRICATED' : 'UNSWORN';
  if (!verdict.claim_true) return 'STRUCK';
  return claim.label === 'FABRICATED' ? 'FABRICATED' : 'LOCKED';
}

/** Credibility change for one ruled claim. */
export function credibilityDelta(claim: Claim, status: LockStatus, verdict: Verdict | undefined): number {
  const gain = pyRound(claim.bond * (1 - claim.confidence));
  if (status === 'STRUCK') return -claim.bond;
  if (status === 'LOCKED') return gain;
  // eval/score.py credits a FABRICATED claim that held exactly like a LOCKED one.
  if (status === 'FABRICATED') return verdict && !verdict.flaky && verdict.claim_true === true ? gain : 0;
  return 0;
}

/** Mean of (confidence - claim_true)^2 over claims with a non-flaky boolean verdict. */
export function brier(claims: Claim[], verdicts: Verdict[]): number | null {
  const byRef = claimVerdicts(verdicts);
  const errs = claims.flatMap((c) => {
    const v = byRef.get(c.id);
    return v && !v.flaky && typeof v.claim_true === 'boolean' ? [(c.confidence - Number(v.claim_true)) ** 2] : [];
  });
  return errs.length ? errs.reduce((a, b) => a + b, 0) / errs.length : null;
}

/** 100 * matched / non-flaky, rounded like eval/score.py. */
export function fidelity(verdicts: Verdict[]): number | null {
  const live = verdicts.filter((v) => !v.flaky);
  return live.length ? pyRound((100 * live.filter((v) => v.match).length) / live.length) : null;
}

function measured(cf: CaseFile | null, value: string, of: string): Measured | null {
  const n = cf?.counts;
  return n && typeof n[value] === 'number' && typeof n[of] === 'number' ? { value: n[value], of: n[of] } : null;
}

/** Scores for the claims that have a status; fidelity covers every verdict in the bundle. */
export function computeScores(bundle: CaseBundle, statuses: Record<string, LockStatus>, opts: { rollbacks?: number } = {}): Scores {
  const cf = bundle.caseFile;
  const byRef = claimVerdicts(bundle.verdicts);
  const ruled = bundle.claims.filter((c) => statuses[c.id]);
  const count = (st: LockStatus) => ruled.filter((c) => statuses[c.id] === st).length;
  const start = cf?.credibility_start ?? CREDIBILITY_START;
  const scores: Scores = {
    credibilityStart: start,
    credibility: ruled.reduce((sum, c) => sum + credibilityDelta(c, statuses[c.id], byRef.get(c.id)), start),
    brier: brier(ruled, bundle.verdicts),
    fidelity: fidelity(bundle.verdicts),
    claimsMade: bundle.claims.length,
    claimsSurvived: count('LOCKED'),
    struck: count('STRUCK'),
    unsworn: count('UNSWORN'),
    fabricated: count('FABRICATED'),
    rollbacks: opts.rollbacks ?? 0,
    falseStrikes: measured(cf, 'false_strikes', 'false_strikes_of'),
    trapsCaught: measured(cf, 'traps_caught', 'traps_of'),
  };
  // The case file is P4's result for the finished ruling, so it only takes over once every claim is ruled.
  if (!cf || !ruled.length || ruled.length < bundle.claims.length) return scores;
  const n = cf.counts;
  return {
    ...scores,
    credibility: cf.credibility_end,
    brier: cf.brier,
    fidelity: cf.fidelity,
    claimsMade: n.claims ?? scores.claimsMade,
    claimsSurvived: n.locked ?? scores.claimsSurvived,
    struck: n.struck ?? scores.struck,
    unsworn: n.unsworn ?? scores.unsworn,
    fabricated: n.fabricated ?? scores.fabricated,
  };
}
