# -*- coding: utf-8 -*-
site_name = "拍摄现场"
site_url = "https://xn--kpu43ihs1c.psbolddeltaco.site"
import sys, re, json, base64, html, os, threading, time, hashlib
from urllib.parse import quote, unquote, urljoin, urlparse
try: from lxml import etree
except ImportError: etree = None
try: import requests
except ImportError: requests = None
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    urllib3 = None
try: from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): self.extend = extend
        def homeContent(self, filter): return {'class': [], 'filters': {}}
        def homeVideoContent(self): return {'list': []}
        def categoryContent(self, tid, pg, filter, extend): return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 24, 'total': 0}
        def detailContent(self, ids): return {'list': []}
        def playerContent(self, flag, id, vipFlags=None): return {'parse': 1, 'playUrl': '', 'url': '', 'header': {}}
        def searchContent(self, key, quick, pg='1'): return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 24, 'total': 0}
        def isVideoFormat(self, url): return False
        def getDependence(self): return []
        def manualVideoCheck(self): return False
        def localProxy(self, param): return [404, 'text/plain', b'']

def fix_url(url, host):
    if not url: return ""
    if url.startswith("//"): return "https:" + url
    if url.startswith("http"): return url
    if url.startswith("/"): return urljoin(host, url)
    return urljoin(host, "/" + url)

def clean_text(text):
    if not text: return ""
    return html.unescape(re.sub(r'<[^>]+>', '', str(text))).strip()

def _page(pg):
    try:
        v = int(str(pg or "").strip())
        return v if v > 0 else 1
    except Exception:
        return 1

def _extract_vod_data(text):
    """从页面HTML提取 atob('...') 中的 base64 JSON"""
    if not text:
        return None
    m = re.search(r"atob\('([A-Za-z0-9+/=]+)'\)", text)
    if not m:
        m = re.search(r'atob\("([A-Za-z0-9+/=]+)"\)', text)
    if not m:
        return None
    try:
        return json.loads(base64.b64decode(m.group(1)).decode("utf-8", "replace"))
    except Exception:
        return None

def _unwrap_play(url):
    """解包 aojiexi.com/?url=xxx 跳转链接为真实播放地址"""
    if not url:
        return ""
    if "url=" in url:
        m = re.search(r'[?&]url=([^&]+)', url)
        if m:
            u = unquote(m.group(1))
            if u.startswith("http"):
                return u
    return url

def _clean_play(url):
    """统一清洗播放地址: 处理 '第1集$url' 格式 + aojiexi 跳转 + 多余字符"""
    if not url:
        return ""
    u = str(url).strip()
    if "$" in u:
        u = u.split("$", 1)[1].strip()
    u = _unwrap_play(u)
    if "url=" in u:
        m = re.search(r'[?&]url=([^&]+)', u)
        if m:
            inner = unquote(m.group(1))
            if inner.startswith("http"):
                u = inner
    u = u.strip().strip('"').strip("'").strip()
    return u

