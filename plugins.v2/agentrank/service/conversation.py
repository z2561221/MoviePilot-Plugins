"""专属影评师对话、待确认命令与受控执行服务。"""

import hashlib
import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..agent_tools.context import CONVERSATION_AGENT_ROLE, build_trusted_context
from ..model.config import WEIGHT_DEFAULTS, normalize_config
from ..model.conversation import (
    ConversationCommand,
    ConversationMessage,
    ConversationThread,
)
from ..storage.repository import AgentRankRepository
from .data_lifecycle import DataLifecycleService
from .feedback_action import FeedbackActionService
from .profile_preferences import ProfilePreferenceService
from .prompt import build_conversation_prompt


_SENSITIVE_PSYCHOLOGY_TERMS = (
    "人格",
    "焦虑",
    "孤独",
    "疾病",
    "创伤",
    "抑郁",
    "心理诊断",
    "心理障碍",
)
_INTENTS = frozenset({"read_only", "write_request", "ambiguous"})
_REMINDER_DELAYS = {
    "in_1_day": timedelta(days=1),
    "in_3_days": timedelta(days=3),
    "in_7_days": timedelta(days=7),
}


logger = logging.getLogger(__name__)


class ConversationError(RuntimeError):
    """表示对话或命令不能安全继续。"""

    def __init__(self, code: str, message: str, status_code: int = 409):
        """保存稳定错误码、用户文案和 HTTP 状态码。"""
        self.code = str(code)
        self.message = str(message)
        self.status_code = int(status_code)
        super().__init__(self.message)


@dataclass(frozen=True)
class ConversationCommandDraft:
    """表示通过严格解析但尚未绑定宿主事实的命令草案。"""

    kind: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class ConversationAgentReply:
    """表示不含思维链和模型原文的结构化对话回答。"""

    intent: str
    reply: str
    evidence_refs: Tuple[str, ...]
    commands: Tuple[ConversationCommandDraft, ...]
    uncertainties: Tuple[str, ...]


