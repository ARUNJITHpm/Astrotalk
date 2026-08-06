// The screens Part 13 carried over from /admin, /console and /whatsapp.
//
// What is worth testing here is not that the panels render — it is that they
// tell the truth about a system where half the integrations are stand-ins. Most
// of these assertions are about a warning appearing, or a misleading button
// NOT appearing.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import type { ContentPost } from '../api/content'
import { AuthProvider, type Me } from '../lib/auth'

const OWNER: Me = { operator_id: null, roles: ['owner'], temple_ids: [], is_owner: true }

function post(over: Partial<ContentPost> = {}): ContentPost {
  return {
    id: 1,
    day: '2026-07-28',
    platform: 'wa_channel',
    kind: 'panchangam',
    body: 'ഇന്നത്തെ പഞ്ചാംഗം',
    media_key: null,
    media_url: null,
    status: 'approved',
    external_id: null,
    created_at: '2026-07-28T02:00:00Z',
    published_at: null,
    ...over,
  }
}

interface Call {
  url: string
  method: string
  body: unknown
}
let calls: Call[] = []

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as Response
}

function stubApi(opts: { posts?: ContentPost[]; whatsappLive?: boolean } = {}) {
  return vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET'
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body
    calls.push({ url: String(url), method, body })

    if (url.includes('/admin/operators/me')) return jsonResponse(OWNER)
    if (url.includes('/admin/integrations')) {
      return jsonResponse({
        app_env: 'production',
        integrations: { whatsapp: opts.whatsappLive ?? false },
      })
    }
    if (url.includes('/admin/overview')) {
      return jsonResponse({
        generated_at: '2026-07-28T06:00:00Z',
        system: {
          app_env: 'production',
          chat_provider: 'sarvam',
          session_ttl_hours: 47,
          chat_rate_limit_per_hour: 30,
          integrations: {
            llm: true,
            ephemeris: true,
            whatsapp: opts.whatsappLive ?? false,
            razorpay: false,
          },
          api_keys_present: { openai: true, sarvam: true, geocoding: false },
        },
        users: {},
        chat: {},
        llm: {},
      })
    }
    if (url.includes('/content/posts')) {
      if (method === 'GET') return jsonResponse(opts.posts ?? [post()])
      return jsonResponse(post({ status: 'approved' }))
    }
    if (url.includes('/content/run-daily')) {
      return jsonResponse({ day: '2026-07-28', created: [], skipped: ['wa_channel'] })
    }
    if (url.includes('/whatsapp/simulate')) {
      return jsonResponse({ reply: 'നമസ്കാരം 🙏' })
    }
    if (url.includes('/admin/users-chats')) {
      return jsonResponse([
        { phone: '+919812345678', name: 'Ananya Nair', turns: 4, last_active: '2026-07-27T10:00:00Z' },
      ])
    }
    if (url.includes('/admin/user-chat/')) {
      return jsonResponse([
        {
          user_id: '+919812345678',
          conversation_id: 'c1',
          messages: [
            { role: 'system', content: 'You are Tara…' },
            { role: 'user', content: 'എന്റെ നക്ഷത്രം ഏതാണ്?' },
          ],
          reply: 'നിങ്ങളുടെ നക്ഷത്രം തിരുവോണം.',
          created_at: '2026-07-27T10:00:00Z',
          llm_provider: 'sarvam',
          llm_model: 'sarvam-m',
          prompt_tokens: 100,
          completion_tokens: 20,
          total_tokens: 120,
          price_inr: null,
          price_usd: null,
        },
      ])
    }
    if (url.includes('/notifications/run-festivals')) {
      return jsonResponse({ target_day: '2026-07-31', festivals: 2, sent: 12, skipped: 1 })
    }
    return jsonResponse([])
  })
}

