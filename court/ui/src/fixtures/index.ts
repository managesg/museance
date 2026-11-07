import type { Attack, CaseBundle, Claim, Verdict } from '../contracts';
import type { BenchSuggestion } from '../engine/types';
import attacks from '../../../../fixtures/attacks.json';
import claims from '../../../../fixtures/claims.json';
import verdicts from '../../../../fixtures/verdicts.json';
import caseYaml from '../../../../cases/app1-fixture.case.yml?raw';
import repairsJsonl from '../../../../cases/app1/repairs.jsonl?raw';
import { FIXTURE_BUILDS } from '../feed/builds';
import { parseCase, parseRepairs } from '../feed/parse';
import { APP1_EVIDENCE, APP1_SHEET } from './app1.extra';

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
  caseFile: parseCase(caseYaml),
  repairs: parseRepairs(repairsJsonl),
  builds: FIXTURE_BUILDS,
  after: null,
};

export function loadFixtureBundle(): CaseBundle {
  return BUNDLE;
}

export const BENCH_SUGGESTIONS: BenchSuggestion[] = [
  { label: '7 ÷ 0 =', steps: ['click:#k7', 'click:#kdiv', 'click:#k0', 'click:#keq'] },
  { label: '.1 + .1 =', steps: ['click:#kdot', 'click:#k1', 'click:#kadd', 'click:#kdot', 'click:#k1', 'click:#keq'] },
];
