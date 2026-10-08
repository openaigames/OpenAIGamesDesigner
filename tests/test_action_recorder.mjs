import assert from 'node:assert/strict';
import {ActionRecorder,observeThreeMixer,observePhaserSprite} from '../adapters/engines/action_timing/web/action-recorder.mjs';
import {EventEmitter} from 'node:events';
let clock=0;
const metadata={engine:'web',engine_version:'unit',action:'test',revision:'one',source:'unit test',input_mode:'software',input_description:'unit callbacks'};
const create=(options={})=>new ActionRecorder(metadata,{now:()=>clock,...options}).start();
const r=create();r.record('logic','commit');clock=.5;r.record('logic','commit');clock=1;
const result=r.stop();assert.deepEqual(result.events.map(e=>e.id),['commit#1','commit#2']);assert.equal(result.events[1].t_s,.5);
assert.equal(r.record('logic','after_stop'),null);assert.equal(result.duration_s,1);
result.events[0].id='changed';assert.equal(r.stop().events[0].id,'commit#1');
r.start();assert.equal(r.record('logic','commit'),'commit#1');assert.throws(()=>r.start());r.stop(false);
const limited=create({maxEvents:1});limited.record('logic','first');limited.record('logic','dropped');assert.equal(limited.stop().dropped_events,1);
const invalid=create();assert.throws(()=>invalid.record('logic','bad#1'));assert.throws(()=>invalid.record('logic','good',NaN));clock=-1;assert.throws(()=>invalid.record('logic','backwards'));clock=2;invalid.stop();
class Mixer extends EventEmitter { addEventListener(...a){this.on(...a)} removeEventListener(...a){this.off(...a)} }
const mixer=new Mixer(), t=create();observeThreeMixer(t,mixer);mixer.emit('finished');assert.equal(t.stop().events[0].id,'finished#1');assert.equal(mixer.listenerCount('finished'),0);
const sprite=new EventEmitter(),scene={events:new EventEmitter()},p=create();observePhaserSprite(p,scene,sprite);sprite.emit('animationstart');scene.events.emit('shutdown');assert.equal(p.stop().complete,false);assert.equal(sprite.listenerCount('animationstart'),0);assert.equal(scene.events.listenerCount('shutdown'),0);
console.log('PASS: repeat identities, independent snapshots, clock guards, overflow, stopped recording, Three/Phaser listener cleanup. These are unit checks; native browser fixtures run separately.');
