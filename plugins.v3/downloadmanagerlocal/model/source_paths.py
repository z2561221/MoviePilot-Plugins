"""本地下载源的显式历史别名；只转换路径，不访问文件或修改宿主记录。"""

from pathlib import PurePosixPath

from .sync_delete import DeleteRejected, lines, path_text, text, within


class SourcePaths:
    """只做一次最长目录匹配；反查兼容路径用于发现所有历史引用。"""

    def __init__(self, config):
        self.config = config
        roots = [path_text(root) for root in lines(config.get("sync_delete_source_paths"))]
        aliases = {}
        for line in lines(config.get("sync_delete_source_aliases")):
            parts = line.split("#")
            if len(parts) != 2:
                raise DeleteRejected("历史源路径映射需要两段，以 # 分隔")
            old, current = (path_text(part) for part in parts)
            if old == "/" or current == "/" or old == current:
                raise DeleteRejected("历史源路径映射不能使用根目录或相同目录")
            if not any(root != "/" and within(current, root) for root in roots):
                raise DeleteRejected("历史源路径映射的当前目录不在允许源目录内")
            if old in aliases and aliases[old] != current:
                raise DeleteRejected("同一历史源目录不能映射到多个当前目录")
            aliases[old] = current
        if len(aliases) > 100:
            raise DeleteRejected("历史源路径映射超过单次上限")
        for current in aliases.values():
            if any(within(current, old) or within(old, current) for old in aliases):
                raise DeleteRejected("历史源路径映射不能循环、串联或交叠当前目录")
        self.aliases = sorted(aliases.items(), key=lambda pair: len(pair[0]), reverse=True)

    def canonical(self, value):
        """仅接受本地路径，local: 只是本地存储标记；不剥离远程协议。"""
        path = path_text(text(value).removeprefix("local:"))
        for old, current in self.aliases:
            if within(path, old):
                return str(PurePosixPath(current) / PurePosixPath(path).relative_to(old))
        return path

    def equivalents(self, value):
        """包括当前路径和能确切回到该路径的所有旧路径，不扩展相邻目录。"""
        current = self.canonical(value)
        paths = {current}
        for old, target in self.aliases:
            if within(current, target):
                candidate = str(PurePosixPath(old) / PurePosixPath(current).relative_to(target))
                if self.canonical(candidate) == current:
                    paths.add(candidate)
        return sorted(paths)

    def checked(self, value):
        """保护目录对所有等价名称生效，不能用另一个名称绕过。"""
        paths = self.equivalents(value)
        excluded = [path_text(root) for root in lines(self.config.get("sync_delete_exclude_paths"))]
        if any(within(path, root) for path in paths for root in excluded):
            raise DeleteRejected("下载源位于保护目录")
        return self.canonical(value)
