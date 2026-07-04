"""诊断 legacy 兼容 shim，业务实现位于 service.diagnostics。"""

from ..service.diagnostics import build_diagnostics

__all__ = ("build_diagnostics",)
