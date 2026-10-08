import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../tools/workbench/web/display-data.js',import.meta.url),'utf8');
const {needsAttention,artDocumentForDisplay,knownMetadata}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
for(const field of ['artRegistrationError','versionError']){
  assert.equal(needsAttention({status:'succeeded',[field]:'record conflict'}),true,'Generated files still require record repair');
  assert.equal(needsAttention({status:'registered',[field]:'record conflict'}),true);
}
assert.equal(needsAttention({status:'succeeded'}),false);
assert.equal(needsAttention({status:'failed'}),true);
const doc='# 项目美术\n| 来源与许可 |\n| 已授权 |\n<!-- art-lifecycle:start -->\n```json\n{"secret_internal_field":"hidden"}\n```\n<!-- art-lifecycle:end -->\n## 制作备注\n待复查';
const shown=artDocumentForDisplay(doc);
assert(shown.includes('已授权')&&shown.includes('待复查'));
assert(!shown.includes('secret_internal_field')&&!shown.includes('```'));
assert.equal(artDocumentForDisplay('# 旧项目\n原说明'), '# 旧项目\n原说明');
assert.equal(knownMetadata('未登记'),false);
assert.equal(knownMetadata(undefined),false);
assert.equal(knownMetadata('本项目原创'),true);
console.log('12 display assertions passed');
