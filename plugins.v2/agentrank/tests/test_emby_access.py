"""AgentRank 共享 Emby 服务访问与稳定用户枚举测试。"""

import importlib
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_emby_access_test"

package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

emby_module = importlib.import_module(f"{PACKAGE_NAME}.adapter.emby")
EmbyServiceAccess = emby_module.EmbyServiceAccess


class FakeInstance:
    """提供 Emby 服务访问器需要的最小实例字段。"""

    def __init__(self, host, api_key="secret", inactive=False, server_id=""):
        self._host = host
        self._apikey = api_key
        self._inactive = inactive
        self.serverid = server_id

    def is_inactive(self):
        return self._inactive


class FakeHelper:
    """返回预设 MoviePilot 媒体服务器服务。"""

    def __init__(self, services):
        self._services = services

    def get_services(self):
        return self._services


class FakeResponse:
    """提供状态码和 JSON 载荷。"""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeRequest:
    """按 URL 返回预设 Emby Users 响应。"""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_res(self, url, params=None):
        self.calls.append((url, dict(params or {})))
        return self.responses.get(url)


def _service(instance, service_type="emby"):
    return SimpleNamespace(type=service_type, instance=instance)


def test_enumerates_same_named_users_on_multiple_servers_as_distinct_identities():
    """同名用户必须按服务器和 Emby user ID 保持隔离。"""
    request = FakeRequest(
        {
            "http://home/Users": FakeResponse(
                200, [{"Id": "user-1", "Name": "Alice"}]
            ),
            "http://remote/Users": FakeResponse(
                200, [{"Id": "user-9", "Name": "Alice"}]
            ),
        }
    )
    access = EmbyServiceAccess(
        helper=FakeHelper(
            {
                "home": _service(FakeInstance("http://home")),
                "remote": _service(FakeInstance("http://remote")),
            }
        ),
        request_factory=lambda timeout: request,
    )

    identities = access.enumerate_identities()

    assert [identity.profile_id for identity in identities] == [
        "emby:home:user-1",
        "emby:remote:user-9",
    ]
    assert [identity.username for identity in identities] == ["Alice", "Alice"]
    assert all("secret" not in identity.to_dict().values() for identity in identities)


def test_offline_emby_and_non_emby_services_are_not_enumerated():
    """离线 Emby 与其他媒体服务器不得触发 Users 请求。"""
    request = FakeRequest({})
    access = EmbyServiceAccess(
        helper=FakeHelper(
            {
                "offline": _service(FakeInstance("http://offline", inactive=True)),
                "jellyfin": _service(
                    FakeInstance("http://jellyfin"), service_type="jellyfin"
                ),
            }
        ),
        request_factory=lambda timeout: request,
    )

    assert access.enumerate_identities() == []
    assert request.calls == []


def test_online_emby_with_no_users_returns_an_empty_identity_list():
    """在线服务返回空 Users 列表时不得制造默认用户。"""
    request = FakeRequest({"http://empty/Users": FakeResponse(200, [])})
    access = EmbyServiceAccess(
        helper=FakeHelper({"empty": _service(FakeInstance("http://empty"))}),
        request_factory=lambda timeout: request,
    )

    assert access.enumerate_identities() == []
    assert request.calls == [("http://empty/Users", {"api_key": "secret"})]


def test_users_endpoint_falls_back_to_emby_prefix_after_404():
    """标准 Users 路径为 404 时改用带 emby 前缀的兼容路径。"""
    request = FakeRequest(
        {
            "http://legacy/Users": FakeResponse(404, {}),
            "http://legacy/emby/Users": FakeResponse(
                200, [{"Id": "user-3", "Name": "Carol"}]
            ),
        }
    )
    access = EmbyServiceAccess(
        helper=FakeHelper({"legacy": _service(FakeInstance("http://legacy"))}),
        request_factory=lambda timeout: request,
    )

    identities = access.enumerate_identities()

    assert [identity.profile_id for identity in identities] == [
        "emby:legacy:user-3"
    ]
    assert [url for url, _params in request.calls] == [
        "http://legacy/Users",
        "http://legacy/emby/Users",
    ]


def test_malformed_policy_does_not_abort_user_enumeration():
    """异常 Policy 字段不得影响其他合法用户进入身份列表。"""
    request = FakeRequest(
        {
            "http://policy/Users": FakeResponse(
                200,
                [
                    {"Id": "user-4", "Name": "Dave", "Policy": "invalid"},
                    {
                        "Id": "user-5",
                        "Name": "Disabled",
                        "Policy": {"IsDisabled": True},
                    },
                ],
            )
        }
    )
    access = EmbyServiceAccess(
        helper=FakeHelper({"policy": _service(FakeInstance("http://policy"))}),
        request_factory=lambda timeout: request,
    )

    assert [identity.profile_id for identity in access.enumerate_identities()] == [
        "emby:policy:user-4"
    ]


def test_unsafe_service_display_name_uses_stable_server_id_scope():
    """包含空格的服务名使用 Emby server ID，避免生成非法 profile_id。"""
    request = FakeRequest(
        {
            "http://named/Users": FakeResponse(
                200, [{"Id": "user-2", "Name": "Bob"}]
            )
        }
    )
    access = EmbyServiceAccess(
        helper=FakeHelper(
            {
                "家庭 Emby": _service(
                    FakeInstance("http://named", server_id="server-abc")
                )
            }
        ),
        request_factory=lambda timeout: request,
    )

    identity = access.enumerate_identities()[0]

    assert identity.server_name == "server-abc"
    assert access.resolve_service(identity.server_name)[0] == "家庭 Emby"
