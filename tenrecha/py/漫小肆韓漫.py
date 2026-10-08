#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
漫小肆韓漫 Spider (jjmhw8.top / freexcomic.com)
- 一级: 全部 / 排行
- 全部: filters = 状态 + 标签 + 地区（状态置顶）
- 排行: filters = 新番榜 / 人气榜 / 完结榜
- 搜索: /search?keyword=xxx
- 列表: 多容器 + <a><li> 结构 + 全页 /book/ 兜底 + ul.book-list 支持
- 详情/二级: 保持原实现
- 翻页优化: 提升封面并发、减小封面尺寸、短超时、加列表结果缓存
"""
import re
import io
import json
import base64
import requests
from urllib.parse import urljoin, quote, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from base.spider import Spider

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


class Spider(Spider):
    VERSION_PREFIX = 'mxs_'

    # ========= 图片策略 =========
    COVER_B64 = True
    COVER_W = 240
    COVER_Q = 65
    CONC_COVER = 32

    CHAP_B64 = False
    CHAP_W = 800
    CHAP_Q = 72
    CONC_CHAP = 24

    PLAY_MAX_IMAGES = 0

    TIMEOUT = 12
    TIMEOUT_IMG = 5

    JUNK_KEYS = ('logo', 'avatar', 'favicon', 'placeholder', 'spacer',
                 'blank.gif', 'loading', 'qrcode', 'share', 'banner',
                 'icon', 'header-logo', 'mmrtx')

    def getName(self):
        return '漫小肆韓漫'

    # ==================== 初始化 ====================
    def init(self, extend=''):
        self.host = 'https://www.jjmhw8.top'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Referer': self.host + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                      'image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=128, pool_maxsize=128, max_retries=0)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

        self._html_cache = {}
        self._detail_cache = {}
        self._chapter_cache = {}
        self._b64_cache = {}
        self._list_cache = {}

        try:
            e = json.loads(extend) if isinstance(extend, str) and extend.strip().startswith('{') else {}
            p = e.get('proxy', '')
            if p:
                if not p.startswith('http'):
                    p = 'http://' + p
                self.session.proxies.update({'http': p, 'https': p})
            if 'cover_b64' in e:
                self.COVER_B64 = bool(e['cover_b64'])
            if 'chap_b64' in e:
                self.CHAP_B64 = bool(e['chap_b64'])
            if e.get('host'):
                self.host = str(e['host']).rstrip('/')
        except Exception:
            pass

        self.classes = []
        self.filters = {}
        self._load_classes()

        print(f'[漫小肆] init host={self.host} classes={len(self.classes)} '
              f'cover_b64={self.COVER_B64} chap_b64={self.CHAP_B64} pil={_HAS_PIL}')

    # ==================== 基础工具 ====================
    def _real_id(self, vid):
        vid = str(vid)
        return vid[len(self.VERSION_PREFIX):] if vid.startswith(self.VERSION_PREFIX) else vid

    def _fix(self, u):
        if not u:
            return ''
        u = str(u).strip().replace('&amp;', '&')
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http://') or u.startswith('https://'):
            return u
        return urljoin(self.host + '/', u)

    def _clean(self, t):
        if t is None:
            return ''
        return re.sub(r'\s+', ' ',
                      str(t).replace('\xa0', ' ').replace('\u3000', ' ')).strip()

    def _http_get(self, u, timeout=None, use_cache=True):
        full = self._fix(u)
        if use_cache and full in self._html_cache:
            return self._html_cache[full]
        try:
            r = self.session.get(full, timeout=timeout or self.TIMEOUT,
                                 verify=False,
                                 proxies=self.session.proxies or None,
                                 allow_redirects=True)
            if not r.encoding or r.encoding.lower() in ('iso-8859-1', 'ascii'):
                r.encoding = 'utf-8'
            text = r.text or ''
            print(f'[漫小肆] GET {full} -> {r.status_code} len={len(text)}')
            if r.status_code == 200 and len(text) > 200 and use_cache:
                self._html_cache[full] = text
            return text
        except Exception as e:
            print(f'[漫小肆] 请求异常 {full} {e}')
            return ''

    # ==================== 图片工具 ====================
    def _ok_img(self, u):
        if not u:
            return False
        low = u.lower()
        if low.startswith('data:') or 'base64' in low:
            return False
        if not re.search(r'\.(jpg|jpeg|png|gif|webp|avif)', low):
            return False
        for k in self.JUNK_KEYS:
            if k in low:
                return False
        return True

    def _pick_img(self, img):
        if img is None:
            return ''
        for attr in ('data-original', 'data-src', 'data-lazy-src',
                     'data-echo', 'data-url', 'src'):
            v = img.get(attr)
            if not v:
                continue
            v = str(v).strip().replace('&amp;', '&')
            if v.startswith('data:') or 'base64' in v.lower():
                continue
            v = self._fix(v)
            if self._ok_img(v):
                return v
        ss = img.get('srcset') or ''
        if ss:
            first = ss.split(',')[0].strip().split(' ')[0]
            v = self._fix(first)
            if self._ok_img(v):
                return v
        return ''

    def _compress(self, raw_bytes, max_w, quality):
        if not (_HAS_PIL and max_w > 0):
            return raw_bytes, None
        try:
            im = Image.open(io.BytesIO(raw_bytes))
            if im.mode in ('RGBA', 'P', 'LA'):
                bg = Image.new('RGB', im.size, (255, 255, 255))
                im = im.convert('RGBA')
                bg.paste(im, mask=im.split()[-1])
                im = bg
            elif im.mode != 'RGB':
                im = im.convert('RGB')
            w, h = im.size
            if w > max_w:
                nh = int(h * max_w / w)
                im = im.resize((max_w, nh), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format='JPEG', quality=quality, optimize=True)
            return buf.getvalue(), 'image/jpeg'
        except Exception as e:
            print(f'[漫小肆] 压缩失败 {e}')
            return raw_bytes, None

    def _fetch_b64(self, url, max_w, quality, max_kb=0):
        if not url:
            return ''
        key = f'{max_w}_{quality}_{max_kb}|{url}'
        if key in self._b64_cache:
            return self._b64_cache[key]
        h = {
            'User-Agent': self.headers['User-Agent'],
            'Referer': self.host + '/',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        }
        try:
            r = self.session.get(url, headers=h, timeout=self.TIMEOUT_IMG,
                                 verify=False, allow_redirects=True, stream=True)
            if max_kb > 0:
                cl = r.headers.get('Content-Length')
                if cl and cl.isdigit() and int(cl) > max_kb * 1024:
                    r.close()
                    self._b64_cache[key] = url
                    return url
            if r.status_code != 200:
                r.close()
                return url
            chunks, total = [], 0
            limit = max_kb * 1024 if max_kb > 0 else 0
            for chunk in r.iter_content(32 * 1024):
                if not chunk:
                    continue
                chunks.append(chunk)
                total += len(chunk)
                if limit and total > limit:
                    r.close()
                    self._b64_cache[key] = url
                    return url
            r.close()
            raw = b''.join(chunks)
            if len(raw) < 500:
                return url
            data, forced_ct = self._compress(raw, max_w, quality)
            ct = forced_ct or r.headers.get('Content-Type', '') or 'image/jpeg'
            if 'image' not in ct.lower():
                ct = 'image/jpeg'
            b64 = base64.b64encode(data).decode('ascii')
            uri = f'data:{ct};base64,{b64}'
            self._b64_cache[key] = uri
            return uri
        except Exception as e:
            print(f'[漫小肆] b64 异常 ...{url[-40:]} {e}')
        return url

    def _batch_b64(self, urls, max_w, quality, workers, max_kb=0):
        if not urls:
            return []
        results = [None] * len(urls)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(self._fetch_b64, u, max_w, quality, max_kb): i
                    for i, u in enumerate(urls)}
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    results[i] = fut.result()
                except Exception:
                    results[i] = urls[i]
        return [results[i] if results[i] else urls[i] for i in range(len(urls))]

    # ==================== 分类加载 ====================
    def _load_classes(self):
        self.classes = [
            {'type_name': '全部', 'type_id': '/booklist'},
            {'type_name': '排行', 'type_id': '/rank'},
        ]

        tags = ['青春', '性感', '长腿', '多人', '御姐', '巨乳', '新婚',
                '媳妇', '暧昧', '清纯', '调教', '少妇', '风骚', '同居',
                '淫乱', '好友', '女神', '诱惑', '偷情', '出轨', '正妹', '家教']

        html = self._http_get('/tag', use_cache=False)
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            for a in soup.select('ul.search-class li a[href]'):
                href = a.get('href', '').strip()
                m = re.search(r'tag=([^&]+)', href)
                if not m:
                    continue
                t = unquote(m.group(1)).strip()
                if t and t not in tags:
                    tags.append(t)

        tag_values = [{'n': '全部', 'v': '全部'}]
        for t in tags:
            tag_values.append({'n': t, 'v': t})

        self.filters = {
            '/booklist': [
                {'key': 'status', 'name': '状态', 'value': [
                    {'n': '全部',   'v': '-1'},
                    {'n': '连载中', 'v': '0'},
                    {'n': '已完结', 'v': '1'},
                ]},
                {'key': 'tag', 'name': '标签', 'value': tag_values},
                {'key': 'area', 'name': '地区', 'value': [
                    {'n': '全部', 'v': '-1'},
                    {'n': '韩国', 'v': '1'},
                    {'n': '日本', 'v': '2'},
                    {'n': '台湾', 'v': '3'},
                ]},
            ],
            '/rank': [
                {'key': 'tab', 'name': '榜单', 'value': [
                    {'n': '新番榜', 'v': '1'},
                    {'n': '人气榜', 'v': '2'},
                    {'n': '完结榜', 'v': '3'},
                ]},
            ],
        }

        print(f'[漫小肆] classes({len(self.classes)}) = {[c["type_name"] for c in self.classes]}')
        print(f'[漫小肆] filters = {list(self.filters.keys())}, 标签数 = {len(tag_values)}')

    # ==================== ★ 列表解析（新增 ul.book-list 支持） ====================
    def _parse_list(self, html):
        out, seen = [], set()
        if not html:
            print('[漫小肆] _parse_list: html 为空')
            return []
        print(f'[漫小肆] _parse_list: html {len(html)} 字节')
        soup = BeautifulSoup(html, 'html.parser')

        # ★ 新增 ul.book-list（搜索页用）
        cards = soup.select('ul.manga-list-2 li')
        if not cards:
            cards = soup.select('ul.book-list li')
        if not cards:
            cards = soup.select('ul.rank-list li')
        if not cards:
            cards = soup.select('ul.update-list li')
        if not cards:
            cards = soup.select('ul.manga-list li')
        if not cards:
            cards = soup.select('.manga-list-2 li, .book-list li, '
                                '.rank-list li, .update-list li, .manga-list li')
        print(f'[漫小肆] 卡片容器命中 {len(cards)}')

        raw = []
        for li in cards:
            try:
                a = li.select_one('a[href*="/book/"]')
                if a is None:
                    p = li.find_parent('a')
                    if p is not None and re.search(r'/book/\d+', p.get('href') or ''):
                        a = p
                if a is None:
                    continue
                href = a.get('href', '')
                if not href or not re.search(r'/book/\d+', href):
                    continue
                full = self._fix(href)
                if full in seen:
                    continue

                title = ''
                # ★ 加 .book-list-info-title（搜索页）
                t = (li.select_one('.manga-list-2-title a')
                     or li.select_one('.book-list-info-title')
                     or li.select_one('.rank-list-info-right-title')
                     or li.select_one('.manga-title')
                     or li.select_one('a[title]'))
                if t is not None:
                    title = self._clean(t.get('title') or t.get_text())
                if not title:
                    title = self._clean(a.get('title') or a.get_text())
                if not title or len(title) < 1 or len(title) > 60:
                    continue

                pic = ''
                # ★ 加 img.book-list-cover-img（搜索页）
                img = (li.select_one('img.manga-list-2-cover-img')
                       or li.select_one('img.book-list-cover-img')
                       or li.select_one('img.rank-list-cover-img')
                       or li.select_one('.manga-list-2-cover img')
                       or li.select_one('img'))
                if img is not None:
                    pic = self._pick_img(img)

                remark = ''
                # ★ 加 .book-list-info-bottom-right-font（搜索页显示连载状态）
                r = (li.select_one('.manga-list-2-tip')
                     or li.select_one('.book-list-info-desc')
                     or li.select_one('.rank-list-info-right-subtitle')
                     or li.select_one('.update-tip'))
                if r is not None:
                    remark = self._clean(r.get_text())

                seen.add(full)
                raw.append((full, title, pic, remark))
            except Exception as e:
                print(f'[漫小肆] 卡片异常 {e}')

        if not raw:
            print('[漫小肆] 卡片解析为空，启用全页 /book/ 兜底')
            for a in soup.select('a[href*="/book/"]'):
                href = a.get('href', '')
                if not re.search(r'/book/\d+', href):
                    continue
                full = self._fix(href)
                if full in seen:
                    continue
                title = self._clean(a.get('title') or a.get_text())
                if not title or len(title) < 2 or len(title) > 60:
                    continue
                pic = ''
                img = a.select_one('img')
                if img is not None:
                    pic = self._pick_img(img)
                if not pic:
                    parent = a.find_parent(['li', 'div', 'article'])
                    if parent is not None:
                        for im in parent.find_all('img'):
                            v = self._pick_img(im)
                            if v:
                                pic = v
                                break
                seen.add(full)
                raw.append((full, title, pic, ''))
            print(f'[漫小肆] 兜底命中 {len(raw)} 条')

        if self.COVER_B64 and raw:
            pics = [r[2] for r in raw]
            b64_list = self._batch_b64(pics, self.COVER_W, self.COVER_Q,
                                       self.CONC_COVER)
        else:
            b64_list = [r[2] for r in raw]

        for (full, title, pic, remark), cover in zip(raw, b64_list):
            out.append({
                'vod_id': self.VERSION_PREFIX + full,
                'vod_name': title,
                'vod_pic': cover or pic,
                'vod_remarks': remark,
            })

        print(f'[漫小肆] 列表 -> {len(out)} 条')
        return out

    # ==================== 分页 ====================
    def _extract_pagecount(self, html, pg, has_items=False):
        if not html:
            return pg + 1 if has_items else pg
        soup = BeautifulSoup(html, 'html.parser')
        mx = 0
        for a in soup.select('a[href]'):
            href = a.get('href', '')
            m = re.search(r'[?&](?:page|p)=(\d+)', href, re.I)
            if not m:
                m = re.search(r'/page/(\d+)', href, re.I)
            if m:
                try:
                    mx = max(mx, int(m.group(1)))
                except Exception:
                    pass
        if mx:
            return mx
        return pg + 1 if has_items else pg

    # ==================== 分类内容 ====================
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        base = str(tid).strip()
        if base.startswith(self.host):
            base = base.replace(self.host, '')
        if not base:
            base = '/'
        ext = extend or {}

        if '/booklist' in base:
            tag = ext.get('tag') or '全部'
            status = ext.get('status') if ext.get('status') is not None else '-1'
            area = ext.get('area') if ext.get('area') is not None else '-1'

            tag_q = quote(str(tag))
            if pg > 1:
                url = f'/booklist/?page={pg}&tag={tag_q}&area={area}&end={status}'
            else:
                url = f'/booklist/?tag={tag_q}&area={area}&end={status}'

            if url in self._list_cache:
                items, pagecount = self._list_cache[url]
                print(f'[漫小肆] booklist 列表缓存命中 {url} -> {len(items)} 条')
                return {'page': pg, 'pagecount': pagecount,
                        'limit': len(items) or 24, 'total': 0, 'list': items}

            html = self._http_get(url)
            items = self._parse_list(html)
            pagecount = self._extract_pagecount(html, pg, has_items=bool(items))
            self._list_cache[url] = (items, pagecount)
            print(f'[漫小肆] booklist pg={pg} tag={tag} area={area} status={status} '
                  f'url={url} -> {len(items)} 条 pc={pagecount}')
            return {'page': pg, 'pagecount': pagecount,
                    'limit': len(items) or 24, 'total': 0, 'list': items}

        if '/rank' in base:
            tab = str(ext.get('tab') or '1')
            cache_key = f'/rank|{tab}'
            if cache_key in self._list_cache:
                items, pagecount = self._list_cache[cache_key]
                print(f'[漫小肆] rank 缓存命中 tab={tab} -> {len(items)} 条')
                return {'page': pg, 'pagecount': pagecount,
                        'limit': len(items) or 24, 'total': 0, 'list': items}

            html = self._http_get('/rank', use_cache=False)

            if html:
                m = re.search(
                    r'(<ul[^>]*id=["\']rankList_%s["\'][^>]*>.*?</ul>)'
                    % re.escape(tab),
                    html, re.S | re.I)
                if m:
                    html = m.group(1)
                    print(f'[漫小肆] 排行 tab={tab} 截取成功，片段 {len(html)} 字节')
                else:
                    print(f'[漫小肆] 排行 tab={tab} 未找到 rankList_{tab}，使用整页')
            items = self._parse_list(html)
            self._list_cache[cache_key] = (items, pg)
            print(f'[漫小肆] rank tab={tab} -> {len(items)} 条')
            return {'page': pg, 'pagecount': pg,
                    'limit': len(items) or 24, 'total': 0, 'list': items}

        base_norm = base.rstrip('/')
        if pg <= 1:
            candidates = [base_norm]
        else:
            sep = '&' if '?' in base_norm else '?'
            candidates = [
                f'{base_norm}{sep}page={pg}',
                f'{base_norm}/page/{pg}',
                f'{base_norm}{sep}p={pg}',
            ]

        html, items, hit_url = '', [], ''
        for url in candidates:
            html = self._http_get(url)
            if not html:
                print(f'[漫小肆] 分页 URL 无响应: {url}')
                continue
            items = self._parse_list(html)
            if items:
                hit_url = url
                break
            print(f'[漫小肆] 分页 URL {url} 解析为空，试下一个')

        pagecount = self._extract_pagecount(html, pg, has_items=bool(items))
        print(f'[漫小肆] cat={base_norm} pg={pg} url={hit_url or candidates[0]} '
              f'-> {len(items)} 条 pc={pagecount}')
        return {'page': pg, 'pagecount': pagecount,
                'limit': len(items) or 24, 'total': 0, 'list': items}

    # ==================== 详情（保持原样） ====================
    def _parse_detail(self, url):
        if url in self._detail_cache:
            return self._detail_cache[url]

        html = self._http_get(url, use_cache=False)
        if not html:
            self._detail_cache[url] = ('', '', '', [])
            return self._detail_cache[url]

        soup = BeautifulSoup(html, 'html.parser')

        title = ''
        h = (soup.select_one('h1')
             or soup.select_one('.book-title')
             or soup.select_one('.manga-title')
             or soup.select_one('.detail-title'))
        if h is not None:
            title = self._clean(h.get_text())
        if not title:
            t = soup.select_one('title')
            if t is not None:
                title = self._clean(t.get_text()).split('-')[0].split('_')[0].strip()
        if not title:
            title = url.rstrip('/').rsplit('/', 1)[-1]

        cover = ''
        img = (soup.select_one('.manga-cover img')
               or soup.select_one('.book-cover img')
               or soup.select_one('.detail-cover img')
               or soup.select_one('img[data-original]'))
        if img is not None:
            cover = self._pick_img(img)
        if not cover:
            og = soup.select_one('meta[property="og:image"]')
            if og is not None and og.get('content'):
                cover = self._fix(og.get('content'))

        desc = ''
        d = (soup.select_one('.manga-desc')
             or soup.select_one('.book-desc')
             or soup.select_one('.detail-desc')
             or soup.select_one('.desc'))
        if d is not None:
            desc = self._clean(d.get_text())
        if not desc:
            m = soup.select_one('meta[name="description"]')
            if m and m.get('content'):
                desc = self._clean(m.get('content'))

        chapters, seen = [], set()
        for a in soup.select('a[href]'):
            href = a.get('href', '')
            if not href:
                continue
            text = self._clean(a.get_text() or a.get('title'))
            is_chapter = (
                re.search(r'/(chapter|read|view)/', href, re.I)
                or re.search(r'第\s*\d+\s*[話话章回卷]', text)
            )
            if not is_chapter:
                continue
            full = self._fix(href)
            if full in seen:
                continue
            if not text:
                m = re.search(r'/(\d+)', full)
                text = f'第{m.group(1)}話' if m else '章节'
            seen.add(full)
            chapters.append((text, full))

        def _key(item):
            m = re.search(r'(\d+)', item[1].rsplit('/', 1)[-1])
            return int(m.group(1)) if m else 0
        chapters.sort(key=_key)

        if not chapters:
            chapters.append(('查看图集', url))

        result = (title, cover, desc, chapters)
        self._detail_cache[url] = result
        print(f'[漫小肆] 详情 "{title}" 共 {len(chapters)} 話')
        return result

    def _fetch_chapter_images(self, url):
        url = self._fix(url)
        if url in self._chapter_cache:
            return self._chapter_cache[url]

        html = self._http_get(url, use_cache=False)
        imgs = self._extract_chapter_images(html)
        self._chapter_cache[url] = imgs
        print(f'[漫小肆] 章节 {url} -> {len(imgs)} 张图')
        return imgs

    def _extract_chapter_images(self, html):
        if not html:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        imgs, seen = [], set()

        containers = (
            '.chapter-content', '#chapter-content', '.view-content',
            '.manga-content', '#chapter-images', '.chapter-images',
            '.comic-content', '#comic-content', '.content-body',
            '.reader-content', '.read-content', '#read-content',
        )
        for sel in containers:
            nodes = soup.select(sel)
            if not nodes:
                continue
            for n in nodes:
                for img in n.select('img'):
                    v = self._pick_img(img)
                    if v and v not in seen:
                        seen.add(v)
                        imgs.append(v)
            if len(imgs) >= 2:
                return imgs

        priority, other = [], []
        for img in soup.select('img'):
            v = self._pick_img(img)
            if not v or v in seen:
                continue
            low = v.lower()
            if any(k in low for k in self.JUNK_KEYS):
                continue
            seen.add(v)
            if any(k in low for k in ('/upload/', '/chapter/', '/comic/', '/static/upload')):
                priority.append(v)
            else:
                other.append(v)

        return priority if len(priority) >= 2 else priority + other

    # ==================== 框架接口 ====================
    def homeContent(self, filter):
        return {'class': self.classes,
                'filters': self.filters,
                'list': self.homeVideoContent().get('list', [])}

    def homeVideoContent(self):
        html = self._http_get('/')
        items = self._parse_list(html)
        print(f'[漫小肆] 首页命中 {len(items)} 条')
        return {'list': items[:60]}

    def detailContent(self, ids):
        out = []
        for vid in (ids if isinstance(ids, list) else [ids]):
            try:
                url = self._fix(self._real_id(vid))
                title, cover, desc, chapters = self._parse_detail(url)

                if cover and self.COVER_B64:
                    pic = self._fetch_b64(cover, self.COVER_W, self.COVER_Q)
                else:
                    pic = cover

                play_url = '#'.join(f'{n}${h}' for n, h in chapters)

                out.append({
                    'vod_id': str(vid),
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_content': desc or title,
                    'vod_play_from': '漫小肆',
                    'vod_play_url': play_url,
                    'vod_player': 'pics',
                    'vod_remarks': f'共{len(chapters)}話' if chapters else '',
                })
            except Exception as e:
                print(f'[漫小肆] 详情失败 {vid} {e}')
        return {'list': out}

    # ==================== ★ 搜索（用 keyword 参数） ====================
    def searchContent(self, key, quick, pg='1'):
        pg = int(pg) if str(pg).isdigit() else 1

        # ★ 站点搜索参数为 keyword
        if pg > 1:
            url = f'/search?keyword={quote(key)}&page={pg}'
        else:
            url = f'/search?keyword={quote(key)}'

        html = self._http_get(url, use_cache=False)
        if not html or len(html) < 500:
            print(f'[漫小肆] 搜索 "{key}" 无响应 url={url}')
            return {'page': pg, 'pagecount': pg, 'limit': 0, 'total': 0, 'list': []}

        items = self._parse_list(html)
        pagecount = self._extract_pagecount(html, pg, has_items=bool(items))
        print(f'[漫小肆] 搜索 "{key}" p{pg} url={url} -> {len(items)} 条')
        return {'page': pg, 'pagecount': pagecount,
                'limit': len(items) or 24, 'total': 0, 'list': items}

    def playerContent(self, flag, id, vipFlags):
        url = self._fix(self._real_id(id))
        imgs = self._fetch_chapter_images(url)
        if not imgs:
            return {'parse': 0, 'playUrl': '', 'url': '',
                    'header': json.dumps(self.headers)}

        if self.PLAY_MAX_IMAGES > 0 and len(imgs) > self.PLAY_MAX_IMAGES:
            imgs = imgs[:self.PLAY_MAX_IMAGES]

        if self.CHAP_B64:
            urls = self._batch_b64(imgs, self.CHAP_W, self.CHAP_Q,
                                   self.CONC_CHAP)
            ok = sum(1 for u in urls if u.startswith('data:'))
            print(f'[漫小肆] 播放 {len(urls)} 张，b64 {ok}')
        else:
            urls = imgs
            print(f'[漫小肆] 播放 {len(urls)} 张 (原始 URL)')

        return {'parse': 0, 'playUrl': '',
                'url': 'pics://' + '&&'.join(urls),
                'header': json.dumps(self.headers)}

    def localProxy(self, params):
        url = ''
        if isinstance(params, dict):
            for k in ('url', 'u', 'src', 'path', 'uri'):
                if params.get(k):
                    url = str(params[k])
                    break
        elif isinstance(params, (list, tuple)) and params:
            url = str(params[0])
        elif isinstance(params, str):
            url = params

        for pfx in ('proxy://', 'proxy:', 'localproxy://', 'localProxy://'):
            if url.startswith(pfx):
                url = url[len(pfx):]
                break

        if url.startswith('//'):
            url = 'https:' + url
        if not url.startswith('http'):
            return [404, 'text/plain', b'']

        try:
            h = self.headers.copy()
            h['Referer'] = self.host + '/'
            h['Accept'] = 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
            r = self.session.get(url, headers=h, timeout=15, verify=False)
            if r.status_code == 200 and len(r.content) > 100:
                ct = r.headers.get('Content-Type', '') or 'image/jpeg'
                if 'image' not in ct.lower():
                    ct = 'image/jpeg'
                return [200, ct, r.content]
        except Exception as e:
            print(f'[漫小肆] localProxy 异常 {e}')
        return [404, 'text/plain', b'']

    def destroy(self):
        self._html_cache.clear()
        self._detail_cache.clear()
        self._chapter_cache.clear()
        self._b64_cache.clear()
        self._list_cache.clear()