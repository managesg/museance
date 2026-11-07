import './hud.css';

const PER_COIN = 100;
const SLOTS = 20; // a 2000-credit stack fills the frame; more stays at 20 coins while the number keeps counting
const STEP = 10;
const BASE = 219; // face centre of the bottom coin, resting on the stand's top face
const JITTER = [0, 3, -2, 4, -3, 1, -4, 2, 3, -1, -3, 4, 0, -2, 3, -4, 2, -1, 1, -3];

const BAND = 'M-50 0V9A50 13 0 0 0 50 9V0A50 13 0 0 1 -50 0Z';
const RIM = 'M-50 0V9A50 13 0 0 0 50 9V0';
const STAND = 'M26 236L214 235L224 247L224.5 318L15.5 318.5L16 247.5Z';
const STAND_TOP = 'M26 236L214 235L224 247L16 247.5Z';
const WINDOW =
  'M32 256.5Q120 255 208 256.2Q211.5 256.4 211.6 260L212 304Q211.8 307.6 208.2 307.8Q120 309.2 32.2 307.6Q28.6 307.4 28.5 303.8L28.3 260.2Q28.4 256.6 32 256.5Z';
const RIBBON = 'M-126 -22Q0 -27 126 -22L126 20Q0 15 -126 20Z';
const TAIL_L = 'M-104 -10L-150 -10L-134 8L-150 27L-104 27Z';
const TAIL_R = 'M104 -10L150 -10L134 8L150 27L104 27Z';
const FOLDS = 'M-126 20L-104 27L-104 20ZM126 20L104 27L104 20Z';
const PUFFS = [
  [-96, 26, 7],
  [-4, 31, 5.5],
  [94, 26, 7],
] as const;

const coins = (n: number) => Math.max(0, Math.min(SLOTS, Math.round(n / PER_COIN)));
// Face centre of the n-th coin from the bottom; with none left the ghost column runs down to the stand.
const top = (n: number) => (n > 0 ? BASE - (n - 1) * STEP : BASE + 9);
const whole = (n: number) => (n < 0 ? `−${Math.abs(Math.round(n))}` : String(Math.round(n)));

/**
 * McClusky's bankroll: one brass coin per 100 credits on a walnut stand, with a dashed ghost of the stack he started
 * with. 240x340 design px; set CSS width/height to scale it.
 */
export function CredibilityMeter({ credibility, start }: { credibility: number; start: number }) {
  const value = Number.isFinite(credibility) ? credibility : 0;
  const have = coins(value);
  const had = coins(start);
  const low = value < 300;
  const text = whole(value);
  return (
    <svg className="hud-cred" viewBox="0 0 240 340" width="240" height="340" role="img">
      <title>{`Credibility ${text} credits, started at ${whole(start)}${low ? '. Medium unreliable.' : ''}`}</title>
      <ellipse cx="122" cy="327" rx="104" ry="9" fill="var(--floor-shadow)" />
      <path d={STAND} fill="var(--wood)" />
      <path d={STAND_TOP} fill="var(--wood-light)" />
      <path d="M16 247.5L224 247" fill="none" stroke="var(--ink)" strokeWidth="3" strokeLinecap="round" />
      <path d={STAND} fill="none" stroke="var(--ink)" strokeWidth="4" strokeLinejoin="round" />
      <path d={WINDOW} fill="var(--paper)" stroke="var(--ink)" strokeWidth="3" strokeLinejoin="round" />
      <text
        key={text}
        className={`hud-cred__num${value < start ? ' is-down' : ''}`}
        x="120"
        y="283"
        textAnchor="middle"
        dominantBaseline="central"
      >
        {text}
      </text>
      {had > have && (
        <g
          key={`${have}-${had}`}
          className="hud-cred__ghost"
          transform="translate(120 0)"
          fill="none"
          stroke="var(--ink)"
          strokeOpacity="0.5"
          strokeWidth="2.5"
          strokeDasharray="8 6"
        >
          <path d={`M-50 ${top(have)}V${top(had)}M50 ${top(have)}V${top(had)}`} />
          <ellipse cy={top(had)} rx="50" ry="13" />
        </g>
      )}
      {JITTER.map((dx, i) => (
        <g key={i} className={`hud-coin${i < have ? ' is-on' : ''}`} transform={`translate(${120 + dx} ${BASE - i * STEP})`}>
          <g className="hud-coin__real" strokeLinejoin="round">
            <path d={BAND} fill="var(--brass-deep)" />
            <path d={RIM} fill="none" stroke="var(--ink)" strokeWidth="3.5" />
            <ellipse rx="50" ry="13" fill="var(--brass)" stroke="var(--ink)" strokeWidth="3.5" />
            <ellipse rx="34" ry="7.5" fill="none" stroke="var(--brass-deep)" strokeWidth="2.5" />
          </g>
        </g>
      ))}
      {low && (
        <g transform="translate(120 92)">
          <g className="hud-banner" strokeLinejoin="round">
            <path d={TAIL_L} fill="var(--crimson-deep)" stroke="var(--ink)" strokeWidth="3.5" />
            <path d={TAIL_R} fill="var(--crimson-deep)" stroke="var(--ink)" strokeWidth="3.5" />
            <path d={FOLDS} fill="var(--ink)" />
            <path d={RIBBON} fill="var(--crimson)" stroke="var(--ink)" strokeWidth="3.5" />
            <text
              className="hud-banner__word"
              y="-1"
              textAnchor="middle"
              dominantBaseline="central"
              textLength="226"
              lengthAdjust="spacingAndGlyphs"
            >
              MEDIUM UNRELIABLE
            </text>
            {PUFFS.map(([x, y, r]) => (
              <circle
                key={x}
                className="hud-puff"
                cx={x}
                cy={y}
                r={r}
                fill="var(--paper-deep)"
                stroke="var(--ink)"
                strokeWidth="1.6"
              />
            ))}
          </g>
        </g>
      )}
    </svg>
  );
}
