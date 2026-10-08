# -*- coding: utf-8 -*-

import re
import json
import base64
import html as _html
from urllib.parse import quote, unquote, urljoin

try:
    from lxml import etree  # noqa: F401  (备用, 当前以正则解析)
except ImportError:
    etree = None
try:
    import requests
except ImportError:
    requests = None
try:
    import cloudscraper
except ImportError:
    cloudscraper = None
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

SITE = "https://goodav17.com"
EMBED_HOST = "https://ggjav.com"
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# FC2 等含空格地址的 HLS 清洗代理开关。
# 说明: proxy:// 仅标准 TVBox 系(影视仓原版)支持, 部分 HKL/影视仓改版会报
#       "不支持的协议 proxy"。默认关闭直接投递 m3u8; 若 APP 支持 proxy://,
#       改 True 可让 FC2 分片空格经本地代理转 %20 后播放。
ENABLE_HLS_PROXY = False

# 兜底分类(首页导航解析失败时使用)
FALLBACK_TYPES = [
    ("home", "首頁"), ("local", "本土自拍"), ("vr", "VR"),
    ("人妻", "人妻"), ("素人", "素人"), ("巨乳", "巨乳"), ("無碼", "無碼"),
    ("中出", "中出"), ("OL", "OL"), ("學生", "學生"), ("護士", "護士"),
    ("潮吹", "潮吹"), ("絲襪", "絲襪"), ("美腿", "美腿"), ("美尻", "美尻"),
    ("癡女", "癡女"), ("輕熟女", "輕熟女"), ("肛交", "肛交"), ("自慰", "自慰"),
    ("口爆", "口爆"), ("顏射", "顏射"), ("乳交", "乳交"), ("足交", "足交"),
]


class _EmptyResp(object):
    text = ""
    content = b""
    status_code = 0


def _clean_text(t):
    t = _html.unescape(t or "")
    return re.sub(r"\s+", " ", t).strip()


def _page(pg):
    try:
        p = int(pg)
    except (TypeError, ValueError):
        return 1
    return p if p > 0 else 1


def _b64d(s):
    """Base64 解码, 自动补齐 padding。"""
    if not s:
        return ""
    s = s.strip().replace(" ", "+")
    s += "=" * (-len(s) % 4)
    try:
        return base64.b64decode(s).decode("utf-8", "ignore")
    except Exception:
        return ""


def _clean_detail_title(title):
    """详情页标题清理: 去掉站点后缀与"| 来源"标记。"""
    t = title or ""
    t = re.split(r"\s*[-|]\s*正妹AV.*$", t)[0]
    t = re.sub(r"\s*\|\s*[^|]+$", "", t)
    return _clean_text(t)


def _extract_no(alt, name):
    """从 alt/标题中提取番号, 如 SONE-829 / FC2-PPV 4848428。"""
    m = re.search(r"(?i)\b(fc2[-_ ]?ppv\s*\d+|[a-z]{2,6}-\d{2,6})\b",
                  (alt or "") + " " + (name or ""))
    if not m:
        return ""
    v = m.group(1).upper()
    if v.startswith("FC2"):
        v = "FC2-PPV " + v.split("PPV", 1)[1].strip()
    return v


def _parse_movies(html, host):
    """解析 <div class='movie'> 视频列表。"""
    out = []
    seen = set()
    # 本地页图片在 HTML 注释里还存了一份, 先剥掉注释避免干扰
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    for part in html.split("<div class='movie'>")[1:]:
        hrefs = re.findall(r"/(?:html|local_html)/(\d+)/", part)
        if not hrefs:
            continue
        vid = hrefs[0]
        if vid in seen:
            continue
        seen.add(vid)
        local = "local_html" in part
        # 封面: 优先 large_image, 回退 src
        pic = ""
        m = re.search(r"large_image=['\"]([^'\"]+)", part)
        if m:
            pic = m.group(1)
        else:
            m = re.search(r"<img[^>]*src=['\"]([^'\"]+)", part)
            if m:
                pic = m.group(1)
        # 标题: 图片链接无文本, 取最后一个带文本的 a
        name = ""
        for m in re.finditer(r'/(?:html|local_html)/\d+/">([^<]*)</a>', part):
            t = _clean_text(m.group(1))
            if t:
                name = t
        alt = ""
        m = re.search(r"alt=['\"]([^'\"]*)", part)
        if m:
            alt = m.group(1)
        remarks = "本土自拍" if local else _extract_no(alt, name)
        out.append({
            "vod_id": ("local_" + vid) if local else vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
        })
    return out


