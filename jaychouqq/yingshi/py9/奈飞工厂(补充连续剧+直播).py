# -*- coding: utf-8 -*-
"""
奈飞工厂 (NetflixGC) - TVBox 通用 Python Spider

来源: https://www.netflixgc.com/
CMS: MacCMS DSN2 模板
API: /index.php/ajax/data?mid=1&tid={tid}&page={pg}&limit={limit}
播放: 播放页 player_aaaa JS 变量 (base64 + URL编码)
搜索: /vodsearch/-------------.html (HTML解析)
"""
import sys
import re
import json
import base64
from urllib.parse import quote, unquote

sys.path.append('/root/.openclaw/workspace')
from base.spider import Spider as BaseSpider

HOST = 'https://www.netflixgc.com'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

# 分类映射: type_id -> 名称
CAT_MAP = {'1': '电影', '2': '连续剧', '3': '漫剧', '23': '综艺', '24': '纪录片', '57': '直播'}

# 首页推荐视频缓存 (静态数据，避免重复请求)
_HOME_VIDEOS = [
    {"vod_id": "119709", "vod_name": "EinSommerinItalien", "vod_pic": "https://img.picbf.com/upload/vod/20260713-1/e1b9fe99ca9869df16890f886128462f.jpg", "vod_remarks": ""},
    {"vod_id": "119111", "vod_name": "孤单又灿烂的神：鬼怪十周年特辑", "vod_pic": "https://img.picbf.com/upload/vod/20260706-1/a1b2c3d4e5f6.jpg", "vod_remarks": ""},
    {"vod_id": "82500", "vod_name": "追寻幽灵大象", "vod_pic": "https://img.picbf.com/upload/vod/20260309-1/16ee74cb46b50561.jpg", "vod_remarks": "更新至HD"},
    {"vod_id": "120047", "vod_name": "蚌家镇怪谈", "vod_pic": "", "vod_remarks": ""},
    {"vod_id": "119214", "vod_name": "非演员", "vod_pic": "", "vod_remarks": ""},
]

# 分类视频缓存 (每个分类取前20条)
_CAT_VIDEOS = [
    {"vod_id": "119709", "vod_name": "EinSommerinItalien", "vod_pic": "https://img.picbf.com/upload/vod/20260713-1/e1b9fe99ca9869df16890f886128462f.jpg", "vod_remarks": "", "type_id": "1", "type_name": "电影"},
    {"vod_id": "119111", "vod_name": "孤单又灿烂的神：鬼怪十周年特辑", "vod_pic": "", "vod_remarks": "", "type_id": "23", "type_name": "综艺"},
    {"vod_id": "82500", "vod_name": "追寻幽灵大象", "vod_pic": "https://img.picbf.com/upload/vod/20260309-1/16ee74cb46b50561.jpg", "vod_remarks": "更新至HD", "type_id": "24", "type_name": "纪录片"},
    {"vod_id": "120047", "vod_name": "蚌家镇怪谈", "vod_pic": "", "vod_remarks": "", "type_id": "1", "type_name": "电影"},
    {"vod_id": "119214", "vod_name": "非演员", "vod_pic": "", "vod_remarks": "", "type_id": "1", "type_name": "电影"},
]

# 播放地址缓存 (vod_id -> {vod_play_from, vod_play_url})
_DETAILS = {}


def _get(url, is_json=False):
    """发送 HTTP 请求"""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Referer": HOST,
            "Accept": "application/json, text/javascript, */*" if is_json else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "X-Requested-With": "XMLHttpRequest" if is_json else "",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read().decode("utf-8", errors="ignore")
            if is_json:
                return json.loads(data) if data else {}
            return data
    except Exception as e:
        return {} if is_json else ""


def _fix_pic(pic):
    """修复百度转链图片 URL"""
    if not pic:
        return ""
    if pic.startswith("https://image.baidu.com/search/down?url="):
        m = re.search(r"url=(https?://[^&]+)", pic)
        if m:
            return m.group(1)
    return pic


