# -*- coding: utf-8 -*-
import sys
import re
import json
import time
import urllib.parse
import requests

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, **kw):
            t = kw.pop('timeout', 20)
            r = requests.get(url, headers=headers, timeout=t, verify=False, **kw)
            r.encoding = 'utf-8'
            return r

_API = 'http://sekihfde.com/api'
_PLAY_UUID = '724b9c9fdd5e7b6f'
_CATS = {'t': 0, 'list': []}
_ITEM_PIC = {}
_FALLBACK = [
    ('58', '热播电影'), ('56', '小编推荐'), ('51', '国产AV'), ('10', '国产精品'), ('57', '黑料特爆'),
    ('53', '网红主播'), ('16', '欧美激情'), ('25', '三级电影'), ('14', 'H动漫'), ('41', '高清无码'),
    ('54', 'AV解说'), ('40', '美乳巨乳'), ('39', 'AV剧情'), ('36', '淫欲痴女'), ('35', '人妻熟女'),
    ('9', '绝色佳人'), ('46', '师生不伦'), ('38', '风俗按摩'), ('43', '家庭乱伦'), ('47', '绝顶痉挛'),
    ('42', '少女萝莉'), ('37', '制服丝袜'), ('44', '痴汉轮奸'), ('50', '女同性爱'), ('55', '恐怖系列'),
]


class Spider(Spider):
    host = 'http://sekihfde.com'
    ua = 'ok'
    classes = [{'type_name': n, 'type_id': i} for i, n in _FALLBACK]
    filters = {}

    def init(self, extend=''):
        pass

    def _get(self, u, timeout=10):
        for i in range(2):
            try:
                r = requests.get(u, headers={'User-Agent': self.ua}, timeout=timeout, verify=False)
                r.encoding = 'utf-8'
                if r.status_code == 200 and r.text:
                    return r.text
            except Exception:
                pass
            time.sleep(0.5)
        return ''

    def _cats(self):
        global _CATS
        if time.time() - _CATS['t'] > 3600 or not _CATS['list']:
            h = self._get(_API + '/videosort')
            try:
                j = json.loads(h or '')
                _CATS['list'] = [{'type_id': str(c['id']), 'type_name': c['name']} for c in j.get('rescont', [])]
                _CATS['t'] = time.time()
            except Exception:
                pass
        return _CATS['list'] or self.classes

    def _items(self, h):
        out = []
        try:
            j = json.loads(h or '')
            rc = j.get('rescont')
            data = rc.get('data') if isinstance(rc, dict) else rc
            if not isinstance(data, list):
                return out
            for it in data:
                _ITEM_PIC[str(it.get('id', ''))] = it.get('coverpath', '') or ''
                out.append({'vod_id': str(it.get('id', '')), 'vod_name': it.get('title', '') or '', 'vod_pic': it.get('coverpath', '') or '', 'vod_remarks': it.get('authername', '') or ''})
        except Exception:
            pass
        return out

    def _page(self, h):
        try:
            j = json.loads(h or '')
            rc = j.get('rescont')
            if isinstance(rc, dict):
                return int(rc.get('last_page') or 1), int(rc.get('total') or 0)
        except Exception:
            pass
        return 1, 0

    def getName(self):
        return '采花大盗'

    def isVideoFormat(self, u):
        return any(x in u for x in ('.m3u8', '.mp4', '.flv'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def homeContent(self, filter=False):
        return {'class': self._cats(), 'filters': self.filters, 'list': []}

    def homeVideoContent(self):
        h = self._get('%s/videosort/58?orderby=new&page=1' % _API)
        return {'list': self._items(h) if h else []}

    def categoryContent(self, tid, pg=1, filter=False, extend=''):
        pg = int(pg or 1)
        h = self._get('%s/videosort/%s?orderby=new&page=%d' % (_API, tid, pg))
        if not h:
            return {'page': pg, 'pagecount': 1, 'limit': 15, 'total': 0, 'list': []}
        pc, total = self._page(h)
        return {'page': pg, 'pagecount': pc, 'limit': 15, 'total': total, 'list': self._items(h)}

    def detailContent(self, ids):
        vid = str(ids[0])
        h = self._get('%s/videoplay/%s?uuid=%s' % (_API, vid, _PLAY_UUID))
        name = ''
        try:
            j = json.loads(h or '')
            rc = j.get('rescont') or {}
            name = rc.get('title', '') or ''
        except Exception:
            pass
        vod = {'vod_id': vid, 'vod_name': name, 'vod_pic': _ITEM_PIC.get(vid, ''), 'vod_remarks': '', 'vod_play_from': '线路1', 'vod_play_url': '第1集$%s/videoplay/%s?uuid=%s' % (_API, vid, _PLAY_UUID)}
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        h = self._get('%s/videosort/0?page=%s&serach=%s' % (_API, str(pg), urllib.parse.quote(key, safe='')))
        if not h:
            return {'page': int(pg or 1), 'pagecount': 1, 'limit': 15, 'total': 0, 'list': []}
        pc, total = self._page(h)
        return {'page': int(pg or 1), 'pagecount': pc, 'limit': 15, 'total': total, 'list': self._items(h)}

    def playerContent(self, flag, id, vipFlags=None):
        h = self._get(str(id))
        vp = ''
        try:
            j = json.loads(h or '')
            vp = (j.get('rescont') or {}).get('videopath', '') or ''
        except Exception:
            pass
        url = vp if vp.startswith('http') else ('http://sekihfde.com/api/index.m3u8?m3u8=' + vp if vp else '')
        return {'parse': 0, 'url': url, 'header': {'User-Agent': self.ua}}

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
