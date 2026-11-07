import type {
  Attack, BehaviorSheet, Builds, CaseBundle, CaseFile, Claim, ClaimTest, Evidence, LedgerEvent, Lock, Repair, SheetLine, Verdict,
} from '../contracts';

// A rule returns the first problem it finds in x (named by the path `at`), or null when x fits.
type Rule = (x: unknown, at: string) => string | null;

const is = (ok: (x: unknown) => boolean, want: string): Rule => (x, at) => (ok(x) ? null : `${at}: expected ${want}`);
const str = is((x) => typeof x === 'string', 'a string');
const num = is((x) => typeof x === 'number' && Number.isFinite(x), 'a number');
const bool = is((x) => typeof x === 'boolean', 'true or false');
const oneOf = (...vals: string[]) => is((x) => vals.includes(x as string), vals.join(' | '));
const anything: Rule = () => null;
const opt = (r: Rule): Rule => (x, at) => (x === undefined ? null : r(x, at));
const orNull = (r: Rule): Rule => (x, at) => (x === null ? null : r(x, at));

const list = (r: Rule): Rule => (x, at) => {
  if (!Array.isArray(x)) return `${at}: expected a list`;
  for (const [i, item] of x.entries()) {
    const p = r(item, `${at}[${i}]`);
    if (p) return p;
  }
  return null;
};

// One rule per field of T, enforced by the mapped type, so a contract change that this file misses fails to compile.
function obj<T>(rules: { [K in keyof T]-?: Rule }): Rule {
  return (x, at) => {
    if (typeof x !== 'object' || x === null || Array.isArray(x)) return `${at}: expected an object`;
    for (const [k, r] of Object.entries<Rule>(rules)) {
      const p = r((x as Record<string, unknown>)[k], `${at}.${k}`);
      if (p) return p;
    }
    return null;
  };
}

const tier = oneOf('A', 'B', 'C', 'D');
const strs = list(str);

const evidence = obj<Evidence>({
  id: str, app: str, tier, kind: oneOf('page', 'screenshot', 'video', 'issue', 'doc'), source: str,
  text: opt(str), path: opt(str), license: opt(str),
});
const sheet = obj<BehaviorSheet>({
  app: str,
  lines: list(obj<SheetLine>({ id: str, screen: str, text: str, label: oneOf('SEEN', 'GUESSED'), citations: strs, conflicts: strs })),
});
const claim = obj<Claim>({
  id: str, app: str, screen: str, text: str,
  test: obj<ClaimTest>({ steps: strs, observe: str, expect: str }),
  tier, label: oneOf('SEEN', 'GUESSED', 'FABRICATED'), evidence: opt(strs),
  confidence: is((x) => typeof x === 'number' && x >= 0 && x <= 1, 'a number from 0 to 1'),
  bond: is((x) => Number.isInteger(x) && (x as number) >= 0, 'a whole number of at least 0'),
  commit: opt(str),
});
const attack = obj<Attack>({ id: str, app: str, screen: str, steps: strs, observe: str, commit: opt(str) });
const verdict = obj<Verdict>({
  ref: str, kind: oneOf('claim', 'attack'), original: str, revival: str, claim_true: opt(orNull(bool)),
  match: bool, flaky: bool, shrunk_steps: opt(strs),
});
const lock = obj<Lock>({ claim_id: str, status: oneOf('LOCKED', 'STRUCK', 'UNSWORN', 'FABRICATED'), reason: opt(str) });
const ledgerEvent = obj<LedgerEvent>({ seq: num, ts: str, type: str, payload: anything, prev_hash: str, hash: str });
const caseFile = obj<CaseFile>({
  app: str, fidelity: num, brier: num, credibility_start: num, credibility_end: num,
  locked: strs, struck: strs, fabricated: strs, unsworn: strs,
  counts: is((x) => typeof x === 'object' && x !== null && Object.values(x).every((n) => n === null || typeof n === 'number'), 'counts by name (a number or null)'),
});
const repair = obj<Repair>({
  claim_id: str, decision: oneOf('patched', 'rollback', 'unsworn'), reason: str, from_sha256: opt(str), to_sha256: opt(str),
});
const builds = obj<Builds>({ original: str, revival: str, revivalAfter: orNull(str), scale: num });
const after = obj<NonNullable<CaseBundle['after']>>({ verdicts: list(verdict), locks: list(lock), caseFile: orNull(caseFile) });
const bundle = obj<CaseBundle>({
  app: str, appLabel: str, source: anything, // toBundle stamps the source the caller asked for
  evidence: list(evidence), sheet: orNull(sheet), claims: list(claim), attacks: list(attack), verdicts: list(verdict),
  locks: list(lock), ledger: list(ledgerEvent), caseFile: orNull(caseFile), repairs: list(repair),
  builds, after: orNull(after),
});

/** The first thing wrong with x as a CaseBundle (e.g. "bundle.claims[2].bond: expected ..."), or null when it is one. */
export function bundleProblem(x: unknown): string | null {
  return bundle(x, 'bundle');
}

/** x as a CaseBundle from `source` when every array and required field fits CONTRACTS.md, else null. */
export function toBundle(x: unknown, source: CaseBundle['source']): CaseBundle | null {
  return bundle(x, 'bundle') === null ? { ...(x as CaseBundle), source } : null;
}

export function isVerdict(x: unknown): x is Verdict {
  return verdict(x, 'verdict') === null;
}
