"""路径转换工具"""


def convert_save_path(save_path: str, from_root: str, to_root: str) -> str:
    """将保存路径从源下载器根目录映射到目标下载器根目录。

    例如：/downloads/movie/xxx → /media/movie/xxx
    """
    if not save_path or not from_root or not to_root:
        return save_path
    source = from_root.replace('\\', '/').rstrip('/') or '/'
    path = save_path.replace('\\', '/')
    if path.rstrip('/') == source or path == source:
        return to_root
    prefix = source.rstrip('/') + '/'
    if not path.startswith(prefix):
        return save_path
    separator = '\\' if '\\' in to_root and '/' not in to_root else '/'
    suffix = path[len(prefix):].replace('/', separator)
    return to_root.rstrip('/\\') + separator + suffix
