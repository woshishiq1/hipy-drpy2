# coding=utf-8
import json
from base.spider import Spider as BaseSpider
import os

class Spider(BaseSpider):

    def getName(self):
        return "py动作测试"

    def init(self, extend=""):
        self.port = 9980

    def homeContent(self, filter):
        return {
            'class': [
                {'type_id': 'action', 'type_name': '动作'},
            ]
        }

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        if int(pg) > 1:
            return {'list': [], 'page': pg}
        return {'list': self._action_list(), 'page': pg}

    def detailContent(self, ids):
        return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        return {'parse': 0, 'url': id}

    def action(self, action_str):
        try:
            obj = json.loads(action_str)
            act = obj.get('action', action_str)
            value = obj.get('value', '')
        except (json.JSONDecodeError, TypeError):
            act = action_str
            value = ''

        if act == '单项输入':
            if isinstance(value, dict) and "text" in value:
                url = value["text"]
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                return self._handle_webview(url)
            
        return f'py动作: {act}\n数据: {json.dumps(value, ensure_ascii=False) if value else "无"}'

    def _handle_webview(self, value):
        return {'action': {'actionId': 'OPEN_URL', 'type': 'browser', 'title': 'browser',
                           'height': -50, 'textZoom': 100, 'url': value}}

    # ==================== 动态生成HTML文件列表 ====================
    def _action_list(self):
        items = []

        # 1. 保留“访问网址”动作，方便手动输入
        items.append(self._vod('访问网址', {
            'actionId': '单项输入',
            'id': 'text',
            'type': 'input',
            'title': '网址输入',
            'tip': '请输入网址',
            'value': '',
            'msg': '请输入网址'
        }))

        # 2. 动态扫描指定文件夹中的所有 .html 文件
        folder = '/storage/emulated/0/纯福利1/html/'   # 目标文件夹，可按需修改
        if os.path.exists(folder):
            # 获取所有 .html 文件并按文件名排序
            html_files = [f for f in os.listdir(folder) if f.endswith('.html')]
            html_files.sort()

            for filename in html_files:
                name = os.path.splitext(filename)[0]          # 去掉扩展名作为显示名称
                url = 'file://' + os.path.join(folder, filename)  # 构建 file:// URL
                config = {
                    'actionId': 'OPEN_URL',
                    'type': 'browser',
                    'title': 'browser',
                    'style': 'fullscreen',    # 全屏样式，可按需调整
                    'height': -260,
                    'textZoom': 70,
                    'url': url
                }
                items.append(self._vod(name, config))

        return items

    @staticmethod
    def _vod(name, config):
        return {
            'vod_id': json.dumps(config, ensure_ascii=False),
            'vod_name': name,
            'vod_tag': 'action'
        }

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        pass