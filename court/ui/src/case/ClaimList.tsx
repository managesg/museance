import { useEffect, useRef } from 'react';
import type { CardView } from '../engine/types';
import { Explain } from './Explain';
import type { Term } from './glossary';
import './claims.css';

const RULED = new Set(['LOCKED', 'STRUCK', 'UNSWORN', 'FABRICATED']);

export function ClaimList({ cards, focusId }: { cards: CardView[]; focusId: string | null }) {
  const focused = useRef<HTMLLIElement>(null);
  useEffect(() => {
    const smooth = !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    focused.current?.scrollIntoView({ block: 'nearest', behavior: smooth ? 'smooth' : 'auto' });
  }, [focusId]);
  return (
    <ul className="cl-list" aria-label="Claims">
      {cards.map(({ claim, status }) => (
        <li
          key={claim.id}
          ref={claim.id === focusId ? focused : undefined}
          className={`cl-row${claim.id === focusId ? ' is-focus' : ''}`}
          aria-current={claim.id === focusId || undefined}
        >
          <span className="cl-row__id">{claim.id}</span>
          <span className="cl-row__text" title={claim.text}>{claim.text}</span>
          <span className={`cl-chip cl-chip--${status.toLowerCase()}`}>
            <Explain term={RULED.has(status) ? (status.toLowerCase() as Term) : undefined}>{status}</Explain>
          </span>
          <span className="cl-row__pct">{Math.round(claim.confidence * 100)}%</span>
        </li>
      ))}
    </ul>
  );
}
