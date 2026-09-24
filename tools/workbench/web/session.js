let csrf='';
export async function api(path,body,headers={}){
  const response=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{...(body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf}),...headers},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const result=await response.json();if(!response.ok)throw Object.assign(Error(result.error||'本机服务暂不可用'),{status:response.status});
  if(result.csrf)csrf=result.csrf;return result;
}
const setup=new URLSearchParams(location.hash.slice(1));
if(setup.has('setup')){
  // Old bookmarks keep their requested view; local connection no longer needs a token.
  const view=setup.get('view')||'assets';
  history.replaceState(null,'',location.pathname+location.search+'#'+view);
}
export let state;
try{
  await api('/session',{}, {'X-Workbench-Connect':'1'});
  state=await api('/api/session');
}
catch(error){
  document.body.classList.add('connection-required');
  document.getElementById('connection-page').hidden=false;
  document.getElementById('connection-title').textContent='暂时无法连接项目看板';
  document.getElementById('connection-reason').textContent=error.status===401
    ?'浏览器未保留本机连接。请允许此地址使用 Cookie，然后重试。'
    :'请确认看板服务仍在运行，并直接打开它提供的 127.0.0.1 本机地址。';
  document.getElementById('connection-retry').onclick=()=>location.reload();
  throw error;
}
