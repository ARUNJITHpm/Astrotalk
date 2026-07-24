import { qs } from './client'

test('qs omits empty/null/undefined values and url-encodes the rest', () => {
  expect(qs({})).toBe('')
  expect(qs({ a: 1, b: undefined, c: null, d: '', e: 'x y' })).toBe('?a=1&e=x%20y')
  expect(qs({ nak: 3 })).toBe('?nak=3')
})