class ConversationReplyParser:
    """严格解析专属影评师 JSON 并拒绝越权命令。"""

    root_keys = frozenset(
        {"intent", "reply", "evidence_refs", "commands", "uncertainties"}
    )
    command_keys = frozenset({"kind", "payload"})

    @staticmethod
    def _text(value: Any, limit: int) -> str:
        """把不可信标量规范为有界单行文本。"""
        return " ".join(str(value or "").split()).strip()[: max(1, int(limit))]

    @classmethod
    def _texts(
        cls, values: Any, *, limit: int, text_limit: int
    ) -> Tuple[str, ...]:
        """解析有界唯一字符串数组。"""
        if not isinstance(values, list):
            raise ConversationError("invalid_agent_output", "Agent 对话输出格式无效", 502)
        result = []
        for value in values:
            if not isinstance(value, str):
                raise ConversationError(
                    "invalid_agent_output", "Agent 对话输出格式无效", 502
                )
            text = " ".join(value.split()).strip()
            if len(text) > text_limit:
                raise ConversationError(
                    "invalid_agent_output", "Agent 对话输出文本超限", 502
                )
            if text and text not in result:
                result.append(text)
            if len(result) > limit:
                raise ConversationError(
                    "invalid_agent_output", "Agent 对话输出数量超限", 502
                )
        return tuple(result)

    @classmethod
    def parse(
        cls, raw: Any, *, allowed_evidence_refs: Iterable[str]
    ) -> ConversationAgentReply:
        """解析单个严格 JSON 对象并验证命令与证据引用。"""
        try:
            value = json.loads(str(raw or ""))
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise ConversationError(
                "invalid_agent_output", "Agent 对话输出不是合法 JSON", 502
            ) from error
        if not isinstance(value, Mapping) or set(value) != cls.root_keys:
            raise ConversationError("invalid_agent_output", "Agent 对话输出字段无效", 502)
        intent = cls._text(value.get("intent"), 32)
        raw_reply = value.get("reply")
        reply = " ".join(raw_reply.split()).strip() if isinstance(raw_reply, str) else ""
        if len(reply) > 800:
            raise ConversationError("invalid_agent_output", "Agent 对话回答过长", 502)
        if intent not in _INTENTS or not reply:
            raise ConversationError("invalid_agent_output", "Agent 对话回答不完整", 502)
        if any(term in reply for term in _SENSITIVE_PSYCHOLOGY_TERMS):
            raise ConversationError(
                "unsafe_agent_output", "Agent 对话包含不允许的敏感心理推断", 502
            )
        evidence_refs = cls._texts(
            value.get("evidence_refs"), limit=24, text_limit=160
        )
        allowed = {str(item or "").strip() for item in allowed_evidence_refs or ()}
        if any(item not in allowed for item in evidence_refs):
            raise ConversationError(
                "invalid_evidence_reference", "Agent 对话引用了当前上下文外的证据", 502
            )
        raw_commands = value.get("commands")
        if not isinstance(raw_commands, list) or len(raw_commands) > 3:
            raise ConversationError("invalid_agent_output", "Agent 对话命令数量无效", 502)
        commands = []
        for raw_command in raw_commands:
            if not isinstance(raw_command, Mapping) or set(raw_command) != cls.command_keys:
                raise ConversationError(
                    "invalid_agent_output", "Agent 对话命令格式无效", 502
                )
            kind = cls._text(raw_command.get("kind"), 32)
            payload = raw_command.get("payload")
            if kind not in {"profile_tag", "weight", "ignore", "subscribe", "reset_learning"}:
                raise ConversationError(
                    "invalid_agent_command", "Agent 提出了不允许的写操作", 502
                )
            if not isinstance(payload, Mapping):
                raise ConversationError(
                    "invalid_agent_command", "Agent 写操作参数无效", 502
                )
            normalized = dict(payload)
            if kind == "profile_tag":
                if set(normalized) != {"kind", "action", "tag"}:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 标签命令字段无效", 502
                    )
                raw_tag = normalized.get("tag")
                tag = " ".join(raw_tag.split()).strip() if isinstance(raw_tag, str) else ""
                if len(tag) > 20:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 标签命令参数过长", 502
                    )
                normalized = {
                    "kind": cls._text(normalized.get("kind"), 16),
                    "action": cls._text(normalized.get("action"), 16),
                    "tag": tag,
                }
                if (
                    normalized["kind"] not in {"positive", "negative"}
                    or normalized["action"] not in {"add", "remove", "restore"}
                    or not normalized["tag"]
                ):
                    raise ConversationError(
                        "invalid_agent_command", "Agent 标签命令参数无效", 502
                    )
            elif kind == "weight":
                if set(normalized) != {"weight_name", "value"}:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 权重命令字段无效", 502
                    )
                raw_weight_name = normalized.get("weight_name")
                weight_name = (
                    " ".join(raw_weight_name.split()).strip()
                    if isinstance(raw_weight_name, str)
                    else ""
                )
                if len(weight_name) > 32:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 权重名称过长", 502
                    )
                try:
                    weight_value = float(normalized.get("value"))
                except (TypeError, ValueError) as error:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 权重值无效", 502
                    ) from error
                if weight_name not in WEIGHT_DEFAULTS or not 0.0 <= weight_value <= 1.0:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 权重命令参数无效", 502
                    )
                normalized = {"weight_name": weight_name, "value": weight_value}
            elif kind in {"ignore", "subscribe"}:
                if set(normalized) != {"candidate_id"}:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 作品命令字段无效", 502
                    )
                raw_candidate_id = normalized.get("candidate_id")
                candidate_id = (
                    " ".join(raw_candidate_id.split()).strip()
                    if isinstance(raw_candidate_id, str)
                    else ""
                )
                if len(candidate_id) > 128:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 候选标识过长", 502
                    )
                if not candidate_id:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 作品命令缺少候选标识", 502
                    )
                normalized = {"candidate_id": candidate_id}
            elif normalized:
                raise ConversationError(
                    "invalid_agent_command", "Agent 重置命令不能包含参数", 502
                )
            commands.append(ConversationCommandDraft(kind=kind, payload=normalized))
        uncertainties = cls._texts(
            value.get("uncertainties"), limit=8, text_limit=240
        )
        if intent == "read_only" and commands:
            raise ConversationError(
                "invalid_agent_command", "只读回答不能包含写操作", 502
            )
        if intent == "write_request" and not commands:
            raise ConversationError(
                "invalid_agent_command", "写操作请求缺少待确认命令", 502
            )
        if intent == "ambiguous" and (commands or not uncertainties):
            raise ConversationError(
                "invalid_agent_output", "含义不明确时必须询问且不能写入", 502
            )
        return ConversationAgentReply(
            intent=intent,
            reply=reply,
            evidence_refs=evidence_refs,
            commands=tuple(commands),
            uncertainties=uncertainties,
        )


