"""AgentRank 稳定 Emby 用户身份测试。"""

import importlib
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType

import pytest


PLUGIN_DIR = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "agentrank_identity_test"
package = sys.modules.setdefault(PACKAGE_NAME, ModuleType(PACKAGE_NAME))
package.__path__ = [str(PLUGIN_DIR)]

identity_module = importlib.import_module(f"{PACKAGE_NAME}.model.identity")
EmbyIdentity = identity_module.EmbyIdentity


def test_identity_is_stable_across_display_name_changes_and_round_trips():
    """显示名变化不应改变由服务器和 user ID 组成的画像主键。"""
    identity = EmbyIdentity("家庭服", "user-001", "Alice Zhang")
    renamed = EmbyIdentity("家庭服", "user-001", "Alice")

    assert identity.profile_id == "emby:家庭服:user-001"
    assert renamed.profile_id == identity.profile_id
    assert EmbyIdentity.from_dict(identity.to_dict()) == identity


def test_same_username_on_different_servers_remains_isolated():
    """不同服务器的同名用户必须获得不同画像主键。"""
    home = EmbyIdentity("home", "id-1", "Alice")
    remote = EmbyIdentity("remote", "id-1", "Alice")

    assert home.profile_id != remote.profile_id
    assert {home.profile_id, remote.profile_id} == {
        "emby:home:id-1",
        "emby:remote:id-1",
    }


@pytest.mark.parametrize(
    ("server_name", "user_id", "username"),
    [
        ("", "id-1", "Alice"),
        ("home", "", "Alice"),
        ("home", "id-1", ""),
        ("home/server", "id-1", "Alice"),
        ("home", "id:1", "Alice"),
        ("home server", "id-1", "Alice"),
        ("home", "id-1", "Alice\nAdmin"),
    ],
)
def test_identity_rejects_missing_or_unsafe_scope_values(
    server_name, user_id, username
):
    """空身份、作用域分隔符、空白和控制字符必须被拒绝。"""
    with pytest.raises(ValueError):
        EmbyIdentity(server_name, user_id, username)


def test_identity_rejects_tampered_profile_id_and_is_immutable():
    """持久化主键必须匹配身份字段，且实例创建后不可改写。"""
    identity = EmbyIdentity("home", "id-1", "Alice")
    value = identity.to_dict()
    value["profile_id"] = "emby:other:id-1"

    with pytest.raises(ValueError, match="profile_id"):
        EmbyIdentity.from_dict(value)
    with pytest.raises(FrozenInstanceError):
        identity.user_id = "id-2"


@pytest.mark.parametrize("schema_version", [0, -1])
def test_identity_rejects_non_positive_persisted_schema_version(schema_version):
    """持久化数据不得用非正版本号绕过身份结构校验。"""
    value = EmbyIdentity("home", "id-1", "Alice").to_dict()
    value["schema_version"] = schema_version

    with pytest.raises(ValueError, match="schema_version"):
        EmbyIdentity.from_dict(value)
