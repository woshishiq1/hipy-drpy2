# -*- coding: utf-8 -*-
# 麻豆影院 - 强制适配版（含广告拦截）
# 详情页: /index.php/vod/role/id/{id}.html  (含多线路入口)
# 播放页: /index.php/vod/detail/id/{id}.html (含真实 m3u8)

import sys
import re
import json
import base64
import requests
from urllib.parse import urljoin, quote, unquote
from bs4 import BeautifulSoup
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "MADOUYY"

    def init(self, extend=""):
        self.hosts = [
            "https://mdyy6c5c5ce5.1010941.xyz",
            "https://mdyy.cc",
            "https://www.mdyy.cc",
        ]
        self.host = self.hosts[0]
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

    # ---------- 网络请求 ----------

    def _fetch(self, url, headers=None):
        text = ""
        for host in self.hosts:
            try:
                full = host + url if url.startswith("/") else url
                h = headers or self.session.headers.copy()
                h["Referer"] = host + "/"
                r = self.session.get(full, headers=h, timeout=15)
                r.encoding = "utf-8"
                if r.status_code == 200:
                    self.host = host
                    text = r.text
                    break
            except Exception as e:
                print(f"[请求失败] {host}: {e}")
        return text

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        if url.startswith("http"):
            return url
        return self.host + "/" + url

    # ---------- 首页 ----------

    def homeContent(self, filter=False):
        classes = [
            {"type_id": "1", "type_name": "麻豆传媒"},
            {"type_id": "2", "type_name": "高清国产"},
            {"type_id": "3", "type_name": "日韩无码"},
            {"type_id": "4", "type_name": "亚洲有码"},
            {"type_id": "5", "type_name": "中文字幕"},
            {"type_id": "6", "type_name": "欧美情色"},
            {"type_id": "7", "type_name": "岛国女优"},
            {"type_id": "8", "type_name": "明星换脸"},
            {"type_id": "9", "type_name": "美女主播"},
            {"type_id": "10", "type_name": "萝莉少女"},
            {"type_id": "12", "type_name": "变态调教"},
            {"type_id": "15", "type_name": "激情动漫"},
            {"type_id": "16", "type_name": "熟女人妻"},
            {"type_id": "20", "type_name": "强奸乱伦"},
            {"type_id": "11", "type_name": "网曝黑料"},
            {"type_id": "13", "type_name": "网红头条"},
            {"type_id": "14", "type_name": "极品媚黑"},
            {"type_id": "21", "type_name": "淫妻作乐"},
            {"type_id": "22", "type_name": "足浴撩妹"},
            {"type_id": "23", "type_name": "反差母狗"},
            {"type_id": "24", "type_name": "多人群交"},
        ]
        return {"class": classes}

    def homeVideoContent(self):
        return {
            "list": [
                {"vod_id": "folder$" + c["type_id"], "vod_name": c["type_name"], "vod_pic": "", "vod_remarks": "分类", "vod_tag": "folder"}
                for c in self.homeContent()["class"]
            ]
        }

    # ---------- 分类 ----------

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        tid = str(tid or "0")
        if tid.startswith("folder$"):
            tid = tid.split("$", 1)[1]

        if tid == "0":
            url = "/"
        else:
            url = f"/index.php/vod/type/id/{tid}.html" if pg == 1 else f"/index.php/vod/type/id/{tid}/page/{pg}.html"

        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": pg, "limit": 0, "total": 0}

        videos = self._parse_list(html)
        pagecount = pg + 1 if len(videos) >= 8 else pg
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * len(videos),
        }

    def _parse_list(self, html):
        """解析列表：只取 md0（md1/md2 是广告跳转）"""
        videos = []
        soup = BeautifulSoup(html, "html.parser")
        for section in soup.find_all("section"):
            main = section.find("main")
            if not main:
                continue
            for article in main.find_all("article"):
                a = article.find("a", href=True, class_="md0")
                if not a:
                    continue
                href = a.get("href", "")
                if not href.startswith("/index.php/vod/role/id/"):
                    continue
                vid = href.split("/")[-1].replace(".html", "")
                cite = a.find("cite")
                title = cite.get_text(strip=True) if cite else ""
                img = a.find("img")
                pic = img.get("data-src") or img.get("src") or "" if img else ""
                pic = self._fix_url(pic)
                if title and vid:
                    videos.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": ""})
        return videos

    # ---------- 详情页（role 页提取多线路） ----------

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        vid = re.sub(r'\D', '', vid)
        if not vid:
            return {"list": []}

        detail_url = f"/index.php/vod/role/id/{vid}.html"
        html = self._fetch(detail_url)
        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")

        # 标题多层提取
        title = self._extract_title(soup, html)
        # 清洗前缀
        title = re.sub(r'^(麻豆|高清|国产|日韩|欧美|中文字幕|激情动漫)[-—\s]+', '', title)

        # 封面
        pic = self._extract_pic(soup)
        pic = self._fix_url(pic)

        # 提取多线路播放列表
        play_from, play_url = self._extract_playlist(soup, html, vid)

        # 兜底：如果没找到任何线路，直接构造 detail 页作为单线路
        if not play_from:
            play_from = ["默认线路"]
            play_url = [f"播放${self.host}/index.php/vod/detail/id/{vid}.html"]

        vod = {
            "vod_id": vid,
            "vod_name": title or vid,
            "vod_pic": pic,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        return {"list": [vod]}

    def _extract_title(self, soup, html):
        """6层标题兜底"""
        # 1. h1
        h1 = soup.find("h1")
        if h1:
            txt = h1.get_text(strip=True)
            if txt:
                return txt
        # 2. og:title
        og = soup.find("meta", property="og:title")
        if og:
            return og.get("content", "")
        # 3. meta name=title
        mt = soup.find("meta", attrs={"name": "title"})
        if mt:
            return mt.get("content", "")
        # 4. class 匹配
        for cls in ["title", "name", "vod_name", "video-title", "movie-name", "vod-title"]:
            tag = soup.find(class_=re.compile(cls, re.I))
            if tag:
                return tag.get_text(strip=True)
        # 5. cite
        cite = soup.find("cite")
        if cite:
            return cite.get_text(strip=True)
        # 6. 正则
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            return re.sub(r'<[^>]+>', '', m.group(1)).strip()
        return ""

    def _extract_pic(self, soup):
        og = soup.find("meta", property="og:image")
        if og:
            return og.get("content", "")
        img = soup.find("img", class_=re.compile(r"lazyload|vod_pic|pic", re.I))
        if img:
            return img.get("data-src") or img.get("src") or ""
        return ""

    def _extract_playlist(self, soup, html, vid):
        """提取 role 页的多线路播放入口"""
        play_from = []
        play_url = []

        # 该站 role 页里的播放链接指向 /detail/ 页
        # 常见容器：.module-play-list, .stui-content__playlist, .play-list, .playlist, .module-row-one
        containers = [
            soup.select_one(".module-play-list"),
            soup.select_one(".stui-content__playlist"),
            soup.select_one(".play-list"),
            soup.select_one(".playlist"),
            soup.select_one("#playlists"),
            soup.select_one(".module-row-one"),
            soup.select_one(".stui-vodlist__head"),
        ]

        for container in containers:
            if not container:
                continue

            # 找线路分组
            groups = container.find_all(["div", "ul"], recursive=False)
            if not groups:
                groups = [container]

            for g in groups:
                # 提取线路名
                line_name = "默认线路"
                title_tag = g.find_previous(["h3", "span", "div", "h2"], class_=re.compile(r"title|head|name|line|from|play_from", re.I))
                if title_tag:
                    line_name = title_tag.get_text(strip=True)
                inner = g.find(["h3", "span", "h2"], class_=re.compile(r"title|head", re.I))
                if inner:
                    line_name = inner.get_text(strip=True)
                    inner.decompose()

                links = []
                for a in g.find_all("a", href=True):
                    href = a.get("href", "")
                    text = a.get_text(strip=True) or "播放"
                    # 该站播放入口是 /detail/ 或 /play/
                    if "/detail/" in href or "/play/" in href or "/vod/detail/" in href or "/vod/play/" in href:
                        links.append(f"{text}${self._fix_url(href)}")

                if links:
                    # 去重
                    seen = set()
                    unique = []
                    for l in links:
                        u = l.split("$", 1)[1] if "$" in l else l
                        if u not in seen:
                            seen.add(u)
                            unique.append(l)
                    play_from.append(line_name)
                    play_url.append("#".join(unique))

            if play_from:
                break

        # 如果没找到容器，全局搜索 /detail/ 和 /play/ 链接
        if not play_from:
            all_links = []
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if "/detail/" in href or "/play/" in href:
                    text = a.get_text(strip=True) or "播放"
                    all_links.append(f"{text}${self._fix_url(href)}")
            if all_links:
                play_from.append("默认线路")
                play_url.append("#".join(all_links))

        # 如果 role 页直接有 video/iframe（少数情况）
        if not play_from:
            direct = self._extract_direct_video(soup, html)
            if direct:
                play_from.append("默认线路")
                play_url.append(f"播放${direct}")

        return play_from, play_url

    def _extract_direct_video(self, soup, html):
        iframe = soup.find("iframe")
        if iframe:
            src = iframe.get("src")
            if src:
                return self._fix_url(src)
        video = soup.find("video")
        if video:
            src = video.get("src")
            if src:
                return self._fix_url(src)
        m = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4|flv)[^\s"\']*)', html)
        if m:
            return m.group(1)
        return ""

    # ---------- 播放页（detail 页解析真实 m3u8） ----------

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 1, "url": "", "header": ""}

        # 已经是直链
        if self.isVideoFormat(id):
            return {
                "parse": 0,
                "url": self.源天纹(id, self.host + "/"),
                "header": json.dumps({
                    "User-Agent": self.session.headers["User-Agent"],
                    "Referer": self.host + "/",
                })
            }

        # 请求播放页（/detail/ 或 /play/）
        html = self._fetch(id)
        if not html:
            return {
                "parse": 1,
                "url": id,
                "header": json.dumps({"Referer": self.host + "/"})
            }

        real_url = self._parse_player_page(html)
        if real_url and self.isVideoFormat(real_url):
            return {
                "parse": 0,
                "url": self.源天纹(real_url, self.host + "/"),
                "header": json.dumps({
                    "User-Agent": self.session.headers["User-Agent"],
                    "Referer": self.host + "/",
                })
            }

        # 兜底 WebView
        return {
            "parse": 1,
            "url": id,
            "header": json.dumps({
                "User-Agent": self.session.headers["User-Agent"],
                "Referer": self.host + "/",
            })
        }

    def _parse_player_page(self, html):
        """从 detail/play 页提取真实 m3u8（多层强制兜底）"""
        # 1. 苹果CMS v10 player_aaaa
        m = re.search(r'var\s+player_aaaa\s*=\s*({.+?});', html, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                url = data.get("url", "")
                if url:
                    if url.startswith("http"):
                        return url
                    # base64
                    try:
                        decoded = base64.b64decode(url).decode("utf-8")
                        if decoded.startswith("http"):
                            return decoded
                    except:
                        pass
                    # urldecode
                    decoded = unquote(url)
                    if decoded.startswith("http"):
                        return decoded
            except Exception as e:
                print(f"[player_aaaa] 解析失败: {e}")

        # 2. 其他 JS 变量
        patterns = [
            r'var\s+(?:video|file|playUrl|play_url|src|url|m3u8)\s*=\s*["\']([^"\']+)["\']',
            r'"videoUrl"\s*:\s*["\']([^"\']+)["\']',
            r'"url"\s*:\s*["\']([^"\']+)["\']',
            r'"link"\s*:\s*["\']([^"\']+)["\']',
            r'player\(["\'][^"\']*["\'],\s*["\']([^"\']+)["\']',
            r'src\s*=\s*["\']([^"\']+\.(?:m3u8|mp4|flv))["\']',
        ]
        for pattern in patterns:
            m = re.search(pattern, html, re.S)
            if m:
                url = m.group(1)
                if url.startswith("http"):
                    return url
                try:
                    decoded = base64.b64decode(url).decode("utf-8")
                    if decoded.startswith("http"):
                        return decoded
                except:
                    pass

        # 3. iframe
        soup = BeautifulSoup(html, "html.parser")
        iframe = soup.find("iframe")
        if iframe:
            src = iframe.get("src")
            if src and src.startswith("http"):
                return src

        # 4. video 标签
        video = soup.find("video")
        if video:
            src = video.get("src") or ""
            if src:
                return self._fix_url(src)
            source = video.find("source")
            if source:
                src = source.get("src") or ""
                if src:
                    return self._fix_url(src)

        # 5. 正则强制兜底 m3u8/mp4/flv
        m = re.search(r'(https?://[^\s"\']+\.(?:m3u8|mp4|flv)[^\s"\']*)', html)
        if m:
            return m.group(1)

        # 6. 更宽松的正则（任意 http 链接）
        m = re.search(r'(https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}[^\s"\'<>]+)', html)
        if m:
            url = m.group(1)
            if ".m3u8" in url or ".mp4" in url or ".flv" in url:
                return url

        return ""

    # ---------- 搜索 ----------

    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg) if pg else 1
        enc = quote(key)
        url = f"/index.php/vod/search.html?wd={enc}"
        if pg > 1:
            url += f"&page={pg}"

        html = self._fetch(url)
        if not html:
            try:
                r = self.session.post(
                    self.host + "/index.php/vod/search.html",
                    data={"wd": key},
                    headers=self.session.headers,
                    timeout=15
                )
                r.encoding = "utf-8"
                html = r.text
            except Exception as e:
                print(f"[搜索POST] 失败: {e}")

        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 0, "total": 0}

        videos = self._parse_list(html)
        pagecount = pg + 1 if len(videos) >= 8 else pg
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": len(videos),
            "total": pagecount * len(videos),
        }

    def isVideoFormat(self, url):
        return url and (".m3u8" in url or ".mp4" in url or ".flv" in url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

# ==================== 无始经·虚空截流·广告禁地 ====================
    def localProxy(self, param):
        """虚空门 — 横渡混沌，截杀天外邪魔（广告）"""
        try:
            if not isinstance(param, dict):
                param = {}
            pt = param.get('type') or param.get('action') or param.get('do')
            u = param.get('url', '')
            if pt != 'm3u8' or not u:
                return [404, "text/plain", "nf"]
            rf = param.get('referer', '') or (getattr(self, 'host', '') or getattr(self, 'BASE_URL', ''))
            if isinstance(u, list):
                u = u[0]
            if isinstance(rf, list):
                rf = rf[0]
            u = __import__('urllib.parse').parse.unquote(u)
            rf = __import__('urllib.parse').parse.unquote(rf)
            raw = self.神识探(u, rf)
            if not raw:
                return [404, "text/plain", "err"]
            c = self.斩道诀(raw, u, rf)
            return [200, "application/vnd.apple.mpegurl", c.encode("utf-8") if isinstance(c, str) else c, {}]
        except Exception:
            return [404, "text/plain", "err"]

    def 源天纹(self, url, referer):
        """源天纹 — 于URL上刻下大帝阵纹，借道TVBox代理"""
        try:
            if hasattr(self, 'getProxyUrl'):
                b = self.getProxyUrl()
                if '?' not in b:
                    b += '?do=py'
                return b + '&type=m3u8&url=' + __import__('urllib.parse').parse.quote(url, safe='') + '&referer=' + __import__('urllib.parse').parse.quote(referer or getattr(self, 'host', '') or getattr(self, 'BASE_URL', ''), safe='')
        except Exception:
            pass
        return url

    def 神识探(self, url, referer):
        """神识探 — 以帝境神识刺破虚妄，取回m3u8真本"""
        try:
            import requests
            ua = getattr(self, 'session', None)
            ua = ua.headers.get('User-Agent', 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36') if ua else 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36'
            h = {
                "User-Agent": ua,
                "Referer": referer,
            }
            r = requests.get(url, headers=h, timeout=15)
            if r.status_code == 200:
                r.encoding = 'utf-8'
                return r.text
        except Exception:
            pass
        return None

    def 禁地判(self, uri, dur=0, prev=None):
        """禁地判 — 以源天神眼照见广告片段，凡邪魔外道皆无所遁形"""
        u = (uri or '').strip().lower()
        if not u:
            return False
        aw = [
            'ad', 'ads', 'advert', 'advertise', 'advertisement', 'sponsor',
            'pre', 'preroll', chr(29255)+chr(22836), chr(24191)+chr(21578), '/gg/', '_gg', 'gg_', '/adv/',
            '/ad/', '/ads/', 'banner', 'promo', 'commercial'
        ]
        if any(w in u for w in aw):
            return True
        try:
            if 0 < float(dur) <= 1.2:
                return True
        except Exception:
            pass
        return False

    def 天机线(self, uri, base):
        """天机线 — 推演URI命格，抽离域名与龙脉轨迹"""
        try:
            f = __import__('urllib.parse').parse.urljoin(base, uri)
            p = __import__('urllib.parse').parse.urlparse(f)
            ph = __import__('re').sub(r'/[^/]*$', '/', p.path or '/')
            return (p.netloc.lower(), ph.lower())
        except Exception:
            return ('', '')

    def 定龙脉(self, murl):
        """定龙脉 — 锁定主音轨之祖根，凡偏离此脉者皆为旁门"""
        try:
            p = __import__('urllib.parse').parse.urlparse(murl).path
            m = __import__('re').search(r'(\/\d{8}\/[^/]+\/\d+kb\/hls\/)', p)
            if m:
                return m.group(1).lower()
            m = __import__('re').search(r'(\/\d{8}\/[^/]+\/)', p)
            if m:
                return m.group(1).lower()
        except Exception:
            pass
        return ''

    def 轮海卷(self, text):
        """轮海卷 — 将m3u8汪洋分流为道宫、四极、化龙、仙台诸境"""
        ls = [x.strip() for x in (text or '').replace('\r', '').split('\n') if x.strip()]
        hd, sg, tl = [], [], []
        pt = []
        ms = 0
        td = 0
        st = False
        i = 0
        while i < len(ls):
            ln = ls[i]
            if ln.startswith('#EXT-X-MEDIA-SEQUENCE'):
                try:
                    ms = int(ln.split(':', 1)[1])
                except Exception:
                    pass
                if not st:
                    hd.append(ln)
                else:
                    pt.append(ln)
            elif ln.startswith('#EXT-X-TARGETDURATION'):
                try:
                    td = float(ln.split(':', 1)[1])
                except Exception:
                    pass
                if not st:
                    hd.append(ln)
                else:
                    pt.append(ln)
            elif ln.startswith('#EXTINF'):
                st = True
                dr = td or 3.0
                m = __import__('re').search(r'#EXTINF:\s*([\d.]+)', ln)
                if m:
                    try:
                        dr = float(m.group(1))
                    except Exception:
                        pass
                tg = pt + [ln]
                pt = []
                uri = ''
                j = i + 1
                while j < len(ls):
                    if ls[j].startswith('#'):
                        tg.append(ls[j])
                        j += 1
                        continue
                    uri = ls[j]
                    break
                if uri:
                    sg.append({'tags': tg, 'uri': uri, 'dur': dr})
                    i = j
                else:
                    tl.extend(tg)
            elif ln.startswith('#EXT-X-ENDLIST'):
                tl.append(ln)
            elif ln.startswith('#'):
                if st:
                    pt.append(ln)
                else:
                    hd.append(ln)
            else:
                st = True
                dr = td or 3.0
                sg.append({'tags': pt, 'uri': ln, 'dur': dr})
                pt = []
            i += 1
        return hd, sg, tl, ms, td

    def 斩道诀(self, txt, base, referer, skip=25):
        """斩道诀 — 天帝拳出，斩尽广告邪魔，重塑纯净大道"""
        t = (txt or '').replace('\r', '')
        if '#EXT-X-STREAM-INF' in t:
            o = []
            for ln in t.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                if ln.startswith('#'):
                    o.append(ln)
                else:
                    a = __import__('urllib.parse').parse.urljoin(base, ln)
                    if '.m3u8' in ln.lower():
                        o.append(self.源天纹(a, referer))
                    else:
                        o.append(a)
            return '\n'.join(o) + '\n'

        hd, sg, tl, ms, td = self.轮海卷(t)
        if not sg:
            return t

        mk = self.定龙脉(base)
        st = {}
        for s in sg:
            k = self.天机线(s['uri'], base)
            st[k] = st.get(k, 0.0) + float(s.get('dur') or 0)
        mkk = max(st.items(), key=lambda x: x[1])[0] if st else ('', '')
        tdur = sum(st.values()) or 0
        mdur = st.get(mkk, 0)

        cl = []
        rm = 0
        for idx, s in enumerate(sg):
            k = self.天机线(s['uri'], base)
            fr = idx < 12
            au = __import__('urllib.parse').parse.urljoin(base, s.get('uri', ''))
            ia = self.禁地判(s['uri'], s.get('dur'), s.get('tags'))
            if mk and mk not in __import__('urllib.parse').parse.urlparse(au).path.lower():
                ia = True
            tt = '\n'.join(s.get('tags') or []).upper()
            if fr and 'METHOD=NONE' in tt and mk and mk not in __import__('urllib.parse').parse.urlparse(au).path.lower():
                ia = True
            if (not ia) and fr and tdur > 0 and mdur >= tdur * 0.6:
                if k != mkk and st.get(k, 0) <= 90:
                    ia = True
            if ia:
                rm += 1
                continue
            s['_idx'] = idx
            cl.append(s)

        if rm == 0 and len(sg) > 4:
            ac = 0.0
            ct = 0
            for idx, s in enumerate(sg[:12]):
                k = self.天机线(s['uri'], base)
                if k == mkk and ac >= 3:
                    break
                ac += float(s.get('dur') or td or 3)
                ct = idx + 1
                if ac >= skip:
                    break
            if ct > 0 and ct < len(sg):
                fk = self.天机线(sg[0]['uri'], base)
                if fk != mkk:
                    cl = sg[ct:]
                    rm = ct

        if not cl:
            cl = sg
            rm = 0

        nl = []
        hm = False
        for ln in hd:
            if ln.startswith('#EXTM3U'):
                hm = True
            if ln.startswith('#EXT-X-MEDIA-SEQUENCE') or ln.startswith('#EXT-X-START'):
                continue
            if ln.startswith('#EXT-X-KEY') and 'METHOD=NONE' in ln.upper() and rm > 0:
                continue
            nl.append(ln)
        if not hm:
            nl.insert(0, '#EXTM3U')
        fi = cl[0].get('_idx', rm) if cl else rm
        nl.append(f'#EXT-X-MEDIA-SEQUENCE:{ms + fi}')
        for s in cl:
            for tg in s.get('tags') or []:
                if tg.startswith('#EXT-X-KEY') or tg.startswith('#EXT-X-MAP'):
                    tg = __import__('re').sub(r'URI="([^"]+)"', lambda m: 'URI="' + __import__('urllib.parse').parse.urljoin(base, m.group(1)) + '"', tg)
                nl.append(tg)
            nl.append(__import__('urllib.parse').parse.urljoin(base, s.get('uri', '')))
        if tl:
            for ln in tl:
                if ln.startswith('#EXT-X-ENDLIST'):
                    nl.append(ln)
        elif '#EXT-X-ENDLIST' in t:
            nl.append('#EXT-X-ENDLIST')
        return '\n'.join(nl) + '\n'
