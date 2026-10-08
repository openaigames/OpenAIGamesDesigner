// All engines record elapsed real time, including pauses and time-scale changes.
const token = /^[A-Za-z0-9_.:/-]{1,120}$/;
const text = (v, name) => { if (typeof v !== 'string' || !v.trim() || v.length > 300 || /[\x00-\x1f]/.test(v)) throw Error(`Invalid ${name}`); return v; };
export class ActionRecorder {
  constructor(metadata, {now = () => performance.now() / 1000, maxEvents = 10000} = {}) {
    if (!['threejs', 'phaser', 'web'].includes(metadata.engine)) throw Error('Invalid engine');
    for (const key of ['action', 'revision', 'source', 'engine_version', 'input_description']) text(metadata[key], key);
    if (!['human', 'software', 'mixed', 'unknown'].includes(metadata.input_mode)) throw Error('Invalid input_mode');
    if (!Number.isInteger(maxEvents) || maxEvents < 1 || maxEvents > 10000) throw Error('Invalid maxEvents');
    this.metadata = {...metadata}; this.now = now; this.maxEvents = maxEvents; this.active = false; this.cleanups = [];
  }
  start() {
    if (this.active) throw Error('Finish the current recording first');
    this.startTime = this.now(); this.last = 0; this.events = []; this.counts = new Map(); this.dropped = 0; this.active = true; this.result = null;
    return this;
  }
  record(track, event, uncertainty = 0) {
    if (!this.active) return null;
    if (!token.test(track) || !token.test(event) || !Number.isFinite(uncertainty) || uncertainty < 0) throw Error('Invalid event');
    if (this.events.length >= this.maxEvents) { this.dropped++; return null; }
    const t = this.now() - this.startTime;
    if (!Number.isFinite(t) || t < this.last) throw Error('Recording clock moved backwards');
    const key = track + '\n' + event, n = (this.counts.get(key) || 0) + 1;
    this.counts.set(key, n); this.last = t;
    const row = {track, id: `${event}#${n}`, t_s: t, uncertainty_s: uncertainty}; this.events.push(row); return row.id;
  }
  stop(complete = true) {
    if (!this.active) { if (!this.result) throw Error('No recording'); return structuredClone(this.result); }
    const duration = this.now() - this.startTime;
    if (!Number.isFinite(duration) || duration < this.last) throw Error('Invalid recording duration');
    this.active = false;
    for (const cleanup of this.cleanups.splice(0)) cleanup();
    this.result = {...this.metadata, schema: 'action-events/1', clock: 'monotonic_seconds', zero_s: 0,
      duration_s: duration, complete: Boolean(complete), dropped_events: this.dropped, events: this.events.map(x => ({...x}))};
    return structuredClone(this.result);
  }
  download(filename = 'action-events.json') {
    if (this.active || !this.result) throw Error('Stop recording before export');
    const url = URL.createObjectURL(new Blob([JSON.stringify(this.result, null, 2)], {type: 'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export function observeThreeMixer(recorder, mixer, track = 'animation') {
  const onFinish = () => recorder.record(track, 'finished');
  const onLoop = () => recorder.record(track, 'loop');
  mixer.addEventListener('finished', onFinish); mixer.addEventListener('loop', onLoop);
  let disposed = false;
  const dispose = () => { if (disposed) return; disposed = true; mixer.removeEventListener('finished', onFinish); mixer.removeEventListener('loop', onLoop); };
  recorder.cleanups.push(dispose); return dispose;
}

export function observePhaserSprite(recorder, scene, sprite, track = 'animation') {
  const onStart = () => recorder.record(track, 'started');
  const onComplete = () => recorder.record(track, 'finished');
  const onShutdown = () => { recorder.record('lifecycle', 'scene_shutdown'); if (recorder.active) recorder.stop(false); dispose(); };
  sprite.on('animationstart', onStart); sprite.on('animationcomplete', onComplete); scene.events.once('shutdown', onShutdown);
  let disposed = false;
  const dispose = () => { if (disposed) return; disposed = true; sprite.off('animationstart', onStart); sprite.off('animationcomplete', onComplete); scene.events.off('shutdown', onShutdown); };
  recorder.cleanups.push(dispose); return dispose;
}
