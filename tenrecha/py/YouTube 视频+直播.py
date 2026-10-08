# coding=utf-8
#!/usr/bin/python
#AureCod 2026.8.22(优化版 - 仅增强缓存与重试，播放逻辑不变)

import re
import json
import html
import time
import threading
import collections
from urllib.parse import quote, unquote, parse_qs, urlencode, urlparse, urlunparse, urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from base.spider import Spider

class Const:
    PROXY_BASE = 'http://127.0.0.1:9978/proxy'
    QUALITY_SUPER = 'super'
    QUALITY_NORMAL = 'normal'
    QUALITY_LIVE = 'live'
    CAT_MOVIE = "电影"
    CAT_LIVE = "直播"
    CAT_MUSIC = "音乐"
    CAT_HDR = "HDR"
    CAT_FREE = "免费"
    CAT_SHORT = "短劇"
    CAT_CARTOON = "动画片"
    EXTRACT_CACHE_TTL = 300
    LIVE_CACHE_TTL = 90
    HLS_MASTER_TTL = 6 * 3600
    HLS_PLAYLIST_TTL = 6 * 3600
    HLS_MEDIA_TTL = 120
    MPD_CACHE_TTL = 600
    SEARCH_CACHE_TTL = 600
    GENERIC_CACHE_TTL = 600
    CLIENT_NAME_MAP = {
        'WEB': 1, 'MWEB': 2, 'ANDROID': 3, 'IOS': 5,
        'TVHTML5': 7, 'ANDROID_VR': 28, 'WEB_EMBEDDED_PLAYER': 56,
        'WEB_REMIX': 67, 'VISIONOS': 101,
    }

INNERTUBE_CLIENTS = [
    {
        'clientName': 'VISIONOS',
        'clientVersion': '1.02',
        'deviceMake': 'Apple',
        'deviceModel': 'RealityDevice17,1',
        'userAgent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 15_7_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15',
        'osName': 'visionOS',
        'osVersion': '26.5.23O471',
        'hl': 'en',
        'gl': 'US'
    },
    {
        'clientName': 'WEB_EMBEDDED_PLAYER',
        'clientVersion': '2.20260708.00.00',
        'hl': 'en',
        'gl': 'US'
    },
]

YOUTUBE_CLASSES = [
    {"type_id": Const.CAT_MOVIE, "type_name": "电影"},
    {"type_id": Const.CAT_LIVE, "type_name": "直播"},
    {"type_id": Const.CAT_MUSIC, "type_name": "音乐"},
    {"type_id": Const.CAT_HDR, "type_name": "HDR"},
    {"type_id": Const.CAT_FREE, "type_name": "免费"},
    {"type_id": Const.CAT_SHORT, "type_name": "短剧"},
    {"type_id": Const.CAT_CARTOON, "type_name": "动画片"}
]

CATEGORY_FILTERS = {
    Const.CAT_MOVIE: [
        {"key": "topic", "name": "官方分类", "value": [{"n": "电影", "v": "电影"}, {"n": "电影与动画", "v": "电影与动画"}, {"n": "电视节目", "v": "电视节目"}]},
        {"key": "tid", "name": "地区", "value": [{"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"}]},
        {"key": "date", "name": "排序/时间", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "latest"}, {"n": "最热", "v": "hottest"}, {"n": "评分最高", "v": "favorite"}, {"n": "当天", "v": "day"}, {"n": "本周", "v": "week"}, {"n": "本月", "v": "month"}]}
    ],
    Const.CAT_LIVE: [
        {"key": "topic", "name": "官方分类", "value": [{"n": "新闻直播", "v": "新闻直播"}, {"n": "游戏直播", "v": "游戏直播"}, {"n": "体育直播", "v": "体育直播"}, {"n": "音乐直播", "v": "音乐直播"}]},
        {"key": "tid", "name": "直播类型", "value": [{"n": "全部直播", "v": "全部直播"}, {"n": "游戏", "v": "游戏"}, {"n": "新闻", "v": "新闻"}, {"n": "体育", "v": "体育"}, {"n": "音乐现场", "v": "音乐现场"}, {"n": "生活", "v": "生活"}]},
        {"key": "date", "name": "排序/时间", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "latest"}, {"n": "最热", "v": "hottest"}, {"n": "评分最高", "v": "favorite"}, {"n": "当天", "v": "day"}, {"n": "本周", "v": "week"}, {"n": "本月", "v": "month"}]}
    ],
    Const.CAT_MUSIC: [
        {"key": "topic", "name": "官方分类", "value": [{"n": "音乐", "v": "音乐"}, {"n": "流行音乐", "v": "流行音乐"}, {"n": "摇滚乐", "v": "摇滚乐"}, {"n": "嘻哈音乐", "v": "嘻哈音乐"}, {"n": "电子音乐", "v": "电子音乐"}, {"n": "重金属", "v": "重金属"}, {"n": "重金属根源雷鬼", "v": "重金属根源雷鬼"}, {"n": "Dub", "v": "Dub"}, {"n": "Bass", "v": "Bass"}]},
        {"key": "tid", "name": "形式/场景", "value": [{"n": "MV", "v": "MV"}, {"n": "现场", "v": "现场"}, {"n": "翻唱", "v": "翻唱"}, {"n": "精选", "v": "精选"}, {"n": "车载", "v": "车载"}]},
        {"key": "date", "name": "排序/时间", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "latest"}, {"n": "最热", "v": "hottest"}, {"n": "评分最高", "v": "favorite"}, {"n": "当天", "v": "day"}, {"n": "本周", "v": "week"}, {"n": "本月", "v": "month"}]}
    ],
    Const.CAT_HDR: [
        {"key": "tid", "name": "画质类型", "value": [{"n": "HDR", "v": "HDR"}, {"n": "杜比", "v": "杜比"}, {"n": "4K", "v": "4K"}, {"n": "8K", "v": "8K"}, {"n": "12K", "v": "12K"}, {"n": "16K", "v": "16K"}]},
        {"key": "topic", "name": "关联主题（加画质）", "value": [{"n": "自然+8K", "v": "自然+8K"}, {"n": "电影+4K", "v": "电影+4K"}, {"n": "风景+HDR", "v": "风景+HDR"}]},
        {"key": "date", "name": "排序/时间", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "latest"}, {"n": "最热", "v": "hottest"}, {"n": "评分最高", "v": "favorite"}, {"n": "当天", "v": "day"}, {"n": "本周", "v": "week"}, {"n": "本月", "v": "month"}]}
    ],
    Const.CAT_FREE: [
        {"key": "tid", "name": "免费内容", "value": [{"n": "免费电影", "v": "免费电影"}, {"n": "免费电视剧", "v": "免费电视剧"}, {"n": "免费纪录片", "v": "免费纪录片"}, {"n": "免费音乐", "v": "免费音乐"}, {"n": "免费课程", "v": "免费课程"}, {"n": "免费直播", "v": "免费直播"}]},
        {"key": "topic", "name": "关联主题（加免费）", "value": [{"n": "电影+免费", "v": "电影+免费"}, {"n": "教育+免费", "v": "教育+免费"}, {"n": "音乐+免费", "v": "音乐+免费"}]},
        {"key": "date", "name": "排序/时间", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "latest"}, {"n": "最热", "v": "hottest"}, {"n": "评分最高", "v": "favorite"}, {"n": "当天", "v": "day"}, {"n": "本周", "v": "week"}, {"n": "本月", "v": "month"}]}
    ],
    Const.CAT_SHORT: [
        {"key": "date", "name": "排序/时间", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "latest"}, {"n": "最热", "v": "hottest"}, {"n": "评分最高", "v": "favorite"}, {"n": "当天", "v": "day"}, {"n": "本周", "v": "week"}, {"n": "本月", "v": "month"}]},
        {"key": "tid", "name": "地区/平台", "value": [{"n": "全部", "v": ""}, {"n": "抖音", "v": "抖音 短剧"}, {"n": "快手", "v": "快手 短剧"}, {"n": "大陆", "v": "大陆 短剧"}, {"n": "香港", "v": "香港 短剧"}, {"n": "澳門", "v": "澳門 短剧"}, {"n": "台湾", "v": "台湾 短剧"}, {"n": "新加坡", "v": "新加坡 短剧"}, {"n": "馬來西亞", "v": "馬來西亞 短剧"}, {"n": "泰國", "v": "泰國 短剧"}, {"n": "越南", "v": "越南 短剧"}, {"n": "印度", "v": "印度 短剧"}, {"n": "韩国", "v": "韩国 短剧"}, {"n": "日本", "v": "日本 短剧"}, {"n": "欧美", "v": "欧美 短剧"}, {"n": "腾讯", "v": "腾讯 短剧"}, {"n": "爱奇艺", "v": "爱奇艺 短剧"}, {"n": "优酷", "v": "优酷 短剧"}, {"n": "芒果", "v": "芒果TV 短剧"}, {"n": "搜狐", "v": "搜狐 短剧"}]},
        {"key": "topic", "name": "类型/频道", "value": [{"n": "全部", "v": ""}, {"n": "都市", "v": "@Urbanshort-TV 都市 短劇"}, {"n": "爱情", "v": "爱情 短劇"}, {"n": "复仇", "v": "复仇 短劇"}, {"n": "霸总", "v": "霸总 短劇"}, {"n": "萌宝", "v": "萌宝 短劇"}, {"n": "古装", "v": "古装 短劇"}, {"n": "穿越", "v": "穿越 短劇"}, {"n": "喜剧", "v": "喜剧 短劇"}, {"n": "奇幻", "v": "奇幻 短劇"}, {"n": "九酱爱追剧", "v": "@NineSauceDramaTV"}, {"n": "百万好剧场", "v": "@1-pw5ox"}, {"n": "咖啡追剧", "v": "@@coffeedrama605"}, {"n": "斗罗短剧", "v": "@DouluoDrama123 斗羅短劇"}, {"n": "嘟嘟剧场", "v": "@DUDUJUCHANG"}, {"n": "牛牛短剧", "v": "@niuniuduanju"}]}
    ],
    Const.CAT_CARTOON: [
        {"key": "date", "name": "排序/时间", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "latest"}, {"n": "最热", "v": "hottest"}, {"n": "评分最高", "v": "favorite"}, {"n": "当天", "v": "day"}, {"n": "本周", "v": "week"}, {"n": "本月", "v": "month"}]},
        {"key": "tid", "name": "平台/频道", "value": [{"n": "全部", "v": ""}, {"n": "小猪佩奇", "v": "@PeppaPigChineseOfficial 小猪佩奇 中文官方 - Peppa Pig"}, {"n": "CoComelon", "v": "@CoComelon"}, {"n": "国漫社", "v": "@Animation  次元 苍穹动漫 PP看动漫 公馆"}, {"n": "国漫工厂", "v": "@3DGuoman  SUB"}, {"n": "阅文动漫", "v": "@yuewenanimation  SUB"}, {"n": "哔哩", "v": "@madebybilibili  哔哩动漫"}, {"n": "腾讯", "v": "@TencentVideoAnimation SUB"}, {"n": "优酷", "v": "@youkuanimation 优酷动漫"}, {"n": "爱奇艺", "v": "@iQIYIAnime 爱奇艺动漫"}]},
        {"key": "topic", "name": "主题/类别", "value": [{"n": "全部", "v": ""}, {"n": "默认中文国漫", "v": "國漫 劇集 3D"}, {"n": "默认动画", "v": "animation"}, {"n": "儿童早教", "v": "儿童早教"}, {"n": "儿童歌曲", "v": "儿童歌曲"}, {"n": "儿童音乐", "v": "儿童音乐"}, {"n": "儿童绘画", "v": "儿童绘画"}, {"n": "宝宝巴士", "v": "宝宝巴士"}, {"n": "儿歌多多", "v": "儿歌多多"}, {"n": "儿童英语启蒙", "v": "儿童英语启蒙"}, {"n": "儿童启蒙故事", "v": "儿童启蒙故事"}, {"n": "儿童安全教育", "v": "儿童安全教育"}, {"n": "默认英文国漫", "v": "3D Chinese cartoon"}, {"n": "合集", "v": "Anime ENG SUB 合集"}]}
    ]
}

