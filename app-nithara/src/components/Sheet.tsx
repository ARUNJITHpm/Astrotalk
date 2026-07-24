import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'

// A modal sheet, ported from the prototype's openSheet/closeAll/syncOverlay.
// While any sheet is open the phone gets [data-overlay] so the floating tab bar
// steps aside (globals.css: .phone[data-overlay] .nav). Mount → next frame set
// data-open so the CSS transition plays (the prototype's rAF trick); on close,
// slide out then unmount after the animation.

let openCount = 0
function syncOverlay() {
  const phone = document.getElementById('phone')
  const nav = document.getElementById('nav')
  if (phone) phone.toggleAttribute('data-overlay', openCount > 0)
  if (nav) {
    nav.setAttribute('aria-hidden', String(openCount > 0))
    if (openCount > 0) nav.setAttribute('inert', '')
    else nav.removeAttribute('inert')
  }
}

export function Sheet({
  open,
  onClose,
  dir = 'up',
  children,
}: {
  open: boolean
  onClose: () => void
  dir?: 'up' | 'right'
  children: ReactNode
}) {
  const [mounted, setMounted] = useState(open)
  const [shown, setShown] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const lastFocus = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (open) {
      setMounted(true)
      const r = requestAnimationFrame(() => setShown(true))
      return () => cancelAnimationFrame(r)
    }
    setShown(false)
    const t = setTimeout(() => setMounted(false), 460)
    return () => clearTimeout(t)
  }, [open])

  useEffect(() => {
    if (!mounted) return
    openCount += 1
    syncOverlay()
    return () => {
      openCount = Math.max(0, openCount - 1)
      syncOverlay()
    }
  }, [mounted])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // Move focus into the dialog on open; restore it to the opener on close.
  useEffect(() => {
    if (shown) {
      lastFocus.current = document.activeElement as HTMLElement | null
      const first = panelRef.current?.querySelector<HTMLElement>('input, button, [tabindex]')
      const t = setTimeout(() => first?.focus({ preventScroll: true }), 60)
      return () => clearTimeout(t)
    }
    lastFocus.current?.focus?.({ preventScroll: true })
    lastFocus.current = null
  }, [shown])

  const host = document.getElementById('phone')
  if (!mounted || !host) return null

  return createPortal(
    <>
      <div className="scrim" data-open={shown || undefined} onClick={onClose} />
      <div
        ref={panelRef}
        className={`sheet ${dir === 'right' ? 'right' : ''}`}
        data-open={shown || undefined}
        role="dialog"
        aria-modal="true"
        aria-hidden={!shown}
      >
        {children}
      </div>
    </>,
    host,
  )
}
