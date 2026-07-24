import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

// The 3D swing-open "darshan" transition that reveals the temple sheet. Ported
// from the prototype's revealWithDoors / .doors CSS. Honours reduced-motion.
const REDUCED =
  typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches

export function Doors({ run, onDone }: { run: boolean; onDone?: () => void }) {
  const [open, setOpen] = useState(false)
  // Keep onDone in a ref so a parent re-render (e.g. temple data arriving mid-
  // reveal) doesn't cancel and re-arm the dismiss timer — depend on `run` only.
  const done = useRef(onDone)
  done.current = onDone

  useEffect(() => {
    if (!run) {
      setOpen(false)
      return
    }
    if (REDUCED) {
      done.current?.()
      return
    }
    const r = requestAnimationFrame(() => setOpen(true))
    const t = setTimeout(() => done.current?.(), 1200)
    return () => {
      cancelAnimationFrame(r)
      clearTimeout(t)
    }
  }, [run])

  const host = document.getElementById('phone')
  if (!run || REDUCED || !host) return null

  return createPortal(
    <div className={`doors run ${open ? 'open' : ''}`} aria-hidden="true">
      <div className="dglow" />
      <div className="leaf l" />
      <div className="leaf r" />
    </div>,
    host,
  )
}
