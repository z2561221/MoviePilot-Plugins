"""自动删除的 QB/TR 原生采样、身份核验和精确文件操作。"""

from __future__ import annotations

import math
import os
import re
import stat
import time
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from app.sdk.logging import logger
from transmission_rpc import TransmissionError

from ..model.auto_delete import Settings, Snapshot, Tracker, digest

TR_FIELDS = ["id", "hashString", "name", "addedDate", "downloadDir", "status", "totalSize",
             "percentDone", "leftUntilDone", "uploadRatio", "secondsSeeding", "rateUpload",
             "uploadLimit", "uploadLimited", "labels", "trackers", "trackerStats"]
PAUSE_CONFIRMATION_DELAYS = (0, 0.5, 1, 2, 3, 3)


def value_of(item, *names, default=None):
    """读取字典或客户端对象字段，缺失属性保持未知。"""
    for name in names:
        try:
            if isinstance(item, dict) and name in item:
                return item[name]
            return getattr(item, name)
        except (AttributeError, KeyError):
            continue
    return default


def number_of(value):
    """保留真实零值，非法及下载器负数特殊值不冒充有效数值。"""
    if isinstance(value, bool):
        return None
    if hasattr(value, "timestamp"):
        value = value.timestamp()
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def safe_error(error) -> str:
    """去掉错误文本中的地址认证及有标签的私密参数。"""
    message = str(error)
    message = re.sub(r"https?://[^\s]+", lambda match: safe_tracker_url(match.group()), message)
    return re.sub(r"(?i)(passkey|token|apikey|password|authorization)(\s*[:=]\s*)[^\s,;]+",
                  r"\1\2[已隐藏]", message)[:1024]


def safe_tracker_url(url: str) -> str:
    """Tracker 凭据可能在路径或查询中，对外仅展示规范主机。"""
    try:
        parsed = urlsplit(url)
        return f"{parsed.scheme}://{parsed.hostname or '[未知主机]'}/[announce路径已隐藏]"
    except ValueError:
        return "[Tracker 地址已隐藏]"


def public_snapshot(snapshot: Snapshot) -> dict:
    """保存/返回快照前隐藏 announce 路径及 Tracker 错误中的私密字段。"""
    payload = snapshot.model_dump(mode="json")
    if payload["trackers"] is not None:
        payload["trackers"] = [{"url": safe_tracker_url(item["url"]),
                                "status": item["status"], "message": safe_error(item["message"])}
                               for item in payload["trackers"]]
    return payload


def binding_of(service) -> str:
    """下载器地址、类型及映射变化使旧规则确认和任务身份失效。"""
    config = getattr(service, "config", None)
    connection = value_of(config, "config", default=None) or config
    return digest({"name": str(getattr(service, "name", "")), "type": str(service.type),
                   "endpoint": {key: str(value_of(connection, key, default=""))
                                for key in ("host", "port", "url", "protocol", "username")},
                   "path_mapping": value_of(config, "path_mapping", default=[]) or []})


