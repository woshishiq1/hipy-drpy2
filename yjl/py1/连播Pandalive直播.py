# -*- coding: utf-8 -*-
import requests
import random
import re


class Spider:
    def init(self, extend=""):
        self.host = "https://5721004.xyz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.pandalive.co.kr/',
            'Origin': 'https://www.pandalive.co.kr'
        }
        self.proxies = [
            "https://hubu.515355.xyz/proxy/?",
            "https://pol.515355.xyz/proxy/",
            "https://f00.515355.xyz/proxy/",
            "https://ce2.515355.xyz/proxy/?",
        ]
        self._cache = {}

    def getName(self):
        return "PandaLive"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        return None

    def _load_m3u(self):
        """解析 M3U 返回 {userId: {stream_url, annotations, tags}}"""
        if '_m3u' in self._cache:
            return self._cache['_m3u']
        m = {}
        try:
            r = requests.get(f"{self.host}/player/list.m3u", headers=self.headers, timeout=10)
            if r.status_code == 200:
                lines = r.text.split('\n')
                header_info = {}
                for line in lines[:10]:
                    if line.startswith('#主播数量'):
                        header_info['total'] = line.split('：')[-1].strip()
                    elif line.startswith('#列表说明'):
                        header_info['desc'] = line
                for i, line in enumerate(lines):
                    if line.startswith('#EXTINF') and i + 1 < len(lines):
                        parts = line.split(',')
                        if len(parts) >= 2:
                            uid = parts[1].strip()
                            nick_meta = parts[2].strip() if len(parts) > 2 else ''
                            # 提取注解: [录] [粉] [🎥] 等
                            tags = re.findall(r'\[([^\]]+)\]', nick_meta)
                            # 去掉注解后的纯昵称
                            clean_nick = re.sub(r'\[[^\]]*\]', '', nick_meta).strip()
                            m[uid] = {
                                'url': lines[i + 1].strip(),
                                'tags': tags,
                                'nick': clean_nick or uid,
                                'is_recorded': '录' in tags,
                                'is_fan': '粉' in tags,
                                'header_info': header_info,
                            }
        except Exception:
            pass
        self._cache['_m3u'] = m
        return m

    def _load_list(self):
        """加载 list.json + 合并 M3U 元数据，只返回有流的频道"""
        if '_list' in self._cache:
            return self._cache['_list']
        m3u = self._load_m3u()
        processed = []
        if not m3u:
            self._cache['_list'] = []
            return []
        try:
            r = requests.get(f"{self.host}/player/list.json", headers=self.headers, timeout=10)
            if r.status_code == 200:
                raw = r.json().get('list', [])
                # 按 m3u 顺序排列（m3u 顺序即主播列表手动更新顺序）
                seen = set()
                for uid in m3u:
                    if uid in seen:
                        continue
                    seen.add(uid)
                    # 查找 json 中对应条目
                    match = None
                    for item in raw:
                        if item.get('userId') == uid:
                            match = item
                            break
                    if not match:
                        continue
                    m3u_meta = m3u[uid]
                    nick = match.get('userNick', m3u_meta['nick'] or uid)
                    title = match.get('title', '無標題')
                    is_adult = match.get('isAdult', False)
                    is_pw = match.get('isPw', False)
                    v_type = match.get('type', '')
                    user_count = match.get('user', 0)
                    thumb = match.get('thumbUrl', '')
                    tags = list(m3u_meta['tags'])
                    if is_adult:
                        tags.append('19+')
                    tag_str = ' '.join(f'[{t}]' for t in tags)
                    processed.append({
                        'vod_id': f"live_{uid}",
                        'vod_name': f"📺 {nick}",
                        'vod_pic': thumb,
                        'vod_remarks': f"👤 {user_count} {tag_str}",
                        'vod_content': title or f'{nick} 的直播',
                        'vod_actor': uid,
                        'vod_tag': '录播' if m3u_meta['is_recorded'] else '直播',
                        '_isAdult': is_adult,
                        '_isPw': is_pw,
                        '_type': v_type,
                        '_isRecorded': m3u_meta['is_recorded'],
                        '_isFan': m3u_meta['is_fan'],
                        '_user_count': user_count,
                        '_score': match.get('totalScoreCnt', 0),
                        '_bookmark': match.get('bookmarkCnt', 0),
                    })
        except Exception:
            pass
        self._cache['_list'] = processed
        return processed

    def homeContent(self, filter):
        try:
            all_data = self._load_list()
            classes = [{'type_id': 'pandalive', 'type_name': f'🐼 PandaTV ({len(all_data)})'}]
            filters = {
                "pandalive": [
                    {
                        "key": "type",
                        "name": "類型",
                        "value": [
                            {"n": "全部", "v": "all"},
                            {"n": "🔞 19+", "v": "adult"},
                            {"n": "🔐 密碼房", "v": "pw"},
                            {"n": "💎 粉絲房", "v": "fan"},
                            {"n": "📼 錄播", "v": "recorded"},
                        ]
                    },
                    {
                        "key": "sort",
                        "name": "排序",
                        "value": [
                            {"n": "觀眾量 ↓", "v": "user-desc"},
                            {"n": "實時熱度 ↓", "v": "totalScoreCnt-desc"},
                            {"n": "關注量 ↓", "v": "bookmarkCnt-desc"},
                            {"n": "默認排序", "v": "default"},
                        ]
                    }
                ]
            }
            return {'class': classes, 'list': all_data[:30], 'filters': filters}
        except Exception as e:
            print(f"homeContent錯誤: {e}")
            return {'class': [], 'list': []}

    def homeVideoContent(self):
        try:
            return {'list': self._load_list()[:20]}
        except:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            all_list = self._load_list()
            filtered = all_list

            f_type = extend.get('type', 'all')
            if f_type == 'adult':
                filtered = [v for v in filtered if v.get('_isAdult')]
            elif f_type == 'pw':
                filtered = [v for v in filtered if v.get('_isPw')]
            elif f_type == 'fan':
                filtered = [v for v in filtered if v.get('_type') == 'fan' or v.get('_isFan')]
            elif f_type == 'recorded':
                filtered = [v for v in filtered if v.get('_isRecorded')]

            sort_type = extend.get('sort', 'default')
            if sort_type == 'user-desc':
                filtered.sort(key=lambda x: x.get('_user_count', 0), reverse=True)
            elif sort_type == 'totalScoreCnt-desc':
                filtered.sort(key=lambda x: x.get('_score', 0), reverse=True)
            elif sort_type == 'bookmarkCnt-desc':
                filtered.sort(key=lambda x: x.get('_bookmark', 0), reverse=True)

            pg = int(pg)
            limit = 30
            start = (pg - 1) * limit
            end = start + limit
            page_list = filtered[start:end] if start < len(filtered) else []

            return {
                'list': page_list,
                'page': pg,
                'pagecount': (len(filtered) + limit - 1) // limit if filtered else 1,
                'limit': limit,
                'total': len(filtered)
            }
        except Exception as e:
            print(f"categoryContent錯誤: {e}")
            return {'list': [], 'page': int(pg)}

    def detailContent(self, ids):
        try:
            first_id = ids[0] if isinstance(ids, list) else ids
            user_id = first_id.replace("live_", "")

            # 从缓存列表中找对应主播信息
            all_list = self._load_list()
            vod_info = None
            for v in all_list:
                if v['vod_id'] == first_id:
                    vod_info = v
                    break

            m3u = self._load_m3u()
            meta = m3u.get(user_id)
            if not meta:
                return {'list': []}

            stream_url = meta['url']

            # 随机打乱代理顺序，避免单线路过载
            shuffled = list(self.proxies)
            random.shuffle(shuffled)
            play_links = [f"代理{i}${p}{stream_url}" for i, p in enumerate(shuffled, 1)]

            vod = {
                'vod_id': first_id,
                'vod_name': vod_info['vod_name'] if vod_info else f"PandaTV - {user_id}",
                'vod_pic': vod_info.get('vod_pic', '') if vod_info else '',
                'vod_content': vod_info.get('vod_content', f'主播: {user_id}') if vod_info else f'主播: {user_id}',
                'vod_play_from': 'PandaLive',
                'vod_play_url': '#'.join(play_links)
            }
            return {'list': [vod]}
        except Exception as e:
            print(f"detailContent錯誤: {e}")
            return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        try:
            all_v = self._load_list()
            key_l = key.lower()
            res = [v for v in all_v if key_l in v['vod_name'].lower() or key_l in v['vod_actor'].lower()]
            return {'list': res[:50], 'page': int(pg)}
        except:
            return {'list': [], 'page': int(pg)}

    def playerContent(self, flag, id, vipFlags):
        return {
            'parse': 0,
            'url': id,
            'header': self.headers
        }

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
