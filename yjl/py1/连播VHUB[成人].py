# coding: utf-8
import json
import sys
import re
import urllib.request
import urllib.parse
import ssl

sys.path.append('..')
from base.spider import Spider

VERSION = '2.0.0'

SITE_URL = 'https://newxvideos.pages.dev'
API_URL = 'https://newxvideos.pages.dev/api'

CATEGORIES = [
    {"type_id": "Arab-159", "type_name": "阿拉伯"},
    {"type_id": "Mature-38", "type_name": "成熟"},
    {"type_id": "Cuckold-237", "type_name": "出轨背叛"},
    {"type_id": "Femdom-235", "type_name": "调教"},
    {"type_id": "Anal-12", "type_name": "肛交"},
    {"type_id": "Brunette-25", "type_name": "褐发"},
    {"type_id": "Black_Woman-30", "type_name": "黑人"},
    {"type_id": "Redhead-31", "type_name": "红发"},
    {"type_id": "Fucked_Up_Family-81", "type_name": "家庭乱搞"},
    {"type_id": "Blonde-20", "type_name": "金发"},
    {"type_id": "Big_Cock-34", "type_name": "巨屌"},
    {"type_id": "Big_Tits-23", "type_name": "巨乳"},
    {"type_id": "Big_Ass-24", "type_name": "巨臀"},
    {"type_id": "Blowjob-15", "type_name": "口交"},
    {"type_id": "Latina-16", "type_name": "拉丁裔"},
    {"type_id": "Milf-19", "type_name": "辣妈"},
    {"type_id": "Gapes-167", "type_name": "裂开"},
    {"type_id": "Ass-14", "type_name": "美臀"},
    {"type_id": "Lesbian-26", "type_name": "女同"},
    {"type_id": "bbw-51", "type_name": "胖女"},
    {"type_id": "Squirting-56", "type_name": "喷出"},
    {"type_id": "Fisting-165", "type_name": "拳交"},
    {"type_id": "Gangbang-69", "type_name": "群交"},
    {"type_id": "Teen-13", "type_name": "少女"},
    {"type_id": "Cumshot-18", "type_name": "射颜"},
    {"type_id": "Cam_Porn-58", "type_name": "摄像头"},
    {"type_id": "Bi_Sexual-62", "type_name": "双性恋"},
    {"type_id": "Stockings-28", "type_name": "丝袜"},
    {"type_id": "Oiled-22", "type_name": "涂油"},
    {"type_id": "Lingerie-83", "type_name": "性感内衣"},
    {"type_id": "Asian_Woman-32", "type_name": "亚洲"},
    {"type_id": "Amateur-65", "type_name": "业余"},
    {"type_id": "Interracial-27", "type_name": "异族"},
    {"type_id": "Indian-89", "type_name": "印度"},
    {"type_id": "Creampie-40", "type_name": "中出"},
    {"type_id": "Solo_and_Masturbation-33", "type_name": "自慰"},
    {"type_id": "AI-239", "type_name": "AI"},
    {"type_id": "ASMR-229", "type_name": "ASMR"},
]


