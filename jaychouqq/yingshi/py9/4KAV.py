# coding=utf-8
"""
目标站: 4K-AV  首页: https://4k-av.com  (英文站 /en/，另有中文站 /zh/)
TVBox / OK影视 / 默影视 兼容 Python 源 (type 3)：
  - homeContent / categoryContent / detailContent / searchContent / playerContent 全接口
  - 分类: TV / Movies / AV + 年份(2026-2019) + 标签(Action/Drama/...)
  - 播放链路: 详情页 <video><source src=".../1080P/{hash}.m3u8"> 内嵌直链，
    无需签名、无需 WASM；m3u8 内 ts 分片为相对路径，按 m3u8 同目录解析即可播放
  - TV 剧集: 每集独立详情页(/en/tv/{id}-{slug}/)，详情页 #rtlist 列出全部集链接，
    本脚本将全部集聚合进 vod_play_url，播放时逐集解析真实 m3u8
  - 注意: 站点对 HTML 页有频率限制(连续快速请求会 403)，脚本内置浏览器头 + 失败重试
    + 可配置请求间隔；m3u8/ts 直链不受限

配置（写在配置 json 的 ext 里，不写用默认值）:
    {"host": "https://4k-av.com", "delay": 0.4, "timeout": 15, "cookie": ""}
    - host:    站点域名(备用镜像)
    - delay:   页面请求间隔秒数(默认 0.4，被限流时可调大到 1-2)
    - cookie:  可选 Cookie 字符串(一般无需)
"""
import gzip
import io
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def log(self, msg):
            pass

        def getProxyUrl(self):
            return ''


