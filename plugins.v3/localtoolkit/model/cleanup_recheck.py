"""媒体状态核验失败的可操作诊断，不携带地址、凭据或原始响应。"""


class CleanupReadError(Exception):
    """向只读核验提供稳定原因与处理建议。"""

    def __init__(self, code: str, message: str, action: str):
        super().__init__(message)
        self.code = code
        self.action = action


def unavailable(diagnose: bool, code: str, message: str, action: str):
    """保留既有未知状态语义，仅显式诊断时抛出可读原因。"""
    if diagnose:
        raise CleanupReadError(code, message, action)
    return None, None
