import { useEffect, useState } from 'react'
import { Icon } from './Icon'

// A tiny global toast, matching the prototype's toast(msg). Fire from anywhere:
//   import { toast } from '../components/Toast'; toast('Saved')
type Listener = (msg: string) => void
let listener: Listener | null = null

export function toast(message: string) {
  listener?.(message)
}

export function ToastHost() {
  const [msg, setMsg] = useState('')
  const [show, setShow] = useState(false)

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    listener = (m: string) => {
      setMsg(m)
      setShow(true)
      clearTimeout(timer)
      timer = setTimeout(() => setShow(false), 2400)
    }
    return () => {
      listener = null
      clearTimeout(timer)
    }
  }, [])

  return (
    <div className="toast" id="toast" role="status" aria-live="polite" data-show={show || undefined}>
      <Icon name="i-check" cls="ic sm" />
      <span>{msg}</span>
    </div>
  )
}
