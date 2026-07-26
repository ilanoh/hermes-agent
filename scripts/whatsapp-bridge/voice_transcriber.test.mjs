import test from 'node:test';
import assert from 'node:assert/strict';

import { createVoiceTranscriber } from './voice_transcriber.js';

test('off unless a python and a model are both configured', () => {
  assert.equal(createVoiceTranscriber({ python: '/usr/bin/python3' }), null);
  assert.equal(createVoiceTranscriber({ model: '/models/whisper' }), null);
});

test('runs the script on the file with the model and returns its trimmed output', async () => {
  const runs = [];
  const transcribe = createVoiceTranscriber({
    python: '/venv/bin/python',
    model: '/models/whisper',
    run: (file, args, options, done) => { runs.push({ file, args, options }); done(null, ' shalom \n'); },
  });
  assert.equal(await transcribe('/cache/aud_1.ogg'), 'shalom');
  assert.equal(runs[0].file, '/venv/bin/python');
  assert.match(runs[0].args[0], /transcribe_voice\.py$/);
  assert.deepEqual(runs[0].args.slice(1), ['/models/whisper', '/cache/aud_1.ogg']);
});

test('a failing run rejects', async () => {
  const transcribe = createVoiceTranscriber({
    python: '/venv/bin/python', model: '/models/whisper', run: (file, args, options, done) => done(new Error('boom')),
  });
  await assert.rejects(transcribe('/cache/aud_1.ogg'), /boom/);
});
