export function serviceDetails(d, esc) {
  const sources={project:'当前项目设置',local_default:'本机默认设置'};
  const credentials={environment:'环境变量',local_store:'本机加密保存',missing:'未配置'};
  const c=d.connection;
  return `<section class="job-lineage"><h4>当前使用的设置</h4><p>设置来源：${esc(sources[d.configuration_source]||'待核对')}</p>${c?`<p>认证方式：${esc(c.authentication)}</p><p>密钥管理页面：${esc(c.key_page)}</p><p>生成请求地址：${esc(c.submit_url)}</p><p>任务查询地址：${esc(c.query_url)}</p>${c.submit_action?`<p>生成操作：${esc(c.submit_action)}；查询操作：${esc(c.query_action)}</p>`:''}`:''}${(d.credentials||[]).map(x=>`<p>${esc(x.environment_variable)}：${esc(credentials[x.source]||'待核对')}</p>`).join('')}<p>${esc(d.message)}</p>${d.ready_to_attempt===false?'<p>本机设置还不完整，请先补齐对应密钥或地域。</p>':''}${d.capabilities?.length?`<details><summary>本地已接入的生成方式</summary><ul>${d.capabilities.map(x=>`<li>${esc(x.label)} · ${esc(x.model)} · ${x.min_images}–${x.max_images} 张图 · ${x.prompt==='none'?'不发送约束文字':x.prompt_with_images?'可同时发送约束文字':'需要约束文字'}</li>`).join('')}</ul></details>`:''}</section>`;
}

export function failureDetails(d, esc) {
  if(!d)return '';
  return `<section class="job-lineage"><h3>本次未完成的原因</h3><p>${esc(d.message)}</p><p>${esc(d.next_step)}</p>${d.remote_id?`<p>已有云任务：${esc(d.remote_id)}</p>`:''}${d.code||d.http_status?`<details><summary>错误编号</summary><p>${esc(d.code||'')} ${d.http_status?'HTTP '+d.http_status:''}</p>${d.request_id?`<p>请求编号：${esc(d.request_id)}</p>`:''}</details>`:''}</section>`;
}
