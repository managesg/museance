import { useId, type CSSProperties } from 'react';
import type { CaseFile, LockStatus, Tier } from '../contracts';
import type { CardView, LeaderRow, StageState } from '../engine/types';
import { Leaderboard } from '../bets/Leaderboard';
import './sentence.css';

type Group = 'struck' | 'locked' | 'fabricated' | 'unsworn';
type Seg = readonly [cls: string, text: string];
interface Line { tone?: Group; segs: Seg[] }
interface Entry { id?: string; tier?: Tier; text?: string; note?: string }

// The struck list leads: it is what a reviewer reads first.
const GROUPS: readonly (readonly [Group, LockStatus])[] = [
  ['struck', 'STRUCK'],
  ['locked', 'LOCKED'],
  ['fabricated', 'FABRICATED'],
  ['unsworn', 'UNSWORN'],
];

const DASH = '—';
const TYPE_START_MS = 420;
const TYPE_BUDGET_MS = 2000; // the record types out in about this long however many lines it has

const PAPER =
  'M16 8C300 3 700 11 1100 5C1230 3 1330 8 1384 7Q1394 8 1393 19C1397 300 1391 700 1395 980Q1394 993 1382 992C1100 997 700 990 300 995C160 996 60 992 17 994Q7 993 7 982C3 700 9 300 5 19Q6 8 16 8Z';
const SLIP =
  'M15 6C140 3 330 9 486 5Q495 6 495 16C498 200 493 430 496 624Q495 634 485 634C330 637 150 632 16 635Q6 634 6 624C3 430 8 200 4 17Q5 6 15 6Z';
const FRAME_OUT =
  'M24 10C120 8 280 12 376 9C385 9.5 390.5 15 390 24C391.5 100 389 200 390.8 276C390.5 285 385 290.5 376 290C280 292 120 289 24 291C15 290.5 9.5 285 9.8 276C8.6 200 10.8 100 9.2 24C9.5 15 15 10 24 10Z';
const FRAME_IN =
  'M36 23C130 21.5 270 24.5 364 22.5C372 23 377 28 376.5 36C377.6 110 375.8 190 377 264C376.6 272 372 277 364 276.8C270 278.4 130 276 36 277.4C28 277 23 272.4 23.4 264C22.4 190 24.4 110 23 36C23.3 28 28 23 36 23Z';
// [left %, drift x, drift y]
const PUFFS = [
  [4, -16, 6],
  [22, -8, 12],
  [50, 0, 14],
  [76, 8, 12],
  [94, 16, 6],
] as const;

const describe = ({ claim }: CardView) => `${claim.screen}: ${claim.text}`;
const toEntry = (card: CardView): Entry => ({
  id: card.claim.id,
  tier: card.claim.tier,
  text: describe(card),
  note: card.repairedFrom && `repairs ${card.repairedFrom}`,
});

const isLock = (s: CardView['status']): s is LockStatus => GROUPS.some(([, status]) => status === s);

// eval/case_file.py writes each entry as "screen: text [tier]"; matching it back to its card recovers the claim id.
function caseEntries(lines: string[], cards: CardView[]): Entry[] {
  return lines.map((line) => {
    const card = cards.find((c) => line === c.claim.id || line === `${describe(c)} [${c.claim.tier}]`);
    return card ? toEntry(card) : { text: line };
  });
}

function cardEntries(cards: CardView[], status: LockStatus): Entry[] {
  const own = cards.filter((c) => c.status === status).map(toEntry);
  if (status === 'STRUCK') {
    // A repair takes over its struck card on stage, but the strike still stands in the record.
    const onStage = new Set(cards.map((c) => c.claim.id));
    const replaced = cards.flatMap((c) =>
      c.repairedFrom && !onStage.has(c.repairedFrom) ? [{ id: c.repairedFrom, note: `repaired as ${c.claim.id}` }] : [],
    );
    return [...own, ...replaced];
  }
  // A claim with no ruling at sentencing is unsworn, as eval/score.py counts it.
  if (status === 'UNSWORN') return [...own, ...cards.filter((c) => !isLock(c.status)).map((c) => ({ ...toEntry(c), note: 'no ruling' }))];
  return own;
}

