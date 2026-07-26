/**
 * Transcribes a WhatsApp voice note with a local Whisper model, for the inbound
 * webhook routing: a person on the server's numbers list who answers by voice
 * is read like one who types.
 *
 * Runs transcribe_voice.py with a Python that has faster-whisper installed,
 * as the bridge's own account, on the CPU. The model is a local folder, so
 * nothing is downloaded and no audio leaves the machine.
 *
 * Off unless both are set:
 *   WHATSAPP_INBOUND_WHISPER_PYTHON  python executable with faster-whisper
 *   WHATSAPP_INBOUND_WHISPER_MODEL   folder of a CTranslate2 Whisper model
 */

import { execFile } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const SCRIPT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'transcribe_voice.py');
// A minute of speech takes well under this on four cores.
const TIMEOUT_MS = 5 * 60 * 1000;

/**
 * @returns {((filePath: string) => Promise<string>) | null} the transcriber, or null when it is not configured
 */
export function createVoiceTranscriber({ python = '', model = '', run = execFile, timeoutMs = TIMEOUT_MS } = {}) {
  if (!python || !model) {
    return null;
  }
  return (filePath) => new Promise((resolve, reject) => {
    run(python, [SCRIPT, model, filePath], { timeout: timeoutMs, maxBuffer: 1024 * 1024 }, (err, stdout) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(String(stdout).trim());
    });
  });
}
