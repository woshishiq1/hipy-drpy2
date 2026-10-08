# -*- coding: utf-8 -*-
# 夜社 yeshex.com Spider —— 影视仓/OK影视/WebHomeTV/PickTV 四壳通用

import re
import json
import base64
import time

try:
    from urllib.parse import quote, urljoin, unquote
    from urllib.request import Request, urlopen
except Exception:
    try:
        from urllib import quote, urljoin, unquote
        from urllib2 import Request, urlopen
    except Exception:
        quote = urljoin = unquote = None
        Request = urlopen = None

BASE = "https://xn--9hsjt4-9k8ope792un7wa.hnsxdnyjyjcyjfkzx.org:7982"
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")
TIMEOUT = 20
RETRY = 2

# 视频/动漫/有声 类目 (mid=1, 全部可经 /play/ 播放)
CATS = [
    ("2", "视频"),
    ("13", "AI短剧"),
    ("11", "国产视频"),
    ("12", "日本AV"),
    ("14", "欧美无码"),
    ("35", "韩国BJ"),
    ("1", "动漫"),
    ("7", "同人作品"),
    ("8", "动画卡通"),
    ("10", "3D动漫"),
    ("9", "中文动漫"),
    ("32", "里番"),
    ("33", "泡面番"),
    ("3", "有声"),
    ("15", "有声小说"),
    ("16", "淫词艳曲"),
    ("17", "激情骚麦"),
]
# 首页区块顺序 (与站点首页模块一致)
HOME_TIDS = ["13", "11", "12", "2", "1", "3"]
# 图片画廊类目 (漫画/写真, 非视频, 不列入)
_GALLERY_TIDS = {"4", "5", "18", "19", "20", "21", "22", "23", "24", "31", "34"}

_PAGE_RE = re.compile(r'var a="([^"]+)"')


class _Http(object):
    """urllib 降级层: 统一 UA + 重试"""
    _ua = UA
    _timeout = TIMEOUT

    def _open(self, url, data=None):
        hdr = {"User-Agent": self._ua, "Accept": "*/*"}
        req = Request(url, data=data, headers=hdr)
        return urlopen(req, timeout=self._timeout)

    def get_bytes(self, url, retry=RETRY):
        last = None
        for i in range(retry + 1):
            try:
                return self._open(url).read()
            except Exception as e:
                last = e
                if i < retry:
                    time.sleep(1 + i)
        raise last

    def get(self, url, retry=RETRY):
        raw = self.get_bytes(url, retry)
        if isinstance(raw, bytes):
            return raw.decode("utf-8", "replace")
        return raw


