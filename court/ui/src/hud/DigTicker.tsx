import { useId, type ReactNode } from 'react';
import type { Evidence, Tier } from '../contracts';
import './hud2.css';

// Newest tags kept mounted; older ones have already been pushed out of the frame.
const SHOWN = 6;

const DISC =
  'M18 3.2C26.6 3 33 9.6 32.8 18.2C32.6 26.8 26.2 33 17.6 32.8C9.2 32.6 3 26.4 3.2 17.8C3.4 9.4 9.8 3.4 18 3.2Z';
// An evidence tag, corners clipped at the tied end, stretched to the slip.
const TAG =
  'M17 2.4C120 1.6 300 3.2 408 2.2Q413.6 2.4 413.6 8C414.2 26 413 44 413.8 58Q413.6 63.8 408 63.6C300 64.6 120 62.8 17 64L2.6 50.8C2.2 38 3 27 2.4 15.4Z';

const FRAME =
  'M4.5 6.3C12 5.7 20.2 6.1 27.7 5.9Q28.9 5.9 28.9 7.2C29.1 13 28.7 19.4 29 25.1Q29 26.5 27.6 26.5C20 26.8 12 26.3 4.7 26.6Q3.3 26.6 3.3 25.2C3.1 19.3 3.5 13.2 3.2 7.6Q3.2 6.3 4.5 6.3Z';
const SHEET = 'M7.4 3.6L19.8 3.3L26.4 9.9L26.1 28.4Q26.1 28.9 25.6 28.9L7.6 29.1Q7 29.1 7 28.5L6.8 4.2Q6.8 3.6 7.4 3.6Z';
const BUBBLE =
  'M6.8 4.8C13 4.2 19.6 4.5 25.6 4.6Q28.6 4.7 28.6 7.6C28.8 11.4 28.6 15 28.7 18.6Q28.7 21.4 25.8 21.4C20 21.7 15 21.3 12.2 21.5L6.6 27.4L7.6 21.5Q3.4 21.6 3.4 18.6C3.2 15 3.5 11 3.3 7.6Q3.3 4.9 6.8 4.8Z';
const HILLS =
  'M3.4 22.6C6.8 18.4 9.6 15.2 12.4 15.4C14.6 15.5 16 18 17.8 19.6C19.4 17.6 21.2 16.4 23 16.6C25.2 16.8 27.2 19 28.9 21.2';

// One ink weight across the set; each kind gets a single accent from the set's palette.
const KIND: Record<Evidence['kind'], ReactNode> = {
  page: (
    <>
      <path d={FRAME} fill="var(--paper)" />
      <path d="M4.5 6.3C12 5.7 20.2 6.1 27.7 5.9Q28.9 5.9 28.9 7.2V11.5C20 11.2 12 11.7 3.3 11.4L3.2 7.6Q3.2 6.3 4.5 6.3Z" fill="var(--wall)" />
      <path className="hud-kind__ink" d={`${FRAME}M3.5 11.4C12 11.1 20 11.7 28.8 11.4M8.2 16.6H23.4M8.2 21.4H18.6`} />
    </>
  ),
  screenshot: (
    <>
      <path d={FRAME} fill="var(--paper)" />
      <path d={`${HILLS}L29 25.1Q29 26.5 27.6 26.5C20 26.8 12 26.3 4.7 26.6Q3.3 26.6 3.3 25.2Z`} fill="var(--wall)" />
      <circle cx="21.8" cy="11.4" r="2.7" fill="var(--flame)" />
      <path className="hud-kind__ink" d={`${FRAME}${HILLS}M24.5 11.4A2.7 2.7 0 1 1 19.1 11.4A2.7 2.7 0 1 1 24.5 11.4Z`} />
    </>
  ),
  video: (
    <>
      <path d={FRAME} fill="var(--paper)" />
      <path d="M13.4 12.2L20 16.2L13.5 20.1Z" fill="var(--terracotta)" />
      <path className="hud-kind__ink" d={`${FRAME}M13.4 12.2L20 16.2L13.5 20.1Z`} />
      <path className="hud-kind__ink" d="M6.4 9.4H26.4M6.4 23H26.4" strokeDasharray="2 2.8" />
    </>
  ),
  issue: (
    <>
      <path d={BUBBLE} fill="var(--paper)" />
      <path className="hud-kind__ink" d={`${BUBBLE}M16.1 8.8L15.9 14.2M15.9 17.6V17.7`} />
    </>
  ),
  doc: (
    <>
      <path d={SHEET} fill="var(--paper)" />
      <path d="M19.8 3.3L19.9 9.6Q19.9 10 20.3 10L26.4 9.9Z" fill="var(--paper-deep)" />
      <path className="hud-kind__ink" d={`${SHEET}M19.8 3.3L19.9 9.6Q19.9 10 20.3 10L26.4 9.9M11 15.2H22.2M11 19.6H22.6M11 24H18.2`} />
    </>
  ),
};

