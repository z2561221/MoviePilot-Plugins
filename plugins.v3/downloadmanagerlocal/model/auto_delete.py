"""自动删除规则、任务快照和接口数据合同。"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal
from uuid import uuid4

import regex
from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTROL_KEY = "auto_delete_control"
BLOCKS_KEY = "auto_delete_blocks"
INDEX_KEY = "auto_delete_job_index"
JOB_PREFIX = "auto_delete_job_"
STATUS_KEY = "auto_delete_status"
RETIREMENTS_KEY = "auto_delete_retirements"
TERMINAL_STATES = {"removed", "deleted", "released", "absent"}
UNSETTLED_STATES = {"prepared", "pausing", "approved", "deleting", "removing", "restoring"}
JOB_STATES = Literal["prepared", "pausing", "paused", "approved", "deleting", "removing",
                     "restoring", "removed", "deleted", "released", "absent", "review"]
MODULE_STATES = Literal["disabled", "idle", "accepted", "running", "degraded", "error", "preview", "stopped"]
REGEX_FIELDS = (
    "name_include", "name_exclude", "path_include", "path_exclude",
    "tracker_include", "tracker_exclude", "tracker_error", "category",
    "tag_include", "tag_exclude",
)
NUMBER_FIELDS = (
    "ratio_min", "ratio_max", "seed_hours_min", "added_hours_min",
    "size_gib_min", "size_gib_max", "upload_kib_max",
)


class StrictModel(BaseModel):
    """拒绝未声明参数，避免配置字段拼写错误被静默忽略。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Conditions(StrictModel):
    """一条规则内按 AND 判断的名称、范围及数值条件。"""

    name_include: str = Field(default="", max_length=1024)
    name_exclude: str = Field(default="", max_length=1024)
    path_include: str = Field(default="", max_length=1024)
    path_exclude: str = Field(default="", max_length=1024)
    tracker_include: str = Field(default="", max_length=1024)
    tracker_exclude: str = Field(default="", max_length=1024)
    tracker_error: str = Field(default="", max_length=1024)
    category: str = Field(default="", max_length=1024)
    tag_include: str = Field(default="", max_length=1024)
    tag_exclude: str = Field(default="", max_length=1024)
    ratio_min: float | None = Field(default=None, ge=0)
    ratio_max: float | None = Field(default=None, ge=0)
    seed_hours_min: float | None = Field(default=None, ge=0)
    added_hours_min: float | None = Field(default=None, ge=0)
    size_gib_min: float | None = Field(default=None, ge=0)
    size_gib_max: float | None = Field(default=None, ge=0)
    upload_kib_max: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_conditions(self):
        """保存前校验正则及区间，空值保留为不限制。"""
        for field_name in REGEX_FIELDS:
            pattern = getattr(self, field_name)
            if pattern:
                try:
                    regex.compile(pattern)
                except regex.error as error:
                    raise ValueError(f"{field_name} 正则无效：{error}") from error
        for minimum, maximum in ((self.ratio_min, self.ratio_max),
                                 (self.size_gib_min, self.size_gib_max)):
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError("最小值不能大于最大值")
        return self


