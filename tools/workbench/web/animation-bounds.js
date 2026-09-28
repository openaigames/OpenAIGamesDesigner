import * as THREE from 'three';

export function poseBounds(model){
 model.updateMatrixWorld(true);
 model.traverse(o=>{if(o.isSkinnedMesh){o.skeleton.update();o.computeBoundingBox();}});
 const box=new THREE.Box3().setFromObject(model);
 if(box.isEmpty())model.traverse(o=>{if(o.isBone)box.expandByPoint(o.getWorldPosition(new THREE.Vector3()));});
 return box;
}

// A single evaluated pose is useful for framing a moving character. Restoring
// the mixer leaves the imported asset unchanged, just as envelope sampling does.
export function clipPoseBounds(model,clip,time=0){
 const mixer=new THREE.AnimationMixer(model),action=mixer.clipAction(clip);
 action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();
 try{mixer.setTime(Math.max(0,Math.min(time,clip.duration)));return poseBounds(model);}
 finally{mixer.stopAllAction();mixer.uncacheRoot(model);poseBounds(model);}
}

// Fit derived previews to an observed clip envelope. Normalizing only the bind
// pose can put all animated geometry outside the camera when root keys move.
export function animationBounds(model,clip){
 const bounds=new THREE.Box3(),mixer=new THREE.AnimationMixer(model);
 const action=mixer.clipAction(clip);action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();
 try{
  for(let i=0;i<=24;i++){
   mixer.setTime(clip.duration*i/24);model.updateMatrixWorld(true);
   model.traverse(o=>{if(o.isSkinnedMesh){o.skeleton.update();o.computeBoundingBox();}});
   bounds.union(new THREE.Box3().setFromObject(model));
  }
 }finally{mixer.stopAllAction();mixer.uncacheRoot(model);model.updateMatrixWorld(true);model.traverse(o=>{if(o.isSkinnedMesh){o.skeleton.update();o.computeBoundingBox();}});}
 return bounds;
}
