"""在真实 LangChain 图中验证阶段约束，不访问模型供应商。"""

import asyncio
from types import SimpleNamespace
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
from pydantic import PrivateAttr

from app.plugins.agentrank.adapter.protocol import AgentRankProtocolMiddleware


class StageModel(BaseChatModel):
    """记录实际绑定参数并按指定工具返回本地测试响应。"""

    _bound: list = PrivateAttr(default_factory=list)
    _seen: list = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self):
        """返回无网络模型类型。"""
        return "agentrank-stage-test"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        """记录图实际传入的工具与选择参数。"""
        self._bound = tools
        self._seen.append(([tool.name for tool in tools], tool_choice))
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs: Any):
        """调用唯一允许的工具，不进行真实模型请求。"""
        name = self._bound[0].name
        return ChatResult(generations=[ChatGeneration(message=AIMessage(
            content="", tool_calls=[{"name": name, "args": {}, "id": f"call-{len(self._seen)}"}]
        ))])


def test_real_graph_reads_once_then_submits():
    """真实图第二轮只绑定提交工具，并在提交后结束。"""
    collector = SimpleNamespace(context_read=False, expected_tool="submit")
    calls = []

    async def read():
        """返回固定证据并推进阶段。"""
        calls.append("read")
        collector.context_read = True
        return '{"fact":"verified"}'

    async def submit():
        """记录唯一的终结提交。"""
        calls.append("submit")
        return '{"status":"accepted"}'

    model = StageModel()
    graph = create_agent(model=model, tools=[
        StructuredTool.from_function(coroutine=read, name="read"),
        StructuredTool.from_function(coroutine=submit, name="submit", return_direct=True),
    ], middleware=[AgentRankProtocolMiddleware(collector)])
    asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "run"}]}))
    assert calls == ["read", "submit"]
    assert [names for names, _ in model._seen] == [["read"], ["submit"]]
    assert model._seen[-1][1]["function"]["name"] == "submit"