def normalize_native(raw, name: str, kind: str, binding: str, trackers=None) -> Snapshot:
    """按原生进度与剩余字节确认完成，不用累计下载量。"""
    state = value_of(raw, "state", "status", default="")
    if kind == "transmission" and type(state) is int:
        state = {0: "stopped", 1: "check pending", 2: "checking", 3: "download pending",
                 4: "downloading", 5: "seed pending", 6: "seeding"}.get(state, "unknown")
    state = str(getattr(state, "name", None) or getattr(state, "value", None) or state)
    normalized = state.lower().replace(" ", "").replace("_", "")
    progress = number_of(value_of(raw, "percent_done", "percentDone", "progress") if kind == "transmission"
                         else value_of(raw, "progress"))
    left = number_of(value_of(raw, "amount_left", "left_until_done", "leftUntilDone"))
    completed = progress is not None and progress >= 1 and left is not None and left == 0
    valid_states = {"uploading", "forcedup", "stalledup", "pausedup", "stoppedup", "queuedup", "seeding", "seedpending", "stopped"}
    if normalized not in valid_states:
        completed = False
    labels = value_of(raw, "tags", "labels")
    if isinstance(labels, str):
        labels = [item.strip() for item in labels.split(",") if item.strip()]
    if labels is not None:
        labels = [str(item) for item in labels]
    total_size = number_of(value_of(raw, "total_size", "totalSize", "size"))
    upload_limit = number_of(value_of(raw, "up_limit", "upload_limit", "uploadLimit"))
    if kind == "transmission":
        upload_limit = upload_limit * 1024 if upload_limit is not None and value_of(raw, "upload_limited", "uploadLimited") is True else None
    elif upload_limit == 0:
        upload_limit = None
    raw_ratio = value_of(raw, "ratio", "upload_ratio", "uploadRatio")
    ratio = number_of(raw_ratio)
    ratio_state = "finite" if ratio is not None else "unknown"
    if raw_ratio in (-2, "-2") and kind == "transmission" or str(raw_ratio).lower() in {"inf", "infinity"}:
        ratio_state = "infinite"
    return Snapshot(
        downloader=name, binding=binding, kind=kind,
        hash=str(value_of(raw, "hash", "hash_string", "hashString", default="")).lower(),
        name=str(value_of(raw, "name", default="")),
        added_at=number_of(value_of(raw, "added_on", "added_date", "date_added", "addedDate")),
        save_path=str(value_of(raw, "save_path", "download_dir", "downloadDir", default="")),
        total_bytes=int(total_size) if total_size is not None else None,
        completed=completed, state=state, ratio=ratio, ratio_state=ratio_state,
        seed_seconds=number_of(value_of(raw, "seeding_time", "seconds_seeding", "secondsSeeding")),
        upload_bps=number_of(value_of(raw, "upspeed", "rate_upload", "rateUpload")),
        upload_limit_bps=upload_limit,
        category=value_of(raw, "category", "group"), tags=labels, trackers=trackers,
    )


