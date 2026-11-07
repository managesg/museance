// Dev-only visual check of the cast, set, cards and stamps in every mood (open /gallery.html).
import { useEffect, useState, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/unifrakturcook/700.css'
import '@fontsource/alfa-slab-one/400.css'
import '@fontsource/courier-prime/400.css'
import '@fontsource/courier-prime/700.css'
import '@fontsource/atkinson-hyperlegible/400.css'
import '@fontsource/atkinson-hyperlegible/700.css'
import { McClusky } from '../cast/McClusky'
import { Ghost } from '../cast/Ghost'
import { DrHoot } from '../cast/DrHoot'
import { Faux } from '../cast/Faux'
import { Stenographer } from '../cast/Stenographer'
import { LittleGuy } from '../cast/LittleGuy'
import { CourtroomBackdrop } from '../set/Courtroom'
import { ClaimCard } from '../cards/ClaimCard'
import { ClaimSpread } from '../cards/ClaimSpread'
import { Stamp } from '../cards/Stamp'
import type { Claim, LockStatus, Verdict } from '../contracts'
import type { CardView, GuyKind, GuyState } from '../engine/types'

// Two fixture claims copied from fixtures/claims.json and verdicts.json (the dev server cannot import outside court/ui yet).
const claims: Claim[] = [
  { id: 'c02', app: 'app1', screen: 'multiply', text: '7 x 8 shows 56', test: { steps: ['click:#k7', 'click:#kmul', 'click:#k8', 'click:#keq'], observe: '#display', expect: '56' }, tier: 'A', label: 'SEEN', evidence: ['shot-002'], confidence: 0.9, bond: 180 },
  { id: 'c03', app: 'app1', screen: 'divide', text: '1 / 8 rounds to 0.13', test: { steps: ['click:#k1', 'click:#kdiv', 'click:#k8', 'click:#keq'], observe: '#display', expect: '0.13' }, tier: 'C', label: 'GUESSED', evidence: ['thread-003'], confidence: 0.6, bond: 60 },
  { id: 'c05', app: 'app1', screen: 'divide', text: 'dividing by zero shows Error', test: { steps: ['click:#k7', 'click:#kdiv', 'click:#k0', 'click:#keq'], observe: '#display', expect: 'Error' }, tier: 'D', label: 'FABRICATED', evidence: [], confidence: 0.3, bond: 10 },
]
const verdicts: Verdict[] = [
  { ref: 'c02', kind: 'claim', original: '56', revival: '56', claim_true: true, match: true, flaky: false, shrunk_steps: [] },
  { ref: 'c03', kind: 'claim', original: '0.12', revival: '0.13', claim_true: false, match: false, flaky: false, shrunk_steps: ['click:#k1', 'click:#kdiv', 'click:#k8', 'click:#keq'] },
  { ref: 'c05', kind: 'claim', original: 'Error', revival: 'Infinity', claim_true: true, match: false, flaky: false, shrunk_steps: ['click:#k7', 'click:#kdiv', 'click:#k0', 'click:#keq'] },
]
const statuses: CardView['status'][] = ['sealed', 'sworn', 'under-cross', 'LOCKED', 'STRUCK', 'UNSWORN', 'FABRICATED']
const view = (i: number, status: CardView['status']): CardView => ({ claim: claims[i % claims.length], status, verdict: verdicts[i % verdicts.length], bets: { trueCredits: 300, falseCredits: 200 } })

function Row({ title, children }: { title: string; children: ReactNode }) {
  return <section><h2>{title}</h2><div className="items">{children}</div></section>
}
function Item({ label, w, h, children }: { label: string; w: number; h: number; children: ReactNode }) {
  return (
    <figure style={{ width: w }}>
      <div style={{ width: w, height: h, position: 'relative' }}>{children}</div>
      <figcaption>{label}</figcaption>
    </figure>
  )
}

const KINDS: GuyKind[] = ['calculator', 'brush', 'clock', 'keycap']
const GUY_STATES: GuyState[] = ['idle', 'nervous', 'glitch', 'locked', 'repaired', 'fabricated']
const MC = ['idle', 'swearing', 'nervous', 'caught', 'fainted', 'relieved'] as const
const GH = ['idle', 'hopeful', 'sad', 'flicker', 'relieved'] as const
const HO = ['idle', 'writing', 'attacking', 'unimpressed', 'satisfied'] as const
const FX = ['hidden', 'wave', 'bow', 'smug'] as const
const ST = ['idle', 'scribbling', 'sealing'] as const
const CARD_RUN: CardView['status'][] = ['sealed', 'sworn', 'under-cross', 'STRUCK', 'LOCKED']

// Every tile steps to its next mood on one shared tick, so transitions can be watched side by side.
function Live() {
  const [i, setI] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setI(x => x + 1), 2200)
    return () => clearInterval(t)
  }, [])
  const mc = MC[i % MC.length]
  const s = CARD_RUN[i % CARD_RUN.length]
  return (
    <Row title={`Live cycle · step ${i}`}>
      <Item label={`McClusky · ${mc}`} w={240} h={300}><McClusky mood={mc} stress={mc === 'nervous' || mc === 'caught' ? 0.85 : 0.2} /></Item>
      <Item label={`Ghost · ${GH[i % GH.length]}`} w={200} h={240}><Ghost mood={GH[i % GH.length]} /></Item>
      <Item label={`Hoot · ${HO[i % HO.length]}`} w={200} h={275}><DrHoot mood={HO[i % HO.length]} /></Item>
      <Item label={`Faux · ${FX[i % FX.length]}`} w={170} h={300}><Faux mood={FX[i % FX.length]} /></Item>
      <Item label={`Steno · ${ST[i % ST.length]}`} w={160} h={220}><Stenographer mood={ST[i % ST.length]} /></Item>
      <Item label={`keycap · ${GUY_STATES[i % GUY_STATES.length]}`} w={140} h={175}><LittleGuy kind="keycap" glyph="÷" state={GUY_STATES[i % GUY_STATES.length]} label="divide" /></Item>
      <Item label={`card · ${s}`} w={200} h={300}><ClaimCard view={view(1, s)} size="small" /></Item>
    </Row>
  )
}

