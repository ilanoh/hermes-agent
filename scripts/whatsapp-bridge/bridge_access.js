/**
 * Access controls of the bridge's loopback HTTP API.
 *
 * The bridge listens on 127.0.0.1, which every local account can reach, and
 * /send-media reads the file a caller names. Two optional controls, both set
 * by the adapter through the environment:
 *
 *   WHATSAPP_BRIDGE_TOKEN       every request must carry `Authorization: Bearer <token>`
 *   WHATSAPP_BRIDGE_SPOOL_DIR   /send-media only sends files inside this folder; the
 *                               adapter copies each outgoing file there first
 *
 * Unset, each control is off and the bridge behaves as before.
 */

import { createHash, timingSafeEqual } from 'crypto';
import { realpathSync } from 'fs';
import path from 'path';

const digest = (value) => createHash('sha256').update(value).digest();

/** Express middleware refusing requests without the bearer token; a no-op when token is empty. */
export function createTokenGuard(token) {
  if (!token) {
    return (req, res, next) => next();
  }
  const expected = digest(token);
  return (req, res, next) => {
    const header = req.headers.authorization || '';
    const presented = header.startsWith('Bearer ') ? header.slice('Bearer '.length) : '';
    if (!presented || !timingSafeEqual(digest(presented), expected)) {
      return res.status(401).json({ error: 'Unauthorized' });
    }
    next();
  };
}

/**
 * The real path of filePath when sending it is allowed, or null.
 * Without a spool folder every existing path is allowed (previous behaviour).
 * With one, the real path, symlinks resolved, must sit inside the spool folder.
 */
export function resolveSendablePath(filePath, spoolDir) {
  let real;
  try {
    real = realpathSync(filePath);
  } catch {
    return null;
  }
  if (!spoolDir) {
    return real;
  }
  let spool;
  try {
    spool = realpathSync(spoolDir);
  } catch {
    return null;
  }
  return real.startsWith(spool + path.sep) ? real : null;
}
