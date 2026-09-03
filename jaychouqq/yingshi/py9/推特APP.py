from base.spider import Spider
import json,random,string,time,requests,hashlib,re
from base64 import b64decode
from urllib.parse import quote,unquote,parse_qs
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

class Spider(Spider):

    PIC_RE = re.compile(r'(?:(?:jpe|image|img|cover|video|pic)/[^\s"\'&,;]+|[\w/\-.]+\.(?:jpg|jpeg|png|gif|webp|bmp))', re.I)

    def getName(self):
        return '推特APP'

    def init(self, extend=""):
        self.hs = ['wcyfhknomg', 'pdcqllfomw', 'alxhzjvean', 'bqeaaxzplt', 'hfbtpixjso']
        self.ua = 'Mozilla/5.0 (Linux; Android 11; M2012K10C Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/87.0.4280.141 Mobile Safari/537.36;SuiRui/twitter/ver=1.4.4'
        self.did = self.getdid()
        self.token, self.phost, self.host = self.gettoken()
        self.api_cache = {}
        self.img_cache = {}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def action(self, action):
        pass

    def destroy(self):
        pass

    def homeContent(self, filter):
        data = self._api('/api/video/classifyList')
        classes = [{'type_name': '精选', 'type_id': 'jx'}]
        for k in data.get('data', []):
            tid = str(k.get('classifyId', ''))
            name = k.get('classifyTitle', '')
            if tid and name:
                classes.append({'type_name': name, 'type_id': tid})
        sort = [{'key': 'fl', 'name': '分类', 'value': [{'n': '最近更新', 'v': '1'}, {'n': '最多播放', 'v': '2'}, {'n': '好评榜', 'v': '3'}]}]
        filters = {c['type_id']: sort for c in classes if c['type_id'] != 'jx'}
        filters['jx'] = [{'key': 'type', 'name': '精选', 'value': [{'n': '日榜', 'v': '1'}, {'n': '周榜', 'v': '2'}, {'n': '月榜', 'v': '3'}, {'n': '总榜', 'v': '4'}]}]
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        return {'list': self.categoryContent('jx', '1', False, {'type': '1'}).get('list', [])}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg or '1')
        ext = self._ext(extend)
        path = '/api/video/queryVideoByClassifyId?pageSize=20&page=%s&classifyId=%s&sortType=%s' % (pg, tid, ext.get('fl', '1'))
        if 'click' in str(tid):
            path = '/api/video/queryPersonVideoByType?pageSize=20&page=%s&userId=%s' % (pg, str(tid).replace('click', ''))
        if tid == 'jx':
            path = '/api/video/getRankVideos?pageSize=20&page=%s&type=%s' % (pg, ext.get('type', '1'))
        data = self._api(path)
        arr = data.get('data', []) if isinstance(data.get('data', []), list) else data.get('videoList', [])
        return {'list': self.items(arr, 'click' in str(tid)), 'page': pg, 'pagecount': 9999, 'limit': 20, 'total': 999999}

    def detailContent(self, array):
        raw = str(array[0])
        if '?' not in raw and '%3f' in raw.lower():
            raw = unquote(raw)
        click = raw.endswith('click')
        if click:
            raw = raw[:-5]
        pp = raw.split('?', 3)
        vid = pp[0] if len(pp) > 0 else raw
        uid = pp[1] if len(pp) > 1 else ''
        nick = unquote(pp[2]) if len(pp) > 2 else '推特APP'
        title = unquote(pp[3]) if len(pp) > 3 else ''
        name = (title or nick or '推特APP').replace('$', '＄')
        clj = nick
        if not click and uid:
            clj = '[a=cr:' + json.dumps({'id': uid + 'click', 'name': nick}) + '/]' + nick + '[/a]'
        vod = {'vod_id': raw, 'vod_name': name, 'vod_pic': '', 'vod_director': clj, 'vod_content': name, 'vod_play_from': '酷鱼专线', 'vod_play_url': name + '$' + vid}
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        data = self._api('/api/search/keyWord?pageSize=20&page=%s&searchWord=%s&searchType=1' % (pg, quote(key)))
        return {'list': self.items(data.get('videoList', []), False), 'page': pg, 'pagecount': 9999, 'limit': 20, 'total': 999999}

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, str(pg or '1'))

    def playerContent(self, flag, id, vipFlags=None):
        vid = str(id)
        data = self.watch(vid)
        ak = data.get('authKey', '')
        vu = data.get('videoUrl', '')
        url = ''
        if ak and vu:
            url = '%s/api/m3u8/decode/authPath?auth_key=%s&path=%s' % (self.host, ak, vu)
        if not url:
            url = data.get('playPath', '') or ''
        return {'parse': 0, 'playUrl': '', 'url': url, 'header': self.headers()}

    def localProxy(self, param):
        tp, u = self.proxy_param(param)
        if not u:
            return [404, 'text/plain', '']
        ct, body = self.img_asset(u)
        return [200, ct or 'image/jpeg', body]

    def items(self, arr, clicked=False):
        res = []
        for k in arr or []:
            cover = k.get('coverImg') or []
            pic = cover[0] if isinstance(cover, list) and cover else cover if isinstance(cover, str) else ''
            vid = str(k.get('videoId', ''))
            uid = str(k.get('userId', ''))
            nick = str(k.get('nickName', ''))
            if not vid:
                continue
            id = '%s?%s?%s?%s' % (vid, uid, quote(nick), quote(k.get('title') or nick or vid))
            if clicked:
                id = id + 'click'
            res.append({'vod_id': id, 'vod_name': k.get('title') or nick or vid, 'vod_pic': self.proxypic(pic), 'vod_remarks': self.dtim(k.get('playTime')), 'style': {'type': 'rect', 'ratio': 1.33}})
        return res

    def _ext(self, extend):
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except Exception:
                return {}
        return extend if isinstance(extend, dict) else {}

    def _api(self, path, post=None):
        url = self.host + path if path.startswith('/') else path
        try:
            key = 'GET:' + url
            if post is not None:
                key = 'POST:' + url
            if key in self.api_cache:
                return self.api_cache[key]
            r = self.req(url, post)
            if r is None:
                return {}
            j = r.json()
            data = self.aes(j.get('encData', '')) if j.get('encData') else j
            if len(self.api_cache) > 80:
                self.api_cache.clear()
            self.api_cache[key] = data
            return data
        except Exception:
            return {}

    def watch(self, vid):
        try:
            url = self.host + '/api/video/can/watch?videoId=%s' % vid
            r = self.req(url, None)
            if r is None:
                return {}
            j = r.json()
            return self.aes(j.get('encData', '')) if j.get('encData') else j
        except Exception:
            return {}

    def req(self, url, post=None):
        headers = self.headers()
        try:
            if post is not None:
                return self.post(url, json=post, headers=headers, timeout=12)
            return self.fetch(url, headers=headers, timeout=12)
        except Exception:
            pass
        try:
            if post is not None:
                return requests.post(url, json=post, headers=headers, timeout=12, verify=False)
            return requests.get(url, headers=headers, timeout=12, verify=False)
        except Exception:
            return None

    def gettoken(self, i=0, max_attempts=10):
        if i >= len(self.hs) or i >= max_attempts:
            return '', '', ''
        line = ''
        try:
            line = self.getCache('twline') or ''
        except Exception:
            line = ''
        if line and i == 0:
            try:
                d, suffix = line.split('|', 1)
                r = self.tryline(d)
                if r[0]:
                    return r
            except Exception:
                pass
        current_domain = 'https://%s.%s.work' % (''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(5, 10))), self.hs[i])
        try:
            r = self.tryline(current_domain)
            if r[0]:
                try:
                    self.setCache('twline', current_domain + '|' + self.did)
                except Exception:
                    pass
                return r
        except Exception:
            pass
        return self.gettoken(i + 1, max_attempts)

    def tryline(self, domain):
        try:
            sign, t = self.getsign()
            headers = {'User-Agent': self.ua, 'Accept': 'application/json', 'deviceid': self.did, 't': t, 's': sign}
            data = {'deviceId': self.did, 'tt': 'U', 'code': '##X-4m6Goo4zzPi1hF##', 'chCode': 'tt09'}
            r = requests.post(domain + '/api/user/traveler', json=data, headers=headers, timeout=6, verify=False)
            r.raise_for_status()
            data1 = r.json()['data']
            if data1.get('token') and data1.get('imgDomain'):
                return data1['token'], data1['imgDomain'], domain
        except Exception:
            pass
        return '', '', ''

    def headers(self):
        sign, t = self.getsign()
        return {'User-Agent': self.ua, 'deviceid': self.did, 't': t, 's': sign, 'aut': self.token}

    def getsign(self):
        t = str(int(time.time() * 1000))
        return self.md5(t), t

    def aes(self, word):
        try:
            key = b64decode('SmhiR2NpT2lKSVV6STFOaQ==')
            iv = key
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(b64decode(word)), AES.block_size)
            return json.loads(decrypted.decode('utf-8'))
        except Exception:
            return {}

    def dtim(self, seconds):
        try:
            seconds = int(seconds or 0)
            hours = seconds // 3600
            remaining_seconds = seconds % 3600
            minutes = remaining_seconds % 3600 // 60
            remaining_seconds = remaining_seconds % 60
            if hours > 0:
                return '%02d:%02d:%02d' % (hours, minutes, remaining_seconds)
            return '%02d:%02d' % (minutes, remaining_seconds)
        except Exception:
            return ''

    def getdid(self):
        did = ''
        try:
            did = self.getCache('did') or ''
        except Exception:
            did = ''
        if not did:
            did = self.md5(str(int(time.time())) + str(random.randint(1000, 9999)))
            try:
                self.setCache('did', did)
            except Exception:
                pass
        return did

    def md5(self, text):
        return hashlib.md5(str(text).encode('utf-8')).hexdigest()

    def proxypic(self, u):
        if not u:
            return ''
        p = ''
        try:
            p = self.getProxyUrl() or ''
        except Exception:
            p = ''
        if 'do=py' not in p:
            p = 'http://127.0.0.1:9978/proxy?do=py'
        elif '/proxy' not in p:
            p = p.replace('?do=py', '/proxy?do=py')
        sep = '&' if '?' in p else '?'
        name = '推特APP'
        try:
            name = self.getName() or '推特APP'
        except Exception:
            pass
        return p + sep + 'type=' + name + '&key=' + name + '&u=' + u + '&url=' + u

    def proxy_param(self, param):
        tp, u = self._param_strict(param)
        if u:
            return tp, u
        vals = []
        try:
            if isinstance(param, dict):
                for k, v in list(param.items()):
                    vals.append(str(v))
                    vals.append(str(k))
            elif param is not None:
                vals.append(str(param))
        except Exception:
            return 'img', ''
        for v in vals:
            try:
                m = self.PIC_RE.search(unquote(v))
                if m:
                    return 'img', m.group(0)
            except Exception:
                continue
        return 'img', ''

    def _param_strict(self, param):
        try:
            if isinstance(param, dict):
                u = param.get('u') or param.get('url') or param.get('img') or param.get('src') or ''
                if u:
                    return param.get('do') or param.get('type') or 'img', unquote(str(u))
                q = parse_qs(str(param.get('query', '') or param.get('params', '') or param.get('param', '') or ''))
            else:
                q = parse_qs(str(param))
            return (q.get('do') or q.get('type') or ['img'])[0], unquote((q.get('u') or q.get('url') or q.get('img') or q.get('src') or [''])[0])
        except Exception:
            return 'img', ''

    def imgurl(self, u):
        if not u:
            return ''
        if str(u).startswith('http'):
            return u
        return (self.phost or '') + u

    def img_asset(self, u):
        if u in self.img_cache:
            return self.img_cache[u]
        try:
            r = self.reqimg(self.imgurl(u))
            if r is None:
                return 'text/plain', b''
            body = self.img(r.content, 100, '2020-zq3-888')
            ct = r.headers.get('Content-Type', 'image/jpeg')
            if len(self.img_cache) > 160:
                self.img_cache.clear()
            self.img_cache[u] = (ct, body)
            return ct, body
        except Exception:
            return 'text/plain', b''

    def reqimg(self, url):
        try:
            return self.fetch(url, headers={'User-Agent': self.ua}, timeout=12)
        except Exception:
            pass
        try:
            return requests.get(url, headers={'User-Agent': self.ua}, timeout=15, verify=False)
        except Exception:
            return None

    def img(self, data, length, key):
        GIF = b'\x47\x49\x46'
        JPG = b'\xFF\xD8\xFF'
        PNG = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'
        if len(data) > 7 and (data[:3] == GIF or data[:3] == JPG or data[1:8] == PNG[1:8]):
            return data
        key_bytes = key.encode('utf-8')
        result = bytearray(data)
        for i in range(min(length, len(result))):
            result[i] ^= key_bytes[i % len(key_bytes)]
        return bytes(result)