class ConversationService:
    """维护有界对话并把全部写请求收敛为待确认命令。"""

    def __init__(
        self,
        repository: AgentRankRepository,
        agent_adapter: Any,
        *,
        plugin: Any = None,
        message_limit: int = 200,
        now_factory: Callable[[], datetime] = None,
        pending_handler: Callable[[ConversationCommand], Any] = None,
    ):
        """绑定仓储、受限 Agent、运行插件与可测试时钟。"""
        if not isinstance(repository, AgentRankRepository):
            raise TypeError("repository must be AgentRankRepository")
        self._repository = repository
        self._agent_adapter = agent_adapter
        self._plugin = plugin
        self._message_limit = max(1, min(int(message_limit), 100000))
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))
        self._pending_handler = pending_handler

    def set_pending_handler(
        self, handler: Callable[[ConversationCommand], Any] = None
    ) -> None:
        """设置新建待确认命令的非阻断通知回调。"""
        self._pending_handler = handler

    def _emit_pending(self, commands: Sequence[ConversationCommand]) -> None:
        """逐条发送待确认命令通知，通知失败不回滚已完成对话。"""
        if not callable(self._pending_handler):
            return
        for command in commands:
            try:
                self._pending_handler(command)
            except Exception:
                logger.exception(
                    "AgentRank 对话待确认通知失败 command_id=%s",
                    command.command_id,
                )

    def _now(self) -> str:
        """返回带时区的当前 ISO 时间。"""
        now = self._now_factory()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.isoformat()

    @staticmethod
    def _stable_id(prefix: str, *parts: Any) -> str:
        """根据作用域生成不泄露原文且重试稳定的记录 ID。"""
        payload = ":".join(str(item or "") for item in parts)
        digest = hashlib.sha256(f"{prefix}:{payload}".encode("utf-8")).hexdigest()[:24]
        return f"{prefix}:{digest}"

    @staticmethod
    def _scope_token(prefix: str, value: str) -> str:
        """生成满足 Agent 私有 session 约束的安全作用域。"""
        digest = hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:20]
        return f"{prefix}-{digest}"

    @staticmethod
    def _message_text(value: Any) -> str:
        """规范化并校验用户对话文本。"""
        text = " ".join(str(value or "").split()).strip()
        if not text:
            raise ConversationError("message_required", "请输入要发送的内容", 422)
        if len(text) > 1000:
            raise ConversationError("message_too_long", "单条消息不能超过一千字", 422)
        return text

    @staticmethod
    def _idempotency_key(value: Any) -> str:
        """校验对话写入幂等键。"""
        key = str(value or "").strip()
        if not key:
            raise ConversationError(
                "idempotency_key_required", "发送消息需要幂等键", 422
            )
        if len(key) > 256:
            raise ConversationError(
                "idempotency_key_invalid", "消息幂等键过长", 422
            )
        return key

    def _thread(
        self, profile_id: str, actor_id: str, created_at: str
    ) -> ConversationThread:
        """读取现有线程或创建一个稳定的 profile 线程。"""
        existing = self._repository.load_conversation_thread(profile_id)
        if existing is not None:
            return existing
        return ConversationThread(
            thread_id=self._stable_id("conversation-thread", profile_id),
            profile_id=profile_id,
            created_by_mp_user_id=actor_id,
            created_at=created_at,
            updated_at=created_at,
        )

    @staticmethod
    def _candidate_data(candidate: Any) -> Dict[str, Any]:
        """投影对话所需的有界作品事实。"""
        raw = candidate.to_dict() if hasattr(candidate, "to_dict") else dict(candidate or {})
        return {
            "candidate_id": str(raw.get("candidate_id") or ""),
            "title": str(raw.get("title") or "")[:160],
            "media_type": str(raw.get("media_type") or "")[:24],
            "year": raw.get("year"),
            "overview": str(raw.get("overview") or "")[:1000],
            "genres": list(raw.get("genres") or ())[:24],
            "actors": list(raw.get("actors") or ())[:12],
            "directors": list(raw.get("directors") or ())[:8],
            "regions": list(raw.get("regions") or ())[:12],
        }

    @staticmethod
    def _playback_data(snapshot: Any) -> Dict[str, Any]:
        """投影最多二十条播放证据并保留来源状态。"""
        if snapshot is None:
            return {"status": "unavailable", "samples": []}
        raw = snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot or {})
        samples = list(raw.get("samples") or ())[-20:]
        return {
            "status": str(raw.get("status") or ""),
            "source": str(raw.get("source") or ""),
            "collected_at": str(raw.get("collected_at") or ""),
            "samples": samples,
        }

    def _trusted_context(
        self,
        profile_id: str,
        message: ConversationMessage,
        messages: Sequence[ConversationMessage],
        commands: Sequence[ConversationCommand],
    ) -> Tuple[Any, set[str]]:
        """组装只含当前 profile 可验证事实的对话 Agent 上下文。"""
        board = self._repository.load_board(profile_id)
        board_ids = [item.candidate_id for item in board.recommendations] if board else []
        candidates = []
        if board is not None:
            candidates = [
                self._candidate_data(item)
                for item in self._repository.load_candidate_snapshot(
                    board.run_id, profile_id
                )
                if item.candidate_id in board_ids
            ]
        analyses = []
        analysis_ids = set()
        if board is not None:
            visible_ids = {
                item.analysis_id for item in board.recommendations if item.analysis_id
            }
            for analysis in self._repository.load_recommendation_analyses(profile_id):
                if analysis.analysis_id in visible_ids:
                    analyses.append(analysis.to_dict())
                    analysis_ids.add(analysis.analysis_id)
        memory = self._repository.load_preference_memory(profile_id)
        memory_data = memory.to_dict()
        memory_ids = {
            item.item_id
            for item in memory.items
            if item.status == "active" and not item.tombstone
        }
        playback = self._playback_data(
            self._repository.load_playback_snapshot(profile_id)
        )
        playback_ids = {
            str(item.get("stable_id") or "")
            for item in playback.get("samples") or []
            if isinstance(item, Mapping) and item.get("stable_id")
        }
        proposals = [
            {
                "proposal_id": item.proposal_id,
                "status": item.status,
                "impact_preview": list(item.impact_preview),
            }
            for item in self._repository.load_memory_proposals(profile_id)
            if item.status == "pending_confirmation"
        ][-8:]
        questions = [
            {
                "question_id": item.question_id,
                "status": item.status,
                "question": item.question,
            }
            for item in self._repository.load_pending_questions(profile_id)
            if item.status == "pending"
        ][-8:]
        pending_commands = [
            {
                "command_id": item.command_id,
                "kind": item.kind,
                "preview": item.preview,
            }
            for item in commands
            if item.status == "pending_confirmation"
        ][-8:]
        history = [
            {
                "message_id": item.message_id,
                "role": item.role,
                "content": item.content,
                "status": item.status,
            }
            for item in messages
            if item.status == "completed" and item.message_id != message.message_id
        ][-8:]
        allowed_refs = {
            *[f"candidate:{item}" for item in board_ids],
            *[f"analysis:{item}" for item in analysis_ids],
            *[f"memory:{item}" for item in memory_ids],
            *[f"playback:{item}" for item in playback_ids],
        }
        context = build_trusted_context(
            username=self._scope_token("profile", profile_id),
            run_id=self._scope_token("message", message.message_id),
            candidates=candidates,
            archive_feedback={"entries": []},
            weights={},
            playback=playback,
            agent_role=CONVERSATION_AGENT_ROLE,
            confirmed_memory=memory_data,
            analysis={"items": analyses},
            pending_context={
                "memory_proposals": proposals,
                "questions": questions,
                "commands": pending_commands,
            },
            conversation={
                "thread_id": message.thread_id,
                "current_message": {
                    "message_id": message.message_id,
                    "content": message.content,
                },
                "recent_messages": history,
            },
        )
        return context, allowed_refs

    @staticmethod
    def _command_conflict_key(command: ConversationCommand) -> str:
        """返回用于 supersedes 的确定性命令目标键。"""
        payload = dict(command.payload)
        if command.kind == "profile_tag":
            return f"profile_tag:{payload.get('kind')}:{payload.get('tag')}"
        if command.kind == "weight":
            return f"weight:{payload.get('weight_name')}"
        if command.kind in {"ignore", "subscribe"}:
            return f"{command.kind}:{payload.get('candidate_id')}"
        return command.kind

    def _materialize_commands(
        self,
        *,
        profile_id: str,
        thread: ConversationThread,
        source_message: ConversationMessage,
        drafts: Sequence[ConversationCommandDraft],
        existing: Sequence[ConversationCommand],
    ) -> Tuple[List[ConversationCommand], List[ConversationCommand]]:
        """用当前榜单事实重建命令并标记同目标旧提案被替代。"""
        board = self._repository.load_board(profile_id)
        board_items = {
            item.candidate_id: item for item in (board.recommendations if board else ())
        }
        now = self._now()
        created = []
        updated_existing = list(existing)
        for index, draft in enumerate(drafts, 1):
            payload = dict(draft.payload)
            if draft.kind == "profile_tag":
                title = "更新明确偏好标签"
                action_text = {"add": "添加", "remove": "归档", "restore": "恢复"}.get(
                    str(payload.get("action") or ""), "更新"
                )
                direction = "喜欢" if payload.get("kind") == "positive" else "不喜欢"
                preview = f"{action_text}{direction}标签：{str(payload.get('tag') or '')[:20]}"
            elif draft.kind == "weight":
                if str(payload.get("weight_name") or "") not in WEIGHT_DEFAULTS:
                    raise ConversationError(
                        "invalid_agent_command", "Agent 提出了未知权重", 502
                    )
                title = "调整全局基准权重"
                preview = (
                    f"将 {payload.get('weight_name')} 调整为 "
                    f"{float(payload.get('value')):.2f}；仅管理员可确认"
                )
            elif draft.kind in {"ignore", "subscribe"}:
                candidate_id = str(payload.get("candidate_id") or "").strip()
                item = board_items.get(candidate_id)
                if board is None or item is None:
                    raise ConversationError(
                        "stale_agent_command", "Agent 引用了当前榜单外的作品", 502
                    )
                if draft.kind == "ignore":
                    payload = {
                        "candidate_id": candidate_id,
                        "run_id": board.run_id,
                        "analysis_id": item.analysis_id,
                        "board_revision": board.revision,
                    }
                    title = "忽略榜单作品"
                    preview = f"从当前榜单忽略：{item.title}"
                else:
                    payload = {"candidate_id": candidate_id}
                    title = "订阅榜单作品"
                    preview = f"确认后订阅：{item.title}"
            else:
                payload = {}
                title = "重置专属影评师学习数据"
                preview = "清除反馈、记忆、对话与学习策略；保留榜单和人工标签"
            payload_json = json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            command_id = self._stable_id(
                "conversation-command",
                source_message.message_id,
                index,
                draft.kind,
                payload_json,
            )
            command = ConversationCommand(
                command_id=command_id,
                profile_id=profile_id,
                thread_id=thread.thread_id,
                source_message_id=source_message.message_id,
                kind=draft.kind,
                title=title,
                preview=preview,
                payload=payload,
                requested_by_mp_user_id=source_message.created_by_mp_user_id,
                created_at=now,
                requires_superuser=draft.kind == "weight",
            )
            conflict_key = self._command_conflict_key(command)
            for position, current in enumerate(updated_existing):
                if (
                    current.status == "pending_confirmation"
                    and self._command_conflict_key(current) == conflict_key
                ):
                    superseded = current.resolve(
                        status="superseded",
                        actor_id=source_message.created_by_mp_user_id,
                        resolved_at=now,
                        code="superseded",
                        message="已由更新的对话命令替代",
                    )
                    updated_existing[position] = superseded
                    command = replace(command, supersedes=current.command_id)
            created.append(command)
            updated_existing.append(command)
        return updated_existing, created

    @staticmethod
    def _provenance(value: Any) -> Tuple[str, str]:
        """只读取 Agent 适配器允许公开的供应商与模型字段。"""
        raw = getattr(value, "provenance", None)
        provenance = dict(raw) if isinstance(raw, Mapping) else {}
        return (
            str(provenance.get("provider") or "")[:80],
            str(provenance.get("model") or "")[:120],
        )

    def _snapshot_data(
        self,
        thread: ConversationThread,
        messages: Sequence[ConversationMessage],
        commands: Sequence[ConversationCommand],
        *,
        created: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """返回前端可安全展示的完整线程快照。"""
        data = {
            "thread": thread.to_public_dict(),
            "messages": [item.to_public_dict() for item in messages],
            "commands": [item.to_public_dict() for item in commands],
        }
        if created is not None:
            data["created"] = bool(created)
        return data

    def snapshot(self, profile_id: str) -> Dict[str, Any]:
        """读取一个 profile 的当前有界对话快照。"""
        thread = self._repository.load_conversation_thread(profile_id)
        if thread is None:
            return {"thread": None, "messages": [], "commands": []}
        messages, commands = self._repository.load_conversation_records(profile_id)
        return self._snapshot_data(thread, messages, commands)

    async def send(
        self,
        *,
        profile_id: str,
        content: Any,
        idempotency_key: Any,
        actor_id: str,
    ) -> Dict[str, Any]:
        """幂等保存用户草稿、调用只读 Agent 并原子完成一轮对话。"""
        target = str(profile_id or "").strip()
        actor = str(actor_id or "").strip()
        if not target or not actor:
            raise ConversationError("conversation_actor_required", "无法确认当前操作用户", 403)
        text = self._message_text(content)
        key = self._idempotency_key(idempotency_key)
        now = self._now()
        with self._repository.feedback_action_guard(target):
            thread = self._thread(target, actor, now)
            messages, commands = self._repository.load_conversation_records(
                target, strict=True
            )
            for existing in messages:
                if existing.role != "user" or existing.idempotency_key != key:
                    continue
                if existing.content != text or existing.created_by_mp_user_id != actor:
                    raise ConversationError(
                        "idempotency_conflict", "该幂等键已用于不同消息", 409
                    )
                return self._snapshot_data(thread, messages, commands, created=False)
            message = ConversationMessage(
                message_id=self._stable_id("conversation-message", target, actor, key),
                profile_id=target,
                thread_id=thread.thread_id,
                role="user",
                content=text,
                status="processing",
                created_at=now,
                idempotency_key=key,
                created_by_mp_user_id=actor,
            )
            thread = replace(
                thread,
                updated_at=now,
                revision=thread.revision + 1,
                last_message_id=message.message_id,
            )
            messages.append(message)
            self._repository.save_conversation_state(
                thread, messages, commands, limit=self._message_limit
            )
        return await self._run_message(target, message.message_id, created=True)

    async def retry(
        self, *, profile_id: str, message_id: str, actor_id: str
    ) -> Dict[str, Any]:
        """仅重试当前操作者的一条失败草稿，不创建重复消息。"""
        target = str(profile_id or "").strip()
        actor = str(actor_id or "").strip()
        source_id = str(message_id or "").strip()
        with self._repository.feedback_action_guard(target):
            thread = self._repository.load_conversation_thread(target)
            messages, commands = self._repository.load_conversation_records(
                target, strict=True
            )
            if thread is None:
                raise ConversationError("conversation_not_found", "对话不存在", 404)
            source = next((item for item in messages if item.message_id == source_id), None)
            if source is None or source.role != "user":
                raise ConversationError("message_not_found", "待重试消息不存在", 404)
            if source.created_by_mp_user_id != actor:
                raise ConversationError("message_forbidden", "不能重试其他用户的消息", 403)
            if source.status != "failed":
                raise ConversationError("message_not_retryable", "该消息当前不能重试", 409)
            source = replace(
                source,
                status="processing",
                error_code="",
                error_message="",
                provider="",
                model="",
            )
            messages = [source if item.message_id == source_id else item for item in messages]
            self._repository.save_conversation_state(
                thread, messages, commands, limit=self._message_limit
            )
        return await self._run_message(target, source_id, created=False)

    async def _run_message(
        self, profile_id: str, message_id: str, *, created: bool
    ) -> Dict[str, Any]:
        """调用受限 Agent，并把成功或失败状态原子写回草稿。"""
        thread = self._repository.load_conversation_thread(profile_id)
        messages, commands = self._repository.load_conversation_records(
            profile_id, strict=True
        )
        source = next((item for item in messages if item.message_id == message_id), None)
        if thread is None or source is None or source.status != "processing":
            raise ConversationError("message_not_processing", "消息状态已变化，请刷新", 409)
        trusted_context, allowed_refs = self._trusted_context(
            profile_id, source, messages, commands
        )
        try:
            method = getattr(self._agent_adapter, "run_conversation", None)
            if not callable(method):
                method = getattr(self._agent_adapter, "run", None)
            if not callable(method):
                raise RuntimeError("conversation Agent adapter is unavailable")
            raw = await method(build_conversation_prompt(), trusted_context)
            parsed = ConversationReplyParser.parse(
                raw, allowed_evidence_refs=allowed_refs
            )
            provider, model = self._provenance(raw)
        except Exception as error:
            with self._repository.feedback_action_guard(profile_id):
                current_thread = self._repository.load_conversation_thread(profile_id)
                current_messages, current_commands = self._repository.load_conversation_records(
                    profile_id, strict=True
                )
                current = next(
                    (item for item in current_messages if item.message_id == message_id),
                    None,
                )
                if current_thread is not None and current is not None and current.status == "processing":
                    provenance = getattr(error, "agentrank_provenance", None)
                    safe = dict(provenance) if isinstance(provenance, Mapping) else {}
                    failed = replace(
                        current,
                        status="failed",
                        error_code=(
                            error.code
                            if isinstance(error, ConversationError)
                            else "agent_unavailable"
                        ),
                        error_message="对话生成失败，草稿已保留，可重试",
                        provider=str(safe.get("provider") or "")[:80],
                        model=str(safe.get("model") or "")[:120],
                    )
                    current_messages = [
                        failed if item.message_id == message_id else item
                        for item in current_messages
                    ]
                    self._repository.save_conversation_state(
                        current_thread,
                        current_messages,
                        current_commands,
                        limit=self._message_limit,
                        action="conversation_failure_write_failed",
                    )
            if isinstance(error, ConversationError):
                raise
            raise ConversationError(
                "conversation_failed", "对话生成失败，草稿已保留，可重试", 502
            ) from error
        with self._repository.feedback_action_guard(profile_id):
            thread = self._repository.load_conversation_thread(profile_id)
            messages, commands = self._repository.load_conversation_records(
                profile_id, strict=True
            )
            source = next((item for item in messages if item.message_id == message_id), None)
            if thread is None or source is None or source.status != "processing":
                raise ConversationError("message_superseded", "消息已被其他请求更新", 409)
            try:
                commands, created_commands = self._materialize_commands(
                    profile_id=profile_id,
                    thread=thread,
                    source_message=source,
                    drafts=parsed.commands,
                    existing=commands,
                )
            except Exception as error:
                failed = replace(
                    source,
                    status="failed",
                    error_code=(
                        error.code
                        if isinstance(error, ConversationError)
                        else "invalid_agent_command"
                    ),
                    error_message="Agent 命令无法绑定当前榜单，草稿已保留，可重试",
                    provider=provider,
                    model=model,
                )
                messages = [
                    failed if item.message_id == source.message_id else item
                    for item in messages
                ]
                self._repository.save_conversation_state(
                    thread,
                    messages,
                    commands,
                    limit=self._message_limit,
                    action="conversation_command_validation_write_failed",
                )
                if isinstance(error, ConversationError):
                    raise
                raise ConversationError(
                    "invalid_agent_command",
                    "Agent 命令无法绑定当前榜单，草稿已保留，可重试",
                    502,
                ) from error
            assistant_id = self._stable_id("conversation-reply", source.message_id)
            assistant = ConversationMessage(
                message_id=assistant_id,
                profile_id=profile_id,
                thread_id=thread.thread_id,
                role="assistant",
                content=parsed.reply,
                status="completed",
                created_at=self._now(),
                reply_to=source.message_id,
                related_candidate_ids=tuple(
                    item.removeprefix("candidate:")
                    for item in parsed.evidence_refs
                    if item.startswith("candidate:")
                ),
                related_analysis_ids=tuple(
                    item.removeprefix("analysis:")
                    for item in parsed.evidence_refs
                    if item.startswith("analysis:")
                ),
                command_ids=tuple(item.command_id for item in created_commands),
                provider=provider,
                model=model,
            )
            completed_source = replace(source, status="completed")
            messages = [
                completed_source if item.message_id == source.message_id else item
                for item in messages
            ]
            messages.append(assistant)
            pending_ids = tuple(
                item.command_id
                for item in commands
                if item.status == "pending_confirmation"
            )
            thread = replace(
                thread,
                updated_at=assistant.created_at,
                revision=thread.revision + 1,
                summary=assistant.content[:400],
                last_message_id=assistant.message_id,
                related_analysis_ids=tuple(
                    dict.fromkeys(
                        (*thread.related_analysis_ids, *assistant.related_analysis_ids)
                    )
                )[-24:],
                pending_command_ids=pending_ids[-64:],
            )
            self._repository.save_conversation_state(
                thread,
                messages,
                commands,
                limit=self._message_limit,
                action="conversation_completion_write_failed",
            )
            snapshot = self._snapshot_data(
                thread, messages, commands, created=created
            )
        self._emit_pending(created_commands)
        return snapshot

    def set_command_reminder(
        self,
        *,
        profile_id: str,
        command_id: str,
        reminder_policy: str,
        actor_id: str,
        is_superuser: bool = False,
    ) -> ConversationCommand:
        """为用户自己的待确认命令设置稍后提醒或永不提醒。"""
        target = str(profile_id or "").strip()
        target_id = str(command_id or "").strip()
        actor = str(actor_id or "").strip()
        policy = str(reminder_policy or "").strip().casefold()
        if policy not in {*_REMINDER_DELAYS, "never"}:
            raise ConversationError(
                "reminder_policy_invalid", "提醒时间必须是一、三、七天后或不提醒", 422
            )
        if not actor:
            raise ConversationError(
                "conversation_actor_required", "无法确认当前操作用户", 403
            )
        with self._repository.feedback_action_guard(target):
            thread = self._repository.load_conversation_thread(target)
            messages, commands = self._repository.load_conversation_records(
                target, strict=True
            )
            if thread is None:
                raise ConversationError("conversation_not_found", "对话不存在", 404)
            command = next(
                (item for item in commands if item.command_id == target_id), None
            )
            if command is None:
                raise ConversationError("command_not_found", "待确认命令不存在", 404)
            if command.requested_by_mp_user_id != actor and not is_superuser:
                raise ConversationError("command_forbidden", "不能操作其他用户的命令", 403)
            if command.terminal:
                raise ConversationError(
                    "command_already_resolved", "命令已经处理", 409
                )
            current = self._now_factory()
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            next_remind_at = (
                (current.astimezone(timezone.utc) + _REMINDER_DELAYS[policy]).isoformat()
                if policy in _REMINDER_DELAYS
                else ""
            )
            updated = replace(
                command,
                reminder_policy=policy,
                next_remind_at=next_remind_at,
            )
            commands = [
                updated if item.command_id == target_id else item for item in commands
            ]
            thread = replace(
                thread,
                updated_at=self._now(),
                revision=thread.revision + 1,
            )
            self._repository.save_conversation_state(
                thread, messages, commands, limit=self._message_limit
            )
            return updated

    def claim_due_command_reminders(
        self, profile_id: str
    ) -> List[ConversationCommand]:
        """原子领取到期命令提醒并清空本次提醒时间。"""
        target = str(profile_id or "").strip()
        current = self._now_factory()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)
        with self._repository.feedback_action_guard(target):
            thread = self._repository.load_conversation_thread(target)
            messages, commands = self._repository.load_conversation_records(
                target, strict=True
            )
            if thread is None:
                return []
            claimed: List[ConversationCommand] = []
            updated_commands: List[ConversationCommand] = []
            for command in commands:
                if command.status != "pending_confirmation" or not command.next_remind_at:
                    updated_commands.append(command)
                    continue
                due = datetime.fromisoformat(
                    command.next_remind_at.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                if due > current:
                    updated_commands.append(command)
                    continue
                updated = replace(
                    command,
                    next_remind_at="",
                    last_reminded_at=current.isoformat(),
                )
                updated_commands.append(updated)
                claimed.append(updated)
            if not claimed:
                return []
            thread = replace(
                thread,
                updated_at=current.isoformat(),
                revision=thread.revision + 1,
            )
            self._repository.save_conversation_state(
                thread, messages, updated_commands, limit=self._message_limit
            )
            return claimed

    def _execute_command(
        self, command: ConversationCommand, *, actor_id: str, is_superuser: bool
    ) -> Tuple[str, str, Dict[str, Any]]:
        """把确认命令委托给现有受控 service，并返回安全结果。"""
        if command.requires_superuser and not is_superuser:
            raise ConversationError(
                "superuser_required", "该全局设置只能由管理员确认", 403
            )
        payload = dict(command.payload)
        if command.kind == "profile_tag":
            result = ProfilePreferenceService(self._repository).update(
                command.profile_id,
                str(payload.get("kind") or ""),
                str(payload.get("action") or ""),
                payload.get("tag"),
            )
            return (
                "profile_tag_updated",
                "明确偏好标签已更新" if result.changed else "明确偏好标签无需变更",
                {"changed": result.changed},
            )
        if command.kind == "weight":
            if self._plugin is None or not hasattr(self._plugin, "update_config"):
                raise ConversationError("config_unavailable", "插件配置服务不可用", 503)
            weight_name = str(payload.get("weight_name") or "")
            old_config = dict(getattr(self._plugin, "_config", {}) or {})
            updated = dict(old_config)
            updated_weights = dict(updated.get("weights") or {})
            updated_weights[weight_name] = float(payload.get("value"))
            updated["weights"] = updated_weights
            normalized = normalize_config(updated)
            persisted = {
                key: value for key, value in normalized.items() if key != "_validation_errors"
            }
            try:
                self._plugin.update_config(config=persisted)
                self._plugin._config = dict(normalized)
                runtime = getattr(self._plugin, "_runtime", None)
                if runtime is not None and isinstance(getattr(runtime, "config", None), dict):
                    runtime.config["weights"] = dict(normalized.get("weights") or {})
            except Exception as error:
                self._plugin._config = old_config
                raise ConversationError(
                    "weight_update_failed", "权重保存失败，原配置已保留", 500
                ) from error
            return "weight_updated", "全局基准权重已更新", {"changed": True}
        if command.kind == "ignore":
            result = FeedbackActionService(
                self._repository,
                analysis_limit=int(
                    (getattr(self._plugin, "_config", {}) or {}).get(
                        "analysis_record_limit", 500
                    )
                ),
            ).act(
                profile_id=command.profile_id,
                candidate_id=str(payload.get("candidate_id") or ""),
                kind="ignore",
                idempotency_key=f"conversation-command:{command.command_id}",
                actor_id=actor_id,
                analysis_id=str(payload.get("analysis_id") or ""),
                expected_board_revision=payload.get("board_revision"),
                expected_run_id=str(payload.get("run_id") or ""),
            )
            queue = getattr(self._plugin, "_feedback_queue", None) if self._plugin else None
            if queue is not None and hasattr(queue, "enqueue_event"):
                try:
                    queue.enqueue_event(result.event)
                except Exception:
                    return (
                        "candidate_ignored_learning_pending",
                        "作品已忽略，偏好理解任务可稍后重试",
                        {"changed": result.changed, "learning_pending": True},
                    )
            return "candidate_ignored", "作品已从当前榜单忽略", {"changed": result.changed}
        if command.kind == "subscribe":
            runtime = getattr(self._plugin, "_runtime", None) if self._plugin else None
            service = getattr(runtime, "subscription_service", None) if runtime else None
            if service is None:
                raise ConversationError(
                    "subscription_not_ready", "订阅安全链尚未就绪", 409
                )
            threshold = float(
                (getattr(self._plugin, "_config", {}) or {}).get(
                    "confidence_threshold", 0.0
                )
            )
            result = service.subscribe(
                command.profile_id,
                str(payload.get("candidate_id") or ""),
                threshold,
            )
            if not result.success:
                raise ConversationError(result.code, result.message, 409)
            return result.code, result.message, {"changed": result.changed}
        lifecycle = DataLifecycleService(
            self._repository,
            getattr(self._plugin, "_config", {}) if self._plugin else {},
        )
        result = lifecycle.reset_learning(command.profile_id, True)
        return "learning_reset", "专属影评师学习数据已重置", result

    def respond_command(
        self,
        *,
        profile_id: str,
        command_id: str,
        action: str,
        actor_id: str,
        is_superuser: bool = False,
    ) -> Dict[str, Any]:
        """确认或拒绝一条命令；重复同终态请求保持幂等。"""
        target = str(profile_id or "").strip()
        actor = str(actor_id or "").strip()
        target_command_id = str(command_id or "").strip()
        decision = str(action or "").strip()
        if decision not in {"confirm", "reject"}:
            raise ConversationError(
                "invalid_command_action", "命令操作必须是 confirm 或 reject", 422
            )
        if not actor:
            raise ConversationError("conversation_actor_required", "无法确认当前操作用户", 403)
        with self._repository.feedback_action_guard(target):
            thread = self._repository.load_conversation_thread(target)
            messages, commands = self._repository.load_conversation_records(
                target, strict=True
            )
            if thread is None:
                raise ConversationError("conversation_not_found", "对话不存在", 404)
            command = next(
                (item for item in commands if item.command_id == target_command_id),
                None,
            )
            if command is None:
                raise ConversationError("command_not_found", "待确认命令不存在", 404)
            if command.requested_by_mp_user_id != actor and not is_superuser:
                raise ConversationError("command_forbidden", "不能确认其他用户的命令", 403)
            desired_status = "confirmed" if decision == "confirm" else "rejected"
            if command.terminal:
                if command.status == desired_status:
                    return {
                        "command": command.to_public_dict(),
                        "idempotent": True,
                    }
                raise ConversationError(
                    "command_already_resolved", "命令已经以其他结果结束", 409
                )
            now = self._now()
            if decision == "reject":
                resolved = command.resolve(
                    status="rejected",
                    actor_id=actor,
                    resolved_at=now,
                    code="rejected",
                    message="用户已拒绝执行",
                )
                result_data: Dict[str, Any] = {"changed": False}
            elif command.kind == "reset_learning":
                prepared = command.resolve(
                    status="confirmed",
                    actor_id=actor,
                    resolved_at=now,
                    code="learning_reset",
                    message="专属影评师学习数据已重置",
                )
                commands = [
                    prepared if item.command_id == command.command_id else item
                    for item in commands
                ]
                thread = replace(
                    thread,
                    updated_at=now,
                    revision=thread.revision + 1,
                    pending_command_ids=tuple(
                        item.command_id
                        for item in commands
                        if item.status == "pending_confirmation"
                    ),
                )
                self._repository.save_conversation_state(
                    thread, messages, commands, limit=self._message_limit
                )
                code, message, result_data = self._execute_command(
                    command, actor_id=actor, is_superuser=is_superuser
                )
                receipt_thread = ConversationThread(
                    thread_id=thread.thread_id,
                    profile_id=thread.profile_id,
                    created_by_mp_user_id=thread.created_by_mp_user_id,
                    created_at=thread.created_at,
                    updated_at=now,
                    revision=thread.revision + 1,
                    summary="专属影评师学习数据已重置。",
                )
                self._repository.save_conversation_state(
                    receipt_thread,
                    [],
                    [prepared],
                    limit=self._message_limit,
                    action="conversation_reset_receipt_write_failed",
                )
                return {
                    "command": prepared.to_public_dict(),
                    "idempotent": False,
                    "result": result_data,
                    "conversation_cleared": True,
                    "receipt_preserved": True,
                }
            else:
                try:
                    code, message, result_data = self._execute_command(
                        command, actor_id=actor, is_superuser=is_superuser
                    )
                    resolved = command.resolve(
                        status="confirmed",
                        actor_id=actor,
                        resolved_at=now,
                        code=code,
                        message=message,
                    )
                except ConversationError:
                    raise
                except Exception as error:
                    resolved = command.resolve(
                        status="failed",
                        actor_id=actor,
                        resolved_at=now,
                        code="command_failed",
                        message="命令执行失败，未确认任何新偏好",
                    )
                    result_data = {"changed": False}
                    commands = [
                        resolved if item.command_id == command.command_id else item
                        for item in commands
                    ]
                    thread = replace(
                        thread,
                        updated_at=now,
                        revision=thread.revision + 1,
                        pending_command_ids=tuple(
                            item.command_id
                            for item in commands
                            if item.status == "pending_confirmation"
                        ),
                    )
                    self._repository.save_conversation_state(
                        thread, messages, commands, limit=self._message_limit
                    )
                    raise ConversationError(
                        "command_failed", "命令执行失败，原状态已保留", 500
                    ) from error
            commands = [
                resolved if item.command_id == command.command_id else item
                for item in commands
            ]
            thread = replace(
                thread,
                updated_at=now,
                revision=thread.revision + 1,
                pending_command_ids=tuple(
                    item.command_id
                    for item in commands
                    if item.status == "pending_confirmation"
                ),
            )
            self._repository.save_conversation_state(
                thread, messages, commands, limit=self._message_limit
            )
            return {
                "command": resolved.to_public_dict(),
                "idempotent": False,
                "result": result_data,
            }
