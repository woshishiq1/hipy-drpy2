# coding: utf-8
import json
import re
import time
from html import unescape
from urllib.parse import quote, urljoin
from base.spider import Spider


class Spider(Spider):
    host = "https://chaturbate.com"
    _m3u8_cache = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
        "Referer": "https://chaturbate.com/",
    }
    categories = [
        ("女性", "female-cams"), ("情侣", "couple-cams"),  ("男性", "male-cams"), ("变性", "trans-cams"), ("新人", "new-cams"),
        ("游戏", "gaming-cams"), ("熟女", "mature-cams"),
        ("北美", "north-american-cams"), ("南美", "south-american-cams"),
        ("亚洲", "asian-cams"), ("欧洲/俄罗斯", "euro-russian-cams"),
        ("其他地区", "other-region-cams"),
    ]
    category_params = {
        "female-cams": "&genders=f",
        "male-cams": "&genders=m",
        "couple-cams": "&genders=c",
        "trans-cams": "&genders=t",
        "new-cams": "&new_cams=true",
        "gaming-cams": "&gaming=true",
        "mature-cams": "&from_age=50&to_age=100",
        "north-american-cams": "&regions=NA",
        "south-american-cams": "&regions=SA",
        "asian-cams": "&regions=AS",
        "euro-russian-cams": "&regions=ER",
        "other-region-cams": "&regions=O",
    }

    def init(self, extend=''):
        self.host = "https://chaturbate.com"

    def _get(self, url, headers=None):
        try:
            response = self.fetch(url, headers=headers or self.headers)
            if isinstance(response, str):
                return response
            if isinstance(response, dict):
                return response
            text = getattr(response, "text", None)
            if text is not None:
                return text
            content = getattr(response, "content", None)
            if isinstance(content, bytes):
                return content.decode("utf-8", "ignore")
            if content is not None:
                return str(content)
            return str(response)
        except Exception:
            return ""

    @staticmethod
    def _clean(s):
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

    def _api_rooms(self, page=1, params=''):
        offset = max(0, int(page or 1) - 1) * 90
        url = self.host + "/api/ts/roomlist/room-list/?limit=90&offset=%d&require_fingerprint=false%s" % (offset, params)
        data = self._get(url)
        if isinstance(data, dict):
            return data
        try:
            return json.loads(data or "{}")
        except Exception:
            return {}

    def _api_cards(self, data):
        result = []
        for room in (data or {}).get("rooms", []):
            name = str(room.get("username") or "").strip()
            if not name:
                continue
            subject = self._clean(room.get("subject") or room.get("room_subject") or "")
            viewers = room.get("num_users")
            pic = "https://thumb.live.mmcdn.com/ri/%s.jpg" % name
            result.append({
                "vod_id": name, "vod_name": name, "vod_pic": pic,
                "vod_remarks": "%s 人" % viewers if viewers is not None else "",
                "vod_content": subject,
            })
        return result

    def _cards(self, html):
        result, seen = [], set()
        blocks = re.findall(r'<li[^>]+class="[^"]*RoomCard[^>]*>(.*?)</li>', html or '', re.S | re.I)
        for block in blocks:
            m = re.search(r'href="/([A-Za-z0-9_]+)/(?:"|\s)', block)
            if not m:
                continue
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            pic = ''
            pm = re.search(r'<img[^>]+(?:src|data-src)="([^"]+)"', block, re.I)
            if pm:
                pic = urljoin(self.host, pm.group(1))
            sm = re.search(r'class="[^"]*RoomCardSubject[^"]*"[^>]*>(.*?)</ul>', block, re.S | re.I)
            subject = self._clean(sm.group(1)) if sm else ''
            vm = re.search(r'class="(?:time|viewers)[^"]*"[^>]*>(.*?)</', block, re.S | re.I)
            viewers = self._clean(vm.group(1)) if vm else ''
            result.append({
                "vod_id": name, "vod_name": name, "vod_pic": pic,
                "vod_remarks": viewers, "vod_content": subject,
            })
        return result

    def homeContent(self, filter):
        return {"class": [{"type_id": x[1], "type_name": x[0]} for x in self.categories], "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        params = self.category_params.get(tid, '')
        data = self._api_rooms(page, params)
        items = self._api_cards(data)
        total = int(data.get("total_count") or 0)
        pagecount = max(1, (total + 89) // 90) if total else 1
        return {"list": items, "page": page, "pagecount": pagecount, "limit": len(items), "total": total}

    def searchContent(self, key, quick, pg='1'):
        page = int(pg or 1)
        url = self.host + '/api/ts/roomlist/room-list/?limit=90&offset=%d&require_fingerprint=false&q=%s' % (max(0, page - 1) * 90, quote(key, safe=''))
        data = self._get(url)
        if not isinstance(data, dict):
            try:
                data = json.loads(data or '{}')
            except Exception:
                data = {}
        items = self._api_cards(data)
        total = int(data.get("total_count") or 0)
        pagecount = max(1, (total + 89) // 90) if total else 1
        return {"list": items, "page": page, "pagecount": pagecount, "limit": len(items), "total": total}

    def detailContent(self, ids):
        room = str(ids[0] if isinstance(ids, list) else ids).strip('/')
        html = self._get(self.host + '/' + room + '/')
        title = room
        tm = re.search(r'<title[^>]*>(.*?)</title>', html or '', re.S | re.I)
        if tm:
            title = self._clean(tm.group(1)).split(' - ')[0].strip() or room
        pic = 'https://thumb.live.mmcdn.com/ri/%s.jpg' % room
        im = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html or '', re.I)
        if im:
            pic = re.sub(r"/(?:riw|r|thumb)/", "/ri/", urljoin(self.host, im.group(1)))
        desc = ''
        dm = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html or '', re.I)
        if dm:
            desc = unescape(dm.group(1))
        sources = self._resolution_sources(room, html)
        if sources:
            play_from = '$$$'.join(x[0] for x in sources)
            play_url = '$$$'.join(x[1] for x in sources)
        else:
            play_from, play_url = '直播间', '进入直播间$' + self.host + '/' + room + '/'
        return {"list": [{"vod_id": room, "vod_name": title, "vod_pic": pic,
            "vod_content": desc, "vod_play_from": play_from, "vod_play_url": play_url}]}

    def playerContent(self, flag, id, vipFlags):
        value = str(id or '').strip()
        if '|' in value:
            room, resolution = value.split('|', 1)
        else:
            room, resolution = value.strip('/').split('/')[-1], ''
        room = room.strip('/')
        resolution = (resolution or '').strip().lower().replace('p', '')
        referer = self.host + '/' + room + '/'
        html = self._get(referer)
        ctx = self._chatvideocontext(room)
        stream = str(ctx.get('hls_source') or '').strip().replace('\\/', '/')
        if not stream:
            stream = self._hls_source(html)
        if not stream:
            return {"parse": 1, "url": referer, "header": self.headers}

        # 走 localProxy 重构主清单：保留 AUDIO 组，修复分离音轨无声
        proxy = self._proxy_url(stream, resolution or 'all')
        return {"parse": 0, "url": proxy, "header": {
            "User-Agent": self.headers["User-Agent"], "Referer": referer, "Origin": self.host}}

    def _hls_source(self, html):
        m = re.search(r'hls_source\\u0022:\s*\\u0022(.*?)\\u0022', html or '', re.S)
        if not m:
            return ''
        try:
            return m.group(1).encode('utf-8').decode('unicode_escape').replace('\\/', '/')
        except Exception:
            return m.group(1).replace('\\u002d', '-').replace('\\u003d', '=').replace('\\u0026', '&').replace('\\/', '/')

    def _chatvideocontext(self, room):
        room = str(room or '').strip('/')
        if not room:
            return {}
        headers = dict(self.headers)
        headers['Referer'] = self.host + '/' + room + '/'
        headers['Origin'] = self.host
        data = self._get(self.host + '/api/chatvideocontext/' + room + '/', headers=headers)
        if not isinstance(data, dict):
            try:
                data = json.loads(data or '{}')
            except Exception:
                data = {}
        return data or {}

    def _hls_source_fallback(self, room):
        data = self._chatvideocontext(room)
        stream = str((data or {}).get('hls_source') or '').strip()
        return stream.replace('\\/', '/')

    def _hls_variants(self, master):
        text = self._get(master)
        if '#EXTM3U' not in text:
            return []
        result, pending = [], ''
        for line in text.replace('\r', '').split('\n'):
            line = line.strip()
            if line.startswith('#EXT-X-STREAM-INF:'):
                pending = line
            elif pending and line and not line.startswith('#'):
                match = re.search(r'RESOLUTION=\d+x(\d+)', pending, re.I)
                am = re.search(r'AUDIO="([^"]+)"', pending, re.I)
                result.append({
                    'height': (match.group(1) if match else ''),
                    'url': urljoin(master, line),
                    'separate_audio': bool(am),
                })
                pending = ''
        return result

    @staticmethod
    def _select_variant(variants, resolution):
        target = str(resolution or '').lower().replace('p', '').strip()
        for item in variants:
            if str(item.get('height') or '') == target:
                return item
        return {}

    def _resolution_sources(self, room, html):
        stream = self._hls_source(html)
        variants = self._hls_variants(stream) if stream else []
        variants.sort(key=lambda item: int(item.get('height') or 0), reverse=True)
        seen = set()
        out = []
        for item in variants:
            h = str(item.get('height') or '').strip()
            if not h or h in seen:
                continue
            seen.add(h)
            out.append((h + 'P', '播放$' + room + '|' + h + 'p'))
        return out

    def _proxy_url(self, master, q_idx='all'):
        try:
            proxy = str(self.getProxyUrl() or '').strip()
        except Exception:
            proxy = ''
        if not proxy:
            return master
        return proxy + '&type=cb_m3u8&ptype=cb_m3u8&url=' + quote(master, safe='') + '&q=' + str(q_idx) + '&ext=.m3u8'

    def localProxy(self, params):
        params = params or {}
        ptype = str(params.get('type') or params.get('ptype') or '').strip()
        if ptype != 'cb_m3u8':
            return None
        url = str(params.get('url', '') or '')
        q_idx = str(params.get('q', 'all') or '')

        curr_time = time.time()
        cache_key = (url.split('?', 1)[0] + '_' + q_idx) if url else ('_' + q_idx)
        cdata = self._m3u8_cache.get(cache_key)
        if cdata and curr_time < cdata[1]:
            return [200, 'application/vnd.apple.mpegurl', cdata[0]]

        try:
            text = self._get(url)
        except Exception:
            text = ''
        if '#EXTM3U' not in (text or ''):
            return [200, 'application/vnd.apple.mpegurl', text or '']

        base = url.rsplit('/', 1)[0] + '/'
        lines = text.replace('\r', '').split('\n')
        audio_tags = {}
        for line in lines:
            if line.strip().startswith('#EXT-X-MEDIA:TYPE=AUDIO'):
                gm = re.search(r'GROUP-ID="([^"]+)"', line)
                if gm:
                    line = re.sub(r'URI="([^"]+)"', lambda m: 'URI="' + urljoin(base, m.group(1)) + '"', line)
                    audio_tags[gm.group(1)] = line

        streams = []
        for i in range(len(lines)):
            s = lines[i].strip()
            if s.startswith('#EXT-X-STREAM-INF') and i + 1 < len(lines):
                bw_m = re.search(r'BANDWIDTH=(\d+)', s)
                bw = int(bw_m.group(1)) if bw_m else 0
                rh_m = re.search(r'RESOLUTION=\d+x(\d+)', s, re.I)
                rh = rh_m.group(1) if rh_m else ''
                streams.append({'bw': bw, 'h': rh, 'inf': s, 'uri': lines[i+1].strip()})

        if not streams:
            new_chunklist = []
            for line in lines:
                s = line.strip()
                if not s:
                    continue
                if s.startswith('#'):
                    if 'URI="' in s:
                        s = re.sub(r'URI="([^"]+)"', lambda m: 'URI="' + urljoin(base, m.group(1)) + '"', s)
                    new_chunklist.append(s)
                else:
                    new_chunklist.append(urljoin(base, s))
            final_content = '\n'.join(new_chunklist)
            self._m3u8_cache[cache_key] = (final_content, curr_time + 15)
            return [200, 'application/vnd.apple.mpegurl', final_content]

        streams.sort(key=lambda x: x['bw'], reverse=True)
        selected = None
        target = str(q_idx or 'all').lower().replace('p', '').strip()

        if target and target != 'all':
            for s in streams:
                if str(s.get('h') or '') == target:
                    selected = s
                    break
            if not selected:
                for s in streams:
                    if '_chunklist_' + target + '_' in s['uri']:
                        selected = s
                        break

        # all / 未命中：统一强制最高码率（最高分辨率）
        if not selected:
            selected = streams[0]

        new_lines = ['#EXTM3U', '#EXT-X-VERSION:6', '#EXT-X-INDEPENDENT-SEGMENTS']
        am = re.search(r'AUDIO="([^"]+)"', selected['inf'])
        audio_group = am.group(1) if am else None
        if audio_group and audio_group in audio_tags:
            new_lines.append(audio_tags[audio_group])

        inf_line = re.sub(r',CODECS="[^"]*"', '', selected['inf'])
        inf_line = re.sub(r',mp4a[^",]*', '', inf_line)
        new_lines.append(inf_line)
        new_lines.append(urljoin(base, selected['uri']))
        final_content = '\n'.join(new_lines)
        self._m3u8_cache[cache_key] = (final_content, curr_time + 15)
        return [200, 'application/vnd.apple.mpegurl', final_content]

    def isVideoFormat(self, url):
        return False
