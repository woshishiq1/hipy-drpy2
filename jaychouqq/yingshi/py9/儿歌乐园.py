# -*- coding: utf-8 -*-
# ==========================================================
#  BeddySongs 全球儿歌乐园
#  站点: https://beddysongs.com/zh
#  API:  https://vyourtime.com/api
#  架构: Nuxt 3 (SSR) + Spring Boot, 纯 JSON GET API, 无需认证
#  内容: 全球儿歌音频平台 (MP3 音频, Cloudflare R2 签名 URL, 7天有效)
#
#  接口一览 :
#     GET /song/query/index                       -> 首页精选歌曲
#     GET /song/query/list?searchKey=&searchValue=&page=&pageSize=  -> 分页列表
#         searchKey: type / country / age / (空=全部)
#         searchValue: lullaby / CN / 0-1 / (空=全部)
#     GET /song/query/{urlSlug}                   -> 歌曲详情(含 audioUrl)
#
#  已实现 : 分类(3组+全部) / 子分类筛选器 / 分页 / 详情 / 播放(MP3) / 搜索 / 封面
#  适配: 影视仓 / OK影视 / TVBox
# ==========================================================

import sys
import json
import re

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    import requests

    class BaseSpider(object):
        def fetch(self, url, headers=None, timeout=20, verify=False, cookies=None):
            s = requests.Session()
            s.trust_env = False
            return s.get(url, headers=headers, timeout=timeout,
                         verify=verify, cookies=cookies)

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

try:
    import requests as _requests
except ImportError:
    _requests = None