class BaseExtractor:
    """提取器公共基类"""

    def __init__(self, session, headers=None, config=None):
        self.session = session
        self.headers = headers or {}
        self.config = config or {}
        self._lock = threading.Lock()
        self.player_cache = {}
        self.sig_plan_cache = {}
        self.n_function_cache = {}

    @staticmethod
    def extract_video_id(text):
        text = str(text or '').strip()
        for pattern in [
            r'(?:v=|/v/|/embed/|/shorts/|youtu\.be/)([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$',
        ]:
            m = re.search(pattern, text)
            if m:
                return m.group(1)
        raise ValueError('无法识别 YouTube 视频 ID')

    @staticmethod
    def _client_name_id(client_name):
        return Const.CLIENT_NAME_MAP.get(client_name, 1)

    @staticmethod
    def _extract_ytcfg(text):
        m = re.search(r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;', text, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        return None

    @staticmethod
    def _extract_json_after(text, marker):
        pos = text.find(marker)
        if pos < 0:
            return None
        start = text.find('{', pos)
        if start < 0:
            return None
        depth = 0
        in_str = None
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if in_str:
                if ch == in_str:
                    in_str = None
                continue
            if ch == '"':
                in_str = ch
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except Exception:
                        return None
        return None

    @staticmethod
    def _search(pattern, text, default=None):
        m = re.search(pattern, text or '', re.S)
        return m.group(1) if m else default

    @staticmethod
    def _extract_player_url(text):
        for pattern in [
            r'"jsUrl":"([^"]+)"',
            r'"PLAYER_JS_URL":"([^"]+)"',
            r'(/s/player/[^"\\]+/base\.js)',
        ]:
            m = re.search(pattern, text)
            if m:
                return m.group(1).replace('\\/', '/')
        return ''

    # ---------- HTTP 方法（增加重试） ----------
    def _get(self, url, **kwargs):
        headers = self.headers.copy()
        headers.update(kwargs.pop('headers', {}) or {})
        timeout = kwargs.pop('timeout', 60)
        max_retries = 3
        backoff = 1
        for attempt in range(max_retries + 1):
            try:
                r = self.session.get(url, headers=headers, timeout=timeout, **kwargs)
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                if attempt == max_retries:
                    
                    raise
                time.sleep(backoff * (2 ** attempt))
        raise RuntimeError("无法完成 GET 请求")

    def _post_json(self, url, payload, headers=None):
        h = self.headers.copy()
        h.update({'Content-Type': 'application/json', 'Origin': 'https://www.youtube.com'})
        if headers:
            h.update({k: v for k, v in headers.items() if v})
        max_retries = 3
        backoff = 1
        for attempt in range(max_retries + 1):
            try:
                r = self.session.post(url, json=payload, headers=h, timeout=60)
                r.raise_for_status()
                return r.json()
            except requests.RequestException as e:
                if attempt == max_retries:
                    raise
                time.sleep(backoff * (2 ** attempt))
        raise RuntimeError("无法完成 POST 请求")

    # ---------- Player JS ----------
    def _get_player_code(self, player_url):
        if not player_url:
            return ''
        with self._lock:
            if player_url in self.player_cache:
                return self.player_cache[player_url]
        if player_url.startswith('//'):
            player_url = 'https:' + player_url
        elif player_url.startswith('/'):
            player_url = 'https://www.youtube.com' + player_url
        try:
            code = self._get(player_url, timeout=90).text
        except Exception as e:
            code = ''
        with self._lock:
            self.player_cache[player_url] = code
        return code

    def _extract_signature_timestamp(self, player_url):
        try:
            code = self._get_player_code(player_url)
            sts = self._search(r'(?:signatureTimestamp|sts)\s*:\s*(\d{5})', code)
            return int(sts) if sts else None
        except Exception as e:
            return None

    def _extract_initial_player_response(self, text):
        return self._extract_json_after(text, 'ytInitialPlayerResponse')

    # ---------- 签名解密 ----------
    def _decrypt_sig(self, sig, player_url):
        cache_key = player_url or ''
        with self._lock:
            plan = self.sig_plan_cache.get(cache_key)
        if plan is None:
            code = self._get_player_code(player_url)
            plan = self._extract_sig_plan(code)
            with self._lock:
                self.sig_plan_cache[cache_key] = plan
        if not plan:
            return sig
        arr = list(sig)
        for op, arg in plan:
            if op == 'reverse':
                arr.reverse()
            elif op in ('slice', 'splice'):
                arr = arr[int(arg):]
            elif op == 'swap' and arr:
                j = int(arg) % len(arr)
                arr[0], arr[j] = arr[j], arr[0]
        return ''.join(arr)

    def _extract_sig_plan(self, code):
        if not code:
            return None
        name = None
        patterns = [
            r'\.sig\|\|([a-zA-Z0-9_$]+)\(',
            r'"signature",\s*([a-zA-Z0-9_$]+)\(',
            r'([a-zA-Z0-9_$]+)=function\(a\)\{a=a\.split\(""\);',
            r'([a-zA-Z0-9_$]+)\s*=\s*function\(a\)\{a=a\.split\(""\)',
            r'([a-zA-Z0-9_$]+)\(a\)\{a=a\.split\(""\)',
            r'([a-zA-Z0-9_$]+)\s*:\s*function\(a\)\{a=a\.split\(""\)',
            r'(?:^|;)\s*([a-zA-Z0-9_$]+)\s*=\s*function\(a\)\{[^}]*split\(""\)',
            r'\.get\("n"\)\)\&\&\(b=([a-zA-Z0-9_$]+)\(b\)',
        ]
        for pattern in patterns:
            m = re.search(pattern, code)
            if m:
                name = m.group(1)
                break
        if not name:
            return None
        body = self._extract_js_function_body(code, name)
        if not body:
            return None
        helper = self._search(r'([a-zA-Z0-9_$]+)\.[a-zA-Z0-9_$]+\(a,\d+\)', body)
        helper_map = self._extract_helper_object(code, helper) if helper else {}
        plan = []
        for part in body.split(';'):
            if 'reverse()' in part:
                plan.append(('reverse', 0))
                continue
            m = re.search(r'\.slice\((\d+)\)', part)
            if m:
                plan.append(('slice', int(m.group(1))))
                continue
            m = re.search(r'\.splice\(0,(\d+)\)', part)
            if m:
                plan.append(('splice', int(m.group(1))))
                continue
            m = re.search(r'([a-zA-Z0-9_$]+)\.([a-zA-Z0-9_$]+)\(a,(\d+)\)', part)
            if m and m.group(1) == helper:
                op = helper_map.get(m.group(2))
                if op:
                    plan.append((op, int(m.group(3))))
        return plan or None

    def _extract_helper_object(self, code, name):
        if not name:
            return {}
        m = re.search(r'var\s+' + re.escape(name) + r'=\{(.+?)\};', code, re.S) or \
            re.search(re.escape(name) + r'=\{(.+?)\};', code, re.S)
        if not m:
            return {}
        result = {}
        for method, body in re.findall(r'([a-zA-Z0-9_$]+):function\([a-z,]+\)\{(.*?)\}', m.group(1)):
            if '.reverse(' in body:
                result[method] = 'reverse'
            elif '.splice(' in body:
                result[method] = 'splice'
            elif '.slice(' in body:
                result[method] = 'slice'
            elif 'a[0]' in body and 'length' in body:
                result[method] = 'swap'
        return result

    def _decrypt_nsig(self, media_url, player_url):
        try:
            parsed = urlparse(media_url)
            query = parse_qs(parsed.query)
            n_value = query.get('n', [None])[0]
            if not n_value:
                return media_url
            path_match = re.search(r'/n/([^/]+)', parsed.path)
            if path_match and path_match.group(1) != n_value:
                new_path = parsed.path.replace(f"/n/{path_match.group(1)}", f"/n/{n_value}", 1)
                return urlunparse(parsed._replace(path=new_path))
            if player_url:
                func = self._get_n_function(player_url)
                if func:
                    new_n = func(n_value)
                    if new_n != n_value:
                        query['n'] = [new_n]
                        new_query = urlencode(query, doseq=True)
                        return urlunparse(parsed._replace(query=new_query))
            return media_url
        except Exception as e:
            return media_url

    def _get_n_function(self, player_url):
        with self._lock:
            if player_url in self.n_function_cache:
                return self.n_function_cache[player_url]
        code = self._get_player_code(player_url)
        func = self._extract_n_function(code)
        with self._lock:
            self.n_function_cache[player_url] = func
        return func

    def _extract_n_function(self, code):
        if not code:
            return None
        name = None
        patterns = [
            r'\.get\("n"\)\)\&\&\(b=([a-zA-Z0-9_$]+)(?:\[(\d+)\])?\(b\)',
            r'\.get\("n"\)\)\&\&\(b=([a-zA-Z0-9_$]+)\(b\)',
            r'([a-zA-Z0-9_$]+)=function\(a\)\{var b=a\.split\(""\)',
            r'function\s+([a-zA-Z0-9_$]+)\(a\)\{var b=a\.split\(""\)',
            r'([a-zA-Z0-9_$]+)=function\(a\)\{a=a\.split\(""\)',
            r'([a-zA-Z0-9_$]+)\(a\)\{var b=a\.split\(""\)',
            r'([a-zA-Z0-9_$]+)\s*:\s*function\(a\)\{[^}]*\.get\("n"\)',
            r'\.get\("n"\)[^;]*;\s*if\s*\(\s*typeof\s+([a-zA-Z0-9_$]+)\s*===',
        ]
        for pattern in patterns:
            m = re.search(pattern, code)
            if m:
                name = m.group(1)
                break
        if not name:
            return None
        body = self._extract_js_function_body(code, name)
        if not body:
            return None

        def transform(value):
            arr = list(value)
            for part in body.split(';'):
                if 'reverse()' in part:
                    arr.reverse()
                m = re.search(r'\.slice\((\d+)\)', part)
                if m:
                    arr = arr[int(m.group(1)):]
                m = re.search(r'\.splice\(0,(\d+)\)', part)
                if m:
                    arr = arr[int(m.group(1)):]
            return ''.join(arr) or value
        return transform

    def _extract_js_function_body(self, code, name):
        starts = []
        for pattern in [
            r'function\s+' + re.escape(name) + r'\s*\([^)]*\)\s*\{',
            re.escape(name) + r'\s*=\s*function\s*\([^)]*\)\s*\{',
            r'var\s+' + re.escape(name) + r'\s*=\s*function\s*\([^)]*\)\s*\{',
            re.escape(name) + r'\s*:\s*function\s*\([^)]*\)\s*\{',
        ]:
            m = re.search(pattern, code)
            if m:
                starts.append(m.end() - 1)
        if not starts:
            return ''
        start = starts[0]
        depth = 0
        in_str = None
        escape = False
        for i in range(start, len(code)):
            ch = code[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if in_str:
                if ch == in_str:
                    in_str = None
                continue
            if ch in ('"', "'", '`'):
                in_str = ch
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return code[start + 1:i]
        return ''

    # ---------- InnerTube API ----------
    def _call_player_api(self, video_id, api_key, context, referer, visitor_data=None, sts=None):
        results = []
        fallback = None
        for client_info in INNERTUBE_CLIENTS:
            client_name = client_info.get('clientName')
            ctx = {'client': client_info.copy()}
            try:
                url = f'https://www.youtube.com/youtubei/v1/player?key={api_key}&prettyPrint=false'
                payload = {
                    'context': ctx,
                    'videoId': video_id,
                    'playbackContext': {
                        'contentPlaybackContext': {
                            'html5Preference': 'HTML5_PREF_WANTS',
                            **({'signatureTimestamp': sts} if sts else {})
                        }
                    },
                    'contentCheckOk': True,
                    'racyCheckOk': True,
                }
                po_token = self._get_po_token(client_name, 'gvs')
                if po_token:
                    payload['serviceIntegrityDimensions'] = {'poToken': po_token}
                headers = {
                    'Referer': referer,
                    'X-YouTube-Client-Name': str(self._client_name_id(client_name)),
                    'X-YouTube-Client-Version': client_info.get('clientVersion') or '',
                }
                if visitor_data:
                    headers['X-Goog-Visitor-Id'] = visitor_data
                client_ua = client_info.get('userAgent')
                if client_ua:
                    headers['User-Agent'] = client_ua

                data = self._post_json(url, payload, headers=headers)
                streaming = data.get('streamingData') or {}
                if streaming:
                    data['_client_name'] = client_name
                    data['_client_ua'] = client_ua
                    results.append(data)
                if streaming and fallback is None:
                    fallback = data
                elif fallback is None:
                    fallback = data
            except Exception as e:
                continue
        return results or ([fallback] if fallback else [])

    def _get_po_token(self, client_name, context='gvs'):
        tokens = self.config.get('po_token') or self.config.get('po_tokens') or {}
        if isinstance(tokens, str):
            return tokens
        if isinstance(tokens, dict):
            return tokens.get(f'{client_name}.{context}') or tokens.get(client_name) or tokens.get(context)
        return None


class YouTubeLite(BaseExtractor):
    """YouTube 点播视频提取器"""

    def __init__(self, session, headers=None, config=None):
        super().__init__(session, headers, config)
        self.extract_cache = {}
        self.extract_cache_ttl = int(self.config.get('extract_cache_ttl') or Const.EXTRACT_CACHE_TTL)

    def extract(self, url_or_id):
        video_id = self.extract_video_id(url_or_id)
        with self._lock:
            cached = self.extract_cache.get(video_id)
        if cached and cached.get('expires', 0) > time.time():
            return cached.get('data')

        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        page = self._get(watch_url, timeout=90).text

        ytcfg = self._extract_ytcfg(page) or {}
        player_response = self._extract_initial_player_response(page) or {}
        player_url = self._extract_player_url(page)
        api_key = ytcfg.get('INNERTUBE_API_KEY') or self._search(r'"INNERTUBE_API_KEY":"([^"]+)"', page)
        visitor_data = (
            self.config.get('visitor_data') or ytcfg.get('VISITOR_DATA') or
            (((ytcfg.get('INNERTUBE_CONTEXT') or {}).get('client') or {}).get('visitorData')) or
            ((player_response.get('responseContext') or {}).get('visitorData'))
        )
        if visitor_data and not self.config.get('visitor_data'):
            self.config['visitor_data'] = visitor_data

        sts = self._extract_signature_timestamp(player_url)

        context = ytcfg.get('INNERTUBE_CONTEXT') or {
            'client': {'clientName': 'WEB', 'clientVersion': '2.20240310.01.00', 'hl': 'en', 'gl': 'US'}
        }
        responses = [player_response] if player_response else []
        if api_key:
            api_responses = self._call_player_api(video_id, api_key, context, watch_url, visitor_data, sts)
            if not isinstance(api_responses, list):
                api_responses = [api_responses] if api_responses else []
            responses.extend([x for x in api_responses if x])

        player_response = next(
            (x for x in responses if (x.get('playabilityStatus') or {}).get('status') == 'OK'),
            player_response
        )
        status = (player_response.get('playabilityStatus') or {}).get('status')
        streaming = player_response.get('streamingData') or {}
        if status and status not in ('OK', 'LIVE_STREAM_OFFLINE') and not streaming:
            reason = (player_response.get('playabilityStatus') or {}).get('reason') or status
            raise Exception(f'YouTube 不可播放: {reason}')

        details = player_response.get('videoDetails') or {}
        raw_formats = []
        seen_raw = set()
        for response in responses:
            response_streaming = (response or {}).get('streamingData') or {}
            source_raw = (response_streaming.get('formats') or []) + (response_streaming.get('adaptiveFormats') or [])
            for raw in source_raw:
                key = (raw.get('itag'), raw.get('url') or raw.get('signatureCipher') or raw.get('cipher') or raw.get('mimeType'))
                if key not in seen_raw:
                    seen_raw.add(key)
                    raw = raw.copy()
                    raw['_client_name'] = (response or {}).get('_client_name')
                    raw['_client_ua'] = (response or {}).get('_client_ua')
                    raw_formats.append(raw)

        formats = []
        for raw in raw_formats:
            item = self._normalize_format(raw, player_url)
            if item and item.get('url'):
                formats.append(item)

        if not formats:
            raise Exception('未获取到可用播放地址')

        data = {
            'id': video_id,
            'title': details.get('title') or video_id,
            'duration': int(details.get('lengthSeconds') or 0),
            'formats': formats,
            'is_live': bool(details.get('isLive')),
        }
        with self._lock:
            self.extract_cache[video_id] = {'data': data, 'expires': time.time() + self.extract_cache_ttl}
        return data

    def _normalize_format(self, fmt, player_url):
        media_url = fmt.get('url')
        if not media_url:
            cipher = fmt.get('signatureCipher') or fmt.get('cipher')
            if cipher:
                media_url = self._decrypt_signature_cipher(cipher, player_url)
        if not media_url:
            return None

        media_url = self._decrypt_nsig(media_url, player_url)

        client_name = fmt.get('_client_name')
        po_token = self._get_po_token(client_name, 'gvs') if client_name else None
        if po_token:
            sep = '&' if '?' in media_url else '?'
            media_url = f'{media_url}{sep}pot={quote(po_token)}'

        mime = fmt.get('mimeType') or ''
        ext = 'mp4' if 'mp4' in mime else 'webm' if 'webm' in mime else 'unknown'
        codecs = self._search(r'codecs="([^"]+)"', mime) or ''
        has_audio = mime.startswith('audio/') or any(x in codecs for x in ('mp4a', 'opus', 'vorbis'))
        has_video = mime.startswith('video/') or any(x in codecs for x in ('avc', 'vp9', 'av01', 'h264'))
        headers = (fmt.get('http_headers') or {}).copy()
        if fmt.get('_client_ua'):
            headers['User-Agent'] = fmt.get('_client_ua')

        return {
            'itag': fmt.get('itag'),
            'url': media_url,
            'mimeType': mime,
            'client': fmt.get('_client_name'),
            'ext': ext,
            'width': fmt.get('width') or 0,
            'height': fmt.get('height') or 0,
            'fps': fmt.get('fps') or 0,
            'bitrate': fmt.get('bitrate') or fmt.get('averageBitrate') or 0,
            'contentLength': fmt.get('contentLength'),
            'initRange': fmt.get('initializationRange') or fmt.get('initRange') or {},
            'indexRange': fmt.get('indexRange') or {},
            'codecs': codecs,
            'quality': fmt.get('qualityLabel') or fmt.get('quality'),
            'vcodec': codecs if has_video else 'none',
            'acodec': codecs if has_audio else 'none',
            'headers': headers,
        }

    def _decrypt_signature_cipher(self, cipher, player_url):
        data = parse_qs(cipher)
        media_url = unquote(data.get('url', [''])[0])
        sig = unquote(data.get('s', [''])[0])
        sp = data.get('sp', ['sig'])[0]
        if not media_url:
            return ''
        if sig:
            decoded = self._decrypt_sig(sig, player_url)
            sep = '&' if '?' in media_url else '?'
            media_url = f'{media_url}{sep}{sp}={quote(decoded)}'
        return media_url


class YouTubeLiveLite(BaseExtractor):
    """YouTube 直播提取器"""

    def __init__(self, session, headers=None, config=None):
        super().__init__(session, headers, config)
        self.cache = {}
        self.cache_ttl = int(self.config.get('live_cache_ttl') or Const.LIVE_CACHE_TTL)

    def extract_live(self, url_or_id):
        video_id = self.extract_video_id(url_or_id)
        now = time.time()
        with self._lock:
            cached = self.cache.get(video_id)
        if cached and cached.get('expires', 0) > now:
            return cached.get('data')

        watch_url = f'https://www.youtube.com/watch?v={video_id}'
        page = self._get(watch_url, timeout=90).text

        player_response = self._extract_initial_player_response(page) or {}
        ytcfg = self._extract_ytcfg(page) or {}
        api_key = ytcfg.get('INNERTUBE_API_KEY') or self._search(r'"INNERTUBE_API_KEY":"([^"]+)"', page)
        visitor_data = (
            self.config.get('visitor_data') or ytcfg.get('VISITOR_DATA') or
            (((ytcfg.get('INNERTUBE_CONTEXT') or {}).get('client') or {}).get('visitorData')) or
            ((player_response.get('responseContext') or {}).get('visitorData'))
        )
        if visitor_data and not self.config.get('visitor_data'):
            self.config['visitor_data'] = visitor_data

        status_obj = player_response.get('playabilityStatus') or {}
        streaming = player_response.get('streamingData') or {}
        details = player_response.get('videoDetails') or {}

        page_hls_url = streaming.get('hlsManifestUrl') or ''
        api_data = None
        if api_key:
            api_data = self._call_live_player_api(video_id, api_key, ytcfg, watch_url, visitor_data)
            if api_data:
                api_streaming = api_data.get('streamingData') or {}
                api_details = api_data.get('videoDetails') or {}
                api_hls_url = api_streaming.get('hlsManifestUrl') or ''
                if api_hls_url:
                    streaming = api_streaming
                elif not page_hls_url and api_streaming:
                    streaming = api_streaming
                if api_details:
                    details = api_details
                status_obj = api_data.get('playabilityStatus') or status_obj

        if not (streaming.get('hlsManifestUrl') or '') and page_hls_url:
            streaming = dict(streaming or {})
            streaming['hlsManifestUrl'] = page_hls_url

        hls_url = streaming.get('hlsManifestUrl') or ''
        is_live = bool(details.get('isLive') or hls_url)
        status = status_obj.get('status') or ''
        reason = status_obj.get('reason') or ''
        title = details.get('title') or video_id

        data = {
            'id': video_id,
            'title': title,
            'is_live': is_live,
            'status': status,
            'reason': reason,
            'hls_url': hls_url,
            'duration': int(details.get('lengthSeconds') or 0),
        }
        with self._lock:
            self.cache[video_id] = {'data': data, 'expires': time.time() + self.cache_ttl}
        return data

    def _call_live_player_api(self, video_id, api_key, ytcfg, referer, visitor_data=None):
        for client_info in INNERTUBE_CLIENTS:
            client_name = client_info.get('clientName') or 'ANDROID_VR'
            ctx = {'client': client_info.copy()}
            try:
                url = f'https://www.youtube.com/youtubei/v1/player?key={quote(api_key)}&prettyPrint=false'
                headers = {
                    'Referer': referer,
                    'X-YouTube-Client-Name': str(self._client_name_id(client_name)),
                    'X-YouTube-Client-Version': client_info.get('clientVersion') or '',
                }
                if visitor_data:
                    headers['X-Goog-Visitor-Id'] = visitor_data
                if client_info.get('userAgent'):
                    headers['User-Agent'] = client_info.get('userAgent')

                payload = {
                    'context': ctx,
                    'videoId': video_id,
                    'contentCheckOk': True,
                    'racyCheckOk': True,
                }
                po_token = self._get_po_token(client_name, 'gvs')
                if po_token:
                    payload['serviceIntegrityDimensions'] = {'poToken': po_token}
                data = self._post_json(url, payload, headers=headers)
                streaming = data.get('streamingData') or {}
                if streaming.get('hlsManifestUrl'):
                    data['_client_name'] = client_name
                    return data
            except Exception as e:
                continue
        return None


class Spider(Spider):
    def getName(self):
        return 'YouTube 视频+直播'

    def init(self, extend):
        try:
            self.extendDict = json.loads(extend) if extend else {}
        except Exception:
            self.extendDict = {}
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504, 408, 429],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.keep_alive = False

        # ===== 缓存（带 TTL 和 LRU） =====
        self._cache = {}
        self._cache_lock = threading.Lock()
        self._cache_access = collections.OrderedDict()
        self._max_cache_size = int(self.extendDict.get('max_cache_size', 200))
        self._default_ttl = int(self.extendDict.get('cache_ttl', Const.GENERIC_CACHE_TTL))

        self.search_page_cache = {}
        self.search_page_lock = threading.Lock()
        self.live_search_cache = {}
        self.live_search_lock = threading.Lock()
        self.hls_url_cache = {}
        self.hls_cache_lock = threading.Lock()
        self._hls_key_seq = 0
        self._hls_seq_lock = threading.Lock()

        proxy_config = self.extendDict.get('proxy')
        if proxy_config:
            if isinstance(proxy_config, str):
                proxy_str = proxy_config.strip()
                if proxy_str:
                    if not proxy_str.startswith(('http://', 'https://')):
                        proxy_str = 'http://' + proxy_str
                    self.session.proxies = {'http': proxy_str, 'https': proxy_str}
            elif isinstance(proxy_config, dict):
                proxies = {}
                for k, v in proxy_config.items():
                    if k in ('http', 'https') and v:
                        v_str = v.strip()
                        if v_str:
                            if not v_str.startswith(('http://', 'https://')):
                                v_str = 'http://' + v_str
                            proxies[k] = v_str
                if proxies:
                    self.session.proxies = proxies
                else:
                    self.session.proxies = {}
        else:
            self.session.proxies = {}

        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.youtube.com/'
        }
        self.session.headers.update(self.header)

        self.yt_video = YouTubeLite(self.session, self.header, self.extendDict)
        self.yt_live = YouTubeLiveLite(self.session, self.header, self.extendDict)
        self.hls_proxy_enabled = self.extendDict.get('hls_proxy', True) is not False
        self.mpd_quality_ranking = self.extendDict.get('mpd_quality_ranking', False)

    # ---------- 带 TTL 的缓存方法 ----------
    def setCache(self, key, value, ttl=None):
        if ttl is None:
            ttl = self._default_ttl
        with self._cache_lock:
            self._cache[key] = {
                'data': value,
                'expires': time.time() + ttl
            }
            self._cache_access[key] = time.time()
            self._prune_cache()

    def getCache(self, key):
        with self._cache_lock:
            item = self._cache.get(key)
            if item and item.get('expires', 0) > time.time():
                self._cache_access[key] = time.time()
                return item.get('data')
            elif item:
                self._cache.pop(key, None)
                self._cache_access.pop(key, None)
            return None

    def _prune_cache(self):
        """清理过期和超量缓存（需在锁内调用）"""
        now = time.time()
        expired = [k for k, v in self._cache.items() if v.get('expires', now) < now]
        for k in expired:
            self._cache.pop(k, None)
            self._cache_access.pop(k, None)
        if len(self._cache) > self._max_cache_size:
            sorted_keys = sorted(self._cache_access, key=self._cache_access.get)
            to_remove = sorted_keys[:len(sorted_keys) - self._max_cache_size]
            for k in to_remove:
                self._cache.pop(k, None)
                self._cache_access.pop(k, None)

    # ---------- 搜索缓存（带 TTL） ----------
    def _get_search_cache(self, cache_dict, lock, key):
        with lock:
            item = cache_dict.get(key)
            if item and item.get('expires', 0) > time.time():
                return item.get('data')
            elif item:
                cache_dict.pop(key, None)
            return None

    def _set_search_cache(self, cache_dict, lock, key, value, ttl=Const.SEARCH_CACHE_TTL):
        with lock:
            cache_dict[key] = {
                'data': value,
                'expires': time.time() + ttl
            }
            now = time.time()
            expired = [k for k, v in cache_dict.items() if v.get('expires', now) < now]
            for k in expired:
                cache_dict.pop(k, None)

    # ---------- visitorData 自动提取 ----------
    def _auto_save_visitor_data(self, ytcfg, data=None):
        vd = None
        if ytcfg:
            vd = ytcfg.get('VISITOR_DATA') or \
                 (((ytcfg.get('INNERTUBE_CONTEXT') or {}).get('client') or {}).get('visitorData'))
        if not vd and isinstance(data, dict):
            vd = ((data.get('responseContext') or {}).get('visitorData')) or \
                 ((data.get('client') or {}).get('visitorData'))
        if vd and not self.extendDict.get('visitor_data'):
            self.extendDict['visitor_data'] = vd

    # ---------- 首页 ----------
    def homeContent(self, filter):
        result = {'class': YOUTUBE_CLASSES}
        if filter:
            video_filters = {}
            for c in YOUTUBE_CLASSES:
                cid = c['type_id']
                if cid in CATEGORY_FILTERS:
                    video_filters[cid] = CATEGORY_FILTERS[cid]
            result['filters'] = video_filters
        return result

    def homeVideoContent(self):
        return {'list': []}

    # ---------- 分类 ----------
    def categoryContent(self, cid, page, filter, ext):
        page = int(page or 1)
        filters = ext if isinstance(ext, dict) else {}
        if self._is_live_category(cid):
            keyword = self._build_live_keyword(cid, filters)
            videos, has_more = self._search_live_page(keyword, page)
        else:
            keyword = self._build_video_keyword(cid, filters)
            videos, has_more = self._search_video_page(keyword, page)
        return {
            'list': videos,
            'page': page,
            'pagecount': page + 1 if has_more else page,
            'limit': len(videos),
            'total': len(videos)
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg=1):
        page = int(pg or 1)
        keyword = str(key or '').strip()
        videos_v, _ = self._search_video_page(keyword, page)
        live_keyword = f'{keyword} live' if 'live' not in keyword.lower() and '直播' not in keyword else keyword
        videos_l, _ = self._search_live_page(live_keyword, page)
        seen = set()
        merged = []
        for v in videos_v + videos_l:
            if v['vod_id'] not in seen:
                seen.add(v['vod_id'])
                merged.append(v)
        return {
            'list': merged[:30],
            'page': page,
            'pagecount': page + 1,
            'limit': len(merged),
            'total': len(merged)
        }

    # ---------- 详情 ----------
    def detailContent(self, did):
        video_id = did[0]
        is_live = False
        title = video_id
        status = '视频'
        has_super = False

        try:
            data = self.yt_video.extract(video_id)
            title = data.get('title') or video_id
            is_live = data.get('is_live', False)
            status = '直播中' if is_live else '视频'

            if not is_live:
                formats = data.get('formats') or []
                all_videos = [x for x in formats if x.get('vcodec') != 'none' and x.get('acodec') == 'none']
                high_res = [x for x in all_videos if int(x.get('height') or 0) >= 720]
                has_super = len(high_res) > 0
        except Exception as e:
            is_live = False
            title = self._get_video_title(video_id) or video_id
            status = '视频'

        related = []
        try:
            r = self.session.get(f'https://www.youtube.com/watch?v={video_id}', timeout=90)
            related = self._extract_videos_fixed(r.text, 20)
            ytcfg = self.yt_video._extract_ytcfg(r.text) or {}
            self._auto_save_visitor_data(ytcfg)
        except Exception:
            pass

        safe_title = self._safe_title(title)

        play_sources = []
        play_urls = []

        if is_live:
            play_sources.append('直播')
            play_urls.append(f'{safe_title}${video_id}@{Const.QUALITY_LIVE}')
        else:
            if has_super:
                play_sources.append('极客VP')
                play_urls.append(f'{safe_title}${video_id}@{Const.QUALITY_SUPER}')

            play_sources.append('万能MP')
            play_urls.append(f'{safe_title}${video_id}@{Const.QUALITY_NORMAL}')

        if related:
            play_sources.append('相关推荐')
            play_url2 = '#'.join([f"{self._safe_title(v['vod_name'])}${v['vod_id']}@{Const.QUALITY_NORMAL}" for v in related if v.get('vod_id') != video_id])
            play_urls.append(play_url2)

        vod = {
            'vod_id': video_id,
            'vod_name': title,
            'vod_pic': f'{Const.PROXY_BASE}?do=py&type=image&vid={video_id}',
            'vod_remarks': status,
            'vod_play_from': '$$$'.join(play_sources),
            'vod_play_url': '$$$'.join(play_urls)
        }
        return {'list': [vod]}

    # ---------- 播放 ----------
    def playerContent(self, flag, pid, vipFlags):
        raw_pid = pid.split('$')[-1]
        if '@' in raw_pid:
            video_id, quality_or_type = raw_pid.rsplit('@', 1)
        else:
            video_id, quality_or_type = raw_pid, Const.QUALITY_SUPER

        if quality_or_type == Const.QUALITY_LIVE:
            return self._play_live(video_id)
        else:
            return self._play_video(video_id, quality_or_type)

    # ---------- 私有辅助 ----------
    def _is_live_category(self, cid):
        return 'live' in cid.lower() or '直播' in cid.lower()

    def _build_live_keyword(self, cid, filters=None):
        terms = [cid]
        if isinstance(filters, dict):
            for value in filters.values():
                term = self._normalize_filter_term(value)
                if term:
                    terms.append(term)
        keyword = ' '.join(terms).strip()
        if 'live' not in keyword.lower() and '直播' not in keyword:
            keyword = f'{keyword} live'
        return keyword

    def _build_video_keyword(self, cid, filters=None):
        if cid.startswith('LIST:'):
            raw = cid[5:].strip()
            channels = [ch.strip() for ch in raw.split(',') if ch.strip()]
            terms = []
            for ch in channels:
                if ch.startswith('@'):
                    terms.append(f'channel:{ch}')
                else:
                    terms.append(f'"{ch}"')
            keyword = ' OR '.join(terms) if terms else ''
        else:
            keyword = cid
        if isinstance(filters, dict):
            for value in filters.values():
                term = self._normalize_filter_term(value)
                if term:
                    keyword += ' ' + term
        return keyword.strip()

    def _normalize_filter_term(self, value):
        if isinstance(value, (list, tuple)):
            return ' '.join([self._normalize_filter_term(item) for item in value if item])
        if isinstance(value, dict):
            return ' '.join([self._normalize_filter_term(item) for item in value.values() if item])
        return re.sub(r'\s+', ' ', str(value or '')).strip()[:180]

    def _search_cache_key(self, key):
        return re.sub(r'\s+', ' ', str(key or '')).strip().lower()

    # ---------- 视频搜索 ----------
    def _search_video_page(self, key, page=1):
        page = max(1, int(page or 1))
        cache_key = self._search_cache_key(key)
        session = self._get_search_cache(self.search_page_cache, self.search_page_lock, cache_key)
        if page == 1 or not session:
            session = self._fetch_search_first_page(key)
            self._set_search_cache(self.search_page_cache, self.search_page_lock, cache_key, session)
        while len(session.get('pages', [])) < page and session.get('next'):
            data = self._fetch_search_continuation(session)
            videos = self._extract_videos_from_api(data, 30)
            session.setdefault('pages', []).append(videos)
            session['next'] = self._extract_continuation_token(data)
        pages = session.get('pages', [])
        videos = pages[page - 1] if len(pages) >= page else []
        has_more = bool(session.get('next')) or len(pages) > page
        return videos, has_more

    def _fetch_search_first_page(self, key):
        search_url = f'https://www.youtube.com/results?search_query={quote(str(key or ""))}'
        r = self.session.get(search_url, timeout=90)
        html_str = r.text
        data = self.yt_video._extract_json_after(html_str, 'ytInitialData') or {}
        ytcfg = self.yt_video._extract_ytcfg(html_str) or {}
        self._auto_save_visitor_data(ytcfg, data)
        api_key = ytcfg.get('INNERTUBE_API_KEY') or self.yt_video._search(r'"INNERTUBE_API_KEY":"([^"]+)"', html_str)
        context = ytcfg.get('INNERTUBE_CONTEXT') or {'client': {'clientName': 'WEB', 'clientVersion': '2.20240310.01.00', 'hl': 'zh-CN', 'gl': 'US'}}
        client = context.get('client') or {}
        return {
            'key': key,
            'api_key': api_key,
            'context': context,
            'client_name': client.get('clientName') or 'WEB',
            'client_version': client.get('clientVersion') or '2.20240310.01.00',
            'referer': search_url,
            'pages': [self._extract_videos_from_api(data, 30)],
            'next': self._extract_continuation_token(data),
        }

    # ---------- 直播搜索 ----------
    def _search_live_page(self, key, page=1):
        page = max(1, int(page or 1))
        cache_key = f'live_{self._search_cache_key(key)}'
        session = self._get_search_cache(self.live_search_cache, self.live_search_lock, cache_key)
        if page == 1 or not session:
            session = self._fetch_live_search_first_page(key)
            self._set_search_cache(self.live_search_cache, self.live_search_lock, cache_key, session)
        while len(session.get('pages', [])) < page and session.get('next'):
            data = self._fetch_search_continuation(session)
            videos = self._extract_live_videos_from_api(data, 30)
            session.setdefault('pages', []).append(videos)
            session['next'] = self._extract_continuation_token(data)
        pages = session.get('pages', [])
        videos = pages[page - 1] if len(pages) >= page else []
        has_more = bool(session.get('next')) or len(pages) > page
        return videos, has_more

    def _fetch_live_search_first_page(self, key):
        search_url = f'https://www.youtube.com/results?search_query={quote(str(key or ""))}&sp=EgJAAQ%253D%253D'
        r = self.session.get(search_url, timeout=90)
        html_str = r.text
        data = self.yt_video._extract_json_after(html_str, 'ytInitialData') or {}
        ytcfg = self.yt_video._extract_ytcfg(html_str) or {}
        self._auto_save_visitor_data(ytcfg, data)
        api_key = ytcfg.get('INNERTUBE_API_KEY') or self.yt_video._search(r'"INNERTUBE_API_KEY":"([^"]+)"', html_str)
        context = ytcfg.get('INNERTUBE_CONTEXT') or {'client': {'clientName': 'WEB', 'clientVersion': '2.20240310.01.00', 'hl': 'zh-CN', 'gl': 'US'}}
        client = context.get('client') or {}
        return {
            'key': key,
            'api_key': api_key,
            'context': context,
            'client_name': client.get('clientName') or 'WEB',
            'client_version': client.get('clientVersion') or '2.20240310.01.00',
            'referer': search_url,
            'pages': [self._extract_live_videos_from_api(data, 30)],
            'next': self._extract_continuation_token(data),
        }

    # ---------- 续页 ----------
    def _fetch_search_continuation(self, session):
        token = session.get('next')
        api_key = session.get('api_key')
        if not token or not api_key:
            return {}
        url = f'https://www.youtube.com/youtubei/v1/search?key={quote(api_key)}'
        headers = self.header.copy()
        headers.update({
            'Content-Type': 'application/json',
            'Origin': 'https://www.youtube.com',
            'Referer': session.get('referer') or 'https://www.youtube.com/',
            'X-YouTube-Client-Name': str(self.yt_video._client_name_id(session.get('client_name'))),
            'X-YouTube-Client-Version': session.get('client_version') or '2.20240310.01.00',
        })
        payload = {'context': session.get('context') or {}, 'continuation': token}
        try:
            r = self.session.post(url, json=payload, headers=headers, timeout=90)
            r.raise_for_status()
            data = r.json()
            self._auto_save_visitor_data(None, data)
            return data
        except Exception as e:
            return {}

    # ---------- 提取视频列表 ----------
    def _extract_continuation_token(self, data):
        tokens = []
        def scan(obj):
            if isinstance(obj, dict):
                endpoint = obj.get('continuationEndpoint') or {}
                token = endpoint.get('continuationCommand', {}).get('token')
                if token:
                    tokens.append(token)
                renderer = obj.get('continuationItemRenderer') or {}
                token = renderer.get('continuationEndpoint', {}).get('continuationCommand', {}).get('token')
                if token:
                    tokens.append(token)
                for value in obj.values():
                    scan(value)
            elif isinstance(obj, list):
                for value in obj:
                    scan(value)
        scan(data)
        return tokens[0] if tokens else ''

    def _extract_videos_from_api(self, data, limit=30):
        videos = []
        seen = set()
        def scan(obj):
            if len(videos) >= limit:
                return
            if isinstance(obj, dict):
                for key in ('videoRenderer', 'compactVideoRenderer', 'gridVideoRenderer'):
                    if key in obj:
                        item = self._parse_renderer(obj[key], is_live=False)
                        if item and item['vod_id'] not in seen:
                            seen.add(item['vod_id'])
                            videos.append(item)
                for value in obj.values():
                    scan(value)
            elif isinstance(obj, list):
                for value in obj:
                    scan(value)
        scan(data)
        return videos[:limit]

    def _extract_live_videos_from_api(self, data, limit=30):
        videos = []
        seen = set()
        def scan(obj):
            if len(videos) >= limit:
                return
            if isinstance(obj, dict):
                for key in ('videoRenderer', 'compactVideoRenderer', 'gridVideoRenderer'):
                    if key in obj:
                        item = self._parse_renderer(obj[key], is_live=True)
                        if item and item['vod_id'] not in seen:
                            seen.add(item['vod_id'])
                            videos.append(item)
                for value in obj.values():
                    scan(value)
            elif isinstance(obj, list):
                for value in obj:
                    scan(value)
        scan(data)
        return videos[:limit]

    def _parse_renderer(self, renderer, is_live=False):
        try:
            vid = renderer.get('videoId')
            if not vid:
                nav = renderer.get('navigationEndpoint') or {}
                vid = (nav.get('watchEndpoint') or {}).get('videoId')
            if not vid:
                return None

            is_actually_live = False
            badges = renderer.get('badges', [])
            for badge in badges:
                if isinstance(badge, dict):
                    text = badge.get('text', '') or badge.get('label', '') or ''
                    if '直播' in text or 'LIVE' in text.upper():
                        is_actually_live = True
                        break
            if not is_live and is_actually_live:
                return None

            title_obj = renderer.get('title') or renderer.get('headline') or {}
            title = title_obj.get('simpleText') or ''.join([x.get('text', '') for x in title_obj.get('runs', [])]) or 'YouTube Video'
            dur = ''
            if not is_actually_live:
                dur_obj = renderer.get('lengthText') or {}
                dur = dur_obj.get('simpleText') or ''
            remarks = '直播' if is_actually_live else (dur if dur else '视频')

            return {
                'vod_id': vid,
                'vod_name': html.unescape(title),
                'vod_pic': f'{Const.PROXY_BASE}?do=py&type=image&vid={vid}',
                'vod_remarks': remarks
            }
        except Exception as e:
            return None

    def _extract_videos_fixed(self, html_str, limit=30):
        data = None
        match = re.search(r'var ytInitialData = (\{.*?\});', html_str)
        if match:
            try:
                data = json.loads(match.group(1))
            except Exception:
                pass
        if not data:
            return []
        return self._extract_videos_from_api(data, limit)

    def _get_video_title(self, vid):
        try:
            r = self.session.get(f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json', timeout=30)
            return r.json().get('title') or vid
        except Exception:
            return vid

    def _safe_title(self, title):
        if not title:
            return 'video'
        return re.sub(r'[#$@%&!?*|\\/:<>]', ' ', title)[:60]

    # ==================== 播放核心（原始稳定逻辑，完全未改动） ====================
    def _play_video(self, video_id, quality):
        try:
            data = self.yt_video.extract(video_id)
            formats = data.get('formats') or []

            all_videos = [x for x in formats if x.get('vcodec') != 'none' and x.get('acodec') == 'none']
            if not all_videos:
                all_videos = [x for x in formats if x.get('vcodec') != 'none']

            def filter_and_sort(videos):
                high = [v for v in videos if int(v.get('height') or 0) >= 720]
                candidates = high if high else videos
                candidates.sort(key=lambda x: (int(x.get('height') or 0), int(x.get('bitrate') or 0)), reverse=True)
                seen_res = {}
                result = []
                for v in candidates:
                    h = int(v.get('height') or 0)
                    if h not in seen_res:
                        seen_res[h] = True
                        result.append(v)
                return result

            def is_av1_or_vp9(codecs):
                return 'av01' in codecs or 'vp9' in codecs

            def is_h264(codecs):
                return 'avc' in codecs or 'h264' in codecs

            if quality == Const.QUALITY_SUPER:
                av1_vp9 = [v for v in all_videos if is_av1_or_vp9(v.get('codecs', ''))]
                if av1_vp9:
                    target_videos = filter_and_sort(av1_vp9)
                else:
                    webm = [v for v in all_videos if v.get('ext') == 'webm']
                    target_videos = filter_and_sort(webm) if webm else filter_and_sort(all_videos)
            else:
                h264 = [v for v in all_videos if is_h264(v.get('codecs', ''))]
                if h264:
                    target_videos = filter_and_sort(h264)
                else:
                    mp4 = [v for v in all_videos if v.get('ext') == 'mp4']
                    target_videos = filter_and_sort(mp4) if mp4 else filter_and_sort(all_videos)

            if target_videos and not all(v.get('initRange') and v.get('indexRange') for v in target_videos):
                range_videos = [v for v in all_videos if v.get('initRange') and v.get('indexRange')]
                if range_videos:
                    range_videos.sort(key=lambda x: (int(x.get('height') or 0), int(x.get('bitrate') or 0)), reverse=True)
                    seen_res = {}
                    final = []
                    for v in range_videos:
                        h = int(v.get('height') or 0)
                        if h not in seen_res:
                            seen_res[h] = True
                            final.append(v)
                    target_videos = final

            if not target_videos:
                all_videos.sort(key=lambda x: (int(x.get('height') or 0), int(x.get('bitrate') or 0)), reverse=True)
                seen = set()
                for v in all_videos:
                    h = int(v.get('height') or 0)
                    if h not in seen:
                        seen.add(h)
                        target_videos.append(v)
                        if len(target_videos) >= 3:
                            break

            if not target_videos:
                raise Exception('未获取到可用视频流')

            audio_candidates = [x for x in formats if x.get('acodec') != 'none' and x.get('vcodec') == 'none']
            if not audio_candidates:
                audio_candidates = [x for x in formats if x.get('acodec') != 'none']
            audio_candidates.sort(
                key=lambda x: (1 if x.get('ext') == 'mp4' else 0, int(x.get('bitrate') or 0)),
                reverse=True
            )
            audio = audio_candidates[0] if audio_candidates else None

            cache_key = f'yt_{video_id}_{quality}'
            all_cached = {}
            for v in target_videos:
                all_cached[str(v.get('itag'))] = v
            if audio:
                all_cached[str(audio.get('itag'))] = audio

            self.setCache(cache_key, {
                'target_videos': target_videos,
                'audio_item': audio,
                'all_by_itag': all_cached,
                'duration': data.get('duration') or 0,
            }, ttl=Const.MPD_CACHE_TTL)

            return {
                'parse': 0, 'jx': 0,
                'url': f'{Const.PROXY_BASE}?do=py&type=mpd&vid={video_id}&quality={quality}',
                'format': 'application/dash+xml'
            }
        except Exception as e:
            return {
                'parse': 1,
                'url': f'https://www.youtube.com/embed/{video_id}?autoplay=1',
                'header': json.dumps(self.header)
            }

    # ==================== MPD 生成（原始稳定逻辑） ====================
    def _proxy_mpd(self, params):
        vid = params.get('vid')
        quality = params.get('quality') or Const.QUALITY_SUPER
        data = self.getCache(f'yt_{vid}_{quality}') if vid else None
        if not data:
            return [404, 'text/plain', '视频缓存已过期或不存在']

        target_videos = data.get('target_videos') or []
        audio_item = data.get('audio_item') or {}
        duration = data.get('duration') or 0
        duration_pt = f"PT{int(duration)}S"
        media_base = f'{Const.PROXY_BASE}?do=py&type=media&vid={vid}&quality={quality}'

        def build_video_repr(item, rank):
            itag = item.get('itag', 0)
            init = item.get('initRange') or {}
            index = item.get('indexRange') or {}
            qr_attr = f' qualityRanking="{rank}"' if self.mpd_quality_ranking else ''
            lines = [
                f'        <Representation id="v{itag}" bandwidth="{item.get("bitrate", 1000000)}" '
                f'codecs="{html.escape(item.get("codecs") or "")}" '
                f'height="{item.get("height", 0)}" width="{item.get("width", 0)}" '
                f'frameRate="{item.get("fps", 30)}"{qr_attr}>',
                f'          <BaseURL>{html.escape(media_base + f"&itag={itag}&track=video")}</BaseURL>',
                f'          <SegmentBase indexRange="{index.get("start", "0")}-{index.get("end", "0")}">'
                f'<Initialization range="{init.get("start", "0")}-{init.get("end", "0")}"/></SegmentBase>',
                f'        </Representation>'
            ]
            return '\n'.join(lines)

        mpd_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" '
            f'mediaPresentationDuration="{duration_pt}" minBufferTime="PT4S" '
            'profiles="urn:mpeg:dash:profile:isoff-on-demand:2011">',
            '  <Period id="1" start="PT0S">'
        ]

        if target_videos:
            mime_groups = {}
            for v in target_videos:
                mime_type = "video/webm" if v.get('ext') == 'webm' else "video/mp4"
                mime_groups.setdefault(mime_type, []).append(v)

            for mime_type, videos in mime_groups.items():
                videos.sort(key=lambda x: int(x.get('height') or 0), reverse=True)
                max_height = videos[0].get('height', 0) if videos else 0
                mpd_lines.append(f'    <AdaptationSet mimeType="{mime_type}" startWithSAP="1" segmentAlignment="true" scanType="progressive">')
                mpd_lines.append(f'      <Label>{max_height}p 自适应</Label>')
                for rank, v in enumerate(videos, 1):
                    mpd_lines.append(build_video_repr(v, rank))
                mpd_lines.append('    </AdaptationSet>')

        if audio_item:
            audio_itag = audio_item.get('itag', 0)
            audio_init = audio_item.get('initRange') or {}
            audio_index = audio_item.get('indexRange') or {}
            audio_mime = (audio_item.get('mimeType') or 'audio/mp4').split(';')[0]
            mpd_lines.append(f'    <AdaptationSet mimeType="{html.escape(audio_mime)}" startWithSAP="1" segmentAlignment="true" lang="und">')
            mpd_lines.append(f'      <Representation id="a{audio_itag}" bandwidth="{audio_item.get("bitrate", 128000)}" '
                           f'codecs="{html.escape(audio_item.get("codecs") or "")}" audioSamplingRate="44100">')
            mpd_lines.append(f'        <BaseURL>{html.escape(media_base + f"&itag={audio_itag}&track=audio")}</BaseURL>')
            mpd_lines.append(f'        <SegmentBase indexRange="{audio_index.get("start", "0")}-{audio_index.get("end", "0")}">'
                           f'<Initialization range="{audio_init.get("start", "0")}-{audio_init.get("end", "0")}"/></SegmentBase>')
            mpd_lines.append('      </Representation>')
            mpd_lines.append('    </AdaptationSet>')

        mpd_lines.append('  </Period>')
        mpd_lines.append('</MPD>')
        mpd = '\n'.join(mpd_lines)
        return [200, 'application/dash+xml', mpd]

    # ==================== 流式代理（原始稳定逻辑，仅增加分块读取降低内存） ====================
    def _proxy_media(self, params):
        vid = params.get('vid')
        quality = params.get('quality') or Const.QUALITY_SUPER
        itag = params.get('itag')
        track = params.get('track')
        data = self.getCache(f'yt_{vid}_{quality}') if vid else None
        if not data:
            return [404, 'text/plain', '媒体缓存不存在或已过期']

        all_by_itag = data.get('all_by_itag') or {}
        media_item = None

        if itag and str(itag) in all_by_itag:
            media_item = all_by_itag[str(itag)]
        elif track == 'audio':
            media_item = data.get('audio_item')

        if not media_item:
            return [404, 'text/plain', f'流不存在 (itag={itag})']

        target_url = media_item.get('url')
        if not target_url:
            return [404, 'text/plain', '播放地址不存在']

        headers = self.header.copy()
        headers.update(media_item.get('headers') or {})
        # 兼容 FongMi 可能传的各种 Range 参数名
        range_header = (params.get('range') or params.get('Range') or params.get('range_header')
                        or params.get('http_range') or params.get('RangeHeader'))
        # 有些版本可能分拆传 start/end
        if not range_header:
            start = params.get('start') or params.get('range_start')
            end = params.get('end') or params.get('range_end')
            if start is not None:
                range_header = f'bytes={start}-' + (str(end) if end is not None else '')
        if range_header:
            headers['Range'] = range_header

        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                r = self.session.get(target_url, headers=headers, stream=True, timeout=120)
                if r.status_code in (403, 404) and attempt < max_retries:
                    try:
                        fresh_data = self.yt_video.extract(vid)
                        fresh_formats = fresh_data.get('formats', [])
                        fresh_item = None
                        for f in fresh_formats:
                            if str(f.get('itag')) == str(itag):
                                fresh_item = f
                                break
                        if fresh_item and fresh_item.get('url'):
                            media_item['url'] = fresh_item['url']
                            target_url = fresh_item['url']
                            all_by_itag[str(itag)] = fresh_item
                            data['all_by_itag'] = all_by_itag
                            self.setCache(f'yt_{vid}_{quality}', data, ttl=Const.MPD_CACHE_TTL)
                            continue
                    except Exception:
                        time.sleep(1)
                        continue
                content_type = r.headers.get('content-type', 'application/octet-stream')
                # 解析请求的 Range
                req_start = 0
                req_end = None
                if range_header and range_header.startswith('bytes='):
                    range_spec = range_header[6:]
                    if '-' in range_spec:
                        start_str, end_str = range_spec.split('-', 1)
                        if start_str:
                            req_start = int(start_str)
                        if end_str:
                            req_end = int(end_str)

                # 分块读取
                chunks = []
                for chunk in r.iter_content(chunk_size=65536):
                    chunks.append(chunk)
                content = b''.join(chunks)

                # 若上游返回全量(200)但我们请求了Range，按Range切片
                if range_header and r.status_code == 200 and (req_start > 0 or req_end is not None):
                    full_len = len(content)
                    end_pos = req_end + 1 if req_end is not None else full_len
                    if req_start < full_len:
                        content = content[req_start:min(end_pos, full_len)]
                        # 修正响应头：Content-Range 的 total 必须是原始全量长度
                        resp_headers = {
                            'Content-Type': content_type,
                            'Accept-Ranges': 'bytes',
                            'Cache-Control': 'no-cache',
                            'Content-Range': f'bytes {req_start}-{req_start + len(content) - 1}/{full_len}',
                            'Content-Length': str(len(content)),
                        }
                        return [206, content_type, content, resp_headers]

                resp_headers = {
                    'Content-Type': content_type,
                    'Accept-Ranges': 'bytes',
                    'Cache-Control': 'no-cache',
                }
                if r.headers.get('content-range'):
                    resp_headers['Content-Range'] = r.headers.get('content-range')
                if r.headers.get('content-length'):
                    resp_headers['Content-Length'] = r.headers.get('content-length')
                return [r.status_code, content_type, content, resp_headers]
            except Exception as e:
                if attempt == max_retries:
                    return [500, 'text/plain', f'代理媒体失败: {str(e)}']
                time.sleep(1)
        return [500, 'text/plain', '代理媒体失败']

    def _proxy_single(self, params):
        vid = params.get('vid')
        data = self.getCache(f'yt_single_{vid}') if vid else None
        if not data:
            return [404, 'text/plain', '播放缓存已过期或不存在']
        target_url = data.get('url')
        if not target_url:
            return [404, 'text/plain', '播放地址不存在']
        headers = (data.get('headers') or self.header).copy()
        # 兼容 FongMi 可能传的各种 Range 参数名
        range_header = (params.get('range') or params.get('Range') or params.get('range_header')
                        or params.get('http_range') or params.get('RangeHeader'))
        if not range_header:
            start = params.get('start') or params.get('range_start')
            end = params.get('end') or params.get('range_end')
            if start is not None:
                range_header = f'bytes={start}-' + (str(end) if end is not None else '')
        if range_header:
            headers['Range'] = range_header
        try:
            r = self.session.get(target_url, headers=headers, stream=True, timeout=120)
            content_type = r.headers.get('content-type', 'video/mp4')
            resp_headers = {
                'Content-Type': content_type,
                'Accept-Ranges': 'bytes',
                'Cache-Control': 'no-cache',
            }
            if r.headers.get('content-range'):
                resp_headers['Content-Range'] = r.headers.get('content-range')
            if r.headers.get('content-length'):
                resp_headers['Content-Length'] = r.headers.get('content-length')
            # 解析请求的 Range
            req_start = 0
            req_end = None
            if range_header and range_header.startswith('bytes='):
                range_spec = range_header[6:]
                if '-' in range_spec:
                    start_str, end_str = range_spec.split('-', 1)
                    if start_str:
                        req_start = int(start_str)
                    if end_str:
                        req_end = int(end_str)

            # 分块读取
            chunks = []
            for chunk in r.iter_content(chunk_size=65536):
                chunks.append(chunk)
            content = b''.join(chunks)

            # 若上游返回全量(200)但我们请求了Range，按Range切片
            if range_header and r.status_code == 200 and (req_start > 0 or req_end is not None):
                full_len = len(content)
                end_pos = req_end + 1 if req_end is not None else full_len
                if req_start < full_len:
                    content = content[req_start:min(end_pos, full_len)]
                    resp_headers = {
                        'Content-Type': content_type,
                        'Accept-Ranges': 'bytes',
                        'Cache-Control': 'no-cache',
                        'Content-Range': f'bytes {req_start}-{req_start + len(content) - 1}/{full_len}',
                        'Content-Length': str(len(content)),
                    }
                    return [206, content_type, content, resp_headers]

            return [r.status_code, content_type, content, resp_headers]
        except Exception as e:
            return [500, 'text/plain', '代理播放失败']

    # ---------- 直播 ----------
    def _play_live(self, video_id):
        try:
            data = self.yt_live.extract_live(video_id)
            hls_url = data.get('hls_url') or ''
            if not hls_url:
                raise Exception(data.get('reason') or '未获取到直播 HLS 地址')
            if self.extendDict.get('hls_probe'):
                self._probe_hls(video_id, hls_url)
            play_url = hls_url
            if self.hls_proxy_enabled:
                play_url = self._cache_hls_url(hls_url, video_id, 'master')
            return {
                'parse': 0,
                'jx': 0,
                'url': play_url,
                'header': self.header,
                'format': 'application/x-mpegURL'
            }
        except Exception as e:
            return {'parse': 1, 'jx': 1, 'url': f'https://www.youtube.com/embed/{video_id}?autoplay=1'}

    def _probe_hls(self, video_id, hls_url):
        try:
            response = self.session.get(hls_url, headers=self.header, timeout=120)
            full_text = response.text or ''
            variant_url = self._pick_variant_playlist(hls_url, full_text)
            if variant_url:
                self.session.get(variant_url, headers=self.header, timeout=120)
        except Exception:
            pass

    def _pick_variant_playlist(self, base_url, text):
        lines = [line.strip() for line in (text or '').splitlines()]
        best_score = -1
        best_url = ''
        for index, line in enumerate(lines):
            if not line.startswith('#EXT-X-STREAM-INF'):
                continue
            score = 0
            bandwidth = re.search(r'BANDWIDTH=(\d+)', line)
            resolution = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
            if bandwidth:
                score += int(bandwidth.group(1))
            if resolution:
                score += int(resolution.group(1)) * int(resolution.group(2))
            for next_line in lines[index + 1:]:
                if not next_line or next_line.startswith('#'):
                    continue
                if score > best_score:
                    best_score = score
                    best_url = urljoin(base_url, next_line)
                break
        return best_url

    HLS_TTL = {
        'master': Const.HLS_MASTER_TTL,
        'playlist': Const.HLS_PLAYLIST_TTL,
        'media': Const.HLS_MEDIA_TTL,
        'media_retry': Const.HLS_MEDIA_TTL
    }

    def _hls_ttl(self, kind):
        return self.HLS_TTL.get(kind, 180)

    def _prune_hls_cache(self):
        now = time.time()
        with self.hls_cache_lock:
            expired = [k for k, v in self.hls_url_cache.items() if v.get('expires', 0) < now]
            for k in expired:
                self.hls_url_cache.pop(k, None)

    def _cache_hls_url(self, target_url, video_id='', kind='media'):
        self._prune_hls_cache()
        with self._hls_seq_lock:
            self._hls_key_seq += 1
            seq = self._hls_key_seq
        key = f'{int(time.time() * 1000)}_{seq}'
        with self.hls_cache_lock:
            self.hls_url_cache[key] = {
                'url': target_url,
                'video_id': video_id,
                'kind': kind,
                'expires': time.time() + self._hls_ttl(kind),
            }
        return f'{Const.PROXY_BASE}?do=py&type=hls&key={quote(key)}'

    def _hls_headers(self, target_url, kind=None):
        if kind == 'media_retry':
            return {
                'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 14) gzip',
                'Accept': '*/*',
            }
        headers = self.header.copy()
        headers['Accept'] = '*/*'
        if kind in ('master', 'playlist'):
            headers['Origin'] = 'https://www.youtube.com'
            headers['Referer'] = 'https://www.youtube.com/'
        elif kind == 'media':
            headers['User-Agent'] = 'com.google.android.youtube/19.09.37 (Linux; U; Android 14) gzip'
            headers.pop('Origin', None)
            headers.pop('Referer', None)
        return headers

    def _rewrite_m3u8(self, text, base_url, video_id=''):
        output = []
        for line in (text or '').splitlines():
            stripped = line.strip()
            if not stripped:
                output.append(line)
                continue
            if stripped.startswith('#'):
                output.append(self._rewrite_m3u8_tag(line, base_url, video_id))
                continue
            is_playlist = stripped.endswith('.m3u8') or '/hls_playlist/' in stripped
            kind = 'playlist' if is_playlist else 'media'
            absolute = urljoin(base_url, stripped)
            output.append(self._cache_hls_url(absolute, video_id, kind))
        return '\n'.join(output) + '\n'

    def _rewrite_m3u8_tag(self, line, base_url, video_id=''):
        def replace_uri(match):
            raw_url = match.group(1)
            absolute = urljoin(base_url, raw_url)
            is_playlist = raw_url.endswith('.m3u8') or '/hls_playlist/' in raw_url
            kind = 'playlist' if is_playlist else 'media'
            proxied = self._cache_hls_url(absolute, video_id, kind)
            return f'URI="{proxied}"'
        return re.sub(r'URI="([^"]+)"', replace_uri, line)

    def _proxy_hls(self, params):
        key = params.get('key') or ''
        with self.hls_cache_lock:
            item = self.hls_url_cache.get(key)
        if not item or item.get('expires', 0) < time.time():
            return [404, 'text/plain', 'HLS 缓存已过期']
        with self.hls_cache_lock:
            item['expires'] = time.time() + self._hls_ttl(item.get('kind'))
        target_url = item.get('url') or ''
        video_id = item.get('video_id', '')

        try:
            headers = self._hls_headers(target_url, item.get('kind'))
            max_retries = 3
            for attempt in range(max_retries + 1):
                try:
                    response = self.session.get(target_url, headers=headers, stream=True, timeout=120)
                    if response.status_code in (403, 404) and attempt < max_retries:
                        if video_id and item.get('kind') in ('master', 'playlist'):
                            try:
                                live_data = self.yt_live.extract_live(video_id)
                                new_hls = live_data.get('hls_url')
                                if new_hls:
                                    with self.hls_cache_lock:
                                        item['url'] = new_hls
                                    target_url = new_hls
                                    continue
                            except Exception:
                                time.sleep(1)
                                continue
                        content_type = response.headers.get('content-type') or ''
                    is_m3u8 = item.get('kind') in ('master', 'playlist') or 'mpegurl' in content_type.lower() or target_url.split('?')[0].endswith('.m3u8')
                    if is_m3u8:
                        text = response.text
                        rewritten = self._rewrite_m3u8(text, target_url, video_id)
                        return [response.status_code, 'application/vnd.apple.mpegurl', rewritten, {'Content-Type': 'application/vnd.apple.mpegurl', 'Cache-Control': 'no-cache'}]
                    resp_headers = {'Content-Type': content_type or 'application/octet-stream', 'Cache-Control': 'no-cache'}
                    if response.headers.get('content-length'):
                        resp_headers['Content-Length'] = response.headers.get('content-length')
                    chunks = []
                    for chunk in response.iter_content(chunk_size=65536):
                        chunks.append(chunk)
                    content = b''.join(chunks)
                    return [response.status_code, content_type or 'application/octet-stream', content, resp_headers]
                except Exception as e:
                    if attempt == max_retries:
                        raise
                    time.sleep(1)
        except Exception as e:
            return [500, 'text/plain', f'HLS 代理失败: {str(e)}']
        return [500, 'text/plain', 'HLS 代理失败']

    # ---------- localProxy ----------
    def localProxy(self, params):
        if params.get('do') != 'py':
            return None
        typ = params.get('type')
        if typ == 'mpd':
            return self._proxy_mpd(params)
        if typ == 'media':
            return self._proxy_media(params)
        if typ == 'single':
            return self._proxy_single(params)
        if typ == 'image':
            return self._proxy_image(params)
        if typ == 'hls':
            return self._proxy_hls(params)
        return None

    def _proxy_image(self, params):
        vid = params.get('vid')
        if not vid:
            return [400, 'text/plain', '缺少 video id']
        quality = params.get('quality', 'hqdefault')
        img_url = f'https://i.ytimg.com/vi/{vid}/{quality}.jpg'
        try:
            r = self.session.get(img_url, timeout=30)
            if r.status_code == 200:
                content_type = r.headers.get('content-type', 'image/jpeg')
                return [200, content_type, r.content, {'Cache-Control': 'max-age=86400'}]
            else:
                return [404, 'text/plain', f'图片不存在 ({r.status_code})']
        except Exception as e:
            return [500, 'text/plain', '代理图片失败']

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass
