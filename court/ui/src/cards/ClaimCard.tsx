import { useId } from 'react';
import type { Claim, LockStatus, Tier } from '../contracts';
import type { CardStatus, CardView } from '../engine/types';
import { stepLabel } from './keys';
import { Stamp, WaxSeal } from './Stamp';
import './cards.css';

const TIER_NOTE: Record<Tier, string> = {
  A: 'archived build',
  B: 'on record',
  C: 'testimony only',
  D: 'silence',
};

const STATUS_WORD: Record<CardStatus, string> = {
  sealed: 'sealed',
  sworn: 'sworn',
  'under-cross': 'under cross-examination',
  LOCKED: 'sworn and locked',
  STRUCK: 'struck for perjury',
  UNSWORN: 'unsworn, the test was flaky',
  FABRICATED: 'fabricated',
};

// The card edge, drawn a touch off true in a 2:3 box.
const EDGE =
  'M14 3.5C60 2.2 120 4.6 186 3Q197 3.4 197.2 14C198.6 90 196.4 200 197.6 286Q197 296.8 186 296.6C130 298 70 295.8 14 297Q3 296.6 2.8 286C1.6 210 3.8 100 2.4 14Q3 3.6 14 3.5Z';
const DISC =
  'M18 3.2C26.6 3 33 9.6 32.8 18.2C32.6 26.8 26.2 33 17.6 32.8C9.2 32.6 3 26.4 3.2 17.8C3.4 9.4 9.8 3.4 18 3.2Z';
const STAR = 'M0-9Q1.6-1.6 9 0Q1.6 1.6 0 9Q-1.6 1.6-9 0Q-1.6-1.6 0-9Z';

type ChipTone = 'brass' | 'true' | 'false';
const CHIP: Record<ChipTone, readonly [face: string, side: string]> = {
  brass: ['var(--brass)', 'var(--brass-deep)'],
  true: ['var(--wall)', 'var(--wall-deep)'],
  false: ['var(--crimson)', 'var(--crimson-deep)'],
};
const JITTER = [0, 0.9, -0.7, 0.5, -0.9, 0.4];
const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 });

const isLock = (s: CardStatus): s is LockStatus => s !== 'sealed' && s !== 'sworn' && s !== 'under-cross';
const pct = (c: number) => `${Math.round(c * 100)}%`;
const bondChips = (bond: number) => Math.min(5, Math.max(1, Math.round(bond / 50)));
const betChips = (credits: number) => (credits > 0 ? Math.min(4, Math.max(1, Math.round(credits / 50))) : 0);
const svgId = (raw: string) => raw.replace(/[^\w-]/g, '');

export function ClaimCard({ view, size }: { view: CardView; size: 'small' | 'focus' }) {
  const { claim, status } = view;
  const sealed = status === 'sealed';
  const lock = isLock(status) ? status : null;
  return (
    <article
      className={`cc cc--${size}`}
      data-status={status}
      aria-label={`Claim ${claim.id}, ${claim.screen}, ${STATUS_WORD[status]}`}
    >
      <div className="cc__shadow" aria-hidden="true" />
      <div className="cc__lift">
        <div className="cc__flip" data-face={sealed ? 'back' : 'front'}>
          <div className="cc__face cc__face--front" aria-hidden={sealed || undefined}>
            <svg className="cc__edge" viewBox="0 0 200 300" aria-hidden="true">
              <path
                d={EDGE}
                fill="var(--paper)"
                stroke="var(--ink)"
                strokeWidth="3.5"
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
            <Corners />
            {size === 'focus' ? <FocusFront view={view} /> : <SmallFront claim={claim} />}
          </div>
          <div className="cc__face cc__face--back" aria-hidden={!sealed || undefined}>
            <Back commit={claim.commit} />
          </div>
        </div>
        {lock && (
          <div className={`cc__stamp cc__stamp--${lock === 'LOCKED' ? 'seal' : 'ink'}`}>
            <Stamp status={lock} />
          </div>
        )}
      </div>
      {size === 'small' && <Bets bets={view.bets} />}
    </article>
  );
}

