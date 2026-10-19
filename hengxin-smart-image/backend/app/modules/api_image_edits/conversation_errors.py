"""Fixed public descriptions for domestic image-edit executor failures."""
from app.execution.credential_errors import execution_error_code

AUTH_ERROR = 'Codex 登录凭据已失效，请联系管理员恢复登录后重新提交；本轮未生成可用图片'


def execution_error(control, receipt):
    messages = {
        'timeout': '图片修改超过本轮执行时限，已停止；请检查修改要求后重新提交',
        'output_limit': '本轮执行日志超过安全上限，已停止；请联系管理员检查',
        'cancelled': '本轮图片修改已停止',
        'authentication_failed': AUTH_ERROR,
    }
    return messages.get(execution_error_code(control, receipt),
        'Codex 本轮执行失败，未生成可用图片；请重新提交，若仍失败请联系管理员')