class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://xn--kpu43ihs1c.psbolddeltaco.site"
        self.name = "拍摄现场"
        self.s = requests.Session() if requests else None
        self.session = self.s
        self.ext = ""
        self.proxies = {}
        self.verify = False
        self.timeout = 15
        self.search_fallback = True
        self.search_fallback_pages = 1
        self.reverse_proxy = ""
        self.proxy_target = ""
        self.proxy_api = ""
        self.proxy_full_url = True
        self.play_cache = {}
        self.media_cache = {}
        self._play_map = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.60 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self.cms_type = "nonstandard"
        self.content_type = "video"
        self.seen_ids = set()
        self.cookies = {}
        self._cf_cache = {}
        if self.s: self.s.headers.update(self.headers)
        self._hosts = [
            "https://xn--kpu43ihs1c.psbolddeltaco.site",
            "https://solo.paishexianchang.site",
        ]
        self._types = [
            ("43", "国产原创"), ("35", "中字精品"), ("53", "实拍短片"),
            ("29", "跨性别专区"), ("21", "同志男男"), ("23", "百合实拍"),
            ("25", "猎奇另类"), ("27", "禁忌物种"), ("31", "束缚体验"),
            ("33", "女优精选"), ("37", "黑人特辑"), ("39", "欧美实拍"),
            ("41", "留洋实拍"), ("45", "AI合成区"), ("47", "制服萌系"),
            ("49", "主播私拍"), ("51", "私约现场"), ("55", "剧情伦理"),
            ("57", "黑料揭秘"), ("59", "动画秘档"), ("61", "VR互动"),
            ("63", "真实投稿区"),
        ]

    def init(self, extend=""):
        self.ext = str(extend or "").strip()
        return

    def _parse_extend(self, extend):
        if isinstance(extend, dict): return dict(extend)
        text = str(extend or "").strip()
        if not text: return {}
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {"host": text} if text.startswith(("http://", "https://")) else {}

    def _get_host(self, extend=None):
        data = self._parse_extend(extend)
        h = data.get("host", "").strip()
        if h and h.startswith("http"):
            return h.rstrip("/")
        return self.host.rstrip("/")

    def _get(self, url, **kwargs):
        if not url: return None
        timeout = kwargs.pop("timeout", self.timeout)
        verify = kwargs.pop("verify", self.verify)
        proxies = kwargs.pop("proxies", self.proxies)
        ua = kwargs.pop("ua", None)
        if ua:
            h = dict(self.headers)
            h["User-Agent"] = ua
        else:
            h = self.headers
        if requests:
            if self.s:
                try:
                    return self.s.get(url, timeout=timeout, verify=verify, proxies=proxies, **kwargs)
                except Exception:
                    pass
            return requests.get(url, timeout=timeout, verify=verify, proxies=proxies, headers=h, **kwargs)
        return None

    def _fetcher(self, *args, **kwargs):
        return self._get(*args, **kwargs)

    def fetch(self, url, headers=None, timeout=15):
        if not url:
            return None
        timeout = timeout if timeout is not None else self.timeout
        h = {"User-Agent": "Mozilla/5.0"}
        if headers and isinstance(headers, dict):
            h.update(headers)
        return self._get(url, headers=h, timeout=timeout)

    def _request_vod_data(self, url, ua=None):
        """请求页面并返回解码后的 __vod_data__ JSON"""
        for host in self._hosts:
            target = url if url.startswith("http") else urljoin(host, url)
            try:
                h = dict(self.headers)
                if ua:
                    h["User-Agent"] = ua
                h["Referer"] = host + "/"
                r = requests.get(target, timeout=self.timeout, verify=self.verify, proxies=self.proxies, headers=h)
                if r and r.status_code == 200 and r.text:
                    data = _extract_vod_data(r.text)
                    if data:
                        return data
                    return None
            except Exception:
                continue
        return None

    def _type_name(self, tid):
        for t, n in self._types:
            if str(t) == str(tid):
                return n
        return ""

    def _list_from_data(self, data, host=None):
        """从 __vod_data__ JSON 提取视频列表（播放地址直接从列表数据带出）"""
        host = host or self.host
        items = []
        if not data:
            return items
        rd = data.get("request_data") or {}
        lst = rd.get("list") or []
        for it in lst:
            try:
                vid = it.get("vod_id")
                if vid is None:
                    continue
                tid = it.get("type_id") or data.get("type_id") or ""
                name = clean_text(it.get("vod_name") or "")
                if not name:
                    continue
                detail = "/voddetail/type/%s/id/%s.html" % (tid, vid)
                pic = fix_url(it.get("vod_pic") or "", host)
                remark = clean_text(it.get("vod_duration") or "")
                # 列表数据内嵌播放地址（格式: 第1集$m3u8），解包后缓存，播放不依赖详情页请求
                pu = _clean_play(it.get("vod_play_url") or "")
                if pu and pu.startswith("http"):
                    self._play_map[str(vid)] = pu
                items.append({
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                    "vod_id": detail,
                    "vod_play_url": pu,
                })
            except Exception:
                continue
        return items

    def _total_from_data(self, data):
        if not data:
            return 0
        rd = data.get("request_data") or {}
        return _page(rd.get("total") or 0)

    def classContent(self, tid, pg, filter, extend):
        host = self._get_host(extend)
        page = _page(pg)
        tid_str = str(tid or "").strip()
        url = host + "/vodlist/type/%s/keyword/all/orderby/default/page/%d.html" % (tid_str, page)
        data = self._request_vod_data(url)
        items = self._list_from_data(data, host)
        total = self._total_from_data(data)
        # 空分类降级：用分类名作为关键词搜索，保证有内容
        if not items:
            name = self._type_name(tid_str)
            if name:
                surl = host + "/vodlist/type/all/keyword/%s/orderby/default/page/%d.html" % (quote(name), page)
                sdata = self._request_vod_data(surl)
                sitems = self._list_from_data(sdata, host)
                if sitems:
                    items = sitems
                    total = self._total_from_data(sdata)
        pagecount = max(1, -(-total // 18)) if total else page
        return {'list': items[:24], 'page': page, 'pagecount': pagecount, 'limit': 24, 'total': total}

    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": name} for tid, name in self._types]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        return self.categoryContent("43", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        return self.classContent(tid, pg, filter, extend)

    def detailContent(self, ids):
        if not ids: return {'list': []}
        host = self.host
        vid = ids[0] if ids else ""
        url = fix_url(vid, host)
        play_url = ""
        # 1) 优先用列表数据带出的播放地址（避免详情页被 CF 拦截拿不到）
        vid_num = re.search(r'/id/(\d+)', url)
        vid_key = vid_num.group(1) if vid_num else str(vid)
        if vid_key in self._play_map:
            play_url = self._play_map[vid_key]
        # 2) 尝试详情页补充信息 + 播放地址
        data = self._request_vod_data(url)
        if data:
            vi = data.get("vod_info") or {}
            if not play_url:
                play_url = _clean_play(vi.get("vod_play_url") or "")
            rd = data.get("request_data") or {}
            for it in (rd.get("list") or []):
                pu2 = _clean_play(it.get("vod_play_url") or "")
                if pu2 and pu2.startswith("http"):
                    play_url = pu2
                    break
            # 兜底: 详情数据里若只有 /play/ 页面, 用它作播放地址, playerContent 会再去抓
            if not play_url:
                pid = vi.get("vod_id") or vid_key
                play_url = "/play/?id=%s" % pid
        # 3) 兜底: 详情页 URL 本身（playerContent 会抓页面解 atob 提取 m3u8）
        if not play_url:
            play_url = url
        name = ""
        pic = ""
        remark = ""
        if data:
            vi = data.get("vod_info") or {}
            name = clean_text(vi.get("vod_name") or "")
            pic = fix_url(vi.get("vod_pic") or "", host)
            remark = clean_text(vi.get("vod_remarks") or vi.get("vod_duration") or "")
            if not name:
                name = clean_text(data.get("site_title") or "")
        if not name:
            name = clean_text(re.sub(r'[-_].*$', '', url.rsplit('/', 1)[-1])) or "视频"
        vod = {
            "vod_id": url,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "播放",
            "vod_play_url": "播放$$$" + (play_url if play_url else url),
        }
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags=None):
        play = id
        if not play or not isinstance(play, str):
            return {"parse": 1, "playUrl": "", "url": "", "header": {}}
        # 统一清洗: '第1集$url' 分割 + aojiexi 跳转解包
        play = _clean_play(play)
        if not play:
            return {"parse": 1, "playUrl": "", "url": "", "header": {}}
        if not play.startswith("http") and play:
            play = fix_url(play, self.host)
        # 直链播放: m3u8/mp4 直接交给播放器
        if re.search(r'\.(m3u8|mp4|flv|mpd)(\?|$)', play, re.I):
            tag = "hls" if re.search(r'\.m3u8', play, re.I) else "mp4"
            headers = {
                "User-Agent": self.headers.get("User-Agent", ""),
                "Referer": self.host,
            }
            return {"parse": 0, "playUrl": "", "url": play, "header": headers, "tag": tag}
        # 页面链接: 抓页面, 先解 atob JSON 提取播放地址, 再正则兜底
        if play.startswith("http"):
            try:
                r = self._get(play, ua="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36")
                if r and r.text:
                    text = r.text
                    # 1) atob base64 数据里的播放地址
                    data = _extract_vod_data(text)
                    if data:
                        vi = data.get("vod_info") or {}
                        pu = _clean_play(vi.get("vod_play_url") or "")
                        if pu and pu.startswith("http"):
                            headers = {
                                "User-Agent": self.headers.get("User-Agent", ""),
                                "Referer": self.host,
                            }
                            tag = "hls" if re.search(r'\.m3u8', pu, re.I) else "mp4"
                            return {"parse": 0, "playUrl": "", "url": pu, "header": headers, "tag": tag}
                        rd = data.get("request_data") or {}
                        for it in (rd.get("list") or []):
                            pu = _clean_play(it.get("vod_play_url") or "")
                            if pu and pu.startswith("http"):
                                headers = {
                                    "User-Agent": self.headers.get("User-Agent", ""),
                                    "Referer": self.host,
                                }
                                tag = "hls" if re.search(r'\.m3u8', pu, re.I) else "mp4"
                                return {"parse": 0, "playUrl": "", "url": pu, "header": headers, "tag": tag}
                    # 2) 正则兜底
                    m3 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', text, re.I)
                    if m3:
                        headers = {
                            "User-Agent": self.headers.get("User-Agent", ""),
                            "Referer": self.host,
                        }
                        return {"parse": 0, "playUrl": "", "url": m3.group(1), "header": headers, "tag": "hls"}
                    m4 = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', text, re.I)
                    if m4:
                        headers = {
                            "User-Agent": self.headers.get("User-Agent", ""),
                            "Referer": self.host,
                        }
                        return {"parse": 0, "playUrl": "", "url": m4.group(1), "header": headers, "tag": "mp4"}
            except Exception:
                pass
        return {"parse": 1, "playUrl": "", "url": play or "", "header": {}}

    def searchContent(self, key, quick, pg='1'):
        host = self.host
        page = _page(pg)
        url = host + "/vodlist/type/all/keyword/%s/orderby/default/page/%d.html" % (quote(str(key)), page)
        data = self._request_vod_data(url)
        items = self._list_from_data(data, host)
        total = self._total_from_data(data)
        pagecount = max(1, -(-total // 18)) if total else page
        return {'list': items[:24], 'page': page, 'pagecount': pagecount, 'limit': 24, 'total': total}

    def isVideoFormat(self, url):
        if not url or not isinstance(url, str): return False
        u = url.lower()
        return any(u.endswith(ext) for ext in [".m3u8", ".mp4", ".flv", ".mpd"])

    def getDependence(self):
        return []

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, 'text/plain', b'']


if __name__ == "__main__":
    Spider().init()