class Rule(StrictModel):
    """有稳定 ID、修订号及独立调试/正式模式的规则。"""

    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(default="新规则", min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    enabled: bool = False
    mode: Literal["debug", "delete"] = "debug"
    action: Literal["torrent", "data"] = "torrent"
    downloaders: list[str] = Field(default_factory=list, max_length=64)
    ignore_case: bool = True
    consecutive: int = Field(default=2, ge=1, le=20)
    conditions: Conditions = Field(default_factory=Conditions)

    @model_validator(mode="after")
    def validate_rule(self):
        """启用规则必须有下载器和至少一项明确条件。"""
        self.downloaders = list(dict.fromkeys(name.strip() for name in self.downloaders if name.strip()))
        self.name = self.name.strip()
        if not self.name or any(len(name) > 128 for name in self.downloaders):
            raise ValueError("规则名不能为空，下载器标识不得超过 128 字符")
        if self.enabled and (not self.downloaders or not any(
            value is not None and value != "" for value in self.conditions.model_dump().values()
        )):
            raise ValueError("启用规则必须选择下载器并填写至少一个条件")
        return self


class Settings(StrictModel):
    """自动删除模块独立设置，由插件配置通道持久化。"""

    enabled: bool = False
    schedule_type: Literal["interval", "cron"] = "interval"
    interval_minutes: int = Field(default=5, ge=1, le=10080)
    cron: str = Field(default="", max_length=128)
    sample_minutes: int = Field(default=5, ge=1, le=10080)
    max_tasks: int = Field(default=20, ge=1, le=1000)
    source_paths: list[str] = Field(default_factory=list, max_length=64)
    exclude_paths: list[str] = Field(default_factory=list, max_length=64)
    notify: bool = False
    history_days: int = Field(default=30, ge=1, le=3650)
    rules: list[Rule] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_settings(self):
        """检查规则唯一性、Cron 及删除数据所需的允许目录。"""
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError("规则 ID 不能重复；复制规则须生成新 ID")
        if self.schedule_type == "cron" and (self.enabled or self.cron):
            try:
                CronTrigger.from_crontab(self.cron, timezone="Asia/Shanghai")
            except ValueError as error:
                raise ValueError("Cron 表达式无效") from error
        if any(rule.enabled and rule.action == "data" for rule in self.rules) and not self.source_paths:
            raise ValueError("删除下载数据必须填写允许删除的下载目录")
        for path_text in self.source_paths + self.exclude_paths:
            if (not path_text.startswith("/") or path_text.startswith("//")
                    or path_text.rstrip("/") == "" or ".." in path_text.split("/")
                    or "\\" in path_text or "\x00" in path_text):
                raise ValueError("删除目录须为 MP 容器内的绝对目录，不能使用根目录或 ..")
        return self


def settings_from_config(config: dict | None) -> Settings:
    """仅消费本模块前缀字段，保留宿主及其他模块的配置。"""
    source = config if isinstance(config, dict) else {}
    return Settings.model_validate({name: source["auto_delete_" + name]
                                    for name in Settings.model_fields
                                    if "auto_delete_" + name in source})


def config_values(settings: Settings, revision: int | None = None) -> dict:
    """把模块设置转换为插件配置字段。"""
    payload = {"auto_delete_" + name: value for name, value in settings.model_dump(mode="json").items()}
    if revision is not None:
        payload["auto_delete_config_revision"] = revision
    return payload


def digest(value) -> str:
    """只保存规范 JSON 的 SHA256，不输出下载器凭据。"""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


class Tracker(StrictModel):
    """同一条 announce 的地址、状态和错误文本。"""

    url: str
    status: str
    message: str = ""


class Snapshot(StrictModel):
    """下载器无关的原生任务快照；未知值与零分开。"""

    downloader: str
    binding: str
    kind: str
    hash: str
    name: str
    added_at: float | None = None
    save_path: str = ""
    total_bytes: int | None = None
    completed: bool = False
    state: str = ""
    ratio: float | None = None
    ratio_state: Literal["finite", "infinite", "unknown"] = "finite"
    seed_seconds: float | None = None
    upload_bps: float | None = None
    upload_limit_bps: float | None = None
    category: str | None = None
    tags: list[str] | None = None
    trackers: list[Tracker] | None = None

    @property
    def identity(self) -> list:
        """创建时间和下载器绑定用于保护同 hash 的后续新任务。"""
        return [self.downloader, self.binding, self.hash, self.added_at, self.save_path]

    @property
    def paused(self) -> bool:
        """兼容 QB 新旧暂停状态和 TR stopped 状态。"""
        return self.state.lower().replace(" ", "").startswith(("paused", "stopped"))

    @property
    def valid_hash(self) -> bool:
        """只接受 v1/v2 十六进制 infohash，拒绝 all 等下载器批量哨兵。"""
        return bool(re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", self.hash))


class MatchResult(StrictModel):
    """匹配、未匹配与无法判断分别反馈，不把异常算成空结果。"""

    rule_id: str
    rule_name: str
    revision: int
    status: Literal["match", "no_match", "unknown"]
    reasons: list[str] = Field(default_factory=list)


class FileTarget(StrictModel):
    """下载数据的精确文件身份及逐文件处理检查点。"""

    path: str
    root: str
    identity: list[int]
    deleted: bool = False
    root_identity: list[int] = Field(default_factory=list)


class SampleEvidence(StrictModel):
    """每次有效采样的原生指标，暂停后不重新解释。"""

    time: float
    snapshot: Snapshot
    reasons: list[str]


class ScanEntry(StrictModel):
    """一个实际任务对各相关规则的判断及有效采样进度。"""

    snapshot: Snapshot
    rules: list[MatchResult]
    protected: bool = False
    samples: dict[str, int] = Field(default_factory=dict)
    required_samples: dict[str, int] = Field(default_factory=dict)
    limit_interference: list[str] = Field(default_factory=list)
    block_reason: str = ""


class Job(StrictModel):
    """逐任务状态与不可重新解释的暂停前证据。"""

    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    state: JOB_STATES
    rule_id: str
    rule_name: str
    revision: int = Field(ge=1)
    downloader: str
    torrent_hash: str
    name: str
    identity: list[str | float | None]
    rule_fingerprint: str = ""
    evidence_fingerprint: str = ""
    mode: Literal["debug", "delete"] = "debug"
    action: Literal["torrent", "data"] = "torrent"
    snapshot: Snapshot
    was_running: bool = False
    evidence: list[str] = Field(default_factory=list)
    sample_evidence: list[SampleEvidence] = Field(default_factory=list)
    matches: list[MatchResult] = Field(default_factory=list)
    debug_rule_ids: list[str] = Field(default_factory=list)
    accepted_at: float | None = None
    accepted_fingerprint: str = ""
    interfered: bool = False
    task_removed: bool = False
    data_deleted: bool = False
    before_pause: Snapshot | None = None
    stage: str = "prepared"
    files: list[FileTarget] = Field(default_factory=list)
    file_list_fingerprint: str = ""
    recheck_snapshot: dict[str, dict[str, str | int | float | bool | None]] = Field(default_factory=dict)
    relation_keys: list[str] = Field(default_factory=list)
    created_at: float
    updated_at: float
    error: str = ""

    @model_validator(mode="after")
    def validate_identity(self):
        """缺少原创建时间或详情身份不一致时拒绝任何后续副作用。"""
        if (self.identity != self.snapshot.identity or not self.snapshot.valid_hash
                or not self.snapshot.added_at or self.snapshot.added_at <= 0
                or self.downloader != self.snapshot.downloader or self.torrent_hash != self.snapshot.hash):
            raise ValueError("自动删除记录缺少可信任务身份")
        return self


class Approval(StrictModel):
    """服务端为一版完整规则生成的正式确认。"""

    revision: int = Field(ge=1)
    fingerprint: str
    confirmed_at: float


class DebugScan(StrictModel):
    """成功的调试扫描及样本数，不能把查询失败记成零命中成功。"""

    revision: int = Field(ge=1)
    fingerprint: str
    time: float
    matched: int = 0
    paused: int = 0


class Capabilities(StrictModel):
    """最近读取时确认的字段能力，None 表示尚未查询。"""

    kind: str = ""
    binding: str = ""
    seed_seconds: bool | None = None
    category: bool | None = None
    tags: bool | None = None
    trackers: bool | None = None
    error: str = ""


class ScanSummary(StrictModel):
    """一次扫描的结果与明确的下一次调度时间。"""

    state: MODULE_STATES = "idle"
    run_id: str = ""
    stage: str = "idle"
    last_scan: float | None = None
    finished_at: float | None = None
    next_run: float | None = None
    scanned: int = 0
    matched: int = 0
    paused: int = 0
    removed: int = 0
    reviewed: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    capabilities: dict[str, Capabilities] = Field(default_factory=dict)


class Result(StrictModel):
    """插件 API 裸查询及显式 envelope 中的业务结果。"""

    state: MODULE_STATES = "idle"
    message: str = ""
    revision: int = 0
    run_id: str = ""
    settings: Settings | None = None
    items: list[Job] = Field(default_factory=list)
    matches: list[ScanEntry] = Field(default_factory=list)
    matches_total: int = 0
    truncated: bool = False
    summary: ScanSummary | None = None
    approvals: dict[str, Approval] = Field(default_factory=dict)
    debug_scans: dict[str, DebugScan] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 15


class Status(ScanSummary):
    """模块当前状态，区分生效、扫描中、队列与尚未读取能力。"""

    enabled: bool = False
    active: bool = False
    error: str = ""
    once_pending: bool = False
    rules: int = 0
    debug_rules: int = 0
    delete_rules: int = 0
    protected: int = 0
    pending: int = 0
    paused_total: int = 0
    removed_total: int = 0
    history_days: int = 30
    schedule_type: str = "interval"
    interval_minutes: int = 5
    sample_minutes: int = 5


class SaveRequest(StrictModel):
    """全量替换本模块配置必须提供当前配置修订。"""

    expected_revision: int = Field(ge=0)
    settings: Settings


class PreviewRequest(StrictModel):
    """预览规则草稿，不保存配置或计数。"""

    settings: Settings


class ActivateRequest(StrictModel):
    """确认当前规则，并单独接受选定暂停任务的历史证据。"""

    expected_revision: int = Field(ge=0)
    rule_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    job_ids: list[str] = Field(default_factory=list, max_length=1000)
    evidence_versions: dict[str, str] = Field(default_factory=dict)
    accept_history: bool = False


class ReleaseRequest(StrictModel):
    """解除自己的保护，可显式要求恢复原运行状态。"""

    job_ids: list[str] = Field(min_length=1, max_length=1000)
    restore: bool = False