function renderAt(path: string, opts?: { posts?: ContentPost[]; whatsappLive?: boolean }) {
  sessionStorage.setItem('nithara.console.token', 'the-admin-token')
  sessionStorage.setItem('nithara.console.token_kind', 'admin_token')
  vi.stubGlobal('fetch', stubApi(opts))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  sessionStorage.clear()
  calls = []
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the daily pack', () => {
  it('warns that publishing to Facebook does not reach Facebook', async () => {
    renderAt('/content/daily', { posts: [post({ platform: 'fb_post' })], whatsappLive: true })
    expect(await screen.findByRole('heading', { name: 'Facebook' })).toBeVisible()
    await waitFor(() =>
      expect(screen.getByText(/cannot post to Facebook/i)).toBeVisible(),
    )
  })

  it('warns that a WhatsApp publish is only logged when WhatsApp is mocked', async () => {
    renderAt('/content/daily', { whatsappLive: false })
    await waitFor(() => expect(screen.getByText(/log, not sent/i)).toBeVisible())
  })

  it('says nothing extra when the button does what it says', async () => {
    renderAt('/content/daily', { whatsappLive: true })
    expect(await screen.findByRole('button', { name: 'Publish' })).toBeVisible()
    expect(screen.queryByText(/log, not sent/i)).toBeNull()
    expect(screen.queryByText(/cannot post to/i)).toBeNull()
  })

  it('does not offer publish on a draft the server would refuse', async () => {
    renderAt('/content/daily', { posts: [post({ status: 'draft' })] })
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Publish' })).toBeNull()
  })

  it('gives a failed piece its way back', async () => {
    renderAt('/content/daily', { posts: [post({ status: 'failed' })] })
    expect(await screen.findByRole('button', { name: 'Approve again' })).toBeVisible()
    expect(screen.getByText(/did not go through/i)).toBeVisible()
  })

  it('sends an edited body with the approval, and nothing when untouched', async () => {
    const user = userEvent.setup()
    renderAt('/content/daily', { posts: [post({ status: 'draft' })] })
    const box = await screen.findByRole('textbox')

    await user.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() =>
      expect(calls.find((c) => c.url.includes('/approve'))?.body).toEqual({}),
    )

    calls = []
    await user.clear(box)
    await user.type(box, 'corrected')
    await user.click(screen.getByRole('button', { name: 'Save the edit and approve' }))
    await waitFor(() =>
      expect(calls.find((c) => c.url.includes('/approve'))?.body).toEqual({
        body: 'corrected',
      }),
    )
  })

  it('reads an idempotent second run as "already done", not as a failure', async () => {
    const user = userEvent.setup()
    renderAt('/content/daily')
    await user.click(await screen.findByRole('button', { name: 'Draft the pack' }))
    await waitFor(() => expect(screen.getByText(/nothing new was created/i)).toBeVisible())
  })
})

