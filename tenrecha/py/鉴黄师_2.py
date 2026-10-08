# -*- coding: utf-8 -*-
import sys, re, json, time, base64, html as H, http.client, ssl, http.cookiejar
import urllib.request as ur
from urllib.parse import quote, unquote, urljoin, parse_qs
sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def fetch(self, url, headers=None, timeout=10): return ''
try:
    import requests
    from requests.adapters import HTTPAdapter
    HAS_REQ = True
except Exception:
    HAS_REQ = False
try:
    from urllib3.util.ssl_ import create_urllib3_context
    HAS_U3 = True
except Exception:
    HAS_U3 = False

CIP = 'DEFAULT:!aNULL:!eNULL:!MD5:!3DES:!DES:!RC4:!IDEA:!SEED:!aDSS:!SRP:!PSK'

class CFAdapter(HTTPAdapter):
    def init_poolmanager(self, *a, **kw):
        if HAS_U3:
            try:
                ctx = create_urllib3_context(ciphers=CIP)
                try:
                    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                except Exception:
                    pass
                try:
                    ctx.set_alpn_protocols(['http/1.1'])
                except Exception:
                    pass
                try:
                    ctx.options |= ssl.OP_NO_COMPRESSION
                except Exception:
                    pass
                for curve in ('X25519', 'prime256v1'):
                    try:
                        ctx.set_ecdh_curve(curve)
                        break
                    except Exception:
                        continue
                kw['ssl_context'] = ctx
            except Exception:
                pass
        super(CFAdapter, self).init_poolmanager(*a, **kw)

SITE = 'https://www.javrate.com'
HOSTS = [SITE]
REFERER = SITE + '/'
MAX_PAGE = 500
UA_D = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
UA_M = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
UA_A = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
CATS = [
    ['/movie/new', '最新更新'], ['/menu/uncensored', '无码A片'], ['/menu/censored', '日本A片'],
    ['/menu/chinese', '国产AV'], ['/movie/subtitle', '中文字幕'], ['/best', '最多人看'],
]

# ===== 增量 1: 女优分类 =====
ACTOR_CATS = [
    ['/actor/list/1-0-1.html', '全部女优'], ['/actor/list/1-1-1.html', '知名女优'],
    ['/actor/list/1-2-1.html', '无码女优'], ['/actor/list/1-3-1.html', '日本女优'],
    ['/actor/list/1-4-1.html', '国产女优'], ['/actor/list/1-5-1.html', '素人女优'],
]

