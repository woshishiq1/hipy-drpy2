# coding=utf-8
"""
目标站: 迷你影视 (lvmin.org)
模板: MacCMS 面包影视 (mianbaowang)
站点类型: 综合影视
支持: 首页, 分类(含二级筛选: 类型/年份/语言/字母), 搜索, 详情(多线路), 播放
"""

import sys
import re
import json
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    # ===================== 初始化 =====================
    def init(self, extend=""):
        self.site_url = "https://www.lvmin.org"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.default_pic = 'https://pic.rmb.bdstatic.com/bjh/user/default.png'

        # ---- 一级分类 ----
        self.categories = {
            '1': '电影',
            '2': '电视剧',
            '5': '动漫',
            '29': '短剧',
            '37': '综艺',
        }

        # ---- 二级筛选 ----
        # type_id -> 子分类列表; 每个子分类含 key/name/value
        self.filters = {
            '1': [
                {'key': 'tid', 'name': '类型', 'value': [
                    {'n': '全部', 'v': '1'},
                    {'n': '动作片', 'v': '6'}, {'n': '爱情片', 'v': '7'}, {'n': '科幻片', 'v': '8'},
                    {'n': '恐怖片', 'v': '9'}, {'n': '战争片', 'v': '10'}, {'n': '喜剧片', 'v': '11'},
                    {'n': '剧情片', 'v': '12'}, {'n': '惊悚片', 'v': '20'}, {'n': '恋爱片', 'v': '21'},
                    {'n': '悬疑片', 'v': '22'}, {'n': '奇幻片', 'v': '23'}, {'n': '纪实片', 'v': '24'},
                    {'n': '军事片', 'v': '25'}, {'n': '犯罪片', 'v': '26'},
                ]},
                {'key': 'year', 'name': '年份', 'value': self._year_list()},
                {'key': 'lang', 'name': '语言', 'value': self._lang_list()},
                {'key': 'letter', 'name': '字母', 'value': self._letter_list()},
            ],
            '2': [
                {'key': 'tid', 'name': '类型', 'value': [
                    {'n': '全部', 'v': '2'},
                    {'n': '大陆剧', 'v': '30'}, {'n': '韩剧', 'v': '15'}, {'n': '美剧', 'v': '14'},
                    {'n': '港剧', 'v': '13'}, {'n': '日剧', 'v': '16'}, {'n': '台剧', 'v': '27'},
                    {'n': '泰剧', 'v': '28'},
                ]},
                {'key': 'year', 'name': '年份', 'value': self._year_list()},
                {'key': 'lang', 'name': '语言', 'value': self._lang_list()},
                {'key': 'letter', 'name': '字母', 'value': self._letter_list()},
            ],
            '5': [
                {'key': 'tid', 'name': '类型', 'value': [
                    {'n': '全部', 'v': '5'},
                    {'n': '大陆动漫', 'v': '17'}, {'n': '日本动漫', 'v': '47'}, {'n': '欧美动漫', 'v': '49'},
                    {'n': '香港动漫', 'v': '18'}, {'n': '韩国动漫', 'v': '48'}, {'n': '台湾动漫', 'v': '46'},
                ]},
                {'key': 'year', 'name': '年份', 'value': self._year_list()},
                {'key': 'lang', 'name': '语言', 'value': self._lang_list()},
                {'key': 'letter', 'name': '字母', 'value': self._letter_list()},
            ],
            '29': [
                {'key': 'tid', 'name': '类型', 'value': [
                    {'n': '全部', 'v': '29'},
                    {'n': '总裁短剧', 'v': '52'}, {'n': '神豪短剧', 'v': '53'}, {'n': '穿越重生短剧', 'v': '54'},
                    {'n': '都市短剧', 'v': '55'}, {'n': '年代短剧', 'v': '56'}, {'n': '长篇短剧', 'v': '57'},
                ]},
                {'key': 'year', 'name': '年份', 'value': self._year_list()},
                {'key': 'lang', 'name': '语言', 'value': self._lang_list()},
                {'key': 'letter', 'name': '字母', 'value': self._letter_list()},
            ],
            '37': [
                {'key': 'tid', 'name': '类型', 'value': [
                    {'n': '全部', 'v': '37'},
                    {'n': '大陆综艺', 'v': '38'}, {'n': '欧美综艺', 'v': '43'}, {'n': '香港综艺', 'v': '39'},
                    {'n': '台湾综艺', 'v': '40'}, {'n': '日本综艺', 'v': '41'}, {'n': '韩国综艺', 'v': '42'},
                ]},
                {'key': 'year', 'name': '年份', 'value': self._year_list()},
                {'key': 'lang', 'name': '语言', 'value': self._lang_list()},
                {'key': 'letter', 'name': '字母', 'value': self._letter_list()},
            ],
        }

    # ===================== 工具方法 =====================
    @staticmethod
    def _year_list():
        items = [{'n': '全部', 'v': ''}]
        for y in range(2026, 2003, -1):
            items.append({'n': str(y), 'v': str(y)})
        return items

    @staticmethod
    def _lang_list():
        return [
            {'n': '全部', 'v': ''}, {'n': '国语', 'v': '国语'}, {'n': '英语', 'v': '英语'},
            {'n': '粤语', 'v': '粤语'}, {'n': '闽南语', 'v': '闽南语'}, {'n': '韩语', 'v': '韩语'},
            {'n': '日语', 'v': '日语'}, {'n': '其它', 'v': '其它'},
        ]

    @staticmethod
    def _letter_list():
        items = [{'n': '全部', 'v': ''}]
        for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            items.append({'n': c, 'v': c})
        items.append({'n': '0-9', 'v': '0-9'})
        return items

    def _fetch(self, path, retries=2):
        """带重试的页面抓取，提升加载稳定性"""
        url = self.site_url + path if path.startswith('/') else path
        for i in range(retries + 1):
            try:
                resp = self.fetch(url, headers=self.headers)
                if resp:
                    return resp.text
            except Exception:
                pass
        return ''

    def _decode(self, text):
        """HTML 实体解码"""
        if not text:
            return ''
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        return text.strip()

    def _re(self, pattern, text, default=''):
        """正则搜索，取第一个分组或整个匹配"""
        m = re.search(pattern, text)
        if not m:
            return default
        return m.group(1) if m.lastindex else m.group(0)

    # ===================== 卡片解析 =====================
    def _parse_card(self, html_block):
        """从首页/分类列表的 <li> 块中解析视频卡片"""
        vid = self._re(r'href="/detail/(\d+)\.html"', html_block)
        if not vid:
            return None
        name = self._re(r'title="([^"]+)"', html_block)
        pic = self._re(r'data-original="([^"]+)"', html_block)
        remark = self._re(r'class="pic-text[^"]*"[^>]*>([^<]+)<', html_block)
        score = self._re(r'class="pic-tag[^"]*"[^>]*>([^<]+)<', html_block)
        # 列表页的简介/演员信息
        actor = ''
        p_match = re.search(r'<p class="text[^"]*"[^>]*>([^<]+)<', html_block)
        if p_match:
            actor = p_match.group(1).strip()
        return {
            'vod_id': vid,
            'vod_name': self._decode(name),
            'vod_pic': pic if pic else self.default_pic,
            'vod_remarks': self._decode(remark),
            'vod_score': self._decode(score),
            'vod_actor': self._decode(actor),
        }

    def _parse_list_cards(self, html):
        """批量解析列表页的视频卡片"""
        pattern = r'<li class="col-md-6 col-sm-4 col-xs-3">(.*?)</li>'
        blocks = re.findall(pattern, html, re.DOTALL)
        videos = []
        seen = set()
        for block in blocks:
            card = self._parse_card(block)
            if card and card['vod_id'] not in seen:
                seen.add(card['vod_id'])
                videos.append(card)
        return videos

    def _parse_search_cards(self, html):
        """解析搜索结果页的视频卡片（列表式布局）"""
        pattern = r'<li class="active[^"]*clearfix">(.*?)</li>'
        blocks = re.findall(pattern, html, re.DOTALL)
        videos = []
        seen = set()
        for block in blocks:
            vid = self._re(r'href="/detail/(\d+)\.html"', block)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            name = self._re(r'title="([^"]+)"', block)
            pic = self._re(r'data-original="([^"]+)"', block)
            remark = self._re(r'class="pic-text[^"]*"[^>]*>([^<]+)<', block)
            # 搜索结果页的结构化信息
            director = self._re(r'导演：</span>([^<]+)', block)
            actor = self._re(r'主演：</span>([^<]+)', block)
            type_name = self._re(r'类型：</span>([^<]+)', block)
            area = self._re(r'地区：</span>([^<]+)', block)
            year = self._re(r'年份：</span>([^<]+)', block)
            videos.append({
                'vod_id': vid,
                'vod_name': self._decode(name),
                'vod_pic': pic if pic else self.default_pic,
                'vod_remarks': self._decode(remark),
                'vod_director': self._decode(director),
                'vod_actor': self._decode(actor),
                'vod_type': self._decode(type_name),
                'vod_area': self._decode(area),
                'vod_year': self._decode(year),
            })
        return videos

    # ===================== 构建筛选路径 =====================
    def _build_show_path(self, tid, extend, page):
        """根据分类 ID、筛选参数和页码，构建分类列表 URL 路径"""
        sub_tid = tid
        if extend:
            if extend.get('tid'):
                sub_tid = extend['tid']
        parts = ['/show/{0}.html'.format(sub_tid)]
        if extend:
            if extend.get('year'):
                parts = ['/show/{0}/year/{1}.html'.format(sub_tid, extend['year'])]
            if extend.get('lang'):
                parts = ['/show/{0}/lang/{1}.html'.format(sub_tid, urllib.parse.quote(extend['lang']))]
            if extend.get('letter'):
                parts = ['/show/{0}/letter/{1}.html'.format(sub_tid, extend['letter'])]
        path = parts[0]
        # 页码
        if page and int(page) > 1:
            base = path.replace('.html', '')
            path = '{0}/page/{1}.html'.format(base, page)
        return path

    # ===================== Spider 标准接口 =====================

    def homeContent(self, filter):
        """首页内容 + 分类 + 筛选（优化版）"""
        html = self._fetch('/')
        categories = [{'type_id': k, 'type_name': v} for k, v in self.categories.items()]
        videos = self._parse_list_cards(html)
        return {'class': categories, 'list': videos[:24], 'filters': self.filters}

    def homeVideoContent(self):
        """首页推荐视频（优化版）"""
        html = self._fetch('/')
        videos = self._parse_list_cards(html)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        """分类页内容，支持二级筛选（优化版）"""
        page = int(pg) if pg else 1
        path = self._build_show_path(tid, extend, page)
        html = self._fetch(path)
        videos = self._parse_list_cards(html)[:36]
        limit = 36
        pagecount = page + 1 if len(videos) >= limit else page
        return {
            'list': videos,
            'page': page,
            'pagecount': pagecount,
            'limit': limit,
            'total': len(videos),
        }

    def searchContent(self, key, quick, pg='1'):
        """搜索（优化版）"""
        page = int(pg) if pg else 1
        encoded = urllib.parse.quote(key)
        path = '/search.html?wd={0}'.format(encoded)
        if page > 1:
            path += '&page={0}'.format(page)
        html = self._fetch(path)
        videos = self._parse_search_cards(html)[:20]
        limit = 20
        pagecount = page + 1 if len(videos) >= limit else page
        return {
            'list': videos,
            'page': page,
            'pagecount': pagecount,
            'limit': limit,
            'total': len(videos),
        }

    def detailContent(self, ids):
        """详情页: 解析影片信息 + 多线路播放列表（优化版）"""
        if not ids:
            return {'list': []}
        vid = ids[0]
        html = self._fetch('/detail/{0}.html'.format(vid))
        if not html:
            return {'list': []}

        title = self._re(r'<title>([^_]+?)_', html)
        pic = self._re(r'data-original="([^"]+)"', html)
        
        actors = re.findall(r'href="/search/actor/[^"]*"[^>]*>([^<]+)<', html)[:10]
        actor = ' / '.join([self._decode(a) for a in actors]) if actors else ''
        
        directors = re.findall(r'href="/search/director/[^"]*"[^>]*>([^<]+)<', html)[:5]
        director = ' / '.join([self._decode(d) for d in directors]) if directors else ''
        
        desc = self._re(r'简介：</span>(.*?)</p>', html, '')
        desc = self._decode(re.sub(r'<[^>]+>', '', desc))[:200]
        
        vod_class = self._re(r'类型：</span>([^<]+)', html)
        area = self._re(r'地区：</span>([^<]+)', html)
        year = self._re(r'年份：</span>([^<]+)', html)

        # ---- 解析播放线路（使用 split 方式，兼容 <h3> 内含 img 标签的结构）----
        play_from = []
        play_url = []

        blocks = re.split(r'(<h3 class="title">)', html)
        
        current_line_name = None
        for i, block in enumerate(blocks):
            if '<h3 class="title">' in block and i + 1 < len(blocks):
                next_block = blocks[i + 1] if i + 1 < len(blocks) else ''
                combined = block + next_block
                line_match = re.search(r'</h3>', combined)
                if line_match:
                    before_h3_close = combined[:line_match.start()]
                    line_name = re.sub(r'<[^>]+>', '', before_h3_close).strip()
                    current_line_name = line_name if line_name else '默认线路'
            
            if current_line_name and 'stui-content__playlist' in block:
                ep_pattern = r'<a href="/play/([^"]+)"[^>]*>([^<]+)</a>'
                episodes = re.findall(ep_pattern, block)[:50]
                if episodes:
                    ep_list = ['{0}${1}'.format(self._decode(ep_name), play_path) 
                              for play_path, ep_name in episodes]
                    play_from.append(current_line_name)
                    play_url.append('#'.join(ep_list))
                    current_line_name = None

        if not play_from:
            all_episodes = re.findall(r'<a href="/play/([^"]+)"[^>]*>([^<]+)</a>', html)[:50]
            if all_episodes:
                ep_list = ['{0}${1}'.format(self._decode(ep_name), play_path) 
                          for play_path, ep_name in all_episodes]
                play_from.append('默认线路')
                play_url.append('#'.join(ep_list))
            else:
                play_from.append('默认线路')
                play_url.append('播放$/play/{0}_1_1.html'.format(vid))

        result = [{
            'vod_id': vid,
            'vod_name': self._decode(title),
            'vod_pic': pic if pic else self.default_pic,
            'vod_content': desc,
            'vod_actor': actor,
            'vod_director': director,
            'vod_year': self._decode(year) if year else '',
            'vod_area': self._decode(area) if area else '',
            'vod_type': self._decode(vod_class) if vod_class else '',
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }]
        return {'list': result}

    def playerContent(self, flag, id, vipFlags):
        """播放解析: 从播放页提取 m3u8/mp4 直链（优化版）"""
        play_path = id.strip()
        if not play_path.startswith('/play/'):
            play_path = '/play/{0}'.format(play_path)

        html = self._fetch(play_path)
        if not html:
            return {'parse': 1, 'url': self.site_url + play_path, 'header': self.headers}

        # 快速提取 player_aaaa JSON
        player_json = self._re(r'var player_aaaa=(\{.*?\})\s*</script>', html)
        if not player_json:
            iframe_src = self._re(r'<iframe[^>]+src="([^"]+)"', html)
            if iframe_src and iframe_src.startswith('http'):
                return {
                    'parse': 0,
                    'url': iframe_src,
                    'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.site_url + '/'}
                }
            return {'parse': 1, 'url': self.site_url + play_path, 'header': self.headers}

        try:
            player_data = json.loads(player_json)
        except (json.JSONDecodeError, TypeError):
            return {'parse': 1, 'url': self.site_url + play_path, 'header': self.headers}

        url = player_data.get('url', '')
        encrypt = player_data.get('encrypt', 0)

        if not url:
            return {'parse': 1, 'url': self.site_url + play_path, 'header': self.headers}

        # URL 解码
        url = url.replace('\\/', '/')

        # 如果是 m3u8 或 mp4 直链，直接返回（最快路径）
        if url.startswith('http') and ('.m3u8' in url or '.mp4' in url):
            return {
                'parse': 0,
                'url': url,
                'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.site_url + '/'}
            }

        # 加密处理
        if encrypt == 1:
            import base64
            try:
                url = base64.b64decode(url).decode('utf-8')
            except Exception:
                pass
        elif encrypt == 2:
            import base64
            try:
                url = base64.b64decode(url).decode('utf-8')[::-1]
            except Exception:
                pass

        if url.startswith('http') and ('.m3u8' in url or '.mp4' in url):
            return {
                'parse': 0,
                'url': url,
                'header': {'User-Agent': self.headers['User-Agent'], 'Referer': self.site_url + '/'}
            }

        # 兜底
        return {'parse': 1, 'url': self.site_url + play_path, 'header': self.headers}
