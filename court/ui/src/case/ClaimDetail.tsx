import { Stamp } from '../cards/Stamp';
import { prettyOutput } from '../engine/format';
import type { LockStatus } from '../contracts';
import type { CardView } from '../engine/types';
import { Explain } from './Explain';
import type { Term } from './glossary';
import { stepText } from './steps';
import './claims.css';

const TIER = { A: 'running original', B: 'screenshots', C: 'testimony', D: 'nothing' } as const;
const RULED = new Set(['LOCKED', 'STRUCK', 'UNSWORN', 'FABRICATED']);
// A ruled status is its own glossary term (LOCKED -> locked); a claim's label is seen/guessed on the sheet, or fabricated.
const termOf = (s: string) => (RULED.has(s) ? (s.toLowerCase() as Term) : undefined);

export function ClaimDetail({ view, label }: { view: CardView | null; label?: (sel: string) => string | null }) {
  if (!view) return <section className="cl-detail cl-detail--empty">Claims appear here as the medium swears them.</section>;
  const { claim, status, verdict } = view;
  return (
    <section className="cl-detail" aria-label={`Claim ${claim.id}`}>
      {RULED.has(status) && (
        <div className="cl-detail__stamp">
          <Explain term={termOf(status)}><Stamp status={status as LockStatus} size={status === 'LOCKED' ? 110 : 170} /></Explain>
        </div>
      )}
      <header className="cl-detail__head">
        <span className="cl-detail__id">{claim.id}</span>
        <span>{claim.screen}</span>
        <span className={`cl-label cl-label--${claim.label.toLowerCase()}`}><Explain term={termOf(claim.label) ?? 'sheet'}>{claim.label}</Explain></span>
        <span><Explain term="tier">tier {claim.tier}</Explain> · {TIER[claim.tier]}</span>
      </header>
      <p className="cl-detail__text">{claim.text}</p>
      <ol className="cl-detail__steps">
        {claim.test.steps.map((s, i) => <li key={i}>{stepText(s, label)}</li>)}
      </ol>
      <p className="cl-detail__expect">expect <code>{claim.test.expect || '(empty)'}</code> in <code>{claim.test.observe}</code></p>
      <div className="cl-detail__nums">
        <div><span className="cl-big">{Math.round(claim.confidence * 100)}%</span><small><Explain term="confidence">confidence</Explain></small></div>
        <div><span className="cl-big">{claim.bond}</span><small><Explain term="bond">bond</Explain></small></div>
        <div className="cl-detail__ev"><small><Explain term="evidence">evidence</Explain></small>{claim.evidence?.length ? claim.evidence.join(', ') : 'none'}</div>
      </div>
      {verdict && (
        <p className={`cl-detail__verdict${verdict.match ? '' : ' is-miss'}`}>
          <Explain term="original">original</Explain> showed <b>{prettyOutput(verdict.original) || '(empty)'}</b> · <Explain term="revival">revival</Explain> showed <b>{prettyOutput(verdict.revival) || '(empty)'}</b>
        </p>
      )}
    </section>
  );
}
