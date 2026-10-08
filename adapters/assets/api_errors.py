"""Safe structured API failures; never persist provider messages or bodies."""
import re

_ROOTS = {'AuthFailure', 'FailedOperation', 'InternalError', 'InvalidAction',
          'InvalidParameter', 'InvalidParameterValue', 'LimitExceeded',
          'MissingParameter', 'OperationDenied', 'RequestLimitExceeded',
          'ResourceInUse', 'ResourceNotFound', 'ResourceUnavailable',
          'UnauthorizedOperation', 'UnsupportedOperation'}


class ProviderAPIError(ValueError):
    def __init__(self, result):
        self.diagnostic = {'kind': 'provider_rejection', 'code': 'UnclassifiedProviderError'}
        error = (result.get('Error') or result.get('error')) if isinstance(result, dict) else None
        code = error.get('Code', error.get('code')) if isinstance(error, dict) else None
        if (isinstance(code, str) and len(code) <= 100
                and re.fullmatch(r'[A-Za-z]+(?:\.[A-Za-z]+)*', code)
                and code.split('.')[0] in _ROOTS):
            self.diagnostic['code'] = code
        request_id = result.get('RequestId') if isinstance(result, dict) else None
        if isinstance(request_id, str) and re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', request_id):
            self.diagnostic['request_id'] = request_id
        super().__init__(self.diagnostic['code'])


class HTTPAPIError(ValueError):
    def __init__(self, status, result=None):
        self.diagnostic = {'kind': 'http_failure', 'http_status': int(status)}
        if isinstance(result, dict):
            # ai3d gateway validation uses a numeric top-level Code, unlike
            # downstream business errors. Keep only bounded numeric fields.
            if type(result.get('Code')) is int and 0 <= result['Code'] <= 999999:
                self.diagnostic['code'] = 'TencentGateway.' + str(result['Code'])
                if type(result.get('Type')) is int and 0 <= result['Type'] <= 9999:
                    self.diagnostic['gateway_type'] = result['Type']
                if result.get('Msg') == 'Invalid param':
                    self.diagnostic['message'] = 'Invalid param'
            payload = result.get('Response', result)
            if isinstance(payload, dict) and (payload.get('Error') or payload.get('error')):
                safe = ProviderAPIError(payload).diagnostic
                self.diagnostic.update({k: v for k, v in safe.items() if k != 'kind'})
                error = payload.get('Error') or payload.get('error')
                if isinstance(error, dict):
                    code = error.get('code')
                    if isinstance(code, str) and code in {'invalid_request_error', 'invalid_parameter', 'invalid_api_key',
                                'model_not_found', 'insufficient_quota', 'permission_denied',
                                'rate_limit_exceeded', 'authentication_error'}:
                        self.diagnostic['code'] = code
                    param = error.get('param')
                    if isinstance(param, str) and param in {'Model', 'ImageUrl', 'ImageBase64', 'Prompt', 'EnablePBR',
                                 'FaceCount', 'GenerateType', 'MultiViewImages', 'JobId'}:
                        self.diagnostic['parameter'] = param
        suffix = ': ' + self.diagnostic['code'] if 'code' in self.diagnostic else ''
        super().__init__('HTTP ' + str(int(status)) + suffix)


class TaskResultError(ValueError):
    def __init__(self, kind):
        if kind not in ('remote_task_failed', 'output_invalid'):
            raise ValueError('Unknown task result category')
        self.diagnostic = {'kind': kind}
        super().__init__(kind)
