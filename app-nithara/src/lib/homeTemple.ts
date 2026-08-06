import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { apiGet, apiPut } from '../api/client'

// The chosen "home temple", kept against the ACCOUNT and cached locally.
//
// It used to live in localStorage alone, which meant clearing site data,
// reinstalling, or opening the app on a second phone silently threw away the one
// thing onboarding asks for — while the account itself survived, because it is
// keyed by a server-minted anon id. This file is now what its old comment said
// it would become: a thin cache over the server value.
//
// The cache is not vestigial. It is read synchronously on the very first render,
// before any request has finished, so a returning devotee sees their own temple
// on the home screen instead of the onboarding prompt flashing past. The server
// remains the source of truth; the local copy only ever front-runs it.

const KEY = 'nithara.home_temple'

export interface HomeTemple {
  temple_id: string | null
}

const readCache = (): string | null => {
  try {
    return localStorage.getItem(KEY)
  } catch {
    // Private mode, or storage disabled. Not worth failing over — the server
    // still knows, and this only costs one render of the wrong screen.
    //
    // It is belt-and-braces rather than real resilience: lib/session.ts keeps
    // the bearer token in localStorage with no guard, so a browser refusing
    // storage cannot authenticate at all and never reaches this code.
    return null
  }
}

const writeCache = (id: string | null): void => {
  try {
    if (id) localStorage.setItem(KEY, id)
    else localStorage.removeItem(KEY)
  } catch {
    /* see readCache */
  }
}

/**
 * The account's home temple.
 *
 * Starts from the local cache so the first paint is right, then reconciles with
 * the server. `null` means genuinely not chosen — which is what sends a new
 * devotee into onboarding.
 */
export function useHomeTempleId(): string | null {
  const cached = readCache()
  const { data } = useQuery({
    queryKey: ['home-temple'],
    queryFn: () => apiGet<HomeTemple>('/identity/me/home-temple'),
    // The cached id stands in until the request lands, so the home screen does
    // not flash onboarding at somebody who chose a temple months ago.
    placeholderData: cached ? { temple_id: cached } : undefined,
  })

  // Keep the cache honest, including when the server says the choice is gone.
  useEffect(() => {
    if (data) writeCache(data.temple_id)
  }, [data])

  return data?.temple_id ?? null
}

/** Record the choice. Writes through to the account; the cache follows. */
export async function setHomeTempleId(
  id: string,
  queryClient: ReturnType<typeof useQueryClient>,
): Promise<void> {
  writeCache(id)
  await apiPut<HomeTemple>('/identity/me/home-temple', { temple_id: id })
  await queryClient.invalidateQueries({ queryKey: ['home-temple'] })
}

/**
 * Forget the chosen temple — used when it stops resolving after a directory
 * change, so the devotee is offered onboarding again rather than staring at an
 * empty home screen.
 *
 * Clears the cache only. The account keeps its (now unresolvable) id, because
 * a temple pulled from the directory this morning may be back this afternoon,
 * and quietly erasing somebody's choice on our own data problem is worse than
 * asking them once.
 */
export function clearHomeTempleCache(): void {
  writeCache(null)
}
