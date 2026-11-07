// Dev-only: one cast member on the stage's wall and floor, 512x512, captured to public/avatars/ for the Fetch agents.
import type { ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import '../styles/tokens.css'
import { McClusky } from '../cast/McClusky'
import { DrHoot } from '../cast/DrHoot'
import { Bailiff } from '../cast/Bailiff'

const CAST: Record<string, ReactNode> = {
  mcclusky: <McClusky mood="idle" stress={0.15} />,
  hoot: <DrHoot mood="unimpressed" />,
  bailiff: <Bailiff mood="idle" />,
}

const who = new URLSearchParams(location.search).get('who') ?? 'mcclusky'

createRoot(document.getElementById('root')!).render(
  <div style={{ position: 'relative', width: 512, height: 512, background: 'var(--wall)' }}>
    <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 112, background: 'var(--floor)' }} />
    <div style={{ position: 'absolute', left: 36, top: 28, width: 440, height: 456 }}>{CAST[who] ?? null}</div>
  </div>,
)