// Static composition of the finished pieces at their stage zones (1920x1080 design px), shown at 0.75.
// The exhibit frames, top rail and numbers bar are still being built, so they appear as labelled paper outlines.
const at = (x: number, y: number, w: number, h: number) => ({ position: 'absolute' as const, left: x, top: y, width: w, height: h })
const Placeholder = ({ label }: { label: string }) => (
  <div style={{ width: '100%', height: '100%', border: '3px dashed var(--paper)', borderRadius: 8, display: 'grid', placeItems: 'center', color: 'var(--paper)', font: '24px var(--font-doc)', textAlign: 'center' }}>{label}</div>
)
function StagePreview() {
  const cards: CardView[] = [view(0, 'LOCKED'), view(1, 'STRUCK'), view(2, 'FABRICATED'), view(0, 'sworn'), view(1, 'sealed')]
  return (
    <section>
      <h2>Stage composition (static preview)</h2>
      <div style={{ width: 1440, height: 810, overflow: 'hidden', borderRadius: 6 }}>
        <div style={{ width: 1920, height: 1080, position: 'relative', transform: 'scale(0.75)', transformOrigin: '0 0' }}>
          <div style={at(0, 0, 1920, 1080)}><CourtroomBackdrop tension={0.4} /></div>
          <div style={at(0, 0, 1920, 84)}><Placeholder label="top rail: masthead · phase docket · source badge (building)" /></div>
          <div style={at(56, 110, 500, 440)}><Placeholder label="EXHIBIT O · the original (building)" /></div>
          <div style={at(1364, 110, 500, 440)}><Placeholder label="EXHIBIT R · the revival (building)" /></div>
          <div style={at(820, 90, 280, 330)}><Ghost mood="sad" /></div>
          <div style={at(1420, 150, 240, 430)}><Faux mood="wave" /></div>
          <div style={at(90, 450, 400, 500)}><McClusky mood="nervous" stress={0.6} /></div>
          <div style={at(1390, 430, 330, 470)}><DrHoot mood="attacking" /></div>
          <div style={at(1730, 610, 170, 250)}><Stenographer mood="scribbling" /></div>
          <div style={at(560, 430, 800, 520)}><ClaimSpread cards={cards} focusId={null} width={800} height={520} /></div>
          <div style={at(470, 830, 110, 140)}><LittleGuy kind="keycap" glyph="+" state="locked" label="add" /></div>
          <div style={at(590, 850, 110, 140)}><LittleGuy kind="keycap" glyph="×" state="idle" label="multiply" /></div>
          <div style={at(1220, 850, 110, 140)}><LittleGuy kind="keycap" glyph="÷" state="glitch" label="divide" /></div>
          <div style={at(1340, 830, 110, 140)}><LittleGuy kind="keycap" glyph="C" state="locked" label="clear" /></div>
          <div style={at(460, 904, 1000, 64)}><Placeholder label="McCLUSKY: Ninety percent. On my scarf. (subtitle)" /></div>
          <div style={at(0, 984, 1920, 96)}><Placeholder label="numbers bar: credibility · Brier · fidelity · false strikes · traps (building)" /></div>
        </div>
      </div>
    </section>
  )
}

