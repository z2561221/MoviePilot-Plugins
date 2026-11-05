"""同步删除的宿主、存储和下载器适配；不在导入时建立连接。"""

from __future__ import annotations

import os
import stat
from pathlib import Path, PurePosixPath

from app.chain.storage import StorageChain
from app.db.oper.downloadhistory import DownloadHistoryOper
from app.db.oper.transferhistory import TransferHistoryOper
from app.schemas import FileItem
from app.sdk.queries import get_transfer_history, list_transfer_history
from app.sdk.services import MediaServerHelper

from ..model.sync_delete import (
    MAX_TARGETS,
    MEDIA_EXTENSIONS,
    DeleteRejected,
    lines,
    path_text,
    text,
    within,
)
from ..utils.torrent_adapter import normalize_torrent


def plain(value) -> dict:
    """把宿主快照/旧下载文件对象收敛为不持有 Session 的普通字段。"""
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {key: getattr(value, key, None) for key in (
        "id", "src", "dest", "src_storage", "dest_storage", "src_fileitem", "dest_fileitem",
        "downloader", "download_hash", "fullpath", "savepath", "state", "type", "seasons", "episodes",
        "media_source", "media_id", "mode", "title", "status",
    )}


def packed(item) -> dict:
    """只持久化文件身份字段，不记录播放地址、pickcode 或凭据。"""
    value = plain(item)
    return {key: value.get(key) for key in
            ("storage", "path", "type", "name", "fileid", "parent_fileid", "size", "modify_time_ns")}


