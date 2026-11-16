# coding=utf-8
"""
绿色影视 www.lvsc168.com | TVBox Python 爬虫
站点: myui 模板 + MacCMS 二次开发
关键:
  - 分类严格按站点主导航 5 个: 电影1 / 电视剧2 / 综艺3 / 动漫4 / 短剧26
  - 子分类（动作片5… / 大陆剧13…）作为「类型」筛选维度，不单独占分类
  - 分类列表 /frim/{tid}-{page}.html（48 条/页，page=1 省略）
  - 筛选 /search.php?searchtype=5&tid=&area=&year=&yuyan=&order=&page=N
  - 详情 /movie/{id}.html，播放 /play/{id}-{sid}-{nid}.html
  - 播放地址藏在 base64decode("...") 里，需解码
  - 线路按 nav-tabs 出现顺序与 playlist 编号配对（编号顺序 ≠ 显示顺序）
"""
import re
import sys
import json
import time
import base64
import urllib.parse

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=10, pool_maxsize=10, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[lvsc]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://www.lvsc168.com"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"

DEFAULT_PIC = HOST + "/templets/default/images/img/load.png"

PAGE_SIZE = 48
SEARCH_SIZE = 20

# ------------------------------------------------------------------ 分类
# 站点顶部导航只有这 5 个，严格对齐，不多加
CLASSES = [
    {"type_id": "1",  "type_name": "电影"},
    {"type_id": "2",  "type_name": "电视剧"},
    {"type_id": "3",  "type_name": "综艺"},
    {"type_id": "4",  "type_name": "动漫"},
    {"type_id": "26", "type_name": "短剧"},
]

# 站点分类页左侧的「子分类」块，作为「类型」筛选维度（换 tid）
SUBTYPE = {
    "1": [("动作片", "5"), ("爱情片", "6"), ("科幻片", "7"), ("恐怖片", "8"),
          ("战争片", "9"), ("喜剧片", "10"), ("纪录片", "11"), ("剧情片", "12")],
    "2": [("大陆剧", "13"), ("港台剧", "14"), ("欧美剧", "15"), ("日韩剧", "16"),
          ("泰剧", "27")],
}

FILTER_AREA = ["大陆", "香港", "台湾", "日本", "韩国", "欧美", "泰国", "其他"]

# 站方年份块默认只列到 2010，其余折叠在「more」里；实测 year=1950~2026 全部有效
FILTER_YEAR = [str(y) for y in range(2026, 1949, -1)]

FILTER_LANG = ["国语", "粤语", "英语", "日语", "韩语", "泰语", "法语"]

FILTER_ORDER = [("时间", "time"), ("人气", "hit"), ("评分", "commend")]

# ------------------------------------------------------------------ 正则
_RE_THUMB_A = re.compile(r'<a\b[^>]*class="[^"]*myui-vodlist__thumb[^"]*"[^>]*>', re.I)
_RE_PIC_TEXT = re.compile(r'<span class="pic-text[^"]*">([\s\S]*?)</span>', re.I)
_RE_PIC_TAG = re.compile(r'<span class="pic-tag[^"]*"[^>]*>([\s\S]*?)</span>', re.I)
_RE_TITLE_A = re.compile(r'<h4[^>]*class="[^"]*title[^"]*"[^>]*>[\s\S]{0,150}?<a\b[^>]*>([\s\S]*?)</a>', re.I)
_RE_ACTOR_P = re.compile(r'<p class="text[^"]*"[^>]*>([\s\S]*?)</p>', re.I)
_RE_MID = re.compile(r'/movie/(\d+)\.html', re.I)
_RE_RANK_LI = re.compile(r'<a class="top-line-dot[^"]*"\s+href="([^"]+)"[^>]*title="([^"]*)"', re.I)
_RE_NUM = re.compile(r'<a class="btn btn-warm">\s*(\d+)\s*/\s*(\d+)\s*</a>')
_RE_TAB = re.compile(r'<li><a href="#playlist(\d+)"[^>]*>([^<]*)</a></li>', re.I)
_RE_HEAD = re.compile(r'<div class="myui-panel__head[^"]*"[^>]*>', re.I)
_RE_NOW = re.compile(r'var\s+now\s*=\s*base64decode\("([^"]*)"\)', re.I)
_RE_EXT = re.compile(r'\.(m3u8|mp4|flv|mkv|ts|avi|mov|rmvb|webm)(\?|#|$)', re.I)


