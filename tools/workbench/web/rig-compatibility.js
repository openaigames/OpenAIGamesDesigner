// Structural compatibility for direct playback only; not retargeting or a claim
// that attached equipment and other independently animated components exist.
export function describeRig(root){
 const bones=new Map();let duplicateNames=false,skinnedMeshes=0;
 root.traverse(node=>{
  if(node.isBone){if(bones.has(node.name))duplicateNames=true;bones.set(node.name,node.parent?.isBone?node.parent.name:null);}
  if(node.isSkinnedMesh&&node.skeleton?.bones?.length&&node.geometry?.attributes?.skinIndex&&node.geometry?.attributes?.skinWeight?.array?.some(w=>w>0))skinnedMeshes++;
 });
 return {boneCount:bones.size,skinnedMeshes,duplicateNames,signature:JSON.stringify([...bones].sort(([a],[b])=>a.localeCompare(b)))};
}

export function compatibleRig(source,target){
 return Boolean(source?.boneCount&&target?.skinnedMeshes&&!source.duplicateNames&&!target.duplicateNames&&source.signature===target.signature);
}
