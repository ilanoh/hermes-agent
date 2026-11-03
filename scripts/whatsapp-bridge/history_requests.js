/**
 * On demand chat history from the primary phone.
 *
 * sock.fetchMessageHistory asks the phone for the messages of one chat sent
 * before an anchor message. The phone answers later through the
 * 'messaging-history.set' event with syncType ON_DEMAND, so each answer is
 * paired here with the request waiting for its chat.
 */

export function createHistoryRequests({ timeoutMs = 30000 } = {}) {
  const waiting = new Map();

  function deliver(messages) {
    for (const msg of messages || []) {
      const entry = waiting.get(msg?.key?.remoteJid);
      if (entry) {
        entry.messages.push(msg);
      }
    }
    for (const [chatJid, entry] of waiting) {
      if (entry.messages.length > 0) {
        clearTimeout(entry.timer);
        waiting.delete(chatJid);
        entry.resolve(entry.messages);
      }
    }
  }

  /** Resolves with the chat's messages from the phone's answer, or [] when none arrives in time. */
  function wait(chatJid) {
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        waiting.delete(chatJid);
        resolve([]);
      }, timeoutMs);
      waiting.set(chatJid, { resolve, timer, messages: [] });
    });
  }

  return { deliver, wait };
}
