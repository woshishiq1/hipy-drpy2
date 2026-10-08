# coding=utf-8
#!/usr/bin/python
"""PPnix (ppnix.com) dr_py 爬虫 — 诊断版"""
import sys
import re
import json
import traceback

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    import requests
    class BaseSpider:
        def fetch(self, url, headers=None, timeout=10):
            return requests.get(url, headers=headers or {}, timeout=timeout)


class Spider(BaseSpider):

    HOST = "https://www.ppnix.com"
    CN_URL = "https://www.ppnix.com/cn/"

    CATEGORIES = [
        {'type_id': '1', 'type_name': '电影'},
        {'type_id': '2', 'type_name': '电视剧'},
    ]

    def init(self, extend=""):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': self.HOST + '/',
        }

    def getName(self):
        return "PPnix"

    def homeContent(self, filter):
        result = {}
        result['class'] = [{'type_id': c['type_id'], 'type_name': c['type_name']} for c in self.CATEGORIES]
        try:
            rsp = self.fetch(self.CN_URL, self.headers)
            html = self._html(rsp)
            result['list'] = self._list(html)
        except Exception as e:
            self._log("homeContent ERROR: " + str(e) + " | " + traceback.format_exc().replace('\n', ' '))
            result['list'] = []
        return result

    def homeVideoContent(self):
        try:
            rsp = self.fetch(self.CN_URL, self.headers)
            return {'list': self._list(self._html(rsp))}
        except Exception as e:
            self._log("homeVideoContent ERROR: " + str(e))
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {'page': int(pg) if pg else 1, 'limit': 24}
        path = 'movie' if str(tid) == '1' else 'tv'
        url = "%s/cn/%s/" % (self.HOST, path)
        self._log("categoryContent tid=%s url=%s" % (tid, url))
        try:
            rsp = self.fetch(url, self.headers)
            self._log("categoryContent rsp type=%s" % type(rsp).__name__)
            html = self._html(rsp)
            self._log("categoryContent html len=%s" % len(html))
            result['list'] = self._list(html)
            self._log("categoryContent list count=%d" % len(result['list']))
            m = re.search(r'<a\s+href="[^"]*---(\d+)-\.html"[^>]*>尾页</a>', html)
            result['pagecount'] = int(m.group(1)) + 1 if m else 1
        except Exception as e:
            self._log("categoryContent ERROR: " + str(e) + " | " + traceback.format_exc().replace('\n', ' '))
            result['list'] = []
            result['pagecount'] = 0
        result['total'] = result.get('pagecount', 0) * 24
        return result

    def searchContent(self, key, quick, pg="1"):
        try:
            from urllib.parse import quote
            url = "%s/cn/search/%s--.html" % (self.HOST, quote(key))
            rsp = self.fetch(url, self.headers)
            html = self._html(rsp)
            if html:
                pag = re.search(r'<div\s+class="pagination[^"]*">\s*<ul>(.*?)</ul>', html, re.DOTALL)
                if pag and len(re.findall(r'<li', pag.group(1))) > 0:
                    return {'list': []}
                return {'list': self._list(html)}
        except Exception as e:
            self._log("searchContent ERROR: " + str(e))
        return {'list': []}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) and ids else (ids or '')
        vid = str(vid).split('/')[-1]
        for path in ['movie', 'tv']:
            try:
                url = "%s/cn/%s/%s.html" % (self.HOST, path, vid)
                rsp = self.fetch(url, self.headers)
                html = self._html(rsp)
                if html and 'product-header' in html:
                    vod = self._detail(html, path)
                    if vod and vod.get('vod_name'):
                        return {'list': [vod]}
            except Exception as e:
                self._log("detailContent ERROR: " + str(e))
                continue
        return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        s = str(id)
        if '$' in s:
            parts = s.split('$')
            m3u8 = parts[-1]
        else:
            m3u8 = s
        if not m3u8.startswith('http'):
            m3u8 = self.HOST + m3u8
        return {'header': '', 'parse': 0, 'url': m3u8}

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.match(r'https?://.*?\.(m3u8|mp4|flv|avi|mkv|rmvb|wmv)(\?.*)?$', url, re.IGNORECASE))

    def manualVideoCheck(self):
        pass

    def _log(self, msg):
        print("[PPnix] " + msg, file=sys.stderr)

    def _html(self, rsp):
        if rsp is None:
            return ''
        if hasattr(rsp, 'read') and callable(getattr(rsp, 'read')):
            data = rsp.read()
            if isinstance(data, bytes):
                if data[:2] == b'\x1f\x8b':
                    import gzip
                    try:
                        data = gzip.decompress(data)
                    except Exception:
                        pass
                return data.decode('utf-8', errors='replace')
            return str(data)
        if hasattr(rsp, 'text'):
            t = rsp.text
            if isinstance(t, str):
                return t
            if isinstance(t, bytes):
                return t.decode('utf-8', errors='replace')
            return str(t)
        if hasattr(rsp, 'content'):
            c = rsp.content
            if isinstance(c, bytes):
                return c.decode('utf-8', errors='replace')
            return str(c)
        if isinstance(rsp, bytes):
            return rsp.decode('utf-8', errors='replace')
        if isinstance(rsp, str):
            return rsp
        return str(rsp)

    def _list(self, html):
        videos = []
        if not html:
            return videos
        pat = re.compile(
            r'<li>\s*<a\s+href="/cn/(movie|tv)/(\d+)\.html"\s+class="thumbnail"[^>]*>\s*'
            r'<img[^>]*src="([^"]+)"[^>]*class="thumb"[^>]*>.*?</a>\s*'
            r'<h2>\s*<a\s+href="[^"]*"[^>]*>([^<]+)</a>\s*</h2>\s*'
            r'(?:<footer>.*?<span[^>]*class="rate"[^>]*>([^<]*)</span>.*?</footer>)?',
            re.DOTALL
        )
        for m in pat.findall(html):
            try:
                videos.append({
                    'vod_id': m[0] + '/' + m[1],
                    'vod_name': m[3].strip(),
                    'vod_pic': m[2],
                    'vod_remarks': m[4].strip() if len(m) > 4 and m[4] else '',
                })
            except Exception:
                continue
        return videos

    def _detail(self, html, path):
        if not html:
            return {}
        try:
            title = ''
            m = re.search(r'<h1\s+class="product-title">\s*(.*?)\s*<span', html, re.DOTALL)
            if m:
                title = m.group(1).strip()
            score = ''
            m = re.search(r'<h1\s+class="product-title">.*?<span\s+class="rate">([^<]*)</span>', html, re.DOTALL)
            if m:
                score = m.group(1).strip()
            year = ''
            m = re.search(r'<h1\s+class="product-title">.*?<span>\((\d{4})\)</span>', html, re.DOTALL)
            if m:
                year = m.group(1)
            pic = ''
            m = re.search(r'<header\s+class="product-header">\s*<img[^>]*src="([^"]+)"[^>]*class="thumb"', html, re.DOTALL)
            if m:
                pic = m.group(1)
            director, actors, type_name, area, desc = '', '', '', '', ''
            for em in re.finditer(r'<div\s+class="product-excerpt">(.*?)</div>', html, re.DOTALL):
                block = em.group(1)
                lm = re.match(r'\s*([^：:]+)[：:]', block)
                if not lm:
                    continue
                label = lm.group(1).strip()
                spans = re.findall(r'<span[^>]*>(.*?)</span>', block, re.DOTALL)
                full = ''.join([re.sub(r'<[^>]+>', '', t).strip() for t in spans])
                links = re.findall(r'<a[^>]*>([^<]+)</a>', block)
                lt = ' / '.join([l.strip() for l in links if l.strip()])
                if label.startswith('导演'):
                    director = lt or full
                elif label.startswith('主演'):
                    actors = lt or full
                elif label.startswith('类型'):
                    type_name = lt or full
                elif label.startswith('国家'):
                    area = lt or full
                elif label.startswith('简介'):
                    desc = full
            class_id, info_id, m3u8s = '', '', []
            m = re.search(r"classid=(\d+);classurl='([^']+)';infoid=(\d+);sub='([^']*)';m3u8=\[([^\]]+)\]", html)
            if m:
                class_id, info_id = m.group(1), m.group(3)
                m3u8s = re.findall(r"""['"]([^'"]+)['"]""", m.group(5))
            plays = []
            for i, ep in enumerate(m3u8s):
                url = "%s/info/m3u8/%s/%s.m3u8" % (self.HOST, info_id, ep)
                name = "第%d集" % (i + 1) if class_id == '2' else ep
                plays.append("%s$%s" % (name, url))
            return {
                'vod_id': path + '/' + info_id if info_id else '',
                'vod_name': title,
                'vod_pic': pic,
                'vod_year': year,
                'vod_score': score,
                'vod_director': director,
                'vod_actor': actors,
                'vod_area': area,
                'vod_type': type_name,
                'vod_content': desc,
                'vod_play_from': "电视剧" if class_id == '2' else "电影",
                'vod_play_url': '#'.join(plays) if plays else '',
            }
        except Exception:
            return {}


if __name__ == '__main__':
    sp = Spider()
    sp.init()
    print("home list:", len(sp.homeContent(False).get('list', [])))
    print("movie list:", len(sp.categoryContent('1', '1', False, {}).get('list', [])))
    print("tv list:", len(sp.categoryContent('2', '1', False, {}).get('list', [])))
