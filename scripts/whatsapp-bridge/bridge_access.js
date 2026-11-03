/**
 * File access of the bridge's loopback HTTP API.
 *
 * The bridge listens on 127.0.0.1, which every local account can reach, and
 * /send-media reads the file a caller names. Every request already carries the
 * session bearer (bridge_auth.js). One optional control, set by the adapter
 * through the environment:
 *
 *   WHATSAPP_BRIDGE_SPOOL_DIR   /send-media only sends files inside this folder; the
 *                               adapter copies each outgoing file there first
 *
 * Unset, the control is off and the bridge behaves as before.
 */

import { realpathSync } from 'fs';
import path from 'path';

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
