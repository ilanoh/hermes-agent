import test from 'node:test';
import assert from 'node:assert/strict';

import { checkableNumber } from './phone_check.js';

test('keeps the digits of a formatted international number', () => {
  assert.equal(checkableNumber('+33 6 12 34 56 78'), '33612345678');
  assert.equal(checkableNumber('972-54-123-4567'), '972541234567');
});

test('refuses a number too short or too long for E.164', () => {
  assert.equal(checkableNumber('1234567'), null);
  assert.equal(checkableNumber('1234567890123456'), null);
});

test('refuses an empty or missing value', () => {
  assert.equal(checkableNumber(''), null);
  assert.equal(checkableNumber(undefined), null);
  assert.equal(checkableNumber('abc'), null);
});
