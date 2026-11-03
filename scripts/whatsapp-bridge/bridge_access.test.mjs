import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, writeFileSync, symlinkSync } from 'fs';
import { tmpdir } from 'os';
import path from 'path';

import { createTokenGuard, resolveSendablePath } from './bridge_access.js';

const run = (guard, authorization) => {
  let status = 200;
  let passed = false;
  const res = { status(code) { status = code; return { json() {} }; } };
  guard({ headers: authorization ? { authorization } : {} }, res, () => { passed = true; });
  return { status, passed };
};

test('token guard is a no-op without a token', () => {
  assert.equal(run(createTokenGuard(''), undefined).passed, true);
});

test('token guard accepts the right bearer only', () => {
  const guard = createTokenGuard('s3cret');
  assert.equal(run(guard, 'Bearer s3cret').passed, true);
  assert.deepEqual(run(guard, 'Bearer wrong'), { status: 401, passed: false });
  assert.deepEqual(run(guard, 's3cret'), { status: 401, passed: false });
  assert.deepEqual(run(guard, undefined), { status: 401, passed: false });
});

test('sendable path stays inside the spool folder, symlinks resolved', () => {
  const root = mkdtempSync(path.join(tmpdir(), 'bridge-access-'));
  const spool = path.join(root, 'spool');
  const outside = path.join(root, 'secret.txt');
  const inside = path.join(spool, 'photo.jpg');
  const link = path.join(spool, 'link.txt');
  mkdirSync(spool);
  writeFileSync(outside, 'x');
  writeFileSync(inside, 'x');
  symlinkSync(outside, link);
  assert.ok(resolveSendablePath(inside, spool).endsWith('photo.jpg'));
  assert.equal(resolveSendablePath(outside, spool), null);
  assert.equal(resolveSendablePath(link, spool), null);
  assert.equal(resolveSendablePath(path.join(spool, '..', 'secret.txt'), spool), null);
  assert.equal(resolveSendablePath(path.join(spool, 'missing.jpg'), spool), null);
  assert.ok(resolveSendablePath(outside, '').endsWith('secret.txt'));
});
