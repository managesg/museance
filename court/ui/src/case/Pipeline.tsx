// The case as eight plain steps; each count stays a dash until the show reaches its phase.
import type { CaseBundle, Verdict } from '../contracts';
import { fidelity } from '../engine/scoring';
import { PHASES, type Phase, type StageState } from '../engine/types';
import { Explain } from './Explain';
import type { Term } from './glossary';
import './pipeline.css';

const mismatches = (vs: Verdict[]) => vs.filter((v) => !v.flaky && !v.match).length;
const tally = <T,>(xs: T[], key: (x: T) => string) => xs.reduce<Record<string, number>>((m, x) => ({ ...m, [key(x)]: (m[key(x)] ?? 0) + 1 }), {});
const short = (s: string, n = 64) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
const num = (n: number | null | undefined, d = 0) => (typeof n === 'number' && Number.isFinite(n) ? n.toFixed(d) : '—');

interface Step { name: string; term?: Term; phase: Phase; detail: () => string }

function steps(b: CaseBundle, s: StageState): Step[] {
  const tiers = tally(b.evidence, (e) => e.tier);
  const lines = b.sheet?.lines ?? [];
  const labels = tally(lines, (l) => l.label);
  // medium_confidence is P2's raw guess; it is not in the Claim contract, so read it loosely.
  const fromSubq = b.claims.some((c) => {
    const m = (c as { medium_confidence?: unknown }).medium_confidence;
    return typeof m === 'number' && m !== c.confidence;
  });
  const status = tally(s.cards, (k) => k.status);
  const repair = b.repairs[0];
  const before = b.caseFile?.fidelity ?? fidelity(b.verdicts);
  const after = b.after ? (b.after.caseFile?.fidelity ?? fidelity(b.after.verdicts)) : null;
  return [
    { name: 'Evidence dug', term: 'evidence', phase: 'dig', detail: () => `${b.evidence.length} items · ${(['A', 'B', 'C', 'D'] as const).map((t) => `${t} ${tiers[t] ?? 0}`).join(' · ')}` },
    { name: 'Behavior sheet', term: 'sheet', phase: 'read', detail: () => `${lines.length} lines · ${labels.SEEN ?? 0} seen · ${labels.GUESSED ?? 0} guessed` },
    { name: 'Claims sworn', term: 'claim', phase: 'swear', detail: () => `${b.claims.length} claims${fromSubq ? ' · confidence from SubQ' : ''}` },
    { name: 'Revival built', term: 'revival', phase: 'raise', detail: () => s.exhibits.revivalSrc.match(/v\d+/)?.[0] ?? 'v1' },
    { name: 'Attacks sealed', term: 'attack', phase: 'swear', detail: () => `${b.attacks.length} attacks` },
    {
      name: 'Court ruled',
      term: 'court',
      phase: 'cross',
      detail: () => `${status.LOCKED ?? 0} locked · ${status.STRUCK ?? 0} struck · ${status.UNSWORN ?? 0} unsworn · ${mismatches(b.verdicts)} mismatches`,
    },
    {
      name: 'Repair',
      term: 'repair',
      phase: 'repair',
      detail: () =>
        repair
          ? `${repair.decision}: ${short(repair.reason)}${b.after ? ` · ${mismatches(b.after.verdicts)} mismatches after, fidelity ${num(after)}` : ''}`
          : 'no repair needed',
    },
    {
      name: 'Case file',
      phase: 'sentence',
      detail: () =>
        `fidelity ${num(before)}${after !== null ? ` → ${num(after)}` : ''} · credibility ${num(s.scores.credibilityStart)} → ${num(s.scores.credibility)} · Brier ${num(s.scores.brier, 3)}`,
    },
  ];
}

export function Pipeline({ bundle, state }: { bundle: CaseBundle; state: StageState }) {
  const at = PHASES.indexOf(state.phase);
  return (
    <ol className="pl" aria-label="Case progress">
      {steps(bundle, state).map((st, i) => {
        const p = PHASES.indexOf(st.phase);
        const mark = p < at ? 'done' : p === at ? 'now' : 'waiting';
        return (
          <li key={st.name} className={`pl-step pl-step--${mark}`} aria-current={mark === 'now' ? 'step' : undefined}>
            <span className={`pl-mark pl-mark--${mark}`} aria-hidden="true" />
            <span className="pl-body">
              <span className="pl-name">
                {i + 1}. <Explain term={st.term}>{st.name}</Explain>
                <span className="pl-sr"> ({mark})</span>
              </span>
              <span className="pl-detail">{mark === 'waiting' ? '—' : st.detail()}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