function FocusFront({ view }: { view: CardView }) {
  const { claim } = view;
  return (
    <div className="cc__body">
      <header className="cc__title">
        <div className="cc__head">
          <span className="cc__no">CLAIM No. {claim.id}</span>
          <TierBadge tier={claim.tier} />
        </div>
        <div className="cc__head">
          <span className="cc__screen">{claim.screen}</span>
          <span className={`cc__label cc__label--${claim.label.toLowerCase()}`}>{claim.label}</span>
        </div>
      </header>
      <p className="cc__text">{claim.text}</p>
      <div className="cc__test">
        {claim.test.steps.map((step, i) => (
          <kbd key={i} className="cc__key">
            {stepLabel(step)}
          </kbd>
        ))}
        <Arrow />
        <output className="cc__expect">{claim.test.expect}</output>
      </div>
      <dl className="cc__docket">
        <dt>EVIDENCE</dt>
        <dd className="cc__ids">{claim.evidence?.length ? claim.evidence.join(', ') : 'none'}</dd>
        <dt>ORACLE</dt>
        <dd>{claim.tier === 'A' ? 'yes' : 'no'}</dd>
        <dt className="cc__alarm">IF FALSE</dt>
        <dd>{guyName(claim.screen)} glitches</dd>
        {view.repairedFrom && (
          <>
            <dt>REPAIRS</dt>
            <dd className="cc__ids">{view.repairedFrom}</dd>
          </>
        )}
      </dl>
      <div className="cc__stakes">
        <div className="cc__stake">
          <span className="cc__bond">
            <Chips n={bondChips(claim.bond)} tone="brass" />
            <span className="cc__num">{claim.bond}</span>
          </span>
          <span className="cc__cap">BOND</span>
        </div>
        <div className="cc__stake cc__stake--conf">
          <span className="cc__conf">{pct(claim.confidence)}</span>
          <span className="cc__cap">CONFIDENCE</span>
        </div>
      </div>
    </div>
  );
}

// Each little guy goes by its screen's name: "divide" -> "Divide".
function guyName(screen: string) {
  const name = screen.replace(/[-_]+/g, ' ').trim();
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function SmallFront({ claim }: { claim: Claim }) {
  return (
    <div className="cc__body">
      <div className="cc__head">
        <span className="cc__no">{claim.id}</span>
        <TierBadge tier={claim.tier} />
      </div>
      <span className="cc__screen">{claim.screen}</span>
      <span className="cc__conf">{pct(claim.confidence)}</span>
      <span className="cc__bond">
        <Chips n={bondChips(claim.bond)} tone="brass" />
        <span className="cc__num">{claim.bond}</span>
      </span>
    </div>
  );
}

function Back({ commit }: { commit?: string }) {
  const lattice = `cc-lattice-${svgId(useId())}`;
  const hex = commit?.replace(/^sha256:/i, '').slice(0, 8);
  return (
    <>
      <svg className="cc__edge" viewBox="0 0 200 300" aria-hidden="true">
        <pattern
          id={lattice}
          width="14"
          height="14"
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45 100 150)"
        >
          <path d="M0 0H14M0 0V14" fill="none" stroke="var(--wall)" strokeWidth="1.4" />
        </pattern>
        <path d={EDGE} fill="var(--wall-deep)" />
        <path
          d={EDGE}
          fill={`url(#${lattice})`}
          stroke="var(--ink)"
          strokeWidth="3.5"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <Corners />
      <div className="cc__seal">
        <WaxSeal tone="crimson" stretch className="cc__wax" />
        <span className={hex ? 'cc__hex' : 'cc__hex cc__hex--none'}>{hex || 'unsealed'}</span>
      </div>
    </>
  );
}

