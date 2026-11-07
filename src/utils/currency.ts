/**
 * Reusable Indian Rupee (INR) currency formatter.
 * Formats numeric monetary amounts with the Indian numbering system and the ₹ symbol.
 */
export const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Formats any monetary value into INR string (e.g. ₹260.00).
 * Handles numbers, numeric strings, null, and undefined safely.
 */
export function formatINR(amount: number | string | null | undefined): string {
  if (amount === null || amount === undefined || amount === '') {
    return inrFormatter.format(0);
  }
  const numeric = typeof amount === 'number' ? amount : Number(amount);
  if (Number.isNaN(numeric)) {
    return inrFormatter.format(0);
  }
  return inrFormatter.format(numeric);
}

export default formatINR;
