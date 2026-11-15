"""转种、辅种、校验与删除的公共实例互斥、停止代次和避让边界。"""

from functools import wraps
from threading import RLock

from ..model.sync_delete import BLOCKS_KEY
from ..utils.torrent_adapter import normalize_torrent

_INIT_LOCK = RLock()


def operation_lock(plugin):
    """下载、辅种、校验与删除共用实例锁，避免扫描后又重新创建目标。"""
    with _INIT_LOCK:
        if not hasattr(plugin, "_sync_delete_operation_lock"):
            plugin._sync_delete_operation_lock = RLock()
        return plugin._sync_delete_operation_lock


def operation_stopped(plugin, generation: int) -> bool:
    """共享停止判定用于在途查询回包后的写入门禁。"""
    event = getattr(plugin, "_event", None)
    return (int(getattr(plugin, "_transfer_stop_generation", 0) or 0) != generation
            or (event is not None and event.is_set()))


def coordinated(function):
    """为已有批次入口提供同实例互斥，不改变普通执行结果。"""
    @wraps(function)
    def wrapper(plugin, *args, **kwargs):
        """等锁前固定停止代次，取消后不进入业务，嵌套调用恢复外层快照。"""
        generation = int(getattr(plugin, "_transfer_stop_generation", 0) or 0)
        guard = operation_lock(plugin)
        while not operation_stopped(plugin, generation):
            if guard.acquire(timeout=0.2):
                break
        else:
            return None
        previous = getattr(plugin, "_sync_delete_block_snapshot", None)
        previous_index = getattr(plugin, "_sync_delete_block_index", None)
        try:
            if operation_stopped(plugin, generation):
                return None
            plugin._sync_delete_block_snapshot = (plugin.get_data(BLOCKS_KEY) or {}) if hasattr(plugin, "get_data") else {}
            plugin._sync_delete_block_index = _block_identity_index(plugin._sync_delete_block_snapshot)
            return function(plugin, *args, **kwargs)
        finally:
            plugin._sync_delete_block_snapshot = previous
            plugin._sync_delete_block_index = previous_index
            guard.release()
    return wrapper


def _block_identity_index(blocks) -> frozenset:
    """为批次避让快照建立索引，保留下载器、hash 与创建时间的原匹配语义。"""
    identities = set()
    if not isinstance(blocks, dict):
        return frozenset()
    for block in blocks.values():
        identity = block.get("identity", [])
        downloader = block.get("downloader")
        if (len(identity) == 3 and isinstance(downloader, str)
                and isinstance(identity[0], str) and isinstance(identity[1], (int, float))):
            identities.add((downloader, identity[0], identity[1]))
    return frozenset(identities)


def task_blocked(plugin, downloader: str, torrent, kind: str) -> bool:
    """仅阻止同一创建时间/路径的旧任务；重新下载后的新任务不被永久封锁。"""
    if not hasattr(plugin, "get_data"):
        return False
    index = getattr(plugin, "_sync_delete_block_index", None)
    if index is None:
        blocks = getattr(plugin, "_sync_delete_block_snapshot", None)
        if blocks is None:
            blocks = plugin.get_data(BLOCKS_KEY) or {}
        index = _block_identity_index(blocks)
    if not index:
        return False
    current = normalize_torrent(torrent, downloader, kind)
    return (downloader, current.torrent_hash, current.added_at) in index


