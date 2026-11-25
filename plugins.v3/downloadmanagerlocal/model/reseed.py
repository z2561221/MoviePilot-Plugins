"""辅助铺种任务接口模型。"""

from pydantic import BaseModel, Field


class StopRequest(BaseModel):
    """仅停止明确指定的当前任务。"""

    task_id: str = Field(min_length=1, max_length=100)


class TaskResult(BaseModel):
    """轻量任务状态与计数。"""

    task_id: str = ""
    status: str = "idle"
    mode: str = "iyuu"
    preview: bool = False
    phase: str = ""
    message: str = ""
    scanned: int = 0
    matched: int = 0
    added: int = 0
    skipped: int = 0
    failed: int = 0
    result_count: int = 0
    submission_count: int = 0
    addition_limit: int = 20
    source_limit: int = 0
    created_at: float = 0
    updated_at: float = 0


class ResultItem(BaseModel):
    """不包含站点凭据的候选处理回执。"""

    state: str
    message: str
    source_hash: str = ""
    site: str = ""
    target_hash: str = ""
    downloader: str = ""


class ResultPage(BaseModel):
    """当前任务结果的分页视图。"""

    task_id: str
    items: list[ResultItem] = Field(default_factory=list)
    total: int = 0
