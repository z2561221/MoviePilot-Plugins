"""清理库存媒体服务器适配器。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterable, List, Optional

from app.sdk.logging import logger
from app.sdk.network import RequestUtils
from app.sdk.services import MediaServerHelper

from ..model.library_cleanup import (
    CleanupCandidate,
    candidate_from_media_item,
    read_value,
)
from ..security import redact_sensitive_text


class MediaServerCleanupAdapter:
    """封装清理库存需要的媒体服务器访问能力。"""

    def __init__(self, helper: Optional[MediaServerHelper] = None, chain: Any = None):
        """初始化媒体服务器适配器。"""
        self.helper = helper or MediaServerHelper()
        self.chain = chain if chain is not None else self._build_chain()
        self._user_bindings = ContextVar("cleanup_user_bindings", default=None)

    @contextmanager
    def user_scope(self):
        """将一次扫描/清理中的用户名绑定到同一真实用户 ID。"""
        token = self._user_bindings.set({})
        try:
            yield
        finally:
            self._user_bindings.reset(token)

    def list_servers(self) -> List[dict]:
        """返回可用于清理库存的媒体服务器选项。"""
        servers = []
        for cfg in self.helper.get_configs().values():
            if getattr(cfg, "type", "") not in ("emby", "jellyfin"):
                continue
            name = getattr(cfg, "name", "")
            if name:
                servers.append({"title": name, "value": name})
        return servers

    def list_libraries(self, selected_server: str = "", selected_user: str = "") -> List[dict]:
        """返回媒体库选项。"""
        libraries = []
        for server, service in self._services(selected_server).items():
            for library in self._libraries(server, service, selected_user):
                value = read_value(library, "id", "item_id", "Id")
                title = read_value(library, "name", "Name") or value
                if value:
                    libraries.append({"title": str(title), "value": str(value)})
        return self._dedupe_options(libraries)

    def list_users(self, selected_server: str = "") -> List[dict]:
        """返回媒体服务器用户选项。"""
        users = []
        for _server, service in self._services(selected_server).items():
            for user in self._users(service):
                value = read_value(user, "Name", "name", "username", "Id", "id")
                title = read_value(user, "Name", "name", "username") or value
                if value:
                    users.append({"title": str(title), "value": str(title)})
        return self._dedupe_options(users)

    def iter_candidates(self, config: dict) -> Iterable[CleanupCandidate]:
        """按当前配置枚举媒体候选项。"""
        selected_server = str(config.get("selected_server") or "")
        selected_library = str(config.get("selected_library") or "")
        selected_user = str(config.get("selected_user") or "")
        services = self._services(selected_server)
        if not services:
            raise RuntimeError("未找到可用的媒体服务器，保留原清理计划")
        for server, service in services.items():
            libraries = self._libraries(server, service, selected_user, strict=True)
            matched = False
            for library in libraries:
                library_id = str(read_value(library, "id", "item_id", "Id") or "")
                library_name = str(read_value(library, "name", "Name") or library_id)
                if selected_library and library_id != selected_library:
                    continue
                matched = True
                yield from self.iter_library_candidates(
                    server=server,
                    library_id=library_id,
                    library_name=library_name,
                    selected_user=selected_user,
                )
            if selected_library and not matched:
                raise RuntimeError("所选媒体库不可访问，保留原清理计划")

    def iter_library_candidates(
        self,
        server: str,
        library_id: str,
        library_name: str = "",
        selected_user: str = "",
    ) -> Iterable[CleanupCandidate]:
        """枚举单个媒体库中的候选项。"""
        if not server or not library_id:
            return
        items = self._library_items_by_http(server, library_id, selected_user)
        if items is None:
            raise RuntimeError("无法完整读取媒体库，保留原清理计划")
        for item in items:
            if not item:
                continue
            candidate = candidate_from_media_item(
                item,
                server=server,
                library_id=library_id,
                library_name=library_name,
            )
            if candidate.favorite is None or candidate.played is None or not candidate.date_created:
                candidate = self._enrich_candidate(candidate, selected_user)
            yield candidate

    def _library_items_by_http(
        self,
        server: str,
        library_id: str,
        selected_user: str = "",
    ) -> Optional[List[dict]]:
        """通过 Emby/Jellyfin 原始 API 枚举电影与未刮削普通视频。"""
        service = self.helper.get_service(name=server) if server else None
        instance = getattr(service, "instance", None) if service else None
        service_type = getattr(service, "type", "") if service else ""
        host = getattr(instance, "_host", "")
        apikey = getattr(instance, "_apikey", "")
        user_id = self._resolve_user_id(instance, selected_user, service_type)
        if not host or not apikey or not user_id or not library_id:
            return None
        prefix = "emby/" if service_type == "emby" else ""
        url = f"{host.rstrip('/')}/{prefix}Users/{user_id}/Items"
        params = {
            "api_key": apikey,
            "ParentId": library_id,
            "Recursive": "true",
            "IncludeItemTypes": "Movie,Video",
            "Fields": "ProviderIds,OriginalTitle,ProductionYear,Path,ParentId,DateCreated,UserData",
            "Limit": 200,
            "StartIndex": 0,
        }
        return self._read_pages(url, params)

    def _read_pages(self, url: str, params: dict) -> list[dict]:
        """完整读取用户范围列表，任一页异常均不返回部分结果。"""
        items = []
        seen = set()
        while True:
            res = self._request_utils(timeout=20).get_res(url, dict(params))
            if res is None or res.status_code != 200:
                raise RuntimeError("媒体库分页读取失败，原清理计划未更新")
            payload = res.json()
            rows = payload.get("Items") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise TypeError("媒体库返回的列表格式无效")
            total = payload.get("TotalRecordCount")
            if total is not None and (not isinstance(total, int) or total < 0):
                raise ValueError("媒体库返回的总数量无效")
            for row in rows:
                identity = str(read_value(row, "Id", "id", "item_id") or "")
                if not identity or identity in seen:
                    raise ValueError("媒体库分页缺少条目身份或重复返回同一页")
                seen.add(identity)
                items.append(row)
            if total is not None:
                if len(items) > total:
                    raise ValueError("媒体库分页总数前后不一致，原清理计划未更新")
                if len(items) == total:
                    return items
            if not rows:
                if total is not None and len(items) < total:
                    raise ValueError("媒体库分页提前结束，原清理计划未更新")
                return items
            if total is None and len(rows) < params["Limit"]:
                return items
            params["StartIndex"] += len(rows)

    def delete_item(self, candidate: CleanupCandidate) -> bool:
        """删除媒体服务器中的指定条目。"""
        if not candidate or not candidate.movie_id:
            return False
        service = self.helper.get_service(name=candidate.server) if candidate.server else None
        instance = getattr(service, "instance", None) if service else None
        for method_name in ("delete_item", "del_item", "remove_item"):
            method = getattr(instance, method_name, None)
            if callable(method):
                try:
                    return bool(method(candidate.movie_id))
                except TypeError:
                    return bool(method(candidate.movie_id, True))
                except Exception as err:
                    logger.warning(f"本地工具集：删除媒体条目 {candidate.movie_id} 失败：{redact_sensitive_text(err)}")
                    return False
        return self._delete_by_http(instance, candidate.movie_id)

    def item_exists(self, candidate: CleanupCandidate, selected_user: str = "") -> Optional[bool]:
        """实时复核条目；仅明确 404 表示不存在，错误和无权限均返回未知。"""
        state, _detail = self._read_item(candidate, selected_user)
        return state

    def refresh_candidate(
        self, candidate: CleanupCandidate, selected_user: str = "",
    ) -> tuple[bool | None, CleanupCandidate | None]:
        """按条目 ID 获取当前用户的真实状态，不枚举媒体库或复用旧筛选值。"""
        state, detail = self._read_item(candidate, selected_user, details=True)
        if state is not True:
            return state, None
        fresh = candidate_from_media_item(
            detail, server=candidate.server, library_id=candidate.library_id,
            library_name=candidate.library_name,
        )
        parent_id = str(read_value(detail, "ParentId", "parent_id") or "")
        if candidate.library_id and parent_id != candidate.library_id:
            membership = self._belongs_to_library(candidate, selected_user)
            if membership is None:
                return None, None
            if membership is False:
                fresh.library_id = parent_id or "outside-plan-library"
        return True, fresh

    def _belongs_to_library(self, candidate: CleanupCandidate, selected_user: str) -> bool | None:
        """按单项祖先链确认媒体库归属，兼容媒体库内的嵌套目录。"""
        service = self.helper.get_service(name=candidate.server)
        instance = getattr(service, "instance", None)
        host = getattr(instance, "_host", "")
        key = getattr(instance, "_apikey", "")
        user_id = self._resolve_user_id(instance, selected_user, getattr(service, "type", ""))
        if not host or not key or not user_id:
            return None
        prefix = "emby/" if getattr(service, "type", "") == "emby" else ""
        url = f"{host.rstrip('/')}/{prefix}Items/{candidate.movie_id}/Ancestors"
        response = self._request_utils(timeout=10).get_res(url, {"api_key": key, "UserId": user_id})
        if response is None or response.status_code != 200:
            return None
        ancestors = response.json()
        if not isinstance(ancestors, list):
            return None
        return any(str(read_value(item, "Id", "id", "item_id") or "") == candidate.library_id
                   for item in ancestors)

    def _read_item(
        self, candidate: CleanupCandidate, selected_user: str, *, details: bool = False,
    ) -> tuple[bool | None, Any]:
        """使用同一用户身份读取单项，明确区分不存在、无权限和读取失败。"""
        if not candidate.server or not candidate.movie_id:
            return None, None
        service = self.helper.get_service(name=candidate.server)
        instance = getattr(service, "instance", None)
        service_type = getattr(service, "type", "")
        host = getattr(instance, "_host", "")
        apikey = getattr(instance, "_apikey", "")
        user_id = self._resolve_user_id(instance, selected_user, service_type)
        if service_type not in ("emby", "jellyfin") or not host or not apikey or not user_id:
            return None, None
        prefix = "emby/" if service_type == "emby" else ""
        url = f"{host.rstrip('/')}/{prefix}Users/{user_id}/Items/{candidate.movie_id}"
        params = {"api_key": apikey}
        if details:
            params["Fields"] = "ProviderIds,DateCreated,UserData,ParentId"
        try:
            response = self._request_utils(timeout=10).get_res(url, params)
            # HTTP 错误响应可能为 falsy，不能用 bool(response) 吞掉 404。
            if response is None:
                return None, None
            if response.status_code == 404:
                return False, None
            if response.status_code == 200:
                item = response.json()
                item_id = read_value(item, "Id", "id", "item_id")
                if str(item_id or "") == candidate.movie_id:
                    return True, item
        except Exception as err:
            logger.warning(f"本地工具集：核验媒体条目失败：{redact_sensitive_text(err)}")
        return None, None

    def _build_chain(self) -> Any:
        """延迟构建宿主媒体服务器链，测试环境缺失时返回空。"""
        try:
            from app.chain.mediaserver import MediaServerChain

            return MediaServerChain()
        except Exception:
            return None

    def _services(self, selected_server: str = "") -> Dict[str, Any]:
        """按服务器配置筛选宿主服务实例。"""
        name_filters = [selected_server] if selected_server else None
        services = self.helper.get_services(name_filters=name_filters) or {}
        return {
            name: service
            for name, service in services.items()
            if getattr(service, "type", "") in ("emby", "jellyfin")
            and not self._is_inactive(getattr(service, "instance", None))
        }

    def _libraries(
        self, server: str, service: Any, selected_user: str = "", *, strict: bool = False,
    ) -> List[Any]:
        """读取媒体库列表。"""
        try:
            if selected_user:
                instance = getattr(service, "instance", None)
                service_type = getattr(service, "type", "")
                user_id = self._resolve_user_id(instance, selected_user, service_type)
                if not user_id:
                    raise RuntimeError("所选媒体用户不存在或无法核验")
                host = getattr(instance, "_host", "").rstrip("/")
                prefix = "emby/" if service_type == "emby" else ""
                return self._read_pages(f"{host}/{prefix}Users/{user_id}/Views", {
                    "api_key": instance._apikey, "Limit": 200, "StartIndex": 0,
                })
            if self.chain and hasattr(self.chain, "librarys"):
                result = self.chain.librarys(server=server, username=selected_user or None)
                if result is None and strict:
                    raise RuntimeError("媒体库列表不可访问")
                return result or []
            instance = getattr(service, "instance", None)
            if instance and hasattr(instance, "get_librarys"):
                result = instance.get_librarys(username=selected_user or None)
                if result is None and strict:
                    raise RuntimeError("媒体库列表不可访问")
                return result or []
        except Exception as err:
            if strict:
                raise RuntimeError("读取媒体库列表失败") from err
            logger.warning(f"本地工具集：获取 {server} 媒体库失败：{redact_sensitive_text(err)}")
        if strict:
            raise RuntimeError("媒体服务器未提供媒体库列表接口")
        return []

    def _users(self, service: Any) -> List[Any]:
        """读取媒体服务器用户列表。"""
        instance = getattr(service, "instance", None)
        if not instance:
            return []
        user_list = getattr(instance, "users", None)
        if isinstance(user_list, list):
            return user_list
        return self._users_by_http(instance, getattr(service, "type", ""))

    def _enrich_candidate(self, candidate: CleanupCandidate, selected_user: str = "") -> CleanupCandidate:
        """通过单项详情补充创建时间和收藏状态。"""
        state, enriched = self.refresh_candidate(candidate, selected_user)
        if state is not True or enriched is None:
            return candidate
        if not enriched.code:
            enriched.code = candidate.code
        if not enriched.title:
            enriched.title = candidate.title
        return enriched

    def _item_detail(self, server: str, item_id: str, selected_user: str = "") -> Any:
        """读取单个媒体条目详情。"""
        if self.chain and hasattr(self.chain, "iteminfo"):
            try:
                return self.chain.iteminfo(server=server, item_id=item_id)
            except Exception as err:
                logger.debug(f"本地工具集：通过媒体链读取条目详情失败：{redact_sensitive_text(err)}")
        service = self.helper.get_service(name=server) if server else None
        instance = getattr(service, "instance", None) if service else None
        return self._item_detail_by_http(instance, item_id, selected_user, getattr(service, "type", ""))

    def _users_by_http(self, instance: Any, service_type: str = "") -> List[dict]:
        """通过 Emby/Jellyfin HTTP API 读取用户列表。"""
        host = getattr(instance, "_host", "")
        apikey = getattr(instance, "_apikey", "")
        if not host or not apikey:
            return []
        url = f"{host.rstrip('/')}/{'emby/' if service_type == 'emby' else ''}Users"
        try:
            res = self._request_utils(timeout=10).get_res(url, {"api_key": apikey})
            if res is not None and res.status_code == 200:
                users = res.json()
                return users if isinstance(users, list) else []
        except Exception as err:
            logger.warning(f"本地工具集：读取媒体服务器用户失败：{redact_sensitive_text(err)}")
        return []

    def _item_detail_by_http(
        self,
        instance: Any,
        item_id: str,
        selected_user: str = "",
        service_type: str = "",
    ) -> Any:
        """通过 Emby/Jellyfin HTTP API 读取条目原始详情。"""
        host = getattr(instance, "_host", "")
        apikey = getattr(instance, "_apikey", "")
        user_id = self._resolve_user_id(instance, selected_user, service_type)
        if not host or not apikey or not user_id or not item_id:
            return None
        prefix = "emby/" if service_type == "emby" else ""
        url = f"{host}{prefix}Users/{user_id}/Items/{item_id}"
        params = {
            "api_key": apikey,
            "Fields": "ProviderIds,OriginalTitle,ProductionYear,Path,ParentId,DateCreated,UserData",
        }
        try:
            res = self._request_utils().get_res(url, params)
            if res and res.status_code == 200:
                return res.json()
        except Exception as err:
            logger.warning(f"本地工具集：读取媒体条目详情失败：{redact_sensitive_text(err)}")
        return None

    def _delete_by_http(self, instance: Any, item_id: str) -> bool:
        """通过 Emby/Jellyfin HTTP API 删除条目。"""
        host = getattr(instance, "_host", "")
        apikey = getattr(instance, "_apikey", "")
        if not host or not apikey or not item_id:
            return False
        prefix = "emby/" if "emby" in str(type(instance)).lower() else ""
        url = f"{host}{prefix}Items/{item_id}"
        try:
            res = self._request_utils().delete_res(url, params={"api_key": apikey})
            return bool(res and res.status_code in (200, 204))
        except Exception as err:
            logger.warning(f"本地工具集：删除媒体条目 {item_id} 失败：{redact_sensitive_text(err)}")
        return False

    def _resolve_user_id(
        self, instance: Any, selected_user: str = "", service_type: str = "",
    ) -> Optional[str]:
        """显式用户精确匹配；默认用户保留宿主语义，执行中拒绝换身份。"""
        if instance is None:
            return None
        if selected_user:
            users = self._users_by_http(instance, service_type)
            matches = [user for user in users if isinstance(user, dict) and user.get("Name") == selected_user]
            if len(matches) != 1 or not matches[0].get("Id"):
                return None
            user_id = str(matches[0]["Id"])
        else:
            try:
                user_id = str(instance.get_user(None) or "")
            except Exception:
                return None
        if not user_id:
            return None
        bindings = self._user_bindings.get()
        if bindings is not None:
            key = (getattr(instance, "_host", ""), selected_user)
            if bindings.setdefault(key, user_id) != user_id:
                return None
        return user_id

    def _request_utils(self, timeout: Optional[int] = None) -> Any:
        """延迟导入宿主 HTTP 工具。"""
        return RequestUtils(timeout=timeout) if timeout is not None else RequestUtils()

    @staticmethod
    def _is_inactive(instance: Any) -> bool:
        """判断媒体服务器实例是否不可用。"""
        try:
            return bool(instance and hasattr(instance, "is_inactive") and instance.is_inactive())
        except Exception:
            return True

    @staticmethod
    def _dedupe_options(items: List[dict]) -> List[dict]:
        """按 value 去重选项列表。"""
        seen = set()
        deduped = []
        for item in items:
            value = item.get("value")
            if value in seen:
                continue
            seen.add(value)
            deduped.append(item)
        return deduped