class Spider(Spider):
    def getName(self):
        return "V-HUB[成人]"

    def init(self, extend):
        if extend:
            self.host = extend.get('host', SITE_URL)
        else:
            self.host = SITE_URL
        self.api_url = self.host.rstrip('/') + '/api'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.host + '/',
            'Origin': self.host
        }
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _xhttp(self, params):
        """使用标准库urllib发起HTTP GET请求"""
        try:
            qs = urllib.parse.urlencode(params)
            full_url = self.api_url + '?' + qs
            req = urllib.request.Request(full_url, headers=self.headers, method='GET')
            resp = urllib.request.urlopen(req, context=self._ssl_context, timeout=15)
            data = json.loads(resp.read().decode('utf-8'))
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'data' in data:
                return data['data']
            return []
        except Exception as e:
            print('_xhttp error: %s' % str(e), file=sys.stderr)
            return []

    def _format_time_cn(self, time_str):
        """将英文时间格式转为中文，如 '11 min' -> '11分钟'"""
        if not time_str:
            return ''
        m = re.match(r'^(\d+)\s*min\s*$', time_str.strip(), re.IGNORECASE)
        if m:
            return m.group(1) + '分钟'
        m = re.match(r'^(\d+)\s*h(?:our)?s?\s*(\d+)?\s*min\s*$', time_str.strip(), re.IGNORECASE)
        if m:
            h = m.group(1)
            mi = m.group(2)
            if mi:
                return h + '小时' + mi + '分钟'
            return h + '小时'
        return time_str

    def _extract_xvid(self, url):
        """从视频URL的查询参数中提取xvid值"""
        if not url:
            return ''
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if 'xvid' in qs:
            return qs['xvid'][0]
        return ''

    def _build_vod_list(self, raw_data):
        """将API返回的原始数据构造为vod列表"""
        videos = []
        for item in raw_data:
            title = item.get('title', '')
            clean_title = re.sub(r'^AVOTC资源网[—-]+\s*', '', title).strip()
            if not clean_title:
                clean_title = title

            url = item.get('url', '')
            vod_id = self._extract_xvid(url)
            if not vod_id:
                vod_id = str(item.get('videoid', ''))

            videos.append({
                'vod_id': vod_id,
                'vod_name': clean_title,
                'vod_pic': item.get('img', ''),
                'vod_remarks': self._format_time_cn(item.get('time', '')),
                'vod_url': url
            })
        return videos

    def homeContent(self, filter):
        """首页：返回分类列表 + 首页视频"""
        classes = []
        for cat in CATEGORIES:
            classes.append({'type_id': cat['type_id'], 'type_name': cat['type_name']})

        raw_data = self._xhttp({'play': 'list', 'page': 1})
        videos = self._build_vod_list(raw_data)

        return {'class': classes, 'list': videos}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容"""
        raw_data = self._xhttp({'play': 'class', 'c': tid, 'page': pg})
        videos = self._build_vod_list(raw_data)

        type_name = tid
        for cat in CATEGORIES:
            if cat['type_id'] == tid:
                type_name = cat['type_name']
                break

        return {
            'page': int(pg),
            'pagecount': 9999,
            'limit': 90,
            'total': 9999,
            'type_name': type_name,
            'list': videos
        }

    def detailContent(self, array):
        """详情：通过xvid获取视频播放地址"""
        result = {}
        if not array or not array[0]:
            return result

        xvid = array[0]
        vod = {
            'vod_id': xvid,
            'vod_name': '视频详情',
            'vod_pic': '',
            'vod_remarks': '',
            'vod_play_from': 'newxvideos',
            'vod_play_url': ''
        }

        try:
            qs = urllib.parse.urlencode({'xvid': xvid})
            full_url = self.api_url + '?' + qs
            req = urllib.request.Request(full_url, headers=self.headers, method='GET')
            resp = urllib.request.urlopen(req, context=self._ssl_context, timeout=15)
            data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print('detailContent error: %s' % str(e), file=sys.stderr)
            result['list'] = [vod]
            return result

        play_urls = []

        if isinstance(data, dict):
            item = data
            if 'data' in data and isinstance(data['data'], dict):
                item = data['data']

            hls_url = item.get('hls') or item.get('m3u8') or ''
            hight_url = item.get('hight') or item.get('high') or item.get('hd') or ''
            low_url = item.get('low') or item.get('sd') or ''

            if hls_url:
                play_urls.append('高清HLS$' + hls_url)
            if hight_url:
                play_urls.append('高清MP4$' + hight_url)
            if low_url:
                play_urls.append('低清MP4$' + low_url)

            title = item.get('title', '')
            if title:
                clean_title = re.sub(r'^AVOTC资源网[—-]+\s*', '', title).strip()
                if clean_title:
                    vod['vod_name'] = clean_title

            img = item.get('img', '')
            if img:
                vod['vod_pic'] = img

            time_str = item.get('time', '')
            if time_str:
                vod['vod_remarks'] = self._format_time_cn(time_str)

        elif isinstance(data, list):
            for item in data:
                hls_url = item.get('hls') or item.get('m3u8') or ''
                hight_url = item.get('hight') or item.get('high') or item.get('hd') or ''
                low_url = item.get('low') or item.get('sd') or ''

                if hls_url:
                    play_urls.append('高清HLS$' + hls_url)
                if hight_url:
                    play_urls.append('高清MP4$' + hight_url)
                if low_url:
                    play_urls.append('低清MP4$' + low_url)

                if vod['vod_name'] == '视频详情':
                    title = item.get('title', '')
                    if title:
                        clean_title = re.sub(r'^AVOTC资源网[—-]+\s*', '', title).strip()
                        if clean_title:
                            vod['vod_name'] = clean_title
                    img = item.get('img', '')
                    if img:
                        vod['vod_pic'] = img
                    time_str = item.get('time', '')
                    if time_str:
                        vod['vod_remarks'] = self._format_time_cn(time_str)

        if play_urls:
            vod['vod_play_url'] = '#'.join(play_urls)

        result['list'] = [vod]
        return result

    def searchContent(self, key, quick, pg='1'):
        """搜索"""
        raw_data = self._xhttp({'play': 'k', 'k': key, 'page': pg})
        videos = self._build_vod_list(raw_data)

        return {
            'page': int(pg),
            'pagecount': 9999,
            'limit': 90,
            'total': 9999,
            'list': videos
        }

    def playerContent(self, flag, id, vipFlags):
        """播放地址解析 - 直接返回用户选择的清晰度地址"""
        if id and (id.startswith('http://') or id.startswith('https://')):
            return {
                'parse': 0,
                'playUrl': '',
                'url': id,
                'header': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.host + '/'
                }
            }
        return {'parse': 0, 'playUrl': '', 'url': '', 'header': {}}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return {}

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
