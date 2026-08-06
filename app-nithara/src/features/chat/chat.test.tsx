// A chat exchange.
//
// The plan (Part 8) asked for one, and the thing worth pinning is not that a
// bubble appears — it is that the app never puts words in Nithara's mouth. The
// prototype shipped scripted replies; every one of these asserts the real
// route was called and the real answer shown.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ChatSheet } from './ChatSheet'

const REPLY = 'ഇന്ന് നല്ല നേരം രാവിലെ 6:30 മുതൽ.'

let posts: { url: string; body: Record<string, unknown> }[] = []
let status = 200

function json(body: unknown, code = 200) {
  return {
    ok: code >= 200 && code < 300,
    status: code,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response
}

beforeEach(() => {
  posts = []
  status = 200
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      if ((init.method ?? 'GET') !== 'GET') {
        posts.push({ url: String(url), body: JSON.parse(String(init.body ?? '{}')) })
        return status === 200 ? json({ reply: REPLY }) : json({ detail: 'nope' }, status)
      }
      return json([])
    }),
  )
})

afterEach(() => {
  // Unmount BEFORE the host is removed. React's portal cleanup needs the node
  // it rendered into to still exist, and a tree left mounted fights the next
  // test's render for the #phone element.
  cleanup()
  vi.restoreAllMocks()
  document.querySelectorAll('#phone').forEach((el) => el.remove())
})

/** Render the sheet and wait until it is actually interactive.
 *
 *  Sheet sets aria-hidden until a requestAnimationFrame clears it, and
 *  getByRole skips aria-hidden subtrees — so a test that clicks straight after
 *  render finds no buttons at all, intermittently, depending on how many
 *  microtasks the previous line happened to await. Waiting for the dialog is
 *  the honest fix.
 */
async function openChat() {
  const result = renderChat()
  await screen.findByRole('dialog')
  // Sheet moves focus into the dialog 60ms after it opens. That lands in the
  // MIDDLE of userEvent's typing and steals the input — the outgoing bubble
  // came out as "h". A human types after the sheet has settled; this waits for
  // the same thing.
  await waitFor(() => expect(document.activeElement).not.toBe(document.body))
  return result
}

function renderChat() {
  // Clear any host a previous test left behind: Sheet portals into the FIRST
  // #phone it finds, and a stale one means the sheet renders into a detached
  // node and every query comes back empty.
  document.querySelectorAll('#phone').forEach((el) => el.remove())
  const host = document.createElement('div')
  host.id = 'phone'
  document.body.appendChild(host)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ChatSheet open onClose={() => {}} />
    </QueryClientProvider>,
  )
}

describe('asking Nithara something', () => {
  it('sends the question to the real brain and shows the real answer', async () => {
    // The prototype answered from a script. Nothing here may invent a reply:
    // this is the same POST /chat/message the WhatsApp path uses.
    const user = userEvent.setup()
    await openChat()
    const box = screen.getByPlaceholderText(/Ask Nithara/i)
    await user.type(box, 'ഇന്നത്തെ നല്ല നേരം?')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(screen.getByText(REPLY)).toBeVisible())
    // The route takes the whole thread, so the brain has the context the
    // WhatsApp path gives it. The last user turn is what was just typed.
    const call = posts.find((p) => p.url.includes('/chat/message'))
    expect(call).toBeTruthy()
    const messages = call!.body.messages as { role: string; content: string }[]
    expect(messages[messages.length - 1]).toMatchObject({
      role: 'user',
      content: 'ഇന്നത്തെ നല്ല നേരം?',
    })
  })

  it('echoes what was asked, so the thread reads as a conversation', async () => {
    const user = userEvent.setup()
    await openChat()
    await user.type(screen.getByPlaceholderText(/Ask Nithara/i), 'hello')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    await waitFor(() => expect(screen.getByText('hello')).toBeVisible())
  })

  it('says something went wrong rather than inventing an answer', async () => {
    // The failure mode that matters. A chat UI that silently drops a failed
    // turn looks like Nithara ignored the question.
    status = 500
    const user = userEvent.setup()
    await openChat()
    await user.type(screen.getByPlaceholderText(/Ask Nithara/i), 'hello')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(screen.getByRole('alert')).toBeVisible())
    expect(screen.queryByText(REPLY)).toBeNull()
  })

  it('does not send an empty message', async () => {
    const user = userEvent.setup()
    await openChat()
    await user.click(screen.getByRole('button', { name: 'Send' }))
    expect(posts.some((p) => p.url.includes('/chat/message'))).toBe(false)
  })
})
