import assert from 'node:assert/strict';
import {register} from 'node:module';
register('./three-loader.mjs',import.meta.url);
const THREE=await import('three');
const {describeRig,compatibleRig}=await import('../tools/workbench/web/rig-compatibility.js');
function makeRig({skin=true,parent=true,duplicate=false,weighted=true}={}){
 const root=new THREE.Group(),a=new THREE.Bone(),b=new THREE.Bone();a.name='root';b.name=duplicate?'root':'hand';root.add(a);(parent?a:root).add(b);
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute([0,0,0],3));
 const mesh=skin?new THREE.SkinnedMesh(geometry,new THREE.MeshBasicMaterial()):new THREE.Mesh(geometry,new THREE.MeshBasicMaterial());
 if(skin){geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute([1,0,0,0],4));geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute([weighted?1:0,0,0,0],4));mesh.bind(new THREE.Skeleton([a,b]));}
 root.add(mesh);return root;
}
const source=describeRig(makeRig({skin:false}));
assert.equal(compatibleRig(source,describeRig(makeRig())),true);
assert.equal(compatibleRig(source,describeRig(makeRig({skin:false}))),false,'static geometry must never be offered as an animation rig');
assert.equal(compatibleRig(source,describeRig(makeRig({weighted:false}))),false,'zero skin weights are not a valid deforming model');
assert.equal(compatibleRig(source,describeRig(makeRig({parent:false}))),false,'matching names with different hierarchy must be excluded');
assert.equal(compatibleRig(source,describeRig(makeRig({duplicate:true}))),false,'ambiguous names must be excluded');
assert.equal(compatibleRig(describeRig(new THREE.Group()),describeRig(makeRig())),false);
// Compatible rigs must actually accept and deform from the supplied clip.
const model=makeRig(),mesh=model.children.find(x=>x.isSkinnedMesh),mixer=new THREE.AnimationMixer(model);
mixer.clipAction(new THREE.AnimationClip('move',2,[new THREE.VectorKeyframeTrack('hand.position',[0,2],[0,0,0,2,0,0])])).play();mixer.update(1);model.updateMatrixWorld(true);mesh.skeleton.update();
assert.equal(mesh.applyBoneTransform(0,new THREE.Vector3()).x,1);
console.log('Rig compatibility: valid skins, hierarchy, duplicate names, and visible deformation passed.');