class Spider(BaseSpider):

    def init(self, extend=""):
        # ---- 站点与浏览器头 ----
        self.site_url = "https://4k-av.com"
        self.www_url = "https://www.4k-av.com"
        self.timeout = 15
        self.delay = 0.4          # 页面请求间隔(秒)，防限流
        self.cookie = ""
        if extend:
            ext = (extend or "").strip()
            if ext.startswith('{'):
                try:
                    d = json.loads(ext)
                    self.site_url = str(d.get('host') or self.site_url).rstrip('/')
                    self.delay = float(d.get('delay') or self.delay)
                    self.timeout = int(d.get('timeout') or self.timeout)
                    self.cookie = str(d.get('cookie') or '').strip()
                except Exception:
                    pass
            else:
                self.cookie = ext
        self.my_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                      'image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.site_url + "/en/",
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
        }
        if self.cookie:
            self.my_headers['Cookie'] = self.cookie

        # ---- 分类映射: type_id -> (名称, URL 路径) ----
        self.categories = [
            {"type_id": "1", "type_name": "电视剧"},
            {"type_id": "2", "type_name": "电影"},
            {"type_id": "3", "type_name": "AV"},
            {"type_id": "4", "type_name": "2026年"},
            {"type_id": "5", "type_name": "2025年"},
            {"type_id": "6", "type_name": "2024年"},
            {"type_id": "7", "type_name": "2023年"},
            {"type_id": "8", "type_name": "2022年"},
            {"type_id": "9", "type_name": "2021年"},
            {"type_id": "10", "type_name": "2020年"},
            {"type_id": "11", "type_name": "2019年"},
            {"type_id": "12", "type_name": "动作片"},
            {"type_id": "13", "type_name": "剧情片"},
            {"type_id": "14", "type_name": "冒险片"},
            {"type_id": "15", "type_name": "喜剧片"},
            {"type_id": "16", "type_name": "国产"},
            {"type_id": "17", "type_name": "恐怖片"},
            {"type_id": "18", "type_name": "战争片"},
            {"type_id": "19", "type_name": "科幻片"},
            {"type_id": "20", "type_name": "动画片"},
            {"type_id": "21", "type_name": "韩剧"},
            {"type_id": "22", "type_name": "犯罪片"},
            {"type_id": "23", "type_name": "纪录片"},
        ]
        self._cat_url = {
            "1": "/en/tv/",
            "2": "/en/movie/",
            "3": "/en/av/",
            "4": "/en/2026/",
            "5": "/en/2025/",
            "6": "/en/2024/",
            "7": "/en/2023/",
            "8": "/en/2022/",
            "9": "/en/2021/",
            "10": "/en/2020/",
            "11": "/en/2019/",
            "12": "/en/tag/Action/",
            "13": "/en/tag/Drama/",
            "14": "/en/tag/Adventure/",
            "15": "/en/tag/Comedy/",
            "16": "/en/tag/" + urllib.parse.quote("China's", safe='') + "/",
            "17": "/en/tag/Horror/",
            "18": "/en/tag/War/",
            "19": "/en/tag/Sci-Fi/",
            "20": "/en/tag/Animation/",
            "21": "/en/tag/Korean/",
            "22": "/en/tag/Crime/",
            "23": "/en/tag/Documentary/",
        }
        self._total_page_cache = {}

    # ================= HTTP =================
    def _fetch(self, url, retry=2, referer=None):
        """抓取页面文本；403/超时自动退避重试。返回 str 或 None"""
        if self.delay > 0:
            time.sleep(self.delay)
        headers = dict(self.my_headers)
        if referer:
            headers['Referer'] = referer
        last_err = None
        for i in range(retry + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = resp.read()
                    if resp.headers.get('Content-Encoding', '').lower() == 'gzip':
                        try:
                            data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
                        except OSError:
                            pass
                    return data.decode('utf-8', 'ignore')
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (403, 429, 500, 502, 503):
                    time.sleep(1.2 * (i + 1) + random.uniform(0, 0.5))
                    continue
                return None
            except Exception as e:
                last_err = e
                time.sleep(0.8 * (i + 1))
        return None

    def _abs(self, href):
        """相对链接转绝对；无 /en/ 语言前缀的 /movie/ /tv/ /av/ 路径补上 /en/"""
        h = (href or '').strip().strip('"').strip("'")
        if not h:
            return ''
        if h.startswith('http'):
            return h
        h = h.lstrip('./')
        if not h.startswith('/'):
            h = '/' + h
        if re.match(r'^/(movie|tv|av|20\d\d|tag|s)\b', h) and not h.startswith('/en/'):
            h = '/en' + h
        return self.site_url + h

    # ================= 卡片解析 =================
    def _parse_cards(self, html):
        """解析 NTMitem / RTMitem 卡片列表 -> vods"""
        vods = []
        seen = set()
        blocks = re.split(r'(?=<div class="(?:NTMitem|RTMitem)[^"]*">)', html)
        for blk in blocks:
            if 'NTMitem' not in blk and 'RTMitem' not in blk:
                continue
            href = ''
            m = re.search(r'<a[^>]+href="(/?(?:en/)?(?:movie|tv|av)/[^"]+)"', blk)
            if not m:
                continue
            href = m.group(1)
            key = href
            if key in seen:
                continue
            seen.add(key)

            # 名称: 优先含中文的 title(海报链接 title 常为中文译名)，否则 h2 文本
            name = ''
            m2 = re.search(r'<a[^>]+title="([^"]*[^\x00-\x7f][^"]*)"', blk)
            if m2:
                name = m2.group(1).strip()
            if not name:
                m2 = re.search(r'<a[^>]+title="([^"]*)"', blk)
                if m2:
                    name = m2.group(1).strip()
            if not name or re.match(r'^[\s.]+$', name):
                m2 = re.search(r'<h2[^>]*>(.*?)</h2>', blk, re.S)
                if m2:
                    name = re.sub(r'<[^>]+>', '', m2.group(1)).strip()
            if not name:
                name = '4K-AV'

            # 海报
            pic = ''
            m3 = re.search(r'<img[^>]+src="(https://www\.4k-av\.com[^"]+poster_nail\.jpg)"', blk)
            if m3:
                pic = m3.group(1)

            # 备注(分辨率)
            remarks = ''
            m4 = re.search(r'<label title="(?:Resolution|分辨率)"\s*>(.*?)</label>', blk, re.S)
            if m4:
                remarks = re.sub(r'<[^>]+>', '', m4.group(1)).strip()
            if not remarks:
                m4 = re.search(r'<span[^>]*>(4K[^<]*)</span>', blk)
                if m4:
                    remarks = m4.group(1).strip()

            # 年份
            year = ''
            m5 = re.search(r'<label title="(?:Years|年份)"\s*>(.*?)</label>', blk, re.S)
            if m5:
                year = re.sub(r'<[^>]+>', '', m5.group(1)).strip()

            vods.append({
                "vod_id": self._abs(href),
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remarks,
                "vod_year": year,
            })
        return vods

    # ================= homeContent =================
    def homeContent(self, filter):
        html = self._fetch(self.site_url + "/en/")
        vods = self._parse_cards(html or '')
        return {"class": self.categories, "list": vods}

    # ================= categoryContent =================
    def _get_total_pages(self, path):
        """抓无页码分类页，解析 '页次 X/T' 或 'Page No. X/T' 中的总页数 T；无分页控件返回 1"""
        if path in self._total_page_cache:
            return self._total_page_cache[path]
        html = self._fetch(self.site_url + path) or ''
        m = re.search(r'(?:页次|Page No\.)\s*\d+/(\d+)', html)
        total = int(m.group(1)) if m else 1
        self._total_page_cache[path] = total
        return total

    def categoryContent(self, tid, pg, filter, extend):
        path = self._cat_url.get(str(tid))
        if not path:
            return {"page": pg, "pagecount": 1, "limit": 40, "total": 0, "list": []}
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1

        total = self._get_total_pages(path)
        # 站点第 1 页最老，无页码 URL = 第 total 页(最新)；TVBox pg=1 应给最新
        target = total - pg + 1
        if target < 1:
            return {"page": pg, "pagecount": total, "limit": 40, "total": 0, "list": []}
        if target == total:
            url = self.site_url + path            # 最新页(无页码 URL)
        else:
            url = self.site_url + path + "page-%d.html" % target
        html = self._fetch(url) or ''
        vods = self._parse_cards(html)
        total_n = total * max(len(vods), 1)
        return {"page": pg, "pagecount": total, "limit": len(vods),
                "total": total_n, "list": vods}

    # ================= detailContent =================
    def detailContent(self, ids):
        vid = (ids or '').split(',')[0].strip()
        if not vid:
            return {"list": []}
        url = vid if vid.startswith('http') else self._abs(vid)
        html = self._fetch(url, referer=self.site_url + "/en/") or ''
        if not html:
            return {"list": []}

        # --- 标题/年份/备注 ---
        h1 = ''
        m = re.search(r'<h1[^>]*title="([^"]*)"[^>]*>', html)
        if m:
            h1 = m.group(1).strip()
        if not h1:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if m:
                h1 = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        name = h1 or '4K-AV'

        # 元数据区 <div id="MainContent_videodetail">: 分辨率/片长/年份
        year = ''
        remarks = ''
        vd = re.search(r'<div id="MainContent_videodetail"[^>]*>(.*?)</div>\s*<div', html, re.S)
        if not vd:
            vd = re.search(r'<div[^>]*class="videodetail"[^>]*>(.*?)</div>', html, re.S)
        if vd:
            seg = vd.group(1)
            m = re.search(r'分辨率\s*[:：]\s*([^<\n]{1,30})', seg)
            if m:
                remarks = m.group(1).strip()
            if not remarks:
                m = re.search(r'Resolution\s*[:：]\s*([^<\n]{1,30})', seg)
                if m:
                    remarks = m.group(1).strip()
            m = re.search(r'年份\s*[:：][^>]*>?\s*(\d{4})', seg)
            if not m:
                m = re.search(r'(\d{4})</a>', seg)
            if m:
                year = m.group(1)

        # --- 海报 ---
        pic = ''
        m = re.search(r'<div id="MainContent_poster"[^>]*>.*?<img[^>]+src="([^"]+)"', html, re.S)
        if not m:
            m = re.search(r'<img[^>]+src="(https://www\.4k-av\.com[^"]+poster_nail\.jpg)"', html)
        if m:
            pic = m.group(1).strip()

        # --- 简介(MainContent_videodesc 下的 p) ---
        content = ''
        vde = re.search(r'<div id="MainContent_videodesc"[^>]*>(.*?)</div>\s*</div>', html, re.S)
        if vde:
            t = re.sub(r'<[^>]+>', ' ', vde.group(1))
            t = re.sub(r'\s+', ' ', t).strip()
            if t:
                content = t

        # --- 播放: #rtlist 剧集(每集独立页面) or 单集 ---
        play_from = "4K-AV"
        episodes = []                       # [(集名, URL)]
        rt = re.search(r'<ul id="rtlist">(.*?)</ul>', html, re.S)
        if rt:
            lis = re.split(r'(?=<li>)', rt.group(1))
            for li in lis:
                if '<li' not in li:
                    continue
                # 集名 span: <span>S01E01</span> / <span class="stitle">S01E01</span>
                st = re.search(r'<span[^>]*>(.*?)</span>', li, re.S)
                title = re.sub(r'<[^>]+>', '', st.group(1)).strip() if st else ''
                a = re.search(r'<a[^>]+href="(/?(?:en/)?tv/[^"]+)"', li)
                if a:
                    ep_url = self._abs(a.group(1))
                else:
                    ep_url = url
                if title and re.search(r'[EeP]\d|\d{1,2}', title):
                    episodes.append((title, ep_url))
        if not episodes:
            episodes.append(("正片", url))

        play_url = '#'.join('%s$%s' % (t, u) for t, u in episodes)

        vod = {
            "vod_id": url,
            "vod_name": name,
            "vod_pic": pic,
            "vod_year": year,
            "vod_remarks": remarks,
            "vod_area": "",
            "vod_content": content,
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    # ================= searchContent =================
    def searchContent(self, key, quick, pg=""):
        if not key:
            return {"list": []}
        url = self.site_url + "/en/s?y=" + urllib.parse.quote(str(key))
        html = self._fetch(url) or ''
        vods = self._parse_cards(html)
        return {"list": vods}

    # ================= playerContent =================
    def playerContent(self, ids, flag, vipFlags):
        """ids 为某集详情页 URL，抓页面提取真实 m3u8 直链"""
        vid = (ids or '').strip()
        if not vid:
            return {"parse": 0, "url": "", "header": {}}
        url = vid if vid.startswith('http') else self._abs(vid)
        html = self._fetch(url, referer=self.site_url + "/en/") or ''
        m3u8s = re.findall(r'<source[^>]+src="(https?://[^"]+\.m3u8[^"]*)"', html)
        real = ''
        if m3u8s:
            for u in m3u8s:
                if '1080P' in u or '1080' in u or '720P' in u:
                    real = u
                    break
            if not real:
                real = m3u8s[0]
        if not real:
            # 回退: 交给壳子尝试解析页面
            return {"parse": 1, "url": url, "header": dict(self.my_headers)}
        return {"parse": 0, "url": real, "header": {
            'User-Agent': self.my_headers['User-Agent'],
            'Referer': self.www_url,
        }}


# ================= 本地自测 =================
if __name__ == '__main__':
    s = Spider()
    s.init()
    print("== homeContent ==")
    h = s.homeContent(False)
    print("class:", len(h.get('class', [])), "list:", len(h.get('list', [])))
    for v in h.get('list', [])[:3]:
        print("  ", v)
    print("== categoryContent tid=2 pg=1 (电影最新) ==")
    c = s.categoryContent('2', 1, '', '')
    print("pagecount:", c.get('pagecount'), "limit:", c.get('limit'))
    for v in c.get('list', [])[:3]:
        print("  ", v)
    print("== categoryContent tid=12 pg=1 (动作) ==")
    c2 = s.categoryContent('12', 1, '', '')
    print("pagecount:", c2.get('pagecount'), "limit:", c2.get('limit'))
    for v in c2.get('list', [])[:2]:
        print("  ", v)
    print("== searchContent 'made' ==")
    s2 = s.searchContent('made', False)
    print("size:", len(s2.get('list', [])))
    for v in s2.get('list', [])[:3]:
        print("  ", v)
    if s2.get('list'):
        print("== detailContent ==")
        d = s.detailContent(s2['list'][0]['vod_id'])
        vod = d['list'][0]
        print("  name:", vod['vod_name'], "| year:", vod['vod_year'], "| remarks:", vod['vod_remarks'])
        print("  pic:", vod['vod_pic'][:80])
        print("  content:", vod['vod_content'][:80])
        print("  play_url:", vod['vod_play_url'][:220])
        first_ep_url = vod['vod_play_url'].split('#')[0].split('$')[-1]
        print("== playerContent first ep ==")
        p = s.playerContent(first_ep_url, '', '')
        print("  parse:", p.get('parse'), "url:", p.get('url'))