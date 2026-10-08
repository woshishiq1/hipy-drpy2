# -*- coding: utf-8 -*-
"""
《魑魅魍魉》- TVBox/影视仓 dr_py Python 源 (HKL 兼容版)
站点: http://xn--pg3-chimei100-com-7483af92d.chimei69.com  (页面走 http 明文; 播放 m3u8 走 https)
类型: MacCMS v10
"""
import sys
import re
import json
import html as ihtml
from urllib.parse import quote, urljoin, unquote

try:
    import requests
except ImportError:
    requests = None

try:
    sys.path.append('..')
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        def init(self, extend=""): pass
        def getName(self): return ""
        def homeContent(self, filter): return {'class': [], 'filters': {}}
        def homeVideoContent(self): return {'list': []}
        def categoryContent(self, tid, pg, filter, extend): return {'list': []}
        def detailContent(self, ids): return {'list': []}
        def searchContent(self, key, quick, pg='1'): return {'list': []}
        def playerContent(self, flag, id, vipFlags=None): return {'parse': 0, 'url': id, 'header': {}}


class Spider(BaseSpider):
    name = '魑魅魍魉'
    HOST = 'http://xn--pg3-chimei100-com-7483af92d.chimei69.com'

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = self.HOST
        self.timeout = 20
        # 站点分类（首页导航）
        self.CATEGORIES = (
            ('国产精品', '15'), ('国产精选', '601'), ('原创偷拍', '13'),
            ('自拍偷拍', '591'), ('中文字幕', '20'),
        )
        self.headers = {
            'User-Agent': ('Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 '
                           'Chrome/120.0 Mobile Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.s = requests.Session() if requests else None
        if self.s:
            self.s.headers.update(self.headers)

    def init(self, extend=''):
        config = extend if isinstance(extend, dict) else {}
        if not config and extend:
            try:
                config = json.loads(extend) if isinstance(extend, str) else {}
            except Exception:
                config = {}
        host = str(config.get('host') or config.get('siteUrl') or '').strip().rstrip('/')
        if host.startswith(('http://', 'https://')):
            self.host = host
        return None

    def getName(self):
        return self.name

    def getDependence(self):
        return []

    def homeLayout(self):
        return 0

    def destroy(self):
        try:
            if self.s:
                self.s.close()
        except Exception:
            pass

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        v = str(url or '').lower()
        return any(x in v for x in ('.m3u8', '.mp4', '.m4v', '.mpd', '.flv', '.webm', '.ts'))

    def _request(self, url, params=None, referer=None, post=False, data=None, retry=2):
        headers = dict(self.headers)
        if referer:
            headers['Referer'] = referer
        # 优先运行端自带的 fetch，适配 Android 代理与证书
        fetch = getattr(self, 'fetch', None)
        if callable(fetch) and not post:
            try:
                r = fetch(url, headers=headers, params=params, timeout=self.timeout)
                if r is not None and getattr(r, 'text', ''):
                    return r
            except Exception as e:
                self._log('fetch fail %s: %s' % (url, e))
        if self.s is None:
            return None
        for att in range(max(1, retry)):
            try:
                if post:
                    r = self.s.post(url, data=data, headers=headers, params=params,
                                    timeout=self.timeout, allow_redirects=True, verify=False)
                else:
                    r = self.s.get(url, headers=headers, params=params,
                                   timeout=self.timeout, allow_redirects=True, verify=False)
                if r.status_code in (403, 503, 429):
                    continue
                try:
                    r.encoding = r.apparent_encoding or 'utf-8'
                except Exception:
                    pass
                return r
            except Exception as e:
                self._log('request fail %s: %s' % (url, e))
        return None

    def _log(self, msg):
        try:
            self.log('[%s] %s' % (self.name, msg))
        except Exception:
            print('[%s] %s' % (self.name, msg))

    @staticmethod
    def clean(s):
        return re.sub(r'\s+', ' ', ihtml.unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()

    def _cards(self, html, base_url):
        """解析 list 页 videoImg 结构卡片。兼容 destinction：
        卡片 = <a class="videoImg image_rollover_top" href="/content/{id}.html" title="标题" imgtag="图" style="background-image:url('主图'),..."><span class="vodtime">时长</span></a> + <a title="标题"><b>标题</b></a>"""
        vods = []
        for m in re.finditer(
                r'<a[^>]+class="videoImg[^"]*"[^>]*>.*?</a>\s*<a[^>]*href="([^"]*/content/(\d+)\.html)"[^>]*>(.*?)</a>',
                html or '', re.S):
            href, vid = m.group(1), m.group(2)
            tail = m.group(3)
            head = m.group(0)
            title_m = re.search(r'title="([^"]*)"', head) or re.search(r'title="([^"]*)"', tail)
            title = title_m.group(1) if title_m else ''
            if not title:
                tm = re.search(r'<b[^>]*>([^<]+)</b>', tail)
                title = tm.group(1) if tm else ''
            # 背景图：取第一个 url('主图')
            img = re.search(r"background-image:\s*url\('([^']+)'\)", head)
            pic = img.group(1) if img else ''
            if not pic:
                img2 = re.search(r'imgtag="([^"]*)"', head)
                if img2:
                    pic = img2.group(1)
            dur = re.search(r'<span class="vodtime">([^<]*)</span>', head)
            vods.append({
                'vod_id': vid,
                'vod_name': self.clean(title),
                'vod_pic': urljoin(base_url, pic) if pic else '',
                'vod_remarks': self.clean(dur.group(1)) if dur else '',
            })
        # 兼容：若上面结构没解析到，退回按每个 videoImg 卡片单独匹配
        if not vods:
            for m2 in re.finditer(
                    r'<a[^>]+class="videoImg[^"]*"[^>]*href="([^"]*/content/(\d+)\.html)"[^>]*', html or '', re.I):
                block = m2.group(0)
                href, vid = m2.group(1), m2.group(2)
                tm = re.search(r'title="([^"]*)"', block)
                title = tm.group(1) if tm else ''
                img = re.search(r"background-image:\s*url\('([^']+)'\)", block)
                pic = img.group(1) if img else (re.search(r'imgtag="([^"]*)"', block).group(1) if re.search(r'imgtag="([^"]*)"', block) else '')
                dur = re.search(r'<span class="vodtime">([^<]*)</span>', block)
                vods.append({
                    'vod_id': vid, 'vod_name': self.clean(title),
                    'vod_pic': urljoin(base_url, pic) if pic else '',
                    'vod_remarks': self.clean(dur.group(1)) if dur else '',
                })
        seen, out = set(), []
        for v in vods:
            k = v['vod_id'] + '|' + v['vod_name']
            if k in seen:
                continue
            seen.add(k)
            out.append(v)
        return out

    def homeContent(self, filter=False):
        return {'class': [{'type_id': str(i), 'type_name': n} for n, i in self.CATEGORIES],
                'filters': {}}

    def homeVideoContent(self):
        r = self._request(self.host + '/')
        base = getattr(r, 'url', '') or self.host + '/'
        return {'list': self._cards(r.text, base) if r and r.text else []}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            page = int(pg)
        except (ValueError, TypeError):
            page = 1
        if page < 1:
            page = 1
        if page == 1:
            url = '%s/list/%s.html' % (self.host, tid)
        else:
            url = '%s/list/%s-%s.html' % (self.host, tid, page)
        r = self._request(url)
        if not r or not r.text:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 20, 'total': 0}
        vods = self._cards(r.text, r.url)
        pc = self._pagecount(r.text, tid)
        return {'list': vods, 'page': page, 'pagecount': pc, 'limit': 20, 'total': 0}

    def _pagecount(self, html, tid):
        m = re.search(r'/list/%s-(\d+)\.html[^>]*>\s*尾页' % re.escape(str(tid)), html)
        if m:
            try:
                return max(1, int(m.group(1)))
            except ValueError:
                pass
        nums = [int(x) for x in re.findall(r'/list/%s-(\d+)\.html' % re.escape(str(tid)), html)]
        return max(nums) if nums else 1

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) and ids else ids or '').strip()
        if not vid:
            return {'list': []}
        r = self._request('%s/content/%s.html' % (self.host, vid))
        if not r or not r.text:
            return {'list': []}
        return {'list': [self._detail(r.text, vid, getattr(r, 'url', self.host))]}

    def _detail(self, html, vid, base_url):
        title = ''
        tm = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html) or \
             re.search(r'<h3 class="vid-name"[^>]*>\s*<a[^>]*title="([^"]*)"', html)
        if tm:
            title = self.clean(tm.group(1))
        if (not title) or title.startswith('正在播放') or title.startswith('播放'):
            tm2 = re.search(r'<title>([\s\S]*?)</title>', html)
            if tm2:
                t = self.clean(tm2.group(1))
                # 去掉 播放：/正在播放： 前缀 与 站名后缀
                for pre in ('正在播放：', '正在播放:', '播放：', '播放:'):
                    if t.startswith(pre):
                        t = t[len(pre):]
                t = re.split(r'\s*[-_|]\s*(?:魑魅魍魉|藏姬阁|带你进入|自拍图库)', t)[0].strip(' -')
                title = t
        img = re.search(r"postimg\s*=\s*'([^']+)'", html) or \
              re.search(r"background-image:\s*url\('([^']+)'\)", html) or \
              re.search(r'<img[^>]+(?:src|data-original)="([^"]+\.(?:jpg|png|webp))"', html)
        play_from = '在线播放'
        play_url = ''
        mu = re.search(r"var\s+mac_url\s*=\s*unescape\('([^']+)'\)", html)
        if mu:
            decoded = unquote(mu.group(1))
            pairs = []
            for p in decoded.split('#'):
                if '$' in p:
                    n, u = p.split('$', 1)
                    pairs.append((n.strip(), u.strip()))
            if pairs:
                play_url = '#'.join('%s$%s' % (n, u) for n, u in pairs)
        else:
            mu2 = re.search(r'(https?://[^\s\'"]+\.(?:m3u8|mp4|mpd|flv)[^\s\'"]*)', html)
            if mu2:
                play_url = '第1集$%s' % mu2.group(1)
        return {
            'vod_id': vid,
            'vod_name': title or vid,
            'vod_pic': urljoin(base_url or self.host + '/', img.group(1)) if img else '',
            'vod_content': '',
            'vod_type_name': '',
            'vod_play_from': play_from if play_url else '',
            'vod_play_url': play_url,
        }

    def searchContent(self, key, quick=False, pg='1'):
        keyword = str(key or '').strip()
        try:
            page = int(pg)
        except (ValueError, TypeError):
            page = 1
        if page < 1:
            page = 1
        vods = []
        found = False
        for path in ['/search.php?searchtype=5&wd=%s' % quote(keyword),
                     '/index.php/vod/search.html?wd=%s' % quote(keyword),
                     '/?wd=%s' % quote(keyword)]:
            r = self._request(self.host + path)
            if r and r.text:
                cand = self._cards(r.text, r.url)
                if cand:
                    vods = cand
                    found = True
                    break
        if not found:
            r = self._request(self.host + '/')
            if r and r.text:
                allv = self._cards(r.text, r.url)
                vods = [v for v in allv if keyword in v['vod_name']]
        return {'list': vods, 'page': page, 'pagecount': 1, 'limit': 20, 'total': 0}

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or '').strip()
        if not url:
            return {'parse': 0, 'url': '', 'header': {}}
        if self.isVideoFormat(url):
            return {'parse': 0, 'url': url,
                    'header': {'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0'),
                               'Referer': self.host + '/'}}
        if re.search(r'/content/\d+\.html', url):
            vid = re.search(r'/content/(\d+)\.html', url).group(1)
            r = self._request('%s/content/%s.html' % (self.host, vid))
            if r and r.text:
                mu = re.search(r"var\s+mac_url\s*=\s*unescape\('([^']+)'\)", r.text)
                if mu:
                    decoded = unquote(mu.group(1))
                    mm = re.search(r'(https?://[^\s\'"]+\.(?:m3u8|mp4|mpd|flv)[^\s\'"]*)', decoded)
                    if mm:
                        return {'parse': 0, 'url': mm.group(1),
                                'header': {'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0'),
                                           'Referer': self.host + '/'}}
        return {'parse': 1, 'url': url, 'header': {}}


if __name__ == '__main__':
    s = Spider()
    vods = s.categoryContent('15', 1, False, {})
    print('分类15 第1页:', len(vods.get('list', [])), '条 | 总页:', vods.get('pagecount'))
    if vods.get('list'):
        d = s.detailContent([vods['list'][0]['vod_id']])
        print('详情:', d['list'][0]['vod_name'], '|', d['list'][0]['vod_play_url'][:100])
