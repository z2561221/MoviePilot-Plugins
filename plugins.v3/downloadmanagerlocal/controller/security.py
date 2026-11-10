"""下载中心 HTTP 管理权限与只读能力查询。"""

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from app.sdk.security import verify_token


class PermissionsResult(BaseModel):
    """当前已认证调用者的管理能力，不替代后端逐次授权。"""

    can_manage: bool


def permissions(token=Depends(verify_token)) -> PermissionsResult:
    """普通登录用户可以读取自身权限，API key 遵从宿主认证结果。"""
    return PermissionsResult(can_manage=bool(getattr(token, "super_user", False)))


def require_admin(token=Depends(verify_token)):
    """在任何配置或下载器写入之前拒绝非管理员。"""
    if not getattr(token, "super_user", False):
        raise HTTPException(status_code=403, detail="管理操作需要管理员权限")
    return token
