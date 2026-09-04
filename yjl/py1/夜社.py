# -*- coding: utf-8 -*-
# 夜社 yeshex.com Spider —— 影视仓/OK影视/WebHomeTV/PickTV 四壳通用
# fix1: 保留 query 跟随重定向，避免随机反代丢参数导致列表为空
# fix2: 加入完整分类树(主分类+子分类)，图片(漫画/写真)与小说全部接入

import re
import json
import base64
import time

try:
    from urllib.parse import quote, urljoin, unquote, urlsplit, urlunsplit
    from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
except Exception:
    try:
        from urllib import quote, urljoin, unquote
        from urlparse import urlsplit, urlunsplit
        from urllib2 import Request, urlopen, build_opener, HTTPRedirectHandler
    except Exception:
        quote = urljoin = unquote = None
        urlsplit = urlunsplit = None
        Request = urlopen = build_opener = HTTPRedirectHandler = None

BASE = "https://xn--9hsjt4-9k8ope792un7wa.hnsxdnyjyjcyjfkzx.org:7982"
UA = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36")
TIMEOUT = 20
RETRY = 2


class _KeepQueryRedirect(HTTPRedirectHandler):
    """重定向时保留原始 query，防止反代 Location 丢参数"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit is not None:
            try:
                old = urlsplit(req.full_url)
                new = urlsplit(newurl)
                if not new.query and old.query:
                    newurl = urlunsplit((new.scheme, new.netloc, new.path,
                                         old.query, new.fragment))
            except Exception:
                pass
        return HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, newurl)


# 主分类: (tid, 名称)
MAIN_CATS = [
    ("2", "视频"),
    ("1", "动漫"),
    ("3", "有声"),
    ("4", "漫画"),
    ("5", "写真"),
    ("6", "小说"),
]
# 子分类: 主分类tid -> [(子tid, 名称)]
CHILD_CATS = {
    "2": [("13", "AI短剧"), ("11", "国产视频"), ("12", "日本AV"),
          ("14", "欧美无码"), ("35", "韩国BJ")],
    "1": [("7", "同人作品"), ("8", "动画卡通"), ("10", "3D动漫"),
          ("9", "中文动漫"), ("32", "里番"), ("33", "泡面番")],
    "3": [("15", "有声小说"), ("16", "淫词艳曲"), ("17", "激情骚麦")],
    "4": [("18", "韩国H漫"), ("19", "日本H漫"), ("31", "3D漫画")],
    "5": [("20", "秀人系列"), ("22", "网红COS"), ("21", "机构套图"),
          ("23", "内购私拍"), ("34", "AI绘图"), ("24", "各国套图")],
    "6": [("25", "都市生活"), ("26", "学生校园"), ("27", "家庭乱伦"),
          ("28", "玄幻武侠"), ("29", "系统穿越"), ("30", "同人改编")],
}
# 完整分类列表仅保留主分类, 子分类经主分类的"分类"筛选栏进入
CATS = MAIN_CATS

# 类型判定
NOVEL_TIDS = set(["6"]) | {t for t, _ in CHILD_CATS["6"]}
GALLERY_TIDS = set(["4", "5"]) | {t for t, _ in CHILD_CATS["4"]} | {t for t, _ in CHILD_CATS["5"]}

_PAGE_RE = re.compile(r'var a="([^"]+)"')


class _Http(object):
    """urllib 降级层: 统一 UA + 重试 + 保留 query 跟随重定向"""
    _ua = UA
    _timeout = TIMEOUT
    _opener = None

    @classmethod
    def _get_opener(cls):
        if cls._opener is None:
            if build_opener is not None and HTTPRedirectHandler is not None:
                try:
                    cls._opener = build_opener(_KeepQueryRedirect)
                except Exception:
                    cls._opener = False
            else:
                cls._opener = False
        return cls._opener

    def _open(self, url, data=None):
        hdr = {"User-Agent": self._ua, "Accept": "*/*"}
        req = Request(url, data=data, headers=hdr)
        op = self._get_opener()
        if op:
            try:
                return op.open(req, timeout=self._timeout)
            except TypeError:
                return op.open(req)
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

    def _parse_poster_cards(self, t, href_re):
        """通用 module-poster-item 卡片解析, href_re 为详情链接正则片段"""
        out = []
        for m in re.finditer(
                r'<a href="(%s)"[^>]*title="([^"]+)"[^>]*>(.*?)</a>'
                % href_re, t, re.S):
            href, title, inner = m.group(1), m.group(2).strip(), m.group(3)
            pic = ""
            im = re.search(r'<img[^>]*src="([^"]+)"', inner)
            if im:
                pic = im.group(1)
            if pic and not pic.startswith("http"):
                pic = urljoin(BASE, pic)
            remark = ""
            tm = re.search(r'class="time"[^>]*>([^<]+)<', inner)
            if tm:
                remark = tm.group(1).strip()
            out.append(self._card(href, title, pic, remark))
        return out

    def _ajax_list(self, tid, pg, gallery=False):
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
            if gallery:
                href = "/detail/%s.html" % vid
            else:
                href = "/play/%s/1/1.html" % vid
            items.append(self._card(
                href,
                (it.get("vod_name") or "").strip(),
                it.get("vod_pic") or "",
                remark))
        return items, int(d.get("pagecount") or 1), int(d.get("total") or 0)

    def _type_page_cards(self, tid, gallery=False):
        """HTML 分类页兜底 (静态, 不分页)"""
        if gallery:
            href_re = r"/detail/\d+\.html"
        else:
            href_re = r"/play/\d+/1/1\.html"
        t = self._fetch_page("%s/type/%s.html" % (BASE, tid))
        return self._parse_poster_cards(t, href_re)

    def _novel_cards(self, tid):
        """小说分类页卡片 (/ntype/{tid}.html)"""
        t = self._fetch_page("%s/ntype/%s.html" % (BASE, tid))
        return self._parse_poster_cards(t, r"/novel/\d+\.html")

    # ---------- 首页 ----------
    def homeContent(self, filter=None):
        result = {"class": [{"type_id": tid, "type_name": name}
                            for tid, name in CATS], "list": []}
        for mtid, _mname in MAIN_CATS:
            if mtid in NOVEL_TIDS:
                result["list"].extend(self._novel_cards(mtid)[:12])
            else:
                gallery = mtid in GALLERY_TIDS
                items, _, _ = self._ajax_list(mtid, 1, gallery)
                result["list"].extend(items[:12])
        if not result["list"]:
            for mtid, _mname in MAIN_CATS:
                if mtid in NOVEL_TIDS:
                    result["list"].extend(self._novel_cards(mtid)[:12])
                else:
                    result["list"].extend(
                        self._type_page_cards(mtid, mtid in GALLERY_TIDS)[:12])
        # 主分类 -> 子分类筛选
        filters = {}
        for mtid, _mname in MAIN_CATS:
            value = [{"n": "全部", "v": ""}]
            value += [{"n": n, "v": t} for t, n in CHILD_CATS[mtid]]
            filters[mtid] = [{"key": "tid", "name": "分类", "value": value}]
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
        # 主分类下选择子分类 (filter/extend 均兼容)
        v = None
        if isinstance(extend, dict):
            v = extend.get("tid")
        if not v and isinstance(filter, dict):
            v = filter.get("tid")
        if not v and isinstance(extend, dict):
            for _v in extend.values():
                if _v:
                    v = _v
                    break
        if v:
            tid = str(v)
        if tid in NOVEL_TIDS:
            items = self._novel_cards(tid)
            return {"list": items, "page": pg, "pagecount": 1,
                    "limit": 30, "total": len(items)}
        gallery = tid in GALLERY_TIDS
        items, pagecount, total = self._ajax_list(tid, pg, gallery)
        if not items:
            items = self._type_page_cards(tid, gallery)
            pagecount = 1
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": 30, "total": total}

    # ---------- 详情 ----------
    def _extract_id(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ""
        ids = str(ids)
        m = re.search(r"/(?:play|detail|novel)/(\d+)/", ids)
        if m:
            return m.group(1)
        m = re.search(r"/(\d+)\.html", ids)
        if m:
            return m.group(1)
        m = re.search(r"\d+", ids)
        return m.group(0) if m else None

    def _episodes_from_chpterlist(self, t, link_re):
        """从 chpterlist 容器提取 (url, 名称) 列表"""
        episodes = []
        ci = t.find('<div class="chpterlist">')
        if ci != -1:
            seg = t[ci:ci + 60000]
            for em in re.finditer(
                    r'<a href="(%s)"[^>]*class="link"[^>]*>(.*?)</a>'
                    % link_re, seg):
                ep_url = em.group(1)
                ep_name = re.sub(r"<[^>]+>", "", em.group(2)).strip()
                ep_name = re.sub(r"\(\d+字\)\s*$", "", ep_name).strip()
                if (ep_url, ep_name) not in episodes:
                    episodes.append((ep_url, ep_name))
        return episodes

    def _detail_common(self, page_url, vod_from, vod_player="", vod_tag=""):
        """抓详情页并解析标题/简介/封面/选集, 返回 detail 或 None"""
        t = self._fetch_page(page_url)
        if not t:
            return None
        # player 配置 (视频页才有)
        pm = re.search(r'var player_aaaa=(\{.*?\})</script>', t, re.S)
        pdata = {}
        if pm:
            try:
                pdata = json.loads(pm.group(1))
            except Exception:
                pdata = {}
        vd = pdata.get("vod_data") or {}
        # 标题
        name = ""
        mi = re.search(r'module-image-info.*?<h1>([^<]+)</h1>', t, re.S)
        if mi:
            name = mi.group(1).strip()
        if not name:
            mh = re.search(r'module-info-heading.*?<h1>([^<]+)</h1>', t, re.S)
            if mh:
                name = mh.group(1).strip()
        if not name:
            name = (vd.get("vod_name") or "").strip()
        name = re.sub(r"\s*-\s*第\d+[集话]\s*$", "", name)
        # 简介
        content = ""
        mb = re.search(r'<div class="blurb">(.*?)</div>', t, re.S)
        if mb:
            content = re.sub(r"<[^>]+>", "", mb.group(1)).strip()
        # 封面
        pic = (vd.get("vod_pic") or "").strip()
        if not pic:
            pd = re.search(r'module-image-info[^>]*>.*?data-original="([^"]+)"',
                           t, re.S)
            if pd:
                pic = pd.group(1)
        if not pic:
            mi2 = re.search(r'<img[^>]*src="(https://[^"]+)"', t)
            if mi2:
                pic = mi2.group(1)
        # 选集
        vid = self._extract_id(page_url)
        episodes = self._episodes_from_chpterlist(
            t, r"/play/%s/1/\d+\.html" % vid)
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
            "vod_play_from": vod_from,
            "vod_play_url": vod_play_url,
        }
        if vod_player:
            detail["vod_player"] = vod_player
        if vod_tag:
            detail["vod_tag"] = vod_tag
        return detail

    def detailContent(self, ids):
        vid = self._extract_id(ids)
        if not vid:
            return {"list": []}
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        raw = str(raw or "")
        if "/novel/" in raw:
            detail = self._detail_common(
                "%s/novel/%s.html" % (BASE, vid), "夜社小说",
                vod_player="书", vod_tag="text")
        elif "/detail/" in raw or str(vid) in GALLERY_TIDS:
            detail = self._detail_common(
                "%s/detail/%s.html" % (BASE, vid), "夜社漫画",
                vod_player="画", vod_tag="image")
        else:
            detail = self._detail_common(
                "%s/play/%s/1/1.html" % (BASE, vid), "夜社")
        if detail:
            # 小说选集链接是 /nchpter/, 覆盖默认 /play/
            if "/novel/" in raw and not re.search(r"/nchpter/", detail["vod_play_url"]):
                t = self._fetch_page("%s/novel/%s.html" % (BASE, vid))
                if t:
                    episodes = self._episodes_from_chpterlist(
                        t, r"/nchpter/%s/\d+\.html" % vid)
                    if episodes:
                        detail["vod_play_url"] = "#".join(
                            "%s$%s%s" % (n, BASE, u) for u, n in episodes)
            return {"list": [detail]}
        return {"list": []}

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
        items = self._parse_poster_cards(t, r"/play/\d+/1/1\.html")
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
        # 小说章节: novel:// 协议交给壳的小说阅读器
        if "/nchpter/" in ids:
            url = ids if ids.startswith("http") else BASE + ids
            t = self._fetch_page(url)
            title = ""
            m = re.search(r'module-novel-detail.*?class="title">([^<]+)<', t or "", re.S)
            if m:
                title = m.group(1).strip()
            content = ""
            if t:
                ci = t.find('class="content"')
                if ci != -1:
                    mc = re.search(r'<div class="content">(.*?)</div>',
                                   t[ci:ci + 100000], re.S)
                    if mc:
                        content = re.sub(r"<[^>]+>", "", mc.group(1))
                        content = re.sub(r"&nbsp;", " ", content)
                        content = re.sub(r"\s+", " ", content).strip()
            if content:
                if len(content) > 3000:
                    content = content[:3000] + "..."
                data = json.dumps({"title": title, "content": content},
                                  ensure_ascii=False)
                return {"parse": 0, "url": "novel://" + data}
            return {"parse": 0, "url": ""}
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
        if not t:
            return {"parse": 0, "url": ""}
        m = re.search(r'var player_aaaa=(\{.*?\})</script>', t, re.S)
        if m:
            try:
                p = json.loads(m.group(1))
            except Exception:
                p = {}
            u = (p.get("url") or "").strip()
            if u:
                if u.startswith("/"):
                    u = urljoin(BASE, u)
                if len(self._play_cache) > 300:
                    self._play_cache.clear()
                self._play_cache[ids] = (u, now + 3600)
                return {"parse": 0, "url": u,
                        "header": {"User-Agent": UA, "Referer": BASE},
                        "format": "application/x-mpegURL"}
        # 图库话页: 提取图集容器内全部图片, pics:// 多图浏览
        for cls in ("module-player-cartoon-list", "module-player-pics-list"):
            ci = t.find(cls)
            if ci == -1:
                continue
            start = t.find('>', ci) + 1
            depth = 1
            j = start
            while j < len(t) and depth > 0:
                o = t.find('<div', j)
                c = t.find('</div>', j)
                if o == -1 and c == -1:
                    break
                if o != -1 and (c == -1 or o < c):
                    depth += 1
                    j = o + 4
                else:
                    depth -= 1
                    j = c + 6
            seg = t[start:j]
            imgs = [u for u in re.findall(r'<img[^>]*src="([^"]+)"', seg)
                    if u.startswith("http") and "load.gif" not in u]
            if imgs:
                return {"parse": 0, "url": "pics://" + "&&".join(imgs),
                        "header": {"User-Agent": UA, "Referer": BASE}}
        return {"parse": 0, "url": ""}

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
