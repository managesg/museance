import type { CSSProperties } from 'react';
import type { LeaderRow } from '../engine/types';
import { PastryAvatar } from './PastryAvatar';
import './bets.css';

/** Bettors ranked by credits; tied credits share a rank (1, 1, 3). */
export function Leaderboard({ rows }: { rows: LeaderRow[] }) {
  const ranked = [...rows].sort((a, b) => b.credits - a.credits);
  return (
    <ol className="lb">
      {ranked.map((row, i) => (
        <li key={`${row.pastry}-${row.name}`} className="lb__row" style={{ '--i': i } as CSSProperties}>
          <span className="lb__rank">{1 + ranked.findIndex((r) => r.credits === row.credits)}</span>
          <span className="lb__avatar">
            <PastryAvatar kind={row.pastry} />
          </span>
          <span className="lb__who">
            <span className="lb__name">{row.name}</span>
            <span className="lb__record">
              won {row.wins}, lost {row.losses}
            </span>
          </span>
          <span className="lb__credits">{row.credits}</span>
        </li>
      ))}
    </ol>
  );
}
