#!/usr/bin/python
# -*- coding: utf-8 -*-
#18hlw@pm.me
import sys, json, re, requests, urllib3
from urllib.parse import quote, unquote
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def getName(self):
        return "黑料网"

    def isVideoFormat(self, url):
        if not url:
            return False
        if url.startswith(('novel://', 'text://', 'pics://', 'book_', 'comic_')):
            return False
        return '.mp4' in url or '.m3u8' in url or '.ts' in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'Referer': 'https://heiliao.com/',
    }
    host = 'https://heiliao.com'
    publish_urls = ['https://heiliao74.com/', 'https://hlgw18.com/', 'https://www.heiliao88.com/']
    fallback_hosts = ['https://sridy.bolbdzrv.cc', 'https://b48tu.kypozbnd.cc', 'https://ds6r63epm75a1.cloudfront.net', 'https://heiliao.com']
    cat_map = {
        'hlcg': '最新黑料', 'jrrs': '今日热瓜', 'jqrm': '热门黑料', 'lsdg': '经典黑料',
        'xycg': '校园黑料', 'whhl': '网红黑料', 'fczq': '反差专区', 'ycsq': '原创社区',
        'mxcw': '明星丑闻', 'mrds': '每日大赛', 'qqqw': '全球奇闻', 'ttsq': '推特社区',
        'ysdj': '影视短剧', 'whhj': '网黄合集', 'shxw': '社会新闻', 'thzq': '探花专区',
        'cpcd': '厕拍抄底', 'yqby': '有求必应', 'syzy': '深夜综艺', 'djbl': '独家爆料',
        'jqxs': '黑料小说', 'gchl': '官场爆料', 'hlkt': '黑料课堂', 'hlbg': '黑料爆改',
        'ttzz': '桃图杂志', 'mrrb': '日榜黑料', 'zbjx': '周榜精选', 'ybrg': '月榜热瓜',
    }
    ad_ids = {'39668', '8148', '8147', '8150', '8146', '38757', '41525', '109358', '109356', '106394', '97869'}
    ad_keywords = ('黑料网最新入口', '黑料网海外主站', '黑料APP', '获取最新地址', '发送任意内容至')
    list_ad_keywords = (
        '全新上线', '正式入驻', 'App Store', 'AppStore', 'APP下载', 'App下载', 'App官方',
        '官方运营', '外围招募', '主播/外围', '最新入口', '回家路',
        '棋牌', '娱乐城', '开元', '约炮', 'PG电子', 'PG免费', 'PG娱乐', '官方PG', '官方开元',
    )

    def init(self, extend=""):
        self.session = requests.Session()
        self.host = self.get_working_host()
        self.headers = dict(self.headers)
        self.headers['Referer'] = self.host + '/'

    def get_working_host(self):
        candidates = []
        for pu in self.publish_urls:
            try:
                r = requests.get(pu, headers=self.headers, timeout=8, verify=False)
                if r.status_code != 200:
                    continue
                r.encoding = r.apparent_encoding or 'utf-8'
                for href in re.findall(r'<a[^>]*class="[^"]*line-long[^"]*"[^>]*href="([^"]+)"', r.text):
                    h = href.strip().rstrip('/')
                    if h.startswith('http') and h not in candidates:
                        candidates.append(h)
            except Exception:
                continue
        for c in self.fallback_hosts:
            if c not in candidates:
                candidates.append(c)
        for c in candidates:
            try:
                r = requests.get(c + '/', headers=self.headers, timeout=6, verify=False)
                if r.status_code != 200:
                    continue
                r.encoding = r.apparent_encoding or 'utf-8'
                if 'video-item' in r.text:
                    return c
            except Exception:
                continue
        return self.fallback_hosts[0]

    def _get(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=20)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        except:
            return ''

    def _clean_pic(self, pic):
        if not pic:
            return ''
        if pic.startswith('http'):
            abs_url = pic
        elif pic.startswith('/'):
            abs_url = f'{self.host}{pic}'
        else:
            abs_url = f'{self.host}/{pic}'
        return f"{self.getProxyUrl()}&url={quote(abs_url, safe='')}"

    def _parse_list(self, html):
        items = []
        if not html:
            return items
        pat = r'<div[^>]*class="video-item"[^>]*>(.*?)(?=<div[^>]*class="video-item"[^>]*>|<div[^>]*class="[^"]*page[^"]*"|<div[^>]*class="[^"]*pagination[^"]*"|$)'
        for block in re.finditer(pat, html, re.S):
            b = block.group(1)
            pid_m = re.search(r'archives/(\d+)/', b)
            if not pid_m:
                continue
            pid = pid_m.group(1)
            if pid in self.ad_ids:
                continue
            pic_m = re.search(r'z-image-loader-url=["\']([^"\']+)["\']', b)
            pic = pic_m.group(1).strip() if pic_m else ''
            if not pic:
                continue
            alt_m = re.search(r'alt=["\']([^"\']+)["\']', b)
            title = alt_m.group(1).strip() if alt_m else ''
            if not title:
                continue
            if any(kw in title for kw in self.list_ad_keywords):
                continue
            items.append({"vod_id": pid, "vod_name": title, "vod_pic": self._clean_pic(pic)})
        return items

    def _parse_pagecount(self, html):
        if not html:
            return 1
        nums = re.findall(r'/page/(\d+)/', html)
        return max(int(n) for n in nums) if nums else 1

    def homeContent(self, filter):
        try:
            cats = [{'type_id': k, 'type_name': v} for k, v in self.cat_map.items()]
            return {"class": cats, "list": [], "filters": {}}
        except:
            return {"class": [], "filters": {}, "list": [], "page": 1, "pagecount": 1}

    def homeVideoContent(self):
        try:
            html = self._get(self.host)
            return {"list": self._parse_list(html)[:20]}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            url = f"{self.host}/{tid}/" if page == 1 else f"{self.host}/{tid}/page/{page}/"
            html = self._get(url)
            return {"page": page, "pagecount": self._parse_pagecount(html), "list": self._parse_list(html)}
        except:
            return {"page": int(pg) if pg else 1, "pagecount": 1, "list": []}

    def detailContent(self, ids):
        try:
            vid = ids[0]
            html = self._get(f"{self.host}/archives/{vid}")
            if not html:
                return {"list": []}
            title_m = re.search(r'<h1[^>]*class="[^"]*detail-title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else f"黑料{vid}"

            cs = re.search(r'<div[^>]*class="[^"]*editormd-preview[^"]*"[^>]*>(.*?)(?=<div[^>]*class="[^"]*article-tags|<div[^>]*class="[^"]*article-meta|</article|$)', html, re.S)
            content = cs.group(1) if cs else ''

            img_urls = []
            for m in re.finditer(r'z-image-loader-url=["\']([^"\']+)["\']', content):
                u = m.group(1).strip()
                if not u or not u.startswith('http'):
                    continue
                if 'pic.uforxk.cn' not in u and 'upload_01' not in u:
                    continue
                am = re.search(r'alt=["\']([^"\']*)["\']', content[m.end():m.end()+200])
                alt = am.group(1).strip() if am else ''
                if alt and len(alt) >= 20 and re.fullmatch(r'[0-9a-fA-F]+', alt):
                    continue
                img_urls.append(self._clean_pic(u))

            video_eps_main = []
            video_eps_backup = []
            cover_pic = ''
            dp_idx = 0
            for dp in re.finditer(r"<div[^>]*class=\"[^\"]*dplayer[^\"]*\"[^>]*config='([^']*)'", html):
                cfg_str = dp.group(1).replace('&quot;', '"').replace('&amp;', '&')
                try:
                    cfg = json.loads(cfg_str)
                    v = cfg.get('video', {})
                    if dp_idx == 0 and v.get('pic'):
                        cover_pic = self._clean_pic(v.get('pic'))
                    urls = v.get('urls', [])
                    ep_name = f"第{dp_idx+1}集"
                    ep_raw_title = v.get('title', '') or ''
                    m_ep = re.search(r'(\d+)$', ep_raw_title)
                    if m_ep:
                        ep_name = f"第{int(m_ep.group(1))}集"
                    if urls:
                        video_eps_main.append(f"{ep_name}${urls[0].get('url', '')}")
                        if len(urls) > 1:
                            video_eps_backup.append(f"{ep_name}${urls[1].get('url', '')}")
                    elif v.get('url'):
                        video_eps_main.append(f"{ep_name}${v.get('url')}")
                    dp_idx += 1
                except:
                    continue

            raw_text = re.sub(r'<[^>]+>', '\n', content)
            raw_text = re.sub(r'\n{3,}', '\n\n', raw_text).strip()
            text_parts = []
            for line in raw_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if any(kw in line for kw in self.ad_keywords):
                    continue
                if line.startswith('黑料网') and '最新入口' in line:
                    continue
                if '海外主站' in line or '中转' in line:
                    continue
                text_parts.append(line)
            full_text = '\n'.join(text_parts)

            pic = cover_pic or (img_urls[0] if img_urls else '')

            from_names = []
            ep_parts = []
            if video_eps_main:
                from_names.append('视频')
                ep_parts.append('#'.join(video_eps_main))
                if video_eps_backup:
                    from_names.append('备用')
                    ep_parts.append('#'.join(video_eps_backup))
            if img_urls:
                from_names.append('图文')
                ep_parts.append(f'图片$pics://{"&&".join(img_urls)}')
            if from_names:
                vod = {
                    "vod_id": vid, "vod_name": title, "vod_remarks": "",
                    "vod_pic": pic, "vod_content": full_text[:500],
                    "vod_play_from": "$$$".join(from_names),
                    "vod_play_url": "$$$".join(ep_parts),
                }
            else:
                short = full_text[:300]
                vod = {
                    "vod_id": vid, "vod_name": title, "vod_remarks": "",
                    "vod_pic": pic, "vod_content": full_text[:500],
                    "vod_play_from": "文字",
                    "vod_play_url": f"阅读${short}",
                }
            return {"list": [vod]}
        except:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            kw = quote(key)
            url = f"{self.host}/?s={kw}" if page == 1 else f"{self.host}/page/{page}/?s={kw}"
            html = self._get(url)
            return {"list": self._parse_list(html), "page": page}
        except:
            return {"list": [], "page": int(pg) if pg else 1}

    def playerContent(self, flag, id, vipFlags):
        try:
            if flag == '视频' or flag == '备用':
                return {"parse": 0, "url": id, "header": self.headers, "position": "0"}
            if flag == '图文' or id.startswith('pics://'):
                return {"parse": 0, "playUrl": "", "url": id.replace('图片', ''), "header": self.headers, "position": "0"}
            if flag == '文字' or '阅读' in id:
                content = id.replace('阅读', '')
                if '$$$' in content:
                    content = content.split('$$$')[-1]
                nj = json.dumps({"title": content[:50], "content": content}, ensure_ascii=False)
                return {"parse": 0, "url": f"novel://{nj}", "header": "", "vod_player": "书", "position": "0"}
            if id.startswith('pics://'):
                return {"parse": 0, "playUrl": "", "url": id, "header": self.headers, "position": "0"}
            if id.startswith('http'):
                return {"parse": 0, "url": id, "header": self.headers, "position": "0"}
            return {"parse": 0, "url": id, "header": self.headers, "position": "0"}
        except:
            return {"parse": 0, "url": "", "position": "0"}

    def _img_decrypt(self, data):
        try:
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            key = ''.join(chr(int(c)) for c in '102_53_100_57_54_53_100_102_55_53_51_51_54_50_55_48'.split('_')).encode('utf-8')
            iv = ''.join(chr(int(c)) for c in '57_55_98_54_48_51_57_52_97_98_99_50_102_98_101_49'.split('_')).encode('utf-8')
            cipher = AES.new(key, AES.MODE_CBC, iv)
            dec = cipher.decrypt(data)
            dec = unpad(dec, AES.block_size)
            return dec
        except:
            return data

    def localProxy(self, param):
        try:
            url = param.get('url', '')
            if not url:
                return [404, 'text/plain', b'not found']
            url = unquote(url)
            r = self.session.get(url, headers={'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}, timeout=15, verify=False)
            data = r.content
            if not data:
                return [404, 'text/plain', b'not found']
            dec = self._img_decrypt(data)
            if dec[:2] == b'\xff\xd8':
                data, ct = dec, 'image/jpeg'
            elif dec[:4] == b'\x89PNG':
                data, ct = dec, 'image/png'
            elif dec[:4] == b'RIFF' and dec[8:12] == b'WEBP':
                data, ct = dec, 'image/webp'
            elif data[:2] == b'\xff\xd8':
                ct = 'image/jpeg'
            elif data[:4] == b'\x89PNG':
                ct = 'image/png'
            elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                ct = 'image/webp'
            else:
                ct = r.headers.get('Content-Type', 'image/jpeg')
            return [200, ct, data, {'Content-Length': str(len(data))}]
        except:
            return [404, 'text/plain', b'not found']

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
