import { apiPost } from '../api/client'
import { getToken, setToken } from './session'

// The "no sign-up" promise: on first run the app mints an anonymous session
// (POST /identity/anon) so check-ins, bookings and the family board work without
// an account.
//
// SECURITY: the account key is minted by the SERVER and is deliberately
// digit-free — a client-chosen key would let anyone claim an admin session or
// resolve to a real user's phone number. We only ever store and echo back what
// the server gave us; we never invent one.

const ANON_KEY = 'nithara.anon_id'

interface AnonResponse {
  token: string
  anon_id: string
}

async function mint(): Promise<void> {
  const stored = localStorage.getItem(ANON_KEY)
  const res = await apiPost<AnonResponse>('/identity/anon', stored ? { anon_id: stored } : {})
  localStorage.setItem(ANON_KEY, res.anon_id)
  setToken(res.token)
}

/** Ensure a bearer token exists (mint/resume an anon session if not). */
export async function ensureSession(): Promise<void> {
  if (getToken()) return
  await mint()
}

/** Re-authenticate after a 401 (the 47h session expired). Resumes the SAME
 *  anonymous account via the stored key, so bookings and family stay intact. */
export async function refreshSession(): Promise<void> {
  setToken(null)
  await mint()
}
