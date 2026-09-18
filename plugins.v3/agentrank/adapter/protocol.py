"""受限 Agent 的读取、提交阶段约束。"""

from langchain.agents.middleware.types import AgentMiddleware


class AgentRankProtocolMiddleware(AgentMiddleware):
    """按本轮收集器状态收窄工具，并在供应商明确拒绝时降级工具选择参数。"""

    def __init__(self, collector, *, submission_only=False):
        """保存当前会话的收集器，不与其它用户或运行共享状态。"""
        self.collector = collector
        self.submission_only = submission_only
        self.tool_choice_supported = True

    def _request(self, request):
        """读取前仅开放快照工具，读取后和修正回合仅开放提交工具。"""
        submit = self.submission_only or self.collector.context_read
        tools = [
            tool for tool in request.tools
            if (tool.name == self.collector.expected_tool) == submit
        ]
        if len(tools) != 1:
            raise RuntimeError("AgentRank protocol requires exactly one stage tool")
        choice = (
            {"type": "function", "function": {"name": tools[0].name}}
            if self.tool_choice_supported else None
        )
        return request.override(tools=tools, tool_choice=choice)

    @staticmethod
    def _unsupported_choice(error):
        """仅识别供应商明确拒绝工具选择参数的请求错误。"""
        status = getattr(error, "status_code", None)
        message = str(error).casefold()
        return status in {400, 422} and "tool_choice" in message and any(
            word in message for word in ("unsupported", "not support", "not allowed")
        )

    async def awrap_model_call(self, request, handler):
        """限制异步模型调用；参数明确不受支持时只降级一次。"""
        constrained = self._request(request)
        try:
            return await handler(constrained)
        except Exception as error:
            if not self.tool_choice_supported or not self._unsupported_choice(error):
                raise
            self.tool_choice_supported = False
            return await handler(self._request(request))

    def wrap_model_call(self, request, handler):
        """为宿主同步图执行保留相同的阶段与参数约束。"""
        constrained = self._request(request)
        try:
            return handler(constrained)
        except Exception as error:
            if not self.tool_choice_supported or not self._unsupported_choice(error):
                raise
            self.tool_choice_supported = False
            return handler(self._request(request))
