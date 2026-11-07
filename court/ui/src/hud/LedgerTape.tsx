import type { LedgerEvent } from '../contracts';
import './hud2.css';

// ok: this row's prev_hash is the hash of the row below. open: the chain runs on past the tape. none: genesis.
type Link = 'ok' | 'broken' | 'open' | 'none';

// A face-on link with its hole cut out (even-odd), inked a touch off true.
const RING =
  'M19.6 26C19.7 34.6 16.4 41.2 12 41.1C7.4 41 4.3 34.2 4.4 25.8C4.5 17.6 7.6 10.9 12.1 11C16.6 11.1 19.5 17.8 19.6 26Z' +
  'M15.9 26.2C15.9 31.4 14.2 35.1 12.1 35.1C9.9 35.1 8.2 31.3 8.2 26.1C8.2 20.9 10 17.2 12.2 17.3C14.3 17.4 15.9 21.1 15.9 26.2Z';
// The edge-on link between two rows is drawn as two halves, one per row, left open at the seam so they join unseen.
const HOOK = {
  up: {
    whole: 'M9 0V15Q9 19.4 12 19.4Q15 19.4 15 15V0',
    snapped: 'M9 7.5V15Q9 19.4 12 19.4Q15 19.4 15 15V7.5L13.6 5.6L12.2 8L10.6 5.4Z',
  },
  down: {
    whole: 'M9 52V37Q9 32.6 12 32.6Q15 32.6 15 37V52',
    snapped: 'M9 44.5V37Q9 32.6 12 32.6Q15 32.6 15 37V44.5L13.6 46.4L12.2 44L10.6 46.6Z',
  },
};

const PAPER = 'M2.5 2C90 1.2 250 2.8 337.5 1.8C338.6 60 337 140 338 198C250 199 90 197.6 2 198.6C3 140 1.6 60 2.5 2Z';
const HEAD = 'M7 3.2C120 2.4 240 3.8 353 3Q356.6 3.2 356.6 7V27Q356.6 31.4 352.4 31.4C240 32.2 120 30.8 7.4 31.6Q3.4 31.4 3.4 27.4V7Q3.4 3.4 7 3.2Z';
const ROLL = 'M12 2.4C120 1.6 240 3 348 2.2Q357 2.4 357 10.8Q357 19.4 348 19.4C240 20.2 120 18.8 12 19.6Q3 19.4 3 11Q3 2.6 12 2.4Z';

const pad = (n: number) => String(n).padStart(2, '0');
const isGenesis = (hash: string) => /^0*$/.test(hash);

// The court logs commits and verdicts by ref and locks by claim_id; a repair names the struck claim.
function subject(payload: unknown): string {
  if (typeof payload !== 'object' || payload === null) return '';
  const p = payload as Record<string, unknown>;
  const id = p.ref ?? p.claim_id ?? p.struck_id ?? p.id;
  return typeof id === 'string' ? id : '';
}

export function LedgerTape({ events, max = 6 }: { events: LedgerEvent[]; max?: number }) {
  const rows = [...events].sort((a, b) => b.seq - a.seq).slice(0, max);
  const below = (i: number): Link =>
    i + 1 < rows.length
      ? rows[i].prev_hash === rows[i + 1].hash ? 'ok' : 'broken'
      : isGenesis(rows[i].prev_hash) ? 'none' : 'open';

  return (
    <section className="hud-tape" aria-label="Ledger, newest entry first">
      <svg className="hud-tape__paper" viewBox="0 0 340 200" preserveAspectRatio="none" aria-hidden="true">
        <path d={PAPER} fill="var(--paper)" stroke="var(--ink)" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
      </svg>
      <ol className="hud-tape__feed">
        {rows.length === 0 && <li className="hud-tape__empty">awaiting the first commit</li>}
        {rows.map((ev, i) => (
          <li key={`${ev.seq}:${ev.hash}`} className="hud-tape__row">
            <div className="hud-tape__inner">
              <div className="hud-tape__entry">
                <Chain up={i === 0 ? 'open' : below(i - 1)} down={below(i)} />
                <p className="hud-tape__what">
                  <b>#{pad(ev.seq)}</b> {ev.type} {subject(ev.payload)}
                </p>
                <p className="hud-tape__hash">
                  sha256 <mark>{ev.hash.slice(0, 4)}</mark>…{ev.hash.slice(-4)}
                  <Arrow />
                  <mark>{ev.prev_hash.slice(0, 4)}</mark>…
                </p>
              </div>
            </div>
          </li>
        ))}
      </ol>
      <svg className="hud-tape__head" viewBox="0 0 360 34" preserveAspectRatio="none" aria-hidden="true">
        <path d={HEAD} fill="var(--brass)" />
        <path
          d="M3.4 23.6C120 24.2 240 23.2 356.6 23.8V27Q356.6 31.4 352.4 31.4C240 32.2 120 30.8 7.4 31.6Q3.4 31.4 3.4 27.4Z"
          fill="var(--brass-deep)"
        />
        <path d={HEAD} fill="none" stroke="var(--ink)" strokeWidth="3" vectorEffect="non-scaling-stroke" />
        <path
          d="M16 27.6H344"
          stroke="var(--ink)"
          strokeWidth="3"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <svg className="hud-tape__roll" viewBox="0 0 360 22" preserveAspectRatio="none" aria-hidden="true">
        <path d={ROLL} fill="var(--paper)" />
        <path
          d="M3.2 12.4C120 13.2 240 12 356.8 12.8Q356 19.4 348 19.4C240 20.2 120 18.8 12 19.6Q3.6 19.4 3.2 12.4Z"
          fill="var(--paper-deep)"
        />
        <path d={ROLL} fill="none" stroke="var(--ink)" strokeWidth="3" vectorEffect="non-scaling-stroke" />
        <path
          d="M18 7.6C120 7 240 8 342 7.4"
          fill="none"
          stroke="var(--ink)"
          strokeWidth="2"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      {/* Its own unstretched box, so the word keeps its shape and sits on an exact baseline in the brass face. */}
      <svg className="hud-tape__plate" viewBox="0 0 160 34" aria-hidden="true">
        <text x="80" y="20.5" textAnchor="middle">
          LEDGER
        </text>
      </svg>
    </section>
  );
}

function Chain({ up, down }: { up: Link; down: Link }) {
  const broken = up === 'broken' || down === 'broken';
  return (
    <svg
      className="hud-tape__chain"
      viewBox="0 0 24 52"
      role={broken ? 'img' : undefined}
      aria-label={broken ? 'chain broken here' : undefined}
      aria-hidden={broken ? undefined : true}
    >
      <path className="hud-tape__ring" d={RING} />
      {up !== 'none' && (
        <path className={`hud-tape__hook hud-tape__hook--${up}`} d={up === 'broken' ? HOOK.up.snapped : HOOK.up.whole} />
      )}
      {down !== 'none' && (
        <path
          className={`hud-tape__hook hud-tape__hook--${down}`}
          d={down === 'broken' ? HOOK.down.snapped : HOOK.down.whole}
        />
      )}
    </svg>
  );
}

// Drawn, because Courier Prime has no glyph for the left arrow.
function Arrow() {
  return (
    <svg className="hud-tape__arrow" viewBox="0 0 22 14" role="img" aria-label="chained to">
      <path d="M20 7.6C14.6 6.6 9 8 3.4 7M8.2 2.6L2.8 7.1L8.4 11.6" />
    </svg>
  );
}
