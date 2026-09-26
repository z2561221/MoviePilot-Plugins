"""响应诊断必须区分故障且不泄漏正文或供应商任意字符串。"""

import json
from types import SimpleNamespace

import pytest
from app.plugins.agentrank.adapter.agent import AgentRankAgentAdapter
from app.plugins.agentrank.adapter.diagnostics import response_diagnostic
from langchain_core.messages import AIMessage


def test_response_shape_excludes_private_payloads():
    """损坏工具参数和正文不得混入诊断。"""
    message = AIMessage(
        content="PRIVATE_BODY",
        invalid_tool_calls=[{
            "name": "private_tool", "args": "PRIVATE_ARGS", "id": "secret_id",
            "error": "PRIVATE_ERROR",
        }],
        additional_kwargs={"reasoning_content": "PRIVATE_REASONING"},
        response_metadata={"finish_reason": "PRIVATE_REASON"},
    )
    row = response_diagnostic(SimpleNamespace(result=[message]), phase="submit", forced=True)
    assert row["invalid_tool_call_count"] == 1
    assert row["tool_call_count"] == 0
    assert row["text_chars"] == len("PRIVATE_BODY")
    assert row["reasoning_chars"] == len("PRIVATE_REASONING")
    assert row["finish_reasons"] == ["unknown"]
    assert "PRIVATE" not in json.dumps(row)
    assert "secret" not in json.dumps(row)


@pytest.mark.parametrize("content,expected", [
    ("", "agent_output_missing"),
    ("画像已完成", "agent_text_without_submission"),
    ('{"wrong":true}', "agent_schema_invalid"),
])
def test_output_categories_are_distinct(content, expected):
    """普通文本和不合契约 JSON 不能再伪装成空输出。"""
    assert AgentRankAgentAdapter._classify_repair([content], None)[0] == expected


def test_empty_length_response_preserves_finish_reason():
    """空内容的长度终止与普通 stop 可以区分。"""
    row = response_diagnostic(SimpleNamespace(result=[AIMessage(
        content="", response_metadata={"finish_reason": "length"}
    )]), phase="repair", forced=True)
    assert row["finish_reasons"] == ["length"]
    assert row["text_chars"] == row["tool_call_count"] == 0


def test_schema_diagnostic_survives_run_history_projection():
    """结构校验类型进入运行指标，错误输入不会进入指标。"""
    from app.plugins.agentrank.agent_tools.context import build_trusted_context
    from app.plugins.agentrank.agent_tools.session import (
        AgentRankSessionResultCollector,
    )
    from app.plugins.agentrank.service.recommendation import RecommendationOrchestrator

    trusted = build_trusted_context(
        username="test", run_id="diagnostic-test", candidates=[],
        archive_feedback={}, weights={}, agent_role="profile",
    )
    collector = AgentRankSessionResultCollector(trusted)
    assert not AgentRankAgentAdapter._recover_terminal_submission(
        collector, ['{"PRIVATE_FIELD":"PRIVATE_VALUE"}']
    )
    assert collector.output_diagnostics
    raw = {"output_diagnostics": collector.output_diagnostics}
    metrics = {}
    RecommendationOrchestrator._record_agent_provenance(
        metrics, "profile", SimpleNamespace(provenance=raw),
        stage="profile", attempt=1, duration_ms=1,
    )
    assert metrics["agent_provenance"][0]["output_diagnostics"]
    assert "PRIVATE" not in json.dumps(metrics)


def test_tool_schema_error_captured_before_execution():
    """工具调用 JSON 合法仍可能缺少必填参数，诊断须覆盖这个边界。"""
    from pydantic import BaseModel

    class Submission(BaseModel):
        """最小提交格式。"""
        profile: dict

    tool = SimpleNamespace(name="submit", args_schema=Submission)
    message = AIMessage(content="", tool_calls=[{
        "name": "submit", "args": {"private": "PRIVATE_VALUE"}, "id": "call-1",
    }])
    row = response_diagnostic(SimpleNamespace(result=[message]),
                              phase="submit", forced=True, tools=[tool])
    assert row["tool_call_count"] == 1
    assert row["invalid_tool_call_count"] == 0
    assert row["tool_schema_error_types"] == ["missing"]
    assert "PRIVATE" not in json.dumps(row)


def test_unexpected_tool_name_is_counted_but_not_saved():
    """供应商未遵循强制选择时，只记录计数。"""
    message = AIMessage(content="", tool_calls=[{
        "name": "PRIVATE_TOOL", "args": {}, "id": "call-1",
    }])
    row = response_diagnostic(SimpleNamespace(result=[message]), phase="repair",
                              forced=True, tools=[SimpleNamespace(name="submit")])
    assert row["unexpected_tool_call_count"] == 1
    assert "PRIVATE_TOOL" not in json.dumps(row)
