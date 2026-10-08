# -*- coding: utf-8 -*-
"""
=================================================
  刁民制作，仅供测试，测试完毕请于24小时删除。
=================================================

玩物社区 AI漫剧 标准 Python 源 (TVBox / OK影视 / 影视仓)。

站点: https://thu.ccjxweesh.cc/ai/ai-manju/

特点:
1. 支持 首页/分类/搜索/详情/播放 全流程。
2. 详情页直接解析 _detail_ JSON 与打包脚本, 获取真实 m3u8 直链。
3. 兼容 FongMi/TV (T3) & WebHomeTV / PeekPro (T4)。
"""

import sys
import ast
import json
import re
import time
from urllib.parse import quote

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as rq

    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, **kw)
            r.encoding = 'utf-8'
            return r


class Spider(Spider):
    """
    玩物社区 AI漫剧 Spider
    自定义主题, HTML + JS Packer 解析
    """

    host = 'https://thu.ccjxweesh.cc'

    # CDN 图片 AES-128-CBC 加密参数 (取自前端 lazyload.js)
    _AES_KEY = b'f5d965df75336270'
    _AES_IV = b'97b60394abc2fbe1'

    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': host + '/',
    }

    # 分类列表 (对应 /{type_id}/ 路径)
    classes = [
        {'type_name': 'AI全部', 'type_id': 'ai/all'},
        {'type_name': 'AI成人短剧', 'type_id': 'ai/ai-duanju'},
        {'type_name': 'AI漫剧', 'type_id': 'ai/ai-manju'},
        {'type_name': 'AI换脸', 'type_id': 'ai/ai-huanlian'},
        {'type_name': 'AI美女', 'type_id': 'ai/ai-meinv'},
    ]

    # ===================================================================
    #  基础方法
    # ===================================================================

    def getName(self):
        return '玩物社区AI'

    def init(self, extend=''):
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''

    def isVideoFormat(self, url):
        return any(x in url for x in ['.m3u8', '.mp4', '.flv', '.avi', '.mkv'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ===================================================================
    #  请求封装
    # ===================================================================

    def _fetch_html(self, path):
        """获取页面 HTML"""
        url = path if path.startswith('http') else self.host + path
        r = self.fetch(url, headers=self.header, timeout=15)
        return r.text if hasattr(r, 'text') else r.content.decode('utf-8', errors='ignore')

    # ===================================================================
    #  图片代理
    # ===================================================================

    def _wrap_pic(self, pic_url):
        """将图片 URL 通过 localProxy 代理加载, 修正 CDN 返回的 binary/octet-stream Content-Type"""
        if not pic_url:
            return ''

        pic_url = pic_url.strip()
        if pic_url.startswith(('"', "'")) and pic_url.endswith(('"', "'")):
            pic_url = pic_url[1:-1]

        if pic_url.startswith('//'):
            pic_url = 'https:' + pic_url
        elif not pic_url.startswith(('http://', 'https://')):
            if pic_url.startswith('/'):
                pic_url = self.host + pic_url
            else:
                pic_url = self.host + '/' + pic_url

        # FongMi TV: do=py 路由到 Python 爬虫 localProxy; do=img 走框架内置代理不调用爬虫
        import base64
        encoded = base64.urlsafe_b64encode(pic_url.encode('utf-8')).decode('utf-8')
        return 'http://127.0.0.1:9978/proxy?do=py&url=' + encoded

    # ===================================================================
    #  Dean Edwards JavaScript Packer 解包 (base62)
    # ===================================================================

    @staticmethod
    def _unpack_javascript(block):
        """
        解包 Dean Edwards JavaScript Packer 生成的 eval(...)
        返回解压后的 JS 代码字符串
        """
        try:
            p, a, c, k = Spider._parse_packer_args(block)
            return Spider._unpack(p, a, c, k)
        except Exception:
            return ''

    @staticmethod
    def _parse_packer_args(block):
        """从 eval 块中解析 p, a, c, k"""
        start = block.rfind('}(')
        if start < 0:
            raise ValueError('no args start')
        pos = start + 2

        p, pos = Spider._extract_quoted(block, pos)
        pos = Spider._skip_to(block, pos, ',')
        a = Spider._extract_int(block, pos)
        pos = Spider._skip_to(block, a[1], ',')
        c = Spider._extract_int(block, pos)
        pos = Spider._skip_to(block, c[1], ',')
        k_str, pos = Spider._extract_quoted(block, pos)
        k = k_str.split('|')
        m = re.match(r"\s*\.split\('\|'\)", block[pos:])
        if not m:
            raise ValueError('no split')
        pos += m.end()
        pos = Spider._skip_to(block, pos, ',')
        _ = Spider._extract_int(block, pos)
        pos = Spider._skip_to(block, _[1], ',')
        pos = Spider._skip_to(block, pos, '{')
        pos = Spider._skip_to(block, pos, '}')
        return p, a[0], c[0], k

    @staticmethod
    def _extract_quoted(s, pos):
        """提取 JS 字符串字面量"""
        quote = s[pos]
        if quote not in ('"', "'"):
            raise ValueError('not a string')
        i = pos + 1
        result = []
        while i < len(s):
            c = s[i]
            if c == '\\':
                i += 1
                if i >= len(s):
                    break
                esc = s[i]
                if esc == 'n':
                    result.append('\n')
                elif esc == 't':
                    result.append('\t')
                elif esc == 'r':
                    result.append('\r')
                elif esc == 'b':
                    result.append('\b')
                elif esc == 'f':
                    result.append('\f')
                elif esc == 'x':
                    result.append(chr(int(s[i + 1:i + 3], 16)))
                    i += 2
                elif esc == 'u':
                    result.append(chr(int(s[i + 1:i + 5], 16)))
                    i += 4
                else:
                    result.append(esc)
            elif c == quote:
                return ''.join(result), i + 1
            else:
                result.append(c)
            i += 1
        raise ValueError('unterminated string')

    @staticmethod
    def _extract_int(s, pos):
        m = re.match(r'\s*(\d+)', s[pos:])
        if not m:
            raise ValueError('not an int')
        return int(m.group(1)), pos + m.end()

    @staticmethod
    def _skip_to(s, pos, char):
        while pos < len(s) and s[pos].isspace():
            pos += 1
        if pos >= len(s) or s[pos] != char:
            raise ValueError('expected %s at %d, got %s' % (char, pos, s[pos] if pos < len(s) else 'EOF'))
        return pos + 1

    @staticmethod
    def _unpack(p, a, c, k):
        """执行 base62 替换解压"""
        def encode(num):
            if num < a:
                return _to_digit(num % a)
            return encode(num // a) + _to_digit(num % a)

        def _to_digit(n):
            if n > 35:
                return chr(n + 29)
            return '0123456789abcdefghijklmnopqrstuvwxyz'[n]

        d = {}
        for i in range(c):
            key = encode(i)
            d[key] = k[i] if i < len(k) and k[i] != '' else key

        for i in range(c - 1, -1, -1):
            key = encode(i)
            val = d.get(key, key)
            p = re.sub(r'\b' + re.escape(key) + r'\b', val, p)
        return p

    @staticmethod
    def _extract_eval_block(html, start_marker='eval(function(p,a,c,k,e,d)'):
        """从 HTML 中提取完整的 eval(...) 块"""
        start = html.find(start_marker)
        if start < 0:
            return ''
        depth = 0
        in_str = False
        str_char = ''
        i = start
        while i < len(html):
            c = html[i]
            if in_str:
                if c == '\\':
                    i += 2
                    continue
                if c == str_char:
                    in_str = False
            else:
                if c in ('"', "'", '`'):
                    in_str = True
                    str_char = c
                elif c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        break
            i += 1
        return html[start:i + 1]

    @staticmethod
    def _extract_document_write(unpacked):
        """从解压后的 JS 中提取 document.write 的字符串参数(支持转义引号)"""
        # 优先匹配双引号字符串, 允许内部包含 \"
        m = re.search(r'document\.write\("((?:\\.|[^"\\])*)"\s*\)', unpacked, re.S)
        if not m:
            # 单引号兜底
            m = re.search(r"document\.write\('((?:\\.|[^'\\])*)'\s*\)", unpacked, re.S)
        if not m:
            return ''
        raw = m.group(1)
        try:
            return ast.literal_eval('"' + raw + '"')
        except Exception:
            return raw

    # ===================================================================
    #  首页
    # ===================================================================

    def homeContent(self, filter):
        """返回分类列表"""
        return {'class': self.classes, 'filters': {}}

    def homeVideoContent(self):
        try:
            html = self._fetch_html('/ai/ai-manju/')
            vod_list = self._parse_cards(html)
            return {'list': vod_list[:30]}
        except Exception:
            return {'list': []}

    # ===================================================================
    #  分类内容
    # ===================================================================

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)
            slug = tid

            if pg == 1:
                url = '/%s/' % slug
            else:
                url = '/%s/page/%d/' % (slug, pg)

            html = self._fetch_html(url)
            vod_list = self._parse_cards(html)
            pagecount = self._parse_pagecount(html)

            return {
                'page': pg,
                'pagecount': pagecount,
                'limit': len(vod_list),
                'total': pagecount * 24 if pagecount < 999 else 99999,
                'list': vod_list,
            }
        except Exception:
            return {'page': pg, 'pagecount': 1, 'limit': 20, 'total': 0, 'list': []}

    def _parse_pagecount(self, html):
        """从分页 HTML 中解析总页数"""
        try:
            # 第 <strong>1</strong>/<strong>13</strong> 页
            m = re.search(r'第\s*<[^>]+>(\d+)</[^>]+>\s*/\s*<[^>]+>(\d+)</[^>]+>\s*页', html)
            if m:
                return int(m.group(2))

            # 兜底: 找 /page/数字/
            nums = re.findall(r'/page/(\d+)/', html)
            if nums:
                return max(int(n) for n in nums)

            # 有下一页链接则默认较多页
            if '下一页' in html or '/page/' in html:
                return 999
        except Exception:
            pass
        return 1

    # ===================================================================
    #  详情页
    # ===================================================================

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            detail_path = '/' + vod_id + '/' if not vod_id.startswith('/') else vod_id
            if not detail_path.endswith('/'):
                detail_path += '/'

            html = self._fetch_html(detail_path)

            # 优先使用页面内嵌的 _detail_ JSON
            detail_json = self._extract_detail_json(html)

            if detail_json:
                vod_name = detail_json.get('title', '')
                vod_pic = self._wrap_pic(detail_json.get('poster', ''))
                vod_content = ''
                tags = detail_json.get('tag', [])
                vod_class = ' '.join(str(t) for t in tags[:10])
                vod_remarks = detail_json.get('video_duration', '')
            else:
                # HTML 解析兜底
                vod_name = ''
                title_match = re.search(r'<title>(.*?)</title>', html, re.S)
                if title_match:
                    vod_name = title_match.group(1).strip()
                    vod_name = re.sub(r'\s*[-|]\s*玩物社区.*$', '', vod_name)

                vod_content = ''
                desc_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
                if desc_m:
                    vod_content = desc_m.group(1).strip()

                vod_pic = ''
                og = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', html)
                if og:
                    vod_pic = og.group(1)
                vod_pic = self._wrap_pic(vod_pic)

                vod_class = ''
                tags = re.findall(r'<a[^>]*href="/videos/search/[^"]*"[^>]*>([^<]+)</a>', html)
                if tags:
                    seen = set()
                    clean_tags = []
                    for t in tags:
                        t = t.strip()
                        if t and t not in seen and len(t) < 20:
                            seen.add(t)
                            clean_tags.append(t)
                    vod_class = ' '.join(clean_tags[:8])

                vod_remarks = ''
                remark_m = re.search(r'(\d+\s*(?:月前|天前|小时前|分钟前|周前))\s*发布', html)
                if remark_m:
                    vod_remarks = remark_m.group(1).strip()

            play_from_list = ['AI漫剧']
            play_url_list = ['正片$%s' % vod_id]

            vod = {
                'vod_id': vod_id,
                'vod_name': vod_name,
                'vod_pic': vod_pic,
                'type_name': vod_class or 'AI漫剧',
                'vod_year': '',
                'vod_area': '',
                'vod_actor': '',
                'vod_director': '',
                'vod_content': vod_content,
                'vod_remarks': vod_remarks,
                'vod_play_from': '$$$'.join(play_from_list),
                'vod_play_url': '$$$'.join(play_url_list),
            }
            return {'list': [vod]}
        except Exception:
            return {'list': []}

    def _extract_detail_json(self, html):
        """提取页面内嵌的 _detail_ JSON"""
        try:
            m = re.search(r'const _detail_\s*=\s*(\{.*?\})\s*</script>', html, re.S)
            if m:
                return json.loads(m.group(1))
        except Exception:
            pass
        return {}

    # ===================================================================
    #  搜索
    # ===================================================================

    def searchContent(self, key, quick, pg=1):
        try:
            pg = int(pg or 1)
            encoded_key = quote(key)
            if pg == 1:
                url = '/videos/search/%s/' % encoded_key
            else:
                url = '/videos/search/%s/page/%d/' % (encoded_key, pg)

            html = self._fetch_html(url)
            vod_list = self._parse_cards(html)
            pagecount = self._parse_pagecount(html)

            return {
                'list': vod_list[:30],
                'page': pg,
                'pagecount': pagecount,
            }
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 1}

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    # ===================================================================
    #  播放
    # ===================================================================

    def playerContent(self, flag, id, vipFlags):
        try:
            vod_id = str(id or '')
            if not vod_id:
                return {}

            detail_path = '/' + vod_id + '/' if not vod_id.startswith('/') else vod_id
            if not detail_path.endswith('/'):
                detail_path += '/'

            html = self._fetch_html(detail_path)

            # 优先: 解包页面中的 detail_play 脚本, 获取真实 m3u8
            m3u8_url = self._extract_m3u8_from_detail(html, detail_path)
            if m3u8_url:
                return {
                    'parse': 0,
                    'url': m3u8_url,
                    'header': {
                        'User-Agent': self.header['User-Agent'],
                        'Referer': self.host + '/',
                    },
                }

            # 兜底: 页面中任意 m3u8/mp4 直链
            m3u8 = re.search(r'["\'](https?://[^"\']+\.(?:m3u8|mp4)[^"\']*)["\']', html)
            if m3u8:
                m3u8_url = m3u8.group(1).replace('\\/', '/').replace('&amp;', '&')
                return {
                    'parse': 0,
                    'url': m3u8_url,
                    'header': {
                        'User-Agent': self.header['User-Agent'],
                        'Referer': self.host + '/',
                    },
                }

            # 解析失败则交给外部解析
            return {
                'parse': 1,
                'url': self.host + detail_path,
                'header': {'User-Agent': self.header['User-Agent']},
            }
        except Exception:
            return {}

    def _extract_m3u8_from_detail(self, html, detail_path):
        """
        从详情页解包 detail_play 脚本, 返回 m3u8 直链
        """
        try:
            # 提取 _detail_ 获取 video id
            detail_json = self._extract_detail_json(html)
            if not detail_json:
                return ''
            video_id = detail_json.get('id')
            if not video_id:
                return ''

            # 找到并解包第一个 packed 脚本
            block1 = self._extract_eval_block(html)
            if not block1:
                return ''
            unpacked1 = self._unpack_javascript(block1)
            if not unpacked1:
                return ''

            # 构造 detail_play 请求 URL
            dp_url = self._build_detail_play_url(unpacked1, video_id)
            if not dp_url:
                return ''

            # 请求 detail_play
            dp_html = self._fetch_html(dp_url)
            if not dp_html:
                return ''

            # 解包 detail_play 响应
            block2 = self._extract_eval_block(dp_html)
            if not block2:
                # 也可能响应直接就是 script, 尝试整个内容
                block2 = dp_html
            unpacked2 = self._unpack_javascript(block2)
            if not unpacked2:
                return ''

            # 提取 data-url (属性值在 JS 字符串中, 引号被转义为 \")
            m = re.search(r'data-url=\\"([^"]+)\\"', unpacked2)
            if m:
                return m.group(1).replace('&amp;', '&')

            # 兜底: 任意 m3u8
            m2 = re.search(r'(https?://[^"\'<>\s]+\.m3u8[^"\'<>\s]*)', unpacked2)
            if m2:
                return m2.group(1).replace('&amp;', '&')
        except Exception:
            pass
        return ''

    def _build_detail_play_url(self, unpacked, video_id):
        """
        从解压后的 JS 中提取 detail_play URL 模板并构造最终 URL
        document.write("<script src=\\"/videos/detail_play?id=...&u=\\"+encodeURIComponent(\"TOKEN\")+\"&t=\"+parseInt(...)+\"\\"></script>\"
        """
        try:
            # 提取 <script src=\"URL_TEMPLATE"> 中的 URL 模板
            # 注意: 模板后的引号是 JS 字符串结束符, 不是转义引号
            m = re.search(r'<script\s+src=\\"([^"]+)"', unpacked)
            if not m:
                return ''
            template = m.group(1)

            # 提取 encodeURIComponent 参数 (TOKEN)
            u_match = re.search(r'encodeURIComponent\(["\']([^"\']+)["\']\)', unpacked)
            u_val = u_match.group(1) if u_match else ''

            # 提取时间除数 (parseInt(getTime()/1000/DIVISOR))
            div_match = re.search(r'getTime\(\)/1000/(\d+)', unpacked)
            divisor = int(div_match.group(1)) if div_match else 1800
            t_val = int(time.time() / divisor)

            final = template
            if u_val:
                final += quote(u_val, safe='')
            final += '&t=' + str(t_val)

            if final.startswith('/'):
                final = self.host + final
            return final
        except Exception:
            return ''

    # ===================================================================
    #  本地代理
    # ===================================================================

    def localProxy(self, param):
        """本地代理: do=py 路由到此处, 解密 CDN AES 加密图片"""
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
                # base64 padding 修复: 确保解码前补齐 '='
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

                    # CDN 返回 AES-128-CBC 加密数据, 需解密后才能作为图片显示
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

                    # 兜底: 按文件扩展名判断
                    if not content_type:
                        if '.png' in url:
                            content_type = 'image/png'
                        elif '.webp' in url:
                            content_type = 'image/webp'
                        elif '.gif' in url:
                            content_type = 'image/gif'
                        else:
                            content_type = 'image/jpeg'

                    return [200, content_type, content, {
                        'Content-Type': content_type,
                        'Content-Length': str(len(content)),
                    }]
        except Exception:
            pass
        return [404, 'text/plain', b'', {}]

    def _aes_decrypt(self, encrypted_bytes):
        """AES-128-CBC NoPadding 解密, 三级 fallback"""
        if not encrypted_bytes or len(encrypted_bytes) % 16 != 0:
            return None
        key = self._AES_KEY
        iv = self._AES_IV

        # Tier 1: pycryptodome (Crypto)
        try:
            from Crypto.Cipher import AES as _AES
            cipher = _AES.new(key, _AES.MODE_CBC, iv)
            return cipher.decrypt(encrypted_bytes)
        except Exception:
            pass

        # Tier 2: cryptography
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            return decryptor.update(encrypted_bytes) + decryptor.finalize()
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
                lib.EVP_CIPHER_CTX_set_padding(ctx, 0)

                outlen = ctypes.c_int(0)
                outbuf = ctypes.create_string_buffer(len(encrypted_bytes) + 32)
                lib.EVP_DecryptUpdate.argtypes = [
                    ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int),
                    ctypes.c_char_p, ctypes.c_int]
                lib.EVP_DecryptUpdate.restype = ctypes.c_int
                lib.EVP_DecryptUpdate(ctx, outbuf, ctypes.byref(outlen),
                                      encrypted_bytes, len(encrypted_bytes))

                total = outlen.value
                finallen = ctypes.c_int(0)
                finalbuf = ctypes.create_string_buffer(32)
                lib.EVP_DecryptFinal_ex.argtypes = [
                    ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
                lib.EVP_DecryptFinal_ex.restype = ctypes.c_int
                lib.EVP_DecryptFinal_ex(ctx, finalbuf, ctypes.byref(finallen))
                total += finallen.value

                return outbuf.raw[:total]
            finally:
                lib.EVP_CIPHER_CTX_free.argtypes = [ctypes.c_void_p]
                lib.EVP_CIPHER_CTX_free(ctx)
        except Exception:
            pass

        return None

    # ===================================================================
    #  卡片解析
    # ===================================================================

    def _parse_cards(self, html):
        """解析视频卡片列表 (适配 <div class="video-item" href="...">)"""
        vod_list = []
        seen = set()

        # 匹配 video-item 块, 直到下一个 video-item 或 footer/section
        block_pattern = r'<div\s+class="video-item"\s+href="(/videos/([^/]+)/(vd-[a-zA-Z0-9-]+)/)"\s*>(.*?)(?=<div\s+class="video-item"\s+href=|<footer|<section|<div\s+class="[^"]*pag)'
        matches = re.findall(block_pattern, html, re.S)

        for full_path, cate, vid, block in matches:
            if cate == 'cate' or vid in seen:
                continue
            seen.add(vid)

            # 标题: 优先 img alt, 然后 h2/h3/h4
            name = ''
            alt_m = re.search(r'<img[^>]*alt="([^"]+)"', block)
            if alt_m:
                name = alt_m.group(1).strip()
            if not name:
                h_m = re.search(r'<h[234][^>]*>(.*?)</h[234]>', block, re.S)
                if h_m:
                    name = re.sub(r'<[^>]+>', '', h_m.group(1)).strip()

            # 清理标题尾部时长
            name = re.sub(r'\s+\d{1,2}:\d{2}$', '', name).strip()

            # 图片: 优先 data-src, 再 src
            pic_url = ''
            img_m = re.search(r'<img[^>]*data-src="([^"]+)"', block)
            if img_m:
                pic_url = img_m.group(1)
            if not pic_url:
                img_m = re.search(r'<img[^>]*src="([^"]+)"', block)
                if img_m:
                    pic_url = img_m.group(1)
            pic_url = self._wrap_pic(pic_url)

            # 备注 (时长)
            remark = ''
            remark_m = re.search(r'(\d{1,2}:\d{2})', block)
            if remark_m:
                remark = remark_m.group(1)

            vod_list.append({
                'vod_id': full_path.lstrip('/').rstrip('/'),
                'vod_name': name or vid,
                'vod_pic': pic_url,
                'vod_remarks': remark,
            })

        return vod_list


# =======================================================================
#  本地测试入口
# =======================================================================
if __name__ == '__main__':
    spider = Spider()
    spider.init('')

    print('=== 首页分类 ===')
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))

    print('\n=== 首页推荐 ===')
    print(json.dumps(spider.homeVideoContent(), ensure_ascii=False, indent=2))

    print('\n=== 分类 AI漫剧 第1页 ===')
    print(json.dumps(spider.categoryContent('ai/ai-manju', 1, False, {}), ensure_ascii=False, indent=2))

    print('\n=== 搜索 ===')
    print(json.dumps(spider.searchContent('AI漫剧', False, 1), ensure_ascii=False, indent=2))

    # 取第一个 AI漫剧 视频测详情/播放
    home = spider.homeVideoContent()
    if home.get('list'):
        vid = None
        for item in home['list']:
            if 'ai-manju' in item.get('vod_id', ''):
                vid = item['vod_id']
                break
        if not vid:
            vid = home['list'][0]['vod_id']
        print('\n=== 详情 %s ===' % vid)
        print(json.dumps(spider.detailContent([vid]), ensure_ascii=False, indent=2))
        print('\n=== 播放 %s ===' % vid)
        print(json.dumps(spider.playerContent('AI漫剧', vid, []), ensure_ascii=False, indent=2))
