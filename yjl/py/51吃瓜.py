#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
51吃瓜网 TVBox 爬虫 - 动态配置版

实现规则：
1. 分类动态获取: class 列表从站点页面解析，结构 [{type_id, type_name, type_extend}]
   type_extend 保留站点扩展字段（站点有筛选下拉时自动解析，无则为空，不硬编码）
2. 筛选动态生成: filters 基于每个分类的 type_extend 动态构建
   (class/area/year/order)，站点扩展字段变化时自动跟随
3. 配置缓存: 新进程强制拉取最新配置；同进程多次调用走内存缓存不重复请求；
   API/页面拉取失败降级 spider_cache.json 兜底，再失败用内置默认
4. 分类顺序: _CLASS_ORDER 偏好表控制，如 ("cbdj","吃瓜热门") 表示 cbdj 紧跟"吃瓜热门"，
   只调顺序不改数据，未提及分类保持原顺序，新分类自动排在后面
5. 子分类拆行: type_extend 单个"类型"筛选子分类超 8 个拆成 class + class_more1 + ...，
   每组在 TVBox 独立一行；categoryContent 里 class_moreN 共享 class 字段，取第一个非空
6. 解析器/播放源动态获取: 详情页 dplayer data-config 实时解析，不硬编码播放源 URL
7. TVBox 协议: homeContent 返回 {class, filters, list};
   categoryContent 接收 (tid, pg, filter, extend) 返回 {page, pagecount, list}
8. 父分类聚合: 顶级导航下拉成为主分类，其子分类转为"类型"筛选；不选筛选时并发
   聚合全部子分类第一页(去重限100)，选中某子分类时直接请求该子分类页(支持翻页)
