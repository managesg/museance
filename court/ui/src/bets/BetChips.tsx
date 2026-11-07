import { BOTS, STAKE } from '../engine/bets';
import './bets.css';

type Tone = 'brass' | 'crimson';

const JITTER = [0, 1.1, -0.8, 0.6, -1.1, 0.5];
const STEP = 6;

// One chip per stake, so a stack is as tall as the number of bettors on that side.
function Stack({ credits, tone }: { credits: number; tone: Tone }) {
  const n = credits > 0 ? Math.min(BOTS.length, Math.ceil(credits / STAKE)) : 0;
  const h = 26 + Math.max(0, n - 1) * STEP;
  const top = (i: number) => h - 15.5 - i * STEP;
  return (
    <svg className="bc__stack" viewBox={`0 0 44 ${h}`} style={{ aspectRatio: `44 / ${h}` }} aria-hidden="true">
      {n === 0 ? (
        <ellipse cx={22} cy={top(0) + 3} rx={19} ry={7.5} fill="none" stroke="var(--ink)" strokeWidth={2} strokeDasharray="4 4" />
      ) : (
        Array.from({ length: n }, (_, i) => {
          const y = top(i);
          return (
            <g key={i} transform={`translate(${JITTER[i % JITTER.length]} 0)`}>
              <path d={`M3 ${y}v6a19 7.5 0 0 0 38 0v-6Z`} fill={`var(--${tone}-deep)`} />
              <path d={`M10 ${y + 5.6}v3.6M22 ${y + 7.6}v3.6M34 ${y + 5.6}v3.6`} stroke="var(--paper)" strokeWidth={2.6} />
              <path d={`M3 ${y}v6a19 7.5 0 0 0 38 0v-6`} fill="none" stroke="var(--ink)" strokeWidth={2} strokeLinejoin="round" />
              <ellipse cx={22} cy={y} rx={19} ry={7.5} fill={`var(--${tone})`} stroke="var(--ink)" strokeWidth={2} />
              <ellipse cx={22} cy={y} rx={11} ry={4.2} fill="none" stroke={`var(--${tone}-deep)`} strokeWidth={1.6} />
            </g>
          );
        })
      )}
    </svg>
  );
}

/** The gallery's money on one claim: a brass stack on TRUE, a crimson stack on FALSE, laid under the card. */
export function BetChips({ trueCredits, falseCredits }: { trueCredits: number; falseCredits: number }) {
  return (
    <div className="bc" role="img" aria-label={`Bets: ${trueCredits} credits on true, ${falseCredits} on false`}>
      {(
        [
          ['brass', 'TRUE', trueCredits],
          ['crimson', 'FALSE', falseCredits],
        ] as const
      ).map(([tone, word, credits]) => (
        <span key={word} className={`bc__pile bc__pile--${tone}`}>
          <Stack credits={credits} tone={tone} />
          <span className="bc__tag">
            <span className="bc__count">{credits}</span>
            <span className="bc__word">{word}</span>
          </span>
        </span>
      ))}
    </div>
  );
}
