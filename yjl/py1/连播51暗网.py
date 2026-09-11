#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#51暗网最新入口：51awn4.com
#51暗网官方邮箱：anwangchigua@gmail.com
#永久域名：https://51aw.com
"""
51暗网 TVBox 爬虫站源（自动获取可用域名）
Typecho Mirages 主题 + DPlayer（data-config JSON）
关键: 完整 Chrome UA 才返回完整页面（简短 UA 被服务器截断正文/VIP 视频不下发）
站点会换域名（DNS 污染/封禁），加载源时自动从地址发布页抓取当前可用域名：
51awn4.com -> JS 跳转壳 -> ehiynkuc.com(Base64编码) -> 站点列表 -> 探测可用 -> 缓存
"""
import re
import json
import base64
import urllib.request
import urllib.parse
import ssl

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object


class Spider(BaseSpider):
    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.name = "51awBlock"
        self.host = "https://51aw.com"
        # 地址发布页入口（会 301/JS 跳转到最新发布页），可追加新入口
        self.entries = [
            "https://51awn4.com/",
            "https://awcg48.com/",
            "https://51aw.com/",
        ]
        self._host_done = False
        # 图片解密代理（站点图片 AES-CBC 加密，TVBox 无法直接显示）
        # 公网域名（CF 代理到本机 7800）——TVBox 在外网也能用
        self.img_proxy = "https://py.fzcrym.link:1314/bk51_img?u="
        # ⚠️ 必须完整 Chrome UA——简短 UA 服务器截断正文，VIP 视频直接缺失
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.header = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            # 18+ 年龄确认 cookie——缺失时分类页只有弹窗无内容
            "Cookie": "user-choose=true",
        }
        self.categories = [
            {"type_name": "今日吃瓜", "type_id": "jrrg"},
            {"type_name": "全网热搜", "type_id": "qwrs"},
            {"type_name": "暗网爆料", "type_id": "awcg"},
            {"type_name": "暗网网红", "type_id": "dywh"},
            {"type_name": "每日大赛", "type_id": "mrds"},
            {"type_name": "AI短剧", "type_id": "aidj"},
            {"type_name": "暗网反差", "type_id": "fcll"},
            {"type_name": "暗网校园", "type_id": "xycg"},
            {"type_name": "暗网乱伦", "type_id": "anwangluanlun"},
            {"type_name": "暗网视频", "type_id": "sxzq"},
            {"type_name": "海外大片", "type_id": "hwaw"},
            {"type_name": "AV解说", "type_id": "awdz"},
            {"type_name": "暗网猎奇", "type_id": "awlq"},
            {"type_name": "探花偷拍", "type_id": "tanhua"},
            {"type_name": "每日TOP", "type_id": "meiri-top"},
            {"type_name": "寸止挑战", "type_id": "cunzhi"},
            {"type_name": "动漫天堂", "type_id": "dmtt"},
            {"type_name": "暗史档案", "type_id": "dark-history"},
        ]
        try:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        except Exception:
            self.ctx = None

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return ".m3u8" in url or ".mp4" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def init(self, extend=""):
        self.resolve_host()

    def homeContent(self, filter):
        return {"class": self.categories, "filters": {}, "list": []}

    def homeVideoContent(self):
        html = self.fetch(self.host + "/")
        return {"list": self.parse_cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        # 站点翻页格式: /category/{tid}/ 和 /category/{tid}/{n}/（非 page/n/）
        if pg <= 1:
            url = "%s/category/%s/" % (self.host, tid)
        else:
            url = "%s/category/%s/%d/" % (self.host, tid, pg)
        html = self.fetch(url)
        videos = self.parse_cards(html)
        has_next = len(videos) > 0 and ('%s/%d/' % (tid, pg + 1)) in html
        return {
            "list": videos,
            "page": pg,
            "pagecount": pg + 1 if has_next else pg,
            "limit": max(1, len(videos)),
            "total": 999999 if has_next else pg * max(1, len(videos)),
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        vid = str(vid).strip("/").split("/")[-1]
        url = "%s/archives/%s/" % (self.host, vid)
        html = self.fetch(url)
        if not html:
            return {"list": []}

        title, pic, intro = "", "", ""
        tm = re.search(r'<h1 class="post-title[^"]*"[^>]*>([\s\S]*?)</h1>', html)
        if tm:
            title = self.clean(tm.group(1))
        if not title:
            tm = re.search(r'<title>([^<]+?)\s*-\s*51暗网', html)
            if tm:
                title = self.clean(tm.group(1))

        pm = re.search(r"loadBannerDirect\('([^']+\.(?:jpe?g|png|webp)[^']*)'", html)
        if not pm:
            # 详情页封面: itemprop image（正文头图）
            pm = re.search(r'itemprop="image"\s+content="([^"]+)"', html)
        if not pm:
            pm = re.search(r"loadImage\([\"'](https?[^\")]+\.(?:jpe?g|png|webp))", html)
        if pm and "social-default" not in pm.group(1) and "logo" not in pm.group(1):
            pic = self.fix_url(pm.group(1).replace("\\/", "/"))

        # 简介: og:description / meta description
        im = re.search(r'name="description"\s+content="([^"]+)"', html)
        if not im:
            im = re.search(r'property="og:description"\s+content="([^"]+)"', html)
        if im:
            intro = self.clean(im.group(1))[:200]

        # 选集: 所有 dplayer 块（每集一个），playerContent 实时解析拿新 auth_key
        episodes = []
        seen = set()
        for m in re.finditer(r'<div class="dplayer"([^>]+)>', html):
            attrs = m.group(1)
            vm = re.search(r'data-video_id="([\w-]+)"', attrs)
            vt = re.search(r'data-video_title="([^"]*)"', attrs)
            if not vm or vm.group(1) in seen:
                continue
            seen.add(vm.group(1))
            name = vt.group(1) if vt else ("第%d集" % (len(episodes) + 1))
            # 标题去重前缀（长标题只留尾部分集号）
            name = re.sub(r'^.*?(\d{3})$', r'\1', name) if re.search(r'\d{3}$', name) else name
            episodes.append(name + "$" + vm.group(1))
        if not episodes:
            return {"list": []}
        play_url = "#".join(episodes)

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": intro,
                "vod_play_from": "51aw",
                "vod_play_url": play_url,
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        wd = urllib.parse.quote(str(key))
        if pg <= 1:
            url = "%s/search/%s/" % (self.host, wd)
        else:
            url = "%s/search/%s/page/%d/" % (self.host, wd, pg)
        html = self.fetch(url)
        videos = self.parse_cards(html)
        has_next = len(videos) > 0 and ('page/%d/' % (pg + 1)) in html
        return {
            "list": videos,
            "page": pg,
            "pagecount": pg + 1 if has_next else pg,
            "limit": 20,
            "total": 999999 if has_next else pg * max(1, len(videos)),
        }

    def playerContent(self, flag, id, vipFlags):
        # id = video_id（如 109323001）→ 从详情页实时解析 m3u8（auth_key 时效 ~1h）
        video_id = str(id)
        # 由 video_id 反推文章 id（video_id = 文章id + 分集序号3位）
        arch_id = video_id[:-3] if len(video_id) > 6 and video_id[-3:].isdigit() else video_id
        html = self.fetch("%s/archives/%s/" % (self.host, arch_id))
        media = ""
        if html:
            for m in re.finditer(r'<div class="dplayer"([^>]+)>', html):
                attrs = m.group(1)
                vm = re.search(r'data-video_id="([\w-]+)"', attrs)
                if not vm or vm.group(1) != video_id:
                    continue
                cm = re.search(r"data-config='(\{.*?\})'", attrs, re.S)
                if cm:
                    try:
                        cfg = json.loads(cm.group(1))
                        v = cfg.get("video", {}) or {}
                        media = (v.get("url") or "").replace("\\/", "/")
                    except Exception:
                        media = ""
                break
        if not media:
            # 兜底: 页面里任意 m3u8
            um = re.search(r'(https?://[^"\'\s]+\.m3u8[^"\'\s]*)', html)
            if um:
                media = um.group(1)
        if not media:
            return {"parse": 1, "url": "%s/archives/%s/" % (self.host, arch_id), "header": "{}"}
        headers = {"User-Agent": self.ua, "Referer": self.host + "/"}
        return {
            "parse": 0,
            "playUrl": "",
            "url": media,
            "header": json.dumps(headers),
        }

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]

    # ---------- 内部 ----------
    def resolve_host(self):
        # 自动获取当前可用播放站，结果缓存，只探测一次
        # 顺序: 已知播放站(快) -> 地址发布页收集的候选(慢) -> 默认
        if getattr(self, "_host_done", False):
            return
        self._host_done = True
        for u in ["https://51aw.com/", "https://block.jfnarrqbo.cc/"]:
            if self._check_host(u):
                self.host = u.rstrip("/")
                return
        cands = []
        for e in self.entries:
            for u in self._harvest_candidates(e):
                if u not in cands:
                    cands.append(u)
        for u in cands:
            if self._check_host(u):
                self.host = u.rstrip("/")
                return

    def _harvest_candidates(self, entry, depth=0):
        # 从发布页提取候选站点域名，支持 JS 跳转壳和 Base64 编码页
        out = []
        if depth > 2:
            return out
        html = self.fetch(entry)
        if not html:
            return out
        source = html
        for b in re.findall(r"Base64\.decode\('([^']+)'\)", html):
            try:
                source += "\n" + base64.b64decode(b).decode("utf-8", "replace")
            except Exception:
                pass
        for m in re.finditer(r'https?://([a-zA-Z0-9._-]+)', source):
            dom = m.group(1).rstrip("/").split("/")[0].split("?")[0]
            if self._is_playable_domain(dom):
                u = "https://" + dom
                if u not in out:
                    out.append(u)
        for m in re.finditer(r'([a-zA-Z0-9-]+\.cloudfront\.net)', source):
            u = "https://" + m.group(1)
            if u not in out:
                out.append(u)
        # JS 跳转壳: <a href="...">加载中</a>
        jm = re.search(r'<a[^>]+href=["\'](https?://[^"\']+)["\'][^>]*>', html)
        if jm and jm.group(1) not in entry:
            for u in self._harvest_candidates(jm.group(1), depth + 1):
                if u not in out:
                    out.append(u)
        return out

    def _is_playable_domain(self, dom):
        dom = dom.lower().rstrip("/").split("/")[0]
        if not re.match(r'^[a-z0-9.-]+\.(com|cc|net|top|xyz|vip|cloudfront\.net)$', dom):
            return False
        skip = ("googletagmanager", "google-analytics", "googlesyndication",
                "googleapis", "gstatic", "google", "cloudflare", "jsdelivr",
                "bootcdn", "unpkg", "picsum", "51awn4", "ehiynkuc")
        return not any(s in dom for s in skip)

    def _check_host(self, u):
        u = u.rstrip("/")
        try:
            h = self.fetch(u + "/category/jrrg/", hdr={"Referer": u + "/"}, timeout=8)
        except Exception:
            return False
        return "post-card" in h

    def fetch(self, url, hdr=None, timeout=15):
        headers = self.header
        if hdr:
            headers = dict(self.header)
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

    def fix_url(self, u):
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

    def clean(self, s):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

    def parse_cards(self, html):
        items = []
        seen = set()
        if not html:
            return items
        blocks = re.split(r'<div class="post-card" id="post-card-', html)
        for b in blocks[1:]:
            vid_m = re.match(r'(\d+)', b)
            if not vid_m:
                continue
            vid = vid_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            title = ""
            tm = re.search(r'itemprop="headline"\s*>\s*([\s\S]{0,150}?)<', b)
            if tm:
                title = self.clean(tm.group(1))
            if not title:
                tm = re.search(r'title="([^"]{4,80})"', b)
                if tm:
                    title = self.clean(tm.group(1))
            if not title:
                continue
            pic = ""
            pm = re.search(r"loadBannerDirect\('([^']+)'", b)
            if pm:
                pic = self.fix_url(pm.group(1))
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return items

# ===== PAGE_PLAYLIST_START =====
def _pl_install(_C):
    if getattr(_C, "_pl_patched", False):
        return _C
    _C._pl_patched = True
    _orig_init = getattr(_C, "init", None)
    _orig_home = getattr(_C, "homeContent", None)
    _orig_homev = getattr(_C, "homeVideoContent", None)
    _orig_cate = getattr(_C, "categoryContent", None)
    _orig_detail = getattr(_C, "detailContent", None)
    _orig_search = getattr(_C, "searchContent", None)
    _orig_searchp = getattr(_C, "searchContentPage", None)
    _orig_player = getattr(_C, "playerContent", None)

    def _ensure(self):
        if not hasattr(self, "page_cache"):
            self.page_cache = {}
            self.page_index = {}
            self.page_keys = []
            self._src_cache = {}

    def _clean(s):
        return str(s or "").replace("$", " ").replace("#", " ").strip()

    def _enc(s):
        try:
            from urllib.parse import quote
            return quote(str(s or ""), safe="")
        except Exception:
            return str(s or "")

    def _dec(s):
        try:
            from urllib.parse import unquote
            return unquote(str(s or ""))
        except Exception:
            return str(s or "")

    def _cache_page(self, key, items):
        _ensure(self)
        out = []
        for x in items or []:
            if isinstance(x, dict) and x.get("vod_id"):
                out.append(x)
        if not out:
            return
        self.page_cache[key] = out
        if key in self.page_keys:
            self.page_keys.remove(key)
        self.page_keys.append(key)
        for it in out:
            self.page_index[str(it["vod_id"])] = key
        while len(self.page_keys) > 30:
            old = self.page_keys.pop(0)
            self.page_cache.pop(old, None)

    def _page_of(self, vid):
        _ensure(self)
        key = self.page_index.get(str(vid))
        if key in self.page_cache:
            return list(self.page_cache[key])
        return []

    def _as_result(r):
        if r is None:
            return {}
        if isinstance(r, dict):
            return r
        if isinstance(r, (bytes, bytearray)):
            r = r.decode("utf-8", "ignore")
        if isinstance(r, str):
            s = r.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    import json as _j
                    return _j.loads(s)
                except Exception:
                    return {}
        return {}

    def _split_sources(vod):
        fr = str((vod or {}).get("vod_play_from") or "").split("$$$")
        ur = str((vod or {}).get("vod_play_url") or "").split("$$$")
        while len(ur) < len(fr):
            ur.append("")
        sources = []
        for i, name in enumerate(fr):
            parts = []
            for p in (ur[i] or "").split("#"):
                if not p:
                    continue
                if "$" in p:
                    n, u = p.split("$", 1)
                else:
                    n, u = str(i + 1), p
                parts.append((_clean(n), u))
            sources.append((_clean(name) or ("线路%d" % (i + 1)), parts))
        return [x for x in sources if x[1]]

    def _call_detail(self, vid):
        if not _orig_detail:
            return {}
        try:
            return _as_result(_orig_detail(self, [vid]))
        except TypeError:
            try:
                return _as_result(_orig_detail(self, vid))
            except Exception:
                return {}
        except Exception:
            return {}

    def _load_src(self, vid):
        _ensure(self)
        vid = str(vid)
        if vid in self._src_cache:
            return self._src_cache[vid]
        r = self._pl_call_detail(vid)
        vod = ((r.get("list") or [None])[0]) or {}
        sources = _split_sources(vod)
        self._src_cache[vid] = sources
        return sources

    def _item_parts(self, it, src_idx, current_sources, current_vid):
        iid = str(it.get("vod_id") or "")
        if not iid:
            return []
        name = _clean(it.get("vod_name") or iid) or iid
        if iid == str(current_vid):
            eps = []
            if current_sources:
                if src_idx < len(current_sources) and current_sources[src_idx][1]:
                    eps = current_sources[src_idx][1]
                else:
                    eps = current_sources[0][1]
            if len(eps) > 1:
                out = []
                for i, (en, u) in enumerate(eps):
                    label = _clean("%s %s" % (name, en or ("%02d" % (i + 1))))
                    out.append("%s$%s" % (label, u))
                return out
            if eps:
                return ["%s$%s" % (name, eps[0][1])]
            return ["%s$nid:%s" % (name, _enc(iid))]
        return ["%s$nid:%s" % (name, _enc(iid))]

    def _apply_playlist(self, vid, vod, items):
        sources = _split_sources(vod)
        _ensure(self)
        self._src_cache[str(vid)] = sources
        if not items:
            return vod
        ordered = [x for x in items if str(x.get("vod_id")) == str(vid)]
        ordered += [x for x in items if str(x.get("vod_id")) != str(vid)]
        plist, seen = [], set()
        for it in ordered:
            iid = str(it.get("vod_id") or "")
            if not iid or iid in seen:
                continue
            seen.add(iid)
            plist.append(it)
        if not plist:
            return vod
        if not sources:
            sources = [("线路1", [("播放", "nid:%s" % _enc(vid))])]
        play_from, play_urls = [], []
        for i, (sname, _eps) in enumerate(sources):
            parts = []
            for it in plist:
                parts.extend(self._pl_item_parts(it, i, sources, vid))
            if not parts:
                continue
            play_from.append(sname or ("线路%d" % (i + 1)))
            play_urls.append("#".join(parts))
        if not play_from:
            return vod
        vod = dict(vod)
        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_urls)
        return vod

    def init(self, *args, **kwargs):
        _ensure(self)
        if _orig_init:
            return _orig_init(self, *args, **kwargs)

    def homeContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_home(self, *args, **kwargs) if _orig_home else {}
        try:
            _cache_page(self, ("home",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def homeVideoContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_homev(self, *args, **kwargs) if _orig_homev else {"list": []}
        try:
            _cache_page(self, ("homev",), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def categoryContent(self, *args, **kwargs):
        _ensure(self)
        r = _orig_cate(self, *args, **kwargs) if _orig_cate else {"list": []}
        try:
            tid = args[0] if args else kwargs.get("tid", "")
            pg = args[1] if len(args) > 1 else kwargs.get("pg", "1")
            ext = args[3] if len(args) > 3 else kwargs.get("extend", "")
            _cache_page(self, ("cate", str(tid), str(pg), str(ext)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContent(self, *args, **kwargs):
        _ensure(self)
        if not _orig_search:
            return {"list": []}
        r = _orig_search(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("pg", "1")
            _cache_page(self, ("search", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def searchContentPage(self, *args, **kwargs):
        _ensure(self)
        if not _orig_searchp:
            return {"list": []}
        r = _orig_searchp(self, *args, **kwargs)
        try:
            key = args[0] if args else kwargs.get("key", "")
            pg = args[2] if len(args) > 2 else kwargs.get("page", kwargs.get("pg", "1"))
            _cache_page(self, ("searchp", str(key), str(pg)), _as_result(r).get("list"))
        except Exception:
            pass
        return r

    def detailContent(self, ids, *args, **kwargs):
        _ensure(self)
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
            call_ids = list(ids)
        else:
            vid = str(ids)
            call_ids = [vid]
        if vid.startswith("nid:"):
            vid = _dec(vid[4:])
            call_ids[0] = vid
        cached = _page_of(self, vid)
        if _orig_detail:
            try:
                r = _orig_detail(self, call_ids, *args, **kwargs)
            except TypeError:
                r = _orig_detail(self, call_ids)
        else:
            r = {"list": []}
        try:
            rr = _as_result(r)
            lst = rr.get("list") or []
            if not lst or not isinstance(lst[0], dict):
                return r
            vod = dict(lst[0])
            vod["vod_id"] = str(vod.get("vod_id") or vid)
            if not vod.get("vod_name"):
                hit = next((x for x in cached if str(x.get("vod_id")) == vid), None)
                if hit:
                    vod["vod_name"] = hit.get("vod_name") or vid
            if cached:
                vod = self._pl_apply_playlist(vid, vod, cached)
            rr = dict(rr)
            rr["list"] = [vod]
            if isinstance(r, dict) or r is None:
                return rr
            try:
                import json as _j
                return _j.dumps(rr, ensure_ascii=False)
            except Exception:
                return rr
        except Exception:
            return r

    def playerContent(self, flag, id, vipFlags=None, *args, **kwargs):
        _ensure(self)
        s = str(id)
        if s.startswith("nid:"):
            vid = _dec(s[4:])
            sources = self._pl_load_src(vid)
            real = ""
            if sources:
                picked = None
                for name, eps in sources:
                    if str(name) == str(flag) and eps:
                        picked = eps
                        break
                if not picked:
                    picked = sources[0][1]
                if picked:
                    real = picked[0][1]
            if real and not str(real).startswith("nid:"):
                id = real
            else:
                id = vid
        if not _orig_player:
            return {"parse": 0, "url": id}
        try:
            return _orig_player(self, flag, id, vipFlags, *args, **kwargs)
        except TypeError:
            try:
                return _orig_player(self, flag, id, vipFlags)
            except TypeError:
                return _orig_player(self, flag, id)

    _C._pl_call_detail = _call_detail
    _C._pl_load_src = _load_src
    _C._pl_item_parts = _item_parts
    _C._pl_apply_playlist = _apply_playlist
    if _orig_init:
        _C.init = init
    if _orig_home:
        _C.homeContent = homeContent
    if _orig_homev:
        _C.homeVideoContent = homeVideoContent
    if _orig_cate:
        _C.categoryContent = categoryContent
    if _orig_search:
        _C.searchContent = searchContent
    if _orig_searchp:
        _C.searchContentPage = searchContentPage
    if _orig_detail:
        _C.detailContent = detailContent
    if _orig_player:
        _C.playerContent = playerContent
    return _C

try:
    _pl_install(Spider)
except Exception:
    pass
# ===== PAGE_PLAYLIST_END =====
