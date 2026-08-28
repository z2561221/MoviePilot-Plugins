"""AgentRank API 路由注册与兼容响应入口。"""

from typing import Any, Callable, Dict, List

from .schemas import API_RESPONSE_MODELS


def build_api_routes(
    plugin: Any, controller_factory: Callable[[Any], Any]
) -> List[Dict[str, Any]]:
    """构建全部 bearer 前端 API 路由。"""
    controller = controller_factory(plugin)
    plugin._api_controller = controller
    specs = [
        ("/status", controller.endpoint_status, ["GET"], "获取插件状态"),
        ("/overview", controller.endpoint_overview, ["GET"], "获取用户总览"),
        ("/config/options", controller.endpoint_config_options, ["GET"], "获取配置选项"),
        ("/board", controller.endpoint_board, ["GET"], "获取推荐榜单"),
        ("/profile", controller.endpoint_profile, ["GET"], "获取用户画像"),
        ("/run-progress", controller.endpoint_run_progress, ["GET"], "获取实时运行进度"),
        ("/refresh", controller.endpoint_refresh, ["POST"], "刷新推荐榜单"),
        ("/playback/sync", controller.endpoint_playback_sync, ["POST"], "同步播放画像"),
        ("/attribution", controller.endpoint_attribution, ["GET"], "获取结果归因"),
        (
            "/attribution/native-drawer-opened",
            controller.endpoint_native_drawer_opened,
            ["POST"],
            "记录原生订阅抽屉已打开",
        ),
        (
            "/attribution/verify",
            controller.endpoint_verify_attribution,
            ["POST"],
            "复查订阅入库播放结果",
        ),
        ("/archive", controller.endpoint_archive, ["POST"], "忽略推荐"),
        ("/feedback", controller.endpoint_feedback, ["POST"], "记录三态反馈"),
        ("/analysis", controller.endpoint_analysis, ["GET"], "获取当前结构化推荐分析"),
        (
            "/analysis/comment",
            controller.endpoint_analysis_comment,
            ["POST"],
            "评论并修订 Agent 分析",
        ),
        ("/conversation", controller.endpoint_conversation, ["GET"], "获取 CinePilot Agent 对话"),
        (
            "/conversation/status",
            controller.endpoint_conversation_status,
            ["GET"],
            "获取 CinePilot Agent 未读状态",
        ),
        (
            "/conversation/messages",
            controller.endpoint_conversation_message,
            ["POST"],
            "发送 CinePilot Agent 消息",
        ),
        (
            "/conversation/messages/retry",
            controller.endpoint_retry_conversation_message,
            ["POST"],
            "重试 CinePilot Agent 消息",
        ),
        (
            "/conversation/commands/respond",
            controller.endpoint_respond_conversation_command,
            ["POST"],
            "确认或拒绝 CinePilot Agent 命令",
        ),
        (
            "/pending",
            controller.endpoint_pending_center,
            ["GET"],
            "获取统一待处理中心",
        ),
        (
            "/pending/interview/start",
            controller.endpoint_start_pending_interview,
            ["POST"],
            "启动待办中心动态问询验收",
        ),
        (
            "/pending/respond",
            controller.endpoint_respond_pending,
            ["POST"],
            "回答、拒绝或稍后处理待确认项目",
        ),
        ("/restore", controller.endpoint_restore, ["POST"], "恢复推荐"),
        ("/archive/delete", controller.endpoint_delete_archive, ["POST"], "删除归档"),
        ("/profile/clear", controller.endpoint_clear_profile, ["POST"], "重建画像"),
        (
            "/profile/tags",
            controller.endpoint_update_profile_tag,
            ["POST"],
            "更新人工画像标签",
        ),
        ("/run-history", controller.endpoint_run_history, ["GET"], "获取运行历史"),
        ("/board-history", controller.endpoint_board_history, ["GET"], "获取历史榜单"),
        ("/learning-health", controller.endpoint_learning_health, ["GET"], "获取学习健康度"),
        (
            "/consumption/exposure",
            controller.endpoint_record_exposure,
            ["POST"],
            "记录榜单真实曝光",
        ),
        (
            "/consumption/detail-opened",
            controller.endpoint_record_detail_opened,
            ["POST"],
            "记录榜单详情打开",
        ),
        (
            "/consumption/interaction",
            controller.endpoint_record_consumption_interaction,
            ["POST"],
            "记录订阅与播放结果",
        ),
        ("/data/export", controller.endpoint_data_export, ["GET"], "导出脱敏数据"),
        (
            "/data/reset/learning",
            controller.endpoint_reset_learning,
            ["POST"],
            "仅重置学习数据",
        ),
        (
            "/data/reset/full/prepare",
            controller.endpoint_prepare_full_reset,
            ["POST"],
            "准备清空全部数据",
        ),
        (
            "/data/reset/full",
            controller.endpoint_reset_full,
            ["POST"],
            "执行清空全部数据",
        ),
        ("/subscribe", controller.endpoint_subscribe, ["POST"], "手动订阅推荐"),
    ]
    return [
        {
            "path": path,
            "endpoint": endpoint,
            "methods": methods,
            "auth": "bear",
            "summary": summary,
            "response_model": API_RESPONSE_MODELS[path],
        }
        for path, endpoint, methods, summary in specs
    ]


def status_response(
    plugin: Any, controller_factory: Callable[[Any], Any]
) -> Dict[str, Any]:
    """兼容入口薄委托的状态响应。"""
    controller = controller_factory(plugin)
    return controller._business_data(controller.status())


def config_response(
    plugin: Any, controller_factory: Callable[[Any], Any]
) -> Dict[str, Any]:
    """兼容入口薄委托的配置响应。"""
    controller = controller_factory(plugin)
    return controller._business_data(controller.config_options())