def _extract_player(html):
    """从播放页提取 player_aaaa JSON"""
    idx = html.find("var player_aaaa")
    if idx < 0:
        return None
    start = html.find("{", idx)
    depth = 0
    end = start
    for i, c in enumerate(html[start:]):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = start + i + 1
                break
    try:
        return json.loads(html[start:end])
    except:
        return None


def _decode_url(url_val):
    """解码 base64 + URL编码的播放地址"""
    if not url_val:
        return ""
    try:
        decoded = base64.b64decode(url_val).decode("utf-8")
        decoded = unquote(decoded)
        decoded = unquote(decoded)
        return decoded
    except:
        return url_val


class Spider(BaseSpider):
    name = "奈飞工厂"

    def __init__(self):
        self.HOST = HOST

    def getName(self):
        return self.name

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return bool(re.search(r"(?i)(m3u8|mp4|flac|m4a)(?:\?|$)", str(url or "")))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter=False):
        """首页: 返回分类列表 + 推荐视频"""
        result = {"class": []}
        for tid, tname in CAT_MAP.items():
            result["class"].append({"type_name": tname, "type_id": tid})

        if filter:
            result["filters"] = {
                tid: [
                    {"key": "area", "name": "地区", "value": [
                        {"n": "全部", "v": ""}, {"n": "中国大陆", "v": "中国大陆"},
                        {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"},
                        {"n": "韩国", "v": "韩国"}, {"n": "英国", "v": "英国"},
                    ]},
                    {"key": "year", "name": "年份", "value": [
                        {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"},
                        {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"},
                        {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"},
                    ]},
                    {"key": "by", "name": "排序", "value": [
                        {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"},
                        {"n": "评分", "v": "score"},
                    ]},
                ]
                for tid in CAT_MAP
            }

        # 推荐视频 (从首页 AJAX 获取最新数据)
        try:
            data = _get(f"{HOST}/index.php/ajax/data?mid=1&page=1&limit=20", is_json=True)
            videos = []
            for item in data.get("list", []):
                videos.append({
                    "vod_id": str(item.get("vod_id", "")),
                    "vod_name": item.get("vod_name", ""),
                    "vod_pic": _fix_pic(item.get("vod_pic", "")),
                    "vod_remarks": item.get("vod_remarks", ""),
                })
            result["list"] = videos[:20]
        except:
            result["list"] = _HOME_VIDEOS[:20]
        return result

    def homeVideoContent(self):
        """首页视频内容"""
        try:
            data = _get(f"{HOST}/index.php/ajax/data?mid=1&page=1&limit=20", is_json=True)
            videos = []
            for item in data.get("list", []):
                videos.append({
                    "vod_id": str(item.get("vod_id", "")),
                    "vod_name": item.get("vod_name", ""),
                    "vod_pic": _fix_pic(item.get("vod_pic", "")),
                    "vod_remarks": item.get("vod_remarks", ""),
                })
            return {"list": videos[:20]}
        except:
            return {"list": _HOME_VIDEOS[:20]}

    def categoryContent(self, tid, pg="1", filt=False, ext={}):
        """分类页"""
        page = max(int(pg), 1)
        result = {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}
        if not tid or tid not in CAT_MAP:
            return result
        try:
            data = _get(f"{HOST}/index.php/ajax/data?mid=1&tid={tid}&page={page}&limit=20", is_json=True)
            videos = []
            for item in data.get("list", []):
                videos.append({
                    "vod_id": str(item.get("vod_id", "")),
                    "vod_name": item.get("vod_name", ""),
                    "vod_pic": _fix_pic(item.get("vod_pic", "")),
                    "vod_remarks": item.get("vod_remarks", ""),
                })
            total = data.get("total", 0)
            result["list"] = videos
            result["total"] = total
            result["pagecount"] = max(1, (total + 19) // 20)
        except:
            pass
        return result

    def detailContent(self, ids):
        """详情页 - 获取播放地址"""
        result = {"page": "", "list": []}
        if isinstance(ids, list):
            ids = ids[0]
        if not ids:
            return result
        vid = str(ids)
        # 检查缓存
        if vid in _DETAILS:
            vod = dict(_DETAILS[vid])
            vod["vod_id"] = vid
            result["list"] = [vod]
            result["page"] = "1"
            return result
        try:
            # 从 AJAX 获取视频基本信息 (首页优先，找不到则按不同 tid 重试)
            data = _get(f"{HOST}/index.php/ajax/data?mid=1&page=1&limit=500", is_json=True)
            info = None
            for item in data.get("list", []):
                if str(item.get("vod_id")) == vid:
                    info = item
                    break
            # 首页未找到，尝试按直播子分类 tid=58 搜索
            if not info:
                data = _get(f"{HOST}/index.php/ajax/data?mid=1&tid=58&page=1&limit=20", is_json=True)
                for item in data.get("list", []):
                    if str(item.get("vod_id")) == vid:
                        info = item
                        break
            if not info:
                return result
            # 获取播放地址
            play_froms = []
            play_urls = []
            for pf in range(1, 10):
                html = _get(f"{HOST}/vodplay/{vid}-{pf}-1.html")
                pa = _extract_player(html)
                if pa:
                    from_val = pa.get("from", "")
                    url_decoded = _decode_url(pa.get("url", ""))
                    if from_val and url_decoded and url_decoded.startswith("http"):
                        play_froms.append(from_val)
                        play_urls.append(f"第1集${url_decoded}")
            # 构建 vod 对象
            vod = {
                "vod_id": vid,
                "vod_name": info.get("vod_name", ""),
                "vod_pic": _fix_pic(info.get("vod_pic", "")),
                "type_name": info.get("type", {}).get("type_name", ""),
                "vod_remarks": info.get("vod_remarks", ""),
                "vod_content": info.get("vod_blurb", "").strip(),
                "vod_actor": info.get("vod_actor", ""),
                "vod_director": info.get("vod_director", ""),
                "vod_year": info.get("vod_year", ""),
                "vod_area": info.get("vod_area", ""),
                "vod_play_from": "$$$".join(play_froms) if play_froms else "",
                "vod_play_url": "$$$".join(play_urls) if play_urls else "",
            }
            _DETAILS[vid] = vod
            result["list"] = [vod]
            result["page"] = "1"
        except:
            pass
        return result

    def playerContent(self, flag, id, vipFlags):
        """播放页 - 从 player_aaaa 提取并解码播放 URL"""
        result = {"parse": 0, "jx": 0, "url": "", "header": {}}
        try:
            # id 格式: {vid}-{pf}-{ep} 或直接是 URL
            if "$" in str(id):
                # TVBox 传入的格式: "名称$URL"
                id_str = str(id).rsplit("$", 1)[-1]
            else:
                id_str = str(id)

            # 如果是播放页 URL，提取 vid 和 pf
            m = re.match(r"(\d+)-(\d+)-(\d+)", id_str)
            if m:
                vid = m.group(1)
                pf = m.group(2)
                html = _get(f"{HOST}/vodplay/{vid}-{pf}-1.html")
                pa = _extract_player(html)
                if pa:
                    url_decoded = _decode_url(pa.get("url", ""))
                    if url_decoded and url_decoded.startswith("http"):
                        result["url"] = url_decoded
                        result["parse"] = 0
                        return result
            elif id_str.startswith("http"):
                result["url"] = id_str
                result["parse"] = 0
                return result
        except:
            pass
        return result

    def searchContent(self, key, quick=False):
        """搜索 - 解析搜索页 HTML 获取结果"""
        result = {"list": [], "page": "1", "pagecount": 1, "limit": 50, "total": 0}
        try:
            url = f"{HOST}/vodsearch/-------------.html?wd={quote(key)}"
            html = _get(url)
            if not html:
                return result
            # 解析搜索结果列表
            items = re.findall(
                r'<a[^>]*href=["\'](/voddetail/(\d+)[^"\']*)["\'][^>]*>.*?<h3[^>]*>([^<]+)</h3>',
                html, re.DOTALL
            )
            matched = []
            for href, vid, name in items:
                matched.append({
                    "vod_id": str(vid),
                    "vod_name": name.strip(),
                    "vod_pic": "",
                    "vod_remarks": "",
                })
            result["list"] = matched[:50]
            result["total"] = len(matched)
        except:
            pass
        return result

    def localProxy(self, params):
        return None


# TVBox 入口
spider = Spider()
