# -*- coding: utf-8 -*-

import sys
import re
import json
import requests
import urllib3
import base64
import random
from urllib.parse import quote, unquote, urljoin, urlparse

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
   session = requests.Session()
   host = 'https://kkb1.sixnicejyzj.xyz'
   headers = {
       'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
       'Accept-Language': 'zh-CN,zh;q=0.9',
       'Referer': 'https://kkb1.sixnicejyzj.xyz/',
   }

   def getName(self): return "jyzj"
   def isVideoFormat(self, url): return bool(url and ('.m3u8' in url or '.mp4' in url or '.ts' in url))
   def manualVideoCheck(self): return False
   def destroy(self): pass

   def init(self, extend=""):
       self.session.verify = False
       self._t = {}

   def _fetch(self, url):
       try:
           r = self.session.get(url, headers=self.headers, timeout=20, verify=False)
           r.encoding = 'utf-8'
           return r.text if r.status_code == 200 else ''
       except Exception:
           return ''

   def homeContent(self, filter):
       classes = [
           {'type_id': '1',  'type_name': '精品资源'},
           {'type_id': '2',  'type_name': '特色仓库'},
           {'type_id': '3',  'type_name': '必射精选'},
       ]
       return {'class': classes, 'filters': self._build_filters(), 'type': '影视'}

   def _build_filters(self):
       filters = {}
       filters['1'] = [{'key': 'sub', 'name': '子分类', 'value': [
           {'n': '精品推荐', 'v': '6'}, {'n': '国产精品', 'v': '7'},
           {'n': '主播秀色', 'v': '8'}, {'n': '日本有码', 'v': '9'}, {'n': '日本无码', 'v': '10'},
           {'n': '中文字幕', 'v': '11'}, {'n': '童颜巨乳', 'v': '12'}, {'n': '性感人妻', 'v': '20'},
       ]}]
       filters['2'] = [{'key': 'sub', 'name': '子分类', 'value': [
           {'n': '强奸乱伦', 'v': '13'}, {'n': '欧美情色', 'v': '14'},
           {'n': '三级伦理', 'v': '15'}, {'n': '卡通动漫', 'v': '16'}, {'n': '丝袜OL', 'v': '21'},
           {'n': '自拍偷拍', 'v': '22'}, {'n': '日本片商', 'v': '23'}, {'n': '剧情介绍', 'v': '24'},
       ]}]
       filters['3'] = [{'key': 'sub', 'name': '子分类', 'value': [
           {'n': '网曝系列', 'v': '25'}, {'n': '麻豆传媒', 'v': '26'},
           {'n': '明星换脸', 'v': '27'}, {'n': '国产乱伦', 'v': '28'}, {'n': '国产丝袜', 'v': '29'},
           {'n': '国产SM', 'v': '30'}, {'n': '国产人妻', 'v': '31'}, {'n': '探花嫖娼', 'v': '32'},
       ]}]
       return filters

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
       sub = extend.get('sub', '')
       if sub:
           tid = sub
       tid_str = str(tid)

       url = f'{self.host}/index.php/vod/type/id/{tid_str}-{page}.html' if page > 1 else f'{self.host}/index.php/vod/type/id/{tid_str}.html'
       text = self._fetch(url)
       return self._parse_list(text, page)

   def _parse_list(self, text, page=1):
       items = []
       if not text:
           return self._empty_list(page)

       seen = set()
       for li_block in re.finditer(r'<li[^>]*>(.*?)</li>', text, re.S):
           block = li_block.group(1)

           id_m = re.search(r'href="/index\.php/vod/detail/id/(\d+)\.html"', block)
           if not id_m:
               continue
           vid = id_m.group(1)
           if vid in seen:
               continue
           seen.add(vid)

           pic = ''
           pic_m = re.search(r'<img[^>]+(?:src|data-original)="([^"]+)"', block)
           if pic_m:
               pic = pic_m.group(1).strip()
               if any(k in pic for k in ['loading', 'blank', 'logo', 'icon']):
                   pic = ''

           title = ''
           alt_m = re.search(r'<img[^>]+alt="([^"]+)"', block)
           if alt_m:
               title = alt_m.group(1).strip()
               title = re.sub(r'海报剧照$', '', title)

           if not title:
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

           items.append({
               'vod_id': vid,
               'vod_name': title,
               'vod_pic': pic,
               'vod_remarks': '',
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
       m = re.search(r'<ul[^>]*class="[^"]*detail-actor[^"]*"[^>]*>\s*<li>([^<]+)</li>', text, re.S)
       if m:
           title = m.group(1).strip()

       if not title:
           m = re.search(r'<div[^>]*class="[^"]*detail-poster[^"]*"[^>]*>.*?<img[^>]+alt="([^"]+)"', text, re.S)
           if m:
               title = m.group(1).strip()
               title = re.sub(r'海报剧照$', '', title).strip()

       if not title:
           m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', text, re.S)
           if m:
               title = m.group(1).strip()

       if not title:
           m = re.search(r'<title>([^<]+)</title>', text)
           if m:
               title = m.group(1).strip()
               for suffix in ['_九阴争茎', '- 九阴争茎', '- kkb1', '- sixnicejyzj', '- jyzj']:
                   if suffix in title:
                       title = title.split(suffix)[0].strip()
                       break

       if not title:
           title = f'视频{vid}'

       cover = ''
       m = re.search(r'<div[^>]*class="[^"]*detail-poster[^"]*"[^>]*>.*?<img[^>]+src="([^"]+)"', text, re.S)
       if m:
           cover = m.group(1).strip()
       if not cover:
           m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', text, re.S)
           if m:
               cover = m.group(1).strip()

       content = ''
       m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', text, re.S)
       if m:
           content = m.group(1).strip()
           content = re.sub(r'^.*?剧情:', '', content).strip()

       if not content:
           actor_m = re.search(r'<ul[^>]*class="[^"]*detail-actor[^"]*"[^>]*>(.*?)</ul>', text, re.S)
           if actor_m:
               actor_block = actor_m.group(1)
               lines = re.findall(r'<li>(.*?)</li>', actor_block, re.S)
               info_parts = []
               for line in lines[1:]:
                   txt = re.sub(r'<[^>]+>', '', line).strip()
                   if txt and 'APP下载' not in txt and '在线播放' not in txt:
                       info_parts.append(txt)
               if info_parts:
                   content = ' | '.join(info_parts)

       play_from_list = []
       play_url_list = []

       play_blocks = re.findall(
           r'<ul[^>]*class="[^"]*detail-play-list[^"]*"[^>]*>(.*?)</ul>',
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
           play_url_list.append(f'正片$/index.php/vod/play/id/{vid}/sid/1/nid/1.html')
           play_from_list.append('九阴争茎')

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
       url = f'{self.host}/index.php/vod/search.html?wd={quote(key)}'
       if page > 1:
           url += f'&page={page}'
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
               px = self._z9(id, self.host)
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

       if m3u8 and '.m3u8' in m3u8:
           m3u8 = self._z9(m3u8, self.host)

       return {
           'parse': 0,
           'url': m3u8,
           'header': {'Referer': self.host + '/', 'User-Agent': self.headers['User-Agent']},
           'position': '0'
       }

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
           raw = self._z0(u, rf)
           if not raw:
               return [404, "text/plain", "err"]
           c = self._z1(raw, u, rf)
           return [200, "application/vnd.apple.mpegurl", c]
       except Exception:
           return [404, "text/plain", "err"]

   def _z9(self, url, referer):
       try:
           if hasattr(self, 'getProxyUrl'):
               b = self.getProxyUrl()
               if '?' not in b:
                   b += '?do=py'
               return b + '&type=m3u8&url=' + quote(url, safe='') + '&referer=' + quote(referer or self.host, safe='')
       except Exception:
           pass
       return url

   def _z0(self, url, referer):
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

   def _z1(self, txt, base, referer, skip=25):
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
                       o.append(self._z9(a, referer))
                   else:
                       o.append(a)
           return '\n'.join(o) + '\n'

       hd, sg, tl, ms, td = self._z2(t)
       if not sg:
           return t

       mk = self._z8(base)
       st = {}
       for s in sg:
           k = self._z7(s['uri'], base)
           st[k] = st.get(k, 0.0) + float(s.get('dur') or 0)
       mkk = max(st.items(), key=lambda x: x[1])[0] if st else ('', '')
       tdur = sum(st.values()) or 0
       mdur = st.get(mkk, 0)

       cl = []
       rm = 0
       for idx, s in enumerate(sg):
           k = self._z7(s['uri'], base)
           fr = idx < 12
           au = urljoin(base, s.get('uri', ''))
           ia = self._z6(s['uri'], s.get('dur'), s.get('tags'))
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
               k = self._z7(s['uri'], base)
               if k == mkk and ac >= 3:
                   break
               ac += float(s.get('dur') or td or 3)
               ct = idx + 1
               if ac >= skip:
                   break
           if ct > 0 and ct < len(sg):
               fk = self._z7(sg[0]['uri'], base)
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

   def _z2(self, text):
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

   def _z6(self, uri, dur=0, prev=None):
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

   def _z7(self, uri, base):
       try:
           f = urljoin(base, uri)
           p = urlparse(f)
           ph = re.sub(r'/[^/]*$', '/', p.path or '/')
           return (p.netloc.lower(), ph.lower())
       except Exception:
           return ('', '')

   def _z8(self, murl):
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