class Spider(Spider):
    def init(self, extend=''):
        self._jar = http.cookiejar.CookieJar()
        self._opener = ur.build_opener(ur.HTTPCookieProcessor(self._jar))
        self._tpl = {}
        self._ctx = None
        self._sess = None
        self._dc = {}
        return ''

    def _session(self):
        if self._sess is None and HAS_REQ:
            s = requests.Session()
            s.headers.clear()
            s.mount('https://', CFAdapter())
            self._sess = s
        return self._sess

    def _build_ctx(self):
        if self._ctx:
            return self._ctx
        ctx = ssl.create_default_context()
        try:
            ctx.set_ciphers(CIP)
        except Exception:
            pass
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        except Exception:
            pass
        try:
            ctx.set_alpn_protocols(['http/1.1'])
        except Exception:
            pass
        try:
            ctx.options |= ssl.OP_NO_COMPRESSION
        except Exception:
            pass
        for curve in ('X25519', 'prime256v1'):
            try:
                ctx.set_ecdh_curve(curve)
                break
            except Exception:
                continue
        self._ctx = ctx
        return ctx

    def _chall(self, b):
        head = b[:1500]
        return any(x in head for x in (b'Just a moment', b'cf-chl', b'challenges.cloudflare', b'cf-mitigated'))

    def _httpclient(self, url, hd):
        try:
            p = url.split('://', 1)[1]
            host, path = p.split('/', 1)
            c = http.client.HTTPSConnection(host, timeout=15, context=self._build_ctx())
            h2 = dict(hd)
            ck = '; '.join('%s=%s' % (x.name, x.value) for x in self._jar)
            if ck:
                h2['Cookie'] = ck
            c.request('GET', '/' + path, headers=h2)
            r = c.getresponse()
            b = r.read()
            c.close()
            return b
        except Exception:
            return b''

    def _urllib(self, url, hd):
        try:
            req = ur.Request(url, headers=hd)
            return self._opener.open(req, timeout=15).read()
        except Exception:
            return b''

    def _fetch(self, url, ref=None):
        ref = ref or REFERER
        if HAS_REQ:
            try:
                s = self._session()
                r = s.get(url, headers={'User-Agent': UA_D, 'Referer': ref, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'zh-CN,zh;q=0.9', 'Upgrade-Insecure-Requests': '1'}, timeout=15)
                b = r.content
                if b and not self._chall(b):
                    return b
            except Exception:
                pass
        for hd in ({'User-Agent': UA_D, 'Referer': ref, 'Accept-Encoding': 'identity', 'Connection': 'close', 'Upgrade-Insecure-Requests': '1', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'zh-CN,zh;q=0.9'},
                   {'User-Agent': UA_M, 'Referer': ref, 'Accept-Encoding': 'identity', 'Connection': 'close'},
                   {'User-Agent': UA_A, 'Referer': ref, 'Accept-Encoding': 'identity', 'Connection': 'close'}):
            b = self._httpclient(url, hd)
            if b and not self._chall(b):
                return b
        for hd in ({'User-Agent': UA_D, 'Referer': ref},
                   {'User-Agent': UA_M, 'Referer': ref, 'Accept-Language': 'zh-TW,zh;q=0.9'},
                   {'User-Agent': UA_A, 'Referer': ref}):
            b = self._urllib(url, hd)
            if b and not self._chall(b):
                return b
        return b''

    def _html(self, url):
        b = self._fetch(url)
        return b.decode('utf-8', 'replace') if b else ''

    def _cards(self, html):
        out = []
        for m in re.finditer(r'<div class="mgn-item"', html):
            s = m.start()
            e = html.find('<div class="mgn-item"', s + 10)
            b = html[s:e if e > 0 else s + 4000]
            a = re.search(r'<a href="(/movie/detail/([a-f0-9\-]+)\.html)"[^>]*title="([^"]*)"', b)
            if not a:
                continue
            img = re.search(r'<img[^>]+src="([^"]+)"', b)
            pic = img.group(1) if img else ''
            if pic.startswith('//'):
                pic = 'https:' + pic
            remark = ''
            y = re.search(r'mgn-badge-year[^>]*>([^<]+)', b)
            if y:
                remark = H.unescape(y.group(1)).strip()
            tg = re.search(r'mgn-badge-subtitle[^>]*>([^<]+)', b)
            if tg:
                remark = (remark + ' ' if remark else '') + H.unescape(tg.group(1)).strip()
            act = [H.unescape(x).strip() for x in re.findall(r'mgn-actress[^>]*>\s*<a[^>]*>([^<]+)', b)][:8]
            out.append({'vod_id': a.group(2), 'vod_name': H.unescape(a.group(3)).strip(), 'vod_pic': pic,
                        'vod_actor': ','.join(x for x in act if x), 'vod_remarks': remark})
        return out

    # ===== 增量 2: 女优列表解析 =====
    def _actor_cards(self, html):
        out = []
        for m in re.finditer(r'<div class="actor-card"', html):
            s = m.start()
            e = html.find('<div class="actor-card"', s + 10)
            if e < 0:
                e = html.find('<div class="ads-box"', s + 10)
            if e < 0:
                e = s + 5000
            b = html[s:e]
            a = re.search(r'<a href="(/actor/detail/([a-f0-9\-]+)\.html)"[^>]*title="([^"]*)"', b)
            if not a:
                continue
            img = re.search(r'<img[^>]+src="([^"]+)"', b)
            pic = img.group(1) if img else ''
            if pic.startswith('//'):
                pic = 'https:' + pic
            remark = ''
            r = re.search(r'<div class="right">\s*([^<]+)', b)
            if r:
                remark = H.unescape(r.group(1)).strip()
            name = H.unescape(a.group(3)).strip()
            out.append({'vod_id': SITE + a.group(1), 'vod_name': name, 'vod_pic': pic,
                        'vod_actor': '', 'vod_remarks': remark})
        return out

    def _page_tpl(self, html):
        # ===== 增量 3: 女优分页格式 /actor/list/1-0-2.html =====
        m = re.search(r'href="(/actor/list/\d+-\d+-)(\d+)(\.html)"', html)
        if m:
            return m.group(1) + '{page}' + m.group(3)
        m = re.search(r'href="([^"]*?/)(\d+)-(\d+)-(\d+)/?"', html)
        if m:
            return m.group(1) + '{page}-' + m.group(3) + '-' + m.group(4) + '/'
        m = re.search(r'href="([^"]*?page=)\d+', html)
        if m:
            return m.group(1) + '{page}'
        m = re.search(r'href="([^"]*?/)(\d+)([^0-9][^"]*)"', html)
        if m:
            return m.group(1) + '{page}' + m.group(3)
        return ''

    def homeContent(self, filter=False):
        h = self._html(SITE + '/')
        # ===== 增量 4: 首页分类追加女优 =====
        return {'class': [{'type_id': c[0], 'type_name': c[1]} for c in CATS + ACTOR_CATS], 'list': self._cards(h)[:30]}

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter=False, extend=''):
        try:
            p = int(pg)
        except Exception:
            p = 1
        if p <= 1:
            url = SITE + tid
            h = ''
        else:
            tpl = self._tpl.get(tid) or ''
            if not tpl:
                h0 = self._html(SITE + tid)
                tpl = self._page_tpl(h0)
                self._tpl[tid] = tpl
                h = h0
            else:
                h = ''
            if tpl:
                url = SITE + tpl.replace('{page}', str(p))
            else:
                if '/actor/' in tid:
                    url = SITE + re.sub(r'-\d+\.html$', '-' + str(p) + '.html', tid)
                else:
                    url = SITE + tid + '/' + str(p) + '-2-1/'
        h = h or self._html(url)
        # ===== 增量 5: 女优列表分支 =====
        if '/actor/' in tid:
            ls = self._actor_cards(h)
        else:
            ls = self._cards(h)
        total = 0
        dm = re.search(r'data-page-info="([^"]*)"', h)
        if dm:
            mm = re.search(r'共\s*(\d+)\s*頁', H.unescape(dm.group(1)))
            if mm:
                total = int(mm.group(1))
        return {'list': ls, 'page': p, 'pagecount': min(total or 1, MAX_PAGE), 'total': total * 30 if total else len(ls)}

    def _dh(self, vid):
        now = time.time()
        c = self._dc.get(vid)
        if c and now - c[0] < 300:
            return c[1]
        h = self._html(SITE + '/movie/detail/' + str(vid) + '.html')
        self._dc[vid] = (now, h)
        return h

    def detailContent(self, ids, quick='1'):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        # ===== 增量 6: 女优详情页分支（解析该女优的影片列表） =====
        if '/actor/detail/' in str(vid):
            url = str(vid) if str(vid).startswith('http') else SITE + str(vid)
            h = self._html(url)
            if not h:
                return {'list': []}
            t = re.search(r'<title>([^<]+)</title>', h)
            name = H.unescape(t.group(1)).split('|')[0].strip() if t else str(vid)
            pic = ''
            m = re.search(r'property="og:image"[^>]+content="([^"]+)"', h) or re.search(r'content="([^"]+)"[^>]+property="og:image"', h)
            if m:
                pic = m.group(1)
            act = [H.unescape(x).strip() for x in re.findall(r'(?:actor-name|actress-link)[^>]*>\s*<a[^>]*>([^<]+)', h)][:8]
            ls = self._cards(h)
            pl = []
            for v in ls[:200]:
                pl.append(v['vod_name'] + '$' + v['vod_id'])
            vod = {'vod_id': vid, 'vod_name': name, 'vod_pic': pic, 'vod_actor': ','.join(x for x in act if x),
                   'vod_content': '', 'vod_remarks': 'Javrate',
                   'vod_play_from': 'Javrate', 'vod_play_url': '#'.join(pl) if pl else '暂无影片$' + url}
            return {'list': [vod]}
        url = str(vid) if str(vid).startswith('http') else SITE + '/movie/detail/' + str(vid) + '.html'
        if str(vid).startswith('http'):
            h = self._html(str(vid))
        else:
            h = self._dh(str(vid))
        if not h:
            return {'list': []}
        t = re.search(r'<title>([^<]+)</title>', h)
        name = H.unescape(t.group(1)).split('|')[0].strip() if t else str(vid)
        pic = ''
        m = re.search(r'property="og:image"[^>]+content="([^"]+)"', h) or re.search(r'content="([^"]+)"[^>]+property="og:image"', h)
        if m:
            pic = m.group(1)
        desc = ''
        dm = re.search(r'name="description"[^>]+content="([^"]+)"', h)
        if dm:
            desc = H.unescape(dm.group(1)).strip()
        act = [H.unescape(x).strip() for x in re.findall(r'(?:actor-name|actress-link)[^>]*>\s*<a[^>]*>([^<]+)', h)][:8]
        vod = {'vod_id': vid, 'vod_name': name, 'vod_pic': pic, 'vod_actor': ','.join(x for x in act if x),
               'vod_content': desc, 'vod_remarks': 'Javrate',
               'vod_play_from': 'Javrate', 'vod_play_url': '第1集$' + url}
        return {'list': [vod]}

    def searchContent(self, key, quick=False, pg='1'):
        if not key:
            return {'list': []}
        h = self._html(SITE + '/search/' + quote(key))
        return {'list': self._cards(h)[:40], 'page': 1}

    def searchContentPage(self, key, quick, pg='1'):
        return self.searchContent(key, quick, pg)

    def _resolve_source(self, detail_url):
        vid = detail_url.rsplit('/', 1)[-1].replace('.html', '')
        h = self._dh(vid)
        m = re.search(r'"embedUrl":\s*"([^"]+)"', h)
        if not m:
            m = re.search(r'<iframe[^>]+src="([^"]+)"', h)
        if not m:
            return ''
        embed = m.group(1)
        if embed.startswith('/'):
            embed = urljoin(SITE, embed)
        p = self._html(embed)
        m2 = re.search(r'var\s+source\s*=\s*"([^"]+)"', p)
        if m2:
            src = m2.group(1)
            if src.startswith('//'):
                src = 'https:' + src
            return src
        m3 = re.search(r'var\s+now\s*=\s*"([^"]+)"', p)
        return m3.group(1) if m3 else ''

    def playerContent(self, flag, id, vipFlags=None):
        detail_url = id if id.startswith('http') else SITE + '/movie/detail/' + str(id) + '.html'
        src = self._resolve_source(detail_url)
        if not src:
            return {'parse': 0, 'url': '', 'msg': '播放源获取失败'}
        key = base64.urlsafe_b64encode(src.encode()).decode().rstrip('=') + '|' + detail_url
        return {'parse': 0, 'url': 'http://127.0.0.1:9978/proxy?do=py&key=' + key, 'header': {'User-Agent': UA_D}}

    def _proxy_url(self, key, extra=''):
        return 'http://127.0.0.1:9978/proxy?do=py&key=' + key + extra

    def _g(self, p, n):
        v = p.get(n) or ''
        return v[0] if isinstance(v, list) else v

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                p = param
            else:
                q = param.split('?', 1)[-1]
                p = parse_qs(q) if '=' in q else {'key': [param]}
            key = unquote(self._g(p, 'key'))
            if not key:
                return [404, 'text/plain', '']
            k, _, detail = key.partition('|')
            src = base64.urlsafe_b64decode(k.encode() + b'=' * (-len(k) % 4)).decode()
            base = src.rsplit('/', 1)[0] + '/'
            query = src.split('?', 1)[1] if '?' in src else ''
            seg = unquote(self._g(p, 'seg'))
            if seg:
                vb64 = self._g(p, 'vbase')
                vb = base64.urlsafe_b64decode(unquote(vb64).encode() + b'=' * (-len(unquote(vb64)) % 4)).decode() if vb64 else base
                tu = seg if seg.startswith('http') else urljoin(vb, seg)
                if query:
                    tu += ('&' if '?' in tu else '?') + query
                b = self._fetch(tu, ref=SITE + '/')
                return [200, 'video/mp2t', b] if b else [404, 'text/plain', '']
            vpath = unquote(self._g(p, 'vpath'))
            if vpath:
                vu = urljoin(base, vpath)
                if query:
                    vu += '?' + query
                b = self._fetch(vu, ref=SITE + '/')
                if not b:
                    return [404, 'text/plain', '']
                vbase2 = vu.rsplit('/', 1)[0] + '/'
                vb64 = base64.urlsafe_b64encode(vbase2.encode()).decode().rstrip('=')
                out = []
                for line in b.decode('utf-8', 'replace').splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('http'):
                        out.append(self._proxy_url(key, '&seg=' + quote(line, safe='') + '&vbase=' + quote(vb64, safe='')))
                    else:
                        out.append(line)
                return [200, 'application/vnd.apple.mpegurl', '\n'.join(out).encode()]
            b = self._fetch(src, ref=SITE + '/')
            if not b and detail:
                src2 = self._resolve_source(detail)
                if src2:
                    b = self._fetch(src2, ref=SITE + '/')
                    src = src2
            if not b:
                return [404, 'text/plain', '']
            key = base64.urlsafe_b64encode(src.encode()).decode().rstrip('=') + '|' + detail
            out = []
            ninf = 0
            for line in b.decode('utf-8', 'replace').splitlines():
                line = line.strip()
                if line.startswith('#EXT-X-STREAM-INF'):
                    ninf += 1
                    out.append(line)
                elif line and not line.startswith('#') and not line.startswith('http'):
                    u = self._proxy_url(key, '&vpath=' + quote(line, safe=''))
                    out.extend([u] * max(ninf, 1))
                    ninf = 0
                else:
                    out.append(line)
            return [200, 'application/vnd.apple.mpegurl', '\n'.join(out).encode()]
        except Exception:
            return [404, 'text/plain', '']
