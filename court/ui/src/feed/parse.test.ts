import { describe, expect, it } from 'vitest';
import app1Case from '../../../../cases/app1-fixture.case.yml?raw';
import { loadFixtureBundle } from '../fixtures';
import { fromLedger, parseCase, parseRepairs } from './parse';
import { bundleProblem } from './validate';

describe('parseCase', () => {
  it('reads P4\'s app1 fixture case', () => {
    const c = parseCase(app1Case);
    expect(c).toMatchObject({ app: 'app1-fixture', fidelity: 60, brier: 0.173, credibility_end: 982, unsworn: [] });
    expect(c.locked).toHaveLength(3);
    expect(c.struck).toEqual(['divide: 1 / 8 rounds to 0.13 [C]']);
    expect(c.counts).toMatchObject({ claims: 5, false_strikes_of: 12, traps_of: 8 });
  });

  it('keeps null counts and empty lists', () => {
    const c = parseCase('app: "x"\nfidelity: null\nlocked:\nstruck: []\ncounts:\n  claims: 2\n  false_strikes: null\n');
    expect(c).toMatchObject({ app: 'x', fidelity: null, locked: null, struck: [], counts: { claims: 2, false_strikes: null } });
  });
});

it('parseRepairs keeps rows with claim_id and decision', () => {
  const rows = parseRepairs('{"claim_id":"attacks:todo","decision":"patched","reason":"r","extra":1}\n{"type":"note"}\n{"half');
  expect(rows).toHaveLength(1);
  expect(rows[0]).toMatchObject({ claim_id: 'attacks:todo', decision: 'patched' });
});

it('fromLedger keeps the latest verdict and lock per ref', () => {
  const v = (revival: string) => ({ ref: 'c01', kind: 'claim', original: '1', revival, match: revival === '1', flaky: false });
  const got = fromLedger([
    { type: 'commit', payload: { commit: 'h', kind: 'claim', ref: 'c01' } },
    { type: 'verdict', payload: v('2') },
    { type: 'verdict', payload: v('1') },
    { type: 'lock', payload: { claim_id: 'c01', status: 'STRUCK', reason: 'a' } },
    { type: 'lock', payload: { claim_id: 'c01', status: 'LOCKED', reason: 'b' } },
  ]);
  expect(got.verdicts).toEqual([v('1')]);
  expect(got.locks).toEqual([{ claim_id: 'c01', status: 'LOCKED', reason: 'b' }]);
});

it('the fixture bundle fits the contract, with P4\'s repairs and no invented narrowed claim', () => {
  const b = loadFixtureBundle();
  expect(bundleProblem(b)).toBeNull();
  // P4 keeps appending real repairs to cases/app1/repairs.jsonl (t04 at 14:2x), so require ours, allow more.
  expect(b.repairs.map((r) => r.claim_id)).toEqual(expect.arrayContaining(['c03', 'c05']));
  expect(b.claims.some((c) => c.id === 'c03r')).toBe(false);
  expect(b.builds.scale).toBe(1.7);
});
