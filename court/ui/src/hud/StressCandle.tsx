import { useId } from 'react';
import './hud.css';

// Drawn with the wick at 0,0 so the lean, the flicker and the snuff all pivot where a flame does.
const FLAME = 'M0 2C-12 1 -15 -13 -9 -25C-5 -34 -1 -44 1 -56C6 -44 14 -33 13 -18C12 -6 7 1 0 2Z';
const CORE = 'M0 -1C-6 -2 -7 -10 -4 -17C-2 -22 0 -27 1 -32C4 -25 7 -18 6 -10C5 -4 3 -1 0 -1Z';
const WISPS = ['M0 -6C-9 -18 8 -28 0 -40S-11 -62 2 -76', 'M3 -8C11 -20 -6 -32 4 -46S13 -64 -1 -82'];
const CANDLE = 'M62 246V136Q63 129 70 128Q76 131 80 128Q86 125 92 129Q98 130 98 137V246Z';
const CANDLE_SHADE = 'M88 131Q93 127.5 97.4 133V246H88Z';
// The drip's top is left unstroked so the wax runs over the rim line instead of hanging below it.
const DRIP_EDGE = 'M-3.6 0Q-3.6 17 0 24Q3.6 17 3.6 0';
const DRIP = `${DRIP_EDGE}L3.6 -4H-3.6Z`;
const SOCKET = 'M54 247Q80 243 106 247L104 264Q80 268 56 264Z';
const SOCKET_SHADE = 'M94 245.5Q101 246 106 247L104 264Q99 265.4 93 266Z';
const DISH_SIDE = 'M14 268V276A66 14 0 0 0 146 276V268A66 14 0 0 1 14 268Z';

type Level = 'calm' | 'uneasy' | 'panic' | 'out';
const levelOf = (s: number): Level => (s >= 0.95 ? 'out' : s >= 0.7 ? 'panic' : s >= 0.35 ? 'uneasy' : 'calm');

/** McClusky's stress as a chamberstick candle: the flame grows, leans and gutters, and at 0.95 it goes out. 160x300 design px. */
export function StressCandle({ stress }: { stress: number }) {
  const glow = `hud-glow-${useId().replace(/[^\w-]/g, '')}`;
  const s = Number.isFinite(stress) ? Math.min(1, Math.max(0, stress)) : 0;
  const level = levelOf(s);
  const lean = { transform: `rotate(${(-26 * s).toFixed(1)}deg) scale(${(0.78 + 0.62 * s).toFixed(3)})` };
  const drip = (k: number) => ({ transform: `scaleY(${(0.35 + k * s).toFixed(3)})` });
  return (
    <svg className="hud-candle" data-level={level} viewBox="0 0 160 300" width="160" height="300" role="img">
      <title>{level === 'out' ? 'Stress: the candle is out' : `Stress ${Math.round(s * 100)} percent`}</title>
      <defs>
        <radialGradient id={glow}>
          <stop offset="0" stopColor="var(--flame-core)" stopOpacity="0.85" />
          <stop offset="0.4" stopColor="var(--flame)" stopOpacity="0.35" />
          <stop offset="1" stopColor="var(--flame)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="80" cy="286" rx="66" ry="9" fill="var(--floor-shadow)" />
      <g strokeLinejoin="round" strokeLinecap="round">
        <circle cx="139" cy="257" r="11" fill="none" stroke="var(--ink)" strokeWidth="10" />
        <circle cx="139" cy="257" r="11" fill="none" stroke="var(--brass)" strokeWidth="4.5" />
        <path d={DISH_SIDE} fill="var(--brass-deep)" stroke="var(--ink)" strokeWidth="3.5" />
        <ellipse cx="80" cy="268" rx="66" ry="14" fill="var(--brass)" stroke="var(--ink)" strokeWidth="3.5" />
        <ellipse cx="80" cy="266" rx="46" ry="8.5" fill="var(--brass-deep)" />
        <path d={CANDLE} fill="var(--wax)" />
        <path d={CANDLE_SHADE} fill="var(--paper-deep)" />
        <path d={CANDLE} fill="none" stroke="var(--ink)" strokeWidth="4" />
        <g transform="translate(69 131)">
          <g className="hud-drip" style={drip(1.1)}>
            <path d={DRIP} fill="var(--wax)" />
            <path d={DRIP_EDGE} fill="none" stroke="var(--ink)" strokeWidth="2.5" />
          </g>
        </g>
        <g transform="translate(92 132)">
          <g className="hud-drip" style={drip(0.7)}>
            <path d={DRIP} fill="var(--paper-deep)" />
            <path d={DRIP_EDGE} fill="none" stroke="var(--ink)" strokeWidth="2.5" />
          </g>
        </g>
        <path d={SOCKET} fill="var(--brass)" />
        <path d={SOCKET_SHADE} fill="var(--brass-deep)" />
        <path d={SOCKET} fill="none" stroke="var(--ink)" strokeWidth="3.5" />
        <path d="M80 129Q78.6 123 81 117" fill="none" stroke="var(--ink)" strokeWidth="3" />
      </g>
      <g transform="translate(80 118)">
        <g className="hud-flame-light">
          <g className="hud-flame-lean" style={lean}>
            <circle className="hud-flame-glow" cy="-24" r="58" fill={`url(#${glow})`} />
            <g className="hud-flame-flicker" strokeLinejoin="round">
              <path d={FLAME} fill="var(--flame)" stroke="var(--ink)" strokeWidth="3" />
              <path d={CORE} fill="var(--flame-core)" />
            </g>
          </g>
        </g>
        <circle className="hud-ember" cx="1" cy="-1" r="3" fill="var(--flame)" />
        <g className="hud-smoke" fill="none" stroke="var(--smoke)" strokeLinecap="round">
          <path d={WISPS[0]} pathLength="1" strokeWidth="4.5" />
          <path d={WISPS[1]} pathLength="1" strokeWidth="3" />
        </g>
      </g>
    </svg>
  );
}
