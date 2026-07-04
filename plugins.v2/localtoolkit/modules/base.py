from datetime import datetime
from app.log import logger
from app.schemas.types import NotificationType

class BaseToolModule:
    module_key = ""
    module_name = ""
    def __init__(self, plugin):
        self.plugin = plugin
        self.config = {}
    def load_config(self, config):
        self.config = config or {}
    def get_default_config(self):
        return {}
    def get_service(self):
        return []
    def get_status(self):
        return {}
    def run_once(self):
        raise NotImplementedError
    def add_history(self, status='success', summary='', duration=0):
        history = self.plugin.get_data(key='tool_history') or []
        if not isinstance(history, list):
            logger.warning('本地工具集：历史记录格式异常，已重置')
            history = []
        if summary is None:
            summary = ''
        elif not isinstance(summary, str):
            summary = str(summary)
        try:
            duration = round(float(duration or 0), 3)
        except (TypeError, ValueError):
            duration = 0
        history.insert(0, {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'module': self.module_key,
            'module_name': self.module_name,
            'status': status,
            'summary': summary,
            'duration': duration,
        })
        self.plugin.save_data(key='tool_history', value=history[:30])

    def send_notification(self, title, text):
        if self.config.get('notify', True):
            try:
                self.plugin.post_message(mtype=NotificationType.Plugin, title=title, text=text)
            except Exception as e:
                logger.warning(f'本地工具集：发送通知失败：{e}')
