# -*- coding: utf-8 -*-
import re, json, sys, ssl, base64
from urllib.parse import quote, urlencode
try:
    from base.spider import Spider
except ImportError:
    import requests as rq

    class Spider:
        def fetch(self, url, headers=None, **kw):
            try:
                kw.setdefault('timeout', 15)
                r = rq.get(url, headers=headers, verify=False, **kw)
                r.encoding = 'utf-8'
                return r
            except Exception:
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = __import__('urllib.request', fromlist=['Request', 'urlopen']).Request(url, headers=headers or {})
                    r = __import__('urllib.request', fromlist=['urlopen']).urlopen(req, timeout=15, context=ctx)
                    return type('R', (), {'text': r.read().decode('utf-8', 'ignore'), 'status_code': 200, 'content': b''})()
                except Exception:
                    return None

        def post(self, url, data, headers=None):
            try:
                r = rq.post(url, data=data, headers=headers, timeout=15, verify=False)
                r.encoding = 'utf-8'
                return r
            except Exception:
                try:
                    body = urlencode(data).encode()
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = __import__('urllib.request', fromlist=['Request']).Request(url, data=body, headers=headers or {})
                    r = __import__('urllib.request', fromlist=['urlopen']).urlopen(req, timeout=15, context=ctx)
                    return type('R', (), {'text': r.read().decode('utf-8', 'ignore'), 'status_code': 200, 'content': b''})()
                except Exception:
                    return None