function Gallery() {
  return (
    <main>
      <h1>MUSÉANCE · cast gallery</h1>
      <StagePreview />
      <Live />
      <Row title="McClusky, Esq.">
        {(['idle', 'swearing', 'nervous', 'caught', 'fainted', 'relieved'] as const).map(m => (
          <Item key={m} label={m} w={260} h={320}><McClusky mood={m} stress={m === 'nervous' || m === 'caught' ? 0.85 : 0.2} /></Item>
        ))}
      </Row>
      <Row title="The Departed">
        {(['idle', 'hopeful', 'sad', 'flicker', 'relieved'] as const).map(m => (
          <Item key={m} label={m} w={220} h={264}><Ghost mood={m} /></Item>
        ))}
      </Row>
      <Row title="Dr. Hoot">
        {(['idle', 'writing', 'attacking', 'unimpressed', 'satisfied'] as const).map(m => (
          <Item key={m} label={m} w={220} h={300}><DrHoot mood={m} /></Item>
        ))}
      </Row>
      <Row title="Faux">
        {(['hidden', 'wave', 'bow', 'smug'] as const).map(m => (
          <Item key={m} label={m} w={180} h={315}><Faux mood={m} /></Item>
        ))}
      </Row>
      <Row title="Stenographer">
        {(['idle', 'scribbling', 'sealing'] as const).map(m => (
          <Item key={m} label={m} w={180} h={250}><Stenographer mood={m} /></Item>
        ))}
      </Row>
      <Row title="Little guys">
        {KINDS.flatMap(k => GUY_STATES.map(s => (
          <Item key={k + s} label={`${k} · ${s}`} w={140} h={175}><LittleGuy kind={k} glyph={k === 'keycap' ? '÷' : undefined} state={s} label="divide" /></Item>
        )))}
      </Row>
      <Row title="Claim cards (small)">
        {statuses.map((s, i) => <Item key={s} label={s} w={200} h={300}><ClaimCard view={view(i, s)} size="small" /></Item>)}
      </Row>
      <Row title="Claim card (focus)">
        <Item label="c03 STRUCK" w={420} h={630}><ClaimCard view={view(1, 'STRUCK')} size="focus" /></Item>
        <Item label="c02 sworn" w={420} h={630}><ClaimCard view={view(0, 'sworn')} size="focus" /></Item>
      </Row>
      <Row title="Stamps">
        {(['LOCKED', 'STRUCK', 'UNSWORN', 'FABRICATED'] as LockStatus[]).map(s => (
          <Item key={s} label={s} w={240} h={170}><Stamp status={s} size={200} /></Item>
        ))}
      </Row>
      <Row title="Set">
        <Item label="CourtroomBackdrop (tension 0.3)" w={1440} h={810}><CourtroomBackdrop tension={0.3} /></Item>
      </Row>
    </main>
  )
}

createRoot(document.getElementById('root')!).render(<Gallery />)
