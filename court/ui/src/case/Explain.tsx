import { useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { GLOSSARY, type Term } from './glossary'
import './explain.css'

const TIP_W = 320

// Hover for a moment, focus, or press and hold to see what a term means. No term: the children, plain.
// The tip is portalled to <body> at fixed coordinates, so no scrolling or overflow-hidden column can clip it.
export function Explain({ term, children }: { term?: Term; children: ReactNode }) {
  const [at, setAt] = useState<CSSProperties | null>(null)
  const timer = useRef<number | null>(null)
  const self = useRef<HTMLSpanElement>(null)
  const id = useId()
  if (!term) return <>{children}</>
  const clear = () => {
    if (timer.current !== null) window.clearTimeout(timer.current)
    timer.current = null
  }
  const show = () => {
    const r = self.current?.getBoundingClientRect()
    if (!r) return
    const left = Math.max(8, Math.min(r.left + r.width / 2 - TIP_W / 2, innerWidth - TIP_W - 8))
    // Downward near the top of the screen (the header), upward everywhere else (the numbers bar).
    setAt(r.top < 220 ? { left, top: r.bottom + 10 } : { left, bottom: innerHeight - r.top + 10 })
  }
  const openAfter = (ms: number) => {
    clear()
    timer.current = window.setTimeout(show, ms)
  }
  const close = () => {
    clear()
    setAt(null)
  }
  const entry = GLOSSARY[term]
  return (
    <span
      ref={self}
      className="explain"
      tabIndex={0}
      aria-describedby={at ? id : undefined}
      onMouseEnter={() => openAfter(350)}
      onMouseLeave={close}
      onFocus={show}
      onBlur={close}
      onPointerDown={(e) => { if (e.pointerType !== 'mouse') openAfter(450) }}
      onPointerCancel={clear}
      onKeyDown={(e) => { if (e.key === 'Escape') close() }}
    >
      {children}
      {at && createPortal(
        <span role="tooltip" id={id} className="explain__tip" style={at}>
          <b>{entry.title}.</b> {entry.text}
        </span>,
        document.body,
      )}
    </span>
  )
}
