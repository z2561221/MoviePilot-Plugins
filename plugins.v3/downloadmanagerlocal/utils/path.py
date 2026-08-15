"""路径转换工具"""


def convert_save_path(save_path: str, from_root: str, to_root: str) -> str:
    """将保存路径从源下载器根目录映射到目标下载器根目录。

    例如：/downloads/movie/xxx → /media/movie/xxx
    """
    if not save_path or not from_root or not to_root:
        return save_path
    if save_path.startswith(from_root):
        return save_path.replace(from_root, to_root, 1)
    return save_path
