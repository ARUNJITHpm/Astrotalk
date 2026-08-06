import { useQuery } from '@tanstack/react-query'
import { apiGet, qs } from './client'
import { useEffect } from 'react'

import { currentPosition } from '../lib/native'
import { recallTemple, rememberTemple } from '../lib/lastTemple'
import type {
  Booking,
  FeedItem,
  Member,
  Milestone,
  NakshatramDay,
  Panchangam,
  BirthDetails,
  Chart,
  PoojaCatalogue,
  Stats,
  Temple,
  TempleDetail,
} from './types'

// Until device geolocation (Part 9), distances are computed from a default
// location (Thrissur — the prototype's ME). The backend does the haversine.
export const DEFAULT_LOC = { lat: 10.523, lng: 76.216 }

export interface TempleQuery {
  q?: string
  by?: 'name' | 'place'
  deity?: string
  lat?: number
  lng?: number
  sort?: 'near' | 'rating'
  limit?: number
}

export function useTemples(params: TempleQuery = {}) {
  return useQuery({
    queryKey: ['temples', params],
    queryFn: () =>
      apiGet<Temple[]>('/temples' + qs(params as Record<string, string | number | undefined>)),
  })
}

/**
 * The device's position, asked for ONLY when `enabled`.
 *
 * Never on app open. A permission dialog that appears before the person has
 * asked for anything is the prompt everybody denies, and a denial is sticky —
 * so the ask is attached to an action that means "near me" (the location chip,
 * the onboarding nearby list) where the reason is obvious.
 */
export function useDeviceLocation(enabled: boolean) {
  return useQuery({
    queryKey: ['device-location'],
    enabled,
    // A refusal is an answer, not a failure to retry into.
    retry: false,
    staleTime: 10 * 60 * 1000,
    queryFn: currentPosition,
  })
}

/**
 * Nearby temples, nearest first (the home + map default).
 *
 * Falls back to a fixed point in Thrissur when there is no device position —
 * which is most of the time, and deliberately so. The list is curated either
 * way; what changes is whether "nearest" means nearest to you.
 */
export function useNearbyTemples(limit = 200, from?: { lat: number; lng: number } | null) {
  const origin = from ?? DEFAULT_LOC
  return useTemples({ lat: origin.lat, lng: origin.lng, sort: 'near', limit })
}

export function useTemple(id: string | undefined | null) {
  const query = useQuery({
    queryKey: ['temple', id],
    queryFn: () => apiGet<TempleDetail>(`/temples/${id}`),
    enabled: !!id,
    // Seeds the first render from the last temple kept across launches, so the
    // app opened offline shows the timings instead of an empty hero. The
    // network answer replaces it as soon as one arrives — this is a cache, not
    // a source of truth, and stale timings shown as current would be worse than
    // a spinner.
    placeholderData: () => recallTemple(id) ?? undefined,
  })

  useEffect(() => {
    if (query.data && !query.isPlaceholderData) rememberTemple(query.data)
  }, [query.data, query.isPlaceholderData])

  return query
}

export function useTemplePoojas(id: string | undefined | null, nak?: number) {
  return useQuery({
    queryKey: ['temple-poojas', id, nak ?? null],
    queryFn: () => apiGet<PoojaCatalogue>(`/temples/${id}/poojas` + qs({ nak })),
    enabled: !!id,
  })
}

export function useFeed(params: { temple_id?: string; cat?: string } = {}) {
  return useQuery({
    queryKey: ['feed', params],
    queryFn: () => apiGet<FeedItem[]>('/feed' + qs(params)),
  })
}

export function usePanchangam() {
  return useQuery({
    queryKey: ['panchangam'],
    queryFn: () => apiGet<Panchangam>('/astrology/panchangam'),
  })
}

export function useNakshatramNext(naks: number[]) {
  return useQuery({
    queryKey: ['nakshatram-next', naks],
    queryFn: () =>
      apiGet<NakshatramDay[]>(
        '/astrology/nakshatram/next' + (naks.length ? '?' + naks.map((n) => `nak=${n}`).join('&') : ''),
      ),
    enabled: naks.length > 0,
  })
}

// ---- authed (anon or account) surfaces ----

/**
 * The signed-in account's natal chart, or null when it has none.
 *
 * A 404 is the ordinary state, not an error: Nithara accounts start anonymous
 * and birth details are optional, so most accounts have no chart and the
 * profile offers to make one. Token-scoped — no account id in the URL.
 */
export function useChart() {
  return useQuery({
    queryKey: ['chart'],
    queryFn: async () => {
      try {
        return await apiGet<Chart>('/identity/me/chart')
      } catch (err) {
        if ((err as { status?: number })?.status === 404) return null
        throw err
      }
    },
  })
}

/** The three fields behind the chart, read back so a typo in one does not mean
 *  retyping all three. Fetched only when the edit sheet opens. */
export function useBirthDetails(enabled: boolean) {
  return useQuery({
    queryKey: ['birth'],
    enabled,
    queryFn: () => apiGet<BirthDetails>('/identity/me/birth'),
  })
}

export function useMembers() {
  return useQuery({ queryKey: ['members'], queryFn: () => apiGet<Member[]>('/identity/me/members') })
}

export function useBookings() {
  return useQuery({ queryKey: ['bookings'], queryFn: () => apiGet<Booking[]>('/bookings') })
}

export function useStats() {
  return useQuery({ queryKey: ['stats'], queryFn: () => apiGet<Stats>('/identity/me/stats') })
}

export function useMilestones() {
  return useQuery({ queryKey: ['milestones'], queryFn: () => apiGet<Milestone[]>('/identity/me/milestones') })
}
