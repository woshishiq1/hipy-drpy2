#发任意内容到邮箱 91cg@pm.me
import json
import re
import sys
import os
import time
import hashlib
from base64 import b64decode, b64encode
from urllib.parse import quote, unquote

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from pyquery import PyQuery as pq
sys.path.append('..')
from base.spider import Spider as BaseSpider

img_cache = {}

# 同进程内存缓存: 新进程为空 -> 强制拉取最新; 同进程多次调用 -> 走内存, 不重复请求
_mem = {'types': None, 'config': None}

try:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except Exception:
    _BASE_DIR = os.getcwd()


class Spider(BaseSpider):

    # 子分类超长拆行阈值: 单个"类型"筛选超过 8 个选项时拆成 class / class_more1 / class_more2 ...
    _SUB_MAX = 8
    # 分类 tab 顺序偏好表: 元组 (锚点type_id, 目标type_id) 表示目标分类紧跟锚点分类。
    # 例如 [("/category/dydj/", "/category/mrds/")] 表示 AI短剧 紧跟 每日大赛。
    # 未提及的分类保持接口原顺序, 新分类自动排到后面。
    _CLASS_ORDER = []
    # 分类默认子页偏好表: type_id -> 默认子页 URL。
    # 例如实时偷拍默认显示"实时监控" (/category/sstp/live/), 点开即实时监控内容。
    _CLASS_DEFAULT = {
        '/category/sstp/': '/category/sstp/live/',
    }
    # 分类页面内子 tab 偏好表: type_id -> [{n: tab名, v: tabURL}],
    # 注入该分类的"类型"筛选, 便于在 TVBox 内切换子 tab。
    _CLASS_TABS = {
        '/category/sstp/': [
            {'n': '热门推荐', 'v': '/category/sstp/'},
            {'n': '实时监控', 'v': '/category/sstp/live/'},
            {'n': '精彩回放', 'v': '/category/sstp/replay/'},
        ],
    }
    # API 成功拉取后写入 spider_cache.json; API 失败时即使过期也用它兜底
    _CACHE_FILE = os.path.join(_BASE_DIR, 'spider_cache.json')

    def init(self, extend=""):
        try:
            self.proxies = json.loads(extend)
        except:
            self.proxies = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
        }
        self.host = self.get_working_host().rstrip('/')
        self.headers.update({'Origin': self.host, 'Referer': f"{self.host}/"})
        print(f"使用站点: {self.host}")
        # 新进程打开源 -> 强制拉取最新 /types + /config, APP 改动零延迟生效
        self.types = self._load_types()
        self.config = self._load_config()

    def getName(self):
        return "🌈 91吃瓜中心|终极完美版"

    def isVideoFormat(self, url):
        return any(ext in (url or '') for ext in ['.m3u8', '.mp4', '.ts'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        global img_cache
        img_cache.clear()

    def get_working_host(self):
        dynamic_urls = [
            'https://but.ybejhul.com/',
            'https://air.jrozpnrw.cc/',
            'https://adopt.ybejhul.com'
        ]
        for url in dynamic_urls:
            try:
                response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=10)
                if response.status_code == 200:
                    # 节点必须返回真实内容, 跳过空壳/验证页节点
                    if len(self.getpq(response.text)('#index article, article')) > 0:
                        return url
            except Exception:
                continue
        return dynamic_urls[0]

    # ------------------------------------------------------------------
    # 分类/筛选/解析器 动态化核心
    # ------------------------------------------------------------------

    def _fetch_json(self, url, timeout=10):
        response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def _load_types(self):
        data = _mem.get('types')
        if data:
            return data
        # 1. 站点分类接口
        data = self._types_from_api()
        # 2. 本地 spider_cache.json 兜底 (即使过期)
        if not data:
            data = self._read_cache('types')
        # 3. HTML 导航解析兜底 (站点无 API 时仍完整可用)
        if not data:
            data = self._types_from_html()
        if data:
            self._apply_tabs(data)
            _mem['types'] = data
            self._save_cache('types', data)
        return data

    def _apply_tabs(self, types):
        # 把页面内子 tab (如实时偷拍的热门推荐/实时监控/精彩回放) 注入为"类型"筛选
        for c in types.get('class', []):
            tid = c.get('type_id')
            tabs = self._CLASS_TABS.get(tid)
            if not tabs:
                continue
            ext = c.setdefault('type_extend', {})
            if not ext.get('class'):
                ext['class'] = list(tabs)
        return types

    def _types_from_api(self):
        try:
            raw = self._fetch_json(f"{self.host}/types")
            return self._normalize_types(raw)
        except Exception:
            return None

    def _types_from_html(self):
        try:
            response = requests.get(self.host, headers=self.headers, proxies=self.proxies, timeout=15)
            if response.status_code != 200:
                return None
            data = self.getpq(response.text)
            classes = []
            for li in data('nav.navbar .navbar-nav li.category-level-0, nav.navbar .navbar-nav > li').items():
                a = li.children('a').eq(0)
                btn = li.children('button.nav-link').eq(0)
                name = a.text().strip() if a else btn.text().strip()
                if not name:
                    continue
                subs = []
                for sa in li('.dropdown-menu a').items():
                    sh = (sa.attr('href') or '').strip()
                    st = (sa.text() or '').strip()
                    if sh and st:
                        subs.append({'n': st, 'v': sh})
                if a:
                    href = (a.attr('href') or '').strip()
                else:
                    # 下拉分类父项无 href, 指向第一个子分类
                    href = subs[0]['v'] if subs else ''
                if not href or href == '#' or not href.startswith('/category/'):
                    continue
                ext = {'class': subs} if subs else {}
                classes.append({'type_id': href, 'type_name': name, 'type_extend': ext})
            if not classes:
                classes = [{'type_id': '/latest/', 'type_name': '最新', 'type_extend': {}},
                           {'type_id': '/hot/', 'type_name': '热门', 'type_extend': {}}]
            return {'class': classes}
        except Exception:
            return None

    def _normalize_types(self, raw):
        arr = None
        if isinstance(raw, list):
            arr = raw
        elif isinstance(raw, dict):
            for k in ('data', 'list', 'class', 'types', 'rows'):
                if isinstance(raw.get(k), list):
                    arr = raw[k]
                    break
        if not arr:
            return None
        classes = []
        for item in arr:
            if not isinstance(item, dict):
                continue
            tid = item.get('type_id') or item.get('tid') or item.get('id')
            tname = item.get('type_name') or item.get('name')
            if tid is None or not tname:
                continue
            ext = item.get('type_extend') or item.get('extend') or {}
            if isinstance(ext, list):
                ext = {'class': ext}
            classes.append({'type_id': str(tid), 'type_name': str(tname), 'type_extend': ext})
        return {'class': classes} if classes else None

    def _load_config(self):
        data = _mem.get('config')
        if data:
            return data
        # 1. 站点配置接口
        data = self._config_from_api()
        # 2. 本地 spider_cache.json 兜底 (即使过期)
        if not data:
            data = self._read_cache('config')
        # 3. 空配置兜底: 解析器走 TVBox 内置行为
        if not data:
            data = {}
        _mem['config'] = data
        self._save_cache('config', data)
        return data

    def _config_from_api(self):
        try:
            raw = self._fetch_json(f"{self.host}/config")
            return self._normalize_config(raw)
        except Exception:
            return None

    def _normalize_config(self, raw):
        cfg = {}
        if not isinstance(raw, dict):
            return cfg
        parser = raw.get('parser') or raw.get('parse') or raw.get('parse_url')
        if isinstance(parser, dict):
            pu = parser.get('url') or parser.get('api') or parser.get('parse') or ''
            if pu:
                cfg['parser_url'] = pu
        elif isinstance(parser, str):
            if parser:
                cfg['parser_url'] = parser
        elif isinstance(parser, list):
            for p in parser:
                if isinstance(p, dict):
                    pu = p.get('url') or p.get('api') or p.get('parse') or ''
                    if pu:
                        cfg['parser_url'] = pu
                        break
                elif isinstance(p, str) and p:
                    cfg['parser_url'] = p
                    break
        src = raw.get('play_source') or raw.get('playsource') or raw.get('play') or raw.get('source')
        if src:
            cfg['play_source'] = src
        return cfg

    # ---- spider_cache.json 读写 (兜底缓存, 即使过期也使用) ----

    def _read_cache_file(self):
        try:
            with open(self._CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _read_cache(self, key):
        payload = self._read_cache_file()
        ent = payload.get(key)
        if not ent:
            return None
        return ent.get('data')

    def _save_cache(self, key, data):
        try:
            payload = self._read_cache_file()
            payload[key] = {'time': int(time.time()), 'data': data}
            with open(self._CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---- 筛选动态生成 ----

    def _normalize_opts(self, opts):
        items = []
        if isinstance(opts, dict):
            for n, v in opts.items():
                items.append({'n': str(n), 'v': str(v)})
        elif isinstance(opts, list):
            for o in opts:
                if isinstance(o, dict):
                    n = o.get('n') or o.get('name') or o.get('text')
                    v = o.get('v')
                    if v is None:
                        v = o.get('value') or o.get('id') or o.get('href') or n
                    if n is None:
                        continue
                    items.append({'n': str(n), 'v': str(v)})
                elif isinstance(o, (str, int)):
                    items.append({'n': str(o), 'v': str(o)})
        return items

    def _build_filters(self, type_extend):
        filters = []
        ext = type_extend or {}
        for key, label in (('class', '类型'), ('area', '地区'), ('year', '年份'), ('order', '排序')):
            opts = ext.get(key)
            if not opts:
                continue
            items = self._normalize_opts(opts)
            if not items:
                continue
            if key == 'class' and len(items) > self._SUB_MAX:
                chunks = [items[i:i + self._SUB_MAX] for i in range(0, len(items), self._SUB_MAX)]
                for gi, chunk in enumerate(chunks):
                    filters.append({
                        'key': 'class' if gi == 0 else 'class_more%d' % gi,
                        'name': label if gi == 0 else '%s·%d' % (label, gi + 1),
                        'value': [{'n': '全部', 'v': ''}] + chunk,
                    })
            else:
                filters.append({'key': key, 'name': label,
                                'value': [{'n': '全部', 'v': ''}] + items})
        return filters

    # ---- 分类顺序偏好表: 只调顺序不改数据, 未提及的分类保持接口原顺序 ----

    def _reorder_classes(self, classes):
        if not self._CLASS_ORDER or not classes:
            return classes
        arr = [dict(c) for c in classes]
        for anchor, target in self._CLASS_ORDER:
            ids = [c.get('type_id') for c in arr]
            if target not in ids or anchor == target:
                continue
            t_idx = ids.index(target)
            item = arr.pop(t_idx)
            ids = [c.get('type_id') for c in arr]
            if anchor in ids:
                arr.insert(ids.index(anchor) + 1, item)
            elif anchor is None or anchor == '':
                arr.insert(0, item)
            else:
                arr.insert(t_idx, item)
        return arr

    # ------------------------------------------------------------------
    # TVBox 协议接口
    # ------------------------------------------------------------------

    def homeContent(self, filter):
        types = self._load_types() or {'class': []}
        classes = self._reorder_classes(types.get('class', []))
        filters = {}
        for c in classes:
            filters[c.get('type_id')] = self._build_filters(c.get('type_extend'))
        try:
            response = requests.get(self.host, headers=self.headers, proxies=self.proxies, timeout=15)
            if response.status_code != 200:
                return {'class': classes, 'filters': filters, 'list': []}
            data = self.getpq(response.text)
            return {'class': classes, 'filters': filters,
                    'list': self.getlist(data('#index article, article'))}
        except Exception as e:
            return {'class': classes, 'filters': filters, 'list': []}

    def homeVideoContent(self):
        return self.homeContent(True)

    def _extract_filter(self, filter):
        # 兼容 TVBox 各客户端: filter 可能是 dict / JSON字符串 / 布尔 / None
        if isinstance(filter, str):
            try:
                filter = json.loads(filter)
            except Exception:
                return '', {}
        if not isinstance(filter, dict):
            return '', {}
        f = filter
        cls = ''
        for k in ('class', 'class_more1', 'class_more2', 'class_more3', 'class_more4', 'class_more5'):
            if f.get(k):
                cls = f[k]
                break
        params = {}
        for k, v in f.items():
            if not v:
                continue
            if k == 'class' or k.startswith('class_more'):
                continue
            params[k] = v
        return cls, params

    def categoryContent(self, tid, pg, filter, extend):
        try:
            if '@folder' in tid:
                v = self.getfod(tid.replace('@folder', ''))
                return {'list': v, 'page': 1, 'pagecount': 1, 'limit': 90, 'total': len(v)}

            try:
                pg = int(pg)
            except (TypeError, ValueError):
                pg = 1
            if pg < 1:
                pg = 1
            # 兼容客户端传参: 多数客户端把筛选放 filter(dict/JSON字符串),
            # 影视仓/小苹果等把筛选放 extend 而 filter 只传 True/False
            f = filter
            if isinstance(extend, dict) and extend:
                if not isinstance(f, dict):
                    f = extend
                else:
                    f = {**extend, **f}
            cls, params = self._extract_filter(f)
            cls = unquote(cls)  # 兼容客户端对筛选值做 URL 编码

            # 无筛选时应用分类默认子页 (如实时偷拍默认显示"实时监控")
            if not cls and tid in self._CLASS_DEFAULT:
                tid = self._CLASS_DEFAULT[tid]

            if cls and (cls.startswith('http') or cls.startswith('/')):
                base_url = self._abs(cls).rstrip('/')
            else:
                if cls:
                    params['class'] = cls
                if tid.startswith('http'):
                    base_url = tid.rstrip('/')
                else:
                    path = tid if tid.startswith('/') else f"/{tid}"
                    base_url = f"{self.host}{path}".rstrip('/')

            if pg == 1:
                url = f"{base_url}/"
            else:
                url = f"{base_url}/{pg}/"

            if params:
                qs = '&'.join('%s=%s' % (k, quote(str(v))) for k, v in params.items())
                url = f"{url}?{qs}"

            response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=15)
            if response.status_code != 200:
                return {'list': [], 'page': pg, 'pagecount': 9999, 'limit': 90, 'total': 0}

            data = self.getpq(response.text)
            videos = self.getlist(data('#archive article, #index article, article, a.realtime-card'), tid)

            return {'list': videos, 'page': pg, 'pagecount': 9999, 'limit': 90, 'total': 999999}
        except Exception as e:
            return {'list': [], 'page': pg, 'pagecount': 9999, 'limit': 90, 'total': 0}

    def detailContent(self, ids):
        try:
            url = ids[0] if ids[0].startswith('http') else f"{self.host}{ids[0]}"
            response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=15)
            data = self.getpq(response.text)

            plist = []
            used_names = set()
            if data('.dplayer'):
                for c, k in enumerate(data('.dplayer').items(), start=1):
                    try:
                        config_attr = k.attr('data-config')
                        if config_attr:
                            config = json.loads(config_attr)
                            video_url = config.get('video', {}).get('url', '')

                            if video_url:
                                ep_name = ''
                                parent = k.parents().eq(0)
                                for _ in range(4):
                                    if not parent: break
                                    heading = parent.find('h2, h3, h4').eq(0).text().strip()
                                    if heading:
                                        ep_name = heading
                                        break
                                    parent = parent.parents().eq(0)

                                base_name = ep_name if ep_name else f"视频{c}"
                                name = base_name
                                count = 2
                                while name in used_names:
                                    name = f"{base_name} {count}"
                                    count += 1
                                used_names.add(name)

                                plist.append(f"{name}${video_url}")
                    except: continue

            if not plist:
                content_area = data('.post-content, article')
                for i, link in enumerate(content_area('a').items(), start=1):
                    link_text = link.text().strip()
                    link_href = link.attr('href')

                    if link_href and any(kw in link_text for kw in ['点击观看', '观看', '播放', '视频', '第一弹', '第二弹', '第三弹', '第四弹', '第五弹', '第六弹', '第七弹', '第八弹', '第九弹', '第十弹']):
                        ep_name = link_text.replace('点击观看：', '').replace('点击观看', '').strip()
                        if not ep_name: ep_name = f"视频{i}"

                        if not link_href.startswith('http'):
                            link_href = f"{self.host}{link_href}" if link_href.startswith('/') else f"{self.host}/{link_href}"

                        plist.append(f"{ep_name}${link_href}")

            play_url = '#'.join(plist) if plist else f"未找到视频源${url}"

            vod_content = ''
            try:
                tags = []
                seen_names = set()
                seen_ids = set()

                tag_links = data('.tags a, .keywords a, .post-tags a')

                candidates = []
                for k in tag_links.items():
                    title = k.text().strip()
                    href = k.attr('href')
                    if title and href:
                        candidates.append({'name': title, 'id': href})

                candidates.sort(key=lambda x: len(x['name']), reverse=True)

                for item in candidates:
                    name = item['name']
                    id_ = item['id']

                    if id_ in seen_ids: continue

                    is_duplicate = False
                    for seen in seen_names:
                        if name in seen:
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        target = json.dumps({'id': id_, 'name': name})
                        tags.append(f'[a=cr:{target}/]{name}[/a]')
                        seen_names.add(name)
                        seen_ids.add(id_)

                if tags:
                    vod_content = ' '.join(tags)
                else:
                    vod_content = data('.post-title').text()
            except Exception:
                vod_content = '获取标签失败'

            if not vod_content:
                vod_content = data('h1').text() or '91吃瓜中心'

            return {'list': [{'vod_play_from': '91吃瓜中心', 'vod_play_url': play_url, 'vod_content': vod_content}]}
        except:
            return {'list': [{'vod_play_from': '91吃瓜中心', 'vod_play_url': '获取失败'}]}

    def searchContent(self, key, quick, pg="1"):
        try:
            try:
                pg = int(pg)
            except (TypeError, ValueError):
                pg = 1
            if pg < 1:
                pg = 1

            if pg == 1:
                url = f"{self.host}/search/{key}/"
            else:
                url = f"{self.host}/search/{key}/{pg}/"

            response = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=15)
            return {'list': self.getlist(self.getpq(response.text)('article')), 'page': pg, 'pagecount': 9999}
        except:
            return {'list': [], 'page': pg, 'pagecount': 9999}

    def playerContent(self, flag, id, vipFlags):
        parser_url = (self.config or {}).get('parser_url') or ''
        if parser_url and not self.isVideoFormat(id):
            return {'parse': 1, 'url': parser_url + quote(str(id), safe=''), 'header': self.headers}
        parse = 0 if self.isVideoFormat(id) else 1
        url = self.proxy(id) if '.m3u8' in id else id
        return {'parse': parse, 'url': url, 'header': self.headers}

    def localProxy(self, param):
        try:
            type_ = param.get('type')
            url = param.get('url')
            if type_ == 'cache':
                key = param.get('key')
                if content := img_cache.get(key):
                    return [200, 'image/jpeg', content]
                return [404, 'text/plain', b'Expired']
            elif type_ == 'img':
                real_url = self.d64(url) if not url.startswith('http') else url
                res = requests.get(real_url, headers=self.headers, proxies=self.proxies, timeout=10)
                content = self.aesimg(res.content)
                return [200, 'image/jpeg', content]
            elif type_ == 'm3u8':
                return self.m3Proxy(url)
            else:
                return self.tsProxy(url)
        except:
            return [404, 'text/plain', b'']

    def proxy(self, data, type='m3u8'):
        if data and self.proxies: return f"{self.getProxyUrl()}&url={self.e64(data)}&type={type}"
        return data

    def m3Proxy(self, url):
        url = self.d64(url)
        res = requests.get(url, headers=self.headers, proxies=self.proxies)
        data = res.text
        base = res.url.rsplit('/', 1)[0]
        lines = []
        for line in data.split('\n'):
            if '#EXT' not in line and line.strip():
                if not line.startswith('http'):
                    line = f"{base}/{line}"
                lines.append(self.proxy(line, 'ts'))
            else:
                lines.append(line)
        return [200, "application/vnd.apple.mpegurl", '\n'.join(lines)]

    def tsProxy(self, url):
        return [200, 'video/mp2t', requests.get(self.d64(url), headers=self.headers, proxies=self.proxies).content]

    def e64(self, text):
        return b64encode(str(text).encode()).decode()

    def d64(self, text):
        return b64decode(str(text).encode()).decode()

    def aesimg(self, data):
        if len(data) < 16: return data
        keys = [(b'f5d965df75336270', b'97b60394abc2fbe1'), (b'75336270f5d965df', b'abc2fbe197b60394')]
        for k, v in keys:
            try:
                dec = unpad(AES.new(k, AES.MODE_CBC, v).decrypt(data), 16)
                if dec.startswith(b'\xff\xd8') or dec.startswith(b'\x89PNG'): return dec
            except: pass
            try:
                dec = unpad(AES.new(k, AES.MODE_ECB).decrypt(data), 16)
                if dec.startswith(b'\xff\xd8'): return dec
            except: pass
        return data

    def getlist(self, data, tid=''):
        videos = []
        is_folder = '/mrdg' in (tid or '')
        for k in data.items():
            card_html = k.outer_html() if hasattr(k, 'outer_html') else str(k)
            if k.is_('a.realtime-card') or 'realtime-card' in (k.attr('class') or ''):
                # 实时偷拍等独立模板: <a class="realtime-card" href="..." aria-label="标题">
                href = k.attr('href')
                title = k.attr('aria-label') or k('img').attr('alt') or ''
                if href and title:
                    # 真实封面在 data-xkrkllgl, src 只是占位图, 需优先取
                    img_attr = k('img').attr('data-xkrkllgl') or k('img').attr('data-src') or ''
                    pic = self._proc_url(img_attr) if img_attr else self.getimg('', k, card_html)
                    videos.append({
                        'vod_id': href,
                        'vod_name': title.strip(),
                        'vod_pic': pic,
                        'vod_remarks': k('.realtime-card__status').text().strip() or '',
                        'vod_tag': '',
                        'style': {"type": "rect", "ratio": 1.33}
                    })
                continue
            a = k if k.is_('a') else k('a').eq(0)
            href = a.attr('href')
            title = k('h2').text() or k('.entry-title').text() or k('.post-title').text()
            if not title and k.is_('a'): title = k.text()

            if href and title:
                img = self.getimg(k('script').text(), k, card_html)
                videos.append({
                    'vod_id': f"{href}{'@folder' if is_folder else ''}",
                    'vod_name': title.strip(),
                    'vod_pic': img,
                    'vod_remarks': k('time').text() or '',
                    'vod_tag': 'folder' if is_folder else '',
                    'style': {"type": "rect", "ratio": 1.33}
                })
        return videos

    def getfod(self, id):
        url = f"{self.host}{id}"
        data = self.getpq(requests.get(url, headers=self.headers, proxies=self.proxies).text)
        videos = []
        for i, h2 in enumerate(data('.post-content h2').items()):
            p_txt = data('.post-content p').eq(i * 2)
            p_img = data('.post-content p').eq(i * 2 + 1)
            p_html = p_img.outer_html() if hasattr(p_img, 'outer_html') else str(p_img)
            videos.append({
                'vod_id': p_txt('a').attr('href'),
                'vod_name': p_txt.text().strip(),
                'vod_pic': self.getimg('', p_img, p_html),
                'vod_remarks': h2.text().strip()
            })
        return videos

    def getimg(self, text, elem=None, html_content=None):
        if m := re.search(r"loadBannerDirect\('([^']+)'", text or ''):
            return self._proc_url(m.group(1))

        if html_content is None and elem is not None:
             html_content = elem.outer_html() if hasattr(elem, 'outer_html') else str(elem)
        if not html_content: return ''

        html_content = html_content.replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&')

        if 'data:image' in html_content:
            m = re.search(r'(data:image/[a-zA-Z0-9+/=;,]+)', html_content)
            if m: return self._proc_url(m.group(1))

        m = re.search(r'(https?://[^"\'\s)]+\.(?:jpg|png|jpeg|webp))', html_content, re.I)
        if m: return self._proc_url(m.group(1))

        if 'url(' in html_content:
            m = re.search(r'url\s*\(\s*[\'"]?([^"\'\)]+)[\'"]?\s*\)', html_content, re.I)
            if m: return self._proc_url(m.group(1))

        return ''

    def _proc_url(self, url):
        if not url: return ''
        url = url.strip('\'" ')
        if url.startswith('data:'):
            try:
                _, b64_str = url.split(',', 1)
                raw = b64decode(b64_str)
                if not (raw.startswith(b'\xff\xd8') or raw.startswith(b'\x89PNG') or raw.startswith(b'GIF8')):
                    raw = self.aesimg(raw)
                key = hashlib.md5(raw).hexdigest()
                img_cache[key] = raw
                return f"{self.getProxyUrl()}&type=cache&key={key}"
            except: return ""
        if not url.startswith('http'):
            url = f"{self.host}{url}" if url.startswith('/') else f"{self.host}/{url}"
        return f"{self.getProxyUrl()}&url={self.e64(url)}&type=img"

    def _abs(self, path):
        if not path:
            return self.host
        if path.startswith('http'):
            return path
        return f"{self.host}{path}" if path.startswith('/') else f"{self.host}/{path}"

    def getpq(self, data):
        try: return pq(data)
        except: return pq(data.encode('utf-8'))
