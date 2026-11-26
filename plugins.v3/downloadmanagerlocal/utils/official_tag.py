"""按目标站点与原始发布名识别官种，不依赖联网查询。"""

import re

from bencode import bdecode

DEFAULT_OFFICIAL_MAPPINGS = """观众:Audies|ADE|ADWeb|ADAudio|ADeBook|ADMusic
憨憨:HHWEB
青蛙:FROG|FROGE|FROGWeb|CatEDU
我堡:OurBits|OurTV
猫站:PTerWEB|PTer|PTerMV|PTerTV
高清杜比:QHstudIo|Dream
朋友:FRDS
猪猪:PigoWeb|PigoHD|PigoNF|PigoAD
Sunny:Sunny
馒头:MTeam|MWEB"""
_ROLE_TAG = re.compile(r"[^\w,]*(?:IYUU[\s_-]*)?(?:转种|铺种|辅种|转移做种)", re.IGNORECASE)


def parse_official_mappings(text):
    """按行合并同站组名，忽略空行与缺失两侧的项。"""
    mappings = {}
    for line in (text or "").splitlines():
        site, separator, groups = line.replace("：", ":", 1).partition(":")
        if separator and site.strip():
            mappings.setdefault(site.strip().casefold(), set()).update(
                group.strip().casefold() for group in groups.split("|") if group.strip()
            )
    return mappings


def official_label(plugin):
    """返回启用时的官种标签；非法复合标签不参与写入。"""
    if getattr(plugin, "_tag_official_enabled", False) is not True:
        return ""
    prefix = getattr(plugin, "_tag_official_prefix", "🏅") or ""
    return "" if any(char in prefix for char in ",\r\n") else f"{prefix}官种"


def release_part(name):
    """去除显示名前缀、扩展名与附加副标题，保留发布名。"""
    title = re.sub(r"^(?:\s*\[[^\]]*\]\s*(?:-\s*)?)+", "", str(name or "")).strip()
    title = re.split(r"\s*[\[【]|\s+\|\s+", title, maxsplit=1)[0].rstrip()
    title = re.sub(r"\.(?:mkv|mp4|avi|m2ts|ts|torrent)$", "", title, flags=re.IGNORECASE)
    return title.casefold()


def matches_release(name, groups):
    """仅识别发布名末尾的独立制作组，排除副标题内的组名。"""
    title = release_part(name)
    return any(len(title) > len(group) + 1 and title.endswith((f"-{group}", f"@{group}")) for group in groups)


def transfer_release_name(metadata_name, task_name):
    """原种根名已有组标时优先，以免下载器改名串组；普通根名可回退到任务发布名。"""
    if re.search(r"[-@][\w.]+$", release_part(metadata_name)):
        return metadata_name
    return task_name or metadata_name


def torrent_evidence(content):
    """从当前种子元数据取根名和 announce，不借用母种文件名。"""
    try:
        data = bdecode(content, decode=0)
        info = data[b"info"]
        name = (info.get(b"name.utf-8") or info.get(b"name") or b"").decode("utf-8")
        announces = [data.get(b"announce"), *(url for tier in data.get(b"announce-list", []) for url in tier)]
        return name, [url.decode("utf-8") for url in announces if isinstance(url, bytes) and url]
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError):
        return "", []


def match_official(plugin, site, name):
    """只在指定站点自身的映射内查找组名。"""
    groups = getattr(plugin, "_official_groups", {}).get(str(site or "").strip().casefold(), ())
    return official_label(plugin) if groups and matches_release(name, groups) else ""


def role_tags(tags):
    """只选转种与铺种角色，不把“已整理”或用户自定义用途标签一起移除。"""
    return {tag for tag in tags if _ROLE_TAG.fullmatch(tag.strip())}


def apply_official(tags, label):
    """命中时以官种标签替换角色标签，保留其余标签与顺序。"""
    if not label:
        return tags
    replaced = role_tags(tags)
    return list(dict.fromkeys([*(tag for tag in tags if tag not in replaced), label]))
