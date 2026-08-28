"""AgentRank API 的稳定业务错误与 HTTP 边界转换。"""

from typing import NoReturn

from fastapi import HTTPException


class ApiContractError(Exception):
    """表示可映射为稳定 HTTP 错误的控制器异常。"""

    def __init__(self, status_code: int, code: str, message: str):
        """保存状态码、机器码和用户可读消息。"""
        self.status_code = int(status_code)
        self.code = str(code)
        self.message = str(message)
        super().__init__(self.message)


def http_error(error: ApiContractError) -> NoReturn:
    """在真实 FastAPI endpoint 边界转换业务错误。"""
    raise HTTPException(
        status_code=error.status_code,
        detail=error.message,
        headers={"X-AgentRank-Error-Code": error.code},
    )
