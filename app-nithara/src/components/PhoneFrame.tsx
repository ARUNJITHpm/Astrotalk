import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { Icon } from './Icon'
import { useT } from '../i18n'
import { useOnline } from '../lib/online'

// The fixed 432px device frame from the prototype (.stage centres .phone). On a
// real phone it fills the screen; on desktop it sits centred on the grey stage.
//
// The whole Malayalam type system is gated on `.phone[data-lang="ml"]` in
// globals.css (it swaps --ui/--serif to Anek Malayalam and adjusts leading), so
// the current language must be mirrored onto the element — matching the
// prototype's applyLang() which sets $('#phone').dataset.lang. We also keep
// <html lang> in sync for a11y.
export function PhoneFrame({ children }: { children: ReactNode }) {
  const { t: T, lang } = useT()
  const online = useOnline()
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])
  return (
    <div className="stage">
      <div className="phone" id="phone" data-lang={lang} data-offline={!online || undefined}>
        {/* The service worker precaches the shell, so the app opens with no
            network — and then every screen sits on a failed query. Without
            this it looks broken rather than disconnected. A strip, not a
            toast: the state persists, and a notice that fades leaves the
            empty screens after it unexplained.

            `data-offline` on the frame is what makes room for it — screens and
            sheets are absolutely positioned, so the strip would otherwise sit
            on top of their first 35px rather than above them. */}
        {!online && (
          <div className="offbar" role="status">
            <Icon name="i-globe" cls="ic sm" />
            {T('offlineNote')}
          </div>
        )}
        {children}
      </div>
    </div>
  )
}
