"""豆瓣中心 HTTP 管理权限与只读能力查询。"""

from fastapi import Depends, HTTPException
from app import schemas
from .schemas import PermissionsData
from app.sdk.security import verify_token


def permissions(token=Depends(verify_token)) -> schemas.Response[PermissionsData]:
    """普通登录用户可以读取自身权限，API key 遵从宿主认证结果。"""
    return schemas.Response[PermissionsData](success=True, data=PermissionsData(can_manage=bool(getattr(token, "super_user", False))))


def require_admin(token=Depends(verify_token)):
    """在任何配置或下载器写入之前拒绝非管理员。"""
    if not getattr(token, "super_user", False):
        raise HTTPException(status_code=403, detail="管理操作需要管理员权限")
    return token
