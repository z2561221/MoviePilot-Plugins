"""清理库存媒体服务器适配器。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.helper.mediaserver import MediaServerHelper
from app.log import logger

from ..model.library_cleanup import CleanupCandidate, candidate_from_media_item, read_value


class MediaServerCleanupAdapter:
    """封装清理库存需要的媒体服务器访问能力。"""

    def __init__(self, helper: Optional[MediaServerHelper] = None, chain: Any = None):
        """初始化媒体服务器适配器。"""
        self.helper = helper or MediaServerHelper()
        self.chain = chain if chain is not None else self._build_chain()

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
        for server, service in self._services(selected_server).items():
            libraries = self._libraries(server, service, selected_user)
            for library in libraries:
                library_id = str(read_value(library, "id", "item_id", "Id") or "")
                library_name = str(read_value(library, "name", "Name") or library_id)
                if selected_library and library_id != selected_library:
                    continue
                yield from self.iter_library_candidates(
                    server=server,
                    library_id=library_id,
                    library_name=library_name,
                    selected_user=selected_user,
                )

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
        items = []
        if self.chain and hasattr(self.chain, "items"):
            items = self.chain.items(server=server, library_id=library_id) or []
        for item in items:
            if not item:
                continue
            candidate = candidate_from_media_item(
                item,
                server=server,
                library_id=library_id,
                library_name=library_name,
            )
            if candidate.favorite is None or not candidate.date_created:
                candidate = self._enrich_candidate(candidate, selected_user)
            yield candidate

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
                    logger.warning(f"本地工具集：删除媒体条目 {candidate.movie_id} 失败：{err}")
                    return False
        return self._delete_by_http(instance, candidate.movie_id)

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

    def _libraries(self, server: str, service: Any, selected_user: str = "") -> List[Any]:
        """读取媒体库列表。"""
        try:
            if self.chain and hasattr(self.chain, "librarys"):
                return self.chain.librarys(server=server, username=selected_user or None) or []
            instance = getattr(service, "instance", None)
            if instance and hasattr(instance, "get_librarys"):
                return instance.get_librarys(username=selected_user or None) or []
        except Exception as err:
            logger.warning(f"本地工具集：获取 {server} 媒体库失败：{err}")
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
        detail = self._item_detail(candidate.server, candidate.movie_id, selected_user)
        if not detail:
            return candidate
        enriched = candidate_from_media_item(
            detail,
            server=candidate.server,
            library_id=candidate.library_id,
            library_name=candidate.library_name,
        )
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
                logger.debug(f"本地工具集：通过媒体链读取条目详情失败：{err}")
        service = self.helper.get_service(name=server) if server else None
        instance = getattr(service, "instance", None) if service else None
        return self._item_detail_by_http(instance, item_id, selected_user, getattr(service, "type", ""))

    def _users_by_http(self, instance: Any, service_type: str = "") -> List[dict]:
        """通过 Emby/Jellyfin HTTP API 读取用户列表。"""
        host = getattr(instance, "_host", "")
        apikey = getattr(instance, "_apikey", "")
        if not host or not apikey:
            return []
        url = f"{host}{'emby/' if service_type == 'emby' else ''}Users"
        try:
            res = self._request_utils().get_res(url, {"api_key": apikey})
            if res and res.status_code == 200:
                return res.json() or []
        except Exception as err:
            logger.warning(f"本地工具集：读取媒体服务器用户失败：{err}")
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
        user_id = self._resolve_user_id(instance, selected_user)
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
            logger.warning(f"本地工具集：读取媒体条目详情失败：{err}")
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
            logger.warning(f"本地工具集：删除媒体条目 {item_id} 失败：{err}")
        return False

    def _resolve_user_id(self, instance: Any, selected_user: str = "") -> Optional[str]:
        """解析用户名称对应的媒体服务器用户 ID。"""
        if instance and hasattr(instance, "get_user"):
            try:
                user_id = instance.get_user(selected_user or None)
                if user_id:
                    return str(user_id)
            except Exception:
                return None
        return None

    def _request_utils(self) -> Any:
        """延迟导入宿主 HTTP 工具。"""
        from app.utils.http import RequestUtils

        return RequestUtils()

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
