# -*- coding: utf-8 -*-
import sys
import re
import requests
from urllib.parse import quote, unquote, urljoin
from bs4 import BeautifulSoup

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "有声骚麦"

    candidate_hosts = [
        "https://yssm2.xyz",
        "https://www.yssm2.xyz",
        "https://www.yssm5.xyz",
        "https://yssm5.xyz",
        "https://yssm1.xyz",
    ]

    def init(self, extend=""):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.host = self.get_working_host()
        self.session.headers["Referer"] = self.host + "/"

    def get_working_host(self):
        for h in self.candidate_hosts:
            try:
                r = self.session.get(h + "/", timeout=6)
                r.encoding = "utf-8"
                if r.status_code == 200 and "/play.php?id=" in r.text:
                    return h
            except Exception:
                continue
        return self.candidate_hosts[0]

    def _switch_host(self):
        old = self.host
        rest = [h for h in self.candidate_hosts if h != old]
        for h in rest:
            try:
                r = self.session.get(h + "/", timeout=6)
                r.encoding = "utf-8"
                if r.status_code == 200 and "/play.php?id=" in r.text:
                    self.host = h
                    self.session.headers["Referer"] = h + "/"
                    return True
            except Exception:
                continue
        return False

    def isVideoFormat(self, url):
        return any(x in url.lower() for x in ['.mp3', '.m4a', '.aac', '.m3u8', '.mp4'])

    def manualVideoCheck(self):
        return False

    def _rewrite_host(self, url):
        for h in self.candidate_hosts:
            if url.startswith(h):
                return self.host + url[len(h):]
        return url

    def _fetch(self, url):
        url = self._rewrite_host(url)
        try:
            r = self.session.get(url, timeout=8)
            r.encoding = "utf-8"
            if r.status_code == 200 and len(r.text) > 2000:
                return r.text
        except Exception as e:
            print(f"[yssm] 请求失败: {url} -> {e}")
        if self._switch_host():
            url = self._rewrite_host(url)
            try:
                r = self.session.get(url, timeout=8)
                r.encoding = "utf-8"
                if r.status_code == 200:
                    return r.text
            except Exception as e:
                print(f"[yssm] 切换域名后仍失败: {url} -> {e}")
        return ""

    def _abs_url(self, url):
        if not url:
            return ""
        if url.startswith(("http://", "https://")):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url

    def _clean(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip())

    # ---------- 解析分类/首页/热播榜卡片（保持不变） ----------
    def _parse_book_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        books = []

        cards = soup.select('a.book-card')
        if not cards:
            cards = soup.select('.book-card')

        for card in cards:
            try:
                href = card.get('href', '')
                if not href:
                    play_a = card.select_one('a')
                    if play_a:
                        href = play_a.get('href', '')
                vid_match = re.search(r'/play\.php\?id=(\d+)', href)
                if not vid_match:
                    continue
                vod_id = vid_match.group(1)

                title_tag = card.select_one('.book-title')
                title = self._clean(title_tag.text) if title_tag else ""

                meta_tag = card.select_one('.book-meta')
                author = ""
                if meta_tag:
                    text = meta_tag.get_text(strip=True)
                    if '：' in text:
                        author = text.split('：', 1)[1].strip()
                    elif ':' in text:
                        author = text.split(':', 1)[1].strip()
                    else:
                        author = text

                read_tag = card.select_one('.read-link')
                play_count = self._clean(read_tag.text) if read_tag else ""
                remark = f"播放:{play_count}" if play_count else ""

                books.append({
                    "vod_id": vod_id,
                    "vod_name": f"{title} - {author}" if author else title,
                    "vod_pic": "",
                    "vod_remarks": remark,
                })
            except Exception:
                continue
        return books

    # ---------- 解析最新更新列表（保持不变） ----------
    def _parse_update_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.update-item')
        books = []
        for item in items:
            try:
                play_a = item.select_one('.update-play a')
                if not play_a:
                    continue
                href = play_a.get('href', '')
                vid_match = re.search(r'/play\.php\?id=(\d+)', href)
                if not vid_match:
                    continue
                vod_id = vid_match.group(1)

                title_a = item.select_one('.update-title a')
                title = self._clean(title_a.text) if title_a else ""

                author_span = item.select_one('.update-meta a')
                author = self._clean(author_span.text) if author_span else ""

                time_span = item.select_one('.update-meta span:last-child')
                date = self._clean(time_span.text) if time_span else ""

                read_link = item.select_one('.read-link')
                play_count = self._clean(read_link.text) if read_link else ""

                remark = f"{date} 播放:{play_count}" if play_count else date

                books.append({
                    "vod_id": vod_id,
                    "vod_name": f"{title} - {author}" if author else title,
                    "vod_pic": "",
                    "vod_remarks": remark,
                })
            except Exception:
                continue
        return books

    # ---------- 修复：解析主播列表（解码中文名） ----------
    def _parse_author_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('a.host-item')
        if not items:
            items = soup.select('.host-item a')
            if not items:
                items = soup.select('.host-item')
        authors = []
        for item in items:
            try:
                href = item.get('href', '')
                if not href and item.name == 'a':
                    href = item.get('href', '')
                elif not href:
                    a_tag = item.select_one('a')
                    if a_tag:
                        href = a_tag.get('href', '')
                name_match = re.search(r'name=([^&]+)', href)
                if name_match:
                    # 对提取到的编码字符串进行 URL 解码
                    author_name = unquote(name_match.group(1))
                else:
                    name_tag = item.select_one('.host-name')
                    author_name = self._clean(name_tag.text) if name_tag else "未知"

                count_tag = item.select_one('.host-books')
                count = self._clean(count_tag.text) if count_tag else "0部作品"

                authors.append({
                    "vod_id": author_name,
                    "vod_name": author_name,
                    "vod_pic": "",
                    "vod_remarks": count,
                })
            except Exception:
                continue
        return authors

    # ---------- 修复：获取主播所有作品（防止死循环） ----------
    def _fetch_author_works(self, author_name):
        works = []
        page = 1
        max_pages = 100  # 安全限制，防止死循环
        while page <= max_pages:
            url = f"{self.host}/author_detail.php?name={quote(author_name)}&page={page}"
            html = self._fetch(url)
            if not html:
                break
            soup = BeautifulSoup(html, 'html.parser')
            cards = soup.select('a.book-card')
            if not cards:
                cards = soup.select('.book-card')
            if not cards:
                break
            page_works = []
            for card in cards:
                href = card.get('href', '')
                if not href:
                    play_a = card.select_one('a')
                    if play_a:
                        href = play_a.get('href', '')
                vid_match = re.search(r'/play\.php\?id=(\d+)', href)
                if not vid_match:
                    continue
                vid = vid_match.group(1)
                title_tag = card.select_one('.book-title')
                title = self._clean(title_tag.text) if title_tag else "未知"
                page_works.append({"vod_id": vid, "vod_name": title})
            if not page_works:
                break
            works.extend(page_works)

            # 检测下一页：查找 "»" 按钮（或 <a> 标签）
            next_btn = soup.find('button', string=re.compile('»'))
            if not next_btn or next_btn.get('disabled'):
                next_link = soup.find('a', string=re.compile('»'))
                if not next_link or 'disabled' in next_link.get('class', []):
                    break
            page += 1
        return works

    # ---------- 提取分页总页数（保持不变） ----------
    def _get_pagecount(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        page_links = soup.select('.page-box a, .pagination a, .pagination-button')
        max_page = 1
        for link in page_links:
            href = link.get('href', '')
            m = re.search(r'[?&]page=(\d+)', href)
            if m:
                num = int(m.group(1))
                if num > max_page:
                    max_page = num
        text = soup.get_text()
        m = re.search(r'共\s*(\d+)\s*页', text)
        if m:
            return int(m.group(1))
        m = re.search(r'(\d+)\s*/\s*(\d+)\s*页', text)
        if m:
            return int(m.group(2))
        return max_page if max_page > 1 else 1

    # ---------- 分类入口（保持不变） ----------
    def homeContent(self, filter):
        categories = [
            {"type_id": "经典禁曲", "type_name": "经典禁曲"},
            {"type_id": "单部有声", "type_name": "单部有声"},
            {"type_id": "性爱偷录", "type_name": "性爱偷录"},
            {"type_id": "音乐改编", "type_name": "音乐改编"},
            {"type_id": "有声连载", "type_name": "有声连载"},
            {"type_id": "淫词骚麦", "type_name": "淫词骚麦"},
            {"type_id": "author_list", "type_name": "👤 主播列表"},
            {"type_id": "toplist", "type_name": "🔥 热播榜"},
            {"type_id": "latest", "type_name": "🆕 最新更新"},
        ]
        return {"class": categories}

    def homeVideoContent(self):
        return self.categoryContent("toplist", "1", None, {})

    # ---------- 分类列表（保持不变） ----------
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if pg else 1

        if tid == "author_list":
            url = f"{self.host}/author.php?page={pg}"
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}
            items = self._parse_author_list(html)
            pagecount = self._get_pagecount(html)
            return {
                "list": items,
                "page": pg,
                "pagecount": max(pagecount, pg),
                "limit": len(items) or 20,
                "total": max(pagecount, pg) * (len(items) or 20),
            }

        if tid == "toplist":
            url = f"{self.host}/toplist.php?page={pg}"
        elif tid == "latest":
            url = f"{self.host}/latest.php?page={pg}"
        else:
            url = f"{self.host}/cate_detail.php?cate={quote(tid)}"
            if pg > 1:
                url += f"&page={pg}"

        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

        books = self._parse_book_list(html)
        if not books:
            books = self._parse_update_list(html)

        pagecount = self._get_pagecount(html)
        return {
            "list": books,
            "page": pg,
            "pagecount": max(pagecount, pg),
            "limit": len(books) or 20,
            "total": max(pagecount, pg) * (len(books) or 20),
        }

    # ---------- 详情页（支持主播名跳转） ----------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0])

        # 如果是主播名（非数字），获取所有作品
        if vid and not vid.isdigit():
            works = self._fetch_author_works(vid)
            if works:
                play_list = [f"{w['vod_name']}${w['vod_id']}" for w in works]
                play_url = "#".join(play_list)
                return {
                    "list": [{
                        "vod_id": vid,
                        "vod_name": f"主播 {vid} 的作品",
                        "vod_pic": "",
                        "vod_content": "",
                        "vod_play_from": "有声骚麦",
                        "vod_play_url": play_url,
                    }]
                }
            else:
                return {"list": []}

        # 否则按普通音频处理
        url = f"{self.host}/play.php?id={vid}"
        html = self._fetch(url)
        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, 'html.parser')

        title_tag = soup.select_one('h1') or soup.select_one('.book-name') or soup.select_one('title')
        title = self._clean(title_tag.text) if title_tag else f"音频{vid}"

        audio_url = ""
        audio_item = soup.select_one('.audio-item')
        if audio_item:
            src = audio_item.get('data-src', '')
            if src:
                audio_url = self._abs_url(src)
        if not audio_url:
            audio = soup.find('audio')
            if audio:
                src = audio.get('src')
                if src:
                    audio_url = self._abs_url(src)
                else:
                    source = audio.find('source')
                    if source:
                        src = source.get('src')
                        if src:
                            audio_url = self._abs_url(src)
        if not audio_url:
            m = re.search(r'(https?://[^\s"\']+\.(?:mp3|m4a|aac)[^\s"\']*)', html)
            if m:
                audio_url = m.group(1)

        author = ""
        author_tag = soup.select_one('.book-author-link[href*="author_detail"]')
        if author_tag:
            author = self._clean(author_tag.text)

        vod = {
            "vod_id": vid,
            "vod_name": f"{title} - {author}" if author else title,
            "vod_pic": "",
            "vod_content": "",
            "vod_play_from": "有声骚麦",
            "vod_play_url": f"第1集${audio_url}" if audio_url else "",
        }
        return {"list": [vod]}

    # ---------- 播放器（保持不变） ----------
    def playerContent(self, flag, id, vipFlags=None):
        if '$' in id:
            target = id.split('$', 1)[1]
        else:
            target = id

        if target.isdigit():
            play_page_url = f"{self.host}/play.php?id={target}"
            html = self._fetch(play_page_url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                audio_url = ""
                audio_item = soup.select_one('.audio-item')
                if audio_item:
                    src = audio_item.get('data-src', '')
                    if src:
                        audio_url = self._abs_url(src)
                if not audio_url:
                    audio = soup.find('audio')
                    if audio:
                        src = audio.get('src')
                        if src:
                            audio_url = self._abs_url(src)
                        else:
                            source = audio.find('source')
                            if source:
                                src = source.get('src')
                                if src:
                                    audio_url = self._abs_url(src)
                if not audio_url:
                    m = re.search(r'(https?://[^\s"\']+\.(?:mp3|m4a|aac)[^\s"\']*)', html)
                    if m:
                        audio_url = m.group(1)
                if audio_url:
                    return {
                        "parse": 0,
                        "url": audio_url,
                        "header": {"Referer": self.host + "/", "User-Agent": self.session.headers["User-Agent"]}
                    }
            return {"parse": 0, "url": "", "msg": "未找到音频地址"}

        if not target.startswith('http'):
            target = self._abs_url(target)

        if self.isVideoFormat(target):
            return {
                "parse": 0,
                "url": target,
                "header": {"Referer": self.host + "/", "User-Agent": self.session.headers["User-Agent"]}
            }

        return {"parse": 1, "url": target, "header": {}}

    # ---------- 搜索（保持不变） ----------
    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg) if pg else 1
        enc_key = quote(key)
        url = f"{self.host}/search.php?wd={enc_key}"
        if pg > 1:
            url += f"&page={pg}"
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

        books = self._parse_book_list(html)
        if not books:
            books = self._parse_update_list(html)

        pagecount = self._get_pagecount(html)
        return {
            "list": books,
            "page": pg,
            "pagecount": max(pagecount, pg),
            "limit": len(books) or 20,
            "total": max(pagecount, pg) * (len(books) or 20),
        }

    def localProxy(self, param):
        pass

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
