# coding: utf-8
# 蜜桃源｜XOR图片解密 localProxy + 播放修复
import re
import json
import base64
import urllib.parse
from base.spider import Spider as BaseSpider

IMG_KEY = b'OzoTeoS7D>6Y^@z39JmD'
PROXY = 'http://127.0.0.1:9978/proxy?do=pic&url='

class Spider(BaseSpider):
    def __init__(self):
        self.host = "http://cl2.xbl2.pro"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": f"{self.host}/",
        }
        self.classes = [
            {"type_id": "5",  "type_name": "国产精选"},
            {"type_id": "3",  "type_name": "黑料吃瓜"},
            {"type_id": "4",  "type_name": "厂牌原创"},
            {"type_id": "6",  "type_name": "明星换脸"},
            {"type_id": "7",  "type_name": "AV解说"},
            {"type_id": "8",  "type_name": "禁漫精选"},
            {"type_id": "28", "type_name": "国产大片"},
            {"type_id": "87", "type_name": "日韩大片"},
            {"type_id": "31", "type_name": "欧美大片"},
            {"type_id": "32", "type_name": "网红直播"},
            {"type_id": "33", "type_name": "探花约炮"},
            {"type_id": "88", "type_name": "SM调教"},
            {"type_id": "34", "type_name": "三级伦理"},
            {"type_id": "35", "type_name": "萝莉开苞"},
            {"type_id": "10", "type_name": "父女"},
            {"type_id": "11", "type_name": "母子"},
            {"type_id": "12", "type_name": "兄妹"},
            {"type_id": "13", "type_name": "学生"},
            {"type_id": "14", "type_name": "嫂子"},
            {"type_id": "15", "type_name": "姐夫"},
            {"type_id": "16", "type_name": "师生"},
            {"type_id": "17", "type_name": "全家"},
            {"type_id": "79", "type_name": "真实缅北"},
            {"type_id": "80", "type_name": "恶心恐怖"},
            {"type_id": "81", "type_name": "黄金圣水"},
            {"type_id": "82", "type_name": "校园霸凌"},
            {"type_id": "83", "type_name": "战场实录"},
            {"type_id": "84", "type_name": "人兽乱交"},
            {"type_id": "85", "type_name": "灵异视频"},
            {"type_id": "86", "type_name": "N号房"},
        ]
        self.filters = {}

    def getName(self):
        return "蜜桃源"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend
        self.proxy_ok = True
        self._probe()

    def _probe(self):
        try:
            r = self.fetch('http://127.0.0.1:9978/proxy?do=ping', timeout=1200)
            self.proxy_ok = bool(r)
        except Exception:
            self.proxy_ok = False
        return self.proxy_ok

    def _fetch_decoded(self, url):
        for _ in range(2):
            try:
                resp = self.fetch(url, headers=self.headers, timeout=10000)
                if not resp or not hasattr(resp, "text"):
                    continue
                html = resp.text
                matches = re.findall(r"var str = '([^']+)'", html)
                if matches and len(matches[0]) > 1000:
                    try:
                        first = base64.b64decode(matches[0]).decode('utf-8')
                        second = base64.b64decode(first).decode('utf-8')
                        return second
                    except Exception:
                        pass
                return html
            except Exception:
                continue
        return None

    def _pic(self, url):
        if not url:
            return ""
        if self.proxy_ok:
            return PROXY + urllib.parse.quote(url, safe='')
        return self._data_uri(url)

    def _data_uri(self, url):
        try:
            r = self.fetch(url, headers=self.headers, timeout=10000)
            if not r:
                return url
            raw = r.text.strip()
            raw += '=' * (-len(raw) % 4)
            dec = base64.b64decode(raw)
            n = len(IMG_KEY)
            ks = IMG_KEY * (len(dec) // n + 1)
            img = bytes(a ^ b for a, b in zip(dec, ks))
            mime = 'image/jpeg'
            if img[:4] == b'\x89PNG':
                mime = 'image/png'
            elif img[:3] == b'GIF':
                mime = 'image/gif'
            elif img[:4] == b'RIFF':
                mime = 'image/webp'
            return 'data:%s;base64,%s' % (mime, base64.b64encode(img).decode())
        except Exception:
            return url

    def _pics(self, urls):
        if not urls:
            return []
        if self.proxy_ok:
            return [PROXY + urllib.parse.quote(u, safe='') for u in urls]
        try:
            import threading
        except Exception:
            return [self._data_uri(u) for u in urls]
        out = ['' for _ in urls]

        def work(i, u):
            try:
                out[i] = self._data_uri(u)
            except Exception:
                out[i] = u
        ts = [threading.Thread(target=work, args=(i, u)) for i, u in enumerate(urls)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        return out

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        if not url.startswith("http"):
            return f"{self.host}/{url.lstrip('/')}"
        return url

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        return self.categoryContent("5", "1", False, {})

    def _items(self, html):
        pattern = r'<li class="content-item"[^>]*>.*?<a[^>]*href="(/index\.php/vod/detail/id/(\d+)\.html)"[^>]*title="([^"]*)"[^>]*>(.*?)</a>.*?</li>'
        found = re.findall(pattern, html, re.DOTALL)
        pic_urls = []
        rows = []
        for href, vid, title, inner in found:
            title = title.strip()
            imgs = re.findall(r'<img[^>]*src="([^"]*)"', inner)
            real_pic = ""
            for img in imgs:
                if "faiusr.com" not in img and ".gif" not in img:
                    real_pic = img
                    break
            if not real_pic and imgs:
                real_pic = imgs[-1]
            pic_urls.append(self._fix_url(real_pic))
            rows.append((vid, title))
        pics = self._pics(pic_urls)
        videos = []
        for i, (vid, title) in enumerate(rows):
            videos.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pics[i] if i < len(pics) else "",
                "vod_remarks": ""
            })
        return videos

    def categoryContent(self, tid, pg, filter, extend):
        self._probe()
        try:
            page = int(pg)
            page = max(page, 1)
        except Exception:
            page = 1
        url = f"{self.host}/index.php/vod/type/id/{tid}.html" if page == 1 else f"{self.host}/index.php/vod/type/id/{tid}/page/{page}.html"
        html = self._fetch_decoded(url)
        videos = []
        pagecount = page
        if html:
            videos = self._items(html)
            page_links = re.findall(r'href="/index\.php/vod/type/id/\d+/page/(\d+)\.html"', html)
            if page_links:
                pagecount = max(page, max(int(p) for p in page_links))
        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        if "|$|" in vod_id:
            vod_id = vod_id.split("|$|")[0]
        html = self._fetch_decoded(f"{self.host}/index.php/vod/detail/id/{vod_id}.html")
        if not html:
            return {"list": []}
        title = ""
        title_match = re.search(r'<title>([^<]*)</title>', html)
        if title_match:
            title = title_match.group(1).split('-')[0].strip()
            title = re.sub(r'详情介绍$', '', title).strip()
        pic = ""
        img_match = re.search(r'<img[^>]*src="(https?://aisearch\.cdn\.bcebos\.com/[^"]*)"', html)
        if img_match:
            pic = img_match.group(1)
        play_links = re.findall(
            r'href="(/index\.php/vod/play/id/\d+/sid/(\d+)/nid/(\d+)\.html)"[^>]*>([^<]*)</a>',
            html
        )
        sources = {}
        for href, sid, nid, name in play_links:
            sid = int(sid)
            if sid not in sources:
                sources[sid] = []
            sources[sid].append({
                "name": name.strip() or f"第{nid}集",
                "url": f"{self.host}{href}"
            })
        source_names = []
        source_urls = []
        sids = sorted(sources.keys())
        if sids:
            def _probe_line(play_page):
                pt = self._fetch_decoded(play_page)
                if not pt:
                    return False
                pa = re.search(r'var player_aaaa\s*=\s*({.*?})\s*;?\s*</script>', pt, re.DOTALL)
                if not pa:
                    return False
                try:
                    j = json.loads(pa.group(1))
                    u = j.get('url', '').replace('\\/', '/')
                except Exception:
                    return False
                if not u.startswith('http'):
                    return False
                try:
                    hd = dict(self.headers)
                    hd['Range'] = 'bytes=0-1'
                    r = self.fetch(u, headers=hd, timeout=4000)
                    return r is not None and getattr(r, 'status_code', 0) in (200, 206)
                except Exception:
                    return False
            if not _probe_line(sources[sids[0]][0]['url']) and len(sids) > 1:
                sids = sids[1:] + [sids[0]]
        for sid in sids:
            source_names.append(f"线路{sid}")
            episodes = sources[sid]
            ep_str = "#".join([f"{ep['name']}${ep['url']}" for ep in episodes])
            source_urls.append(ep_str)
        vod_info = {
            "vod_id": vod_id,
            "vod_name": title,
            "vod_pic": self._pic(pic) if pic else "",
            "vod_remarks": "",
            "vod_content": title,
            "vod_play_from": "$$$".join(source_names) if source_names else "蜜桃源",
            "vod_play_url": "$$$".join(source_urls) if source_urls else ""
        }
        return {"list": [vod_info]}

    def searchContent(self, key, quick, pg="1"):
        self._probe()
        try:
            page = int(pg)
            page = max(page, 1)
        except Exception:
            page = 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.host}/index.php/vod/search.html?wd={encoded_key}" if page == 1 else f"{self.host}/index.php/vod/search/page/{page}.html?wd={encoded_key}"
        html = self._fetch_decoded(url)
        videos = []
        if html:
            videos = self._items(html)
        return {"list": videos, "page": page}

    def playerContent(self, flag, id, vipFlags):
        play_url = id
        if not play_url.startswith("http"):
            play_url = self._fix_url(play_url)
        if play_url.endswith((".m3u8", ".mp4", ".ts", ".flv")):
            return {"parse": 0, "url": play_url, "header": self.headers}
        html = self._fetch_decoded(play_url)
        if not html:
            return {"parse": 1, "url": play_url, "header": self.headers}
        player_match = re.search(r'var player_aaaa\s*=\s*({.*?})\s*;?\s*</script>', html, re.DOTALL)
        if player_match:
            try:
                player_data = json.loads(player_match.group(1))
                real_url = player_data.get("url", "").replace(chr(92) + "/", "/")
                if real_url and real_url.endswith((".m3u8", ".mp4", ".ts", ".flv")):
                    return {"parse": 0, "url": real_url, "header": self.headers}
            except Exception:
                pass
        media = re.search(r'(https?://[^\s"\'\;]+\.(?:m3u8|mp4|ts|flv))', html)
        if media:
            return {"parse": 0, "url": media.group(1), "header": self.headers}
        iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if iframe:
            return {"parse": 1, "url": self._fix_url(iframe.group(1)), "header": self.headers}
        return {"parse": 1, "url": play_url, "header": self.headers}

    def localProxy(self, param):
        try:
            p = param or ''
            if p.startswith('http'):
                p = p.split('?', 1)[-1]
            qs = urllib.parse.parse_qs(p)
            do = qs.get('do', ['pic'])[0]
            u = qs.get('url', [''])[0]
            if do != 'pic' or not u:
                return [404, 'text/plain', '']
            for _ in range(2):
                if u.startswith(('http://', 'https://')) or ('%3A' not in u.upper() and '%2F' not in u.upper()):
                    break
                u = urllib.parse.unquote(u)
            resp = self.fetch(u, headers=self.headers, timeout=15000)
            if not resp:
                return [404, 'text/plain', '']
            raw = resp.text.strip()
            raw += '=' * (-len(raw) % 4)
            dec = base64.b64decode(raw)
            n = len(IMG_KEY)
            img = bytes(b ^ IMG_KEY[i % n] for i, b in enumerate(dec))
            mime = 'image/jpeg'
            if img[:4] == b'\x89PNG':
                mime = 'image/png'
            elif img[:3] == b'GIF':
                mime = 'image/gif'
            elif img[:4] == b'RIFF':
                mime = 'image/webp'
            return [200, mime, img]
        except Exception:
            return [404, 'text/plain', '']

    def isVideoFormat(self, url):
        return url.endswith((".m3u8", ".mp4", ".ts", ".flv"))

    def destroy(self):
        pass
