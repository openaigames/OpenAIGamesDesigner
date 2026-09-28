export async function resolve(specifier,context,next){
 if(specifier==='three')return {url:new URL('../tools/workbench/web/vendor/three/build/three.module.js',import.meta.url).href,shortCircuit:true};
 return next(specifier,context);
}
