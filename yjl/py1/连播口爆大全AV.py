# -*- coding: utf-8 -*-
"""KNM111 / 口爆大全AV - FongMi/WebHomeTV/PickTV compatible spider.
仅解析站点公开页面；列表条目保持干净，播放地址只在 detailContent 返回。
"""
import re
import json
import urllib.parse
import urllib.request
from html import unescape
from html.parser import HTMLParser


class _Parser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.links = []
        self.articles = []
        self._a = None
        self._article = None
        self._img = None
        self._text = []
        self._in_h2 = False
        self._in_title = False
        self.title = ''
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class', '')
        if tag == 'title':
            self._in_title = True
        if tag == 'meta' and a.get('name', '').lower() in ('description', 'keywords'):
            self.meta[a.get('name', '').lower()] = a.get('content', '')
        if tag == 'a' and a.get('href'):
            self._a = {'href': a['href'], 'title': a.get('title', ''), 'pic': '', 'name': ''}
        if tag == 'img' and self._a is not None:
            self._a['pic'] = a.get('src') or a.get('data-src') or ''
        if tag == 'h2' and self._a is not None:
            self._in_h2 = True
        if tag == 'article':
            self._article = self._a

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False
        if tag == 'h2':
            self._in_h2 = False
        if tag == 'a' and self._a is not None:
            x = self._a
            if self._in_h2:
                x['name'] = ''.join(self._text).strip()
            if not x['name']:
                x['name'] = x['title']
            if '/video/' in x['href']:
                self.links.append(x.copy())
            self._a = None
            self._text = []
        if tag == 'article' and self._article is not None:
            x = self._article
            if x in self.links and x not in self.articles:
                self.articles.append(x)
            self._article = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h2:
            self._text.append(data)


