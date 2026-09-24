import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { MTLLoader } from 'three/addons/loaders/MTLLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export const canPreviewModel=asset=>['GLB','GLTF','OBJ'].includes(asset.previewExt||asset.ext)&&['native','derived'].includes(asset.preview);
async function loadModel(asset){
 const url=new URL(asset.previewUrl||asset.url,location.href),manager=new THREE.LoadingManager();
 const mount=new URL(asset.assetRoot||'/asset/',location.href);
 manager.setURLModifier(value=>{
  if(value.startsWith('blob:')||value.startsWith('data:'))return value;
  const target=new URL(value,location.href);
  if(target.origin!==mount.origin||!target.pathname.startsWith(mount.pathname))throw new Error('模型依赖必须位于当前项目中');
  return target.href;
 });
 if((asset.previewExt||asset.ext)!=='OBJ')return new GLTFLoader(manager).loadAsync(url.href);
 const response=await fetch(url);if(!response.ok)throw new Error('无法读取 OBJ 文件');
 const text=await response.text(),objLoader=new OBJLoader(manager);let model=objLoader.parse(text),note='';
 const libraries=model.materialLibraries||[];
 if(libraries.length){
  const creators=[];
  for(const library of libraries){try{
   const source=new URL(library,url);manager.resolveURL(source.href);
   const material=await new MTLLoader(manager).loadAsync(source.href);creators.push(material);
  }catch{note='部分材质文件未找到，缺少的部分使用中性材质。';}}
  if(creators.length){
   const fallback=new THREE.MeshPhongMaterial({color:0x5b6575});
   objLoader.setMaterials({create(name){const owner=creators.find(m=>Object.hasOwn(m.materialsInfo,name));return owner?owner.create(name):fallback;}});
   disposeModel(model);model=objLoader.parse(text);
  }
 }else note='OBJ 未附带 MTL 材质，当前显示模型几何。';
 // Keep untextured geometry legible against the light preview background.
 if(!libraries.length||note.startsWith('部分材质'))model.traverse(o=>{for(const m of [].concat(o.material||[]))if(!m.name&&!m.vertexColors&&!m.map)m.color?.setHex(0x5b6575);});
 return {scene:model,animations:[],note};
}
function disposeModel(model){const textures=new Set(),materials=new Set(),geometries=new Set();model?.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of [].concat(o.material||[])){materials.add(m);for(const v of Object.values(m))if(v?.isTexture)textures.add(v);}});textures.forEach(t=>{t.dispose();t.source?.data?.close?.();});materials.forEach(m=>m.dispose());geometries.forEach(g=>g.dispose());}
function normalize(model){model.updateMatrixWorld(true);const box=new THREE.Box3().setFromObject(model),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());const scale=2.6/Math.max(size.x,size.y,size.z,.001);const root=new THREE.Group();root.add(model);root.scale.setScalar(scale);root.position.set(-center.x*scale,-box.min.y*scale,-center.z*scale);root.updateMatrixWorld(true);return {root,height:size.y*scale};}
function stage(canvas,width,height,interactive){
 const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(width,height,false);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(36,width/height,.01,100);camera.position.set(3.6,2.5,4.8);camera.lookAt(0,.9,0);
 const pmrem=new THREE.PMREMGenerator(renderer),environment=new RoomEnvironment();const env=pmrem.fromScene(environment,.04);scene.environment=env.texture;environment.dispose();pmrem.dispose();
 scene.add(new THREE.HemisphereLight(0xd7e7ff,0x4b3e31,2));const key=new THREE.DirectionalLight(0xffe5c8,3);key.position.set(3,6,4);scene.add(key);const rim=new THREE.DirectionalLight(0xa2b9e2,2);rim.position.set(-4,2,-3);scene.add(rim);
 const ground=new THREE.Mesh(new THREE.CircleGeometry(2,64),new THREE.MeshStandardMaterial({color:0xd8deeb,roughness:1,transparent:true,opacity:.55}));ground.rotation.x=-Math.PI/2;ground.position.y=-.012;scene.add(ground);
 const grid=new THREE.GridHelper(12,24,0x98a8cb,0xb5c1d9);grid.material.transparent=true;grid.material.opacity=.22;grid.visible=interactive;grid.position.y=-.005;scene.add(grid);
 const controls=interactive?new OrbitControls(camera,canvas):null;if(controls){controls.target.set(0,.85,0);controls.enableDamping=true;controls.minDistance=1;controls.maxDistance=15;controls.maxPolarAngle=Math.PI*.88;controls.update();}
 return {renderer,scene,camera,controls,grid,ground,env,dispose(){controls?.dispose();env.dispose();disposeModel(ground);disposeModel(grid);renderer.dispose();renderer.forceContextLoss();}};
}

