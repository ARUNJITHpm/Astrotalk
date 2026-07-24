// Mirrors the prototype's ic(name, cls): an <svg> referencing a sprite symbol.
export function Icon({ name, cls = 'ic' }: { name: string; cls?: string }) {
  return (
    <svg className={cls} aria-hidden="true">
      <use href={`#${name}`} />
    </svg>
  )
}
