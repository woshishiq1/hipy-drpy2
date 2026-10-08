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

    # ==================== 数据列表 ====================
    def _action_list(self):
        return [
            self._vod('访问网址', {'actionId': '单项输入', 'id': 'text', 'type': 'input',
                                 'title': '网址输入', 'tip': '请输入网址', 'value': '',
                                 'msg': '请输入网址'}),
            self._vod('youtube', {'actionId': 'OPEN_URL', 'type': 'browser', 'title': 'browser',
                                  'height': -260, 'textZoom': 70, 'url': 'https://m.youtube.com'}),
            self._vod('ebo seks', {'actionId': 'OPEN_URL', 'type': 'browser', 'title': 'browser',
                                  'height': -260, 'textZoom': 70, 'url': 'https://eboseks.one/cat/18-let/'}),
          self._vod('老色胚', {'actionId': 'OPEN_URL', 'type': 'browser', 'title': 'browser',
                                  'height': -260, 'textZoom': 70, 'url': 'https://www.laidhub.com//shorties/ph61311f5650048'}),
                                  self._vod('Anysex', {'actionId': 'OPEN_URL', 'type': 'browser', 'title': 'browser',
                                  'height': -260, 'textZoom': 70, 'url': 'https://theporndude.com/zh/shorties/ph61311f5650048'}),
                                   self._vod('Xvdes', {'actionId': 'OPEN_URL', 'type': 'browser', 'title': 'browser',
                                  'height': -260, 'textZoom': 70, 'url': 'https://www.xvideos.com/shorties/ph61311f5650048'}),
                                  self._vod('XNXX', {'actionId': 'OPEN_URL', 'type': 'browser', 'title': 'browser',
                                  'height': -260, 'textZoom': 70, 'url': 'https://m.drtuber.com/##1/shorties/ph61311f5650048'}),
                                   self._vod('pornhub', {'actionId': 'OPEN_URL', 'type': 'browser', 'title': 'browser',
                                  'height': -260, 'textZoom': 70, 'url': 'https://cn.pornhub.com/shorties/ph61311f5650048'}),
            
 self._vod('JavRyo[密]', {
    'actionId': 'OPEN_URL',
    'type': 'browser',
    'title': 'browser',
    "style": "fullscreen",
    'height': -260,
    'textZoom': 70,
    'url': 'file:///storage/emulated/0/纯福利1/html/JavRyo[密].html'
}),
 self._vod('catemby', {
    'actionId': 'OPEN_URL',
    'type': 'browser',
    'title': 'browser',
    "style": "fullscreen",
    'height': -260,
    'textZoom': 70,
    'url': 'file:///storage/emulated/0/纯福利1/html/catemby.html'
}),
self._vod('Nostr推荐优化版2', {
    'actionId': 'OPEN_URL',
    'type': 'browser',
    'title': 'browser',
    "style": "fullscreen",
    'height': -260,
    'textZoom': 70,
    'url': 'file:///storage/emulated/0/纯福利1/html/Nostr推荐优化版2.html'
}),

        ]

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