const keyLine = (key: string, value: string, tone?: Group): Line => ({ tone, segs: [['sn__k', `${key}: `], ['', value]] });

// JSON strings are valid YAML scalars, the same quoting the case file itself uses.
function entryLine({ id, tier, text, note }: Entry, tone: Group): Line {
  const segs: Seg[] = [['', '  - ']];
  if (id) segs.push(['sn__id', text === undefined ? id : `${id}: `]);
  if (text !== undefined) segs.push(['', JSON.stringify(tier ? `[${tier}] ${text}` : text)]);
  if (note) segs.push(['sn__note', `  # ${note}`]);
  return { tone, segs };
}

const chars = (line: Line) => line.segs.reduce((n, [, text]) => n + text.length, 0);
const signed = (d: number) => `${d > 0 ? '+' : d < 0 ? '−' : '±'}${Math.abs(d)}`;

/** The sentencing overlay: the case file typed onto a court record over the dimmed stage, then the gallery's top three. */
export function SentenceScreen({
  state,
  caseFile,
  leaderboard,
}: {
  state: StageState;
  caseFile: CaseFile | null;
  leaderboard: LeaderRow[];
}) {
  const titleId = useId();
  const galleryId = useId();
  const { cards } = state;
  // state.scores already takes the case file's numbers once every claim is ruled, and re-measures after repairs
  // and bench runs, so the sheet agrees with the numbers bar and the clerk's subtitle.
  const { fidelity, brier, credibilityStart: start, credibility: end } = state.scores;
  const groups = GROUPS.map(([key, status]) => ({
    key,
    list: caseFile ? caseEntries(caseFile[key], cards) : cardEntries(cards, status),
  }));
  const unsworn = groups.find((g) => g.key === 'unsworn')?.list.length ?? 0;

  const lines: Line[] = [
    keyLine('case', JSON.stringify(caseFile?.app ?? state.app)),
    keyLine('fidelity', fidelity === null ? DASH : String(fidelity)),
    ...(unsworn ? [keyLine('status', `UNSWORN (${unsworn})`, 'unsworn')] : []),
    ...groups.flatMap(({ key, list }) => [
      { tone: key, segs: [['sn__k', list.length ? `${key}:` : `${key}: []`]] } satisfies Line,
      ...list.map((e) => entryLine(e, key)),
    ]),
  ];
  const per = Math.min(9, TYPE_BUDGET_MS / Math.max(1, lines.reduce((sum, l) => sum + chars(l), 0)));
  let at = TYPE_START_MS;
  const typed = lines.map((line) => {
    const c = chars(line);
    const start = at;
    at += c * per + 40;
    return { line, c, start, ms: c * per };
  });

  const delta = end - start;
  const fid = fidelity === null ? DASH : String(fidelity);
  const podium = [...leaderboard].sort((a, b) => b.credits - a.credits).slice(0, 3);

  return (
    <section
      className={podium.length ? 'sn' : 'sn sn--solo'}
      aria-labelledby={titleId}
      style={{ '--done': `${Math.round(at)}ms` } as CSSProperties}
    >
      <article className="sn__record">
        <svg className="sn__paper" viewBox="0 0 1400 1000" preserveAspectRatio="none" aria-hidden="true">
          <path d={PAPER} />
        </svg>
        <header className="sn__head">
          <h2 id={titleId} className="sn__title">
            In the matter of {state.appLabel}
          </h2>
          <span className="sn__source">source: {state.source}</span>
        </header>
        <div className="sn__body">
          <ol className="sn__yaml" style={{ '--rows': lines.length } as CSSProperties}>
            {typed.map(({ line, c, start, ms }, i) => (
              <li key={i} className={line.tone ? `sn__ln sn__ln--${line.tone}` : 'sn__ln'}>
                <span
                  className="sn__typed"
                  style={{ '--n': c, '--t': `${Math.round(start)}ms`, '--d': `${Math.round(ms)}ms` } as CSSProperties}
                >
                  {line.segs.map(([cls, text], j) => (cls ? <span key={j} className={cls}>{text}</span> : text))}
                </span>
              </li>
            ))}
          </ol>
          <div className="sn__findings">
            <div
              className="sn__stamp"
              role="img"
              aria-label={fidelity === null ? 'Fidelity not measured' : `Fidelity ${fid} percent`}
            >
              <svg className="sn__frame" viewBox="0 0 400 300" preserveAspectRatio="none" aria-hidden="true">
                <path d={FRAME_OUT} strokeWidth={7} />
                <path d={FRAME_IN} strokeWidth={2.5} />
              </svg>
              <span className={fid.length > 2 ? 'sn__fid sn__fid--wide' : 'sn__fid'}>
                {fid}
                {fidelity !== null && <span className="sn__pct">%</span>}
              </span>
              <span className="sn__fid-word">FIDELITY</span>
              {PUFFS.map(([x, dx, dy]) => (
                <i
                  key={x}
                  className="sn__puff"
                  style={{ left: `${x}%`, '--dx': `${dx}px`, '--dy': `${dy}px` } as CSSProperties}
                />
              ))}
            </div>
            <dl className="sn__figs">
              <div className="sn__fig">
                <dt>Credibility</dt>
                <dd>
                  <span className="sn__num">{start}</span>
                  <svg className="sn__arrow" viewBox="0 0 36 22" role="img" aria-label="to">
                    <path d="M2.5 11.8C11 10.4 20 12.6 31 11M23.5 4.6L32.5 11L23.8 17.6" />
                  </svg>
                  <span className="sn__num">{end}</span>
                  <span className={`sn__delta sn__delta--${delta < 0 ? 'down' : delta > 0 ? 'up' : 'flat'}`}>
                    {signed(delta)}
                  </span>
                </dd>
              </div>
              <div className="sn__fig">
                <dt>Brier</dt>
                <dd>
                  <span className="sn__num">{brier === null ? DASH : brier.toFixed(3)}</span>
                  <span className="sn__gloss">0 is perfect calibration</span>
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </article>

      {podium.length > 0 && (
        <aside className="sn__gallery" aria-labelledby={galleryId}>
          <svg className="sn__slip" viewBox="0 0 500 640" preserveAspectRatio="none" aria-hidden="true">
            <path d={SLIP} />
          </svg>
          <svg className="sn__tack" viewBox="0 0 40 40" aria-hidden="true">
            <path d="M20 5C29 5 35 11 35 20C35 29 28.6 35 20 35C11 35 5 28.6 5 20C5 11.5 11 5 20 5Z" fill="var(--brass-deep)" />
            <path d="M18.5 7.5C26 7.5 31 12.5 31 19.5C31 26 26 30.5 19.5 30.5C12.5 30.5 7.5 25.5 7.5 18.6C7.5 12 12 7.5 18.5 7.5Z" fill="var(--brass)" />
            <path d="M20 5C29 5 35 11 35 20C35 29 28.6 35 20 35C11 35 5 28.6 5 20C5 11.5 11 5 20 5Z" fill="none" stroke="var(--ink)" strokeWidth={3} />
          </svg>
          <h3 id={galleryId} className="sn__gallery-title">
            Top of the gallery
          </h3>
          <Leaderboard rows={podium} />
          <p className="sn__prize">a real pastry for the top three</p>
        </aside>
      )}

      <p className="sn__closing">He’s not a good medium. He’s a measurable one.</p>
    </section>
  );
}
