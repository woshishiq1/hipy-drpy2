"""
@header({
  searchable: 1,
  filterable: 0,
  quickSearch: 1,
  title: 'MSAVX',
  lang: 'hipy',
})
"""

import re
import json
import html
from urllib.parse import urljoin, quote, unquote, unquote_plus

try:
    import requests
except Exception:
    requests = None

from base.spider import Spider


class Spider(Spider):
    host = 'http://transwww.marcelf.com'
    ua = 'Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
    site = host + '/cn/'

    def __init__(self, *args, **kwargs):
        self.extend = ''
        self.s = requests.Session() if requests else None
        if self.s:
            self.s.headers.update({'User-Agent': self.ua, 'Referer': self.site})
            self.s.cookies.set('ym_iscookie', '1', domain='transwww.marcelf.com', path='/')
            self.s.cookies.set('ym_show_number7338', '1', domain='transwww.marcelf.com', path='/')
            self.s.cookies.set('_slide_passed', '1', domain='transwww.marcelf.com', path='/')
            self.s.cookies.set('ad_index', '1', domain='transwww.marcelf.com', path='/')

    def init(self, extend=''):
        self.extend = extend
        return '{}'

    def getName(self):
        return 'MSAVX'

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.s:
            self.s.close()

    def _headers(self, referer=None):
        return {'User-Agent': self.ua, 'Referer': referer or self.site}

    def _get(self, url, referer=None):
        if self.s:
            r = self.s.get(url, headers=self._headers(referer), timeout=20)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r.text
        from urllib.request import Request, urlopen
        return urlopen(Request(url, headers=self._headers(referer)), timeout=20).read().decode('utf-8', 'ignore')

    def _clean(self, s):
        return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()

    def _href(self, h):
        return urljoin(self.host, html.unescape((h or '').replace('\\/', '/')))

    def _decode_html(self, text):
        m = re.search(r'"([0-9a-fA-F]{1000,})"', text)
        if m:
            try:
                return bytes.fromhex(m.group(1)).decode('utf-8', 'ignore')
            except Exception:
                pass
        return text

    def _title_from_script(self, text):
        m = re.search(r'window\.videoConfig\s*=\s*\{.*?title:\s*"([^"]+)"', text, re.S)
        return self._clean(m.group(1)) if m else ''

    def _img_from_script(self, text):
        m = re.search(r'window\.videoConfig\s*=\s*\{.*?img:\s*"([^"]+)"', text, re.S)
        return self._href(m.group(1)) if m else ''

    def _video_url_from_script(self, text):
        m = re.search(r'window\.videoConfig\s*=\s*\{.*?url:\s*"([^"]+)"', text, re.S)
        return self._href(m.group(1)) if m else ''

    def _search_page(self, text):
        out, seen = [], set()
        for m in re.finditer(r'<div[^>]+class=["\'][^"\']*video-preview-trigger[^"\']*["\'].*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>.*?<img[^>]+src=["\']([^"\']+)["\'][^>]*>.*?</div>.*?<a[^>]*>(.*?)</a>', text, re.I | re.S):
            u = self._href(m.group(1))
            if u in seen:
                continue
            title = self._clean(m.group(3))
            if not title:
                title = unquote(u.rstrip('/').split('/')[-1])
            out.append({'vod_id': u, 'vod_name': title, 'vod_pic': self._href(m.group(2)), 'vod_remarks': ''})
            seen.add(u)
        if out:
            return out
        for m in re.finditer(r'<a[^>]+href=["\']([^"\']+/cn/[^"\']+)["\'][^>]*class=["\'][^"\']*video-preview-trigger[^"\']*["\'][^>]*>.*?<img[^>]+src=["\']([^"\']+)["\']', text, re.I | re.S):
            u = self._href(m.group(1))
            if u in seen:
                continue
            title = unquote(u.rstrip('/').split('/')[-1])
            out.append({'vod_id': u, 'vod_name': title, 'vod_pic': self._href(m.group(2)), 'vod_remarks': ''})
            seen.add(u)
        return out

    def _actress_items(self, text):
        out, seen = [], set()
        for m in re.finditer(r'<a[^>]+href=["\']([^"\']*/cn/actresses/[^"\']+)["\'][^>]*>(.*?)</a>', text, re.I | re.S):
            u = self._href(m.group(1))
            if u in seen:
                continue
            name = self._clean(m.group(2))
            if not name:
                name = unquote(u.rstrip('/').split('/')[-1])
            pic = ''
            block = m.group(0)
            im = re.search(r'<img[^>]+src=["\']([^"\']+)', block, re.I)
            if im:
                pic = self._href(im.group(1))
            out.append({'vod_id': 'folder_' + u, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': '目录', 'vod_tag': 'folder'})
            seen.add(u)
        return out

    def _folder_links(self, text, kind):
        out, seen = [], set()
        pat = r'<a[^>]+href=["\']([^"\']*/cn/' + kind + r'/[^"\']+)["\'][^>]*>(.*?)</a>'
        for m in re.finditer(pat, text, re.I | re.S):
            u = self._href(m.group(1))
            if u in seen:
                continue
            name = self._clean(m.group(2))
            if not name or re.search(r'\d+\s*条影片', name):
                continue
            if name in {'VR', '欧美大片'} and kind == 'genres':
                pass
            pic = ''
            block = m.group(0)
            im = re.search(r'<img[^>]+src=["\']([^"\']+)', block, re.I)
            if im:
                pic = self._href(im.group(1))
            out.append({'vod_id': 'folder_' + u, 'vod_name': name, 'vod_pic': pic, 'vod_remarks': '目录', 'vod_tag': 'folder'})
            seen.add(u)
        return out

    def _cats(self):
        t = self._decode_html(self._get(self.site, self.site))
        cats, seen = [], set()
        nav_blocks = re.findall(r'<div[^>]+class=["\'][^"\']*(?:dropdown-menu|flex flex-col|hidden xl:flex)[^"\']*["\'][^>]*>(.*?)</div>', t, re.I | re.S)
        text = '\n'.join(nav_blocks) if nav_blocks else t
        skip = {'首页', '登录', '注册', '会员', '充值', 'APP', '下载', '搜索', '排行', '最新', '热门', '专题', '资讯', '留言', '求片', '更多', '观看日本AV', '观看AV', '我的收藏', '我的影片收藏', '我的片单', '我的女优收藏', '观看记录'}
        for m in re.finditer(r'<a[^>]+href=["\']([^"\']*/(?:cn|dm\d+)/[^"\']*)["\'][^>]*>(.*?)</a>', text, re.I | re.S):
            u = self._href(m.group(1))
            name = self._clean(m.group(2))
            if not name or name in skip or u in seen:
                continue
            if '/user/' in u or 'javascript:' in u:
                continue
            cats.append({'type_id': u, 'type_name': name})
            seen.add(u)
        return cats

    def homeContent(self, filter=False):
        cats = []
        for c in self._cats():
            if c['type_name'] == '女优一览':
                cats.append({'type_id': 'folder_' + self._href('/cn/actresses'), 'type_name': '女优一览', 'vod_tag': 'folder'})
                continue
            if c['type_name'] == '类型':
                cats.append({'type_id': 'folder_' + self._href('/cn/genres'), 'type_name': '类型', 'vod_tag': 'folder'})
                continue
            if c['type_name'] == '发行商':
                cats.append({'type_id': 'folder_' + self._href('/cn/makers'), 'type_name': '发行商', 'vod_tag': 'folder'})
                continue
            try:
                r = self.categoryContent(c['type_id'], 1, False, {})
                if r.get('list'):
                    cats.append(c)
            except Exception:
                pass
        return {'class': cats, 'filters': {}}

    def homeVideoContent(self):
        text = self._decode_html(self._get(self.site, self.site))
        out = self._search_page(text)
        if out:
            return {'list': out}
        out = []
        seen = set()
        for m in re.finditer(r"<div[^>]+class=['\"][^'\"]*(?:video-preview-trigger|thumbnail)[^'\"]*['\"].*?<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>.*?<img[^>]+src=['\"]([^'\"]+)['\"][^>]*>.*?</div>.*?<a[^>]*>(.*?)</a>", text, re.I | re.S):
            u = self._href(m.group(1))
            if u in seen:
                continue
            title = self._clean(m.group(3))
            if not title:
                title = unquote(u.rstrip('/').split('/')[-1])
            out.append({'vod_id': u, 'vod_name': title, 'vod_pic': self._href(m.group(2)), 'vod_remarks': ''})
            seen.add(u)
        return {'list': out}

    def categoryContent(self, tid, pg=1, filter=False, extend=None):
        if str(tid).startswith('folder_'):
            u = str(tid)[7:]
            if re.search(r'/cn/actresses/[^/?#]+/?$', u):
                base = u.rstrip('/')
                u = base + '?sort=published_at&page=' + str(pg)
            else:
                if str(pg) != '1':
                    u += ('&' if '?' in u else '?') + 'page=' + str(pg)
            text = self._decode_html(self._get(u, u))
            total = 0
            m = re.search(r'\.\$\("mac_total"\)\.text\(["\'](\d+)["\']\)', text, re.I)
            if m:
                total = int(m.group(1))
            root_u = u.split('?', 1)[0].rstrip('/')
            if re.search(r'/cn/actresses/?$', root_u):
                items = self._actress_items(text)
            elif re.search(r'/cn/genres/?$', root_u):
                items = self._folder_links(text, 'genres')
            elif re.search(r'/cn/makers/?$', root_u):
                items = self._folder_links(text, 'makers')
            else:
                items = self._search_page(text)
            next_link = re.search(r'href=["\']([^"\']*[?&]page=' + str(int(pg)+1) + r'[^"\']*)["\'][^>]*>\s*下一页', text, re.I)
            pc = int(pg) + 1 if next_link else int(pg)
            if not next_link and len(items) >= 20:
                pc = int(pg) + 1
            return {'page': int(pg), 'pagecount': pc, 'limit': len(items), 'total': total, 'list': items}
        u = tid if str(tid).startswith('http') else self._href(str(tid))
        if str(pg) != '1':
            if '?page=' in u:
                u = re.sub(r'([?&]page=)\d+', r'\g<1>' + str(pg), u)
            elif '?' in u:
                u = u + '&page=' + str(pg)
            else:
                u = u.rstrip('/') + '?page=' + str(pg)
        text = self._decode_html(self._get(u, self.site))
        items = self._search_page(text)
        total = 0
        m = re.search(r'\.\$\("mac_total"\)\.text\(["\'](\d+)["\']\)', text, re.I)
        if m:
            total = int(m.group(1))
        elif items:
            mm = re.search(r'pageCount\s*[:=]\s*(\d+)', text, re.I)
            if mm:
                total = int(mm.group(1))
        next_link = re.search(r'href=["\']([^"\']*[?&]page=' + str(int(pg)+1) + r'[^"\']*)["\'][^>]*>\s*下一页', text, re.I)
        pc = int(pg) + 1 if next_link else int(pg)
        if not next_link and len(items) >= 20:
            pc = int(pg) + 1
        if total and len(items) > 0:
            pc = max(pc, int(pg))
        return {'page': int(pg), 'pagecount': pc, 'limit': len(items), 'total': total, 'list': items}

    def searchContent(self, key, quick=False, pg='1'):
        u = self.site + 'search?keyword=' + quote(str(key))
        if str(pg) != '1':
            u += '&page=' + str(pg)
        text = self._decode_html(self._get(u, self.site))
        items = self._search_page(text)
        return {'page': int(pg), 'pagecount': int(pg) + 1 if len(items) >= 20 else int(pg), 'limit': len(items), 'total': len(items), 'list': items}

    def detailContent(self, ids):
        u = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        u = self._href(u)
        text = self._decode_html(self._get(u, self.site))
        title = self._title_from_script(text)
        if not title:
            m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.I | re.S)
            title = self._clean(m.group(1)) if m else unquote(u.rstrip('/').split('/')[-1])
        pic = self._img_from_script(text)
        if not pic:
            m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', text, re.I)
            pic = self._href(m.group(1)) if m else ''
        content = ''
        m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', text, re.I)
        if m:
            content = self._clean(m.group(1))
        play = self._video_url_from_script(text) or u
        return {'list': [{'vod_id': u, 'vod_name': title, 'vod_pic': pic, 'vod_content': content, 'vod_play_from': 'MSAVX', 'vod_play_url': '正片$' + play}]}

    def playerContent(self, flag, id, vipFlags=None):
        url = id
        page_url = ''
        if str(id).startswith('http') and not re.search(r'\.(?:mp4|m3u8|flv|m4v)(?:$|[?#])', id, re.I):
            page_url = id
            text = self._decode_html(self._get(id, id))
            url = self._video_url_from_script(text) or id
        return {'parse': 0 if re.search(r'\.(?:m3u8|mp4|flv|m4v)(?:$|[?#])', str(url), re.I) else 1, 'jx': 0, 'playUrl': '', 'url': url, 'header': 'User-Agent: %s\r\nReferer: %s' % (self.ua, page_url or self.site)}
