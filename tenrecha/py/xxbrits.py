import re, requests, json
from base.spider import Spider
from urllib.parse import quote, unquote

HOST = 'https://www.xxbrits.com/'

class Spider(Spider):
    def getName(self):
        return "xxbrits"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        if not url:
            return False
        if url.startswith(('pics://', 'novel://', 'text://', 'book_', 'comic_')):
            return False
        return '.mp4' in url or '.m3u8' in url or '.ts' in url

    def manualVideoCheck(self):
        return False

    filterable = False
    searchable = True
    host = HOST
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': HOST,
    }

    def _html(self, url, ref=None):
        h = {**self.headers}
        if ref:
            h['Referer'] = ref
        try:
            r = self.session.get(url, headers=h, timeout=15)
            r.encoding = 'utf-8'
            return r.text
        except:
            return ''

    def _proxy_pic(self, url):
        if not url:
            return ''
        if url.startswith('http') and 'url=' not in url:
            return self.getProxyUrl() + '&url=' + quote(url, safe='')
        return url

    def homeContent(self, filter):
        result = {'class': [], 'filters': {}}
        # 导航：视频 / 分类 / 网红 / 写真图集
        groups = [
            ('videos', '视频'),
            ('categories', '分类'),
            ('pornstars', '网红'),
            ('nudes', '写真'),
        ]
        for gid, gname in groups:
            result['class'].append({'type_id': f'{gid}|@', 'type_name': gname})
        # 排序筛选（站点真实 sort_by 参数）
        sort_video = [
            {'n': '最新', 'v': 'post_date'},
            {'n': '最多观看', 'v': 'video_viewed'},
            {'n': '最高评分', 'v': 'rating'},
            {'n': '最长', 'v': 'duration'},
            {'n': '最多评论', 'v': 'most_commented'},
            {'n': '最多收藏', 'v': 'most_favourited'},
        ]
        sort_nude = [
            {'n': '最热', 'v': 'avg_albums_popularity'},
            {'n': '最高评分', 'v': 'avg_albums_rating'},
            {'n': '最多专辑', 'v': 'total_albums'},
        ]
        result['filters'] = {
            'videos|@': [{'key': 'sort_by', 'name': '排序', 'value': sort_video}],
            'categories|@': [{'key': 'sort_by', 'name': '排序', 'value': sort_video}],
            'pornstars|@': [{'key': 'sort_by', 'name': '排序', 'value': sort_video}],
            'nudes|@': [{'key': 'sort_by', 'name': '排序', 'value': sort_nude}],
        }
        return result

    def homeVideoContent(self):
        return self.categoryContent('videos|@', 1)

    def categoryContent(self, tid, pg, filter=None, extend=None):
        extend = extend or {}
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}
        try:
            pg = int(pg) if pg else 1
        except (ValueError, TypeError):
            pg = 1
        sort = extend.get('sort_by', '')
        # tid 格式：kind|sub@ （@ 表示顶层未选子项）；下钻为 kind|sub（无@），可多级
        # folder_ 二级目录：解析真实 URL，不能当普通分类 ID
        if isinstance(tid, str) and tid.startswith('folder_'):
            folder_url = tid[7:].strip()
            if folder_url.startswith('http'):
                folder_url = folder_url.rstrip('/') + '/'
                if '/n/' in folder_url:
                    slug = folder_url.rstrip('/').rsplit('/', 1)[-1]
                    return self._parse_nudes_album(slug, pg)
                return self._parse_videos(folder_url, pg)
            tid = folder_url
        raw = tid.rstrip('@')
        parts = raw.split('|')
        kind = parts[0]
        sub = parts[1] if len(parts) > 1 else ''
        # 视频类（videos / categories 下钻 / pornstars 下钻）URL 构造，支持排序 + 分页叠加
        def video_url(base):
            path = f'{base}/' if int(pg) == 1 else f'{base}/{pg}/'
            return path + (f'?sort_by={sort}' if sort else '')
        # 视频区：latest / top-rated / most-popular
        if kind == 'videos':
            return self._parse_videos(video_url(f'{HOST}{sub or "latest"}'), pg)
        # 分类：/ct/ 分类目录 → 点分类进视频
        if kind == 'categories':
            if not sub:
                return self._parse_categories(pg)
            return self._parse_videos(video_url(f'{HOST}ct/{sub}'), pg)
        # 网红：/p/ 是专辑列表，点专辑进该网红视频
        if kind == 'pornstars':
            if not sub:
                return self._parse_pornstars(pg)
            return self._parse_videos(video_url(f'{HOST}pornsstar/{sub}'), pg)
        # 写真图集：/n/ 图集列表
        if kind == 'nudes':
            if not sub:
                return self._parse_nudes_albums(video_url(f'{HOST}n'), pg)
            return self._parse_nudes_album(sub, pg)
        # 兜底：按 ct 分类处理
        return self._parse_videos(video_url(f'{HOST}ct/{tid}'), pg)

    def _parse_videos(self, url, pg):
        html = self._html(url)
        # 列表页除前几张外均为懒加载：src 是 base64 占位，真实封面在 data-src
        blocks = re.findall(
            r'<a class="card-image" href="https://www\.xxbrits\.com/videos/(\d+)/([^"]+)/\s*"[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
            html, re.S)
        result = {'list': [], 'page': pg, 'pagecount': 9999}
        for vid, slug, title, inner in blocks:
            # 前几张首屏：src 是真图；其余懒加载：src 是 base64 占位，真图在 data-original
            im = re.search(r'<img[^>]*\bsrc="(https?://[^"]+)"', inner) or re.search(r'<img[^>]*\bdata-original="([^"]+)"', inner) or re.search(r'<img[^>]*\bdata-webp="([^"]+)"', inner)
            img = im.group(1) if im else ''
            result['list'].append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._proxy_pic(img),
                'vod_remarks': '',
            })
        # 真实总页数：分页块里 "Last" 链接指向最后一页，或 ul.list 中最大页码
        m = re.search(r'href="/(?:[^"/]+/)*?(\d+)/"[^>]*>\s*Last\s*</a>', html)
        if m:
            result['pagecount'] = int(m.group(1))
        else:
            nums = re.findall(r'<a href="/(?:[^"/]+/)*?(\d+)/"[^>]*data-action="ajax"', html)
            if nums:
                result['pagecount'] = max(int(x) for x in nums)
        return result

    def _parse_categories(self, pg):
        html = self._html(HOST + 'ct/')
        items = re.findall(
            r'<a class="th" href="\s*https://www\.xxbrits\.com/ct/([^/]+)/"[^>]*title="([^"]+)".*?<img[^>]*\bdata-src="([^"]+)"',
            html, re.S)
        result = {'list': [], 'page': pg, 'pagecount': 1}
        for slug, name, img in items:
            result['list'].append({
                'vod_id': f'folder_{HOST}ct/{slug}/',
                'vod_name': name,
                'vod_pic': self._proxy_pic(img),
                'vod_remarks': '分类',
                'vod_tag': 'folder',
            })
        return result

    def _parse_nudes_albums(self, url, pg=1):
        html = self._html(url)
        blocks = re.findall(
            r'<a[^>]*href="https://www\.xxbrits\.com/n/([^/]+)/"\s*[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
            html, re.S)
        result = {'list': [], 'page': pg, 'pagecount': 9999}
        seen = set()
        for slug, name, inner in blocks:
            if slug in seen:
                continue
            seen.add(slug)
            im = re.search(r'<img[^>]*\bdata-src="([^"]+)"', inner) or re.search(r'<img[^>]*\bsrc="(https?://[^"]+)"', inner)
            img = im.group(1) if im else ''
            result['list'].append({
                'vod_id': f'folder_{HOST}n/{slug}/',
                'vod_name': name,
                'vod_pic': self._proxy_pic(img),
                'vod_remarks': '写真',
            })
        m = re.search(r'href="/n/(\d+)/"[^>]*>\s*Last\s*</a>', html)
        if m:
            result['pagecount'] = int(m.group(1))
        else:
            nums = re.findall(r'href="/n/(\d+)/"', html)
            if nums:
                result['pagecount'] = max(int(x) for x in nums)
        return result

    def _parse_pornstars(self, pg):
        # /p/ 是路径式分页（/p/、/p/2/、.../p/18/），每页 30 个，静态 HTML 含卡片
        url = HOST + 'p/' if int(pg) == 1 else f'{HOST}p/{pg}/'
        html = self._html(url)
        blocks = re.findall(
            r'<a class="card-secondary" href="https://www\.xxbrits\.com/pornsstar/([^/]+)/"[^>]*title="([^"]+)".*?<img[^>]*\bdata-src="([^"]+)"',
            html, re.S)
        result = {'list': [], 'page': pg, 'pagecount': 9999}
        for slug, name, img in blocks:
            result['list'].append({
                'vod_id': f'folder_{HOST}pornsstar/{slug}/',
                'vod_name': name,
                'vod_pic': self._proxy_pic(img),
                'vod_remarks': '网红',
                'vod_tag': 'folder',
            })
        m = re.search(r'href="/p/(\d+)/"[^>]*>\s*Last\s*</a>', html)
        if m:
            result['pagecount'] = int(m.group(1))
        else:
            nums = re.findall(r'href="/p/(\d+)/"', html)
            if nums:
                result['pagecount'] = max(int(x) for x in nums)
        return result

    def _parse_nudes_album(self, slug, pg):
        url = f'{HOST}n/{slug}/'
        html = self._html(url)
        # 真实图集图片在 data-original，域名 media.xxbrits.com / media2.xxbrits.com，路径含 /main/（排除 preview 封面）；图片不防盗链，直链给 pics://
        imgs = re.findall(r'https://media[0-9]*\.xxbrits\.com/albums/main/[^"\s]+\.jpg', html)
        result = {'list': [], 'page': pg, 'pagecount': 1}
        if imgs:
            result['list'].append({
                'vod_id': f'folder_{HOST}n/',
                'vod_name': slug,
                'vod_pic': imgs[0],
                'vod_content': f'共 {len(imgs)} 张写真',
                'vod_play_from': '$$$图集',
                'vod_play_url': '#'.join(f'图{i+1}${u}' for i, u in enumerate(imgs)),
                'vod_remarks': f'{len(imgs)}张',
            })
        return result

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else ids
        # 写真：vod_id 用 n:slug（冒号不被 URL 编码，避开 | 被编码成 %7C 导致识别失败）
        if isinstance(vid, str) and vid.startswith('n:'):
            return self._parse_nudes_album(vid[2:], 1)
        if isinstance(vid, str) and vid.startswith('pornstars:'):
            return self._parse_videos(f'{HOST}pornsstar/{vid[len("pornstars:"):]}/', 1)
        if isinstance(vid, str) and '|' in vid:
            kind, sub = vid.split('|', 1)
            if kind == 'n':
                return self._parse_nudes_album(sub, 1)
            if kind == 'pornstars':
                return self._parse_videos(f'{HOST}pornsstar/{sub}/', 1)
            return {'list': []}
        url = f'{HOST}videos/{vid}/'
        html = self._html(url)
        # 真实清晰度在 embed 页的 get_file 签名直链里（token 绑 session，必须走 localProxy）
        emb = self._html(f'{HOST}embed/{vid}/', ref=url)
        title = ''
        m = re.search(r'<title>([^<]+)</title>', emb)
        if m:
            title = m.group(1).strip()
        if not title:
            m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            if m:
                title = m.group(1).strip()
        if not title:
            m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            if m:
                title = m.group(1)
        pic = ''
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if m:
            pic = m.group(1)
        desc = ''
        m = re.search(r'<meta property="og:description" content="([^"]+)"', html)
        if m:
            desc = m.group(1)
        dur = ''
        m = re.search(r'duration["\s:]+(\d+)', html)
        if m:
            dur = m.group(1)
        urls = re.findall(r'(https://www\.xxbrits\.com/get_file/[^"\'\s]+?\.mp4/\?v-acctoken=[^"\'\s]+)', emb)
        # 按 480p -> orig（从低到高）取第一个存在的
        pick_url = None
        for token in ('480p', 'orig'):
            for u in urls:
                if token == '480p' and f'/{vid}_480p.mp4' in u:
                    pick_url = u
                    break
                if token == 'orig' and f'/{vid}.mp4' in u:
                    pick_url = u
                    break
            if pick_url:
                break
        if pick_url:
            pick_url = pick_url.rstrip('\'"').rstrip()
        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._proxy_pic(pic),
            'vod_content': desc,
            'vod_play_from': '视频',
            'vod_play_url': f'播放${pick_url}' if pick_url else '',
            'vod_director': '',
            'vod_actor': '',
            'vod_remarks': dur,
            'vod_year': '',
            'vod_area': '',
        }
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        try:
            # 图集线路才使用 pics://；视频签名 URL 也是 http，不能误判为图片
            if flag == '图集':
                real = id.split('$', 1)[1] if '$' in id else id
                return {'parse': 0, 'url': f'pics://{real}', 'header': self.headers, 'position': '0'}
            # 视频签名地址直连：站点已实测返回 200 video/mp4，避免代理一次性吞整部大文件
            if flag == '视频' or '播放' in id or id.startswith('http'):
                real = id.split('$', 1)[1] if '$' in id else id
                return {
                    'parse': 0,
                    'playUrl': '',
                    'url': real,
                    'header': json.dumps({
                        'User-Agent': self.headers['User-Agent'],
                        'Referer': HOST + 'embed/'
                    }),
                    'position': '0'
                }
            return {'parse': 0, 'url': id, 'header': self.headers, 'position': '0'}
        except:
            return {'parse': 0, 'url': '', 'position': '0'}

    def searchContent(self, key, quick):
        url = f'{HOST}search/?q={quote(key)}'
        html = self._html(url)
        blocks = re.findall(
            r'<a class="card-image" href="https://www\.xxbrits\.com/videos/(\d+)/([^"]+)/\s*"[^>]*title="([^"]+)"[^>]*>(.*?)</a>',
            html, re.S)
        result = {'list': [], 'page': 1, 'pagecount': 9999}
        for vid, slug, title, inner in blocks:
            im = re.search(r'<img[^>]*\bdata-src="([^"]+)"', inner) or re.search(r'<img[^>]*\bsrc="(https?://[^"]+)"', inner)
            img = im.group(1) if im else ''
            result['list'].append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': self._proxy_pic(img),
                'vod_remarks': '',
            })
        return result

    def localProxy(self, param):
        if param.get('type') == 'xxb':
            url = unquote(param['url'])
            r = self.session.get(url, headers={**self.headers, 'Referer': HOST + 'embed/', 'Accept': '*/*'}, timeout=60, stream=True)
            data = r.content
            ct = r.headers.get('Content-Type', 'video/mp4')
            return [200, ct, data, {'Content-Length': str(len(data))}]
        # 图片代理：框架用 &url= 传参
        url = param.get('url', '')
        if not url:
            return [404, 'text/plain', b'', {}]
        url = unquote(url)
        try:
            r = self.session.get(url, headers={**self.headers, 'Referer': HOST, 'Accept': 'image/webp,image/*,*/*'}, timeout=60, stream=True)
            data = r.content
            if data[:2] == b'\xff\xd8':
                ct = 'image/jpeg'
            elif data[:4] == b'\x89PNG':
                ct = 'image/png'
            elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                ct = 'image/webp'
            else:
                ct = r.headers.get('Content-Type', 'image/jpeg')
            return [200, ct, data, {'Content-Length': str(len(data))}]
        except:
            return [404, 'text/plain', b'', {}]
