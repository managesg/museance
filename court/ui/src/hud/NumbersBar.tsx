import { useId, type ReactNode } from 'react';
import type { CaseBundle } from '../contracts';
import type { Measured, Scores } from '../engine/types';
import { Explain } from '../case/Explain';
import type { Term } from '../case/glossary';
import './hud.css';

const MOULD = 'M-10 2.6Q480 1.2 960 2.9T1930 2.2V11.6Q960 13.2 -10 11.4Z';
const ARROW = 'M3 11.6Q15 10.1 29.5 11M21 4.4L31 11L21.6 17.6';

const finite = (n: number | null | undefined): n is number => typeof n === 'number' && Number.isFinite(n);
const whole = (n: number) => (n < 0 ? `−${Math.abs(Math.round(n))}` : String(Math.round(n)));
const count = (n: number) => (finite(n) ? whole(n) : null);
const ratio = (m: Measured | null) => (m && finite(m.value) && finite(m.of) ? `${whole(m.value)}/${whole(m.of)}` : null);

function Figures({ text, className }: { text: string; className?: string }) {
  return (
    <span className={className ? `hud-num ${className}` : 'hud-num'}>
      <span aria-hidden="true">
        {[...text].map((c, i) => (
          <span key={i} className={c >= '0' && c <= '9' ? 'hud-d' : undefined}>
            {c}
          </span>
        ))}
      </span>
      <span className="hud-sr">{text}</span>
    </span>
  );
}

// Null means the court has not measured it: a dash and a note, never a stand-in number.
function Value({ text }: { text: string | null }) {
  if (text === null) {
    return (
      <>
        <span className="hud-num hud-num--none" aria-hidden="true">
          —
        </span>
        <span className="hud-plate__note">not measured</span>
      </>
    );
  }
  return <Figures key={text} text={text} />;
}

function Plate(props: { label: string; term?: Term; stripes: string | null; kind?: 'unsworn' | 'fabricated'; flagged?: boolean; children: ReactNode }) {
  const { label, term, stripes, kind, flagged, children } = props;
  return (
    <div className={`hud-plate${kind ? ` hud-plate--${kind}` : ''}${flagged ? ' is-flagged' : ''}`}>
      <dt className="hud-plate__label"><Explain term={term}>{label}</Explain></dt>
      <dd className="hud-plate__win">
        {stripes && (
          <svg className="hud-plate__stripes" aria-hidden="true">
            <rect width="100%" height="100%" fill={`url(#${stripes})`} />
          </svg>
        )}
        {children}
      </dd>
    </div>
  );
}

/** The walnut and brass scoreboard along the bottom: 100% wide (1920 design px) by 96. Fixture numbers sit in striped windows. */
/** explain: hover a label for its meaning (the case screen); the stage keeps plain labels. */
export function NumbersBar({ scores, source, explain = false }: { scores: Scores; source: CaseBundle['source']; explain?: boolean }) {
  const t = (term: Term) => (explain ? term : undefined);
  const pattern = `hud-fx-${useId().replace(/[^\w-]/g, '')}`;
  const stripes = source === 'fixture' ? pattern : null;
  const s = scores;
  return (
    <section className="hud-numbers" aria-label="Scores">
      <svg className="hud-numbers__bg" viewBox="0 0 1920 96" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <pattern id={pattern} width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="5" height="12" fill="var(--paper-deep)" />
          </pattern>
        </defs>
        <rect y="8" width="1920" height="88" fill="var(--wood)" />
        <path d={MOULD} fill="var(--wood-light)" stroke="var(--ink)" strokeWidth="4" vectorEffect="non-scaling-stroke" />
      </svg>
      <dl className="hud-numbers__row">
        <Plate label="Credibility" term={t('credibility')} stripes={stripes}>
          <Figures key={`a${s.credibilityStart}`} text={whole(s.credibilityStart)} className="hud-num--from" />
          <svg className="hud-arrow" viewBox="0 0 34 22" aria-hidden="true">
            <path d={ARROW} />
          </svg>
          <span className="hud-sr"> to </span>
          <Figures
            key={`b${s.credibility}`}
            text={whole(s.credibility)}
            className={s.credibility < s.credibilityStart ? 'is-down' : undefined}
          />
        </Plate>
        <Plate label="Brier" term={t('brier')} stripes={stripes}>
          <Value text={finite(s.brier) ? s.brier.toFixed(2) : null} />
        </Plate>
        <Plate label="Fidelity" term={t('fidelity')} stripes={stripes}>
          <Value text={finite(s.fidelity) ? `${Math.round(s.fidelity)}%` : null} />
        </Plate>
        <Plate label="False strikes" term={t('falseStrikes')} stripes={stripes}>
          <Value text={ratio(s.falseStrikes)} />
        </Plate>
        <Plate label="Traps caught" term={t('traps')} stripes={stripes}>
          <Value text={ratio(s.trapsCaught)} />
        </Plate>
        <Plate label="Survived" stripes={stripes}>
          <Value text={ratio({ value: s.claimsSurvived, of: s.claimsMade })} />
        </Plate>
        <Plate label="Unsworn" term={t('unsworn')} stripes={stripes} kind="unsworn" flagged={s.unsworn > 0}>
          <Value text={count(s.unsworn)} />
        </Plate>
        <Plate label="Fabricated" term={t('fabricated')} stripes={stripes} kind="fabricated" flagged={s.fabricated > 0}>
          <Value text={count(s.fabricated)} />
        </Plate>
        <Plate label="Rollbacks" stripes={stripes}>
          <Value text={count(s.rollbacks)} />
        </Plate>
      </dl>
      {stripes && (
        <p className="hud-numbers__src">
          <svg className="hud-swatch" viewBox="0 0 26 36" aria-hidden="true">
            <rect x="1.5" y="1.5" width="23" height="33" rx="4" fill="var(--paper)" />
            <rect x="1.5" y="1.5" width="23" height="33" rx="4" fill={`url(#${stripes})`} />
            <rect x="1.5" y="1.5" width="23" height="33" rx="4" fill="none" stroke="var(--ink)" strokeWidth="2.5" />
          </svg>
          <span>
            <span>fixture data</span>
            <span className="hud-sr"> · </span>
            <span>not measured today</span>
          </span>
        </p>
      )}
    </section>
  );
}
