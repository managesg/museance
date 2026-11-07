import type { SheetLine } from '../contracts';
import './hud2.css';

// Lines kept mounted; earlier ones have already fed up past the heading.
const SHOWN = 12;
const words = new Intl.NumberFormat('en-US');

// The page, drawn a touch off true, with its top right corner folded down.
const SHEET =
  'M10 4.5C120 3.2 280 5.4 400 4L435.5 39C434.6 140 436.4 250 435.2 350Q435 355.6 429.4 355.6C300 356.8 140 354.6 10.6 356Q4.4 355.8 4.6 349.6C3.4 250 5.6 120 4.2 10.4Q4.4 4.6 10 4.5Z';
const EAR = 'M400 4L400.6 35.4Q400.8 39.2 404.6 39.1L435.5 39Z';

export function ReaderSheet({ lines, wordCount }: { lines: SheetLine[]; wordCount: number }) {
  const from = Math.max(0, lines.length - SHOWN);
  return (
    <section className="hud-sheet" aria-label="Behavior sheet">
      <svg className="hud-sheet__paper" viewBox="0 0 440 360" preserveAspectRatio="none" aria-hidden="true">
        <path
          d={SHEET}
          fill="var(--paper)"
          stroke="var(--ink)"
          strokeWidth="3"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        <path
          d={EAR}
          fill="var(--paper-deep)"
          stroke="var(--ink)"
          strokeWidth="2.5"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <h2 className="hud-sheet__title">Behavior sheet</h2>
      <div className="hud-sheet__feed">
        <ol className="hud-sheet__lines">
          {lines.slice(from).map((line, i) => (
            <li key={`${from + i}:${line.id}`} className="hud-sheet__line">
              <div className="hud-sheet__inner">
                <span className={`hud-sheet__tag hud-sheet__tag--${line.label.toLowerCase()}`}>{line.label}</span>
                <div className="hud-sheet__body">
                  <p className="hud-sheet__text">{line.text}</p>
                  {line.conflicts.length > 0 && (
                    <p className="hud-sheet__conflict">
                      <svg className="hud-sheet__clash" viewBox="0 0 24 24" role="img" aria-label="conflicts with">
                        <path d="M12 1.8L14.2 7.6L20.4 5.2L17.6 10.9L22.6 13.6L16.6 15.2L17.8 21.6L12.4 17.6L8.2 22.4L7.6 16.2L1.6 15.4L6.2 11.4L3.2 5.8L9.4 7.4Z" />
                      </svg>
                      {line.conflicts.join(', ')}
                    </p>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>
      <p className="hud-sheet__count">
        <span>words read:</span>{' '}
        <span className="hud-sheet__num">{Number.isFinite(wordCount) ? words.format(wordCount) : '—'}</span>{' '}
        <span>· one pass</span>
      </p>
    </section>
  );
}
