import { expect, it } from 'vitest';
import { parseCase } from '../feed/parse';
import type { Claim, LockStatus, Verdict } from '../contracts';
import { computeScores, fidelity } from './scoring';

import claimsJson from '../../../../dig/out/todo/claims.json';
import v1Locks from '../../../../cases/todo/v1-16claims/locks.json';
import v1Verdicts from '../../../../cases/todo/v1-16claims/verdicts.json';
import v2Verdicts from '../../../../cases/todo/v2-16claims/verdicts.json';
import caseYaml from '../../../../cases/todo.case.yml?raw';

it('parseCase reads a CRLF checkout (Windows core.autocrlf) like an LF one', () => {
  const text = caseYaml;
  expect(parseCase(text.replace(/\r?\n/g, '\r\n'))).toEqual(parseCase(text.replace(/\r\n/g, '\n')));
});

it('todo shows the committed case numbers: 930, Brier 0.071, fidelity 41 -> 100, 15 locked / 1 struck', () => {
  const claims = claimsJson as Claim[];
  const locks = v1Locks as { claim_id: string; status: LockStatus }[];
  const verdicts = v1Verdicts as Verdict[];
  const caseFile = parseCase(caseYaml);
  const statuses = Object.fromEntries(locks.map((l) => [l.claim_id, l.status]));
  const s = computeScores({ claims, verdicts, caseFile } as never, statuses);
  expect(s).toMatchObject({ credibility: 930, brier: 0.071, fidelity: 100, claimsMade: 16, claimsSurvived: 15, struck: 1, falseStrikes: { value: 0, of: 12 } });
  // Unrounded, from the claims and verdicts alone (the case file is not consulted).
  expect(computeScores({ claims, verdicts, caseFile: null, after: null } as never, statuses)).toMatchObject({ credibility: 930 });
  expect(fidelity(verdicts)).toBe(41);
  expect(fidelity(v2Verdicts as Verdict[])).toBe(100);
});
