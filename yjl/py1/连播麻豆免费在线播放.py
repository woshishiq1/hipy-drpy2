#合作请联系：邮箱meimenghuang75@gmail.com
"""
@header({
  searchable: 1,
  filterable: 0,
  quickSearch: 0,
  title: '麻豆免费在线播放',
  lang: 'hipy'
})
"""

import json, re, sys
from urllib import parse as urlparse
import requests as req
from pyquery import PyQuery as pq
sys.path.append('..')
from base.spider import Spider as BaseSpider

class Spider(BaseSpider):

    def getName(self):
        return self.name

    def init(self, extend='{}'):
        self.debug = False
        self.name = '麻豆免费在线播放'
        self.home_url = 'https://c-you.hair'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36'
        }
        self.extend = extend

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def liveContent(self, url):
        return {'list': [], 'code': 0, 'error': 0}

    # ---------- 首页分类 ----------
    def homeContent(self, filterable=False):
        result = {
            'class': [
                {'type_name': '国产精品', 'type_id': '6'},
                {'type_name': '中文字幕', 'type_id': '7'},
                {'type_name': '伦理影片', 'type_id': '8'},
                {'type_name': '自拍偷拍', 'type_id': '9'},
                {'type_name': '口交视频', 'type_id': '10'},
                {'type_name': '日韩无码', 'type_id': '11'},
                {'type_name': '制服诱惑', 'type_id': '12'},
                {'type_name': '国产色情', 'type_id': '13'},
            ],
            'filters': {},
            'list': [],
            'code': 0,
            'error': 0
        }
        return result

    # ---------- 首页推荐 ----------
    def homeVideoContent(self):
        result = {'list': [], 'code': 0, 'error': 0}
        try:
            r = req.get(self.home_url + '/', headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            items = doc('.col-md-3.resent-grid.recommended-grid')
            for item in items.items():
                a = item('.resent-grid-img a')
                href = a.attr('href') or ''
                title = item('h5 a.title').text().strip()
                img = item('.resent-grid-img img').attr('data-original') or ''
                views = item('.views-info span').text().strip()
                if href and title:
                    result['list'].append({
                        'vod_id': href,
                        'vod_name': title,
                        'vod_pic': img,
                        'vod_remarks': views + '观看' if views else '',
                    })
        except Exception as e:
            print(f'homeVideoContent error: {e}')
        return result

    # ---------- 一级分类列表 ----------
    def categoryContent(self, tid, pg, filterable, extend):
        result = {'list': [], 'page': pg, 'pagecount': pg, 'limit': 90, 'total': 999999, 'code': 0, 'error': 0}
        try:
            if int(pg) <= 1:
                url = f'{self.home_url}/vodtype/{tid}.html'
            else:
                url = f'{self.home_url}/vodtype/{tid}-{pg}.html'
            r = req.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            # 获取总页数
            page_info = doc('.pager .active a').text().strip()
            if '/' in page_info:
                total_pages = page_info.split('/')[-1].strip()
                result['pagecount'] = int(total_pages) if total_pages.isdigit() else pg
            else:
                result['pagecount'] = 9999
            items = doc('.col-md-3.resent-grid.recommended-grid')
            for item in items.items():
                a = item('.resent-grid-img a')
                href = a.attr('href') or ''
                title = item('h5 a.title').text().strip()
                img = item('.resent-grid-img img').attr('data-original') or ''
                views = item('.views-info span').text().strip()
                if href and title:
                    result['list'].append({
                        'vod_id': href,
                        'vod_name': title,
                        'vod_pic': img,
                        'vod_remarks': views + '观看' if views else '',
                    })
        except Exception as e:
            print(f'categoryContent error: {e}')
        return result

    # ---------- 二级详情 ----------
    def detailContent(self, ids):
        result = {'list': [], 'code': 0, 'error': 0}
        try:
            vod_id = ids[0]
            url = self.home_url + vod_id
            r = req.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            title = doc('.song-info h3').text().strip()
            img = doc('.video-grid img').attr('src') or ''
            # 影片介绍块
            info_text = doc('#myList li p').text().strip()
            # 提取发布时间和时长
            pub_time = ''
            duration = ''
            pub_match = re.search(r'发布时间：([\d\-]+)', info_text)
            if pub_match:
                pub_time = pub_match.group(1)
            dur_match = re.search(r'视频时长：(\S+)', info_text)
            if dur_match:
                duration = dur_match.group(1)
            # 分类标签
            category = ''
            cat_match = re.search(r'影片分类：(\S+)', info_text)
            if cat_match:
                category = cat_match.group(1).strip()
            # 简介内容
            content = info_text.split('​')[-1].strip() if '​' in info_text else ''
            if not content:
                # 尝试取最后一行非标签内容
                lines = [l.strip() for l in info_text.split('\n') if l.strip()]
                content = lines[-1] if lines else ''
            # 播放链接
            play_url = doc('a[href*="/vodplay/"]').attr('href') or ''
            play_from = '在线播放'
            play_url_formatted = ''
            if play_url:
                play_from = '在线播放'
                play_url_formatted = f'播放${play_url}'
            result['list'].append({
                'vod_id': vod_id,
                'vod_name': title if title else '',
                'vod_pic': img,
                'type_name': category,
                'vod_year': pub_time[:4] if len(pub_time) >= 4 else '',
                'vod_area': '',
                'vod_actor': '',
                'vod_director': '',
                'vod_remarks': duration,
                'vod_content': content,
                'vod_play_from': play_from,
                'vod_play_url': play_url_formatted,
            })
        except Exception as e:
            print(f'detailContent error: {e}')
        return result

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg=1):
        result = {'list': [], 'code': 0, 'error': 0}
        try:
            if int(pg) <= 1:
                url = f'{self.home_url}/vodsearch/{urlparse.quote(key)}-------------.html'
            else:
                url = f'{self.home_url}/vodsearch/{urlparse.quote(key)}-------------{pg}---.html'
            r = req.get(url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            doc = pq(r.text)
            items = doc('.col-md-3.resent-grid.recommended-grid')
            for item in items.items():
                a = item('.resent-grid-img a')
                href = a.attr('href') or ''
                title = item('h5 a.title').text().strip()
                img = item('.resent-grid-img img').attr('data-original') or ''
                views = item('.views-info span').text().strip()
                if href and title:
                    result['list'].append({
                        'vod_id': href,
                        'vod_name': title,
                        'vod_pic': img,
                        'vod_remarks': views + '观看' if views else '',
                    })
        except Exception as e:
            print(f'searchContent error: {e}')
        return result

    # ---------- 播放解析 ----------
    def playerContent(self, flag, pid, vipFlags):
        result = {
            'parse': 1,
            'playUrl': '',
            'url': '',
            'header': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1'
            }
        }
        try:
            play_url = self.home_url + pid
            r = req.get(play_url, headers=self.headers, timeout=10)
            r.encoding = 'utf-8'
            html = r.text
            # 尝试提取 player_data 或其他已知变量
            player_match = re.search(r'var\s+player_data\s*=\s*({.*?});', html, re.DOTALL)
            if player_match:
                player_json = json.loads(player_match.group(1))
                real_url = player_json.get('url', '')
                if real_url:
                    result['url'] = real_url
                    result['parse'] = 0
                    return result
            # 尝试匹配常见 iframe
            iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', html)
            if iframe_match:
                result['url'] = iframe_match.group(1)
                result['parse'] = 1
                return result
            # 尝试匹配 video 标签
            video_match = re.search(r'<video[^>]+src="([^"]+)"', html)
            if video_match:
                result['url'] = video_match.group(1)
                result['parse'] = 0
                return result
            # 尝试匹配 source 标签
            source_match = re.search(r'<source[^>]+src="([^"]+)"', html)
            if source_match:
                result['url'] = source_match.group(1)
                result['parse'] = 0
                return result
            # 兜底：嗅探模式，把播放页URL交给壳子嗅探
            result['url'] = play_url
            result['parse'] = 1
        except Exception as e:
            print(f'playerContent error: {e}')
        return result

    def localProxy(self, params):
        return [404, 'text/plain', 'Not Found']

    def destroy(self):
        return '正在Destroy'

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
