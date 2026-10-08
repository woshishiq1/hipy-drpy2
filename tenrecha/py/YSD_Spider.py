# coding=utf-8
import sys
import re
import json
import requests
import urllib3
import base64
from urllib.parse import quote, unquote, urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    session = requests.Session()
    host = 'https://ysd.yinsd1.sbs'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.210 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://ysd.yinsd1.sbs/',
    }

    def getName(self): return "YSD_Spider"
    def isVideoFormat(self, url): return bool(url and ('.m3u8' in url or '.mp4' in url or '.ts' in url))
    def manualVideoCheck(self): return False
    def destroy(self): pass

    def init(self, extend=""):
        self.session.verify = False
        if not hasattr(self, 'host') or not self.host:
            self.host = "https://ysd.yinsd1.sbs"

    def _fetch(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=20, verify=False)
            r.encoding = 'utf-8'
            return r.text if r.status_code == 200 else ''
        except Exception:
            return ''

    def homeContent(self, filter):
        classes = [
            {'type_id': '28', 'type_name': '视频1区'},
            {'type_id': '39', 'type_name': '视频2区'},
            {'type_id': '50', 'type_name': '视频3区'},
            {'type_id': '56', 'type_name': '视频4区'},
        ]
        
        tags = ["同居", "内射", "多水", "胸大", "网袜", "女神", "另类", "长发", "SM"]
        tag_values = [{"n": "全部", "v": ""}] + [{"n": tag, "v": tag} for tag in tags]
        
        filters = {}
        for cls in classes:
            filters[cls["type_id"]] = [
                {
                    "key": "wd", 
                    "name": "热门标签", 
                    "value": tag_values
                }
            ]
            
        return {'class': classes, 'filters': filters, 'type': '影视'}

    def homeVideoContent(self):
        text = self._fetch(self.host + '/')
        items = self._parse_list(text, page=1).get('list', [])
        return {
            'list': items[:30],
            'page': 1,
            'pagecount': 2 if items else 1,
            'limit': len(items),
            'total': len(items)
        }

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}
        
        wd = extend.get('wd', '')
        if wd:
            if page == 1:
                url = f'{self.host}/index.php/vod/search/wd/{quote(wd)}.html'
            else:
                url = f'{self.host}/index.php/vod/search/page/{page}/wd/{quote(wd)}.html'
        else:
            tid_str = str(tid)
            if tid_str == '1':
                if page == 1:
                    url = f'{self.host}/index.php/vod/type.html'
                else:
                    url = f'{self.host}/index.php/vod/type/page/{page}.html'
            else:
                if page == 1:
                    url = f'{self.host}/index.php/vod/type/id/{tid_str}.html'
                else:
                    url = f'{self.host}/index.php/vod/type/id/{tid_str}/page/{page}.html'
        
        text = self._fetch(url)
        return self._parse_list(text, page)

    def _parse_list(self, text, page=1):
        items = []
        if not text:
            return self._empty_list(page)

        seen = set()
        for li_block in re.finditer(r'<li[^>]*class=["\'][^"\']*content-item[^"\']*["\'][^>]*>(.*?)</li>', text, re.S):
            block = li_block.group(1)

            id_m = re.search(r'href="/index\.php/vod/detail/id/(\d+)\.html"', block)
            if not id_m:
                continue
            vid = id_m.group(1)
            if vid in seen:
                continue
            seen.add(vid)

            title = ''
            atitle_m = re.search(r'<a[^>]+title="([^"]+)"', block)
            if atitle_m:
                title = atitle_m.group(1).strip()

            if not title:
                h_m = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', block, re.S)
                if h_m:
                    title = re.sub(r'<[^>]+>', '', h_m.group(1)).strip()

            if not title:
                a_m = re.search(r'<a[^>]*>([^<]+)</a>', block)
                if a_m:
                    title = a_m.group(1).strip()

            if not title:
                title = f'未知标题{vid}'

            pic = ''
            dom_m = re.search(r'data-original="([^"]+)"', block)
            if dom_m:
                pic = dom_m.group(1).strip()
            if not pic:
                pic_m = re.search(r'<img[^>]+src="([^"]+)"', block)
                if pic_m:
                    pic = pic_m.group(1).strip()
                    if any(k in pic for k in ['loading', 'blank', 'logo', 'icon', '235x140']):
                        pic = ''

            remark = ''
            note_m = re.search(r'<span[^>]*class=["\'][^"\']*note[^"\']*["\'][^>]*>([^<]+)</span>', block)
            if note_m:
                remark = note_m.group(1).strip()

            items.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark,
            })

        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    def _empty_list(self, page):
        return {'list': [], 'page': page, 'pagecount': page, 'limit': 0, 'total': 0}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        return self._vod_detail(vid)

    def _vod_detail(self, vid):
        url = f'{self.host}/index.php/vod/detail/id/{vid}.html'
        text = self._fetch(url)
        if not text:
            return {'list': []}

        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        if not title:
            m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', text, re.S)
            if m:
                title = m.group(1).strip()

        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m:
                title = m.group(1).strip()
                for suffix in ['_淫水洞', '- 淫水洞', '- yinsd', '- YSD']:
                    if suffix in title:
                        title = title.split(suffix)[0].strip()
                        break

        if not title:
            title = f'视频{vid}'

        cover = ''
        m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', text, re.S)
        if m:
            cover = m.group(1).strip()
        if not cover:
            m = re.search(r'<img[^>]+(?:data-original|src)="([^"]+)"[^>]*class=["\'][^"\']*(?:content-img|video-pic|detail-poster|poster)[^"\']*["\']', text, re.S)
            if m:
                cover = m.group(1).strip()

        content = ''
        m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', text, re.S)
        if m:
            content = m.group(1).strip()

        if not content:
            m = re.search(r'<div[^>]*class=["\'][^"\']*content[^"\']*["\'][^>]*>(.*?)</div>', text, re.S)
            if m:
                content = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        if not content:
            content = '无详细简介'

        play_from_list = []
        play_url_list = []

        play_blocks = re.findall(
            r'<ul[^>]*class=["\'][^"\']*detail-play-list[^"\']*["\'][^>]*>(.*?)</ul>',
            text, re.S
        )

        if play_blocks:
            for block in play_blocks:
                eps = re.findall(
                    r'<a[^>]+href="(/index\.php/vod/play/[^"]+)"[^>]*(?:title="([^"]*)")?[^>]*>([^<]+)</a>',
                    block
                )
                if eps:
                    urls = '#'.join([f'{name.strip()}${href}' for href, _, name in eps])
                    play_url_list.append(urls)
                    play_from_list.append('线路' + str(len(play_from_list) + 1))

        if not play_url_list:
            play_url_list.append(f'播放$/index.php/vod/play/id/{vid}/sid/1/nid/1.html')
            play_from_list.append('八卦乾坤镜')

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': cover,
            'vod_content': content,
            'vod_remarks': '',
            'vod_play_from': '$$$'.join(play_from_list),
            'vod_play_url': '$$$'.join(play_url_list),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        if page == 1:
            url = f'{self.host}/index.php/vod/search/wd/{quote(key)}.html'
        else:
            url = f'{self.host}/index.php/vod/search/page/{page}/wd/{quote(key)}.html'
        text = self._fetch(url)
        items = self._parse_list(text, page).get('list', [])
        return {
            'list': items,
            'page': page,
            'pagecount': page + 1 if items else page,
            'limit': len(items),
            'total': page * len(items) + 1
        }

    def playerContent(self, flag, id, vipFlags=None):
        if id.startswith('http'):
            if '.m3u8' in id:
                px = self.金(id, self.host)
                return {'parse': 0, 'url': px, 'header': json.dumps({'Referer': self.host})}
            return {
                'parse': 0,
                'url': id,
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }

        url = self.host + ('' if id.startswith('/') else '/') + id
        text = self._fetch(url)
        m3u8 = ''

        if text:
            for var_name in ['player_aaaa', 'player', 'mac_player', 'player_data', 'cms_player']:
                m = re.search(rf'var\s+{var_name}\s*=\s*(\{{.*?\}})\s*</script>', text, re.S)
                if m:
                    try:
                        player = json.loads(m.group(1))
                        raw_url = player.get('url', '')
                        if raw_url and isinstance(raw_url, str):
                            decoded = raw_url.strip()
                            if re.match(r'^[A-Za-z0-9+/=]{20,}$', decoded):
                                try:
                                    decoded = base64.b64decode(decoded).decode('utf-8')
                                except Exception:
                                    pass
                            if '%' in decoded:
                                try:
                                    decoded = unquote(decoded)
                                except Exception:
                                    pass
                            if decoded.startswith('http'):
                                m3u8 = decoded
                                break
                    except Exception:
                        continue

            if not m3u8:
                m = re.search(r'<iframe[^>]+src="([^"]+)"', text, re.S)
                if m:
                    iframe_src = m.group(1).strip()
                    if iframe_src.startswith('http'):
                        m3u8 = iframe_src
                    else:
                        m3u8 = self.host + ('' if iframe_src.startswith('/') else '/') + iframe_src

            if not m3u8:
                m = re.search(r'["\'](https?://[^\s"<>]+?\.(?:m3u8|mp4|ts|flv))["\']', text)
                if m:
                    m3u8 = m.group(1)

            if not m3u8:
                m = re.search(r'unescape\(["\']([^"\']+)["\']\)', text)
                if m:
                    try:
                        decoded = unquote(m.group(1))
                        if decoded.startswith('http'):
                            m3u8 = decoded
                    except Exception:
                        pass

        if m3u8 and self.isVideoFormat(m3u8):
            px = self.金(m3u8, self.host)
            return {
                'parse': 0,
                'url': px,
                'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
                'position': '0'
            }

        return {
            'parse': 1,
            'url': url,
            'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
        }

    # ==================== 五行八卦 ====================
    def localProxy(self, param):
        try:
            if not isinstance(param, dict):
                param = {}
            pt = param.get('type') or param.get('action') or param.get('do')
            u = param.get('url', '')
            if pt != 'm3u8' or not u:
                return [404, "text/plain", "nf"]
            rf = param.get('referer', '') or self.host
            if isinstance(u, list):
                u = u[0]
            if isinstance(rf, list):
                rf = rf[0]
            u = unquote(u)
            rf = unquote(rf)
            raw = self.木(u, rf)
            if not raw:
                return [404, "text/plain", "err"]
            c = self.火(raw, u, rf)
            return [200, "application/vnd.apple.mpegurl", c]
        except Exception:
            return [404, "text/plain", "err"]

    def 金(self, url, referer):
        try:
            if hasattr(self, 'getProxyUrl'):
                b = self.getProxyUrl()
                if '?' not in b:
                    b += '?do=py'
                return b + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.host, safe='')
        except Exception:
            pass
        return url

    def 木(self, url, referer):
        try:
            h = self.session.headers.copy()
            h['Referer'] = referer
            r = requests.get(url, headers=h, timeout=15)
            if r.status_code == 200:
                r.encoding = 'utf-8'
                return r.text
        except Exception:
            pass
        return None

    def 火(self, txt, base, referer, skip=25):
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
                    a = urljoin(base, ln)
                    if '.m3u8' in ln.lower():
                        o.append(self.金(a, referer))
                    else:
                        o.append(a)
            return '\n'.join(o) + '\n'

        hd, sg, tl, ms, td = self.水(t)
        if not sg:
            return t

        mk = self.兑(base)
        st = {}
        for s in sg:
            k = self.乾(s['uri'], base)
            st[k] = st.get(k, 0.0) + float(s.get('dur') or 0)
        mkk = max(st.items(), key=lambda x: x[1])[0] if st else ('', '')
        tdur = sum(st.values()) or 0
        mdur = st.get(mkk, 0)

        cl = []
        rm = 0
        for idx, s in enumerate(sg):
            k = self.乾(s['uri'], base)
            fr = idx < 12
            au = urljoin(base, s.get('uri', ''))
            ia = self.土(s['uri'], s.get('dur'), s.get('tags'))
            if mk and mk not in urlparse(au).path.lower():
                ia = True
            tt = '\n'.join(s.get('tags') or []).upper()
            if fr and 'METHOD=NONE' in tt and mk and mk not in urlparse(au).path.lower():
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
                k = self.乾(s['uri'], base)
                if k == mkk and ac >= 3:
                    break
                ac += float(s.get('dur') or td or 3)
                ct = idx + 1
                if ac >= skip:
                    break
            if ct > 0 and ct < len(sg):
                fk = self.乾(sg[0]['uri'], base)
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
                    tg = re.sub(r'URI="([^"]+)"', lambda m: 'URI="' + urljoin(base, m.group(1)) + '"', tg)
                nl.append(tg)
            nl.append(urljoin(base, s.get('uri', '')))
        if tl:
            for ln in tl:
                if ln.startswith('#EXT-X-ENDLIST'):
                    nl.append(ln)
        elif '#EXT-X-ENDLIST' in t:
            nl.append('#EXT-X-ENDLIST')
        return '\n'.join(nl) + '\n'

    def 水(self, text):
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
                m = re.search(r'#EXTINF:\s*([\d.]+)', ln)
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

    def 土(self, uri, dur=0, prev=None):
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

    def 乾(self, uri, base):
        try:
            f = urljoin(base, uri)
            p = urlparse(f)
            ph = re.sub(r'/[^/]*$', '/', p.path or '/')
            return (p.netloc.lower(), ph.lower())
        except Exception:
            return ('', '')

    def 兑(self, murl):
        try:
            p = urlparse(murl).path
            m = re.search(r'(/\d{8}/[^/]+/\d+kb/hls/)', p)
            if m:
                return m.group(1).lower()
            m = re.search(r'(/\d{8}/[^/]+/)', p)
            if m:
                return m.group(1).lower()
        except Exception:
            pass
        return ''