class Spider(BaseSpider):
    name = '酷鱼专线'
    host = 'https://beddysongs.com'
    api = 'https://vyourtime.com/api'
    UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) '
          'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 '
          'Mobile/15E148 Safari/604.1')
    PAGE_SIZE = 8
    SEARCH_PER_PAGE = 20

    # ---- 中英文映射 (API 返回英文名, 前端需中文展示) ----
    TYPE_NAMES = {
        'lullaby': '摇篮曲', 'action': '动作歌', 'numbers': '数字歌',
        'roleplay': '角色扮演', 'nature': '自然主题',
        'family': '家庭亲情', 'education': '教育启蒙',
    }
    COUNTRY_NAMES = {
        'CN': '中国', 'DE': '德国', 'ES': '西班牙', 'FR': '法国',
        'JP': '日本', 'KR': '韩国', 'RU': '俄罗斯', 'US': '美国',
    }
    AGE_NAMES = {
        '0-1': '0-12个月', '1-2': '1-2岁', '2-3': '2-3岁', '3-4': '3-4岁',
        '4-5': '4-5岁', '5-6': '5-6岁', '6-8': '6-8岁',
    }

    # ---- 父分类 ----
    CATEGORIES = [
     #  {'type_name': '音乐类型', 'type_id': 'type'},
        {'type_name': '国家', 'type_id': 'country'},
     #  {'type_name': '年龄段', 'type_id': 'age'},
        {'type_name': '全部儿歌', 'type_id': 'all'},
    ]

    # ---- 筛选器 (子分类) ----
    FILTERS = {
        'type': [{'key': 'subtype', 'name': '类型', 'init': 'lullaby', 'value': [
            {'n': '摇篮曲', 'v': 'lullaby'},
            {'n': '动作歌', 'v': 'action'},
            {'n': '数字歌', 'v': 'numbers'},
            {'n': '角色扮演', 'v': 'roleplay'},
            {'n': '自然主题', 'v': 'nature'},
            {'n': '家庭亲情', 'v': 'family'},
            {'n': '教育启蒙', 'v': 'education'},
        ]}],
        'country': [{'key': 'subtype', 'name': '国家', 'init': 'CN', 'value': [
            {'n': '中国', 'v': 'CN'}, {'n': '德国', 'v': 'DE'},
            {'n': '西班牙', 'v': 'ES'}, {'n': '法国', 'v': 'FR'},
            {'n': '日本', 'v': 'JP'}, {'n': '韩国', 'v': 'KR'},
            {'n': '俄罗斯', 'v': 'RU'}, {'n': '美国', 'v': 'US'},
        ]}],
        'age': [{'key': 'subtype', 'name': '年龄', 'init': '0-1', 'value': [
            {'n': '0-12个月', 'v': '0-1'}, {'n': '1-2岁', 'v': '1-2'},
            {'n': '2-3岁', 'v': '2-3'}, {'n': '3-4岁', 'v': '3-4'},
            {'n': '4-5岁', 'v': '4-5'}, {'n': '5-6岁', 'v': '5-6'},
            {'n': '6-8岁', 'v': '6-8'},
        ]}],
    }

    DEFAULT_SUBTYPE = {'type': 'lullaby', 'country': 'CN', 'age': '0-1'}

    # ==================== 生命周期 ====================
    def init(self, extend=''):
        self._search_cache = {}
        return {}

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        low = (url or '').lower()
        return any(k in low for k in ('.m3u8', '.mp4', '.mp3', '.m4a',
                                      '.flv', '.avi', '.mkv', '.mov', '.ts'))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def localProxy(self, param):
        return [200, 'text/plain', '']

    def liveContent(self, url):
        return ''

    def action(self, action):
        return '{}'

    # ==================== 工具 ====================
    def _headers(self):
        return {
            'User-Agent': self.UA,
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': self.host + '/zh/',
        }

    def _get(self, url):
        """GET 请求返回 JSON dict"""
        try:
            r = self.fetch(url, headers=self._headers())
            return json.loads(r.text)
        except Exception:
            return {}

    def _build_list_url(self, search_key, search_value, page):
        base = '%s/song/query/list' % self.api
        if search_key:
            return ('%s?searchKey=%s&searchValue=%s&page=%d&pageSize=%d'
                    % (base, search_key, search_value, page, self.PAGE_SIZE))
        return ('%s?searchKey=&searchValue=&page=%d&pageSize=%d'
                % (base, page, self.PAGE_SIZE))

    def _parse_song(self, song):
        """API song -> TVBox vod dict"""
        title = song.get('title', '') or song.get('titleLocale', '') or '未知'
        remarks_parts = []
        st = song.get('songType', '')
        if st:
            remarks_parts.append(self.TYPE_NAMES.get(st, song.get('songTypeName', st)))
        cc = song.get('countryCode', '')
        if cc:
            remarks_parts.append(self.COUNTRY_NAMES.get(cc, song.get('countryCodeName', cc)))
        dur = song.get('durationName', '')
        if dur:
            remarks_parts.append(dur)
        return {
            'vod_id': song.get('urlSlug', ''),
            'vod_name': title,
            'vod_pic': song.get('coverImage', ''),
            'vod_remarks': ' | '.join(remarks_parts),
        }

    # ==================== 首页 ====================
    def homeContent(self, filter=False):
        result = {'class': self.CATEGORIES, 'filters': self.FILTERS, 'list': []}
        try:
            data = self._get('%s/song/query/index' % self.api)
            songs = data.get('data', [])
            if isinstance(songs, list):
                result['list'] = [self._parse_song(s) for s in songs[:20]]
        except Exception:
            pass
        return result

    def homeVideoContent(self):
        result = {'list': [], 'page': 1, 'pagecount': 1,
                  'limit': 20, 'total': 20}
        try:
            data = self._get('%s/song/query/index' % self.api)
            songs = data.get('data', [])
            if isinstance(songs, list):
                result['list'] = [self._parse_song(s) for s in songs[:20]]
        except Exception:
            pass
        return result

    # ==================== 分类列表 ====================
    def categoryContent(self, tid, pg, filter=False, extend=''):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1

        # 解析 extend
        ext = extend
        if isinstance(ext, str) and ext.strip().startswith('{'):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        if not isinstance(ext, dict):
            ext = {}

        result = {'list': [], 'page': page, 'pagecount': 9999,
                  'limit': self.PAGE_SIZE, 'total': 999999}

        try:
            if tid == 'all':
                search_key = ''
                search_value = ''
            elif tid in ('type', 'country', 'age'):
                search_key = tid
                search_value = ext.get('subtype', '') or self.DEFAULT_SUBTYPE.get(tid, '')
            elif ':' in str(tid):
                parts = str(tid).split(':', 1)
                search_key = parts[0]
                search_value = parts[1]
            else:
                search_key = ''
                search_value = ''

            url = self._build_list_url(search_key, search_value, page)
            data = self._get(url)
            songs = data.get('data', [])

            if songs and isinstance(songs, list):
                result['list'] = [self._parse_song(s) for s in songs]
            else:
                result['pagecount'] = page
                result['total'] = (page - 1) * self.PAGE_SIZE
        except Exception:
            result['pagecount'] = page

        return result

    # ==================== 详情 ====================
    def detailContent(self, ids):
        rid = ids[0] if isinstance(ids, (list, tuple)) and ids else str(ids or '')
        rid = str(rid).strip().strip('/')
        if not rid:
            return {'list': []}

        result = {}
        try:
            url = '%s/song/query/%s' % (self.api, rid)
            data = self._get(url)
            song = data.get('data', {})
            if not song or not isinstance(song, dict):
                result['list'] = [{
                    'vod_id': rid, 'vod_name': '未找到',
                    'vod_content': '未找到该歌曲', 'vod_remarks': '未找到',
                    'vod_play_from': self.name, 'vod_play_url': '',
                }]
                return result

            title = song.get('title', '') or song.get('titleLocale', '') or '未知'

            # 简介
            content_parts = []
            desc = song.get('description', '')
            if desc:
                content_parts.append('简介: %s' % desc)
            st = song.get('songType', '')
            if st:
                content_parts.append('类型: %s' % self.TYPE_NAMES.get(st, st))
            cc = song.get('countryCode', '')
            if cc:
                content_parts.append('国家: %s' % self.COUNTRY_NAMES.get(cc, cc))
            ar = song.get('ageRange', '')
            if ar:
                content_parts.append('适合年龄: %s' % self.AGE_NAMES.get(ar, ar))
            dur = song.get('durationName', '')
            if dur:
                content_parts.append('时长: %s' % dur)
            pc = song.get('playCount', 0)
            if pc:
                content_parts.append('播放: %d次' % pc)
            fc = song.get('favoriteCount', 0)
            if fc:
                content_parts.append('收藏: %d次' % fc)
            rt = song.get('rating', 0)
            if rt:
                content_parts.append('评分: %s' % rt)
            lyrics = song.get('lyrics', '')
            if lyrics:
                content_parts.append('\n歌词:\n%s' % lyrics)
            lyrics_i18n = song.get('lyricsI18n', '')
            if lyrics_i18n:
                content_parts.append('\n歌词翻译:\n%s' % lyrics_i18n)

            # remarks
            remarks_parts = []
            if st:
                remarks_parts.append(self.TYPE_NAMES.get(st, st))
            if cc:
                remarks_parts.append(self.COUNTRY_NAMES.get(cc, cc))
            if dur:
                remarks_parts.append(dur)
            remarks = ' | '.join(remarks_parts)

            vod = {
                'vod_id': rid,
                'vod_name': title,
                'vod_pic': song.get('coverImage', ''),
                'vod_content': '\n'.join(content_parts),
                'vod_remarks': remarks,
                'vod_year': '',
                'vod_area': self.COUNTRY_NAMES.get(cc, cc) if cc else '',
                'vod_actor': self.AGE_NAMES.get(ar, ar) if ar else '',
                'vod_director': '',
                'vod_play_from': self.name,
                'vod_play_url': '%s$%s' % (title, rid),
            }
            result['list'] = [vod]
        except Exception as e:
            result['list'] = [{
                'vod_id': rid, 'vod_name': '加载失败',
                'vod_content': '加载失败: %s' % str(e),
                'vod_remarks': '加载失败',
                'vod_play_from': self.name, 'vod_play_url': '',
            }]
        return result

    # ==================== 播放 ====================
    def playerContent(self, flag, id, *args, **kwargs):
        """兼容 TVBox(4参) / FongMi/OK影视(3参) 双壳契约。
        id 即 urlSlug, 调详情 API 获取新鲜签名 MP3 URL。
        """
        # 解析双壳参数
        if len(args) >= 2:
            slug = str(args[1] or '')       # TVBox 模式: url 在 args[1]
        else:
            slug = str(id or '')            # FongMi 模式: id 即 slug

        # 直链兜底 (万一存的就是 URL)
        if self.isVideoFormat(slug) and slug.startswith('http'):
            return {'parse': 0, 'playUrl': '', 'url': slug,
                    'header': {'User-Agent': self.UA, 'Referer': self.host + '/'},
                    'contentType': 'audio/mpeg'}

        result = {'parse': 0, 'playUrl': '', 'url': '',
                  'header': {}, 'pic': '', 'name': ''}

        try:
            url = '%s/song/query/%s' % (self.api, slug)
            data = self._get(url)
            song = data.get('data', {})
            if song:
                audio_url = song.get('audioUrl', '')
                if audio_url:
                    result.update({
                        'url': audio_url,
                        'header': {'User-Agent': self.UA},
                        'name': song.get('title', ''),
                        'pic': song.get('coverImage', ''),
                        'contentType': 'audio/mpeg',
                    })
                    return result
        except Exception:
            pass

        # 解析失败, 返回嗅探
        result['parse'] = 1
        result['url'] = '%s/zh/song/%s' % (self.host, slug)
        result['header'] = {'User-Agent': self.UA, 'Referer': self.host + '/'}
        return result

    # ==================== 搜索 ====================
    def _fetch_all_songs(self):
        """并发拉取全部歌曲 (空 searchKey 端点, ~50 页), 按 urlSlug 去重"""
        all_songs = []
        seen = set()

        def _add(songs):
            for s in songs:
                slug = s.get('urlSlug', '')
                if slug and slug not in seen:
                    seen.add(slug)
                    all_songs.append(s)

        # 先探测总页数 (第 1 页返回 10 条, 后续每页 8 条)
        first = self._get(self._build_list_url('', '', 1))
        first_songs = first.get('data', [])
        if not first_songs:
            return all_songs
        _add(first_songs)

        # 用 ThreadPoolExecutor 并发拉取后续页
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            max_page = 60  # 上限保险

            def _fetch_page(p):
                try:
                    d = self._get(self._build_list_url('', '', p))
                    return p, d.get('data', []) or []
                except Exception:
                    return p, []

            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {pool.submit(_fetch_page, p): p
                           for p in range(2, max_page + 1)}
                page_data = {}
                for f in as_completed(futures):
                    p, songs = f.result()
                    if songs:
                        page_data[p] = songs

            for p in sorted(page_data.keys()):
                _add(page_data[p])
        except ImportError:
            # ThreadPoolExecutor 不可用, 顺序拉取
            for p in range(2, 60):
                d = self._get(self._build_list_url('', '', p))
                songs = d.get('data', [])
                if not songs:
                    break
                _add(songs)

        return all_songs

    def searchContent(self, key, quick=False, pg='1'):
        key = str(key or '').strip()
        if not key:
            return {'list': []}
        try:
            page = int(pg or 1)
        except Exception:
            page = 1

        # 缓存: 同一关键词只拉取一次全量
        cache_key = key.lower()
        if cache_key not in self._search_cache:
            all_songs = self._fetch_all_songs()
            if not all_songs:
                return {'list': []}

            # 按关键词过滤
            kl = cache_key
            matched = []
            for s in all_songs:
                title = (s.get('title', '') or '').lower()
                locale = (s.get('titleLocale', '') or '').lower()
                desc = (s.get('description', '') or '').lower()
                lyrics = (s.get('lyrics', '') or '').lower()
                if kl in title or kl in locale or kl in desc or kl in lyrics:
                    matched.append(s)
            self._search_cache[cache_key] = matched

        matched = self._search_cache.get(cache_key, [])
        per_page = self.SEARCH_PER_PAGE
        start = (page - 1) * per_page
        end = start + per_page
        page_results = matched[start:end]
        total = len(matched)
        pagecount = max(1, (total + per_page - 1) // per_page) if total else 1

        return {
            'list': [self._parse_song(s) for s in page_results],
            'page': page,
            'pagecount': pagecount,
            'limit': per_page,
            'total': total,
        }

    def searchContentPage(self, key, quick, pg):
        return self.searchContent(key, quick, pg)


if __name__ == '__main__':
    s = Spider()
    s.init()

    print('=== 首页 ===')
    home = s.homeContent()
    print('分类数:', len(home.get('class', [])))
    for c in home.get('class', []):
        print('  ', c['type_id'], c['type_name'])
    print('筛选器:')
    for tid, fl in home.get('filters', {}).items():
        for g in fl:
            print('  tid=%s: %s (init=%s, %d 选项)'
                  % (tid, g['name'], g.get('init', ''), len(g['value'])))
    print('首页列表数:', len(home.get('list', [])))
    for v in home.get('list', [])[:3]:
        print('  ', v['vod_id'], v['vod_name'], v.get('vod_remarks', ''))

    print('\n=== 分类: type (摇篮曲) 第1页 ===')
    cat = s.categoryContent('type', 1, extend={'subtype': 'lullaby'})
    print('list:', len(cat.get('list', [])), 'page:', cat.get('page'))
    for v in cat.get('list', [])[:3]:
        print('  ', v['vod_id'], v['vod_name'], v.get('vod_remarks', ''))

    print('\n=== 分类: country (中国) 第1页 ===')
    cat2 = s.categoryContent('country', 1, extend={'subtype': 'CN'})
    print('list:', len(cat2.get('list', [])))
    for v in cat2.get('list', [])[:3]:
        print('  ', v['vod_id'], v['vod_name'], v.get('vod_remarks', ''))

    print('\n=== 分类: all (全部儿歌) 第1页 ===')
    cat3 = s.categoryContent('all', 1)
    print('list:', len(cat3.get('list', {})))

    print('\n=== 分类: type=lullaby 第2页 (分页验证) ===')
    cat4 = s.categoryContent('type', 2, extend={'subtype': 'lullaby'})
    print('list:', len(cat4.get('list', [])), 'page:', cat4.get('page'))

    print('\n=== 详情 ===')
    if cat.get('list'):
        detail = s.detailContent([cat['list'][0]['vod_id']])
        if detail.get('list'):
            d = detail['list'][0]
            for k, v in d.items():
                if v:
                    print('  %s: %s' % (k, str(v)[:160]))

            # 播放测试
            play_url = (d.get('vod_play_url') or '').split('$')[-1]
            print('\n=== 播放 (FongMi 3参) ===')
            play = s.playerContent(d['vod_play_from'], play_url, [])
            print('parse:', play.get('parse'), 'url:', str(play.get('url', ''))[:120])
            print('contentType:', play.get('contentType', ''))
            print('header:', play.get('header', {}))

    print('\n=== 搜索: sleep ===')
    sr = s.searchContent('sleep')
    print('结果数:', sr.get('total', 0), '页数:', sr.get('pagecount', 1))
    for v in sr.get('list', [])[:5]:
        print('  ', v['vod_id'], v['vod_name'], v.get('vod_remarks', ''))

    print('\n=== 搜索: lullaby 第2页 ===')
    sr2 = s.searchContent('lullaby', False, 2)
    print('结果数:', sr2.get('total', 0), '当前页:', sr2.get('page'))
    for v in sr2.get('list', [])[:3]:
        print('  ', v['vod_id'], v['vod_name'])
