import { PHASES, type Phase } from '../engine/types';
import './hud.css';

const NAMES: Record<Phase, string> = {
  dig: 'Dig',
  read: 'Read',
  raise: 'Raise',
  swear: 'Swear',
  cross: 'Cross',
  repair: 'Repair',
  bench: 'Bench',
  sentence: 'Sentence',
};

/** Brass tabs hanging from the top rail: past phases retract and dim, the current one drops and burns. About 870x84 design px. */
export function PhaseDocket({ phase }: { phase: Phase }) {
  const now = PHASES.indexOf(phase);
  return (
    <ol className="hud-docket" aria-label="Trial phases">
      {PHASES.map((p, i) => (
        <li
          key={p}
          className={`hud-tab ${i < now ? 'is-past' : i === now ? 'is-now' : 'is-next'}`}
          aria-current={i === now ? 'step' : undefined}
        >
          <span className="hud-tab__glow" aria-hidden="true" />
          <span className="hud-tab__plate">{NAMES[p]}</span>
        </li>
      ))}
    </ol>
  );
}
