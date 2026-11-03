/**
 * The number GET /check/:number asks WhatsApp about: its digits, country code
 * first, 8 to 15 of them (E.164). Anything else is refused before WhatsApp is
 * asked, so the route only ever queries a well formed number.
 */

const MIN_DIGITS = 8;
const MAX_DIGITS = 15;

/** The digits of `raw`, or null when they are not a plausible international number. */
export function checkableNumber(raw) {
  const digits = String(raw ?? '').replace(/\D/g, '');
  return digits.length >= MIN_DIGITS && digits.length <= MAX_DIGITS ? digits : null;
}
