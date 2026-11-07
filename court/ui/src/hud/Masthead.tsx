import { useId } from 'react';
import type { CaseBundle } from '../contracts';
import './hud.css';

// Walnut sign board on a 600x72 grid, stretched to the plaque; each edge bows a little so it reads hand cut.
const BOARD =
  'M13 4.5Q300 2.4 587 4.3Q595.6 4.6 595.9 13Q597 36 595.7 59Q595.3 67.3 586.6 67.7Q300 69.8 13.6 67.6Q4.8 67.2 4.4 59Q3.1 36 4.6 13Q5 4.9 13 4.5Z';
const BEVEL = 'M13 4.5Q300 2.4 587 4.3Q595.6 4.6 595.9 13L596 16.5Q300 13.6 4.4 16.4L4.6 13Q5 4.9 13 4.5Z';
const INLAY =
  'M16 11.6Q300 10.2 584 11.4Q588.6 11.6 588.7 16L589 56Q588.8 60.4 584.4 60.6Q300 62 16.2 60.5Q11.6 60.3 11.5 56L11.3 16Q11.5 11.7 16 11.6Z';
// Luggage tag with clipped corners on its own 248x66 grid; the grommet sits in the clipped end.
const TAG = 'M34 4.6L240 3.8Q244.6 3.9 244.6 8.6L245.2 57.4Q245 62.2 240.2 62.3L34.2 61.6L6.4 44.6Q4.4 33 6.6 21.4Z';

function SourceBadge({ source, status }: { source: CaseBundle['source']; status?: string }) {
  const stripes = `hud-tag-${useId().replace(/[^\w-]/g, '')}`;
  const fixture = source === 'fixture';
  const live = !status || status === 'live';
  return (
    <div className={`hud-tag hud-tag--${fixture ? 'fixture' : 'live'}`} data-status={fixture ? undefined : status}>
      <svg className="hud-tag__bg" viewBox="0 0 248 66" aria-hidden="true">
        {fixture && (
          <defs>
            <pattern id={stripes} width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="5" height="12" fill="var(--paper-deep)" />
            </pattern>
          </defs>
        )}
        <path d={TAG} fill="var(--paper)" />
        {fixture && <path d={TAG} fill={`url(#${stripes})`} />}
        <path d={TAG} fill="none" stroke="var(--ink)" strokeWidth="3.5" strokeLinejoin="round" />
        <circle cx="24" cy="33" r="8.5" fill="var(--brass)" stroke="var(--ink)" strokeWidth="2.5" />
        <circle cx="24" cy="33" r="3.4" fill="var(--ink)" />
      </svg>
      {fixture ? (
        <p className="hud-tag__text">
          <b>fixture data</b>
          <span className="hud-sr"> · </span>
          <span>not measured today</span>
        </p>
      ) : (
        <p className="hud-tag__text">
          <span className="hud-tag__head">
            <svg className={`hud-tag__dot${live ? ' is-live' : ''}`} viewBox="0 0 20 20" aria-hidden="true">
              <circle cx="10" cy="10" r="7.5" />
            </svg>
            <b>{live ? 'LIVE' : status}</b>
          </span>
          <span>{source === 'atlas' ? 'MongoDB Atlas' : 'run files'}</span>
        </p>
      )}
    </div>
  );
}

/** Top-left of the rail: the walnut sign board and the data-source tag. About 870x84 design px, sized to its text. */
export function Masthead({ appLabel, source, status }: { appLabel: string; source: CaseBundle['source']; status?: string }) {
  return (
    <header className="hud-masthead">
      <div className="hud-plaque">
        <svg className="hud-plaque__bg" viewBox="0 0 600 72" preserveAspectRatio="none" aria-hidden="true">
          <path d={BOARD} fill="var(--wood)" />
          <path d={BEVEL} fill="var(--wood-light)" />
          <path d={INLAY} fill="none" stroke="var(--brass)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          <path
            d={BOARD}
            fill="none"
            stroke="var(--ink)"
            strokeWidth="4"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        <span className="hud-tack" aria-hidden="true" />
        <h1 className="hud-plaque__title">Muséance</h1>
        <span className="hud-plaque__rule" aria-hidden="true" />
        <p className="hud-plaque__case">
          Court of Fidelity · In re <span className="hud-plaque__app">{appLabel}</span>
        </p>
        <span className="hud-tack hud-tack--r" aria-hidden="true" />
      </div>
      <SourceBadge source={source} status={status} />
    </header>
  );
}