class Spider(object):
    def __init__(self):
        self.http = _Http()
        self.s = self.session = self.sess = self.http
        self.ext = {}
        # 类级缓存: play_url -> (m3u8, 过期时间) / detail_url -> 解析结果
        if not hasattr(self, "_play_cache"):
            self._play_cache = {}
        if not hasattr(self, "_page_cache"):
            self._page_cache = {}

    # ---------- 加载契约 ----------
    def getDependence(self):
        return []

    def init(self, extend=""):
        try:
            if isinstance(extend, dict):
                self.ext = extend
            elif isinstance(extend, str) and extend:
                self.ext = {"ext": extend}
        except Exception:
            self.ext = {}
        self.s = self.session = self.sess = self.http
        return None

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def action(self, action):
        return None

    # ---------- 内部工具 ----------
    def _decode_page(self, text):
        """MacCMS base64 包裹解包, 无包裹原样返回"""
        m = _PAGE_RE.search(text or "")
        if m:
            try:
                return base64.b64decode(m.group(1)).decode("utf-8", "replace")
            except Exception:
                return text
        return text

    def _fetch_page(self, url):
        """带缓存的页面抓取(解码后)"""
        now = time.time()
        hit = self._page_cache.get(url)
        if hit and hit[1] > now:
            return hit[0]
        try:
            raw = self.http.get(url)
        except Exception:
            return ""
        txt = self._decode_page(raw)
        if len(self._page_cache) > 200:
            self._page_cache.clear()
        self._page_cache[url] = (txt, now + 120)
        return txt

    def _card(self, href, title, pic, remark=""):
        return {"vod_id": href, "vod_name": title, "vod_pic": pic,
                "vod_remarks": remark}

    def _parse_cards(self, t):
        """从(解码后)HTML 提取 /play/ 卡片列表"""
        out = []
        for m in re.finditer(
                r'<a href="(/play/\d+/1/1\.html)"[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
                t, re.S):
            href, title, inner = m.group(1), m.group(2).strip(), m.group(3)
            pic = ""
            im = re.search(r'<img[^>]*src="([^"]+)"', inner)
            if im:
                pic = im.group(1)
            if not pic.startswith("http"):
                pic = urljoin(BASE, pic)
            remark = ""
            tm = re.search(r'<div class="time">([^<]+)</div>', inner)
            if tm:
                remark = tm.group(1).strip()
            out.append(self._card(href, title, pic, remark))
        return out

    def _ajax_list(self, tid, pg):
        """AJAX 列表接口, 返回 (items, pagecount, total)"""
        url = ("%s/index.php/ajax/data?mid=1&tid=%s&page=%s&limit=30"
               % (BASE, tid, pg))
        try:
            raw = self.http.get(url)
            d = json.loads(raw)
        except Exception:
            return [], 1, 0
        lst = d.get("list") or []
        items = []
        for it in lst:
            vid = it.get("vod_id")
            if not vid:
                continue
            remark = (it.get("vod_remarks") or "").strip()
            if not remark:
                total = it.get("vod_total")
                try:
                    if int(total) > 1:
                        remark = "%s集" % total
                except Exception:
                    pass
            items.append(self._card(
                "/play/%s/1/1.html" % vid,
                (it.get("vod_name") or "").strip(),
                it.get("vod_pic") or "",
                remark))
        return items, int(d.get("pagecount") or 1), int(d.get("total") or 0)

    def _type_page_cards(self, tid):
        """HTML 分类页兜底 (静态 120 条, 不分页)"""
        t = self._fetch_page("%s/type/%s.html" % (BASE, tid))
        return self._parse_cards(t)

    # ---------- 首页 ----------
    def homeContent(self, filter=None):
        result = {"class": [{"type_id": tid, "type_name": name}
                            for tid, name in CATS], "list": []}
        for tid in HOME_TIDS:
            items, _, _ = self._ajax_list(tid, 1)
            result["list"].extend(items[:15])
        if not result["list"]:
            for tid in HOME_TIDS:
                result["list"].extend(self._type_page_cards(tid)[:15])
        # 分类筛选 (与万奶园一致: 不依赖站点侧过滤, 由壳端用 tid 直查)
        filters = {}
        for tid, name in CATS:
            filters[tid] = [{
                "key": "tid", "name": "分类",
                "value": [{"n": n, "v": t} for t, n in CATS],
            }]
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        return {"list": self.homeContent()["list"]}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        tid = str(tid)
        if tid in _GALLERY_TIDS or tid in ("6", "25", "26", "27", "28", "29", "30"):
            return {"list": [], "page": pg, "pagecount": 1, "limit": 30, "total": 0}
        items, pagecount, total = self._ajax_list(tid, pg)
        if not items:
            items = self._type_page_cards(tid)
            pagecount = 1
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": 30, "total": total}

    # ---------- 详情 ----------
    def _extract_id(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        ids = str(ids)
        if "/novel/" in ids:
            return None
        m = re.search(r"/play/(\d+)/", ids)
        if m:
            return m.group(1)
        m = re.search(r"/(\d+)\.html", ids)
        if m:
            return m.group(1)
        m = re.search(r"\d+", ids)
        return m.group(0) if m else None

    def detailContent(self, ids):
        vid = self._extract_id(ids)
        if not vid:
            return {"list": []}
        page_url = "%s/play/%s/1/1.html" % (BASE, vid)
        t = self._fetch_page(page_url)
        if not t:
            return {"list": []}
        # player 配置
        pm = re.search(r'var player_aaaa=(\{.*?\})</script>', t, re.S)
        pdata = {}
        if pm:
            try:
                pdata = json.loads(pm.group(1))
            except Exception:
                pdata = {}
        vd = pdata.get("vod_data") or {}
        # 标题 (module-info-heading 下 h1)
        name = ""
        mh = re.search(r'module-info-heading.*?<h1>([^<]+)</h1>', t, re.S)
        if mh:
            name = mh.group(1).strip()
        name = re.sub(r"\s*-\s*第\d+[集话]\s*$", "", name)
        if not name:
            name = (vd.get("vod_name") or "").strip()
        # 简介
        content = ""
        mb = re.search(r'<div class="blurb">(.*?)</div>', t, re.S)
        if mb:
            content = re.sub(r"<[^>]+>", "", mb.group(1)).strip()
        # 封面
        pic = (vd.get("vod_pic") or "").strip()
        if not pic:
            mi = re.search(r'<img[^>]*src="(https://[^"]+)"', t)
            if mi:
                pic = mi.group(1)
        # 选集
        episodes = []
        ci = t.find('<div class="chpterlist">')
        if ci != -1:
            for em in re.finditer(
                    r'<a href="(/play/%s/1/\d+\.html)"[^>]*class="link"[^>]*>([^<]+)</a>'
                    % vid, t[ci:ci + 60000]):
                ep_url, ep_name = em.group(1), em.group(2).strip()
                if (ep_url, ep_name) not in episodes:
                    episodes.append((ep_url, ep_name))
        if not episodes:
            episodes = [("/play/%s/1/1.html" % vid, "第1集")]
        vod_play_url = "#".join("%s$%s%s" % (n, BASE, u) for u, n in episodes)
        cls = (vd.get("vod_class") or "").strip()
        if not cls:
            mc = re.search(r'module-info-tag-link[^>]*>.*?<a href="[^"]+">([^<]+)</a>',
                           t, re.S)
            if mc:
                cls = mc.group(1).strip()
        detail = {
            "vod_id": page_url,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_class": cls,
            "vod_play_from": "夜社",
            "vod_play_url": vod_play_url,
        }
        return {"list": [detail]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        kw = quote(key or "")
        if pg == 1:
            url = "%s/vod/search/wd/%s.html" % (BASE, kw)
        else:
            url = "%s/vod/search/page/%d/wd/%s.html" % (BASE, pg, kw)
        t = self._fetch_page(url)
        items = self._parse_cards(t)
        # 搜索分页: 从页脚取最大页码
        pagecount = 1
        if items:
            pages = [int(x) for x in re.findall(r'page/(\d+)/wd/', t)]
            if pages:
                pagecount = max(pages)
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": 20, "total": len(items)}

    # ---------- 播放 ----------
    def playerContent(self, flag, ids, vipFlags=None):
        ids = str(ids or "")
        if not re.search(r"/play/\d+/\d+/\d+\.html", ids):
            m = re.search(r"(\d+)", ids)
            if not m:
                return {"parse": 0, "url": ""}
            ids = "/play/%s/1/1.html" % m.group(1)
        page_url = "%s%s" % (BASE, ids) if ids.startswith("/") else ids
        now = time.time()
        hit = self._play_cache.get(ids)
        if hit and hit[1] > now:
            return {"parse": 0, "url": hit[0],
                    "header": {"User-Agent": UA, "Referer": BASE},
                    "format": "application/x-mpegURL"}
        t = self._fetch_page(page_url)
        m = re.search(r'var player_aaaa=(\{.*?\})</script>', t, re.S)
        if not m:
            return {"parse": 0, "url": ""}
        try:
            p = json.loads(m.group(1))
        except Exception:
            return {"parse": 0, "url": ""}
        u = (p.get("url") or "").strip()
        if not u:
            return {"parse": 0, "url": ""}
        if u.startswith("/"):
            u = urljoin(BASE, u)
        if len(self._play_cache) > 300:
            self._play_cache.clear()
        self._play_cache[ids] = (u, now + 3600)
        return {"parse": 0, "url": u,
                "header": {"User-Agent": UA, "Referer": BASE},
                "format": "application/x-mpegURL"}

    # ---------- 本地代理 (兜底) ----------
    def localProxy(self, param):
        param = param or ""
        url = param
        if "=" in param:
            try:
                kv = {}
                for seg in param.split("&"):
                    if "=" in seg:
                        k, v = seg.split("=", 1)
                        kv[k] = v
                url = kv.get("url") or kv.get("do") or url
            except Exception:
                pass
        try:
            url = base64.b64decode(url).decode("utf-8", "replace")
        except Exception:
            pass
        if not url.startswith("http"):
            url = BASE + url
        try:
            raw = self.http.get_bytes(url)
        except Exception:
            return [404, "text/plain", b"", {}]
        mime = "application/vnd.apple.mpegurl" if "m3u8" in url else "application/octet-stream"
        if "m3u8" in url:
            try:
                txt = raw.decode("utf-8", "replace")
                lines = []
                for line in txt.splitlines():
                    if line and not line.startswith("#"):
                        line = urljoin(url, line)
                    lines.append(line)
                raw = "\n".join(lines).encode("utf-8")
            except Exception:
                pass
        return [200, mime, raw, {}]
