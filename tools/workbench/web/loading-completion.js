// A coalesced Three FileLoader request can complete without itemStart/onLoad
// on the second LoadingManager. Wait for actual outstanding dependencies only.
export function loadingCompletion(manager){
 let pending=0,waiters=[];
 const start=manager.itemStart.bind(manager),end=manager.itemEnd.bind(manager);
 manager.itemStart=url=>{pending++;start(url);};
 manager.itemEnd=url=>{try{end(url);}finally{pending--;if(pending===0){const done=waiters;waiters=[];done.forEach(resolve=>resolve());}}};
 return ()=>pending===0?Promise.resolve():new Promise(resolve=>waiters.push(resolve));
}