const svgId = (raw: string) => raw.replace(/[^\w-]/g, '');

// total: the whole evidence pile, so the count reads 'N of M exhumed'.
export function DigTicker({ items, total }: { items: Evidence[]; total: number }) {
  const n = items.length;
  const from = Math.max(0, n - SHOWN);
  return (
    <section className="hud-dig" aria-label="Evidence pile, newest first">
      <Soil />
      <p className="hud-dig__count">
        <span key={n} className="hud-dig__num">
          {n}
        </span>
        <span className="hud-dig__unit">of {total} exhumed</span>
      </p>
      <ol className="hud-dig__list">
        {items
          .slice(from)
          .map((ev, i) => (
            <li key={`${from + i}:${ev.id}`} className="hud-dig__row">
              <div className="hud-dig__inner">
                <div className="hud-dig__tag">
                  <svg className="hud-dig__edge" viewBox="0 0 416 66" preserveAspectRatio="none" aria-hidden="true">
                    <path
                      d={TAG}
                      fill="var(--paper)"
                      stroke="var(--ink)"
                      strokeWidth="2.5"
                      strokeLinejoin="round"
                      vectorEffect="non-scaling-stroke"
                    />
                  </svg>
                  <TierBadge tier={ev.tier} />
                  <p className="hud-dig__source">
                    <svg className="hud-kind" viewBox="0 0 32 32" role="img" aria-label={ev.kind}>
                      {KIND[ev.kind]}
                    </svg>
                    <span>{ev.source}</span>
                  </p>
                  <p className="hud-dig__excerpt">{ev.text ?? ev.path ?? ''}</p>
                </div>
              </div>
            </li>
          ))
          .reverse()}
      </ol>
    </section>
  );
}

function TierBadge({ tier }: { tier: Tier }) {
  const stripes = `hud-stripes-${svgId(useId())}`;
  return (
    <svg className={`hud-tier hud-tier--${tier.toLowerCase()}`} viewBox="0 0 36 36" role="img" aria-label={`Tier ${tier}`}>
      {tier === 'C' && (
        <pattern id={stripes} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="var(--paper)" />
          <rect width="2.6" height="6" fill="var(--ink)" />
        </pattern>
      )}
      <path className="hud-tier__disc" d={DISC} fill={tier === 'C' ? `url(#${stripes})` : undefined} />
      <text className="hud-tier__letter" x="18" y="18.5">
        {tier}
      </text>
    </svg>
  );
}

// Flat pebbles in the dirt, no outlines: the ground stays quiet behind the tags.
function Soil() {
  const id = `hud-soil-${svgId(useId())}`;
  return (
    <svg className="hud-dig__soil" aria-hidden="true">
      <pattern id={id} width="72" height="64" patternUnits="userSpaceOnUse">
        <path
          d="M8 10q3-2 5 0t-1 3q-3 1-4-3zM40 6q2-1.5 4 0t-1 2.4q-2.4.6-3-2.4zM58 30q3-2 6 0t-1 3.4q-4 1-5-3.4zM20 44q2.4-1.6 4.6 0t-.8 2.8q-3 .8-3.8-2.8zM48 54q2-1.4 3.8 0t-.6 2.2q-2.6.6-3.2-2.2z"
          fill="var(--wood)"
        />
        <path d="M28 22q1.6-1.2 3.2 0t-.6 2q-2 .4-2.6-2zM66 50q1.4-1 2.8 0t-.4 1.8q-1.8.4-2.4-1.8zM4 30q1.4-1 2.8 0t-.4 1.8q-1.8.4-2.4-1.8z" fill="var(--wood-light)" />
      </pattern>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
    </svg>
  );
}
