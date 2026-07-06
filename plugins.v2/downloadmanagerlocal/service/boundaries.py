"""下载中心后端服务边界清单。"""

SERVICE_BOUNDARIES = {
    "archive": {
        "service": "service/archive.py",
        "legacy_name": "rename_archive",
        "legacy_module": "modules/rename_archive.py",
        "owner": "补刀失败归档、恢复、删除与统计",
    },
    "diagnostics": {
        "service": "service/diagnostics.py",
        "legacy_name": "diagnostics",
        "legacy_module": "modules/diagnostics.py",
        "owner": "运行诊断摘要构建",
    },
    "iyuu": {
        "service": "service/iyuu.py",
        "legacy_name": "iyuu",
        "legacy_module": "modules/iyuu.py",
        "owner": "IYUU 辅种扫描、下载、缓存与历史",
    },
    "recheck": {
        "service": "service/recheck.py",
        "legacy_name": "recheck",
        "legacy_module": "modules/recheck.py",
        "owner": "按需做种校验队列与 worker",
    },
    "rename": {
        "service": "service/rename.py",
        "legacy_name": "rename",
        "legacy_module": "modules/rename.py",
        "owner": "种子重命名、补刀和历史记录",
    },
    "site_tag": {
        "service": "service/site_tag.py",
        "legacy_name": "site_tag",
        "legacy_module": "modules/site_tag.py",
        "owner": "站点识别与下载器标签写入",
    },
    "transfer": {
        "service": "service/transfer.py",
        "legacy_name": "transfer",
        "legacy_module": "modules/transfer.py",
        "owner": "转移做种、兜底扫描和转移后处理",
    },
}

LEGACY_MODULE_EXCEPTIONS = {}

LEGACY_MODULE_COMPATIBILITY_SHIMS = {
    item["legacy_module"]: item["service"]
    for item in SERVICE_BOUNDARIES.values()
}