function TierBadge({ tier }: { tier: Tier }) {
  const stripes = `cc-stripes-${svgId(useId())}`;
  return (
    <svg
      className={`cc__tier cc__tier--${tier.toLowerCase()}`}
      viewBox="0 0 36 36"
      role="img"
      aria-label={`Tier ${tier}, ${TIER_NOTE[tier]}`}
    >
      {tier === 'C' && (
        <pattern id={stripes} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" fill="var(--paper)" />
          <rect width="2.6" height="6" fill="var(--ink)" />
        </pattern>
      )}
      <path className="cc__disc" d={DISC} fill={tier === 'C' ? `url(#${stripes})` : undefined} />
      <text className="cc__tier-letter" x="18" y="18.5">
        {tier}
      </text>
    </svg>
  );
}

function Corners() {
  return (
    <>
      {(['tl', 'tr', 'bl', 'br'] as const).map((corner) => (
        <svg key={corner} className={`cc__orn cc__orn--${corner}`} viewBox="-10 -10 20 20" aria-hidden="true">
          <path d={STAR} />
        </svg>
      ))}
    </>
  );
}

function Chips({ n, tone, mark }: { n: number; tone: ChipTone; mark?: 'check' | 'cross' }) {
  const count = Math.max(1, n);
  const h = 16 + count * 4;
  const [face, side] = CHIP[tone];
  const topX = 15 + JITTER[(count - 1) % JITTER.length];
  const topY = h - 9.5 - (count - 1) * 4;
  return (
    <svg
      className={n ? 'cc__chips' : 'cc__chips cc__chips--empty'}
      viewBox={`0 0 30 ${h}`}
      style={{ aspectRatio: `30 / ${h}` }}
      aria-hidden="true"
    >
      {Array.from({ length: count }, (_, i) => {
        const y = h - 9.5 - i * 4;
        return (
          <g key={i} transform={`translate(${JITTER[i % JITTER.length]} 0)`}>
            <path d={`M2 ${y}v4a13 5.5 0 0 0 26 0v-4Z`} fill={side} />
            <path
              d={`M7 ${y + 4.6}v3.4M15 ${y + 5.8}v3.4M23 ${y + 4.6}v3.4`}
              stroke="var(--paper)"
              strokeWidth="2.2"
            />
            <path d={`M2 ${y}v4a13 5.5 0 0 0 26 0v-4`} fill="none" stroke="var(--ink)" strokeWidth="1.5" />
            <ellipse cx="15" cy={y} rx="13" ry="5.5" fill={face} stroke="var(--ink)" strokeWidth="1.5" />
          </g>
        );
      })}
      {mark && n > 0 && (
        <path
          d={
            mark === 'check'
              ? `M${topX - 5} ${topY}l3.4 2.6 6.6-4.8`
              : `M${topX - 4} ${topY - 2.6}l8 5.2M${topX + 4} ${topY - 2.6}l-8 5.2`
          }
          fill="none"
          stroke="var(--paper)"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
    </svg>
  );
}

function Bets({ bets }: { bets: CardView['bets'] }) {
  const { trueCredits, falseCredits } = bets;
  if (trueCredits <= 0 && falseCredits <= 0) return null;
  return (
    <div
      className="cc__bets"
      role="img"
      aria-label={`Bets: ${trueCredits} credits on true, ${falseCredits} on false`}
    >
      <span className="cc__bet">
        <Chips n={betChips(trueCredits)} tone="true" mark="check" />
        <span className="cc__tally">{compact.format(trueCredits)}</span>
      </span>
      <span className="cc__bet">
        <Chips n={betChips(falseCredits)} tone="false" mark="cross" />
        <span className="cc__tally">{compact.format(falseCredits)}</span>
      </span>
    </div>
  );
}

function Arrow() {
  return (
    <svg className="cc__arrow" viewBox="0 0 36 22" aria-hidden="true">
      <path
        d="M2.5 11.8C11 10.4 20 12.6 31 11M23.5 4.6L32.5 11L23.8 17.6"
        fill="none"
        stroke="var(--ink)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
