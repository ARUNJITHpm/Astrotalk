import { NAKSHATRAMS, nakName } from './nakshatrams'

test('there are 27 nakshatrams, each bilingual', () => {
  expect(NAKSHATRAMS).toHaveLength(27)
  for (const [en, ml] of NAKSHATRAMS) {
    expect(en).toBeTruthy()
    expect(ml).toBeTruthy()
  }
})

test('nakName resolves by index and language, matching the backend order', () => {
  // Index 0 = Ashwathi, 3 = Rohini — the same order the API returns/accepts.
  expect(nakName(0, 'en')).toBe('Ashwathi')
  expect(nakName(3, 'en')).toBe('Rohini')
  expect(nakName(3, 'ml')).toBe('രോഹിണി')
  expect(nakName(26, 'en')).toBe('Revathi')
})

test('nakName is empty for an unset or out-of-range star', () => {
  expect(nakName(null, 'en')).toBe('')
  expect(nakName(-1, 'en')).toBe('')
  expect(nakName(27, 'en')).toBe('')
})