describe('the WhatsApp simulator', () => {
  it('will not send until a number has been chosen', async () => {
    renderAt('/channels/whatsapp')
    expect(await screen.findByRole('heading', { name: 'Send as which number?' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Use this number' })).toBeDisabled()
  })

  it('sends the phone in the body and shows the reply as a bubble', async () => {
    const user = userEvent.setup()
    renderAt('/channels/whatsapp')
    await user.type(await screen.findByPlaceholderText('+91 98765 43210'), '+919812345678')
    await user.click(screen.getByRole('button', { name: 'Use this number' }))

    await user.type(screen.getByPlaceholderText('Message'), 'hello')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    await waitFor(() => expect(screen.getByText('നമസ്കാരം 🙏')).toBeVisible())
    const sent = calls.find((c) => c.url.includes('/whatsapp/simulate'))
    expect(sent?.body).toEqual({ phone: '+919812345678', text: 'hello' })
    // The number must never be in the URL — it identifies a person and the
    // conversation is theirs.
    expect(sent?.url).not.toMatch(/9812345678/)
  })

  it('keeps the helpline on screen', async () => {
    renderAt('/channels/whatsapp')
    expect(await screen.findByText(/Tele-MANAS 14416/)).toBeVisible()
  })

  it('says out loud that this moves a real conversation along', async () => {
    renderAt('/channels/whatsapp')
    expect(await screen.findByText(/Use a test number/i)).toBeVisible()
  })
})

describe('notifications', () => {
  it('will not let a mocked run be quoted as delivery', async () => {
    const user = userEvent.setup()
    renderAt('/channels/notifications', { whatsappLive: false })
    await waitFor(() => expect(screen.getByText(/WhatsApp is mocked/i)).toBeVisible())

    await user.click((await screen.findAllByRole('button', { name: 'Run it now' }))[0])
    await waitFor(() => expect(screen.getByText(/no message was delivered/i)).toBeVisible())
  })

  it('warns before the button is pressed when WhatsApp is live', async () => {
    renderAt('/channels/notifications', { whatsappLive: true })
    await waitFor(() => expect(screen.getByText(/sends real messages/i)).toBeVisible())
  })
})

describe('integrations', () => {
  it('names what a mocked service costs, in the operator’s terms', async () => {
    renderAt('/system/integrations')
    expect(await screen.findByRole('heading', { name: 'Integrations' })).toBeVisible()
    await waitFor(() =>
      expect(screen.getByText(/Payments complete without any money moving/i)).toBeVisible(),
    )
    expect(screen.getByText(/2 services are mocked/i)).toBeVisible()
  })

  it('reports whether a credential is set, never what it is', async () => {
    renderAt('/system/integrations')
    await waitFor(() => expect(screen.getByText('openai')).toBeVisible())
    // The overview payload carries booleans only; nothing on screen should look
    // like a secret.
    expect(screen.queryByText(/sk-/)).toBeNull()
  })
})

describe('the chat explorer', () => {
  it('shows what they asked and what Tara answered', async () => {
    const user = userEvent.setup()
    renderAt('/system/chat')
    expect(await screen.findByText('Ananya Nair')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Read' }))

    await waitFor(() => expect(screen.getByText('എന്റെ നക്ഷത്രം ഏതാണ്?')).toBeVisible())
    expect(screen.getByText('നിങ്ങളുടെ നക്ഷത്രം തിരുവോണം.')).toBeVisible()
  })

  it('does not print our own system prompt into the transcript', async () => {
    const user = userEvent.setup()
    renderAt('/system/chat')
    await user.click(await screen.findByRole('button', { name: 'Read' }))
    await waitFor(() => expect(screen.getByText(/തിരുവോണം/)).toBeVisible())
    expect(screen.queryByText(/You are Tara/)).toBeNull()
  })

  it('offers no way to reply', async () => {
    // A support operator finds out what happened. The moment a console can post
    // into somebody's conversation, the transcript stops being evidence.
    const user = userEvent.setup()
    renderAt('/system/chat')
    await user.click(await screen.findByRole('button', { name: 'Read' }))
    await waitFor(() => expect(screen.getByText(/തിരുവോണം/)).toBeVisible())
    expect(screen.queryByRole('button', { name: /reply|send/i })).toBeNull()
  })
})

describe('settings', () => {
  it('never shows the shared admin token', async () => {
    renderAt('/system/settings')
    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeVisible()
    await waitFor(() => expect(screen.getByText(/X-Admin-Token/)).toBeVisible())
    expect(screen.queryByText('the-admin-token')).toBeNull()
  })

  it('describes permissions from the table the guard actually reads', async () => {
    renderAt('/system/settings')
    const table = (await screen.findAllByRole('table'))[0]
    // Channels is owner-only, so every other role gets an em dash.
    const row = within(table)
      .getAllByRole('row')
      .find((r) => within(r).queryByText('Channels'))
    expect(row).toBeTruthy()
    const cells = within(row as HTMLElement).getAllByRole('cell')
    expect(cells[1]).toHaveTextContent('all') // owner
    expect(cells[2]).toHaveTextContent('—') // temple_admin
  })
})