9. 配置排除: _CLASS_EXCLUDE 按名称从主分类移除父分类，如"官方活动"
"""
import re
import json
import os
import time
import ssl
import concurrent.futures
import urllib.request
import urllib.parse

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object

# 进程级内存缓存: {cache_key: cfg}，同进程多次调用不重复拉配置
_MEM_CACHE = {}


class Spider(BaseSpider):
    # 分类顺序偏好表: ("A","B") 表示分类 A 紧跟分类 B 之后，留空保持站点顺序。
    # A 若是某父分类的子分类，则自动提升为主分类（并从原父分类移除）。
    # 默认: AI成人短剧(cbdj) 提升为主分类，排在"吃瓜热门"之后
    _CLASS_ORDER = [("cbdj", "吃瓜热门")]
    # 从主分类中排除的父分类（按名称匹配），如官方活动
    _CLASS_EXCLUDE = ["官方活动"]
    _CACHE_FILE = "spider_cache.json"

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.name = "51吃瓜"
        # 站点入口候选（自动探测可用域名，对应 /config 的站点入口）
        self._host_candidates = [
            "https://artist.cnmhljju.cc/",
            "https://artist.vgwtswi.xyz/",
            "https://ability.vgwtswi.xyz/",
            "https://am.vgwtswi.xyz/",
        ]
        self.host = self._host_candidates[0].rstrip("/")
        # 图片解密代理（站点图片 AES-CBC 加密，TVBox 无法直接显示）
        self.img_proxy = "https://py.fzcrym.link:1314/bk51_img?u="
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        try:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        except Exception:
            self.ctx = None
        self._cfg = None
        # 父分类聚合结果缓存: {key: (timestamp, videos)}，TTL 5 分钟
        self._agg_cache = {}

    # ---------- 协议基础 ----------
    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(ext in (url or "") for ext in [".m3u8", ".mp4", ".ts"])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def init(self, extend=""):
        self.ensure_config()

    # ---------- 配置加载（规则3） ----------
    def ensure_config(self):
        if self._cfg:
            return self._cfg
        key = self._cache_key()
        if key in _MEM_CACHE:
            self._cfg = _MEM_CACHE[key]
        else:
            self._cfg = self._refresh_config()
            _MEM_CACHE[key] = self._cfg
        if self._cfg:
            self.host = self._cfg["host"]
            self.headers["Referer"] = self.host + "/"
        return self._cfg

    def _cache_key(self):
        return self._host_candidates[0].split("//")[1].split("/")[0]

    def _refresh_config(self):
        cfg = self._fetch_config()          # 新进程强制拉最新
        if not cfg:
            cfg = self._load_cache_file()   # 降级: 本地 spider_cache.json
        if not cfg:
            cfg = self._default_config()    # 兜底: 内置默认
        if cfg:
            self._save_cache_file(cfg)
        return cfg

    def _fetch_config(self):
        host = self._resolve_host()
        if not host:
            return None
        html = self.fetch(host + "/", timeout=12)
        if not html:
            return None
        direct, parents = self._parse_nav(html)
        classes, parents = self._build_classes(direct, parents)
        if not classes:
            return None
        # 筛选样本检测: 抓首个分类页，若无筛选控件则全站跳过，避免逐个请求。
        # 只覆盖直接分类，父分类的"类型"筛选（子分类）由 _build_classes 设定，不受影响
        parent_ids = set(parents.keys())
        sample_html = ""
        if classes:
            try:
                sample_html = self.fetch("%s/category/%s/" % (host, classes[0]["type_id"]), timeout=8)
            except Exception:
                sample_html = ""
        if self._parse_selects(sample_html or ""):
            for c in classes:
                if c["type_id"] in parent_ids:
                    continue
                c["type_extend"] = self._parse_selects(
                    self.fetch("%s/category/%s/" % (host, c["type_id"]), timeout=8) or "")
        else:
            for c in classes:
                if c["type_id"] not in parent_ids:
                    c["type_extend"] = {}
        classes = self._apply_class_order(classes)
        return {"host": host, "classes": classes, "parents": parents, "fetched_at": time.time()}

    def _parse_nav(self, html):
        # 解析站点两级导航:
        #   直接分类: <li class="menu-item"><a href="/category/x/">今日吃瓜</a></li>
        #   父分类:   <li class="nav-item dropdown"><button>吃瓜热门</button>
        #               <ul class="dropdown-menu"><li>.../category/x/...</li></ul></li>
        direct = []
        parents = {}
        nav = re.search(r'<ul id="menu-menu-1"[^>]*>([\s\S]*?)</ul>\s*</nav>', html)
        seg = nav.group(1) if nav else html
        for m in re.finditer(r'<li class="menu-item">\s*<a[^>]*href="(/category/([^"/]+)/)"[^>]*>\s*([^<]{1,40}?)\s*</a>', seg):
            slug, name = m.group(2), self._clean(m.group(3))
            if slug and name and not any(x == slug for x, _ in direct):
                direct.append((slug, name))
        for dd in re.finditer(r'<li class="nav-item dropdown">([\s\S]*?)</ul>\s*</li>', seg):
            block = dd.group(1)
            nm = re.search(r'<div>\s*([^<]+?)\s*</div>', block)
            name = self._clean(nm.group(1)) if nm else ""
            # 过滤: 无子分类的导航(官方信息/精品应用)、重复渲染的"首页"下拉
            if not name or name in ("首页",) or name in parents:
                continue
            subs = []
            for a in re.finditer(r'href="/category/([^"/]+)/"[^>]*>\s*([^<]{1,40}?)\s*</a>', block):
                subs.append((a.group(1), self._clean(a.group(2))))
            if subs:
                parents[name] = subs
        return direct, parents

    def _build_classes(self, direct, parents):
        # 生成主分类列表（顶级导航）:
        #   直接分类 + 父分类(子分类转为"类型"筛选) + _CLASS_ORDER 提升的子分类；
        #   父分类无子分类或命中 _CLASS_EXCLUDE 则跳过
        promoted = set()
        for a, b in self._CLASS_ORDER:
            for name, subs in parents.items():
                if a in [s[0] for s in subs] and name != b:
                    promoted.add(a)
        classes = []
        for slug, name in direct:
            classes.append({"type_id": slug, "type_name": name, "type_extend": {}})
        new_parents = {}
        for name, subs in parents.items():
            if name in self._CLASS_EXCLUDE:
                continue
            keep = [(s, n) for s, n in subs if s not in promoted]
            if not keep:
                continue
            new_parents[name] = [s for s, _ in keep]
            classes.append({"type_id": name, "type_name": name,
                            "type_extend": {"class": [{"n": n, "v": s} for s, n in keep]}})
        for a, b in self._CLASS_ORDER:
            for name, subs in parents.items():
                for s, sn in subs:
                    if s == a and not any(c["type_id"] == a for c in classes):
                        classes.append({"type_id": a, "type_name": sn, "type_extend": {}})
        return classes, new_parents

    def _parse_selects(self, html):
        # 通用下拉筛选解析: <select name=...><option value=...>文本</option></select>
        ext = {}
        key_map = {"type": "class", "class": "class", "area": "area",
                   "year": "year", "order": "order", "sort": "order"}
        for sm in re.finditer(r'<select[^>]*name=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</select>', html):
            raw_key = sm.group(1).lower()
            key = key_map.get(raw_key)
            if not key:
                continue
            values = []
            for om in re.finditer(r'<option[^>]*value=["\']?([^"\'>]*)["\']?[^>]*>([\s\S]*?)</option>', sm.group(2)):
                v = om.group(1).strip()
                n = self._clean(om.group(2))
                if not n:
                    continue
                values.append({"n": n, "v": v})
            if values:
                ext[key] = values
        return ext

    def _apply_class_order(self, classes):
        # 规则4: 偏好表控制顺序，只调顺序不改数据
        if not self._CLASS_ORDER:
            return classes
        by_id = {c["type_id"]: c for c in classes}
        after = {}   # B -> A: A 紧跟 B
        a_set = set()
        for a, b in self._CLASS_ORDER:
            if a in by_id and b in by_id and a != b:
                after[b] = a
                a_set.add(a)
        result = []
        placed = set()

        def place_chain(cid):
            if cid in placed or cid not in by_id:
                return
            placed.add(cid)
            result.append(by_id[cid])
            while cid in after and after[cid] not in placed:
                cid = after[cid]
                placed.add(cid)
                result.append(by_id[cid])

        for c in classes:
            cid = c["type_id"]
            if cid in placed or cid in a_set:
                continue  # a_set 成员位置由偏好关系决定
            place_chain(cid)
        for c in classes:
            if c["type_id"] not in placed:
                place_chain(c["type_id"])
        return result

    # ---------- 首页 ----------
    def homeContent(self, filter):
        cfg = self.ensure_config()
        classes = cfg["classes"]
        filters = {}
        for c in classes:
            filters[c["type_id"]] = self._build_filters(c.get("type_extend") or {})
        html = self.fetch(self.host + "/", timeout=12)
        lst = self._parse_list(html)
        return {"class": classes, "filters": filters, "list": lst}

    def homeVideoContent(self):
        self.ensure_config()
        html = self.fetch(self.host + "/", timeout=12)
        return {"list": self._parse_list(html)}

    # ---------- 筛选构建（规则2/5） ----------
    def _build_filters(self, ext):
        groups = []
        cls = ext.get("class") or []
        if cls:
            # 子分类超 8 拆行: class + class_more1 + ...
            for g in range((len(cls) + 7) // 8):
                key = "class" if g == 0 else "class_more%d" % g
                seg = cls[g * 8:(g + 1) * 8]
                groups.append({"key": key, "name": "类型",
                               "value": [{"n": "全部", "v": ""}] + seg})
        if ext.get("area"):
            groups.append({"key": "area", "name": "地区",
                           "value": [{"n": "全部", "v": ""}] + ext["area"]})
        if ext.get("year"):
            groups.append({"key": "year", "name": "年份",
                           "value": [{"n": "全部", "v": ""}] + ext["year"]})
        if ext.get("order"):
            groups.append({"key": "order", "name": "排序", "value": ext["order"]})
        return groups

    # ---------- 分类页 ----------
    def categoryContent(self, tid, pg, filter, extend):
        cfg = self.ensure_config()
        pg = int(pg) if str(pg).isdigit() else 1
        # 兼容客户端传参: 多数客户端把筛选放 filter(dict/JSON字符串),
        # 影视仓/小苹果等把筛选放 extend 而 filter 只传 True/False
        if isinstance(extend, dict) and extend:
            f = filter
            if isinstance(f, str):
                try:
                    f = json.loads(f)
                except Exception:
                    f = {}
            if not isinstance(f, dict):
                f = {}
            filter = {**extend, **f}
        # 父分类（顶级导航下拉）: 聚合其全部子分类第一页内容
        parents = cfg.get("parents") or {}
        if tid in parents:
            return self._category_aggregate(parents[tid], pg, filter)
        if pg <= 1:
            url = "%s/category/%s/" % (self.host, tid)
        else:
            url = "%s/category/%s/%d/" % (self.host, tid, pg)
        qs = self._merge_filter(filter)
        if qs:
            url += "?" + qs
        html = self.fetch(url, timeout=12)
        videos = self._parse_list(html)
        has_next = len(videos) > 0 and ("%s/%d/" % (tid, pg + 1)) in html
        return {
            "list": videos,
            "page": pg,
            "pagecount": pg + 1 if has_next else pg,
            "limit": max(1, len(videos)),
            "total": 999999 if has_next else pg * max(1, len(videos)),
        }

    def _category_aggregate(self, slugs, pg, filter):
        # 父分类聚合: 筛选指定子分类(class)时直接请求该子分类页(支持翻页)；
        # 否则并发抓取全部子分类第一页后合并去重（同进程缓存 5 分钟，避免 TVBox 超时）
        pg = int(pg)
        sub = self._class_filter_value(filter)
        if sub and sub in slugs:
            if pg <= 1:
                url = "%s/category/%s/" % (self.host, sub)
            else:
                url = "%s/category/%s/%d/" % (self.host, sub, pg)
            qs = self._merge_filter(filter)
            if qs:
                url += "?" + qs
            html = self.fetch(url, timeout=12)
            videos = self._parse_list(html)
            has_next = len(videos) > 0 and ("%s/%d/" % (sub, pg + 1)) in html
            return {"list": videos, "page": pg,
                    "pagecount": pg + 1 if has_next else pg,
                    "limit": max(1, len(videos)),
                    "total": 999999 if has_next else pg * max(1, len(videos))}
        if pg > 1:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}
        key = "|".join(slugs)
        now = time.time()
        hit = self._agg_cache.get(key)
        if not hit or now - hit[0] > 300:
            def grab(slug):
                return self._parse_list(self.fetch("%s/category/%s/" % (self.host, slug), timeout=10))
            videos = []
            seen = set()
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(slugs))) as ex:
                for vs in ex.map(grab, slugs):
                    for v in vs:
                        if v["vod_id"] not in seen:
                            seen.add(v["vod_id"])
                            videos.append(v)
            self._agg_cache[key] = (now, videos)
        else:
            videos = hit[1]
        return {"list": videos[:100], "page": 1, "pagecount": 1,
                "limit": len(videos), "total": len(videos)}

    def _normalize_filter(self, filter):
        # 兼容客户端传参形态: dict / JSON字符串 / True/False / None
        if not filter:
            return {}
        if isinstance(filter, str):
            try:
                return json.loads(filter)
            except Exception:
                return {}
        return filter if isinstance(filter, dict) else {}

    def _merge_filter(self, filter):
        # 规则5: class_moreN 共享后端 class 字段，取第一个非空值
        f = self._normalize_filter(filter)
        if not f:
            return ""
        cls = self._class_filter_value(f)
        parts = []
        if cls:
            parts.append(("class", cls))
        for k in ("area", "year", "order"):
            if f.get(k):
                parts.append((k, f[k]))
        return urllib.parse.urlencode(parts)

    def _class_filter_value(self, filter):
        # 提取"类型"筛选值: class 优先，class_moreN 取第一个非空
        f = self._normalize_filter(filter)
        if not f:
            return ""
        v = f.get("class") or ""
        i = 1
        while not v and f.get("class_more%d" % i):
            v = f["class_more%d" % i]
            i += 1
        return v

    # ---------- 详情页（规则6） ----------
    def detailContent(self, ids):
        self.ensure_config()
        vid = ids[0] if isinstance(ids, list) else ids
        vid = str(vid).strip("/").split("/")[-1]
        url = "%s/archives/%s/" % (self.host, vid)
        html = self.fetch(url, timeout=12)
        if not html:
            return {"list": []}

        title = ""
        tm = re.search(r'<h1 class="post-title[^"]*"[^>]*>([\s\S]*?)</h1>', html)
        if tm:
            title = self._clean(tm.group(1))
        if not title:
            tm = re.search(r'<title>([^<]+?)\s*[-|]\s*51吃瓜', html)
            if tm:
                title = self._clean(tm.group(1))
        if not title:
            tm = re.search(r'<title>([^<]+)</title>', html)
            if tm:
                title = self._clean(tm.group(1))

        pic = ""
        pm = re.search(r"loadBannerDirect\(['\"]([^'\"]+\.(?:jpe?g|png|webp)[^'\"]*)['\"]", html)
        if not pm:
            pm = re.search(r'itemprop="image"\s+content="([^"]+)"', html)
        if not pm:
            pm = re.search(r"loadImage\(['\"](https?[^'\"]+\.(?:jpe?g|png|webp))['\"]", html)
        if pm and "logo" not in pm.group(1) and "default" not in pm.group(1):
            pic = self._fix_url(pm.group(1).replace("\\/", "/"))

        intro = ""
        im = re.search(r'name="description"\s+content="([^"]+)"', html)
        if im:
            intro = self._clean(im.group(1))[:200]

        episodes = []
        seen = set()
        for m in re.finditer(r'<div class="dplayer"([^>]+)>', html):
            attrs = m.group(1)
            cm = re.search(r"data-config='(\{.*?\})'", attrs, re.S)
            if not cm:
                continue
            try:
                dcfg = json.loads(cm.group(1))
                media = ((dcfg.get("video") or {}).get("url") or "").replace("\\/", "/")
            except Exception:
                media = ""
            if not media or media in seen:
                continue
            seen.add(media)
            name = self._dplayer_name(html, m.start(), len(episodes) + 1)
            episodes.append("%s$%s" % (name, media))
        if not episodes:
            um = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html)
            if um:
                episodes.append("正片$" + um.group(1))
        if not episodes:
            return {"list": []}

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": intro,
            "vod_play_from": self.name,
            "vod_play_url": "#".join(episodes),
        }]}

    def _dplayer_name(self, html, pos, default_no):
        head = html[:pos]
        hm = re.findall(r'<h[23][^>]*>([\s\S]*?)</h[23]>', head)
        if hm:
            n = self._clean(hm[-1])
            if n:
                return n
        return "第%d集" % default_no

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        self.ensure_config()
        pg = int(pg) if str(pg).isdigit() else 1
        wd = urllib.parse.quote(str(key))
        if pg <= 1:
            url = "%s/search/%s/" % (self.host, wd)
        else:
            url = "%s/search/%s/%d/" % (self.host, wd, pg)
        html = self.fetch(url, timeout=12)
        videos = self._parse_list(html)
        has_next = len(videos) >= 25
        return {
            "list": videos,
            "page": pg,
            "pagecount": pg + 1 if has_next else pg,
            "limit": 20,
            "total": 999999 if has_next else pg * max(1, len(videos)),
        }

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        self.ensure_config()
        url = str(id)
        if self.isVideoFormat(url):
            return {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": json.dumps({"User-Agent": self.ua, "Referer": self.host + "/"}),
            }
        return {"parse": 1, "url": url, "header": "{}"}

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]

    # ---------- 域名探测（对应 /config） ----------
    def _resolve_host(self):
        for u in self._host_candidates:
            if self._check_host(u):
                return u.rstrip("/")
        return None

    def _check_host(self, u):
        try:
            h = self.fetch(u + "/", timeout=8)
        except Exception:
            return False
        return "<article" in h or "loadBannerDirect" in h

    # ---------- 缓存文件 ----------
    def _cache_paths(self):
        paths = []
        try:
            paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), self._CACHE_FILE))
        except Exception:
            pass
        try:
            paths.append(os.path.join(os.getcwd(), self._CACHE_FILE))
        except Exception:
            pass
        try:
            import tempfile
            paths.append(os.path.join(tempfile.gettempdir(), self._CACHE_FILE))
        except Exception:
            pass
        return paths

    def _load_cache_file(self):
        for p in self._cache_paths():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if d.get("host") and d.get("classes") and d.get("parents"):
                    return d
            except Exception:
                continue
        return None

    def _save_cache_file(self, cfg):
        for p in self._cache_paths():
            try:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, ensure_ascii=False)
                return
            except Exception:
                continue

    def _default_config(self):
        # 兜底: 仅当站点和缓存都不可用时使用，保持最小硬编码
        return {
            "host": self._host_candidates[0].rstrip("/"),
            "classes": [
                {"type_id": "wpcz", "type_name": "今日吃瓜", "type_extend": {}},
                {"type_id": "吃瓜热门", "type_name": "吃瓜热门",
                 "type_extend": {"class": [{"n": "学生校园", "v": "xsxy"},
                                           {"n": "网红黑料", "v": "whhl"},
                                           {"n": "热门大瓜", "v": "rdsj"},
                                           {"n": "吃瓜榜单", "v": "mrdg"},
                                           {"n": "必看大瓜", "v": "bkdg"}]}},
                {"type_id": "cbdj", "type_name": "AI成人短剧", "type_extend": {}},
                {"type_id": "娱乐天地", "type_name": "娱乐天地",
                 "type_extend": {"class": [{"n": "影视娱乐", "v": "ysyl"},
                                           {"n": "每日热搜", "v": "mrds"},
                                           {"n": "恋爱基地", "v": "lldd"},
                                           {"n": "搞钱省钱", "v": "gcjq"},
                                           {"n": "童辉合集", "v": "thjx"},
                                           {"n": "万花集锦", "v": "whhj"}]}},
            ],
            "parents": {"吃瓜热门": ["xsxy", "whhl", "rdsj", "mrdg", "bkdg"],
                        "娱乐天地": ["ysyl", "mrds", "lldd", "gcjq", "thjx", "whhj"]},
            "fetched_at": time.time(),
        }

    # ---------- 内部工具 ----------
    def fetch(self, url, hdr=None, timeout=15):
        headers = self.headers
        if hdr:
            headers = dict(self.headers)
            headers.update(hdr)
        try:
            import requests
            r = requests.get(url, headers=headers, timeout=timeout, verify=False)
            if r.status_code == 200 and r.text:
                return r.text
        except Exception:
            pass
        try:
            req = urllib.request.Request(url, headers=headers)
            try:
                resp = urllib.request.urlopen(req, context=self.ctx, timeout=timeout)
            except TypeError:
                resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _fix_url(self, u):
        if not u:
            return ""
        u = u.strip()
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = self.host + u
        if not (u.startswith("http://") or u.startswith("https://")):
            return u
        # 站点加密图片（xustgq.cn）走解密代理；其他图直连
        if "xustgq.cn" in u:
            return self.img_proxy + urllib.parse.quote(u, safe="")
        return u

    def _clean(self, s):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

    def _parse_list(self, html):
        # 解析 article 列表，过滤广告外链（无 /archives/ 链接或 h2 的丢弃）
        items = []
        seen = set()
        if not html:
            return items
        for m in re.finditer(r'<article[\s\S]*?</article>', html):
            block = m.group(0)
            am = re.search(r'<a[^>]*href="(/archives/(\d+)/)"', block)
            if not am:
                continue
            vid = am.group(2)
            if vid in seen:
                continue
            hm = re.search(r'<h2[^>]*>([\s\S]*?)</h2>', block)
            if not hm:
                continue
            title = self._clean(hm.group(1))
            if not title:
                continue
            seen.add(vid)
            pic = ""
            pm = re.search(r"loadBannerDirect\(['\"]([^'\"]+)['\"]", block)
            if pm:
                pic = self._fix_url(pm.group(1))
            rem = ""
            dm = re.search(r'<span[^>]*itemprop="datePublished"[^>]*>([^<]*)', block)
            if dm:
                rem = self._clean(dm.group(1))
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": rem,
            })
        return items