def _get_max_page(html):
    m = re.search(r"max_page\s*=\s*(\d+)", html or "")
    return int(m.group(1)) if m else 0


# ── HKL 框架兼容基类 (框架内运行时由 base.spider 提供) ──
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def init(self, extend=""):
            self.extend = extend

        def homeContent(self, filter):
            return {'class': [], 'filters': {}}

        def homeVideoContent(self):
            return {'list': []}

        def categoryContent(self, tid, pg, filter, extend):
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 24, 'total': 0}

        def detailContent(self, ids):
            return {'list': []}

        def playerContent(self, flag, id, vipFlags=None):
            return {'parse': 0, 'playUrl': '', 'url': '', 'header': ''}

        def searchContent(self, key, quick, pg='1'):
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 24, 'total': 0}

        def isVideoFormat(self, url):
            return False

        def manualVideoCheck(self):
            return False

        def localProxy(self, param):
            return [404, 'text/plain', b'']


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = SITE
        self.name = "正妹AV"
        self.s = requests.Session() if requests else None
        self.session = self.s
        self.ext = ""
        self.proxies = {}
        self.verify = False
        self.timeout = 15
        self.search_fallback = True
        self.search_fallback_pages = 1
        self.headers = {
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": SITE + "/",
        }
        self.cookies = {}
        self._cf_cache = {}
        self._scraper = None
        if self.s:
            self.s.headers.update(self.headers)
            self.s.verify = self.verify

    # ── 配置 ──
    def _parse_extend(self, extend):
        if isinstance(extend, dict):
            return dict(extend)
        text = str(extend or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {"host": text} if text.startswith(("http://", "https://")) else {}

    def setExtendInfo(self, extend):
        self.ext = extend or ""
        cfg = self._parse_extend(extend)
        host = str(cfg.get("host") or cfg.get("HOST") or "").strip().rstrip("/")
        if host.startswith(("http://", "https://")):
            self.host = host
        ua = str(cfg.get("userAgent") or cfg.get("User-Agent") or cfg.get("ua") or "").strip()
        if ua:
            self.headers["User-Agent"] = ua
        cookie = str(cfg.get("cookie") or cfg.get("Cookie") or "").strip()
        if cookie:
            self.headers["Cookie"] = cookie
        elif "Cookie" in self.headers:
            self.headers.pop("Cookie", None)
        referer = str(cfg.get("referer") or cfg.get("Referer") or "").strip()
        self.headers["Referer"] = referer if referer.startswith(("http://", "https://")) else self.host + "/"
        try:
            self.timeout = max(3, int(cfg.get("timeout", self.timeout) or self.timeout))
        except (TypeError, ValueError):
            pass
        self.verify = str(cfg.get("verify", "")).strip().lower() in ("1", "true", "yes", "on")
        proxy = str(cfg.get("proxy") or "").strip()
        self.proxies = {"http": proxy, "https": proxy} if proxy.startswith(("http://", "https://")) else {}
        if self.s:
            self.s.headers.update(self.headers)
            self.s.proxies.update(self.proxies)
            self.s.verify = self.verify
        return None

    def init(self, extend=""):
        self.setExtendInfo(extend if extend else self.ext)
        return None

    def getDependence(self):
        return []

    # ── 请求层 ──
    def _get_scraper(self):
        if self._scraper is None and cloudscraper is not None:
            try:
                self._scraper = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "mobile": False},
                    delay=2)
            except Exception:
                self._scraper = None
        return self._scraper

    def _is_cf_challenge(self, text):
        low = (text or "").lower()
        return ("cf-challenge" in low or "__cf_chl" in low or "just a moment" in low
                or ("cloudflare" in low and "captcha" in low))

    def _cf_bypass(self, url):
        sc = self._get_scraper()
        if sc is None:
            return False
        try:
            resp = sc.get(url, timeout=self.timeout, headers=self.headers)
            if resp is not None and resp.status_code == 200:
                for c in resp.cookies:
                    self.cookies[c.name] = c.value
                if self.s:
                    self.s.cookies.update(resp.cookies)
                return True
        except Exception:
            pass
        return False

    def _request(self, method, url, data=None, json=None, headers=None, timeout=None, retry=2):
        if self.s is None:
            return _EmptyResp()
        kw = {"timeout": timeout or self.timeout}
        if headers:
            kw["headers"] = headers
        if data is not None:
            kw["data"] = data
        if json is not None:
            kw["json"] = json
        try:
            resp = self.s.request(method.upper(), url, **kw)
        except Exception:
            return _EmptyResp()
        if resp.status_code in (403, 503, 429) and self._is_cf_challenge(resp.text):
            for _ in range(max(1, retry)):
                b = self._cf_bypass(url)
                if not b:
                    break
                try:
                    resp = self.s.request(method.upper(), url, **kw)
                except Exception:
                    break
                if not (resp.status_code in (403, 503, 429) and self._is_cf_challenge(resp.text)):
                    break
        return resp

    def _fetch(self, url, timeout=None):
        resp = self._request("GET", url, timeout=timeout)
        if resp is None or not getattr(resp, "content", b""):
            return ""
        text = getattr(resp, "text", "") or ""
        # requests 探测的编码出错(乱码)时, 强制按 utf-8 重解
        if "\ufffd" in text and resp.content:
            try:
                text = resp.content.decode("utf-8", "ignore")
            except Exception:
                pass
        return text

    # ── 首页导航 ──
    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        types = []
        html = self._fetch(self.host + "/1/")
        if html:
            for m in re.finditer(r'href="[^"]*/type/([^"/]+)/1/"\s*>([^<]+)<', html):
                tid, tname = m.group(1), _clean_text(m.group(2))
                if tid and tname and not any(x[0] == tid for x in types):
                    types.append((tid, tname))
        if not types:
            types = list(FALLBACK_TYPES)
        for tid, tname in types:
            result["class"].append({"type_id": tid, "type_name": tname})
        return result

    def homeVideoContent(self):
        html = self._fetch(self.host + "/1/")
        return {"list": _parse_movies(html, self.host)}

    # ── 分类列表 ──
    def categoryContent(self, tid, pg, filter, extend):
        pg = _page(pg)
        tid = str(tid or "")
        if tid.startswith("http"):
            url = tid
        elif tid in ("home", "首頁"):
            url = self.host + "/%d/" % pg
        elif tid in ("local", "本土", "本土自拍"):
            url = self.host + "/local/%d/" % pg
        elif tid.startswith("local_"):
            url = self.host + "/local_type/%s/%d/" % (quote(tid[6:]), pg)
        elif tid == "vr":
            url = self.host + "/vr/%d/" % pg
        else:
            url = self.host + "/type/%s/%d/" % (quote(tid), pg)
        html = self._fetch(url)
        lst = _parse_movies(html, self.host)
        maxp = _get_max_page(html)
        pagecount = maxp if maxp > 0 else pg + 1
        return {"list": lst, "page": pg, "pagecount": pagecount,
                "limit": 24, "total": len(lst)}

    # ── 详情 ──
    def detailContent(self, ids):
        raw_ids = ids if isinstance(ids, (list, tuple)) else [ids]
        vid = str(raw_ids[0] if raw_ids else "").strip()
        result = {"list": []}
        if not vid:
            return result
        local = vid.startswith("local_")
        nid = vid[6:] if local else vid
        if vid.startswith("http"):
            url = vid
        elif local:
            url = self.host + "/local_html/%s/" % nid
        else:
            url = self.host + "/html/%s/" % nid
        html = self._fetch(url)
        if not html:
            return result
        # 标题
        name = ""
        m = re.search(r"<title>([^<]*)</title>", html, re.S | re.I)
        if m:
            name = _clean_detail_title(m.group(1))
        # 封面
        pic = ""
        m = re.search(r"<div id='m_image'>.*?<img[^>]*src=['\"]([^'\"]+)", html, re.S)
        if m:
            pic = m.group(1)
        if not pic:
            m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', html, re.I)
            if m:
                pic = m.group(1)
        # 番号
        remarks = ""
        m = re.search(r"<div id='m_designation'[^>]*>.*?<font[^>]*>\s*([^<]+)", html, re.S)
        if m:
            remarks = _clean_text(m.group(1))
        # 播放: 解析 video_frame iframe(支持 id='video_frame' 与 id="video-frame" 两种写法)
        urls = []
        for m in re.finditer(r"<iframe[^>]*video_frame[^>]*src=['\"]([^'\"]+)", html, re.I):
            embed = m.group(1).replace("&amp;", "&")
            pu = ""
            mu = re.search(r"[?&]u=([^&\s]+)", embed)
            if mu:
                # JAV: u 参数 Base64 = 视频基地址, 真实流 = {基地址}/index.m3u8 (HLS)
                du = _b64d(unquote(mu.group(1)))
                if du:
                    pu = du if du.lower().endswith(".m3u8") else du + "/index.m3u8"
            else:
                # 本土(porn87)等: 请求 embed 页, <video> 的 src 即 m3u8
                ehtml = self._fetch(embed)
                mv = re.search(r"<video[^>]*\ssrc=['\"]([^'\"]+)", ehtml, re.I)
                if mv:
                    pu = mv.group(1)
            if pu:
                pu = pu.replace(" ", "%20")
                # FC2 等分片含空格的流: 仅当 APP 支持 proxy:// 本地代理时才走清洗
                if "%20" in pu and ENABLE_HLS_PROXY:
                    pu = "proxy://do=m3u8&url=" + quote(pu)
                if pu not in urls:
                    urls.append(pu)
        play_url = ""
        if urls:
            eps = []
            for i, u in enumerate(urls):
                ep = "播放%d" % (i + 1) if len(urls) > 1 else "播放"
                eps.append(ep + "$" + u)
            play_url = "#".join(eps)
        result["list"].append({
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_play_from": "正妹AV",
            "vod_play_url": play_url,
        })
        return result

    # ── 播放 ──
    def playerContent(self, flag, id, vipFlags=None):
        u = str(id or "").strip()
        if not u:
            return {"parse": 1, "url": "", "header": {}}
        if u.startswith("proxy://"):
            # 本地 HLS 清洗代理(FC2 分片空格转 %20), 直接交给框架的 localProxy
            return {"parse": 0, "url": u, "header": {}}
        if u.startswith(("http://", "https://")):
            referer = "https://porn87.com/" if "porn87.com" in u else EMBED_HOST + "/"
            return {"parse": 0, "url": u,
                    "header": {"Referer": referer,
                               "User-Agent": self.headers.get("User-Agent", DEFAULT_UA)}}
        return {"parse": 1, "url": "", "header": {}}

    # ── 搜索 ──
    def searchContent(self, key, quick, pg='1'):
        pg = _page(pg)
        key = str(key or "").strip()
        if not key:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 24, "total": 0}
        url = self.host + "/search/%s/%d/" % (quote(key), pg)
        html = self._fetch(url)
        lst = _parse_movies(html, self.host)
        maxp = _get_max_page(html)
        pagecount = maxp if maxp > 0 else pg + 1
        return {"list": lst, "page": pg, "pagecount": pagecount,
                "limit": 24, "total": len(lst)}

    # ── 其余 ──
    def isVideoFormat(self, url):
        u = str(url or "")
        return bool(u) and (u.startswith(("http://", "https://", "proxy://")))

    def manualVideoCheck(self):
        return False

    def _clean_m3u8(self, raw, base):
        """清洗 HLS 播放列表: 相对路径补全 + 空格转 %20 + 变体播放列表继续走代理。

        FC2 等视频的 m3u8 分片 URL 含原始空格(如 "FC2-PPV 4876366.mp4/seg-1.ts"),
        ExoPlayer/okhttp 系播放器(影视仓/TVBox)遇到空格会直接抛异常, 必须转 %20。
        """
        out = []
        for ln in raw.splitlines():
            line = ln.strip()
            if not line or line.startswith("#"):
                out.append(ln)
                continue
            if line.startswith(("http://", "https://")):
                u = line.replace(" ", "%20")
            else:
                u = urljoin(base, line).replace(" ", "%20")
            if ".m3u8" in u.split("?")[0].lower():
                u = "proxy://do=m3u8&url=" + quote(u)
            out.append(u)
        return "\n".join(out)

    def localProxy(self, param):
        # HLS 清洗代理: 播放 URL 形如 proxy://do=m3u8&url=<m3u8地址>
        if param.get("do") == "m3u8":
            try:
                # 框架解析 proxy:// 时可能已解码一次 query; 这里 unquote 后再把空格还原为
                # %20, 保证幂等(无论解码与否, 最终都是 %20 编码的 URL)
                url = unquote(str(param.get("url") or "").strip()).replace(" ", "%20")
                if not url.startswith(("http://", "https://")):
                    return [404, "text/plain", b""]
                r = requests.get(url, headers={"Referer": EMBED_HOST + "/",
                                               "User-Agent": self.headers.get("User-Agent", DEFAULT_UA)},
                                 timeout=15, verify=False)
                if r.status_code != 200:
                    return [404, "text/plain", b""]
                cleaned = self._clean_m3u8(r.text, url)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            except Exception:
                return [404, "text/plain", b""]
        # 图片防盗链代理(兜底): 直接用不了封面时由框架调用
        url = str(param.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return [404, "text/plain", b""]
        try:
            r = requests.get(url, headers={"Referer": self.host + "/",
                                           "User-Agent": self.headers.get("User-Agent", DEFAULT_UA)},
                             timeout=15, verify=False)
            return [200, r.headers.get("Content-Type", "image/jpeg"), r.content]
        except Exception:
            gif = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
            return [200, "image/gif", gif]


# ── 直接调用入口: 不依赖影视框架, 单独运行本文件也能爬 ──
try:
    _spider = Spider()
except Exception:
    _spider = None


def cf_fetch(url, headers=None, timeout=15, verify=False):
    """直接调用: GET 页面文本(自动 Cloudflare 绕过)。"""
    if _spider is None:
        return ""
    return _spider._fetch(url, timeout=timeout)


def cf_post(url, data=None, json=None, headers=None, timeout=15, verify=False):
    """直接调用: POST 响应文本。"""
    if _spider is None:
        return ""
    resp = _spider._request("POST", url, data=data, json=json, timeout=timeout)
    return resp.text if resp is not None else ""


def cf_request(method, url, data=None, json=None, headers=None, timeout=15, verify=False, retry=2):
    """直接调用: 任意方法请求, 返回 response 对象。"""
    if _spider is None:
        return None
    return _spider._request(method, url, data=data, json=json, headers=headers,
                            timeout=timeout, retry=retry)


def cf_clear_cache():
    """清空已缓存的 Cloudflare 绕过凭证。"""
    if _spider is not None:
        _spider._cf_cache.clear()


if __name__ == '__main__':
    import sys
    sp = Spider()
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    if kw:
        print("搜索:", kw)
        r = sp.searchContent(kw, False)
        for v in r["list"][:5]:
            print(" ", v)
        if r["list"]:
            d = sp.detailContent([r["list"][0]["vod_id"]])
            print("详情:", json.dumps(d, ensure_ascii=False)[:500])
            pu = d.get("list", [{}])[0].get("vod_play_url", "")
            print("播放地址:", pu)
    else:
        r = sp.homeVideoContent()
        print("首页视频数:", len(r["list"]))
        for v in r["list"][:5]:
            print(" ", v)
        if r["list"]:
            d = sp.detailContent([r["list"][0]["vod_id"]])
            print("详情:", json.dumps(d, ensure_ascii=False)[:500])
            pu = d.get("list", [{}])[0].get("vod_play_url", "")
            print("播放地址:", pu)
