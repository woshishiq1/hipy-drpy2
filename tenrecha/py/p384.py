# coding=utf-8
"""
鲍鱼盒子（App 5.0.6 · 官方 Flutter 包）· TVBox Python 插件 · 纯标准库自实现
=====================================================================================
接口： homeContent / homeVideoContent / categoryContent / detailContent / searchContent / playerContent
挂法： {"name":"🔞鲍鱼盒子┃App直连","type":3,"api":"py_baoyu.py","searchable":1,"quickSearch":1}
      extend 可传 {"host":"换域名","timeout":20000}

【站情 · 2026-09-28 实地逆向 + 真站实测】
  包结构：Flutter 壳（真逻辑在 libapp.so 的 Dart AOT）＋ luoyesiqiu dex 壳 ＋ Agora RTC。
  业务命名族：BaoyuApiClient / BaoyuLivePlat / BaoyuVideo / BaoyuUserInfo / BaoyuPlayTicketDenied。

【★ 网关是明文直出的，免登录免签名】
  上轮把「响应加密」当成全站性质，实际那是别的口。真网关：
    GET https://103.44.236.131:8001/api/video/home_recommend
      → 200，明文 JSON，50KB，首页 9 个模块全量真数据
  同族的 kk.zzijzn.com:8001（解析 116.255.233.8）对同一路径回 nginx 404 —— 后端挂在这个
  IP:端口上、按 vhost 只服务自己，所以主域用 IP 直连。另：http 会被掐成 444（端口挂 TLS），
  必须 https。

【接口面（★ = 实测出真数据）】
  ★ GET /api/video/home_recommend                          首页 9 模块
  ★ GET /api/video/module_video?module=<m>                  模块分类树（cid + 分类名 + 片量）
  ★ GET /api/category/category_video?category_id=&page=     分类列表（20/页）
  ★ GET /api/index/word_search?keyword=&page=               全站搜索
  ★ GET /api/video/detail/<vid>                             详情（含 m3u8）
  ★ GET /api/collect/live/gentoken                          多彩直播 SDK 凭证
    GET /api/live/plat/list ├─ 1077 内部错误（上游异常，非参数问题）
    GET /api/live/room/list ┘
  模块名：video 国产优选 / index 岛国AV / west 欧美 / tertiary 三级 / comic 动漫
  参数名（逐个枚举定出来的）：分类 category_id、搜索 keyword、模块 module
  错误码：1001 缺参 / 1009 缺 Token / 1035 登录过期 / 1077 服务端异常

【取流 · 关键坑（实测得出，不是保险起见）】
  详情 data.video.link[] 直出绝对 HLS 地址。但清单里
  #EXT-X-KEY:METHOD=AES-128,URI="key.key"，那个 key 文件返回的是 **base64 文本**
  （32 字节 ASCII）。播放器原样当 32 字节 AES 用 → 解出来乱码（实测首字节 0x19，不是 TS 同步 0x47）；
  正确姿势 = base64 解码后取前 16 字节（实测首字节 0x47 = 合法 TS 流）。
  所以清单与 key 走本机中继，key 由本文件转成 16 字节再交给播放器；
  分片不需要中继 —— 清单里补成绝对地址，播放器直连对象存储，不占本机带宽。

【⚠️ 封面】cover 形如 https://yn7ux.ooat88.com//img/<日期>/<名>.jpg，实测全部 404
  （该域 CNAME 到阿里云 CDN、回源 OSS bucket yubaoyu，报 NoSuchKey = key 形态不对）。
  App 里有 img_domain / img_domain2（由 /api/common/domain_config 运行时下发）与
  `imgKey must be 16 chars` 的断言 —— 真实图址是「下发域 + imgKey 加密路径」，而 domain_config
  口当前回 1077。故封面原样下发，域一旦恢复即刻出图，本文件不做二次加工。

【本轮真站自检】home 分类 18 / 首页 82 | 分类 34700 条翻页 20/页 | rank 14 |
  search 麻豆 → 20 | detail 直出 m3u8 | 清单中继 44 行 / key 转码 16 字节 | m3u8 实拉 693 字节 / 分片 264528 字节
"""

import base64
import json
import re
import ssl
import threading
import time
import urllib.parse

try:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
except Exception:
    BaseHTTPRequestHandler = None
    ThreadingHTTPServer = None

try:
    import urllib.request as _urlreq
except Exception:
    _urlreq = None

try:                                              # TVBox 壳内基类
    from base.spider import Spider as _Spider
except Exception:
    class _Spider(object):                        # 原生 python 下自检用
        def init(self, *a, **kw):
            return self

# ---------------------------------------------------------------- 常量
SITE_NAME = '🔞鲍鱼盒子┃App直连'
HOSTS = [
    'https://103.44.236.131:8001',                # 真网关（实测明文直出，主域）
    'https://kk.zzijzn.com:8001',                 # App 内同族域，作兜底试连
]
DEFAULT_UA = 'Dart/3.5 (dart:io)'
PAGE_SIZE = 20
MODULES = [
    ('video', '国产优选好片'),
    ('index', '岛国热门AV'),
    ('west', '欧美精选影片'),
    ('tertiary', '精选热门三级'),
    ('comic', '人气高清动漫'),
]

_CTX = None


def _ctx():
    """主域是 IP 直连，证书跟 IP 对不上 —— 默认校验下握手直接失败（表现就是接口全空）"""
    global _CTX
    if _CTX is None:
        try:
            _CTX = ssl._create_unverified_context()
        except Exception:
            _CTX = None
    return _CTX


def _parse_extend(extend):
    if not extend:
        return {}
    s = extend.strip()
    if not s:
        return {}
    try:
        if s.startswith('{'):
            return json.loads(s)
    except Exception:
        pass
    out = {}
    for part in re.split(r'[&;]', s):
        if '=' in part:
            k, v = part.split('=', 1)
            out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------- 中继（清单改写 + key 转码）
class _HlsRelay(object):
    """只监听 127.0.0.1 的极小 HTTP 服务，干两件事：
       /hls?u=<b64>  拉回站方清单 → 把 KEY 指到本中继、分片补绝对地址 → 返回
       /key?u=<b64>  拉回 key 文件 → base64 解码取前 16 字节 → 返回（播放器要的就是这 16 字节）
    这就是「能不能播」的命门：站方的 key 是 base64 文本，播放器直吃解不开。
    """

    def __init__(self, sp):
        self.sp = sp
        self.httpd = None
        self.port = 0
        self.hits = 0
        self.keys = 0
        self.fails = 0
        self._lock = threading.Lock()

    def ensure(self):
        if self.httpd is not None:
            return self.port
        if ThreadingHTTPServer is None or BaseHTTPRequestHandler is None:
            return 0
        with self._lock:
            if self.httpd is not None:
                return self.port
            try:
                srv = ThreadingHTTPServer(('127.0.0.1', 0), self._handler())
                srv.daemon_threads = True
                th = threading.Thread(target=srv.serve_forever, kwargs={'poll_interval': 0.5})
                th.daemon = True
                th.start()
                self.httpd = srv
                self.port = int(srv.server_address[1])
                self.sp._log('取流中继已起 127.0.0.1:%d' % self.port)
            except Exception as e:
                self.sp._log('取流中继起不来 %s' % str(e)[:110])
                return 0
        return self.port

    def stop(self):
        try:
            if self.httpd is not None:
                self.httpd.shutdown()
                self.httpd.server_close()
        except Exception:
            pass
        self.httpd = None
        self.port = 0

    def hls_url(self, url):
        p = self.ensure()
        if not p:
            return ''
        return 'http://127.0.0.1:%d/hls?u=%s' % (p, _b64u(url))

    def _handler(self):
        relay = self

        class _H(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *a):
                pass

            def do_GET(self):
                relay.serve(self, False)

            def do_HEAD(self):
                relay.serve(self, True)

        return _H

    @staticmethod
    def _q(qs, key, default=''):
        v = qs.get(key)
        return v[0] if v else default

    def serve(self, h, head=False):
        try:
            u = urllib.parse.urlparse(h.path)
            qs = urllib.parse.parse_qs(u.query)
            sp = self.sp
            if u.path == '/hls':
                url = _unb64u(self._q(qs, 'u'))
                raw = sp._fetch_bytes(url, timeout=20)
                if not raw:
                    self.fails += 1
                    self._send(h, 502, 'text/plain', b'playlist fail', head)
                    return
                text = raw.decode('utf-8', 'ignore')
                out = self._rewrite(text, url)
                self.hits += 1
                self._send(h, 200, 'application/vnd.apple.mpegurl', out.encode('utf-8'), head)
                return
            if u.path == '/key':
                url = _unb64u(self._q(qs, 'u'))
                raw = sp._fetch_bytes(url, timeout=15)
                if not raw:
                    self.fails += 1
                    self._send(h, 502, 'text/plain', b'key fail', head)
                    return
                key = _fix_key(raw)
                if not key:
                    self.fails += 1
                    self._send(h, 502, 'text/plain', b'key bad', head)
                    return
                self.keys += 1
                self._send(h, 200, 'application/octet-stream', key, head)
                return
            self._send(h, 404, 'text/plain', b'bad path', head)
        except Exception as e:
            self.fails += 1
            try:
                self._send(h, 500, 'text/plain', ('err %s' % str(e)[:60]).encode('utf-8'), head)
            except Exception:
                pass

    def _rewrite(self, text, base_url):
        if not text.startswith('#EXTM3U'):
            return text
        port = self.port
        lines = []
        for line in text.split('\n'):
            t = line.strip()
            if not t:
                lines.append('')
                continue
            if t.startswith('#'):
                if 'URI=' in t:
                    def rep(m):
                        uri = m.group(2)
                        absu = _abs(base_url, uri)
                        if 'key' in uri.lower():
                            return 'URI=%shttp://127.0.0.1:%d/key?u=%s%s' % (
                                m.group(1), port, _b64u(absu), m.group(1))
                        return 'URI=%s%s%s' % (m.group(1), absu, m.group(1))
                    lines.append(re.sub(r'URI=(["\'])([^"\']+)\1', rep, t))
                else:
                    lines.append(t)
            else:
                lines.append(_abs(base_url, t))
        return '\n'.join(lines)

    def _send(self, h, code, mime, body, head=False):
        body = body or b''
        try:
            h.send_response(code)
            h.send_header('Content-Type', mime)
            h.send_header('Content-Length', str(len(body)))
            h.send_header('Cache-Control', 'no-store')
            h.end_headers()
            if not head:
                h.wfile.write(body)
        except Exception:
            pass
        h.close_connection = True