class Spider(Spider):
    # 主域名 lubosp.com, 失效自动切换备用镜像
    hosts = ['https://www.lubosp.com', 'https://www.lookluping.xyz']
    host = 'https://www.lubosp.com'
    header = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    classes = [
        {'type_name': '最新视频', 'type_id': 'new'},
        {'type_name': '热门精选', 'type_id': 'hot'},
        {'type_name': '走光合集', 'type_id': 'zouguang'},
        {'type_name': '免费视频', 'type_id': 'free'},
        {'type_name': '抖音快手', 'type_id': 'type01'},
        {'type_name': '百万粉丝博主', 'type_id': 'type01c02'},
        {'type_name': '十万粉丝博主', 'type_id': 'type01c11'},
        {'type_name': '高颜值女博主', 'type_id': 'type01c12'},
        {'type_name': '会议私播', 'type_id': 'type27'},
        {'type_name': '偷拍系列', 'type_id': 'type28'},
    ]
    # 会员区(封面直链)分类映射: type_id -> 站内栏目路径
    _vip_cats = {
        'type01': 'type01',
        'type01c02': 'type01/column02',
        'type01c11': 'type01/column11',
        'type01c12': 'type01/column12',
        'type27': 'type27',
        'type28': 'toupai/type28',
    }
    # 无分页的分类(站内主栏目无 index_N.html)
    _nopg = {'type01'}
    # 关键词聚合池缓存
    _pool_cache = None
    _pool_time = 0.0

    def getName(self):
        return '直播录屏'

    def init(self, extend=''):
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''
        return {}

    def isVideoFormat(self, url):
        return any(x in url for x in ['.m3u8', '.mp4', '.flv', '.avi', '.mkv'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def post(self, url, data, headers=None):
        try:
            import requests as rq
            r = rq.post(url, data=data, headers=headers, timeout=15, verify=False)
            r.encoding = 'utf-8'
            return r
        except Exception:
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                body = urlencode(data).encode()
                req = __import__('urllib.request', fromlist=['Request']).Request(url, data=body, headers=headers or {})
                r = __import__('urllib.request', fromlist=['urlopen']).urlopen(req, timeout=15, context=ctx)
                return type('R', (), {'text': r.read().decode('utf-8', 'ignore'), 'status_code': 200, 'content': b''})()
            except Exception:
                return None

    def _fetch_html(self, path, data=None):
        # 多域名容灾: 主站失败自动切换备用镜像
        last = ''
        for host in self.hosts:
            url = path if path.startswith('http') else host + path
            try:
                if data is not None:
                    r = self.post(url, data, headers=self.header)
                else:
                    r = self.fetch(url, headers=self.header, timeout=15)
                if not r:
                    continue
                # 兼容 TVBox 基类 fetch 可能直接返回 str/bytes/response 对象
                if isinstance(r, str):
                    t = r
                elif isinstance(r, bytes):
                    t = r.decode('utf-8', 'ignore')
                elif hasattr(r, 'text') and r.text:
                    t = r.text
                else:
                    t = getattr(r, 'content', b'').decode('utf-8', 'ignore')
                try:
                    t = t.encode('latin-1').decode('utf-8')
                except Exception:
                    pass
                if t and len(t) > 500:
                    return t
                last = last or t
            except Exception:
                continue
        return last

    def _wrap_pic(self, pic):
        if not pic:
            return ''
        pic = pic.strip()
        if pic.startswith(('"', "'")) and pic.endswith(('"', "'")):
            pic = pic[1:-1]
        pic = pic.replace('&amp;', '&')
        if '127.0.0.1' in pic or 'proxy' in pic:
            return pic
        if pic.startswith('//'):
            pic = 'https:' + pic
        elif not pic.startswith(('http://', 'https://')):
            pic = (self.host + pic) if pic.startswith('/') else self.host + '/' + pic
        return pic

    def homeContent(self, filter):
        filters = {}
        for c in self.classes:
            filters[c['type_id']] = []
        return {'class': self.classes, 'filters': filters}

    def homeVideoContent(self):
        html = self._fetch_html('/')
        lst = self._vip_items(html)
        if not lst:
            lst = self._items(html)
        return {'list': lst[:48]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)
            if pg < 1:
                pg = 1
            # ---- 特殊聚合分类 ----
            if tid == 'new':
                html = self._fetch_html('/')
                vod_list = self._vip_items(html)[:48] if pg == 1 else []
                return {'page': pg, 'pagecount': 1, 'limit': len(vod_list), 'total': len(vod_list), 'list': vod_list}
            if tid == 'hot':
                vod_list = self._hot_items() if pg == 1 else []
                return {'page': pg, 'pagecount': 1, 'limit': len(vod_list), 'total': len(vod_list), 'list': vod_list}
            if tid == 'zouguang':
                hits = [it for it in self._pool() if '走光' in it['vod_name']]
                pagecount = max(1, (len(hits) + 23) // 24)
                if pg > pagecount:
                    return {'page': pg, 'pagecount': pagecount, 'limit': 24, 'total': len(hits), 'list': []}
                start = (pg - 1) * 24
                return {'page': pg, 'pagecount': pagecount, 'limit': 24, 'total': len(hits), 'list': hits[start:start + 24]}
            # ---- 普通栏目分类 ----
            base = self._vip_cats.get(tid)
            if base:
                url = '/%s/' % base if pg == 1 else '/%s/index_%d.html' % (base, pg)
                html = self._fetch_html(url)
                if not html or '信息提示' in html[:2000]:
                    return {'page': pg, 'pagecount': 1, 'limit': 24, 'total': 0, 'list': []}
                vod_list = self._vip_items(html)
                if not vod_list:
                    return {'page': pg, 'pagecount': 1 if pg == 1 else max(1, pg - 1), 'limit': 24, 'total': 0, 'list': []}
                pagecount = 1 if tid in self._nopg else self._pagecount(html, pg)
                return {'page': pg, 'pagecount': pagecount, 'limit': len(vod_list), 'total': 24 * pagecount, 'list': vod_list}
            url = '/free/' if pg == 1 else '/free/index_%d.html' % pg
            html = self._fetch_html(url)
            if not html or '信息提示' in html[:2000]:
                return {'page': pg, 'pagecount': 1, 'limit': 24, 'total': 0, 'list': []}
            vod_list = self._items(html)
            pagecount = self._pagecount(html, pg)
            return {'page': pg, 'pagecount': pagecount, 'limit': len(vod_list), 'total': 48 * pagecount, 'list': vod_list}
        except Exception:
            return {'page': pg, 'pagecount': 1, 'limit': 24, 'total': 0, 'list': []}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else str(ids)
            if vid.startswith('vip@'):
                return self._vip_detail(vid)
            if vid.isdigit():
                aid = vid
                path = 'free/' + aid
            else:
                aid = re.search(r'(\d+)', vid).group(1) if re.search(r'(\d+)', vid) else vid
                path = vid.strip('/').rstrip('.html')
            html = self._fetch_html('/' + path + '.html')
            if not html or 'buyvideo' not in html:
                return {'list': []}
            vod = {'vod_id': vid}
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            name = m.group(1).strip() if m else re.search(r'<title>([^<]*)</title>', html).group(1).strip()
            vod['vod_name'] = name
            m = re.search(r'<img[^>]+src="([^"]*?/video/[^"]+)"', html)
            if not m:
                m = re.search(r'<img[^>]+src="([^"]+)"', html)
            vod['vod_pic'] = self._wrap_pic(m.group(1) if m else '')
            vod['vod_remarks'] = ''
            vod['vod_actor'] = ''
            vod['vod_director'] = ''
            vod['type_name'] = '免费视频'
            vod['vod_year'] = ''
            vod['vod_area'] = ''
            vod['vod_content'] = name
            b = re.search(r'buyvideo" classid="(\d+)" xxid="(\d+)"', html)
            if not b:
                b = re.search(r'classid="(\d+)"[^>]*xxid="(\d+)"', html)
            cid = b.group(1) if b else '26'
            xid = b.group(2) if b else aid
            vod['vod_play_from'] = '直播录屏'
            vod['vod_play_url'] = self._series_url(name, vid, path, cid, xid)
            return {'list': [vod]}
        except Exception:
            return {'list': []}

    def _series_url(self, name, vid, path, cid, xid):
        mm = re.search(r'^(.*?)\s*\((\d+)\)\s*\.\w+$', name.strip())
        if not mm:
            return '正片$%s' % path
        sn = mm.group(1)
        cur = int(mm.group(2))
        series = {cur: path}
        for p in range(1, 6):
            url = '/free/' if p == 1 else '/free/index_%d.html' % p
            h = self._fetch_html(url)
            if not h or '信息提示' in h[:2000]:
                break
            for it in self._items(h):
                im = re.search(r'^(.*?)\s*\((\d+)\)\s*\.\w+$', it['vod_name'].strip())
                if im and im.group(1) == sn:
                    n = int(im.group(2))
                    if n not in series:
                        series[n] = it['vod_id']
            if len(series) >= 60:
                break
        eps = ['%s$%s' % (('第%d段' % n), p) for n, p in sorted(series.items())]
        return '#'.join(eps) if eps else '正片$%s' % path

    def searchContent(self, key, quick, pg=1):
        try:
            raw = str(key)
            items = []
            seen = set()
            for p in range(1, 6):
                url = '/free/' if p == 1 else '/free/index_%d.html' % p
                html = self._fetch_html(url)
                if not html:
                    continue
                if '信息提示' in html[:2000]:
                    break
                for it in self._items(html):
                    if raw.lower() not in it['vod_name'].lower():
                        continue
                    if it['vod_id'] in seen:
                        continue
                    seen.add(it['vod_id'])
                    items.append(it)
                if len(items) >= 80:
                    break
            # 会员区各分类(含抖音快手子栏目)一并搜索(封面直链项)
            if len(items) < 80:
                for base in ('type01', 'type01/column02', 'type01/column11', 'type01/column12', 'type27', 'toupai/type28'):
                    h = self._fetch_html('/' + base + '/')
                    if not h or '信息提示' in h[:2000]:
                        continue
                    for it in self._vip_items(h):
                        if raw.lower() not in it['vod_name'].lower():
                            continue
                        if it['vod_id'] in seen:
                            continue
                        seen.add(it['vod_id'])
                        items.append(it)
                    if len(items) >= 80:
                        break
            return {'list': items[:80], 'page': 1}
        except Exception:
            return {'list': [], 'page': 1}

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        try:
            vid = str(id)
            if vid.startswith('vip@'):
                # 会员区封面直链: vod.jpg -> index.m3u8, 失效时降级走详情页解析
                try:
                    m3u8, path, _name = self._decode_vip(vid)
                except Exception:
                    return {}
                if m3u8 and '.m3u8' in m3u8:
                    return {'parse': 0, 'url': m3u8, 'header': {'Referer': self.host + '/', 'User-Agent': self.header['User-Agent']}}
                if path:
                    vid = path
                else:
                    return {}
            if vid.isdigit():
                aid = vid
                path = 'free/' + aid
            else:
                aid = re.search(r'(\d+)', vid).group(1) if re.search(r'(\d+)', vid) else vid
                path = vid.strip('/').rstrip('.html')
            if not aid:
                return {}
            html = self._fetch_html('/' + path + '.html')
            if not html or 'buyvideo' not in html:
                return {}
            b = re.search(r'buyvideo" classid="(\d+)" xxid="(\d+)"', html)
            if not b:
                b = re.search(r'classid="(\d+)"[^>]*xxid="(\d+)"', html)
            cid = b.group(1) if b else '26'
            xid = b.group(2) if b else aid
            r = self._fetch_html('/e/moyublog/bofang/', {'id': xid, 'classid': cid})
            if not r:
                return {}
            try:
                obj = json.loads(r)
                nr = obj.get('nr', '') or ''
            except Exception:
                nr = r
            m = re.search(r'url:\s*["\']([^"\']+)["\']', nr)
            if m:
                return {'parse': 0, 'url': m.group(1).replace('\\/', '/'), 'header': {'Referer': self.host + '/', 'User-Agent': self.header['User-Agent']}}
            m = re.search(r'src\s*=\s*["\']?\s*\\?(/e/DownSys/play/[^"\']+)', nr)
            u = m.group(1).replace('\\/', '/').replace(' ', '') if m else ''
            if u.startswith('/'):
                u = self.host + u
            if not u:
                return {}
            fr = self._fetch_html(u)
            if not fr:
                return {}
            m = re.search(r'url:\s*["\']([^"\']+)["\']', fr)
            if not m:
                return {}
            return {'parse': 0, 'url': m.group(1).replace('\\/', '/'), 'header': {'Referer': self.host + '/', 'User-Agent': self.header['User-Agent']}}
        except Exception:
            return {}

    def localProxy(self, param):
        return []

    def _pagecount(self, html, pn=1):
        pages = [int(x) for x in re.findall(r'index_(\d+)\.html', html)]
        if pages:
            return max(pages)
        return pn + 5 if '下一页' in html or 'index_%d.html' % (pn + 1) in html else pn

    def _items(self, html):
        items = []
        seen = set()
        for m in re.finditer(r'<a href="([^"]*?/(\d+)\.html)"([^>]*)>(.*?)</a>', html, re.S):
            vid = m.group(2)
            path = m.group(1).strip('/')
            if not path.startswith('free/'):
                continue
            if vid in seen:
                continue
            t = re.search(r'title="([^"]*)"', m.group(3))
            name = t.group(1).strip() if t else re.sub(r'<[^>]+>', '', m.group(4)).strip()
            if not name or len(name) > 100:
                continue
            seen.add(vid)
            after = html[m.end():m.end() + 800]
            img = re.search(r'<img[^>]+(?:data-original|original|src)="([^"]+)"', after)
            pic = self._wrap_pic(img.group(1) if img else '')
            items.append({'vod_id': path, 'vod_name': name[:50], 'vod_pic': pic, 'vod_remarks': ''})
        return items

    # ---------- 会员区(封面直链)支持: 移植自 JS 规则 ----------
    # JS 原型: pdfa(h,'ul,4&&li') -> pdfh(li,'h2&&Text')标题 / pdfh(li,'img&&src')封面
    #          url = img.replace('vod.jpg','index.m3u8')
    def _vip_items(self, html):
        items = []
        seen = set()
        if not html:
            return items
        for m in re.finditer(r'<li[^>]*>.*?</li>', html, re.S):
            li = m.group(0)
            im = re.search(r'<img[^>]+(?:data-original|src)="([^"]+)"', li)
            if not im or 'vod.jpg' not in im.group(1):
                continue
            pic = im.group(1).replace('&amp;', '&').strip()
            if pic in seen:
                continue
            hm = re.search(r'<h2[^>]*>(.*?)</h2>', li, re.S)
            if hm:
                name = re.sub(r'<[^>]+>', '', hm.group(1)).strip()
            else:
                tm = re.search(r'<a[^>]+title="([^"]*)"', li) or re.search(r'<img[^>]+alt="([^"]*)"', li)
                name = tm.group(1).strip() if tm else ''
            if not name or len(name) > 100:
                continue
            am = re.search(r'<a[^>]+href="([^"]+\.html)"', li)
            path = am.group(1).strip('/').split('?')[0] if am else ''
            if path.endswith('.html'):
                path = path[:-5]
            if not path.startswith(('free/', 'type', 'toupai/')):
                path = ''
            m3u8 = pic.replace('vod.jpg', 'index.m3u8')
            rm = re.search(r'ico-left[^>]*>([^<]+)<', li)
            remarks = rm.group(1).strip() if rm else ''
            seen.add(pic)
            items.append({'vod_id': self._encode_vip(m3u8, path, name), 'vod_name': name[:50], 'vod_pic': pic, 'vod_remarks': remarks})
        return items

    def _encode_vip(self, m3u8, path, name):
        raw = '%s|%s|%s' % (m3u8, path, name or '')
        return 'vip@' + base64.urlsafe_b64encode(raw.encode('utf-8')).decode()

    def _hot_items(self, html=None):
        # 首页"热门精选"tab(class=hide)里的跨分类精选列表
        h = self._fetch_html('/')
        if not h:
            return []
        m = re.search(r'<div class="hide">\s*<ul[^>]*>(.*?)</ul>', h, re.S)
        if not m:
            m = re.search(r'class="hide"[^>]*>\s*<ul[^>]*>(.*?)</ul>', h, re.S)
        if not m:
            return []
        return self._vip_items(m.group(1))

    def _pool(self, pages=3):
        # 全站栏目聚合池(关键词分类用), 30分钟缓存避免重复抓取
        import time as _time
        now = _time.time()
        if self._pool_cache and now - self._pool_time < 1800:
            return self._pool_cache
        pool = []
        seen = set()
        for base in ('type01', 'type01/column02', 'type01/column11', 'type01/column12', 'type27', 'toupai/type28', 'free'):
            for pg in range(1, pages + 1):
                url = '/%s/' % base if pg == 1 else '/%s/index_%d.html' % (base, pg)
                html = self._fetch_html(url)
                if not html or '信息提示' in html[:2000]:
                    break
                items = self._vip_items(html)
                if not items:
                    break
                for it in items:
                    if it['vod_id'] not in seen:
                        seen.add(it['vod_id'])
                        pool.append(it)
        if pool:
            self._pool_cache = pool
            self._pool_time = now
        return pool or []

    def _decode_vip(self, vid):
        raw = base64.urlsafe_b64decode(vid[4:].encode('utf-8')).decode('utf-8', 'ignore')
        parts = raw.split('|')
        m3u8 = parts[0] if parts else ''
        path = parts[1] if len(parts) > 1 else ''
        name = parts[2] if len(parts) > 2 else ''
        return m3u8, path, name

    def _vip_detail(self, vid):
        try:
            m3u8, path, name = self._decode_vip(vid)
            vod = {'vod_id': vid, 'vod_name': name or '会员视频', 'vod_pic': '', 'vod_remarks': '',
                   'vod_actor': '', 'vod_director': '', 'type_name': '会员视频',
                   'vod_year': '', 'vod_area': '', 'vod_content': name,
                   'vod_play_from': '直播录屏', 'vod_play_url': '正片$' + vid}
            if path:
                html = self._fetch_html('/' + path + '.html')
                if html:
                    hm = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
                    if hm and hm.group(1).strip():
                        vod['vod_name'] = hm.group(1).strip()
                    pm = re.search(r'<img[^>]+src="([^"]*?/video/[^"]+)"', html) or re.search(r'<img[^>]+src="([^"]+)"', html)
                    if pm:
                        vod['vod_pic'] = self._wrap_pic(pm.group(1))
            if not vod['vod_pic'] and m3u8:
                vod['vod_pic'] = m3u8.replace('index.m3u8', 'vod.jpg')
            return {'list': [vod]}
        except Exception:
            return {'list': []}