"""Local configuration and bounded failure explanations. No service requests."""
import json
import re
from pathlib import Path
from . import api_common, credential_store, generation_capabilities


def configuration(root, provider):
    if provider not in ('tripo', 'hunyuan3d'):
        raise ValueError('请选择 Tripo 或混元 3D。')
    path = Path(root) / '.openaigame/asset-providers.json'
    config = json.loads(path.read_text('utf-8-sig')) if path.exists() else {}
    if not isinstance(config, dict):
        raise ValueError('项目服务配置需要是一个对象。')
    project = provider in config
    settings = config[provider] if project else credential_store.default_settings(provider)
    if not isinstance(settings, dict) or settings.get('mode') != 'api':
        return {'provider': provider, 'configuration_source': 'project' if project else 'local_default',
                'message': '当前项目使用本地命令，API 检查不适用。', 'network_checked': False, 'generation_submitted': False}
    result = api_common.doctor(provider, settings)
    result.update(configuration_source='project' if project else 'local_default',
                  message='这里只检查本机设置；账户权限、额度和网络尚未验证。',
                  capabilities=generation_capabilities.catalog(provider, settings),
                  connection=generation_capabilities.connection(provider, settings))
    return result


def explain(diagnostic, remote_id=None):
    code = diagnostic.get('code', '')
    if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', code):
        code = ''
    status = diagnostic.get('http_status')
    if type(status) is not int or not 100 <= status <= 599:
        status = None
    kind = diagnostic.get('kind')
    lower = code.lower()
    category, message = 'unknown', '原因尚未确定，请结合任务记录和服务控制台检查。'
    if kind == 'output_invalid':
        category, message = 'output', '返回文件或结果格式不符合预期。请先检查已有结果。'
    elif kind == 'remote_task_failed':
        category, message = 'task', '云端任务未完成，请在服务控制台查看原因。'
    elif status == 401 or lower.startswith('authfailure') or lower in ('invalid_api_key', 'authentication_error'):
        category, message = 'authentication', '认证未通过，请核对密钥来源和认证方式。'
    elif lower == 'insufficient_quota' or 'insufficient' in lower or 'credit' in lower:
        category, message = 'quota', '服务报告额度不足，请检查账户额度。'
    elif status == 403 or lower.startswith(('unauthorizedoperation', 'operationdenied')) or lower == 'permission_denied':
        category, message = 'permission', '服务拒绝访问，请检查账户权限。'
    elif status == 429 or lower.startswith('requestlimitexceeded') or lower == 'rate_limit_exceeded':
        category, message = 'rate_limit', '请求过于频繁，请稍后查询已有任务。'
    elif status in (400, 422) or lower.startswith(('invalidparameter', 'missingparameter')) or lower in ('invalid_request_error', 'invalid_parameter', 'model_not_found'):
        category, message = 'parameters', '请求参数不符合接口要求，请检查模型版本、生成方式和图片输入。'
    elif status is not None and status >= 500:
        category, message = 'service', '生成服务暂时出现错误，请先查询任务是否已创建。'
    elif kind == 'network_failure':
        category, message = 'network', '未能完成网络请求，提交结果可能需要进一步核对。'
    elif kind == 'io_failure':
        category, message = 'io', '文件或网络操作未完成，请先检查已有任务和本地文件。'
    remote_id = remote_id if isinstance(remote_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', remote_id) else None
    result = {'category': category, 'message': message, 'code': code, 'http_status': status,
              'next_step': '继续查询已有任务，不重新生成。' if remote_id else '先在服务控制台确认是否已有任务，再决定是否重新生成。',
              'remote_id': remote_id, 'automatic_resubmit': False}
    rid = diagnostic.get('request_id')
    if isinstance(rid, str) and re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', rid):
        result['request_id'] = rid
    return result


def job_failure(root, job):
    if not job.get('attempts') or job.get('status') not in ('failed', 'blocked', 'cancelled', 'interrupted'):
        return None
    job_id = job.get('job_id', '')
    if not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', job_id):
        return None
    path = Path(root) / '.openaigame/asset-jobs' / job_id / f"attempt-{len(job['attempts'])}" / 'diagnostic.json'
    data = {}
    if path.is_file() and path.stat().st_size <= 16384:
        try:
            data = json.loads(path.read_text('utf-8-sig'))
        except (ValueError, OSError):
            pass
    return explain(data if isinstance(data, dict) else {}, job.get('provider_job_id'))
