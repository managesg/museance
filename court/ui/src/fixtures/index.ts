import type { Attack, CaseBundle, Claim, Verdict } from '../contracts';
import type { BenchSuggestion } from '../engine/types';
import attacks from '../../../../fixtures/attacks.json';
import claims from '../../../../fixtures/claims.json';
import verdicts from '../../../../fixtures/verdicts.json';
import { APP1_EVIDENCE, APP1_REPAIRS, APP1_SHEET } from './app1.extra';

// Built once so callers that key effects or memos on the bundle get the same object every time.
const BUNDLE: CaseBundle = {
  app: 'app1',
  appLabel: 'fixture-calc',
  source: 'fixture',
  evidence: APP1_EVIDENCE,
  sheet: APP1_SHEET,
  // JSON imports widen the enum fields (tier, label, kind) to string; the files follow contracts/*.schema.json.
  claims: claims as Claim[],
  attacks: attacks as Attack[],
  verdicts: verdicts as Verdict[],
  locks: [],
  ledger: [],
  caseFile: null,
  repairs: APP1_REPAIRS,
};

export function loadFixtureBundle(): CaseBundle {
  return BUNDLE;
}

export const BENCH_SUGGESTIONS: BenchSuggestion[] = [
  { label: '7 ÷ 0 =', steps: ['click:#k7', 'click:#kdiv', 'click:#k0', 'click:#keq'] },
  { label: '.1 + .1 =', steps: ['click:#kdot', 'click:#k1', 'click:#kadd', 'click:#kdot', 'click:#k1', 'click:#keq'] },
];