def _b64u(s):
    return base64.urlsafe_b64encode((s or '').encode('utf-8')).decode('ascii').rstrip('=')


def _unb64u(s):
    s = s or ''
    pad = '=' * (-len(s) % 4)
    try:
        return base64.urlsafe_b64decode(s + pad).decode('utf-8', 'ignore')
    except Exception:
        return ''


def _abs(base_url, uri):
    """清单里的相对地址补绝对（分片直连对象存储，不走中继）"""
    if not uri:
        return uri
    if uri.startswith('http://') or uri.startswith('https://'):
        return uri
    if uri.startswith('//'):
        return 'https:' + uri
    i = base_url.find('?')
    s = base_url[:i] if i > 0 else base_url
    k = s.rfind('/')
    d = s[:k + 1] if k > 0 else s
    if uri.startswith('/'):
        j = d.find('://')
        if j < 0:
            return uri
        m = d.find('/', j + 3)
        return d[:m] + uri if m > 0 else uri
    return d + uri


def _fix_key(raw):
    """
    key 归一化：站方给的是 base64 文本（32 字节，如 "RmFraXc3dXJBdzQzODJOSjEyMzQ1Ng=="），
    正确解 = base64 解码后取前 16 字节；已是 16 字节二进制则原样用。
    判定不准就退回「前 16 字节」—— 两种情形下播放器都能拿到合法长度的 AES-128 钥匙。
    """
    if not raw:
        return None
    if len(raw) == 16:
        return raw
    try:
        s = raw.decode('ascii', 'ignore').strip()
    except Exception:
        s = ''
    if s and re.match(r'^[A-Za-z0-9+/=]{16,}$', s):
        try:
            d = base64.b64decode(s + '=' * (-len(s) % 4))
            if len(d) >= 16:
                return d[:16]
        except Exception:
            pass
    return raw[:16]