def _attr(tag, name):
    m = re.search(r'\b' + name + r'\s*=\s*"([^"]*)"', tag, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b" + name + r"\s*=\s*'([^']*)'", tag, re.I)
    return m.group(1).strip() if m else ""


def _html(s):
    if not s:
        return ""
    s = re.sub(r'<[^>]+>', '', s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
          .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
          .replace("&ldquo;", "“").replace("&rdquo;", "”")
          .replace("&hellip;", "…").replace("&mdash;", "—"))
    s = re.sub(r'&[a-zA-Z#0-9]{2,8};', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def _pic(u):
    u = (u or "").strip()
    if not u:
        return DEFAULT_PIC
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    if u.startswith("/"):
        return HOST + u
    return DEFAULT_PIC


class Spider(Spider):

    # ------------------------------------------------------------ 基础
    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self._session = None
        self.header = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": HOST + "/",
        }
        self._last_req = 0.0
        self._home_html = ""

    def getName(self):
        return "绿色影视"

    def init(self, extend=""):
        return

    def isVideoFormat(self, url):
        return bool(url and _RE_EXT.search(url))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        return

    def close(self):
        try:
            if self._session is not None:
                self._session.close()
        except Exception:
            pass
        self._session = None

    # ------------------------------------------------------------ 网络
    def _fetch(self, url):
        import requests as _rq
        if self._session is None:
            self._session = _rq.Session()
            self._session.verify = False
            try:
                import urllib3
                urllib3.disable_warnings()
            except Exception:
                pass
        gap = time.time() - self._last_req
        if gap < 0.25:
            time.sleep(0.25 - gap)
        for i in range(3):
            self._last_req = time.time()
            try:
                r = self._session.get(url, headers=self.header, timeout=25, verify=False)
                if r.status_code == 200:
                    r.encoding = 'utf-8'
                    if r.text and len(r.text) > 500:
                        return r.text
            except Exception as e:
                self.log("req err %s %s" % (url, e))
            if i < 2:
                time.sleep(0.6 + i * 0.6)
        return ""

    # ------------------------------------------------------------ 卡片
    def _scope(self, h, pat):
        """把解析范围限定到指定 ul 容器，避免抓到侧栏/推荐位"""
        m = re.search(pat, h or "", re.I)
        if not m:
            return h or ""
        start = m.end()
        end = h.find("</ul>", start)
        if end < 0:
            return h[start:]
        return h[start:end]

    def _cards(self, h):
        if not h:
            return []
        h = re.sub(r'<div class="myui-content__thumb">[\s\S]*?</div>', '', h, count=1)
        out = []
        seen = set()
        for m in _RE_THUMB_A.finditer(h):
            tag = m.group(0)
            href = _attr(tag, "href")
            sm = _RE_MID.search(href)
            if not sm:
                continue
            vid = sm.group(1)
            if vid in seen:
                continue
            seg = h[m.end(): m.end() + 1500]
            name = _html(_attr(tag, "title"))
            if not name:
                tm = _RE_TITLE_A.search(seg)
                name = _html(tm.group(1)) if tm else ""
            if not name:
                continue
            seen.add(vid)
            pic = _attr(tag, "data-original") or _attr(tag, "data-src") or _attr(tag, "src")
            rm = _RE_PIC_TEXT.search(seg)
            remark = _html(rm.group(1)) if rm else ""
            tg = _RE_PIC_TAG.search(seg)
            score = _html(tg.group(1)) if tg else ""
            score = re.sub(r'[^\d.]', '', score)
            am = _RE_ACTOR_P.search(seg)
            actors = _html(am.group(1)) if am else ""
            actors = re.sub(r'^主演\s*[:：]\s*', '', actors)
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": _pic(pic),
                "vod_remarks": remark,
                "vod_actor": actors,
                "vod_score": score,
            })
        return out

    def _rank(self, seg):
        out = []
        seen = set()
        for href, title in _RE_RANK_LI.findall(seg):
            sm = _RE_MID.search(href)
            if not sm:
                continue
            vid = sm.group(1)
            if vid in seen:
                continue
            name = _html(title)
            if not name:
                continue
            seen.add(vid)
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": DEFAULT_PIC,
                "vod_remarks": "",
            })
        return out

    def _pagecount(self, h, pg):
        m = _RE_NUM.search(h or "")
        if m:
            try:
                return max(1, int(m.group(2)))
            except Exception:
                pass
        return pg

    # ------------------------------------------------------------ 首页
    def homeContent(self, filter):
        result = {}
        result["class"] = [{"type_id": c["type_id"], "type_name": c["type_name"]}
                           for c in CLASSES]
        if filter:
            filters = {}
            for c in CLASSES:
                tid = c["type_id"]
                fl = []
                sub = SUBTYPE.get(tid)
                if sub:
                    vals = [{"n": "全部", "v": ""}]
                    for nm, st in sub:
                        vals.append({"n": nm, "v": st})
                    fl.append({"key": "类型", "name": "类型", "value": vals})
                vals = [{"n": "全部", "v": ""}]
                for a in FILTER_AREA:
                    vals.append({"n": a, "v": a})
                fl.append({"key": "地区", "name": "地区", "value": vals})

                vals = [{"n": "全部", "v": ""}]
                for y in FILTER_YEAR:
                    vals.append({"n": y, "v": y})
                fl.append({"key": "年份", "name": "年份", "value": vals})

                vals = [{"n": "全部", "v": ""}]
                for l in FILTER_LANG:
                    vals.append({"n": l, "v": l})
                fl.append({"key": "语言", "name": "语言", "value": vals})

                vals = [{"n": "默认", "v": ""}]
                for nm, ov in FILTER_ORDER:
                    vals.append({"n": nm, "v": ov})
                fl.append({"key": "排序", "name": "排序", "value": vals})

                filters[tid] = fl
            result["filters"] = filters
        return result

    def homeVideoContent(self):
        h = self._home_html or self._fetch(HOST + "/")
        if h:
            self._home_html = h
        if not h:
            return {"list": []}

        heads = []
        for m in _RE_HEAD.finditer(h):
            seg = h[m.end(): m.end() + 700]
            t = re.search(r'<h3[^>]*>([\s\S]*?)</h3>', seg)
            if not t:
                continue
            name = re.sub(r'\s+', ' ', _html(t.group(1))).strip()
            if not name:
                continue
            heads.append((m.end() + t.end(), name))

        groups = []
        used = set()
        for i, (start, name) in enumerate(heads):
            end = heads[i + 1][0] if i + 1 < len(heads) else len(h)
            block = h[start:end]
            items = self._cards(block)
            extra = self._rank(block)
            if extra:
                have = set(x["vod_id"] for x in items)
                for x in extra:
                    if x["vod_id"] not in have:
                        items.append(x)
                        have.add(x["vod_id"])
            if not items:
                continue
            gname = name
            if gname in used:
                gname = "%s %d" % (name, i + 1)
            used.add(gname)
            groups.append({"vod_name": gname, "vod_id": "", "vod_list": items})

        return {"list": groups}

    # ------------------------------------------------------------ 分类
    def _cat_url(self, tid, pg):
        if pg <= 1:
            return HOST + "/frim/%s.html" % tid
        return HOST + "/frim/%s-%d.html" % (tid, pg)

    def _search_url(self, tid, ext, pg):
        params = [("searchtype", "5"), ("tid", tid)]
        if ext.get("地区"):
            params.append(("area", ext["地区"]))
        if ext.get("年份"):
            params.append(("year", ext["年份"]))
        if ext.get("语言"):
            params.append(("yuyan", ext["语言"]))
        if ext.get("排序"):
            params.append(("order", ext["排序"]))
        if pg > 1:
            params.append(("page", str(pg)))
        qs = "&".join("%s=%s" % (k, urllib.parse.quote(str(v))) for k, v in params)
        return HOST + "/search.php?" + qs

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or "1")
        ext = dict(extend or {})
        # 「类型」维度是切子分类，换 tid
        if ext.get("类型"):
            tid = str(ext["类型"])
        ext.pop("类型", None)

        use_search = bool(ext.get("地区") or ext.get("年份") or ext.get("语言") or ext.get("排序"))
        if use_search:
            url = self._search_url(tid, ext, pg)
        else:
            url = self._cat_url(tid, pg)

        h = self._fetch(url)
        scoped = self._scope(h, r'<ul class="myui-vodlist__media[^"]*"[^>]*>')
        if scoped == h:
            scoped = self._scope(h, r'<ul class="myui-vodlist clearfix"[^>]*>')
        cards = self._cards(scoped)
        pc = self._pagecount(h, pg)
        return {
            "list": cards,
            "page": pg,
            "pagecount": pc,
            "limit": PAGE_SIZE,
            "total": len(cards) * pc if cards else 0,
        }

    # ------------------------------------------------------------ 详情
    def _field(self, h, label):
        m = re.search(r'<span class="text-muted[^"]*">\s*' + label + r'\s*[:：]\s*</span>([\s\S]*?)(?=</p>|<span class="text-muted)', h)
        if not m:
            return ""
        seg = m.group(1)
        links = re.findall(r'<a\b[^>]*>([\s\S]*?)</a>', seg, re.I)
        if links:
            vals = [_html(x) for x in links]
            vals = [x for x in vals if x]
            if vals:
                return ",".join(vals)
        return _html(seg)

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        m = _RE_MID.search(str(vid or ""))
        if m:
            vid = m.group(1)
        vid = re.sub(r'\D', '', str(vid or ""))
        if not vid:
            return {"list": []}

        h = self._fetch(HOST + "/movie/%s.html" % vid)
        if not h:
            return {"list": []}

        # 标题 / 副标题（副标题在 h1 的 font 里）
        t = re.search(r'<h1 class="title[^"]*">([\s\S]*?)</h1>', h, re.I)
        title_raw = t.group(1) if t else ""
        remark = ""
        fm = re.search(r'<font[^>]*>([\s\S]*?)</font>', title_raw, re.I)
        if fm:
            remark = _html(fm.group(1))
            title_raw = title_raw.replace(fm.group(0), "")
        name = _html(title_raw)
        if not name:
            return {"list": []}

        # 竖图
        pic = ""
        tm = re.search(r'<div class="myui-content__thumb">([\s\S]*?)</div>', h, re.I)
        if tm:
            im = re.search(r'<img\b[^>]*>', tm.group(1), re.I)
            if im:
                pic = (_attr(im.group(0), "data-original")
                       or _attr(im.group(0), "data-src")
                       or _attr(im.group(0), "src"))
        if not pic:
            im = re.search(r'<img\b[^>]*data-original="([^"]+)"', h, re.I)
            if im:
                pic = im.group(1)

        # 评分
        score = ""
        sm = re.search(r'<span class="branch">\s*([\d.]+)\s*</span>', h, re.I)
        if sm:
            score = sm.group(1)

        cat = self._field(h, "分类")
        area = self._field(h, "地区")
        year = self._field(h, "年份")
        lang = self._field(h, "语言")
        actor = self._field(h, "主演")
        director = self._field(h, "导演")

        # 简介：优先 #jq 完整剧情
        content_body = ""
        jq = h.find('id="jq"')
        if jq > 0:
            blk = h[jq: jq + 12000]
            pm = re.search(r'<div class="tab-content myui-panel_bd">([\s\S]*?)</div>', blk, re.I)
            if pm:
                content_body = _html(pm.group(1))
        if len(content_body) < 12:
            dm = re.search(r'<p class="desc[^"]*">([\s\S]*?)</p>', h, re.I)
            if dm:
                seg = re.sub(r'<a href="#jq">[\s\S]*?</a>', '', dm.group(1))
                seg = re.sub(r'<span class="left text-muted">[\s\S]*?</span>', '', seg)
                content_body = _html(seg)
        if not content_body:
            bits = []
            if year and area:
                bits.append("%s年%s出品的%s" % (year, area, cat or "影视作品"))
            elif year:
                bits.append("%s年出品的%s" % (year, cat or "影视作品"))
            if director:
                bits.append("由%s执导" % director)
            if actor:
                bits.append("由%s等主演" % actor)
            if remark:
                bits.append("当前更新至%s" % remark)
            content_body = "，".join(bits) if bits else "暂无简介"
        content = INTRO_PREFIX + "\n" + content_body

        # 线路：nav-tabs 显示顺序 → 对应 playlist 编号块
        play_from = []
        play_url = []
        tabs = _RE_TAB.findall(h)
        for num, label in tabs:
            label = _html(label) or ("线路%s" % num)
            blk_m = re.search(r'<div id="playlist%s"[\s\S]*?</div>' % re.escape(num), h, re.I)
            if not blk_m:
                continue
            blk = blk_m.group(0)
            um = re.search(r'<ul class="myui-content__list[^"]*"[^>]*>([\s\S]*?)</ul>', blk, re.I)
            if not um:
                continue
            eps = []
            for href, tx in re.findall(r'<a\b[^>]*href="([^"]*)"[^>]*title="([^"]*)"', um.group(1), re.I):
                if "/play/" not in href:
                    continue
                nm = _html(tx) or "播放"
                eps.append("%s$%s" % (nm, href))
            if not eps:
                # 属性顺序不定的兜底
                for a in re.finditer(r'<a\b[^>]*>([\s\S]*?)</a>', um.group(1), re.I):
                    tag = a.group(0)
                    href = _attr(tag, "href")
                    if "/play/" not in href:
                        continue
                    nm = _html(_attr(tag, "title")) or _html(a.group(1)) or "播放"
                    eps.append("%s$%s" % (nm, href))
            if not eps:
                continue
            if label in play_from:
                label = "%s%s" % (label, num)
            play_from.append(label)
            play_url.append("#".join(eps))

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": _pic(pic),
            "vod_remarks": remark,
            "type_name": cat,
            "vod_year": year,
            "vod_area": area,
            "vod_lang": lang,
            "vod_actor": actor,
            "vod_director": director,
            "vod_score": score,
            "vod_content": content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    # ------------------------------------------------------------ 播放
    def playerContent(self, flag, id, vipFlags):
        s = str(id or "").strip()
        if s.startswith("http"):
            url = s
        elif s.startswith("/"):
            url = HOST + s
        elif s.endswith(".html"):
            url = HOST + "/play/" + s
        else:
            url = HOST + "/play/%s.html" % s
        h = self._fetch(url)
        header = json.dumps({"User-Agent": UA, "Referer": HOST + "/"})

        u = ""
        m = _RE_NOW.search(h or "")
        if m and m.group(1):
            try:
                u = base64.b64decode(m.group(1) + "===").decode("utf-8", "ignore").strip()
            except Exception:
                u = ""
        if not u:
            # 兜底：老版 player_aaaa
            pm = re.search(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', h or "", re.I)
            if pm:
                try:
                    u = (json.loads(pm.group(1)).get("url") or "").strip()
                except Exception:
                    u = ""
        if not u:
            return {"parse": 1, "playUrl": "", "url": url, "header": header}

        if u.startswith("//"):
            u = "https:" + u
        if not _RE_EXT.search(u):
            u = u.rstrip("/") + "/index.m3u8"
        return {"parse": 0, "playUrl": "", "url": u, "header": header}

    # ------------------------------------------------------------ 搜索
    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg="1"):
        pg = int(pg or 1)
        kw = urllib.parse.quote(str(key or "").strip())
        if not kw:
            return {"list": [], "page": 1, "pagecount": 1, "limit": SEARCH_SIZE, "total": 0}
        url = HOST + "/search.php?searchword=%s" % kw
        if pg > 1:
            url += "&page=%d" % pg
        h = self._fetch(url)
        cards = self._cards(self._scope(h, r'<ul class="myui-vodlist clearfix"[^>]*>'))
        pc = self._pagecount(h, pg)
        if pg > pc:
            cards = []
        elif pc <= pg and len(cards) >= SEARCH_SIZE:
            pc = pg + 1
        return {
            "list": cards,
            "page": pg,
            "pagecount": pc,
            "limit": SEARCH_SIZE,
            "total": len(cards) * pc if cards else 0,
        }
