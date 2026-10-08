# -*- coding: utf-8 -*-
"""
泡泡屋 (ppw666.com -> ppw.zloazdb.com) Python Spider 修复版
兼容 FongMi/TV (T3) 与 WebHomeTV / PeekPro (T4)

2026-09-07 修复记录（原 tlobcnv.com 域名已失效）：
- 门户: http://ppw666.com/ (JS 跳转)
- 前端/API: https://ppw.zloazdb.com (Next.js SPA + REST API，旧 tlobcnv.com 已 301)
- API 域名从 /api/app/v1/config 的 app.permanentDomain 动态确认
- 封面CDN: 由 /config 的 domains.image 动态返回 (nvimg.woknyy.cn / mvimg.vzgrqw.cn)
  - 封面文件 = {imageDomain}{coverPath}.log  (coverPath 已含 .jpg 后缀，仍需补 .log)
  - AES-128-CBC 加密 JPEG, key/IV 未变:
    key: 88ce35562a6f085b53a00145444c445f, IV: d005d14d7ce6312ae54527a659be2c55
  - 旧第三方解密代理 backend.appmiaoda.com/.../cover-proxy 已失效(403)，改为本地解密
- 播放CDN: https://idx.jvnmtr.cn (m3u8) / https://segs.jvnmtr.cn (TS分片+AES key)，未变

封面显示方案 (vod_pic)：
- 封面走 FongMi/TVBox localProxy 协议（TVBox 不支持 data URI 作 vod_pic）：
  vod_pic = "http://127.0.0.1:9978/proxy?do=py&url=" + base64(封面文件URL)
  - do=py 路由到爬虫 localProxy()；do=img 走框架内置代理不解密
- localProxy(): self.fetch 下载 .log -> AES-128-CBC 解密(PKCS7) -> 按 magic bytes 定类型
  -> 返回 [200, content_type, content, {Content-Type, Content-Length}]
- 解密三级 fallback: pycryptodome -> cryptography -> ctypes+libcrypto (TVBox 兼容)

认证流程：
- POST /api/app/v1/auth/register {"deviceFingerprint":"web:Linux:zh-CN"} -> JWT token
- 所有业务接口需 Authorization: Bearer <token>
- Token 有效期 2 小时

播放原理：
- playPath 形如 /日期/{hash}/720/{fileid}
- m3u8 URL = https://idx.jvnmtr.cn + playPath去掉最后一段 + /index.m3u8
- m3u8 内 #EXT-X-KEY:METHOD=AES-128,URI="/keys/encX.key" (标准 HLS, TVBox 可直接播放)

会员机制：
- 普通视频: 全部免费
- 合集: unlockCoins 解锁, freeEpisodes (前N集) 免费
"""
import sys
import re
import json
import time

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as rq
    class Spider:
        _session = rq.Session()
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = self._session.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r
        def post(self, url, headers=None, data=None, **kw):
            kw.pop('timeout', None)
            r = self._session.post(url, headers=headers, data=data, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r


class Spider(Spider):
    HOST = 'https://ppw.zloazdb.com'
    API = 'https://ppw.zloazdb.com/api/app/v1'
    # 封面 CDN 由 /config 动态获取；下面为兜底默认值
    IMG_HOST = 'https://nvimg.woknyy.cn'
    M3U8_HOST = 'https://idx.jvnmtr.cn'
    # 封面解密参数 (AES-128-CBC)
    COVER_KEY = bytes.fromhex('88ce35562a6f085b53a00145444c445f')
    COVER_IV = bytes.fromhex('d005d14d7ce6312ae54527a659be2c55')
    def getName(self):
        return "泡泡屋"

    def init(self, extend=''):
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''
        self.host = self.HOST
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self._token = ''
        self._token_time = 0
        self._domains_loaded = False
        # playPath 缓存：vid -> playPath，避免播放时重复请求详情页
        self._play_cache = {}
        # 合集 episodes 缓存：collection_id -> [episode, ...]
        self._ep_cache = {}

    # ========== 域名动态获取 ==========

    def _load_domains(self):
        """从 /config 动态获取封面/播放 CDN 域名，失败时保留默认值"""
        if self._domains_loaded:
            return
        self._domains_loaded = True
        try:
            token = self._ensure_token()
            import requests as rq
            headers = dict(self.header)
            if token:
                headers['Authorization'] = 'Bearer ' + token
            rsp = rq.get(self.API + '/config', headers=headers, timeout=15)
            data = rsp.json()
            domains = (data.get('data') or {}).get('domains') or {}

            # 图片域名 (resource-image)
            for grp in domains.get('image') or []:
                if grp.get('code') == 'resource-image':
                    for dom in grp.get('domains') or []:
                        if dom.get('enabled') and dom.get('value') and dom['value'] != '/':
                            self.IMG_HOST = dom['value'].rstrip('/')
                            break
            # 播放索引域名 (m3u8)
            for grp in domains.get('video') or []:
                if grp.get('code') == 'm3u8':
                    for dom in grp.get('domains') or []:
                        if dom.get('enabled') and dom.get('value'):
                            self.M3U8_HOST = dom['value'].rstrip('/')
                            break
        except Exception:
            pass

    # ========== 认证 ==========

    def _ensure_token(self):
        """确保 token 有效，过期自动重新注册"""
        if self._token and (time.time() - self._token_time < 7000):
            return self._token
        try:
            import requests as rq
            url = self.API + '/auth/register'
            body = json.dumps({'deviceFingerprint': 'web:Linux:zh-CN'})
            rsp = rq.post(url, headers={**self.header, 'Content-Type': 'application/json'},
                          data=body, timeout=15)
            data = rsp.json()
            if data.get('code') == 0:
                self._token = data['data']['token']
                self._token_time = time.time()
                return self._token
        except Exception:
            pass
        return self._token

    def _auth_header(self):
        """返回带 Bearer token 的请求头"""
        token = self._ensure_token()
        h = dict(self.header)
        if token:
            h['Authorization'] = 'Bearer ' + token
        return h

    def _api_get(self, path, params=None):
        """GET 请求 API，自动带 token，失败重试一次"""
        url = self.API + path
        headers = self._auth_header()
        for attempt in range(2):
            try:
                rsp = self.fetch(url, headers=headers, timeout=15)
                data = rsp.json()
                # token 过期时重新注册
                if data.get('code') == 1001 and attempt == 0:
                    self._token = ''
                    self._token_time = 0
                    headers = self._auth_header()
                    continue
                return data
            except Exception:
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                return {}
        return {}

    # ========== 封面图 (localProxy 解密) ==========

    def _cover_url(self, cover_path):
        """
        拼接封面图完整 URL 并走 FongMi/TVBox localProxy 协议：
           vod_pic = "http://127.0.0.1:9978/proxy?do=py&url=" + base64(图片完整URL)
        由爬虫 localProxy() 下载 .log 加密文件 -> AES-128-CBC 解密 -> 返回图片。
        合集封面 coverPath 是完整明文 URL（旧域名 ncp.maimaitom.com 已失效），
        同样提取路径后走 localProxy 解密（加密 .log 版本位于当前可达 CDN）。
        """
        if not cover_path:
            return ''
        if cover_path.startswith('http'):
            # 合集封面 coverPath 是完整明文 URL（旧域名 ncp.maimaitom.com 已失效），
            # 提取路径部分统一走 localProxy 解密：文件实际以加密 .log 形式存在于
            # 可达 CDN（IMG_HOST + 路径 + .log），用与普通封面相同的 AES 参数解密。
            from urllib.parse import urlparse
            cover_path = urlparse(cover_path).path
        if not cover_path.startswith('/'):
            cover_path = '/' + cover_path

        self._load_domains()
        # 注意：coverPath 已含 .jpg/.webp 后缀，取图仍需补 .log（AES 加密文件）
        file_url = self.IMG_HOST + cover_path + '.log'

        import base64
        encoded = base64.urlsafe_b64encode(file_url.encode('utf-8')).decode('ascii')
        return 'http://127.0.0.1:9978/proxy?do=py&url=' + encoded

    def localProxy(self, param):
        """
        TVBox localProxy 入口：do=py 路由到此处。
        下载 AES-128-CBC 加密的封面 .log -> 解密 -> 按 magic bytes 设置 Content-Type 返回。
        返回 [200, content_type, content, {headers}] (FongMi 标准格式)。
        """
        try:
            from urllib.parse import parse_qs
            if isinstance(param, str):
                param_dict = parse_qs(param)
            else:
                param_dict = param

            # 不检查 do 参数, 直接提取 url (FongMi TV 将 do=py 路由到爬虫 localProxy)
            url = param_dict.get('url', '')
            if isinstance(url, list):
                url = url[0] if url else ''

            if url:
                import base64
                # base64 padding 补齐
                url += '=' * (-len(url) % 4)
                try:
                    url = base64.urlsafe_b64decode(url).decode('utf-8')
                except Exception:
                    pass

                if url:
                    headers = {
                        'User-Agent': self.header['User-Agent'],
                        'Referer': self.host + '/',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    }
                    r = self.fetch(url, headers=headers, timeout=15)
                    content = r.content if hasattr(r, 'content') else r.text.encode('utf-8')

                    # AES-128-CBC 加密数据 -> 解密为 JPEG
                    if content and len(content) >= 16 and len(content) % 16 == 0:
                        decrypted = self._aes_decrypt(content)
                        if decrypted:
                            content = decrypted

                    # 按文件头 (magic bytes) 判断真实图片格式
                    content_type = ''
                    if len(content) >= 4:
                        if content[:2] == b'\xff\xd8':
                            content_type = 'image/jpeg'
                        elif content[:4] == b'\x89PNG':
                            content_type = 'image/png'
                        elif content[:4] == b'RIFF':
                            content_type = 'image/webp'
                        elif content[:3] == b'GIF':
                            content_type = 'image/gif'
                    if not content_type:
                        content_type = 'image/jpeg'

                    return [200, content_type, content, {
                        'Content-Type': content_type,
                        'Content-Length': str(len(content)),
                    }]
        except Exception:
            pass
        return [404, 'text/plain', b'', {}]

    def _aes_decrypt(self, encrypted_bytes):
        """AES-128-CBC 解密 (PKCS7 padding), 三级 fallback: pycryptodome -> cryptography -> ctypes+libcrypto"""
        if not encrypted_bytes or len(encrypted_bytes) % 16 != 0:
            return None
        key = self.COVER_KEY
        iv = self.COVER_IV

        # Tier 1: pycryptodome (Crypto)
        try:
            from Crypto.Cipher import AES as _AES
            dec = _AES.new(key, _AES.MODE_CBC, iv).decrypt(encrypted_bytes)
            pad = dec[-1]
            if 1 <= pad <= 16 and dec[-pad:] == bytes([pad]) * pad:
                dec = dec[:-pad]
            return dec
        except Exception:
            pass

        # Tier 2: cryptography
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            dec = decryptor.update(encrypted_bytes) + decryptor.finalize()
            pad = dec[-1]
            if 1 <= pad <= 16 and dec[-pad:] == bytes([pad]) * pad:
                dec = dec[:-pad]
            return dec
        except Exception:
            pass

        # Tier 3: ctypes + libcrypto (OpenSSL EVP, TVBox 设备最可靠)
        try:
            import ctypes
            import ctypes.util
            lib_path = ctypes.util.find_library('crypto')
            if not lib_path:
                for p in ['/system/lib64/libcrypto.so', '/system/lib/libcrypto.so',
                          '/usr/lib/x86_64-linux-gnu/libcrypto.so', '/usr/lib/libcrypto.so']:
                    try:
                        lib = ctypes.CDLL(p)
                        break
                    except Exception:
                        continue
                else:
                    lib = ctypes.CDLL('libcrypto.so')
            else:
                lib = ctypes.CDLL(lib_path)

            lib.EVP_CIPHER_CTX_new.restype = ctypes.c_void_p
            ctx = lib.EVP_CIPHER_CTX_new()
            if not ctx:
                raise Exception('CTX_new failed')

            try:
                lib.EVP_aes_128_cbc.restype = ctypes.c_void_p
                cipher_type = lib.EVP_aes_128_cbc()

                lib.EVP_DecryptInit_ex.argtypes = [
                    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                    ctypes.c_char_p, ctypes.c_char_p]
                lib.EVP_DecryptInit_ex.restype = ctypes.c_int
                lib.EVP_DecryptInit_ex(ctx, cipher_type, None, key, iv)

                lib.EVP_CIPHER_CTX_set_padding.argtypes = [ctypes.c_void_p, ctypes.c_int]
                lib.EVP_CIPHER_CTX_set_padding(ctx, 1)  # PKCS7 padding

                lib.EVP_DecryptUpdate.argtypes = [
                    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                    ctypes.c_void_p, ctypes.c_int]
                lib.EVP_DecryptUpdate.restype = ctypes.c_int
                out_len = ctypes.c_int(0)
                out_buf = ctypes.create_string_buffer(len(encrypted_bytes) + 16)
                if lib.EVP_DecryptUpdate(ctx, out_buf, ctypes.byref(out_len),
                                         encrypted_bytes, len(encrypted_bytes)) != 1:
                    raise Exception('DecryptUpdate failed')

                lib.EVP_DecryptFinal_ex.argtypes = [
                    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
                lib.EVP_DecryptFinal_ex.restype = ctypes.c_int
                final_len = ctypes.c_int(0)
                lib.EVP_DecryptFinal_ex(ctx, ctypes.byref(out_buf, out_len.value),
                                        ctypes.byref(final_len))
                return out_buf.raw[:out_len.value + final_len.value]
            finally:
                lib.EVP_CIPHER_CTX_free(ctx)
        except Exception:
            pass

        return None

    # ========== m3u8 URL 构建 ==========

    def _build_m3u8_url(self, play_path):
        """
        构建 m3u8 直链 URL。
        playPath 形如 /20260904/{hash}/720/{fileid}
        最后一段 fileid 不参与 m3u8 URL，去掉后才返回 200。
        """
        if not play_path:
            return ''
        self._load_domains()
        # 去掉最后一段（fileid），保留目录部分
        m3u8_dir = play_path.rsplit('/', 1)[0] if play_path.count('/') >= 3 else play_path
        return self.M3U8_HOST + m3u8_dir + '/index.m3u8'

    # ========== 视频对象转换 ==========

    def _to_vod(self, item):
        """将 API 视频对象转为 TVBox vod 格式"""
        vod = {
            'vod_id': str(item.get('id', '')),
            'vod_name': item.get('title', ''),
            'vod_pic': self._cover_url(item.get('coverPath', '')),
            'vod_remarks': item.get('duration', ''),
        }
        return vod

    def _to_collection_vod(self, item):
        """将合集对象转为 TVBox vod 格式"""
        episodes = item.get('episodes', 0)
        free_eps = item.get('freeEpisodes', 0)
        unlock_coins = item.get('unlockCoins', 0)
        remark = f'{episodes}集'
        if free_eps > 0:
            remark += f'(免费{free_eps}集)'
        if unlock_coins == 0:
            remark = f'{episodes}集(免费)'
        col_id = 'col_' + str(item.get('id', ''))
        vod = {
            'vod_id': col_id,
            'vod_name': item.get('title', ''),
            'vod_pic': self._cover_url(item.get('coverPath', '')),
            'vod_remarks': remark,
            # TVBox 标准要求每个视频项必须包含 vod_play_url，否则该分类项无法渲染
            'vod_play_url': '播放$' + col_id,
        }
        return vod

    # ========== 首页 ==========

    def homeContent(self, filter):
        """首页分类栏 + 筛选器"""
        from urllib.parse import quote
        classes = []
        filters = {}

        # 固定分类
        classes.append({'type_id': 'all', 'type_name': '最新'})
        classes.append({'type_id': 'hot', 'type_name': '热门'})
        classes.append({'type_id': 'collections', 'type_name': '合集'})

        # 排序筛选器
        sort_filter = {
            'key': 'sort',
            'name': '排序',
            'value': [
                {'n': '最新', 'v': 'time'},
                {'n': '热门', 'v': 'hot'},
            ]
        }
        filters['all'] = [sort_filter]
        filters['hot'] = [sort_filter]
        filters['collections'] = []

        # 获取分类树
        data = self._api_get('/videos/categories')
        cats = (data.get('data') or {}).get('list', [])

        # 只添加主分类，不添加子分类
        # 原因：API 不支持子分类服务端筛选，客户端只过滤当前页 30 条
        for cat in cats:
            type_id = cat.get('name', '')
            type_name = cat.get('name', '')
            classes.append({'type_id': type_id, 'type_name': type_name})
            filters[type_id] = [sort_filter]

        result = {'class': classes, 'filters': filters}
        return result

    def homeVideoContent(self):
        """首页推荐视频"""
        result = {'list': []}
        try:
            # 优先获取今日更新
            data = self._api_get('/home/today')
            items = (data.get('data') or {}).get('list', [])
            if not items:
                data = self._api_get('/videos?sort=time&page=1&pageSize=20')
                items = (data.get('data') or {}).get('list', [])
            result['list'] = [self._to_vod(v) for v in items]
        except Exception:
            pass
        return result

    # ========== 分类列表 ==========

    def categoryContent(self, tid, pg, filter, ext):
        """分类视频列表"""
        from urllib.parse import quote
        page = int(pg) if pg else 1
        if page < 1:
            page = 1

        # 解析筛选参数
        sort = 'time'
        if ext:
            if isinstance(ext, dict):
                sort = ext.get('sort', 'time') or 'time'
            elif isinstance(ext, str):
                try:
                    params = json.loads(ext)
                    sort = params.get('sort', 'time') or 'time'
                except Exception:
                    pass
        if sort not in ('time', 'hot'):
            sort = 'time'

        # 合集分类
        if tid == 'collections':
            data = self._api_get(f'/collections?page={page}&pageSize=30')
            d = data.get('data') or {}
            videos = [self._to_collection_vod(v) for v in d.get('list', [])]
            total = d.get('total', 0)
            page_size = 30
            page_count = max(1, (total + page_size - 1) // page_size) if total else 1
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': page_size,
                'total': total,
            }

        # 热门分类
        if tid == 'hot':
            data = self._api_get(f'/home/hot?sort=plays&page={page}&pageSize=30')
            d = data.get('data') or {}
            videos = [self._to_vod(v) for v in d.get('list', [])]
            total = d.get('total', 0)
            page_size = 30
            page_count = max(1, (total + page_size - 1) // page_size) if total else 1
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': page_size,
                'total': total,
            }

        # 普通分类
        params_list = [f'sort={sort}', f'page={page}', 'pageSize=30']
        if tid and tid != 'all':
            params_list.insert(0, f'category={quote(tid)}')

        url_path = '/videos?' + '&'.join(params_list)
        data = self._api_get(url_path)

        d = data.get('data') or {}
        videos = [self._to_vod(v) for v in d.get('list', [])]

        total = d.get('total', 0)
        page_size = d.get('pageSize', 30)
        page_count = max(1, (total + page_size - 1) // page_size) if total else 1

        return {
            'list': videos,
            'page': page,
            'pagecount': page_count,
            'limit': page_size,
            'total': total,
        }

    # ========== 详情页 ==========

    def detailContent(self, ids):
        """视频详情"""
        vid = str(ids[0]) if ids else ''
        if not vid:
            return {}

        # 合集详情
        if vid.startswith('col_'):
            return self._collection_detail(vid[4:])

        # 普通视频详情
        data = self._api_get(f'/videos/{vid}')
        d = data.get('data') or {}
        if not d:
            return {}

        play_path = d.get('playPath', '')
        if play_path:
            self._play_cache[vid] = play_path

        vod = {
            'vod_id': vid,
            'vod_name': d.get('title', ''),
            'vod_pic': self._cover_url(d.get('coverPath', '')),
            'vod_year': '',
            'vod_area': d.get('category', ''),
            'vod_remarks': d.get('duration', ''),
            'vod_tags': d.get('tag', ''),
            'vod_play_from': '泡泡屋',
            'vod_play_url': '播放$' + vid,
        }

        # 尝试获取推荐
        try:
            rec_data = self._api_get(f'/videos/{vid}/recommend?limit=6')
            rec_items = (rec_data.get('data') or {}).get('list', [])
            if rec_items:
                vod['vod_content'] = '相关推荐：' + '、'.join(
                    v.get('title', '')[:20] for v in rec_items[:3]
                )
        except Exception:
            pass

        return {'list': [vod]}

    def _collection_detail(self, cid):
        """合集详情 - 展示免费剧集列表"""
        data = self._api_get(f'/collections/{cid}')
        d = data.get('data') or {}
        if not d:
            return {}

        # 获取剧集列表
        ep_data = self._api_get(f'/collections/{cid}/episodes')
        episodes = (ep_data.get('data') or {}).get('list', [])
        self._ep_cache[cid] = episodes

        # 构建播放列表：免费剧集
        free_eps = [ep for ep in episodes if ep.get('free')]
        if not free_eps:
            # 如果没有标记免费的，取前10集
            free_eps = episodes[:10]

        play_names = []
        for ep in free_eps:
            idx = ep.get('index', 0)
            title = ep.get('title', f'第{idx}集')
            ep_id = f'col_{cid}_{idx}'
            play_names.append(f'{title}${ep_id}')

        vod = {
            'vod_id': 'col_' + cid,
            'vod_name': d.get('title', ''),
            'vod_pic': self._cover_url(d.get('coverPath', '')),
            'vod_year': d.get('releaseDate', ''),
            'vod_area': '',
            'vod_remarks': f'{d.get("episodes", 0)}集(免费{len(free_eps)}集)',
            'vod_content': d.get('intro', ''),
            'vod_play_from': '免费剧集',
            'vod_play_url': '#'.join(play_names),
        }

        return {'list': [vod]}

    # ========== 播放解析 ==========

    def playerContent(self, flag, id, vipFlags):
        """播放解析 - 返回 m3u8 直链"""
        if not id:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        # 如果 id 以 $ 分隔，取后面的部分
        if '$' in id:
            parts = id.split('$')
            if len(parts) == 2:
                id = parts[1]

        vid = str(id)

        # 合集剧集播放
        if vid.startswith('col_'):
            return self._collection_play(vid)

        # 普通视频播放
        # 优先从缓存取 playPath
        play_path = self._play_cache.get(vid)
        if not play_path:
            try:
                data = self._api_get(f'/videos/{vid}')
                d = data.get('data') or {}
                play_path = d.get('playPath', '')
                if play_path:
                    self._play_cache[vid] = play_path
            except Exception:
                pass

        if not play_path:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        m3u8_url = self._build_m3u8_url(play_path)

        return {
            'parse': 0,
            'playUrl': '',
            'url': m3u8_url,
            'header': {
                'User-Agent': self.header['User-Agent'],
                'Referer': self.host + '/',
            },
            'format': 'application/x-mpegURL',
            'contentType': 'application/x-mpegURL',
        }

    def _collection_play(self, vid):
        """合集剧集播放"""
        # vid 格式: col_{cid}_{episode_index}
        parts = vid.split('_')
        if len(parts) < 3:
            return {'parse': 1, 'playUrl': '', 'url': ''}
        cid = parts[1]
        ep_idx = int(parts[2]) if parts[2].isdigit() else 0

        # 从缓存取 episodes
        episodes = self._ep_cache.get(cid)
        if not episodes:
            ep_data = self._api_get(f'/collections/{cid}/episodes')
            episodes = (ep_data.get('data') or {}).get('list', [])
            self._ep_cache[cid] = episodes

        # 找到对应剧集
        play_path = ''
        for ep in episodes:
            if ep.get('index') == ep_idx:
                play_path = ep.get('playPath', '')
                break

        if not play_path:
            return {'parse': 1, 'playUrl': '', 'url': ''}

        m3u8_url = self._build_m3u8_url(play_path)

        return {
            'parse': 0,
            'playUrl': '',
            'url': m3u8_url,
            'header': {
                'User-Agent': self.header['User-Agent'],
                'Referer': self.host + '/',
            },
            'format': 'application/x-mpegURL',
            'contentType': 'application/x-mpegURL',
        }

    # ========== 搜索 ==========

    def searchContent(self, key, quick, pg):
        """搜索视频"""
        from urllib.parse import quote
        page = int(pg) if pg else 1
        if page < 1:
            page = 1

        try:
            url_path = f'/search?keyword={quote(key)}&type=video&page={page}&pageSize=20'
            data = self._api_get(url_path)
            d = data.get('data') or {}
            videos = [self._to_vod(v) for v in d.get('list', [])]
            total = d.get('total', 0)
            page_size = 20
            page_count = max(1, (total + page_size - 1) // page_size) if total else 1
            return {
                'list': videos,
                'page': page,
                'pagecount': page_count,
                'limit': page_size,
                'total': total,
            }
        except Exception:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 20, 'total': 0}

    # ========== 直播/本地规则（不需要） ==========

    def isLive(self):
        return False

    def manualContent(self, lv):
        return {}