class AutoDeleteAdapter:
    """所有外部副作用集中于适配器，测试替换此接口。"""

    def __init__(self, plugin, check=lambda: None):
        """下载器按实际操作获取，写入前由执行器再次校验。"""
        self.plugin = plugin
        self.check = check

    def for_runtime(self, check):
        """配置換代不让新执行器沿用旧停止检查。"""
        return AutoDeleteAdapter(self.plugin, check)

    def service(self, downloader):
        """拒绝未配置、不可用和未支持的下载器。"""
        service = self.plugin.service_info(downloader)
        if not service or service.type not in {"qbittorrent", "transmission"}:
            raise ValueError(f"下载器不可用或类型不支持：{downloader}")
        return service

    def poll(self, downloader, *, ids=None, need_trackers=False, need_category=False, need_seed_time=False) -> list[Snapshot]:
        """每个下载器每轮一次基础查询；错误与成功空列表严格区分。"""
        service = self.service(downloader)
        try:
            if service.type == "transmission" and getattr(service.instance, "trc", None):
                fields = TR_FIELDS if need_trackers else [key for key in TR_FIELDS if key not in {"trackers", "trackerStats"}]
                raw_items = service.instance.trc.get_torrents(ids=ids, arguments=fields)
            else:
                response = service.instance.get_torrents(ids=ids) if ids is not None else service.instance.get_torrents()
                raw_items, error = response if isinstance(response, tuple) and len(response) == 2 else (response, None)
                if error or raw_items is None:
                    raise RuntimeError("下载器查询未成功")
            binding = binding_of(service)
            categories = {}
            if need_category and service.type == "transmission" and getattr(service.instance, "trc", None):
                try:
                    category_items = service.instance.trc.get_torrents(ids=ids, arguments=["hashString", "group"])
                    categories = {str(value_of(item, "hash_string", "hashString", default="")).lower(): value_of(item, "group")
                                  for item in category_items}
                except (TransmissionError, ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError) as error:
                    categories = {}
            result = []
            for raw in raw_items:
                snapshot = normalize_native(raw, downloader, service.type, binding)
                if need_seed_time and service.type == "qbittorrent" and snapshot.completed and snapshot.seed_seconds is None:
                    try:
                        properties = service.instance.qbc.torrents_properties(torrent_hash=snapshot.hash)
                        snapshot.seed_seconds = number_of(value_of(properties, "seeding_time"))
                    except (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError):
                        snapshot.seed_seconds = None
                if need_category and service.type == "transmission":
                    snapshot.category = categories.get(snapshot.hash)
                if need_trackers and snapshot.completed:
                    snapshot.trackers = self.trackers(service, raw, snapshot.hash)
                result.append(snapshot)
            return result
        except Exception as error:
            raise RuntimeError(f"{downloader} 查询失败（{type(error).__name__}）") from error

    def enrich(self, snapshot, *, need_trackers=False, need_seed_time=False):
        """只为通过基础条件的候选补查缺少的时长和 Tracker。"""
        self.check()
        service = self.service(snapshot.downloader)
        if need_seed_time and service.type == "qbittorrent" and snapshot.seed_seconds is None:
            try:
                properties = service.instance.qbc.torrents_properties(torrent_hash=snapshot.hash)
                snapshot.seed_seconds = number_of(value_of(properties, "seeding_time"))
            except (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError):
                snapshot.seed_seconds = None
        if need_trackers:
            if service.type == "transmission":
                current = self.poll(snapshot.downloader, ids=[snapshot.hash], need_trackers=True)
                if len(current) != 1 or current[0].identity != snapshot.identity:
                    raise ValueError("补查期间原任务身份已变化")
                snapshot.trackers = current[0].trackers
            else:
                snapshot.trackers = self.trackers(service, None, snapshot.hash)
        return snapshot

    def trackers(self, service, raw, torrent_hash) -> list[Tracker] | None:
        """保留同条 Tracker 的 URL/状态/消息，失败保持未知。"""
        try:
            if service.type == "qbittorrent":
                items = service.instance.qbc.torrents_trackers(torrent_hash=torrent_hash)
                result = []
                for item in items:
                    if value_of(item, "tier", default=-1) < 0:
                        continue
                    status = {0: "disabled", 1: "uncontacted", 2: "working", 3: "updating", 4: "error"}.get(value_of(item, "status"), "unknown")
                    result.append(Tracker(url=value_of(item, "url", default=""), status=status,
                                          message=str(value_of(item, "msg", default=""))))
                return result
            result = []
            for item in value_of(raw, "tracker_stats", "trackerStats", default=[]) or []:
                success = value_of(item, "last_announce_succeeded", "lastAnnounceSucceeded")
                announced = value_of(item, "has_announced", "hasAnnounced")
                status = "uncontacted" if announced is False else "working" if success is True else "error" if success is False else "unknown"
                result.append(Tracker(url=str(value_of(item, "announce", default="")), status=status,
                                      message=str(value_of(item, "last_announce_result", "lastAnnounceResult", default=""))))
            return result
        except (ValueError, RuntimeError, TypeError, OSError, KeyError, AttributeError) as error:
            logger.error("自动删除 Tracker 读取失败（" + type(error).__name__ + "）")
            return None

    def current(self, expected: Snapshot) -> Snapshot | None:
        """定向核验原任务；成功不存在与身份变化分别处理。"""
        if not expected.valid_hash:
            raise ValueError("种子 hash 无效，拒绝下载器操作")
        items = self.poll(expected.downloader, ids=[expected.hash])
        if not items:
            return None
        if len(items) != 1 or items[0].identity != expected.identity:
            raise ValueError("下载任务已重建、移动或下载器配置已变化")
        return items[0]

    def pause(self, expected: Snapshot) -> Snapshot | None:
        """仅对原身份暂停，并以实际状态回读确认。"""
        current = self.current(expected)
        if current is None or current.paused:
            return current
        self.check()
        if self.service(expected.downloader).instance.stop_torrents(ids=[expected.hash]) is False:
            raise RuntimeError("下载器拒绝暂停")
        for delay in PAUSE_CONFIRMATION_DELAYS:
            if delay:
                self.check()
                time.sleep(delay)
            self.check()
            current = self.current(expected)
            if current is None or current.paused:
                return current
        raise RuntimeError("下载器尚未确认暂停，保留保护待复核")

    def remove(self, expected: Snapshot):
        """精确移除原任务，文件由已核验的文件执行器单独处理。"""
        current = self.current(expected)
        if current is None:
            return
        if not current.paused:
            raise ValueError("种子尚未暂停，停止移除")
        self.check()
        if self.service(expected.downloader).instance.delete_torrents(ids=[expected.hash], delete_file=False) is False:
            raise RuntimeError("下载器拒绝删除任务")
        if self.current(expected) is not None:
            raise RuntimeError("移除后任务仍存在，结果待核验")

    def restore(self, expected: Snapshot, *, check=None):
        """人工明确恢复时才启动原身份且仍暂停的任务。"""
        current = self.current(expected)
        if current is None:
            return
        if not current.paused:
            return
        (check or self.check)()
        if self.service(expected.downloader).instance.start_torrents(ids=[expected.hash]) is False:
            raise RuntimeError("下载器拒绝恢复")
        current = self.current(expected)
        if current is None or current.paused:
            raise RuntimeError("下载器尚未确认恢复")

    def file_paths(self, snapshot: Snapshot) -> list[str]:
        """使用实际文件清单和下载器映射，不根据名称猜测文件。"""
        if not snapshot.valid_hash:
            raise ValueError("种子 hash 无效，不能读取文件清单")
        service = self.service(snapshot.downloader)
        return self._mapped_file_paths(snapshot, service, service.instance.get_files(snapshot.hash))

    @staticmethod
    def _mapped_file_paths(snapshot, service, files):
        """把下载器实时返回的相对文件名映射到容器路径。"""
        save_path = snapshot.save_path
        mappings = value_of(getattr(service, "config", None), "path_mapping", default=[]) or []
        for storage_path, downloader_path in sorted(mappings, key=lambda item: len(item[1]), reverse=True):
            downloader_path = str(downloader_path).rstrip("/")
            if save_path == downloader_path or save_path.startswith(downloader_path + "/"):
                save_path = str(storage_path).rstrip("/") + save_path[len(downloader_path):]
                break
        save_path = save_path.removeprefix("local:")
        if not save_path.startswith("/"):
            raise ValueError("下载器文件无法映射为 MP 容器绝对路径")
        if isinstance(files, dict):
            files = files.values()
        if not files:
            raise ValueError("下载任务文件清单不可用")
        paths = []
        for item in files:
            name = str(value_of(item, "name", default=""))
            relative = PurePosixPath(name)
            if not name or relative.is_absolute() or ".." in relative.parts:
                raise ValueError("下载任务文件路径无效")
            paths.append(str(PurePosixPath(save_path) / relative))
            if len(paths) > 10000:
                raise ValueError("单任务文件清单过大")
        if not paths:
            raise ValueError("下载任务文件清单为空")
        return sorted(set(paths))

    def prepare_files(self, snapshot: Snapshot, settings: Settings) -> list[dict]:
        """完整检查文件边界和所有下载器引用，未确认范围拒绝删盘。"""
        paths = self.file_paths(snapshot)
        self.check_shared_references(snapshot, paths)
        result = []
        roots = [Path(value.rstrip("/")) for value in settings.source_paths]
        for path_text in paths:
            path = Path(path_text)
            if any(path == Path(value) or path.is_relative_to(Path(value)) for value in settings.exclude_paths):
                raise ValueError("命中下载数据保护目录")
            root = next((value for value in roots if path != value and path.is_relative_to(value)), None)
            if (root is None or root.is_symlink() or not root.is_dir() or path.is_symlink()
                    or not path.resolve().is_relative_to(root.resolve())):
                raise ValueError("下载文件越界、目录不可用或存在软链接")
            file_stat = path.stat()
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError("清单包含非普通文件")
            self.check_library_reference(path_text)
            root_stat = root.stat()
            result.append({"path": path_text, "root": str(root), "identity": [file_stat.st_dev, file_stat.st_ino, file_stat.st_size, file_stat.st_mtime_ns],
                           "root_identity": [root_stat.st_dev, root_stat.st_ino], "deleted": False})
        return result

    def check_shared_references(self, snapshot, paths):
        """核对完整下载器目录，缺少运行实例时不能宣称没有共享文件。"""
        from .moviepilot import create_downloader_helper, get_downloader_services

        configured = create_downloader_helper().get_configs(include_disabled=True)
        services = get_downloader_services()
        if not isinstance(services, dict) or not services or not isinstance(configured, dict):
            raise ValueError("下载器目录不完整，无法核对共用文件")
        if set(configured) - set(services):
            raise ValueError("有下载器未连接，无法完整核对共用文件")
        targets = {str(Path(path).resolve()) for path in paths}
        for service in services.values():
            if getattr(service, "type", "") == "transmission" and getattr(service.instance, "trc", None):
                # 一次 RPC 取回身份和原生文件清单。每次复查都重新读取，以发现改名或新增引用。
                fields = ["id", "hashString", "downloadDir", "addedDate", "files"]
                rows = service.instance.trc.get_torrents(arguments=fields)
                binding = binding_of(service)
                for row in rows:
                    other = normalize_native(row.fields, service.name, service.type, binding)
                    if other.identity == snapshot.identity:
                        continue
                    files = self._mapped_file_paths(other, service, row.fields["files"])
                    if any(str(Path(path).resolve()) in targets for path in files):
                        raise ValueError(f"文件被其他下载任务共用：{service.name}")
            else:
                for other in self.poll(service.name):
                    if other.identity == snapshot.identity:
                        continue
                    if any(str(Path(path).resolve()) in targets for path in self.file_paths(other)):
                        raise ValueError(f"文件被其他下载任务共用：{service.name}")

    def check_library_reference(self, path_text):
        """下载文件同时作为媒体库目标时保留，SDK 查询失败不当作无引用。"""
        from app.sdk.queries import list_transfer_history

        page = list_transfer_history(filters={"dest": path_text, "status": True}, page={"page": 1, "count": 1})
        if page.total is None:
            raise ValueError("媒体库文件引用查询无法确认完整性")
        if page.items or page.total:
            raise ValueError("该下载文件仍被媒体库整理目标引用")

    def delete_file(self, item: dict):
        """目录句柄逐级拒绝软链接，只删除原身份文件，不递归清理目录。"""
        if os.name != "posix" or os.unlink not in os.supports_dir_fd:
            raise ValueError("当前运行环境不支持目录句柄核验，停止删除下载数据")
        root = PurePosixPath(item["root"])
        path = PurePosixPath(item["path"])
        relative = path.relative_to(root)
        if not relative.parts or ".." in relative.parts or path == root:
            raise ValueError("下载文件不在允许目录内")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptors = [os.open(str(root), flags)]
        try:
            root_stat = os.fstat(descriptors[0])
            if [root_stat.st_dev, root_stat.st_ino] != item["root_identity"]:
                raise ValueError("允许删除目录已被替换")
            for directory in relative.parts[:-1]:
                descriptors.append(os.open(directory, flags, dir_fd=descriptors[-1]))
            name = relative.name
            file_stat = os.stat(name, dir_fd=descriptors[-1], follow_symlinks=False)
            identity = [file_stat.st_dev, file_stat.st_ino, file_stat.st_size, file_stat.st_mtime_ns]
            if identity != item["identity"] or not stat.S_ISREG(file_stat.st_mode):
                raise ValueError("下载文件已被替换，停止删除")
            self.check_library_reference(str(path))
            self.check()
            os.unlink(name, dir_fd=descriptors[-1])
            try:
                os.stat(name, dir_fd=descriptors[-1], follow_symlinks=False)
            except FileNotFoundError:
                return
            raise RuntimeError("文件删除后路径重现，结果需复核")
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