export async function modelPreview(host,asset,onReady){
 const canvas=document.createElement('canvas');canvas.setAttribute('aria-label',asset.title+' 3D 预览');host.append(canvas);
 const ctx=stage(canvas,host.clientWidth||340,host.clientHeight||285,true);let alive=true,model,root,skeleton,mixer,action,animations=[],paused=false,last=performance.now(),frame;
 const observer=new ResizeObserver(()=>{if(!alive)return;const w=host.clientWidth,h=host.clientHeight;ctx.renderer.setSize(w,h,false);ctx.camera.aspect=w/h;ctx.camera.updateProjectionMatrix();});observer.observe(host);
 function tick(now){if(!alive)return;const dt=Math.min((now-last)/1000,.05);last=now;if(mixer&&!paused)mixer.update(dt);ctx.controls.update();ctx.renderer.render(ctx.scene,ctx.camera);if(action)onReady?.tick?.(action.time,action.getClip().duration,paused);frame=requestAnimationFrame(tick);}frame=requestAnimationFrame(tick);
 const api={dispose(){alive=false;cancelAnimationFrame(frame);observer.disconnect();if(mixer){mixer.stopAllAction();mixer.uncacheRoot(model);}skeleton?.dispose();disposeModel(root);ctx.dispose();},
  play(){paused=!paused;return paused;},get paused(){return paused;},setTime(t){if(!action)return;action.time=Math.min(Math.max(0,t),action.getClip().duration-.00001);mixer.update(0);},
  setSpeed(v){if(mixer)mixer.timeScale=v;},selectClip(i){if(!mixer)return;mixer.stopAllAction();action=mixer.clipAction(animations[i]);action.reset().play();paused=false;return animations[i]?.duration||0;},
  wireframe(v){model?.traverse(o=>{if(o.isMesh)for(const m of [].concat(o.material||[])){m.wireframe=v;}});},skeleton(v){if(skeleton)skeleton.visible=v;},grid(v){ctx.grid.visible=v;},rotate(v){ctx.controls.autoRotate=v;ctx.controls.autoRotateSpeed=1.2;},
  reset(){ctx.camera.position.set(3.6,2.5,4.8);ctx.controls.target.set(0,(api.height||1.7)*.47,0);ctx.controls.update();},background(v){host.style.background=v;},exposure(v){ctx.renderer.toneMappingExposure=v;},screenshot(){ctx.renderer.render(ctx.scene,ctx.camera);return canvas.toDataURL('image/png');},part(i,visible){api.meshes[i].visible=visible;},meshes:[]};
 loadModel(asset).then(gltf=>{if(!alive){disposeModel(gltf.scene);return;}model=gltf.scene;animations=gltf.animations;api.note=gltf.note||asset.previewNote||'';const normalized=normalize(model);root=normalized.root;api.height=normalized.height;ctx.scene.add(root);ctx.controls.target.set(0,normalized.height*.47,0);ctx.controls.update();
  model.traverse(o=>{if(o.isMesh)api.meshes.push(o);});skeleton=new THREE.SkeletonHelper(root);skeleton.visible=false;skeleton.material.depthTest=false;skeleton.renderOrder=9;ctx.scene.add(skeleton);if(animations.length){mixer=new THREE.AnimationMixer(model);action=mixer.clipAction(animations[0]);action.play();}
  canvas.dataset.loaded='true';canvas.dataset.animations=animations.length;host.querySelector('.preview-loading')?.remove();onReady.ready(api,animations);
 }).catch(error=>{if(!alive)return;canvas.dataset.error='true';host.querySelector('.preview-loading')?.remove();const el=document.createElement('div');el.className='preview-error';el.style.position='absolute';el.style.inset='0';el.textContent='模型加载失败。请检查文件格式与贴图依赖。';host.append(el);console.warn('Model preview failed:',asset.name,error.message);});
 return api;
}

let thumbnailStage;
export async function modelThumbnail(asset){
 if(!thumbnailStage){const canvas=document.createElement('canvas');thumbnailStage=stage(canvas,320,260,false);thumbnailStage.renderer.setPixelRatio(1);thumbnailStage.renderer.setSize(320,260,false);}
 const ctx=thumbnailStage,gltf=await loadModel(asset);const {root,height}=normalize(gltf.scene);ctx.scene.add(root);ctx.camera.position.set(3.7,2.6,4.7);ctx.camera.lookAt(0,height*.48,0);
 let mixer;if(gltf.animations.length){mixer=new THREE.AnimationMixer(gltf.scene);mixer.clipAction(gltf.animations[0]).play();mixer.update(.5);}ctx.renderer.render(ctx.scene,ctx.camera);const data=ctx.renderer.domElement.toDataURL('image/png');ctx.scene.remove(root);mixer?.stopAllAction();disposeModel(root);return data;
}

export function disposeThumbnails(){thumbnailStage?.dispose();thumbnailStage=null;}
