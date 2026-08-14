import time
import redis
from app.log import logger
from app.core.config import settings
from ..security import redact_sensitive_text, safe_error_text
from .base import BaseToolModule

class TmdbCacheModule(BaseToolModule):
    """清理 TMDB 缓存模块，按需清理 Redis 中的 TMDB 缓存键。"""

    module_key = 'tmdb_cache'
    module_name = '清理TMDB'
    _TMDB_CACHE_PATTERNS = ['app.modules.themoviedb*', '__tmdb_cache__*', 'curetmdbanime:tmdb*']
    def get_default_config(self):
        """返回清理 TMDB 缓存默认配置。"""
        return {'notify': True, 'auto_clear': False, 'threshold_mb': 50}
    def _redis(self):
        try:
            client = redis.from_url(settings.CACHE_BACKEND_URL or 'redis://localhost:6379', decode_responses=False, socket_timeout=5)
            client.ping(); return client
        except Exception as e:
            logger.warning(f'本地工具集：Redis连接失败：{redact_sensitive_text(e)}')
            return None
    def get_service(self):
        """清理 TMDB 缓存只支持手动运行，不注册后台服务。"""
        # TMDB 缓存清理仅按需运行，不注册周期服务。
        return []
    def _keys(self):
        client=self._redis()
        if not client: return []
        keys=[]
        for pattern in self._TMDB_CACHE_PATTERNS:
            try: keys.extend(client.keys(f'region:{pattern}'))
            except Exception as e: logger.warning(f'本地工具集：查询缓存键失败 pattern={pattern}: {redact_sensitive_text(e)}')
        return list(set(keys))
    def _status(self):
        client=self._redis()
        if not client: return {'keys':0,'size_kb':0.0,'error':'Redis 未连接'}
        keys=self._keys(); total=0
        for k in keys:
            try:
                dump=client.dump(k); total += len(k) + (len(dump) if dump else 0)
            except Exception: pass
        return {'keys':len(keys),'size_kb':round(total/1024,1),'error':None}
    def get_status(self):
        """返回 TMDB 缓存模块状态。"""
        st=self._status(); st.update({'run_mode': 'manual'}); return st
    def run_once(self):
        """执行一次 TMDB 缓存清理。"""
        start=time.time(); client=self._redis(); before=self._status()
        if not client:
            self.add_history('failed','Redis 未连接',time.time()-start); return {'success':False,'message':'Redis 未连接'}
        if self.config.get('auto_clear') and self.config.get('threshold_mb',0)>0 and before['size_kb'] < float(self.config.get('threshold_mb',50))*1024:
            msg=f"缓存 {before['size_kb']/1024:.2f}MB 未超过阈值 {self.config.get('threshold_mb')}MB"
            self.add_history('success',msg,time.time()-start)
            if self.config.get('notify', True):
                self.send_notification('本地工具集 - 清理TMDB', msg)
            return {'success':True,'message':msg,'deleted':0}
        keys=self._keys(); deleted=0
        try:
            if keys: deleted=client.delete(*keys)
        except Exception as e:
            logger.error(f'本地工具集：清理TMDB缓存失败：{redact_sensitive_text(e)}')
            safe_message = safe_error_text('清理 TMDB 缓存')
            self.add_history('failed', safe_message, time.time()-start)
            if self.config.get('notify', True):
                self.send_notification('本地工具集 - 清理TMDB', safe_message)
            return {'success': False, 'message': safe_message}
        after=self._status(); summary=f"清理 TMDB 缓存 {deleted}/{len(keys)} 个，清理后 {after['keys']} 个键"
        logger.info('本地工具集：'+summary)
        self.plugin.save_data(key='tmdb_cache_result', value={'before':before,'after':after,'deleted':deleted})
        self.add_history('success', summary, time.time()-start)
        if self.config.get('notify', True):
            self.send_notification('本地工具集 - 清理TMDB', summary)
        return {'success': True, 'deleted': deleted, 'total': len(keys), 'before': before, 'after': after, 'message': summary}
