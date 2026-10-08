# coding=utf-8
import base64, json, re, sys, threading, time
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.parse import quote, urlparse
import requests
from urllib3.util.retry import Retry
from base.spider import Spider
sys.path.append("..")

class Spider(Spider):
    def init(self, extend="{}"):
        self.create_session_with_retry()
        self.dynamic_urls = ["https://zh.stripchat.com", "https://zh.stripchat.global", "https://zh.stripol.com"]
        self.Doppiocdn = "doppiocdn.org"
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:153.0) Gecko/20100101 Firefox/153.0"
        self.headers = {"User-Agent": ua, "Accept-Language": "zh,en;q=0.5"}
        self.host = self.dynamic_urls[0]
        self._update_headers_for_host(self.host)
        self.stripchat_preferredVideoCodec = "H264"
        self.stripchat_key = "YzWScuyQRGAGcxx1KIJmiQ7BY9Vi35ftwLqUOVO8uoo="
        self.stripchat_pkey = "Fq6m2TO2ZeBkRPm9"
        self.stripchat_play = "0 0"
        self.danmu_cache, self.danmu_threads, self.danmu_lock = {}, {}, threading.Lock()

    def _update_headers_for_host(self, host_url):
        self.host = host_url
        self.headers["Origin"] = host_url
        self.headers["Referer"] = f"{host_url}/"
        self.json_headers = {**self.headers, "Accept": "application/json, text/plain, */*"}

    def _request_with_failover(self, path, timeout=(5, 10)):
        urls_to_try = list(self.dynamic_urls)
        if self.host in urls_to_try:
            urls_to_try.remove(self.host)
            urls_to_try.insert(0, self.host)
        for domain in urls_to_try:
            clean_domain = domain.strip().rstrip('/')
            full_url = f'{clean_domain}{path}' if path.startswith('/') else f'/{path}'
            headers = {'User-Agent': self.headers.get('User-Agent'), 'Accept': 'application/json, text/plain, */*',
                       'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8', 'Origin': clean_domain, 'Referer': f'{clean_domain}/'}
            try:
                self.log(f'尝试请求: {full_url}')
                r = self.session_get(full_url, headers=headers, timeout=timeout)
                if r and r.status_code == 200:
                    ct = r.headers.get('Content-Type', '')
                    if 'application/json' in ct or r.text.strip().startswith('{'):
                        data = r.json()
                        if isinstance(data, dict) and data:
                            if self.host != clean_domain:
                                self._update_headers_for_host(clean_domain)
                            return data
            except: pass
        return {}

    def getName(self): return 'StripChat'
    def isVideoFormat(self, url): pass
    def manualVideoCheck(self): pass
    def destroy(self): pass
    def homeVideoContent(self): pass

    def datetime_utc8(self, s, fmt): return (datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ') + timedelta(hours=8)).strftime(fmt)

    def homeContent(self, filter):
        CLASSES = [{'type_name': '女主播', 'type_id': 'girls'}, {'type_name': '情侣', 'type_id': 'couples'},
                   {'type_name': '男主播', 'type_id': 'men'}, {'type_name': '跨性别', 'type_id': 'trans'}]
        VALUE = [{'n': '新主播', 'v': 'autoTagNew'}, {'n': '推荐', 'v': 'recommended'}, {'v': 'fuckMachine', 'n': '炮机'},
                 {'n': '青年', 'v': 'ageTeen'}, {'n': 'VR', 'v': 'autoTagVr'}, {'n': '亚洲人', 'v': 'ethnicityAsian'},
                 {'n': '🇨🇳中国', 'v': 'tagLanguageChinese'}, {'n': '🇯🇵日本', 'v': 'tagLanguageJapanese'},
                 {'n': '🇰🇷韩国', 'v': 'tagLanguageKorean'}, {'n': '🇻🇳越南', 'v': 'tagLanguageVietnamese'},
                 {'v': 'tagLanguageUkrainian', 'n': '🇺🇦乌克兰'}, {'v': 'tagLanguageRussianSpeaking', 'n': '🇷🇺俄罗斯'},
                 {'v': 'tagLanguageUSModels', 'n': '🇺🇸美国'}, {'v': 'tagLanguageColombian', 'n': '🇨🇴哥伦比亚'},
                 {'v': 'tagLanguageGermanSpeaking', 'n': '🇩🇪德国'}, {'v': 'tagLanguageFrench', 'n': '🇫🇷法国'},
                 {'v': 'tagLanguageUKModels', 'n': '🇬🇧英国'}, {'v': 'tagLanguageCanadian', 'n': '🇨🇦加拿大'},
                 {'v': 'tagLanguageMexican', 'n': '🇲🇽墨西哥'}, {'v': 'ethnicityIndian', 'n': '🇮🇳印度'},
                 {'v': 'tagLanguageVenezuelan', 'n': '🇻🇪委内瑞拉'}, {'v': 'tagLanguageRomanian', 'n': '🇷🇴罗马尼亚'},
                 {'v': 'tagLanguageAfrican', 'n': '🌍非洲'}, {'v': 'tagLanguageSpanishSpeaking', 'n': '🇪🇸西班牙'},
                 {'v': 'ethnicityMiddleEastern', 'n': '🇸🇦🇦🇪阿拉伯'}, {'v': 'tagLanguageKenyan', 'n': '🇰🇪肯尼亚'},
                 {'v': 'tagLanguageSouthAfrican', 'n': '🇿🇦南非'}, {'v': 'tagLanguageBrazilian', 'n': '🇧🇷巴西'},
                 {'v': 'tagLanguageThai', 'n': '🇹🇭泰国'}, {'v': 'tagLanguageItalian', 'n': '🇮🇹意大利'},
                 {'n': '亚洲', 'v': 'ethnicityAsian'}, {'n': '白人', 'v': 'ethnicityWhite'},
                 {'n': '拉丁', 'v': 'ethnicityLatino'}, {'n': '混血', 'v': 'ethnicityMultiracial'},
                 {'n': '印度', 'v': 'ethnicityIndian'}, {'n': '阿拉伯', 'v': 'ethnicityMiddleEastern'},
                 {'n': '黑人', 'v': 'ethnicityEbony'}, {'n': '✨新主播', 'v': 'autoTagNew'},
                 {'n': 'VR直播', 'v': 'autoTagVr'}, {'n': '18+', 'v': 'ageTeen'},
                 {'n': '鲜嫩青年22+', 'v': 'ageYoung'}, {'n': '学生', 'v': 'subcultureStudent'},
                 {'n': '口交', 'v': 'doBlowjob'}, {'n': '深喉', 'v': 'doDeepThroat'},
                 {'n': '恋足', 'v': 'doFootFetish'}, {'n': '互动玩具', 'v': 'autoTagInteractiveToy'},
                 {'n': '自慰', 'v': 'doMasturbation'}, {'n': '肛交', 'v': 'doAnal'},
                 {'n': '潮吹', 'v': 'doSquirt'}, {'n': '狗式', 'v': 'doDoggyStyle'},
                 {'n': 'Cosplay', 'v': 'doCosplay'}, {'n': 'RolePlay', 'v': 'doRolePlay'}]
        VALUE_MEN = [{'n': '情侣', 'v': 'sexGayCouples'}, {'n': '直男', 'v': 'orientationStraight'}]
        TIDS = ('girls', 'couples', 'men', 'trans')
        filters = {tid: [{'key': 'tag', 'value': VALUE_MEN + VALUE if tid == 'men' else VALUE}] for tid in TIDS}
        return {'class': CLASSES, 'filters': filters}

    def _parse_status_remark(self, is_live, status, viewers=0):
        if not is_live or status == 'off':
            st = '⚫已下播'
        elif status == 'public':
            st = '🔴直播中'
        elif status == 'groupShow':
            st = '🎫门票房'
        elif status == 'ticket':
            st = '🎫购票房'
        else:
            st = f'🎫{status}'
        return f'{st} 👤{viewers}人' if viewers else st
    def _get_status_tag(self, status):
        if status == 'public': return '🔴直播'
        elif status == 'groupShow': return '🎫门票'
        elif status == 'ticket': return '🎫购票'
        elif status == 'off': return '⚫下播'
        return ''

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg_str, page_num = str(pg), int(pg)
            if tid.startswith('search '):
                _, tag, key = tid.split(maxsplit=2)
                path = f'/api/front/v4/models/search/group/username?query={key}&limit=900&primaryTag={tag}'
                rsp = self._request_with_failover(path)
                videos = []
                for u in rsp.get('models', []):
                    status = u.get('status', 'off')
                    is_live = status in ['public', 'groupShow', 'ticket']
                    viewers = u.get('viewersCount', 0)
                    videos.append({'vod_id': str(u['id']),
                        'vod_name': f"{self.country_code_to_flag(str(u.get('country', '')))}{u['username']}",
                        'vod_pic': f"https://img.{self.Doppiocdn}/snapshot/{u['id']}/{u.get('snapshotTimestamp', '')}",
                        'style': {'type': 'rect', 'ratio': 1.78},
                        'vod_remarks': self._parse_status_remark(is_live, status, viewers),
                        'vod_tag': self._get_status_tag(status)})
                return {'list': videos, 'page': pg_str, 'pagecount': '1', 'limit': '900', 'total': str(len(videos))}
            limit, offset = 60, 60 * (page_num - 1)
            path = f'/api/front/models?improveTs=false&removeShows=false&limit={limit}&offset={offset}&primaryTag={tid}&sortBy=stripRanking&rcmGrp=A&rbCnGr=true&prxCnGr=false&nic=false'
            if 'tag' in extend and extend['tag']: path += f'&filterGroupTags=[["{extend["tag"]}"]]'
            rsp = self._request_with_failover(path)
            videos = []
            for v in rsp.get('models', []):
                is_live = v.get('isLive', False)
                status = v.get('status', 'off')
                viewers = v.get('viewersCount', 0)
                videos.append({'vod_id': str(v['id']),
                    'vod_name': f"{self.country_code_to_flag(str(v.get('country', '')))}{v['username']}",
                    'vod_pic': f"https://img.{self.Doppiocdn}/snapshot/{v['id']}/{v.get('snapshotTimestamp', '')}",
                    'vod_remarks': self._parse_status_remark(is_live, status, viewers),
                    'vod_tag': self._get_status_tag(status)})
            total = int(rsp.get('filteredCount', 0))
            return {'list': videos, 'page': pg_str, 'pagecount': str((total + limit - 1) // limit), 'limit': str(limit), 'total': str(total)}
        except: return {'list': [], 'page': str(pg), 'pagecount': '1', 'limit': '60', 'total': '0'}

    def detailContent(self, array):
        if not array: return {'list': []}
        uid = array[0]
        try:
            return {'list': [{'vod_id': uid, 'vod_pic': '', 'vod_director': '',
                'vod_content': 'Stripchat 直播流',
                'vod_remarks': '🔴 直播中',
                'vod_play_from': '线路一$$$线路二$$$线路三',
                'vod_play_url': f'主线路${uid}$$$备用线路$lemon_{uid}$$$备用线路三$sacf_{uid}'}]}
        except: return {'list': []}
    def searchContent(self, key, quick, pg='1'):
        if int(pg) > 1: return {}
        return {'list': [{'vod_id': f'search {t["type_id"]} {key}', 'vod_name': t['type_name'], 'vod_tag': 'folder'}
                        for t in self.homeContent(False).get('class', [])]}

    def playerContent(self, flag, id, vipFlags):
        urls = []
        try:
            sid = id.split('_')[-1]
            self.start_danmu(sid)
            headers = {'User-Agent': self.headers.get('User-Agent'), 'Origin': self.host, 'Referer': f'{self.host}/'}
            # 使用备用线路（sacfedge）
            m3u8_url = f'https://edge-hls.sacfedge.com/hls/{sid}/master/{sid}_auto.m3u8?playlistType=lowLatency'
            r = self.session_get(m3u8_url, headers=headers, timeout=10)
            if r and r.status_code == 200:
                lines = r.text.strip().split('\n')
                for i, line in enumerate(lines):
                    if '#EXT-X-STREAM-INF' in line:
                        qn_start = line.find('NAME="') + 6
                        qn = line[qn_start:line.find('"', qn_start)]
                        urls.extend([qn, f'{self.getProxyUrl()}&url={quote(lines[i+1])}'])
            else:
                # 降级到主线路
                m3u8_url = f'https://edge-hls.{self.Doppiocdn}/hls/{sid}/master/{sid}_auto.m3u8?playlistType=lowLatency'
                r = self.session_get(m3u8_url, headers=headers, timeout=10)
                if r and r.status_code == 200:
                    lines = r.text.strip().split('\n')
                    for i, line in enumerate(lines):
                        if '#EXT-X-STREAM-INF' in line:
                            qn_start = line.find('NAME="') + 6
                            qn = line[qn_start:line.find('"', qn_start)]
                            urls.extend([qn, f'{self.getProxyUrl()}&url={quote(lines[i+1])}'])
            if urls: return {'url': urls, 'parse': '2', 'position': '0', 'header': headers}
            return {'url': [], 'parse': 0}
        except: return {'url': [], 'parse': 0}

    def update_vod(self, username):
        try:
            data = self.detailContent([username]).get('list')[0]
            self.post('http://127.0.0.1:9978/action?do=refresh&type=vod', data={'json': json.dumps(data)})
        except: pass

    def localProxy(self, param):
        url, type_ = param['url'], param.get('type', '')
        headers = {'User-Agent': self.headers.get('User-Agent'), 'Origin': self.host, 'Referer': f'{self.host}/'}
        if type_ == 'media':
            try:
                data = self.session_get(url, headers=headers, timeout=(5, 15))
                return [200, 'video/mp4', data.content] if data and data.status_code == 200 else [404, 'text/plain', '']
            except: return [404, 'text/plain', '']
        try:
            rsp = self.session_get(url, headers=headers, timeout=(5, 15))
            if rsp.status_code != 200: return [404, 'text/plain', '']
            data = rsp.text
            if '#EXT-X-MOUFLON-ADVERT' in data or '#EXT-X-PLAYLIST-TYPE:VOD' in data or '#EXT-X-ENDLIST' in data:
                return [200, 'application/vnd.apple.mpegur', data]
            if '#EXT-X-MOUFLON:URI:' in data:
                data = self.process_m3u8(data)
            return [200, 'application/vnd.apple.mpegur', data]
        except: return [404, 'text/plain', '']

    def process_m3u8(self, content):
        lines = content.strip().split('\n')
        for i, line in enumerate(lines):
            if line.startswith('#EXT-X-MOUFLON:URI:') and 'media.mp4' in lines[i+1]:
                mouflon = line.split(':', 2)[2].strip()
                encrypted = re.sub(r'(_part\d+)?\.mp4$', '', mouflon).rsplit('_', 2)[1]
                new_url = mouflon.replace(encrypted, self._decode(encrypted[::-1], self.stripchat_key))
                lines[i+1] = re.sub(r'https://media-hls\.doppiocdn\.\w+/b-hls-\d+/media\.mp4',
                                    f'{self.getProxyUrl()}&type=media&url={quote(new_url)}', lines[i+1])
            elif line.startswith('#EXT-X-MAP:URI'):
                match = re.search(r'URI=["\']?(https?://[^\s"\'<>]+)["\']?', line)
                if match:
                    original_url = match.group(1)
                    lines[i] = line.replace(original_url, f'{self.getProxyUrl()}&type=media&url={quote(original_url)}')
        return '\n'.join(lines)

    def country_code_to_flag(self, code):
        return ''.join(chr(ord(c.upper()) - ord('A') + 0x1F1E6) for c in code) if len(code) == 2 and code.isalpha() else code

    @staticmethod
    @lru_cache(maxsize=20)
    def _decode(encrypted_b64, key_b64):
        encrypted_b64 += '=' * (4 - len(encrypted_b64) % 4)
        key_bytes, encrypted = base64.b64decode(key_b64), base64.b64decode(encrypted_b64)
        decrypted = bytearray(len(encrypted))
        for i in range(len(encrypted)):
            decrypted[i] = encrypted[i] ^ (key_bytes[i % len(key_bytes)] & 0xFF)
        return decrypted.decode('utf-8')

    def create_session_with_retry(self):
        self.session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.2, status_forcelist=[408, 429, 500, 502, 503, 504])
        self.session.mount('http://', requests.adapters.HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50))
        self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50))

    def session_get(self, url, headers=None, stream=False, timeout=(3, 5)):
        return self.session.get(url, headers=self.headers if headers is None else headers, timeout=timeout, stream=stream, allow_redirects=True)

    def start_danmu(self, room_id):
        try:
            entry = self.danmu_threads.get(room_id)
            if entry and entry[0].is_alive(): return
            for rid, (ot, stop_evt) in list(self.danmu_threads.items()):
                if rid != room_id and ot.is_alive():
                    stop_evt.set(); ot.join(timeout=1.0); del self.danmu_threads[rid]
            stop_event = threading.Event()
            t = threading.Thread(target=self._danmu_poll_worker, args=(room_id, stop_event), daemon=True)
            self.danmu_threads[room_id] = (t, stop_event)
            t.start()
        except: pass

    def _danmu_poll_worker(self, room_id, stop_event):
        while True:
            if stop_event.is_set(): break
            try:
                self.fetch_chat_once(room_id)
                if stop_event.wait(5): break
            except:
                if stop_event.wait(10): break

    def fetch_chat_once(self, room_id):
        path = f'/api/front/v2/models/{room_id}/chat?source=regular&uniq={int(time.time() * 1000)}'
        data = self._request_with_failover(path)
        arr = data.get('messages') if isinstance(data, dict) else []
        if not isinstance(arr, list) or not arr: return 0
        newId, newMsg = 0, []
        with self.danmu_lock:
            cache = self.danmu_cache.get(room_id, {})
            oldId, cacheMsg = cache.get('id', 0), cache.get('msg', [])
            for raw in reversed(arr):
                id = int(raw.get('id', 0))
                if oldId and id <= oldId: break
                if not newId: newId = id
                item = self.normalize_chat_message(raw)
                if item: newMsg.append(item)
            if newId:
                if newMsg:
                    cacheMsg = (newMsg + cacheMsg)[:30]
                self.danmu_cache[room_id] = {'id': newId, 'msg': cacheMsg}
        if oldId:
            for m in reversed(newMsg):
                self.send_live_danmaku(m)
                time.sleep(0.15)
        return len(newMsg)

    def replace_emoji(self, text):
        emoji_map = {':heart:': '❤️', ':dancing:': '💃', ':thumbsup:': '👍', ':flower:': '🌹', ':lol:': '😄',
                     ':flirt:': '😉', ':devil:': '😈', ':hideeyes:': '🙈', ':ask:': '❓', ':inlove:': '😍',
                     ':tongue:': '😛', ':cry:': '😭', ':fire:': '🔥', ':asking:': '🤔', ':wink:': '😉',
                     ':ok:': '👌', ':shy:': '😳', ':angry:': '😡', ':facepalm:': '🤦‍♂️', ':ass:': '🍑'}
        for k, v in emoji_map.items(): text = text.replace(k, v)
        return text

    def normalize_chat_message(self, msg):
        try:
            if not isinstance(msg, dict): return None
            details = msg.get('details') or {}
            text = msg.get('text') or msg.get('message') or msg.get('content') or msg.get('body') or ''
            if not text and isinstance(details, dict):
                text = details.get('body') or details.get('message') or details.get('text') or ''
            if isinstance(text, dict): text = text.get('text') or text.get('body') or ''
            tp = msg.get('type') or ''
            if not text and tp == 'tip':
                amount = details.get('amount') or details.get('tokens') or '' if isinstance(details, dict) else ''
                text = f'打赏 {amount} tk' if amount else '打赏'
            if not text and tp == 'lovense': text = 'Lovense互动'
            ud = msg.get('userData') or msg.get('user') or msg.get('sender') or {}
            user = ''
            if isinstance(ud, dict): user = ud.get('username') or ud.get('name') or ud.get('login') or ''
            elif isinstance(ud, str): user = ud
            if not user: user = msg.get('username') or msg.get('userName') or ''
            text, user = str(text).strip(), str(user).strip()
            if not text: return None
            return {'time': msg.get('createdAt'), 'user': user[:32], 'text': self.replace_emoji(text)[:120]}
        except: return None

    def send_live_danmaku(self, item):
        try:
            text, user = str(item.get('text', '')).strip(), str(item.get('user', '')).strip()
            show = (f'{user}: {text}' if user else text)[:80]
            if not show: return False
            query = f'do=danmaku&text={quote(show)}'
            for base in [self.base_url] if self.base_url else self.get_action_bases():
                try:
                    r = self.session_get(f'{base}/action?{query}', timeout=1)
                    if r and r.status_code == 200 and r.text.strip() == 'OK':
                        self.base_url = base; return True
                except: pass
            return False
        except: return False

    def get_danmaku_desc(self, room_id):
        cache = self.danmu_cache.get(room_id, {})
        msg = []
        for item in cache.get('msg', []):
            t = self.datetime_utc8(item.get('time'), '%H:%M')
            user, text = item.get('user', ''), item.get('text', '')
            msg.append(f'{t} {user}: {text}' if user else f'{t} {text}')
        return '\n'.join(msg)

    def get_action_bases(self):
        bases = []
        try:
            p = urlparse(self.getProxyUrl())
            if p.scheme and p.netloc: bases.append(f'{p.scheme}://{p.netloc}')
        except: pass
        for b in ['http://127.0.0.1:9978', 'http://127.0.0.1:9979']:
            if b not in bases: bases.append(b)
        return bases

    base_url = ''

    def call_local_action(self, query, log_name):
        for base in [self.base_url] if self.base_url else self.get_action_bases():
            try:
                r = self.session_get(f'{base}/action?{query}', timeout=2)
                if r and r.status_code == 200 and r.text.strip() == 'OK':
                    self.base_url = base; return True
            except: pass
        return False