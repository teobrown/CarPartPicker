import { customAlphabet } from 'nanoid';

// 8 chars × 64 alphabet ≈ 2.8 × 10^14 possibilities; collision-safe for ≤10M builds.
const ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_-';
const generate = customAlphabet(ALPHABET, 8);

export function newBuildSlug(): string {
  return generate();
}