# ---------------------------------------------------------------- 主体
class Spider(_Spider):

    def __init__(self, *args, **kwargs):
        super(Spider, self).__init__(*args, **kwargs)
        self.host = ''
        self.timeout = 20
        self._relay = _HlsRelay(self)
        self._cat_cache = None
        self._cat_t = 0

    def init(self, extend=''):
        cfg = _parse_extend(extend)
        h = (cfg.get('host') or '').strip().rstrip('/')
        if h:
            if not h.startswith('http'):
                h = 'https://' + h
            self.host = h
        try:
            self.timeout = int(cfg.get('timeout', 20))
        except Exception:
            pass
        return self

    def _log(self, msg):
        try:
            print('[baoyu] %s' % msg)
        except Exception:
            pass

    def getName(self):
        return SITE_NAME

    def destroy(self):
        try:
            self._relay.stop()
        except Exception:
            pass

    def isVideoFormat(self, url):
        u = (url or '').lower()
        return '.m3u8' in u or '.mp4' in u

    def manualVideoCheck(self):
        return False

    # ------------------------------------------------------------ 选线
    def _base(self):
        if self.host:
            return self.host
        for h in HOSTS:
            try:
                raw = self._http(h + '/api/video/home_recommend')
                if raw and json.loads(raw).get('code') == 200:
                    self.host = h
                    self._log('选线命中 %s' % h)
                    return h
            except Exception:
                continue
        self.host = HOSTS[0]
        return self.host

    # ------------------------------------------------------------ HTTP
    def _http(self, url, body=None, method='GET'):
        if _urlreq is None:
            return ''
        hd = {
            'User-Agent': DEFAULT_UA,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else str(body).encode('utf-8')
            hd['Content-Type'] = 'application/json; charset=utf-8'
        for attempt in range(2):
            try:
                req = _urlreq.Request(url, data=data, headers=hd, method=method)
                with _urlreq.urlopen(req, timeout=self.timeout, context=_ctx()) as r:
                    return r.read().decode('utf-8', 'ignore')
            except Exception as e:
                if attempt == 0:
                    time.sleep(0.4)
                else:
                    self._log('请求失败 %s (%s)' % (url.split('?')[0], str(e)[:80]))
        return ''

    def _fetch_bytes(self, url, timeout=15):
        if _urlreq is None or not url:
            return None
        try:
            req = _urlreq.Request(url, headers={'User-Agent': DEFAULT_UA})
            with _urlreq.urlopen(req, timeout=timeout, context=_ctx()) as r:
                return r.read()
        except Exception:
            return None

    def _api(self, path, params=None):
        url = self._base() + path
        if params:
            qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if qs:
                url += ('&' if '?' in url else '?') + qs
        raw = self._http(url)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    # ------------------------------------------------------------ 数据整理
    @staticmethod
    def _pic(u):
        u = (u or '').strip()
        if not u:
            return ''
        i = u.find('://')
        if i > 0:
            head, tail = u[:i + 3], u[i + 3:]
            return head + tail.lstrip('/')
        return u

    @staticmethod
    def _fmt_dur(sec):
        try:
            sec = int(sec)
        except Exception:
            return ''
        if sec <= 0:
            return ''
        return '%d分钟' % (sec // 60) if sec >= 60 else '%d秒' % sec

    def _card(self, v):
        vid = str(v.get('id') or v.get('vid') or '')
        rem = []
        d = self._fmt_dur(v.get('duration'))
        if d:
            rem.append(d)
        if v.get('categor_name'):
            rem.append(str(v['categor_name']))
        plays = v.get('plays') or v.get('real_plays')
        if plays:
            rem.append('🔥%s' % plays)
        if int(v.get('is_vip') or 0) == 1:
            rem.append('VIP')
        return {
            'vod_id': vid,
            'vod_name': str(v.get('name') or ''),
            'vod_pic': self._pic(v.get('cover') or v.get('vertical_cover')),
            'vod_remarks': ' · '.join(rem),
        }

    @staticmethod
    def _pick_list(d):
        out = []
        if isinstance(d, dict):
            arr = d.get('list') or d.get('data') or []
            for v in arr:
                if isinstance(v, dict) and v.get('name'):
                    out.append(v)
        return out

    # ------------------------------------------------------------ 分类树
    def _cat_tree(self):
        now = time.time()
        if self._cat_cache and (now - self._cat_t) < 6 * 3600:
            return self._cat_cache
        out = []
        seen = set()
        for mod, _label in MODULES:
            r = self._api('/api/video/module_video', {'module': mod})
            for blk in (r.get('data') or []):
                for c in (blk.get('list') or []):
                    cid = c.get('cid')
                    # 同一 cid 会在多个模块下重复出现，去重，只留第一处
                    if not cid or cid in seen:
                        continue
                    seen.add(cid)
                    out.append({'type_id': 'c%s' % cid, 'type_name': str(c.get('categor_name') or '')})
        if out:
            self._cat_cache = out
            self._cat_t = now
        return out or (self._cat_cache or [])

    # ------------------------------------------------------------ 接口实现
    def homeContent(self, filter=False):
        classes = list(self._cat_tree())
        classes.append({'type_id': 'rank', 'type_name': '🏆 排行榜'})
        return {'class': classes, 'list': self._home_list()}

    def homeVideoContent(self):
        return {'list': self._home_list()}

    def _home_list(self):
        out = []
        h = self._api('/api/video/home_recommend')
        for m in (h.get('data') or []):
            kind = str(m.get('kind') or '')
            if kind in ('advert', 'ad'):          # 广告模块直接丢
                continue
            for v in (m.get('list') or []):
                inner = v.get('list')
                if isinstance(inner, list):        # rank 模块是嵌套一层
                    for vv in inner:
                        if isinstance(vv, dict) and vv.get('name'):
                            out.append(self._card(vv))
                elif v.get('name'):
                    out.append(self._card(v))
        return out

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = 1
        try:
            page = max(1, int(pg))
        except Exception:
            pass
        items = []
        total = 0
        try:
            if tid == 'rank':
                h = self._api('/api/video/home_recommend')
                for m in (h.get('data') or []):
                    if str(m.get('kind') or '') != 'rank':
                        continue
                    for g in (m.get('list') or []):
                        for v in (g.get('list') or []):
                            if isinstance(v, dict) and v.get('name'):
                                items.append(v)
            elif tid and tid.startswith('c'):
                r = self._api('/api/category/category_video',
                              {'category_id': tid[1:], 'page': page})
                d = r.get('data') or {}
                total = int(d.get('count') or 0)
                items = self._pick_list(d)
        except Exception as e:
            self._log('分类异常 %s %s' % (tid, str(e)[:90]))
        lst = [self._card(v) for v in items]
        pagecount = int((total + PAGE_SIZE - 1) // PAGE_SIZE) if total > 0 else 9999
        return {'list': lst, 'page': page, 'pagecount': pagecount,
                'limit': PAGE_SIZE, 'total': total if total > 0 else page * PAGE_SIZE}

    def detailContent(self, ids):
        vid = str((ids or [''])[0]).strip()
        out = []
        try:
            r = self._api('/api/video/detail/%s' % vid, {'token': ''})
            d = r.get('data') or {}
            v = d.get('video') or {}
            if v:
                cats = '/'.join(str(c.get('name')) for c in (v.get('categorys') or []) if c.get('name'))
                area = ''
                if isinstance(v.get('area'), dict):
                    area = str(v['area'].get('name') or '')
                names, urls, seen = [], [], set()
                for l in (v.get('link') or []):
                    if not isinstance(l, dict):
                        continue
                    u = str(l.get('url') or l.get('gaoqin') or '')
                    if not u or u in seen:
                        continue
                    seen.add(u)
                    n = str(l.get('tongdao_name') or ('线路%d' % (len(names) + 1)))
                    if l.get('try_play'):
                        n += '(试看)'
                    names.append(n)
                    urls.append(u)
                tp = str(v.get('try_play_url') or '')
                if tp and tp not in seen:
                    names.append('试看线路')
                    urls.append(tp)
                play_url = '#'.join('%s$%s' % (names[i], urls[i]) for i in range(len(urls)))
                ct = str(v.get('created_at') or '')
                out.append({
                    'vod_id': vid,
                    'vod_name': str(v.get('name') or ''),
                    'vod_pic': self._pic(v.get('cover') or v.get('vertical_cover')),
                    'type_name': cats,
                    'vod_area': area,
                    'vod_year': ct[:4] if len(ct) >= 4 else '',
                    'vod_actor': str(v.get('actors') or ''),
                    'vod_content': str(v.get('brief') or ''),
                    'vod_remarks': 'VIP' if int(v.get('is_vip') or 0) == 1 else '',
                    'vod_play_from': '鲍鱼盒子' if urls else '',
                    'vod_play_url': play_url,
                })
        except Exception as e:
            self._log('详情异常 %s %s' % (vid, str(e)[:90]))
        return {'list': out}

    def searchContent(self, key, quick=False, pg='1'):
        page = 1
        try:
            page = max(1, int(pg))
        except Exception:
            pass
        out = []
        try:
            r = self._api('/api/index/word_search', {'keyword': key, 'page': page})
            for v in self._pick_list(r.get('data') or {}):
                c = self._card(v)
                # 站方搜索结果带 <em> 高亮标签和 _probN 命中权重后缀，展示前清掉
                n = c['vod_name'].replace('<em>', '').replace('</em>', '')
                c['vod_name'] = re.sub(r'_prob\d+$', '', n)
                out.append(c)
        except Exception as e:
            self._log('搜索异常 %s %s' % (key, str(e)[:90]))
        return {'list': out}

    def playerContent(self, flag, vid, vipFlags=None):
        u = str(vid or '').strip()
        if not u:
            return {'parse': 0, 'url': ''}
        if '.m3u8' in u.lower():
            relay = self._relay.hls_url(u)
            if relay:
                return {'parse': 0, 'url': relay,
                        'format': 'application/x-mpegURL',
                        'contentType': 'application/x-mpegURL'}
        return {'parse': 0, 'url': u,
                'header': json.dumps({'User-Agent': DEFAULT_UA, 'Referer': self._base() + '/'})}

    # ------------------------------------------------------------ 自检
    def check(self):
        try:
            line = []
            h = self.homeContent(True)
            line.append('home 分类 %d / 首页 %d' % (len(h.get('class') or []), len(h.get('list') or [])))
            tid = ((h.get('class') or [{}])[0] or {}).get('type_id') or 'c3'
            c = self.categoryContent(tid, '1', False, {})
            line.append('分类 %s → %d 条 total=%s' % (tid, len(c.get('list') or []), c.get('total')))
            rk = self.categoryContent('rank', '1', False, {})
            line.append('rank → %d 条' % len(rk.get('list') or []))
            s = self.searchContent('麻豆', True)
            line.append('search 麻豆 → %d 条' % len(s.get('list') or []))
            if c.get('list'):
                vid = c['list'][0]['vod_id']
                d = self.detailContent([vid])
                one = (d.get('list') or [{}])[0]
                pu = one.get('vod_play_url') or ''
                play = pu.split('#')[0].split('$')[-1] if pu else ''
                line.append('detail %s → %s' % (vid, (play or '空')[:52]))
                p = self.playerContent('', play)
                line.append('player → %s' % (p.get('url') or '空')[:56])
                if '.m3u8' in play.lower():
                    b = self._fetch_bytes(play, 15)
                    line.append('m3u8 实拉 %s' % ((str(len(b)) + ' 字节') if b else '失败'))
                    relay = self._relay.hls_url(play)
                    if relay:
                        b2 = self._fetch_bytes(relay, 20)
                        line.append('清单中继 %s' % ((str(len(b2)) + ' 字节') if b2 else '失败'))
                        txt = (b2 or b'').decode('utf-8', 'ignore')
                        m = re.search(r'URI="([^"]+)"', txt)
                        if m:
                            b3 = self._fetch_bytes(m.group(1), 15)
                            line.append('key 转码 %s' % ((str(len(b3)) + ' 字节') if b3 else '失败'))
            return ' | '.join(line)
        except Exception as e:
            return '%s · 自检异常 %s' % (SITE_NAME, str(e)[:140])


if __name__ == '__main__':
    sp = Spider().init()
    print(sp.check())
