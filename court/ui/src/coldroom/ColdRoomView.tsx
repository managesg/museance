// ?view=coldroom: the same cold-room controller, two builds. The court proves cooling behaves the same,
// and the setpoint attack lands only on the legacy build. Data: ./model.ts (P1's sample run).
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { verifyLedger } from '../engine/hash';
import { celsius, EVENTS, hms, ITEMS, MAX_SIM, refOf, regs, simSeconds, SUMMARY, writeTaken, type Item, type Side } from './model';
import './coldroom.css';

const STEP_MS = 400;
const HAS_CHAIN = EVENTS.length > 0 && EVENTS.every((e) => typeof e.hash === 'string' && typeof e.prev_hash === 'string');
const HERO = ITEMS.find((i) => i.kind === 'attack') ?? null;

const PATHS = {
  lockOpen: (
    <>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 7.7-1.6" />
    </>
  ),
  lockClosed: (
    <>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </>
  ),
  fan: (
    <>
      <circle cx="12" cy="12" r="1.6" />
      <path d="M12 10.4C11 6 12 3 15 3.4s1.6 4.6-1.6 7.4" />
      <path d="M13.6 12c4.4-1 7.4 0 7 3s-4.6 1.6-7.4-1.6" />
      <path d="M12 13.6c1 4.4 0 7.4-3 7s-1.6-4.6 1.6-7.4" />
      <path d="M10.4 12C6 13 3 12 3.4 9s4.6-1.6 7.4 1.6" />
    </>
  ),
  drop: <path d="M12 3c3 4 6 7.5 6 11a6 6 0 0 1-12 0c0-3.5 3-7 6-11Z" />,
  bell: (
    <>
      <path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15Z" />
      <path d="M10 20.5a2 2 0 0 0 4 0" />
    </>
  ),
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  cross: <path d="M6 6l12 12M18 6L6 18" />,
  shield: (
    <>
      <path d="M12 3l7 3v5c0 5-3 8.5-7 10-4-1.5-7-5-7-10V6Z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
  link: (
    <>
      <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" />
      <path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />
    </>
  ),
  play: <path d="M8 5v14l11-7Z" fill="currentColor" />,
  pause: <path d="M9 5v14M15 5v14" />,
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  seal: <path d="M5 9h14M5 15h14M10 4 8 20M16 4l-2 16" />,
  differ: <path d="M5 9h14M5 15h14M16 4 8 20" />,
};
type IconName = keyof typeof PATHS;

function Icon({ name, size = 24 }: { name: IconName; size?: number }) {
  return (
    <svg
      className={`cr-icon cr-icon-${name}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}

function Badge({ tone, icon, children }: { tone: 'ok' | 'bad' | 'steel' | 'wait'; icon: IconName; children: ReactNode }) {
  return (
    <span className={`cr-badge cr-badge-${tone}`}>
      <Icon name={icon} size={18} />
      {children}
    </span>
  );
}

/** The ruling an item shows, as an icon and a word (never color alone). */
function ruling(item: Item, landed: boolean, sealed: boolean, locked: boolean) {
  const v = item.verdict;
  if (!landed || !v) return sealed ? <Badge tone="wait" icon="seal">sealed</Badge> : <Badge tone="wait" icon="clock">waiting</Badge>;
  if (item.kind === 'attack') {
    const blocked = !v.match && writeTaken(item, 'original') && writeTaken(item, 'revival') === false;
    return blocked ? <Badge tone="ok" icon="shield">blocked on patch</Badge> : <Badge tone="bad" icon="cross">not blocked</Badge>;
  }
  return (
    <>
      {v.match ? <Badge tone="ok" icon="check">MATCH</Badge> : <Badge tone="bad" icon="cross">MISMATCH</Badge>}
      {locked && <Badge tone="ok" icon="lockClosed">LOCKED</Badge>}
    </>
  );
}

function Indicator({ icon, label, on, alarm = false }: { icon: IconName; label: string; on: number | undefined; alarm?: boolean }) {
  const state = on == null ? 'unknown' : on ? 'on' : 'off';
  return (
    <div className={`cr-ind is-${state}${alarm ? ' is-alarm' : ''}`}>
      <Icon name={icon} size={48} />
      <span className="cr-ind-label">{label}</span>
      <span className="cr-ind-state">{on == null ? '—' : on ? 'ON' : 'OFF'}</span>
    </div>
  );
}

function Panel({ side, item }: { side: Side; item: Item | null }) {
  const legacy = side === 'original';
  const r = item?.verdict ? regs(item.verdict[side]) : {};
  const taken = item ? writeTaken(item, side) : null;
  return (
    <section className={`cr-panel cr-panel-${side}`} aria-label={legacy ? 'Original build' : 'Patched build'}>
      <header className="cr-panel-head">
        <div>
          <h2>{legacy ? 'ORIGINAL' : 'PATCHED'}</h2>
          <p>{legacy ? 'legacy controller' : 'MUSÉANCE revival'}</p>
        </div>
        <span className={`cr-lock ${legacy ? 'is-open' : 'is-closed'}`}>
          <Icon name={legacy ? 'lockOpen' : 'lockClosed'} size={34} />
          {legacy ? 'no auth: anyone can write' : 'writes need a PIN'}
        </span>
      </header>
      <div className="cr-temp">
        <span className="cr-temp-value">
          {celsius(r.hr0)}
          <small> °C</small>
        </span>
        <span className="cr-temp-label">room temperature</span>
      </div>
      <div className="cr-setpoint">
        <span>
          setpoint <b>{celsius(r.hr1)} °C</b>
        </span>
        {taken === true && <Badge tone="bad" icon="lockOpen">write accepted</Badge>}
        {taken === false && <Badge tone="ok" icon="shield">write rejected</Badge>}
      </div>
      <div className="cr-inds">
        <Indicator icon="fan" label="Compressor" on={r.coil0} />
        <Indicator icon="drop" label="Defrost" on={r.coil1} />
        <Indicator icon="bell" label="Alarm" on={r.coil2} alarm />
      </div>
      {taken != null && (
        <p className={`cr-caption ${taken ? 'is-bad' : 'is-ok'}`}>
          {taken ? `Setpoint moved to ${celsius(r.hr1)} °C.` : `Setpoint stays at ${celsius(r.hr1)} °C.`} Room at {celsius(r.hr0)} °C, compressor{' '}
          {r.coil0 ? 'on' : 'off'}, alarm {r.coil2 ? 'raised' : 'silent'}.
        </p>
      )}
    </section>
  );
}

function Evidence({ item }: { item: Item }) {
  const v = item.verdict;
  const o = v ? regs(v.original) : {};
  const p = v ? regs(v.revival) : {};
  const row = (label: string, mine: Record<string, number>, other: Record<string, number>) => (
    <div className="cr-ev-row">
      <span>{label}</span>
      <code>
        {Object.entries(mine).map(([k, n]) => (
          <span key={k} className={other[k] === n ? '' : 'is-diff'}>
            {k}={n}{' '}
          </span>
        ))}
      </code>
    </div>
  );
  return (
    <div className="cr-evidence">
      <div className="cr-ev-row">
        <span>steps</span>
        <code>{item.steps.join('  →  ')}</code>
      </div>
      {v ? (
        <>
          {row('original', o, p)}
          {row('patched', p, o)}
        </>
      ) : (
        <p className="cr-muted">No verdict on the replay yet.</p>
      )}
    </div>
  );
}

export function ColdRoomView() {
  const [n, setN] = useState(0); // ledger events replayed so far
  const [playing, setPlaying] = useState(false);
  const [hover, setHover] = useState<string | null>(null);
  const [chainOk, setChainOk] = useState<boolean | null>(null);
  const total = EVENTS.length;
  const running = playing && n < total;
  const done = n >= total;

  useEffect(() => {
    if (HAS_CHAIN) void verifyLedger(EVENTS).then(setChainOk, () => setChainOk(false));
  }, []);

  useEffect(() => {
    if (!running) return;
    const t = setTimeout(() => setN((k) => k + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [running, n]);

  const seen = useMemo(() => {
    const sealed = new Set<string>();
    const landed = new Set<string>();
    const locked = new Set<string>();
    let last: string | null = null;
    for (const e of EVENTS.slice(0, n)) {
      const ref = refOf(e);
      if (!ref) continue;
      if (e.type === 'commit') sealed.add(ref);
      if (e.type === 'verdict') {
        landed.add(ref);
        last = ref;
      }
      if (e.type === 'lock') locked.add(ref);
    }
    return { sealed, landed, locked, last };
  }, [n]);

  const byId = (id: string | null) => ITEMS.find((i) => i.id === id) ?? null;
  // A hovered card shows its evidence; otherwise the last verdict in; at the end, the attack.
  const hovered = byId(hover);
  const shown = hovered ?? (done ? HERO : byId(seen.last));
  const shownLanded = !!shown && (done || seen.landed.has(shown.id));
  const panelItem = shown && shownLanded ? shown : null;
  const sim = panelItem ? simSeconds(panelItem.steps) : 0;
  const lastEvent = n > 0 ? EVENTS[n - 1] : null;
  const lastVerdict = byId(seen.last);

  const announce = done
    ? `All ${total} ledger events replayed. ${SUMMARY.identical} of ${SUMMARY.controls} control behaviors identical, ${SUMMARY.blocked} of ${SUMMARY.attacks} attacks blocked on the patch.`
    : lastVerdict?.verdict
      ? `${lastVerdict.text}: ${lastVerdict.kind === 'attack' ? 'the builds differ' : lastVerdict.verdict.match ? 'identical on both builds' : 'the builds differ'}.`
      : '';

  const play = () => {
    if (done) {
      setN(0);
      setPlaying(true);
    } else setPlaying(!running);
  };

  const groups: { title: string; sub: string; kind: Item['kind'] }[] = [
    { title: 'Control behavior, must MATCH', sub: 'cooling on/off · hysteresis · high-temp alarm · defrost schedule', kind: 'claim' },
    { title: 'Security, must DIFFER', sub: 'unauthorized configuration changes: legacy accepts, patch rejects', kind: 'attack' },
  ];

  return (
    <div className="cr">
      <header className="cr-top">
        <h1>
          MUSÉANCE <span>·</span> Cold Room Court
        </h1>
        <p className="cr-honest">
          <strong>Modeled controller, not vendor code.</strong> Modeled on the Danfoss controllers in the Oct/Nov 2026 EU supermarket attacks.
        </p>
        {HAS_CHAIN && (
          <p className="cr-head">
            <span className="cr-muted">ledger head</span> <code>{EVENTS[total - 1].hash.slice(0, 12)}</code>
            {chainOk == null ? (
              <Badge tone="wait" icon="clock">checking chain</Badge>
            ) : chainOk ? (
              <Badge tone="ok" icon="link">chain intact</Badge>
            ) : (
              <Badge tone="bad" icon="cross">chain broken</Badge>
            )}
          </p>
        )}
      </header>

      <main className="cr-main">
        <Panel side="original" item={panelItem} />
        <div className="cr-center">
          <button type="button" className="cr-play" onClick={play}>
            <Icon name={running ? 'pause' : 'play'} size={28} />
            {running ? 'Pause' : done ? 'Replay' : n ? 'Resume' : 'Play'}
          </button>
          <p className="cr-progress">
            event <b>{n}</b> / {total}
            {lastEvent && (
              <>
                {' '}
                · {lastEvent.type} <code>{refOf(lastEvent)}</code>
              </>
            )}
          </p>
          <div className="cr-time">
            <div className="cr-time-head">
              <span>simulated time</span>
              <b>{hms(sim)}</b>
            </div>
            <div
              className="cr-track"
              role="img"
              aria-label={`simulated time ${hms(sim)} of ${hms(MAX_SIM)}`}
            >
              <div className="cr-track-fill" style={{ width: `${(sim / MAX_SIM) * 100}%` }} />
              <div className="cr-thumb" style={{ left: `${(sim / MAX_SIM) * 100}%` }} />
              {Array.from({ length: Math.floor(MAX_SIM / 3600) + 1 }, (_, h) => (
                <span key={h} className="cr-hour" style={{ left: `${((h * 3600) / MAX_SIM) * 100}%` }}>
                  {h}h
                </span>
              ))}
            </div>
          </div>
          {shown ? (
            <div className="cr-now">
              <code className="cr-muted">{shown.id}</code>
              <p>{shown.text}</p>
              <div className="cr-badges">{ruling(shown, shownLanded, done || seen.sealed.has(shown.id), shown.locked && (done || seen.locked.has(shown.id)))}</div>
            </div>
          ) : (
            <p className="cr-now cr-muted">Press Play: the court replays its {total} ledger events in order.</p>
          )}
          {hovered ? <Evidence item={hovered} /> : <p className="cr-hint">Hover or focus a card to see the court's evidence.</p>}
        </div>
        <Panel side="revival" item={panelItem} />
      </main>

      <section className="cr-groups">
        {groups.map((g) => {
          const items = ITEMS.filter((i) => i.kind === g.kind);
          return (
            <div key={g.kind} className="cr-group">
              <h3>
                {g.title} <span>{g.sub}</span>
              </h3>
              <ul className="cr-cards" style={{ gridTemplateColumns: `repeat(${items.length}, 1fr)` }}>
                {items.map((i) => {
                  const landed = done || seen.landed.has(i.id);
                  return (
                    <li key={i.id}>
                      <button
                        type="button"
                        className={`cr-card${landed ? ' is-in' : ''}${shown?.id === i.id ? ' is-shown' : ''}`}
                        onMouseEnter={() => setHover(i.id)}
                        onMouseLeave={() => setHover(null)}
                        onFocus={() => setHover(i.id)}
                        onBlur={() => setHover(null)}
                      >
                        <code>{i.id}</code>
                        <span className="cr-card-text">{i.text}</span>
                        <span className="cr-badges">
                          {ruling(i, landed, done || seen.sealed.has(i.id), i.locked && (done || seen.locked.has(i.id)))}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </section>

      <footer className="cr-strip">
        {done ? (
          <ul>
            <li>
              <Icon name={SUMMARY.identical === SUMMARY.controls ? 'check' : 'cross'} size={30} />
              {SUMMARY.identical}/{SUMMARY.controls} control behaviors identical and locked
            </li>
            <li>
              <Icon name={SUMMARY.blocked === SUMMARY.attacks ? 'shield' : 'cross'} size={30} />
              {SUMMARY.blocked}/{SUMMARY.attacks} attacks blocked on the patch
            </li>
            <li>
              <Icon name={SUMMARY.flaky ? 'cross' : 'check'} size={30} />
              {SUMMARY.flaky} flaky
            </li>
            {HAS_CHAIN && (
              <li>
                <Icon name={chainOk ? 'link' : 'cross'} size={30} />
                {chainOk ? 'ledger intact' : 'ledger broken'} · {total} events
              </li>
            )}
          </ul>
        ) : (
          <p className="cr-strip-wait">
            <Icon name="clock" size={30} />
            {n ? `The court is ruling: ${seen.landed.size} of ${ITEMS.length} verdicts in` : 'The court has not ruled yet'}
          </p>
        )}
        <p className="cr-fine">
          Same model-free court; only the test bench changed: an industrial protocol (Modbus TCP) instead of a browser. Next: the real end-of-life
          OpenPLC_v3 runtime.
        </p>
      </footer>
      <p className="cr-sr" aria-live="polite">
        {announce}
      </p>
    </div>
  );
}
