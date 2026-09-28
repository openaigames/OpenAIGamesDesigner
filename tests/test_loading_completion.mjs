import assert from 'node:assert/strict';
import {loadingCompletion} from '../tools/workbench/web/loading-completion.js';
const manager={itemStart(){},itemEnd(){}};
const ready=loadingCompletion(manager);
await ready(); // a coalesced/cached request never invokes this manager
manager.itemStart('texture-a');manager.itemStart('texture-b');
let completed=false;const pending=ready().then(()=>completed=true);
manager.itemEnd('texture-a');await Promise.resolve();assert.equal(completed,false);
manager.itemEnd('texture-b');await pending;assert.equal(completed,true);
await ready();
console.log('Loading completion: coalesced request and outstanding texture dependencies passed.');
