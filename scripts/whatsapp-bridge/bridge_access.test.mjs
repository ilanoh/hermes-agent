import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, writeFileSync, symlinkSync } from 'fs';
import { tmpdir } from 'os';
import path from 'path';

import { resolveSendablePath } from './bridge_access.js';

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
