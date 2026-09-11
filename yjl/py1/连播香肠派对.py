# -*- coding: utf-8 -*-
import re
import json
import urllib.parse
from urllib.parse import urljoin, quote
import sys
sys.path.append('..')
from base.spider import Spider
from bs4 import BeautifulSoup

class Spider(Spider):
    def getName(self):
        return "香肠派对"

    def init(self, extend=""):
        self.host = "https://xiang512.xiang.party/xcpd"
        pass

    def header(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'Referer': self.host
        }

    def homeContent(self, filter):
        result = {"class": [], "filters": {}, "list": []}
        
        # 分类列表
        classes = [
            {"type_id": "1", "type_name": "在线看片"},
            {"type_id": "2", "type_name": "无需等待"},
            {"type_id": "3", "type_name": "不用下载"},
            {"type_id": "4", "type_name": "全部免费"}
        ]
        result["class"] = classes
        
        # 获取首页视频
        url = f"{self.host}/"
        rsp = self.fetch(url, headers=self.header())
        if rsp.status_code != 200:
            return result
        
        root = BeautifulSoup(rsp.text, 'html.parser')
        videos = []
        
        # 查找视频列表
        items = root.select('ul.thumbnail-group.clearfix li')
        for item in items:
            try:
                a = item.select_one('a.thumbnail')
                if not a:
                    continue
                href = a.get('href', '')
                vod_id = re.search(r'/vod(?:detail|play)/(\d+)', href)
                if not vod_id:
                    continue
                vod_id = vod_id.group(1)
                
                img = a.select_one('img')
                pic = img.get('src', '') if img else ''
                
                info = item.select_one('.video-info')
                if info:
                    h5 = info.select_one('h5 a')
                    name = h5.get('title', '') if h5 else ''
                    if not name:
                        name = h5.text.strip() if h5 else ''
                    p = info.select_one('p')
                    remarks = p.text.strip() if p else ''
                else:
                    name = a.get('title', '')
                    remarks = ''
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
                if len(videos) >= 20:
                    break
            except:
                continue
        
        result["list"] = videos
        return result

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        p = int(pg)
        # 修复分页URL格式
        url = f"{self.host}/vodtype/{tid}-{p}.html"
        rsp = self.fetch(url, headers=self.header())
        if rsp.status_code != 200:
            return {"list": [], "page": p, "pagecount": 1}
        
        root = BeautifulSoup(rsp.text, 'html.parser')
        videos = []
        
        # 提取总页数（从“共XX条数据,当前X/913页”）
        pagecount = p
        page_info = root.find(string=re.compile(r'共\d+条数据,当前\d+/(\d+)页'))
        if page_info:
            try:
                pagecount = int(re.search(r'/(\d+)页', page_info).group(1))
            except:
                pass
        
        # 提取视频列表
        items = root.select('ul.thumbnail-group.clearfix li')
        for item in items:
            try:
                a = item.select_one('a.thumbnail')
                if not a:
                    continue
                href = a.get('href', '')
                vod_id = re.search(r'/vod(?:detail|play)/(\d+)', href)
                if not vod_id:
                    continue
                vod_id = vod_id.group(1)
                
                img = a.select_one('img')
                pic = img.get('src', '') if img else ''
                
                info = item.select_one('.video-info')
                if info:
                    h5 = info.select_one('h5 a')
                    name = h5.get('title', '') if h5 else ''
                    if not name:
                        name = h5.text.strip() if h5 else ''
                    p_elem = info.select_one('p')
                    remarks = p_elem.text.strip() if p_elem else ''
                else:
                    name = a.get('title', '')
                    remarks = ''
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
            except:
                continue
        
        return {
            "list": videos,
            "page": p,
            "pagecount": pagecount
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids.split(",")[0]
        url = f"{self.host}/voddetail/{vid}.html"
        rsp = self.fetch(url, headers=self.header())
        if rsp.status_code != 200:
            return {"list": []}
        
        root = BeautifulSoup(rsp.text, 'html.parser')
        
        # 标题
        title = ""
        h1 = root.select_one('h1.appel-title')
        if h1:
            title = h1.text.strip()
        if not title:
            title_elem = root.select_one('title')
            if title_elem:
                title = title_elem.text.replace('视频介绍--香肠派对', '').strip()
        
        # 图片
        pic = ""
        img = root.select_one('img.appel-img')
        if img:
            pic = img.get('src', '')
        if not pic:
            img = root.select_one('.detail-poster img')
            if img:
                pic = img.get('src', '')
        
        # 描述
        desc = ""
        desc_elem = root.select_one('.detail-content')
        if desc_elem:
            desc = desc_elem.text.strip()
        if not desc:
            desc_elem = root.select_one('.appel-content')
            if desc_elem:
                desc = desc_elem.text.strip()
        
        # 播放列表
        play_from_list = []
        play_url_list = []
        
        # 查找线路
        tabs = root.select('.detail-tab li a')
        play_blocks = root.select('ul.detail-play-list')
        
        for i, block in enumerate(play_blocks):
            line_name = tabs[i].text.strip() if i < len(tabs) else f"线路{i+1}"
            urls = []
            for a in block.select('a'):
                href = a.get('href', '')
                if href:
                    full_url = urljoin(self.host, href)
                    name = a.text.strip() or f"第{len(urls)+1}集"
                    urls.append(f"{name}${full_url}")
            if urls:
                play_from_list.append(line_name)
                play_url_list.append("#".join(urls))
        
        # 如果没有找到，尝试其他选择器
        if not play_from_list:
            lines = root.select('.ff-playurl-tab li a')
            for i, block in enumerate(root.select('.ff-playurl-tab-pane')):
                line_name = lines[i].text.strip() if i < len(lines) else f"线路{i+1}"
                urls = []
                for a in block.select('a'):
                    href = a.get('href', '')
                    if href:
                        full_url = urljoin(self.host, href)
                        name = a.text.strip() or f"第{len(urls)+1}集"
                        urls.append(f"{name}${full_url}")
                if urls:
                    play_from_list.append(line_name)
                    play_url_list.append("#".join(urls))
        
        vod_play_from = "$$$".join(play_from_list) if play_from_list else ""
        vod_play_url = "$$$".join(play_url_list) if play_url_list else ""
        
        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }]}

    def searchContent(self, key, quick, pg="1"):
        p = int(pg)
        url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={p}"
        rsp = self.fetch(url, headers=self.header())
        if rsp.status_code != 200:
            return {"list": []}
        
        root = BeautifulSoup(rsp.text, 'html.parser')
        videos = []
        
        items = root.select('ul.thumbnail-group.clearfix li')
        for item in items:
            try:
                a = item.select_one('a.thumbnail')
                if not a:
                    continue
                href = a.get('href', '')
                vod_id = re.search(r'/vod(?:detail|play)/(\d+)', href)
                if not vod_id:
                    continue
                vod_id = vod_id.group(1)
                
                img = a.select_one('img')
                pic = img.get('src', '') if img else ''
                
                info = item.select_one('.video-info')
                if info:
                    h5 = info.select_one('h5 a')
                    name = h5.get('title', '') if h5 else ''
                    if not name:
                        name = h5.text.strip() if h5 else ''
                    p_elem = info.select_one('p')
                    remarks = p_elem.text.strip() if p_elem else ''
                else:
                    name = a.get('title', '')
                    remarks = ''
                
                videos.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
            except:
                continue
        
        return {"list": videos, "page": p}

    def playerContent(self, flag, id, vipFlags):
        # 构建播放页URL
        if id.startswith('http'):
            play_url = id
        else:
            play_url = urljoin(self.host, id)
        
        rsp = self.fetch(play_url, headers=self.header())
        if rsp.status_code != 200:
            return {"parse": 0, "playUrl": play_url}
        
        html = rsp.text
        
        # 方法1：从 player_aaaa 提取
        match = re.search(r'var player_aaaa\s*=\s*({.*?});', html, re.DOTALL)
        if match:
            try:
                js_str = match.group(1)
                js_str = re.sub(r'(\w+):', r'"\1":', js_str)
                player_data = json.loads(js_str)
                if player_data.get('url'):
                    return {"parse": 0, "playUrl": player_data['url']}
            except:
                pass
        
        # 方法2：从 iframe 提取（关键修复）
        # 匹配 id="playleft" 的 td 中的 iframe
        iframe_match = re.search(r'<td[^>]*id="playleft"[^>]*>.*?<iframe[^>]+src="([^"]+)"', html, re.DOTALL)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            # 提取 url 参数
            m3u8_match = re.search(r'[?&]url=([^&]+)', iframe_url)
            if m3u8_match:
                m3u8_url = urllib.parse.unquote(m3u8_match.group(1))
                return {"parse": 0, "playUrl": m3u8_url}
            # 如果 iframe 本身就是 m3u8
            if '.m3u8' in iframe_url:
                return {"parse": 0, "playUrl": iframe_url}
        
        # 方法3：直接查找 iframe
        iframe_match2 = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if iframe_match2:
            iframe_url = iframe_match2.group(1)
            m3u8_match = re.search(r'[?&]url=([^&]+)', iframe_url)
            if m3u8_match:
                m3u8_url = urllib.parse.unquote(m3u8_match.group(1))
                return {"parse": 0, "playUrl": m3u8_url}
        
        # 方法4：直接查找 m3u8
        m3u8 = re.search(r'https?://[^"\']+\.m3u8[^"\']*', html)
        if m3u8:
            return {"parse": 0, "playUrl": m3u8.group(0)}
        
        # 方法5：让系统解析
        return {"parse": 1, "url": play_url}

    def localProxy(self, params):
        return [200, "video/MP2T", ""]

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