class SyncDeleteAdapter:
    """隔离所有外部影响，测试以同一接口的内存替身验证执行顺序。"""

    def __init__(self, plugin, config: dict):
        self.plugin = plugin
        self.config = config
        self.chain = StorageChain()

    def check_write(self) -> None:
        """网络核验结束后、每次外部写入前再检查停止与配置代次。"""
        runtime = getattr(self.plugin, "_sync_delete_runtime", None)
        if runtime is not None:
            runtime.check(self.config)

    def servers(self) -> list[str]:
        """读取启用的 Emby 服务名称，用于旧通知的单服务器归属判断。"""
        return list(MediaServerHelper().get_services(type_filter="emby"))

    def histories(self, *, search: str = "", source: str = "") -> list[dict]:
        """完整分页读取相关整理历史，截断、重复或总数漂移均拒绝执行。"""
        filters = {"status": True}
        if search:
            filters["text"] = search
        if source:
            filters["src"] = source
        result, seen, total = [], set(), None
        for page_number in range(1, 102):
            page = list_transfer_history(filters=filters, page={"page": page_number, "count": 200})
            if total is None:
                total = page.total
            if total != page.total or total > 20000:
                raise DeleteRejected("整理历史查询规模过大或正在变化，请稍后重试")
            for row in page.items:
                original = plain(row)
                value = {key: original.get(key) for key in (
                    "id", "src", "dest", "src_storage", "dest_storage", "downloader", "download_hash",
                    "seasons", "episodes", "media_source", "media_id", "mode", "status", "type", "title",
                )}
                for key in ("src_fileitem", "dest_fileitem"):
                    value[key] = packed(original[key]) if original.get(key) else {}
                if value["id"] in seen:
                    raise DeleteRejected("整理历史分页出现重复，未形成完整快照")
                seen.add(value["id"])
                result.append(value)
            if not page.has_next:
                if len(result) != total:
                    raise DeleteRejected("整理历史未读取完整")
                return result
        raise DeleteRejected("整理历史超过查询上限")

    def download_files(self, torrent_hash: str = "", path: str = "") -> list[dict]:
        """下载文件状态尚无查询 SDK，使用 v3.2.4 的短生命周期 Oper。"""
        oper = DownloadHistoryOper()
        values = oper.get_files_by_fullpath(path) if path else oper.get_files_by_hash(torrent_hash)
        return [plain(value) for value in values]

    def delete_record(self, record: dict) -> None:
        """实体处理完成后才删除同身份整理记录，不触发宿主的连带删种接口。"""
        current = get_transfer_history(record["id"])
        if current is None:
            return
        current = plain(current)
        if any(text(current.get(key)) != text(record.get(key)) for key in (
                "src", "dest", "src_storage", "dest_storage", "download_hash", "media_source", "media_id")):
            raise DeleteRejected("整理记录身份已变化")
        self.check_write()
        TransferHistoryOper().delete(record["id"])
        if get_transfer_history(record["id"]) is not None:
            raise DeleteRejected("整理记录删除未确认")

    def mark_source_deleted(self, path: str) -> None:
        """实体已经核验删除后更新下载文件状态，不广播整包删除事件。"""
        self.check_write()
        DownloadHistoryOper().delete_file_by_fullpath(path)

    def source_root(self, path: str) -> str:
        """下载源只能在显式允许目录内，且必须排除保护路径。"""
        path = path_text(path)
        if any(within(path, path_text(root)) for root in lines(self.config["sync_delete_exclude_paths"])):
            raise DeleteRejected("下载源位于保护目录")
        roots = [path_text(root) for root in lines(self.config["sync_delete_source_paths"])]
        allowed = [root for root in roots if root != "/" and within(path, root, strict=True)]
        if not allowed:
            raise DeleteRejected("下载源不在已配置的源文件目录内")
        return max(allowed, key=len)

    def lookup(self, storage: str, path: str, root: str) -> dict | None:
        """确认目标存在或不存在；115 逐层使用完整列表，失败绝不归空。"""
        path, root = path_text(path), path_text(root)
        if not within(path, root):
            raise DeleteRejected("文件路径越过允许目录")
        if any(within(path, path_text(value)) for value in lines(self.config["sync_delete_exclude_paths"])):
            raise DeleteRejected("目标文件位于保护目录")
        if storage == "local":
            parent = Path(root)
            if not parent.is_dir():
                raise DeleteRejected("本地根目录不可访问，不能判定文件不存在")
            target = Path(path)
            if not target.resolve().is_relative_to(parent.resolve()):
                raise DeleteRejected("软链接指向允许目录之外")
            try:
                info = target.lstat()
            except FileNotFoundError:
                return None
            if stat.S_ISLNK(info.st_mode):
                raise DeleteRejected("软链接目标需要单独确认")
            return {"storage": storage, "path": path, "type": "dir" if target.is_dir() else "file",
                    "name": target.name, "fileid": None, "size": info.st_size,
                    "identity": [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]}
        if storage != "115网盘Plus":
            # 未核验提供方的空列表语义前，不扩大自动网盘删除范围。
            raise DeleteRejected("当前自动网盘删除仅支持已核验的 115网盘Plus 存储")
        # 从固定网盘根 ID 逐层查找，避免 get_file_item 的旧路径/ID 缓存命中已移动对象。
        current = {"storage": storage, "path": "/", "type": "dir", "fileid": "0", "name": ""}
        for part in PurePosixPath(path).relative_to("/").parts:
            if current["type"] != "dir":
                raise DeleteRejected("目标父路径不是目录")
            children = self.children(current)
            matches = [child for child in children if child["name"] == part]
            if not matches:
                if within(root, current["path"], strict=True):
                    raise DeleteRejected("网盘映射根目录不可确认")
                return None
            if len(matches) != 1:
                raise DeleteRejected("网盘目标名称不唯一")
            current = matches[0]
        if not current.get("fileid"):
            raise DeleteRejected("网盘目标缺少文件 ID")
        current["identity"] = [text(current["fileid"]), current.get("size"), current["type"]]
        return current

    def children(self, parent: dict) -> list[dict]:
        """直接消费存储层结果；P115Disk v3.0.3 查询异常返回 None。"""
        if parent["storage"] == "local":
            result = []
            for child in Path(parent["path"]).iterdir():
                if child.is_symlink():
                    raise DeleteRejected("目录包含软链接，停止展开")
                result.append({"storage": "local", "path": child.as_posix(), "name": child.name,
                               "type": "dir" if child.is_dir() else "file"})
        else:
            request = dict(parent, path=parent["path"].rstrip("/") + "/")
            request.pop("identity", None)
            values = self.chain.list_files(FileItem(**request), recursion=False)
            if not isinstance(values, list):
                raise DeleteRejected("网盘目录查询失败，不能判定目标不存在")
            result = [packed(item) for item in values]
        if len(result) > MAX_TARGETS:
            raise DeleteRejected("目录内容超过单次操作上限")
        for child in result:
            if (text(child.get("storage")) != parent["storage"]
                    or str(PurePosixPath(path_text(child["path"])).parent) != path_text(parent["path"])):
                raise DeleteRejected("存储返回的子项越界")
        return result

    def media_targets(self, storage: str, path: str, root: str, *, strm: bool = False) -> list[dict]:
        """精确解析 STRM 对应实体，目录逐文件展开，不递归删除整个目录。"""
        if strm and path.lower().endswith(".strm"):
            base = PurePosixPath(path[:-5])
            parent = self.lookup(storage, str(base.parent), root)
            if parent is None:
                return []
            matches = [child for child in self.children(parent) if child["type"] == "file"
                       and (child["name"] == base.name or PurePosixPath(child["name"]).stem == base.name)
                       and PurePosixPath(child["name"]).suffix.lower() in MEDIA_EXTENSIONS]
            if len(matches) > 1:
                raise DeleteRejected("STRM 对应多个网盘版本，不能猜测删除目标")
            if not matches:
                return []
            path = matches[0]["path"]
        first = self.lookup(storage, path, root)
        if first is None:
            return []
        pending, result, seen = [first], [], set()
        while pending:
            item = pending.pop()
            item_path = path_text(item["path"])
            if item_path in seen or len(seen) >= MAX_TARGETS:
                raise DeleteRejected("目录循环或超过展开上限")
            seen.add(item_path)
            if item["type"] == "dir":
                pending.extend(self.children(item))
            elif PurePosixPath(item_path).suffix.lower() in MEDIA_EXTENSIONS:
                exact = self.lookup(storage, item_path, root)
                if exact is None:
                    raise DeleteRejected("规划期间文件发生变化")
                result.append(dict(exact, root=root))
        return result

    def delete_file(self, snapshot: dict) -> None:
        """按快照核对后只删除精确文件；任何回读异常都保留未完成状态。"""
        storage, path, root = (snapshot[key] for key in ("storage", "path", "root"))
        current = self.lookup(storage, path, root)
        if current is None:
            return
        if current["type"] != "file" or current.get("identity") != snapshot.get("identity"):
            raise DeleteRejected("文件身份已变化，停止旧删除任务")
        if path == root:
            raise DeleteRejected("不能删除允许目录本身")
        self.check_write()
        if storage == "local":
            os.unlink(path)
        else:
            item = {key: value for key, value in current.items() if key not in {"identity", "root"}}
            self.chain.delete_file(FileItem(**item))
        if self.lookup(storage, path, root) is not None:
            raise DeleteRejected("删除请求后仍能查到目标，保留待重试")

    def torrent(self, downloader: str, torrent_id: str) -> dict | None:
        """查询指定任务及文件清单，区分空列表和下载器错误。"""
        service = self.plugin.service_info(downloader)
        if not service:
            raise DeleteRejected(f"下载器不可用：{downloader}")
        response = service.instance.get_torrents(ids=[torrent_id])
        if not isinstance(response, tuple) or len(response) != 2 or response[1]:
            raise DeleteRejected(f"下载器查询失败：{downloader}")
        if not response[0]:
            return None
        if len(response[0]) != 1:
            raise DeleteRejected("下载任务定位不唯一")
        torrent = normalize_torrent(response[0][0], downloader, service.type)
        # 使用实际任务字段与宿主的路径反向映射，不使用当前默认目录猜测。
        save_path = torrent.save_path
        mappings = getattr(getattr(service, "config", None), "path_mapping", None) or []
        for storage_path, downloader_path in sorted(mappings, key=lambda pair: len(pair[1]), reverse=True):
            downloader_path = str(downloader_path).rstrip("/")
            if save_path == downloader_path or save_path.startswith(downloader_path + "/"):
                save_path = str(storage_path).rstrip("/") + save_path[len(downloader_path):]
                break
        save_path = save_path.removeprefix("local:")
        save_path = path_text(save_path)
        files = service.instance.get_files(torrent_id)
        if isinstance(files, dict):
            files = list(files.values())
        if not files or len(files) > MAX_TARGETS:
            raise DeleteRejected("下载任务文件清单不可用")
        paths = []
        for item in files:
            name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
            if not name or str(name).startswith("/") or ".." in PurePosixPath(str(name)).parts:
                raise DeleteRejected("下载任务文件路径无效")
            paths.append(path_text(str(PurePosixPath(save_path) / str(name))))
        if not torrent.torrent_hash or not torrent.added_at:
            raise DeleteRejected("下载任务缺少可核验的 hash 或创建时间")
        return {"downloader": downloader, "id": torrent_id, "hash": torrent.torrent_hash,
                "save_path": save_path, "files": sorted(set(paths)), "state": torrent.state,
                "identity": [torrent.torrent_hash, torrent.added_at, save_path]}

    def prune_local_parents(self, snapshot: dict) -> None:
        """只移除精确本地文件之上的空目录，保留允许根及所有非空目录。"""
        if snapshot["storage"] != "local":
            return
        root = Path(snapshot["root"])
        parent = Path(snapshot["path"]).parent
        while parent != root and parent.is_relative_to(root):
            if parent.is_symlink() or not parent.resolve().is_relative_to(root.resolve()):
                raise DeleteRejected("空目录清理发现软链接越界")
            try:
                self.check_write()
                parent.rmdir()
            except FileNotFoundError:
                pass
            except OSError:
                # rmdir 原子拒绝非空目录；不改用递归删除。
                break
            parent = parent.parent

    def pause(self, task: dict) -> None:
        """暂停后回读状态；返回值不能替代停止状态。"""
        current = self.torrent(task["downloader"], task["id"])
        if current is None:
            return
        if current["identity"] != task["identity"]:
            raise DeleteRejected("下载任务已被重建或移动")
        self.check_write()
        self.plugin.service_info(task["downloader"]).instance.stop_torrents(ids=[task["id"]])
        for delay in (0, 0.3, 0.7):
            runtime = getattr(self.plugin, "_sync_delete_runtime", None)
            if delay and runtime and runtime.stop.wait(delay):
                raise DeleteRejected("同步删除已停止")
            current = self.torrent(task["downloader"], task["id"])
            if current is None:
                return
            if current["identity"] != task["identity"]:
                raise DeleteRejected("暂停期间下载任务身份变化")
            if text(current["state"]).lower().startswith(("paused", "stopped")):
                return
        raise DeleteRejected("下载任务尚未确认暂停，请稍后重试")

    def remove(self, task: dict) -> None:
        """文件已独立处理后移除种子，永远不让下载器整包删除数据。"""
        current = self.torrent(task["downloader"], task["id"])
        if current is None:
            return
        if current["identity"] != task["identity"]:
            raise DeleteRejected("下载任务身份变化")
        self.check_write()
        self.plugin.service_info(task["downloader"]).instance.delete_torrents(ids=[task["id"]], delete_file=False)
        if self.torrent(task["downloader"], task["id"]) is not None:
            raise DeleteRejected("下载任务移除后仍存在")
