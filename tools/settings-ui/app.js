'use strict';
let csrf = '';
let active = false;
let approvalFingerprint = '';
const notice = document.querySelector('#notice');
function message(text, error = false) { notice.textContent = text; notice.classList.toggle('error', error); }
async function request(path, body, extra = {}) {
  const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
    headers: {...(body === undefined ? {} : {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}), ...extra},
    ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '本机服务暂不可用。');
  return result;
}
function render(state) {
  csrf = state.csrf; active = state.storage_available;
  for (const card of document.querySelectorAll('.card')) {
    const info = state.providers[card.dataset.provider];
    const badge = card.querySelector('.badge');
    badge.textContent = info.saved ? '本机已保存' : info.environment_present ? '使用环境变量' : '未配置';
    badge.classList.toggle('saved', info.saved || info.environment_present);
    card.querySelector('.primary').disabled = !active;
    card.querySelector('.remove').disabled = !active || !info.saved;
    card.querySelector('.provider-note').textContent = info.environment_present ? '检测到环境变量，调用时优先使用环境变量中的密钥。' : info.saved ? '已保存供后续任务使用；尚未验证服务账户。' : '';
  }
  if (!active) message('当前页面的加密保存仅支持 Windows；其他系统可继续使用环境变量。', true);
  const approval = state.approval;
  document.querySelector('#approval').hidden = !approval;
  approvalFingerprint = approval && !approval.approved && !approval.error ? approval.fingerprint || '' : '';
  document.querySelector('#accept-charge').checked = false;
  document.querySelector('#accept-charge').disabled = !approvalFingerprint;
  document.querySelector('#approve').disabled = true;
  if (approval) {
    document.querySelector('#approval-summary').textContent = approval.error || (approval.approved ? '本次请求已授权，等待助手执行。' : '请核对服务、提示词与输入文件。未确认前，工具不能提交生成。');
    document.querySelector('#approval-details').textContent = JSON.stringify({project: approval.project, job_id: approval.job_id,
      provider: approval.provider, parameters: approval.parameters, inputs: approval.inputs}, null, 2);
  }
}
document.querySelector('#accept-charge').addEventListener('change', (event) => {
  document.querySelector('#approve').disabled = !event.target.checked || !approvalFingerprint;
});
document.querySelector('#approve').addEventListener('click', async () => {
  const consent = document.querySelector('#accept-charge');
  if (!consent.checked || !approvalFingerprint) return;
  const button = document.querySelector('#approve'); button.disabled = true;
  consent.disabled = true;
  try { render(await request('/api/approve', {fingerprint: approvalFingerprint, accept_charge: true})); message('本次请求已授权，等待助手执行。新的请求仍需单独确认。'); }
  catch (error) { message(error.message, true); }
  finally {
    consent.disabled = !approvalFingerprint;
    button.disabled = !consent.checked || !approvalFingerprint;
  }
});
for (const card of document.querySelectorAll('.card')) {
  card.querySelector('form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (!active) return;
    const input = card.querySelector('input'); const button = card.querySelector('.primary');
    button.disabled = true;
    try { render(await request('/api/save', {provider: card.dataset.provider, key: input.value})); input.value = ''; message('密钥已在本机加密保存。后续任务可直接读取，尚未发起生成。'); }
    catch (error) { message(error.message, true); button.disabled = !active; }
  });
  card.querySelector('.remove').addEventListener('click', async () => {
    if (!window.confirm('删除这个服务的本机密钥？环境变量和服务平台上的密钥不会被删除。')) return;
    try { render(await request('/api/remove', {provider: card.dataset.provider})); card.querySelector('input').value = ''; message('本机保存的密钥已删除。'); }
    catch (error) { message(error.message, true); }
  });
}
document.querySelector('#refresh').addEventListener('click', async () => {
  try { render(await request('/api/state')); if (active) message('配置状态已刷新。此检查没有访问生成服务或消耗额度。'); }
  catch (error) { message(error.message, true); }
});
document.querySelector('#close').addEventListener('click', async () => {
  try { await request('/api/close', {}); active = false; document.querySelectorAll('button,input').forEach(e => e.disabled = true); message('设置服务已关闭。保存的配置继续有效，可以关闭此页。'); }
  catch (error) { message(error.message, true); }
});
(async () => {
  const token = window.location.hash.slice(1);
  history.replaceState(null, '', '/');
  try {
    let state;
    try { state = await request('/api/state'); }
    catch (error) {
      if (!token) throw error;
      await request('/session', {}, {'X-Setup-Token': token});
      state = await request('/api/state');
    }
    render(state);
    if (active) message('已连接本机。密钥只在保存时提交给本机工具，不会回显或写入项目文件。');
  } catch (error) { message(error.message, true); }
})();
