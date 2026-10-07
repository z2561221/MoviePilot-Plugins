"""保存路径映射仅匹配根目录本身与目录内路径。"""

import pytest
from app.plugins.downloadmanagerlocal.utils.path import convert_save_path


@pytest.mark.parametrize("path,source,target,expected", [
    ("/downloads2/Movie", "/downloads", "/seed", "/downloads2/Movie"),
    ("/downloads/Movie", "/downloads", "/seed", "/seed/Movie"),
    ("/downloads", "/downloads/", "/seed/", "/seed/"),
    ("/downloads/Movie", "/downloads/", "/seed/", "/seed/Movie"),
    ("/Movie", "/", "/seed", "/seed/Movie"),
    ("/downloads/Movie", "/downloads", "/", "/Movie"),
    (r"D:\downloads2\Movie", r"D:\downloads", r"E:\seed", r"D:\downloads2\Movie"),
    (r"D:\downloads\Movie", r"D:\downloads", r"E:\seed", r"E:\seed\Movie"),
    ("smb:/share2/Movie", "smb:/share", "/seed", "smb:/share2/Movie"),
    ("smb:/share/Movie", "smb:/share", "smb:/other", "smb:/other/Movie"),
    ("/downloads/Movie", "", "/seed", "/downloads/Movie"),
])
def test_mapping_preserves_directory_and_storage_identity(path, source, target, expected):
    """覆盖相似前缀、根目录、尾分隔符、Windows 与远程身份。"""
    assert convert_save_path(path, source, target) == expected
