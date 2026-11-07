// Fixture material for fixtures/app1 (fixture-calc), written today for lane testing: an invented evidence pile,
// behavior sheet and repair. Nothing here was dug up from a real dead app; sources are plain descriptions, not links.
import type { BehaviorSheet, Evidence, Repair, SheetLine, Tier } from '../contracts';

const ev = (id: string, tier: Tier, kind: Evidence['kind'], source: string, text: string): Evidence => ({
  id, app: 'app1', tier, kind, source, text, license: 'MIT',
});

// shot-001, shot-002, thread-003 and shot-004 are the ids fixtures/claims.json cites.
export const APP1_EVIDENCE: Evidence[] = [
  ev('shot-001', 'A', 'screenshot', 'Fixture screenshot of the archived build', 'The display reads 15 right after 7 + 8 =.'),
  ev('shot-002', 'A', 'screenshot', 'Fixture screenshot of the archived build', 'The display reads 56 right after 7 x 8 =.'),
  ev('thread-003', 'C', 'page', 'Fixture forum thread “decimals in fixture-calc?”',
    'A user says 1 / 8 comes out as 0.13: “it rounds like a normal calculator.” The README says results are truncated.'),
  ev('shot-004', 'A', 'screenshot', 'Fixture screenshot of the archived build', 'The display reads 0 right after pressing C.'),
  ev('build-005', 'A', 'page', 'Fixture archive: the built page of fixture-calc, which still runs',
    'One page with a display and ten keys: 7 8 1 0 + x / . = C. The display starts at 0.'),
  ev('video-006', 'B', 'video', 'Fixture tutorial video “fixture-calc in 60 seconds”, at 0:42',
    'The presenter types 7 + 8 = and the display shows 15. The video ends before any division.'),
  ev('readme-007', 'B', 'doc', 'Fixture README from the archived source folder',
    'A four-function pocket calculator. The display starts at 0 and a leading 0 is replaced by the next digit. Results are truncated to two decimals. C clears everything back to 0.'),
  ev('issue-008', 'C', 'issue', 'Fixture issue report #8, closed',
    '“1 / 8 shows 0.12, I expected 0.13.” Closed by the maker: “by design, results are cut to two decimals, not rounded.”'),
  ev('doc-009', 'B', 'doc', 'Fixture help page “Keys”',
    'Lists the keys 7 8 1 0 . + x / = C. The dot key starts a decimal; C clears everything back to 0.'),
  ev('issue-010', 'C', 'issue', 'Fixture issue report #10, open',
    '“Pressing x twice, as in 8 x x 7 =, gives 0. Is that a bug?” No reply.'),
  ev('doc-011', 'D', 'doc', 'Fixture help page “When things go wrong”',
    'Only the title survives in the archived table of contents. The page itself is empty.'),
  ev('page-012', 'D', 'page', 'Fixture changelog, entry for version 1.2',
    'The entry reads “changed how decimals are shown”. Its link to the details is dead; nothing else survives.'),
];

const line = (id: string, screen: string, text: string, label: SheetLine['label'], citations: string[], conflicts: string[] = []): SheetLine => ({
  id, screen, text, label, citations, conflicts,
});

// conflicts = evidence ids that contradict the line, as dig/reader.py writes them.
export const APP1_SHEET: BehaviorSheet = {
  app: 'app1',
  lines: [
    line('b001', 'add', '7 + 8 = shows 15', 'SEEN', ['shot-001', 'video-006']),
    line('b002', 'multiply', '7 x 8 = shows 56', 'SEEN', ['shot-002']),
    line('b003', 'divide', '1 / 8 = shows 0.13, rounded to two decimals', 'GUESSED', ['thread-003'], ['readme-007', 'issue-008']),
    line('b004', 'clear', 'C sets the display back to 0', 'SEEN', ['shot-004', 'doc-009', 'readme-007']),
    line('b005', 'clear', 'The display shows 0 when the page loads', 'SEEN', ['build-005', 'readme-007']),
    line('b006', 'clear', 'After C, typing 0 0 still shows a single 0', 'GUESSED', ['readme-007']),
    line('b007', 'add', '.1 + .1 = shows 0.2', 'GUESSED', ['doc-009']),
    line('b008', 'multiply', 'Pressing x twice, as in 8 x x 7 =, shows 0', 'GUESSED', ['issue-010']),
    line('b009', 'divide', 'Dividing by zero shows Error', 'GUESSED', []),
  ],
};

// c03 was struck because the original truncates 1 / 8 to 0.12; public/revival-fixture-repaired truncates too.
export const APP1_REPAIRS: Repair[] = [
  {
    struck_id: 'c03',
    claim: {
      id: 'c03r', app: 'app1', screen: 'divide', text: '1 / 8 truncates to 0.12',
      test: { steps: ['click:#k1', 'click:#kdiv', 'click:#k8', 'click:#keq'], observe: '#display', expect: '0.12' },
      tier: 'C', label: 'GUESSED', evidence: ['issue-008'], confidence: 0.74, bond: 50,
    },
    verdict: { ref: 'c03r', kind: 'claim', original: '0.12', revival: '0.12', claim_true: true, match: true, flaky: false, shrunk_steps: [] },
    // revive/repair.py: a rollback drops the patch and keeps the old build; this patch was kept (cases/app1/repairs.jsonl: patched).
    rollback: false,
    note: 'rounds -> truncates',
  },
];
