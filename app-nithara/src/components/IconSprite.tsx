// The prototype's inline SVG symbol sheet, extracted verbatim (31 symbols) and
// injected once so every <Icon> can reference #i-… by id.
import sprite from './sprite.svg?raw'

export function IconSprite() {
  return (
    <div
      aria-hidden="true"
      style={{ display: 'none' }}
      dangerouslySetInnerHTML={{ __html: sprite }}
    />
  )
}
