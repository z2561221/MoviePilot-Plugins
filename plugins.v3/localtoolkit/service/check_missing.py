import re, time
from pathlib import Path
from app.sdk.logging import logger
from ..adapter.cleanup_notification import plain_report
from .base import BaseToolModule
from .missing_report import build_missing_report

class CheckMissingModule(BaseToolModule):
    """扫描缺集模块，按配置路径检查 STRM 剧集缺口。"""

    module_key='check_missing'; module_name='扫描缺集'
    def get_default_config(self):
        """返回扫描缺集默认配置。"""
        return {'notify': True, 'scan_paths':'', 'skip_empty': True}
    def get_service(self):
        """扫描缺集只支持手动运行，不注册后台服务。"""
        # 查漏集仅按需运行，不注册周期服务。
        return []
    def _paths(self):
        raw=self.config.get('scan_paths') or self.config.get('paths') or ''
        if isinstance(raw, list): return raw
        return [x.strip() for x in str(raw).splitlines() if x.strip()]
    @staticmethod
    def _path_label(value):
        """将完整扫描路径收敛为末三级目录标签。"""
        path = Path(value)
        parts = path.parts[-3:]
        return '/'.join(parts) if parts else path.name
    def run_once(self):
        """执行一次缺集扫描。"""
        start=time.time(); results=[]; missing_total=0
        ep_re=re.compile(r'[Ss](\d{1,2})[ ._-]*[Ee](\d{1,3})|[Ee](\d{1,3})')
        for base in self._paths():
            bp=Path(base)
            if not bp.exists():
                results.append({'path':self._path_label(base),'status':'not_exists','missing':[]}); continue
            # 只扫描分类目录（国漫/日番）的直接子目录作为剧集目录
            for cat in [d for d in bp.iterdir() if d.is_dir()]:
                for sd in [d for d in cat.iterdir() if d.is_dir() and any(f.is_file() for f in d.iterdir())]:
                    files=[f for f in sd.rglob('*.strm') if f.is_file()]
                    if self.config.get('skip_empty', True) and not files: continue
                    seasons={}
                    for f in files:
                        m=ep_re.search(f.name)
                        if not m: continue
                        s=int(m.group(1) or 1); e=int(m.group(2) or m.group(3)); seasons.setdefault(s,set()).add(e)
                    for s, eps in seasons.items():
                        if not eps: continue
                        # 跳过 Season 0（特典/OVA/SP），用户不需要
                        if s == 0: continue
                        miss=[i for i in range(1,max(eps)+1) if i not in eps]
                        # 整季全部缺失说明用户不需要这季，不报缺
                        if miss and len(miss) < max(eps):
                            missing_total += len(miss)
                            results.append({'path':self._path_label(cat),'title':sd.name,'season':s,'missing':miss})
        summary=f'扫描 {len(self._paths())} 个路径，缺失 {missing_total} 集'
        self.plugin.save_data(key='check_missing_result', value=results[:500])
        logger.info('本地工具集：'+summary)
        self.add_history('success', summary, time.time()-start)
        if self.config.get('notify', True):
            report = build_missing_report(results, summary)
            self.send_notification(
                '本地工具集 - 扫描缺集', plain_report(report), html_text=report,
            )
        return {'success': True, 'summary': summary, 'missing_total': missing_total, 'items': results[:200]}
    def get_status(self):
        """返回扫描缺集模块状态。"""
        return {'run_mode': 'manual', 'paths': len(self._paths()), 'last_count': len(self.plugin.get_data(key='check_missing_result') or [])}
