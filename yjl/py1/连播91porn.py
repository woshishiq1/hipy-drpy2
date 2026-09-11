# coding: utf-8
import re
import sys
import urllib.parse
import requests
import json
from pyquery import PyQuery as pq
import time

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def __init__(self):
        self.name = '91pron'
        # 定义主域名列表，按优先级排序，请求失败时会自动轮询尝试下一个
        self.hosts = [
            'https://0708.fs708.com/',
            'https://a.91kp.net/',
            'https://91porn.com/'
        ]
        self.host = self.hosts[0]  # 默认使用第一个有效域名
        
        # 1. 选用 PC 端标准 Chrome 请求头，配合防抓取 Cookie
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': self.host,
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 2. 初始化 Session 对象（可自动跨请求保持/累计 Cookie）
        self.session = requests.Session()
        
        # 3. 设置基础初始化 Cookie
        self.cookies = {
            'language': 'cn_CN', 
            'over18': '1',
            'CLIPSHARE': '1'
        }
        # 将基础 Cookie 写入 session，确保后续请求全局生效
        self.session.cookies.update(self.cookies)

        self.class_map = {
            '最新': 'watch',
            '91原创': 'ori',
            '当前最热': 'hot',
            '本月最热': 'top',
            '10分钟以上': 'long',
            '20分钟以上': 'longer',
            '本月收藏': 'tf',
            '最近加精': 'rf',
            '高清': 'hd',
            '每月最热': 'top_m',
            '本月讨论': 'md',
            '收藏最多': 'mf'
        }

    def getName(self):
        return self.name

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        return any(ext in (url or '').lower() for ext in ['.m3u8', '.mp4', '.ts'])

    def manualVideoCheck(self):
        return False

    def _abs_href(self, href):
        if not href:
            return ''
        if href.startswith('http'):
            return href
        if href.startswith('//'):
            return f"https:{href}"
        return f"{self.host.rstrip('/')}/{href.lstrip('/')}"

    def _parse_video_items(self, data):
        vlist = []
        seen_ids = set()
        
        # 1. 从最外层 BootStrap 网格容器入手匹配
        # 正常渲染卡片带有 col-lg-3，而干扰/混淆卡片带有 col-lg-8
        containers = data('div[class*="col-xs-12"]').items()
        
        for container in containers:
            try:
                # 核心修复 1：严格判断最外层容器的类名，跳过 col-lg-8 混淆卡片和广告项
                container_class = (container.attr('class') or '').lower()
                if 'col-lg-8' in container_class or 'ad' in container_class or 'sponsor' in container_class:
                    continue

                # 在安全的容器内部寻找卡片内容
                item = container('.well.well-sm, .videos-text-align')
                if not item:
                    item = container

                # 必须包含有效的 view_video.php 视频播放链接
                a_elem = item('a[href*="view_video.php"]')
                if not a_elem:
                    continue
                
                href = self._abs_href(a_elem.attr('href'))
                
                # 核心修复 2：真实视频链接必须包含 viewkey 参数，排除纯广告跳转/错误链接
                if not href or 'viewkey=' not in href:
                    continue
                
                # 提取 viewkey 作为唯一标识进行严格排重
                vk_match = re.search(r'viewkey=([a-zA-Z0-9]+)', href)
                vk_id = vk_match.group(1) if vk_match else href
                
                if vk_id in seen_ids:
                    continue

                # 提取标题
                title_elem = item('span[class*="video-title"], .video-title')
                title = title_elem.text().strip()
                if not title:
                    title = a_elem.attr('title') or a_elem.text().strip()
                if not title or any(ad_kw in title.lower() for ad_kw in ['广告', 'sponsor', '推广', '赞助']):
                    continue

                # 提取封面图片地址
                pic = ''
                img_elem = item('img')
                if img_elem:
                    pic = (
                        img_elem.attr('data-src') or 
                        img_elem.attr('data-original') or 
                        img_elem.attr('src') or ''
                    )
                
                # 兜底：处理背景图形式的图片
                if not pic:
                    style = item('.img-responsive, .video-img, div[style*="background"]').attr('style') or ''
                    if 'background' in style and 'url(' in style:
                        bg_m = re.search(r'url\([\'"]?([^\'"\)]+)[\'"]?\)', style)
                        if bg_m:
                            pic = bg_m.group(1)

                # 过滤占位图或空图片
                if 'loading' in pic or 'blank' in pic or 'default' in pic:
                    pic = ''
                    
                pic = self._abs_href(pic) if pic else ''

                # 提取时长
                duration = item('.duration').text().strip() or '未知'

                seen_ids.add(vk_id)
                vlist.append({
                    'vod_id': href,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': duration
                })
            except Exception:
                continue
                
        return vlist

    def _parse_pagecount(self, data):
        try:
            nums = [int(m.group(1)) for a in data('a').items() 
                    if (m := re.search(r'[?&]page=(\d+)', a.attr('href') or ''))]
            if nums:
                return max(nums)
            page_nums = [int(a.text().strip()) 
                         for a in data('.pagination li a, .pagingnav a').items() 
                         if a.text().strip().isdigit()]
            return max(page_nums) if page_nums else 1
        except:
            return 1

    def homeContent(self, filter):
        result = {'class': [{'type_name': k, 'type_id': v} for k, v in self.class_map.items()]}
        try:
            html = self._fetch(f"{self.host}index.php").text
            result['list'] = self._parse_video_items(pq(html))
        except:
            result['list'] = []
        return result

    def homeVideoContent(self):
        return []

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        try:
            if tid == 'top_m':
                url = f"{self.host}v.php?category=top&m=-1&viewtype=basic&page={pg}"
            else:
                url = f"{self.host}v.php?category={tid}&viewtype=basic&page={pg}"
                
            html = self._fetch(url).text
            data = pq(html)
            return {
                'list': self._parse_video_items(data),
                'page': pg,
                'pagecount': self._parse_pagecount(data),
                'limit': 24,
                'total': 999999
            }
        except:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

    def _extract_video_url_from_html(self, html):
        """正确匹配并解码 strencode2 中的百分号编码 URL"""
        if not html:
            return None

        # 1. 精准提取 strencode2("...") 里面的字符串参数并解码
        encode_matches = re.findall(r'strencode2\((?:["\'])(.*?)(?:["\'])\)', html)
        for enc_str in encode_matches:
            decoded_tag = urllib.parse.unquote(enc_str)
            if src_m := re.search(r"src=['\"]([^'\"]+)['\"]", decoded_tag, re.I):
                real_url = src_m.group(1).replace('&amp;', '&').strip()
                if self.isVideoFormat(real_url):
                    return self._abs_href(real_url)

        # 黑名单列表：过滤广告视频及相关域名
        ad_keywords = ['ad-i18n-dsp', 'kwai.net', 'googleads', 'popads', 'doubleclick', 'analytics', 'preview', 'cover']

        # 2. 备用逻辑：直接正则寻找完整的视频播放 CDN 链接
        all_urls = re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)[^\s"\'<>]*', html, re.I)
        for url in all_urls:
            url_clean = url.replace('&amp;', '&').strip()
            if any(ad in url_clean.lower() for ad in ad_keywords):
                continue
            if any(kw in url_clean.lower() for kw in ['st=', 'key=', 'secure=', 'token=', 'cdn', 'get_file']):
                return url_clean

        # 3. 兜底提取第一个非广告的链接
        for url in all_urls:
            url_clean = url.replace('&amp;', '&').strip()
            if not any(ad in url_clean.lower() for ad in ad_keywords):
                return url_clean

        return None

    def _extract_vid(self, text):
        patterns = [
            r'viewkey=([a-zA-Z0-9]+)',
            r'/viewvideo\.php\?.*viewkey=([a-zA-Z0-9]+)',
            r'VID["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]+)',
            r'/ev\.php\?VID=([a-zA-Z0-9]+)'
        ]
        for pattern in patterns:
            if m := re.search(pattern, text):
                return m.group(1)
        return None

    def _get_ev_url(self, html, detail_url):
        if m := re.search(r'<textarea[^>]*>\s*(https?://[^<]+/ev\.php\?VID=[^<\s]+)', html, re.I):
            return m.group(1).strip()
        if matches := re.findall(r'(https?://[^"\'\s<>]+/ev\.php\?VID=[a-zA-Z0-9]+)', html, re.I):
            return matches[0]
        if vid := self._extract_vid(html) or self._extract_vid(detail_url):
            return f"{self.host}ev.php?VID={vid}"
        return None

    def detailContent(self, ids):
        if not ids or not ids[0]:
            return {'list': []}
        vod_id = ids[0].strip()
        detail_url = vod_id if vod_id.startswith('http') else f"{self.host.rstrip('/')}/{vod_id.lstrip('/')}"
        
        try:
            resp = self._fetch(detail_url)
            html = resp.text
        except:
            return {'list': []}

        video_url = self._extract_video_url_from_html(html)

        if not video_url:
            ev_url = self._get_ev_url(html, detail_url)
            if ev_url:
                try:
                    ev_resp = self._fetch(ev_url, headers={**self.headers, 'Referer': self.host}, timeout=10)
                    video_url = self._extract_video_url_from_html(ev_resp.text)
                except:
                    pass

        if not video_url:
            video_url = detail_url

        data = pq(html)
        title = data('title').text().strip().split('- 91porn')[0].strip() or '未知标题'
        pic = (data('meta[property="og:image"]').attr('content') or
               data('video#player_one').attr('poster') or
               data('.video-pic img, img.img-responsive').attr('src') or '')
        pic = self._abs_href(pic) if pic else ''
        
        director = '91'
        views = '未知'
        duration = '未知'
        
        if m_dur := re.search(r'\d{2}:\d{2}:\d{2}|\d{2}:\d{2}', html):
            duration = m_dur.group(0)
            
        main_box = data('div[class*="col-md-8"], .col-xs-12')
        for span in main_box.find('span.info').items():
            txt = span.text()
            if '热度' in txt or '观看' in txt:
                if m := re.search(r'[\d]+', span.parent().text().strip()):
                    views = m.group(0)

        remarks = f"{duration} | 观看:{views}" if views != '未知' else duration
        
        return {'list': [{
            'vod_id': vod_id,
            'vod_name': title,
            'vod_pic': pic,
            'vod_play_from': '91Porn',
            'vod_play_url': f'高清${video_url}',
            'vod_director': director,
            'vod_remarks': remarks,
            'vod_content': title
        }]}

    def searchContent(self, key, quick, pg=1):
        pg = int(pg or 1)
        if not key or not key.strip():
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
        try:
            encoded_key = urllib.parse.quote(key.strip())
            url = f"{self.host}search_result.php?search_id={encoded_key}&search_type=search_videos&min_duration=&page={pg}"
            
            html = self._fetch(url).text
            data = pq(html)
            vlist = self._parse_video_items(data)
            
            if not vlist:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}
                
            return {
                'list': vlist,
                'page': pg,
                'pagecount': self._parse_pagecount(data) or (pg + 1),
                'limit': len(vlist),
                'total': 999999
            }
        except:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 0, 'total': 0}

    def playerContent(self, flag, id, vipFlags):
        headers = {
            'User-Agent': self.headers.get('User-Agent'),
            'Referer': f"{self.host.rstrip('/')}/"
        }
        return {
            'parse': 0 if self.isVideoFormat(id) else 1,
            'url': id,
            'header': headers
        }

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def _fetch(self, url, params=None, headers=None, timeout=15):
        """核心改进：使用 self.session 来发起请求，自动保存和携带服务端返回的所有 Cookie"""
        req_headers = (headers or self.headers).copy()

        for host in self.hosts:
            target_url = url
            for old_host in self.hosts:
                if old_host in target_url:
                    target_url = target_url.replace(old_host, host)
                    break
            else:
                if not target_url.startswith('http'):
                    target_url = f"{host.rstrip('/')}/{target_url.lstrip('/')}"

            for attempt in range(2):
                try:
                    # 使用 self.session 代替单次 requests，保证动态 Cookie 继承
                    resp = self.session.get(
                        target_url,
                        headers=req_headers,
                        timeout=timeout,
                        allow_redirects=True,
                        params=params or {},
                        verify=False
                    )
                    if resp.status_code == 200 and len(resp.text.strip()) > 0:
                        self.host = host
                        self.headers['Referer'] = self.host
                        resp.encoding = resp.apparent_encoding or 'utf-8'
                        return resp
                except Exception:
                    if attempt < 1:
                        time.sleep(0.5)

        return type('obj', (object,), {
            'text': '', 'status_code': 404, 'headers': {},
            'content': b'', 'url': url, 'json': lambda: {}
        })()

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
