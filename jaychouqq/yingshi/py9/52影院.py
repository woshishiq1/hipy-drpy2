# coding=utf-8
"""
目标站: 52vod.cc (苹果CMS网页版)
模板: 影视聚合搜索 / 网页解析
站点类型: 综合影视
核心逻辑: 正则解析HTML
支持: 首页, 分类(含二级筛选), 搜索, 详情, 播放(嗅探)
优化: 去重/精简字段/直链嗅探/多线路解析/加载提速/搜索修复
"""

import sys
import re
import urllib.parse

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://52vod.cc"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.site_url + '/',
        }
        self.default_pic = 'https://pic.rmb.bdstatic.com/bjh/user/default.png'

        # 主分类（对应URL路径）
        self.categories = {
            'dianying': '电影',
            'dianshiju': '电视剧',
            'zongyi': '综艺',
            'dongman': '动漫',
            'duanju': '短剧',
            'yingshijieshuo': '影视解说',
        }

        # 二级筛选（类型）
        self.filters = {
            'dianying': [
                {'key': 'type', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''},
                    {'n': '动作片', 'v': 'dongzuopian'},
                    {'n': '喜剧片', 'v': 'xijupian'},
                    {'n': '爱情片', 'v': 'aiqingpian'},
                    {'n': '科幻片', 'v': 'kehuanpian'},
                    {'n': '恐怖片', 'v': 'kongbupian'},
                    {'n': '剧情片', 'v': 'juqingpian'},
                    {'n': '战争片', 'v': 'zhanzhengpian'},
                    {'n': '纪录片', 'v': 'jilupian'},
                ]},
            ],
            'dianshiju': [
                {'key': 'type', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''},
                    {'n': '国产剧', 'v': 'guochanju'},
                    {'n': '港台剧', 'v': 'gangtaiju'},
                    {'n': '日韩剧', 'v': 'rihanju'},
                    {'n': '欧美剧', 'v': 'oumeiju'},
                    {'n': '海外剧', 'v': 'haiwaiju'},
                ]},
            ],
            'zongyi': [
                {'key': 'type', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''},
                    {'n': '大陆综艺', 'v': 'daluzongyi'},
                    {'n': '日韩综艺', 'v': 'rihanzongyi'},
                    {'n': '港台综艺', 'v': 'gangtaizongyi'},
                    {'n': '欧美综艺', 'v': 'oumeizongyi'},
                ]},
            ],
            'dongman': [
                {'key': 'type', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''},
                    {'n': '国产动漫', 'v': 'guochandongman'},
                    {'n': '日韩动漫', 'v': 'rihandongman'},
                    {'n': '港台动漫', 'v': 'gangtaidongman'},
                    {'n': '欧美动漫', 'v': 'oumeidongman'},
                    {'n': '海外动漫', 'v': 'haiwaidongman'},
                    {'n': '动画片', 'v': 'donghuapian'},
                ]},
            ],
            'duanju': [
                {'key': 'type', 'name': '类型', 'value': [
                    {'n': '全部', 'v': ''},
                    {'n': '女频恋爱', 'v': 'nvpinlianai'},
                    {'n': '反转爽剧', 'v': 'fanzhuanshuangju'},
                    {'n': '古装仙侠', 'v': 'guzhuangxianxia'},
                    {'n': '年代穿越', 'v': 'niandaichuanyue'},
                    {'n': '脑洞悬疑', 'v': 'naodongxuanyi'},
                    {'n': '现代都市', 'v': 'xiandaidushi'},
                ]},
            ],
            'yingshijieshuo': [],
        }

    def _fetch(self, url):
        """统一请求，兼容TVBox fetch"""
        try:
            resp = self.fetch(url, headers=self.headers)
            if resp is None:
                return ''
            text = getattr(resp, 'text', '')
            if isinstance(text, bytes):
                text = text.decode('utf-8')
            return text or ''
        except Exception:
            return ''

    def _fix_pic(self, pic):
        """补全图片地址"""
        if not pic:
            return self.default_pic
        pic = pic.strip()
        if pic.startswith('//'):
            return 'https:' + pic
        if pic.startswith('/'):
            return self.site_url + pic
        if pic.startswith('http'):
            return pic
        return self.default_pic

    def _parse_list(self, html):
        """从HTML解析视频列表，兼容首页/分类/搜索"""
        videos = []
        seen = set()
        if not html:
            return videos

        # 先判断是否是搜索页（有 result_list 结构）
        if 'result_list' in html:
            return self._parse_search_list(html)

        # 首页/分类页结构：匹配每个视频卡片
        pattern = r'<a[^>]*href=["\']?/52kan/(\d+)/["\']?[^>]*class=["\']tcl-img["\'][^>]*title=["\']([^"\']*)["\'][^>]*>[\s\S]*?<div[^>]*class=["\'][^"\']*tc_img[^"\']*["\'][^>]*data-original=["\']([^"\']*)["\'][^>]*>[\s\S]*?<p[^>]*class=["\']tc_wz["\'][^>]*>([^<]*)</p>'

        for vid, name, pic, remark in re.findall(pattern, html):
            if vid in seen:
                continue
            seen.add(vid)
            videos.append({
                'vod_id': vid,
                'vod_name': name.strip(),
                'vod_pic': self._fix_pic(pic.strip()),
                'vod_remarks': remark.strip(),
            })

        # 兜底：宽松匹配（仅限主内容区，避免匹配侧边栏推荐）
        if not videos:
            # 尝试在主内容区匹配
            content_area = html
            # 如果有明显的侧边栏，尝试截取主内容
            for side_marker in ['v_right', 'sidebar', 'side-bar', 'hot-list', 'guess-like']:
                idx = content_area.find(side_marker)
                if idx != -1:
                    content_area = content_area[:idx]
                    break

            pattern2 = r'<a[^>]*href=["\']?/52kan/(\d+)/["\']?[^>]*title=["\']([^"\']*)["\'][^>]*>'
            for vid, name in re.findall(pattern2, content_area):
                if vid in seen:
                    continue
                seen.add(vid)
                block_start = content_area.find('/52kan/' + vid + '/')
                block = content_area[block_start:block_start + 800]
                pic_m = re.search(r'data-original=["\']([^"\']*)["\']', block)
                pic = pic_m.group(1) if pic_m else ''
                remark_m = re.search(r'tc_wz["\'][^>]*>([^<]*)</p>', block)
                remark = remark_m.group(1) if remark_m else ''
                videos.append({
                    'vod_id': vid,
                    'vod_name': name.strip(),
                    'vod_pic': self._fix_pic(pic.strip()),
                    'vod_remarks': remark.strip(),
                })

        return videos

    def _parse_search_list(self, html):
        """解析搜索页的结果列表"""
        videos = []
        seen = set()

        # 搜索页结构：
        # <div class="result_list">
        #   <a href="/52kan/ID/" class="pic"><div class="img_wrapper lazyload" data-original="PIC"></div></a>
        #   <div class="search-info">
        #     <div class="result_title"><a href="/52kan/ID/">NAME</a></div>
        #     ...
        #   </div>
        # </div>

        # 找到所有 result_list 块
        result_starts = [m.start() for m in re.finditer(r'<div[^>]*class=["\']result_list["\'][^>]*>', html)]

        for start in result_starts:
            block = html[start:start + 1200]

            # 提取ID和名称（名称在 result_title > a 中）
            title_m = re.search(
                r'<div[^>]*class=["\']result_title["\'][^>]*>[\s\S]*?<a[^>]*href=["\']?/52kan/(\d+)/["\']?[^>]*>([^<]+)</a>',
                block)
            if not title_m:
                continue
            vid = title_m.group(1)
            name = title_m.group(2).strip()

            if vid in seen:
                continue
            seen.add(vid)

            # 提取图片
            pic_m = re.search(r'data-original=["\']([^"\']+)["\']', block)
            pic = pic_m.group(1) if pic_m else ''

            # 提取备注/状态
            remark = ''
            status_m = re.search(r'<li[^>]*>状态[：:]\s*([^<]+)</li>', block)
            if status_m:
                remark = status_m.group(1).strip()
            else:
                # 尝试找 [类型] 作为备注
                type_m = re.search(r'\[([^\]]+)\]', block)
                if type_m:
                    remark = type_m.group(1)

            videos.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': self._fix_pic(pic),
                'vod_remarks': remark,
            })

        return videos

    def _parse_detail_meta(self, html):
        """解析详情页基本信息"""
        info = {
            'name': '', 'pic': '', 'content': '', 'actor': '',
            'director': '', 'year': '', 'area': '', 'type_name': '',
            'remarks': '',
        }
        if not html:
            return info

        # 标题
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m:
            info['name'] = m.group(1).strip()
        else:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                info['name'] = m.group(1).split('_')[0].strip()

        # 图片 - 优先匹配详情页大图
        m = re.search(r'<img[^>]*class=["\'][^"\']*(?:vod_pic|pic|img|lazyload)[^"\']*["\'][^>]*data-original=["\']([^"\']+)["\']', html, re.I)
        if m:
            info['pic'] = self._fix_pic(m.group(1))
        else:
            m = re.search(r'<img[^>]*data-original=["\']([^"\']+)["\']', html, re.I)
            if m:
                info['pic'] = self._fix_pic(m.group(1))
            else:
                m = re.search(r'<img[^>]*src=["\']([^"\']+)["\']', html, re.I)
                if m:
                    info['pic'] = self._fix_pic(m.group(1))

        # 简介
        desc_blocks = re.findall(r'<div[^>]*class=["\'][^"\']*(?:content|desc|summary|intro|vod_content)[^"\']*["\'][^>]*>([\s\S]*?)</div>', html, re.I)
        for block in desc_blocks:
            text = re.sub(r'<[^>]+>', '', block).strip().replace('&nbsp;', ' ')
            if len(text) > len(info['content']):
                info['content'] = text

        # 兜底：找长段落
        if not info['content']:
            ps = re.findall(r'<p[^>]*>([\s\S]*?)</p>', html)
            for p in ps:
                text = re.sub(r'<[^>]+>', '', p).strip().replace('&nbsp;', ' ')
                if len(text) > 30:
                    info['content'] = text
                    break

        # 元信息提取 - 从 <i class="colXX"> 标签中提取
        info_items = re.findall(r'<i[^>]*class=["\'][^"\']*col\d+[^"\']*["\'][^>]*>([\s\S]*?)</i>', html)
        for item in info_items:
            text = re.sub(r'<[^>]+>', ' ', item).strip().replace('&nbsp;', ' ')
            if '主演' in item or '演员' in item:
                m = re.search(r'(?:主演|演员)[：:]\s*([^\n]+)', text)
                if m:
                    info['actor'] = m.group(1).strip()
            elif '导演' in item:
                m = re.search(r'导演[：:]\s*([^\n]+)', text)
                if m:
                    info['director'] = m.group(1).strip()
            elif '类型' in item:
                m = re.search(r'类型[：:]\s*([^\n]+)', text)
                if m:
                    info['type_name'] = m.group(1).strip()
            elif '地区' in item:
                m = re.search(r'地区[：:]\s*([^\n]+)', text)
                if m:
                    info['area'] = m.group(1).strip()
            elif '年份' in item:
                m = re.search(r'(\d{4})', text)
                if m:
                    info['year'] = m.group(1)
            elif '状态' in item:
                m = re.search(r'状态[：:]\s*([^\n]+)', text)
                if m:
                    info['remarks'] = m.group(1).strip()

        # 兜底：从纯文本中提取
        if not info['actor']:
            m = re.search(r'主演[：:]\s*([^<>\n]+?)(?:\s{2,}|$)', html)
            if m:
                info['actor'] = m.group(1).strip()
        if not info['director']:
            m = re.search(r'导演[：:]\s*([^<>\n]+?)(?:\s{2,}|$)', html)
            if m:
                info['director'] = m.group(1).strip()
        if not info['year']:
            m = re.search(r'年份[：:]\s*(\d{4})', html)
            if m:
                info['year'] = m.group(1)
        if not info['remarks']:
            m = re.search(r'状态[：:]\s*([^<>\n]+?)(?:\s{2,}|$)', html)
            if m:
                info['remarks'] = m.group(1).strip()

        return info

    def _parse_detail_play(self, html, vid):
        """解析详情页播放线路和集数"""
        play_from = []
        play_url = []

        if not html or not vid:
            return play_from, play_url

        # 提取线路名：tab-switch li 中的 a 标签文本
        line_pattern = r'<li[^>]*class=["\'][^"\']*tab-switch[^"\']*["\'][^>]*switch=["\'](tab_con_playlist_\d+)["\'][^>]*>\s*<a[^>]*>([^<]+)</a>'
        lines = re.findall(line_pattern, html)

        if not lines:
            return play_from, play_url

        for tab_id, line_name in lines:
            line_name = line_name.strip()
            if not line_name:
                continue

            # 精确定位 tab-content 块
            tab_pattern = r'<div[^>]*id=["\']' + re.escape(tab_id) + r'["\'][^>]*>([\s\S]*?)</div>\s*(?=<div[^>]*id=["\']tab_con_playlist_|</div>\s*</div>\s*<div class="con_juji_bg")'
            tab_match = re.search(tab_pattern, html)

            if not tab_match:
                # 备用：手动找闭合div
                tab_start = html.find('id="' + tab_id + '"')
                if tab_start == -1:
                    tab_start = html.find("id='" + tab_id + "'")
                if tab_start == -1:
                    continue
                tab_html = html[tab_start:]
                depth = 0
                pos = tab_html.find('>')
                if pos == -1:
                    continue
                pos += 1
                depth = 1
                while pos < len(tab_html) and depth > 0:
                    next_open = tab_html.find('<div', pos)
                    next_close = tab_html.find('</div>', pos)
                    if next_close == -1:
                        break
                    if next_open != -1 and next_open < next_close:
                        depth += 1
                        pos = next_open + 4
                    else:
                        depth -= 1
                        pos = next_close + 6
                tab_html = tab_html[:pos]
            else:
                tab_html = tab_match.group(1)

            # 提取集数链接
            ep_pattern = r'<a[^>]*href=["\'](/52tv/\d+-\d+-\d+/)["\'][^>]*>([^<]+)</a>'
            episodes = re.findall(ep_pattern, tab_html)

            if not episodes:
                continue

            # 过滤掉非集数链接
            ep_list = []
            for ep_url, ep_name in episodes:
                ep_name = ep_name.strip()
                if not ep_name or '报错' in ep_name or 'javascript' in ep_url:
                    continue
                ep_list.append(f"{ep_name}${self.site_url}{ep_url}")

            if ep_list:
                play_from.append(line_name)
                play_url.append('#'.join(ep_list))

        return play_from, play_url

    def homeContent(self, filter):
        """首页内容 - 只请求首页，不再额外请求分类页"""
        categories = [{'type_id': k, 'type_name': v} for k, v in self.categories.items()]
        videos = []
        seen = set()

        html = self._fetch(self.site_url + '/')
        for v in self._parse_list(html):
            if v['vod_id'] not in seen:
                seen.add(v['vod_id'])
                videos.append(v)

        filters = {k: v for k, v in self.filters.items() if k in self.categories}
        return {'class': categories, 'list': videos[:30], 'filters': filters}

    def homeVideoContent(self):
        """首页视频推荐"""
        videos = []
        seen = set()
        html = self._fetch(self.site_url + '/')
        for v in self._parse_list(html):
            if v['vod_id'] not in seen:
                seen.add(v['vod_id'])
                videos.append(v)
        return {'list': videos[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容"""
        page = int(pg) if pg else 1

        sub_type = ''
        if extend and isinstance(extend, dict):
            sub_type = extend.get('type', '')

        if sub_type:
            path = '/52vod/{0}/'.format(sub_type)
        else:
            path = '/52vod/{0}/'.format(tid)

        url = self.site_url + path
        if page > 1:
            url += 'page/{0}.html'.format(page)

        html = self._fetch(url)
        videos = self._parse_list(html)

        has_more = len(videos) >= 24
        pagecount = page + 1 if has_more else page

        return {
            'list': videos,
            'page': page,
            'pagecount': pagecount,
            'limit': 30,
            'total': page * 30 if has_more else page * 30,
        }

    def searchContent(self, key, quick, pg='1'):
        """搜索内容 - 修复分页URL格式"""
        page = int(pg) if pg else 1
        encoded = urllib.parse.quote(key)

        # 苹果CMS搜索分页格式: /52vodso/{keyword}-{page}---/
        if page > 1:
            url = '{0}/52vodso/{1}-{2}---/'.format(self.site_url, encoded, page)
        else:
            url = '{0}/52vodso/----/?wd={1}'.format(self.site_url, encoded)

        html = self._fetch(url)
        videos = self._parse_list(html)

        # 搜索结果分页判断：满10条认为有下一页（搜索页通常每页10条）
        has_more = len(videos) >= 10
        pagecount = page + 1 if has_more else page

        return {
            'list': videos,
            'page': page,
            'pagecount': pagecount,
            'limit': 30,
            'total': page * 30 if has_more else page * 30,
        }

    def detailContent(self, ids):
        """详情内容"""
        if not ids:
            return {'list': []}
        vid = str(ids[0])
        url = '{0}/52kan/{1}/'.format(self.site_url, vid)
        html = self._fetch(url)

        if not html:
            return {'list': []}

        meta = self._parse_detail_meta(html)
        play_from, play_url = self._parse_detail_play(html, vid)

        if not play_from:
            play_from = ['默认线路']
            play_url = ['正片${0}'.format(url)]

        result = [{
            'vod_id': vid,
            'vod_name': meta['name'],
            'vod_pic': meta['pic'] or self.default_pic,
            'vod_content': meta['content'],
            'vod_actor': meta['actor'],
            'vod_director': meta['director'],
            'vod_year': meta['year'],
            'vod_area': meta['area'],
            'vod_type': meta['type_name'],
            'vod_remarks': meta['remarks'],
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }]
        return {'list': result}

    def playerContent(self, flag, id, vipFlags):
        """播放处理：该站为JS动态加载，返回播放页供嗅探"""
        if not id:
            return {'parse': 1, 'url': '', 'header': self.headers}

        raw = str(id).strip()
        if '$' in raw:
            raw = raw.split('$')[-1].strip()

        if not raw:
            return {'parse': 1, 'url': id, 'header': self.headers}

        # 直链直接播放
        if raw.startswith('http') and any(ext in raw.lower() for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
            return {
                'parse': 0,
                'url': raw,
                'header': {
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': self.site_url + '/',
                }
            }

        # 返回播放页让TVBox嗅探（包括 /52tv/ 格式的播放页）
        return {
            'parse': 1,
            'url': raw,
            'header': self.headers,
        }