class Spider:
    host = 'https://knm111.top'
    ua = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36'
    referer = host + '/'
    cats = {
        '57': '精品推荐', '58': '主播秀色', '59': 'AV解说', '60': '日本无码',
        '61': '中文字幕', '62': '童颜巨乳', '63': '性感人妻', '64': '强奸乱伦',
        '65': '欧美情色', '67': '群P换妻', '68': '成人动画', '69': '丝袜OL',
        '70': '自拍偷拍', '71': '网曝系列', '72': '同性恋', '90': '探花嫖娼',
        '91': '国产人妻', '92': '国产SM', '93': '国产丝袜', '94': '麻豆传媒',
        '95': '国产乱伦', '96': '自慰系列', '97': '教师学生', '98': '口交视频'
    }

    def __init__(self):
        self.s = None
        self.session = None
        self.sess = None
        self.extend = ''

    def getDependence(self):
        return []

    def init(self, extend=''):
        self.extend = extend or ''
        return None

    def _get(self, url):
        if not url.startswith('http'):
            url = urllib.parse.urljoin(self.host + '/', url)
        req = urllib.request.Request(url, headers={
            'User-Agent': self.ua, 'Referer': self.referer, 'Accept': 'text/html,application/xhtml+xml'
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode('utf-8', 'ignore'), r.geturl()
        except Exception:
            return '', url

    def _parse(self, text):
        p = _Parser()
        try:
            p.feed(text)
        except Exception:
            pass
        out = []
        seen = set()
        for x in p.links:
            href = urllib.parse.urljoin(self.host + '/', x['href'])
            m = re.search(r'/video/\?(\d+)-', href)
            if not m or href in seen:
                continue
            seen.add(href)
            out.append({'vod_id': m.group(1),
                        'vod_name': unescape(x['name'] or x['title']).strip(),
                        'vod_pic': self._pic(x['pic']) if x['pic'] else '',
                        'vod_remarks': ''})
        return out, p

    def _page(self, tid, pg):
        tid = str(tid or '57')
        try:
            pg = int(pg or 1)
        except Exception:
            pg = 1
        path = '/list/?%s.html' % tid if pg <= 1 else '/list/?%s-%s.html' % (tid, pg)
        return self._get(self.host + path)[0]

    def homeContent(self, filter=None):
        classes = [{'type_id': k, 'type_name': v} for k, v in self.cats.items()]
        text = self._get(self.host + '/index.php')[0]
        videos, _ = self._parse(text)
        return {'class': classes, 'list': videos}

    def homeVideoContent(self):
        text = self._get(self.host + '/index.php')[0]
        videos, _ = self._parse(text)
        return {'list': videos}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        videos, _ = self._parse(self._page(tid, pg))
        return {'list': videos, 'page': int(pg or 1), 'pagecount': 9999, 'limit': 20, 'total': 999999}

    def searchContent(self, key, quick=False, pg='1'):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        q = urllib.parse.quote(str(key), safe='')
        url = self.host + '/search.php?searchword=' + q
        if page > 1:
            url += '&page=' + str(page)
        videos, _ = self._parse(self._get(url)[0])
        return {'list': videos, 'page': page, 'pagecount': 9999, 'limit': 20, 'total': 999999}

    def _id(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ''
        if isinstance(ids, dict):
            ids = ids.get('id', '')
        s = str(ids)
        m = re.search(r'(\d+)', s)
        return m.group(1) if m else s

    def detailContent(self, ids):
        vid = self._id(ids)
        text, final = self._get(self.host + '/video/?%s-0-0.html' % vid)
        videos, p = self._parse(text)
        title = p.title.strip()
        title = re.sub(r'^(《|\[)', '', title)
        title = re.sub(r'(》)?(?:全集在线播放|全集在线观看).*$', '', title).strip()
        if not title:
            title = next((x['vod_name'] for x in videos if x['vod_id'] == vid), '视频 ' + vid)
        # 详情页的图片只有相关推荐，不能取第一张；真实封面与播放流同目录。
        mm = re.search(r'\bvar\s+now\s*=\s*["\']([^"\']+)', text, re.I)
        play = mm.group(1) if mm else ''
        pic = ''
        if play:
            pic = re.sub(r'/index\.m3u8(?:\?.*)?$', '/1.jpg', play)
        if not pic:
            # 首页/分类中的同 ID 卡片可作为降级封面来源
            home_videos, _ = self._parse(self._get(self.host + '/index.php')[0])
            pic = next((x.get('vod_pic', '') for x in home_videos if x.get('vod_id') == vid), '')
            if pic.startswith('proxy://?do=py&url='):
                pic = urllib.parse.unquote(pic.split('url=', 1)[1])
        if not pic:
            mm = re.search(r'<img[^>]+src=["\']([^"\']+)', text, re.I)
            pic = mm.group(1) if mm else ''
        vod = {'vod_id': vid, 'vod_name': title, 'vod_pic': self._pic(pic),
               'vod_content': p.meta.get('description', ''), 'vod_remarks': '高清',
               'vod_play_from': 'KNM111', 'vod_play_url': '正片$' + play if play else ''}
        return {'list': [vod]}

    def playerContent(self, flag, ids, vipFlags=None):
        url = str(ids or '')
        if not url.startswith('http'):
            url = self._id(url)
            d = self.detailContent([url]).get('list', [{}])[0]
            pu = d.get('vod_play_url', '')
            url = pu.split('$', 1)[-1] if '$' in pu else pu
        return {'parse': 0, 'jx': 0, 'url': url,
                'header': {'User-Agent': self.ua, 'Referer': self.referer},
                'format': 'application/x-mpegURL'}

    def _pic(self, url):
        if not url:
            return ''
        # 该 CDN 可直接访问；封面返回原始 .jpg 地址，避免部分壳不解析 proxy:// 图片。
        # localProxy 仍保留，作为需要代理时的兼容入口。
        return url

    def localProxy(self, param):
        if isinstance(param, str):
            try: param = json.loads(param)
            except Exception: param = {}
        url = (param or {}).get('url', '')
        if not url:
            return [404, 'text/plain', b'', {}]
        url = urllib.parse.unquote(url)
        req = urllib.request.Request(url, headers={'User-Agent': self.ua, 'Referer': self.referer})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read()
                ctype = r.headers.get('Content-Type', 'image/jpeg').split(';')[0]
                # CDN 常返回 application/octet-stream，影视壳可能因此不显示封面。
                if body.startswith(b'\xff\xd8\xff'):
                    ctype = 'image/jpeg'
                elif body.startswith(b'\x89PNG'):
                    ctype = 'image/png'
                elif body.startswith(b'GIF8'):
                    ctype = 'image/gif'
                elif body.startswith(b'RIFF') and body[8:12] == b'WEBP':
                    ctype = 'image/webp'
                return [200, ctype, body, {'Cache-Control': 'max-age=3600'}]
        except Exception:
            return [502, 'text/plain', b'', {}]

    def manualVideoCheck(self): return False
    def isVideoFormat(self, url): return '.m3u8' in str(url).lower() or '.mp4' in str(url).lower()
    def action(self, action): return {}
    def destroy(self): return None

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
