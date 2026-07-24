import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { useT } from '../i18n'

// The fixed 432px device frame from the prototype (.stage centres .phone). On a
// real phone it fills the screen; on desktop it sits centred on the grey stage.
//
// The whole Malayalam type system is gated on `.phone[data-lang="ml"]` in
// globals.css (it swaps --ui/--serif to Anek Malayalam and adjusts leading), so
// the current language must be mirrored onto the element — matching the
// prototype's applyLang() which sets $('#phone').dataset.lang. We also keep
// <html lang> in sync for a11y.
export function PhoneFrame({ children }: { children: ReactNode }) {
  const { lang } = useT()
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])
  return (
    <div className="stage">
      <div className="phone" id="phone" data-lang={lang}>
        {children}
      </div>
    </div>
  )
}
