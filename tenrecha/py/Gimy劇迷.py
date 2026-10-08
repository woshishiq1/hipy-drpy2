# -*- coding: utf-8 -*-
# TVBox爬虫 - Gimy TV 劇迷 (gimy.now)
# by：轻狂书生

import re
import sys
import json
import urllib3
from base.spider import Spider

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')


class Spider(Spider):
    # ========== 基础配置 ==========
    host = 'https://gimy.now'
    parser_base = ''
    parser_referer = ''

    def_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://gimy.now/',
    }

    # 自营/广告线路过滤（留空不过滤）
    self_operated = []

    # 搜索 mid 映射: 1=电影, 2=电视剧, 3=综艺, 4=动漫
    search_mids = [1, 2, 3, 4]

    # ========== 首页分类 ==========

    def homeContent(self, filter):
        """首页分类"""
        return {'class': [
            {'type_id': '13', 'type_name': '陸劇'},
            {'type_id': '20', 'type_name': '韓劇'},
            {'type_id': '16', 'type_name': '美劇'},
            {'type_id': '15', 'type_name': '日劇'},
            {'type_id': '14', 'type_name': '台劇'},
            {'type_id': '21', 'type_name': '港劇'},
            {'type_id': '31', 'type_name': '海外劇'},
            {'type_id': '34', 'type_name': '短劇'},
            {'type_id': '22', 'type_name': '紀錄片'},
            {'type_id': '11', 'type_name': '劇情片'},
            {'type_id': '6',  'type_name': '動作片'},
            {'type_id': '9',  'type_name': '科幻片'},
            {'type_id': '7',  'type_name': '喜劇片'},
            {'type_id': '10', 'type_name': '恐怖片'},
            {'type_id': '8',  'type_name': '愛情片'},
            {'type_id': '12', 'type_name': '戰爭片'},
            {'type_id': '24', 'type_name': '動畫電影'},
            {'type_id': '29', 'type_name': '綜藝'},
        ]}

    def homeVideoContent(self):
        """首页视频列表"""
        return self.categoryContent('13', 1, {}, {})

    # ========== 分类内容 ==========

    def categoryContent(self, tid, pg, filter, extend):
        """分类内容"""
        if int(pg) == 1:
            url = f'{self.host}/genre/{tid}.html'
        else:
            url = f'{self.host}/genre/{tid}-{pg}.html'

        try:
            response = self.fetch(url, headers=self.def_headers, verify=False)
            html = response.text
            videos = self._extractList(html)
            pagecount = self._getTotalPages(html, tid)
            return {'list': videos, 'pagecount': pagecount, 'page': int(pg)}
        except Exception:
            return {'list': [], 'pagecount': 1, 'page': int(pg)}

    # ========== 搜索 ==========

    def searchContent(self, key, quick, pg='1'):
        """搜索 - 遍历所有 mid 合并去重"""
        result = []
        seen_ids = set()

        try:
            for mid in self.search_mids:
                search_url = f'{self.host}/index.php/ajax/suggest'
                params = {'mid': str(mid), 'wd': key, 'page': pg, 'limit': '20'}
                response = self.fetch(search_url, params=params, headers=self.def_headers, verify=False)
                data = json.loads(response.text)
                if data.get('code') != 1:
                    continue
                for item in data.get('list', []):
                    vid = str(item.get('id', ''))
                    if vid in seen_ids:
                        continue
                    seen_ids.add(vid)
                    result.append({
                        'vod_id': vid,
                        'vod_name': item.get('name', ''),
                        'vod_pic': item.get('pic', '').replace('#err', ''),
                        'vod_remarks': '',
                    })
        except Exception:
            pass

        return {'list': result, 'page': int(pg)}

    # ========== 详情页 ==========

    def detailContent(self, ids):
        """详情页"""
        vod_id = ids[0]

        try:
            url = f'{self.host}/detail/{vod_id}.html'
            response = self.fetch(url, headers=self.def_headers, verify=False)
            html = response.text

            # 标题
            vod_name = ''
            name_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if name_match:
                vod_name = re.sub(r'<[^>]+>', '', name_match.group(1)).strip()

            # 图片: a.video-pic 的 data-original 属性
            vod_pic = ''
            pic_match = re.search(r'<a[^>]*class="video-pic[^"]*"[^>]*data-original="([^"]+)"', html)
            if not pic_match:
                pic_match = re.search(r'<a[^>]*class="video-pic[^"]*"[^>]*data-src="([^"]+)"', html)
            if not pic_match:
                pic_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*(?:pic|img|poster)[^"]*"', html, re.S)
            if pic_match:
                vod_pic = pic_match.group(1)

            # 信息区域: <ul class="info clearfix"> 下的 <li>
            vod_year = ''
            vod_area = ''
            vod_director = ''
            vod_actor = ''
            vod_remarks = ''

            info_match = re.search(r'<ul\s+class="info\s+clearfix">(.*?)</ul>', html, re.S)
            if info_match:
                info_block = info_match.group(1)
                for li_match in re.finditer(r'<li[^>]*>(.*?)</li>', info_block, re.S):
                    li_text = re.sub(r'<[^>]+>', '', li_match.group(1)).strip()

                    if li_text.startswith('狀態'):
                        vod_remarks = re.sub(r'^狀態[：:]\s*', '', li_text).strip()
                    elif li_text.startswith('類別'):
                        vod_remarks = vod_remarks or re.sub(r'^類別[：:]\s*', '', li_text).strip()
                    elif li_text.startswith('主演'):
                        vod_actor = re.sub(r'^主演[：:]\s*', '', li_text).strip()
                    elif li_text.startswith('年代'):
                        ym = re.search(r'(\d{4})', li_text)
                        if ym:
                            vod_year = ym.group(1)
                    elif li_text.startswith('導演'):
                        vod_director = re.sub(r'^導演[：:]\s*', '', li_text).strip()
                    elif '國家' in li_text or '地區' in li_text:
                        vod_area = re.sub(r'^.*?[：:]\s*', '', li_text).strip()

            # 简介: 优先 meta description
            vod_content = ''
            meta_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html)
            if meta_match:
                vod_content = meta_match.group(1).strip()
                # 清理标题前缀 (如 "海角遇見愛線上看，")
                vod_content = re.sub(r'^.*?線上看[，,]?\s*', '', vod_content).strip()
                vod_content = re.sub(r'\[.*?\],?', '', vod_content).strip()

            # 备选: span class=detail
            if not vod_content:
                detail_match = re.search(r'<span[^>]*class="[^"]*detail[^"]*"[^>]*>(.*?)</span>', html, re.S)
                if detail_match:
                    vod_content = re.sub(r'<[^>]+>', '', detail_match.group(1)).strip()
                    vod_content = re.sub(r'\s+', ' ', vod_content).strip()

            # 加上简介前缀
            if vod_content:
                vod_content = '【by：轻狂书生】\n' + vod_content
            else:
                vod_content = '【by：轻狂书生】'

            # ===== 播放源: 用 id 精确匹配 tab 和 playlist =====

            # 步骤1: 从 nav-tabs 获取线路名称和 source_id
            source_map = []  # [(source_id, source_name), ...]
            tabs_match = re.search(r'<ul\s+class="[^"]*nav-tabs[^"]*"[^>]*>(.*?)</ul>', html, re.S)
            if tabs_match:
                for a_match in re.finditer(r'<a[^>]*href="#con_playlist_(\d+)"[^>]*>(.*?)</a>', tabs_match.group(1), re.S):
                    source_id = a_match.group(1)
                    source_name = re.sub(r'<[^>]+>', '', a_match.group(2)).strip()
                    source_map.append((source_id, source_name))

            # 步骤2: 从 id=con_playlist_N 精确提取每个线路的剧集
            playlist_data = {}  # {source_id: [(ep_name, href), ...]}
            for pl_match in re.finditer(r'<ul[^>]*id="con_playlist_(\d+)"[^>]*>(.*?)</ul>', html, re.S):
                pl_id = pl_match.group(1)
                pl_html = pl_match.group(2)
                episodes = []
                for a_match in re.finditer(r'<a[^>]*href="(/play/[^"]+)"[^>]*>(.*?)</a>', pl_html, re.S):
                    href = a_match.group(1)
                    ep_name = re.sub(r'<[^>]+>', '', a_match.group(2)).strip()
                    if not ep_name:
                        ep_match = re.search(r'/play/\d+-\d+-(\d+)\.html', href)
                        ep_name = f'第{int(ep_match.group(1)):02d}集' if ep_match else href
                    episodes.append((ep_name, href))
                if pl_id not in playlist_data:
                    playlist_data[pl_id] = episodes

            # 步骤3: 按 source_map 顺序组装播放源
            play_from = []
            play_url = []

            for source_id, source_name in source_map:
                if self.self_operated and source_name in self.self_operated:
                    continue

                episodes = playlist_data.get(source_id, [])
                if not episodes:
                    continue

                ep_list = []
                for ep_name, href in episodes:
                    ep_list.append(f'{ep_name}${self.host}{href}')

                play_from.append(source_name.replace(' ', ''))
                play_url.append('#'.join(ep_list))

            video = {
                'vod_id': vod_id,
                'vod_name': vod_name,
                'vod_pic': vod_pic,
                'vod_year': vod_year,
                'vod_area': vod_area,
                'vod_director': vod_director,
                'vod_actor': vod_actor,
                'vod_content': vod_content,
                'vod_remarks': vod_remarks,
                'vod_play_from': '$$$'.join(play_from) if play_from else '',
                'vod_play_url': '$$$'.join(play_url) if play_url else '',
            }

            return {'list': [video]}
        except Exception:
            return {'list': []}

    # ========== 播放解析 ==========

    def playerContent(self, flag, vid, vip_flags):
        """播放解析"""
        jx = 0
        url = ''

        try:
            response = self.fetch(vid, headers=self.def_headers, verify=False)
            html = response.text

            # 1. 优先提取 player_data JSON
            video_url = ''
            play_from = ''
            player_match = re.search(r'player_data\s*=\s*(\{.+?\})\s*;', html, re.S)
            if not player_match:
                player_match = re.search(r'player_data\s*=\s*(\{.+?\})\s*</script>', html, re.S)
            if not player_match:
                player_match = re.search(r'player_aaaa\s*=\s*(\{.+?\})\s*</script>', html, re.S)
            if not player_match:
                player_match = re.search(r'player_aaaa\s*=\s*(\{.+?\})\s*;', html, re.S)

            if player_match:
                json_str = player_match.group(1).strip()
                json_str = re.sub(r'<[^>]+>$', '', json_str).strip()
                try:
                    player_data = json.loads(json_str)
                    video_url = player_data.get('url', '')
                    play_from = player_data.get('from', '')
                    if video_url and '\\u' in video_url:
                        video_url = video_url.encode('utf-8').decode('unicode_escape')
                except json.JSONDecodeError:
                    url_match = re.search(r'"url"\s*:\s*"([^"]+)"', json_str)
                    if url_match:
                        video_url = url_match.group(1)
                        if '\\u' in video_url:
                            video_url = video_url.encode('utf-8').decode('unicode_escape')

            # 2. 备选: iframe
            if not video_url:
                iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
                if iframe_match:
                    video_url = iframe_match.group(1)
                    if video_url.startswith('//'):
                        video_url = 'https:' + video_url

            # 3. 兜底: 直接 m3u8/mp4
            if not video_url:
                m3u8_match = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if m3u8_match:
                    video_url = m3u8_match.group(1)
                if not video_url:
                    mp4_match = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
                    if mp4_match:
                        video_url = mp4_match.group(1)

            # 4. 判断是否需要解析
            if video_url:
                # 直链: m3u8/mp4 直接播放
                if '.m3u8' in video_url or '.mp4' in video_url:
                    url = video_url
                    jx = 0
                # JD- 加密线路: 用 /d/parse.php 解析
                elif video_url.startswith('JD-') or 'JD-' in video_url:
                    parsed = self._parse_jd(video_url)
                    if parsed:
                        url = parsed
                        jx = 0
                    else:
                        url = video_url
                        jx = 1
                # VIP 平台链接: 用 /v/parse.php 解析
                elif re.search(r'(?:v\.youku|www\.iqiyi|v\.qq|www\.bilibili|www\.mgtv|www\.le\.com|tv\.sohu|www\.pptv)\.com', video_url):
                    parsed = self._parse_vip(video_url)
                    if parsed:
                        url = parsed
                        jx = 0
                    else:
                        url = video_url
                        jx = 1
                # 其他非直链
                else:
                    url = video_url
                    jx = 1

            if not url:
                url = vid
                jx = 1

        except Exception:
            url = vid
            jx = 1

        return {
            'jx': jx,
            'parse': 0,
            'url': url,
            'header': {
                **self.def_headers,
                'Referer': self.host + '/',
            }
        }

    def _parse_jd(self, jd_url):
        """解析 JD- 加密线路 (4K/超清/2K 等)"""
        try:
            parse_api = f'https://play.gimyai.tw/d/parse.php?url={jd_url}'
            parse_headers = {
                **self.def_headers,
                'Referer': 'https://play.gimyai.tw/',
                'X-Requested-With': 'XMLHttpRequest',
            }
            response = self.fetch(parse_api, headers=parse_headers, verify=False)
            data = json.loads(response.text)
            if str(data.get('code')) == '200':
                return data.get('url', '')
        except Exception:
            pass
        return None

    def _parse_vip(self, video_url):
        """解析 VIP 平台链接 (优酷/奇异/腾讯/芒果等)"""
        try:
            parse_api = f'https://play.gimyai.tw/v/parse.php?url={video_url}'
            parse_headers = {
                **self.def_headers,
                'Referer': 'https://play.gimyai.tw/',
                'X-Requested-With': 'XMLHttpRequest',
            }
            response = self.fetch(parse_api, headers=parse_headers, verify=False)
            data = json.loads(response.text)
            if str(data.get('code')) == '200':
                return data.get('url', '')
        except Exception:
            pass
        return None

    # ========== 辅助方法 ==========

    def _extractList(self, html):
        """从HTML提取视频列表"""
        videos = []
        seen_ids = set()

        for li_match in re.finditer(r'<li\s+class="col-md-2[^"]*">(.*?)</li>', html, re.S):
            li_html = li_match.group(1)

            # 图片和链接
            pic_a_match = re.search(
                r'<a\s+class="video-pic[^"]*"[^>]*data-original="([^"]*)"[^>]*href="(/detail/\d+\.html)"[^>]*title="([^"]*)"',
                li_html
            )
            if not pic_a_match:
                pic_a_match = re.search(
                    r'<a\s+class="video-pic[^"]*"[^>]*href="(/detail/\d+\.html)"[^>]*data-original="([^"]*)"[^>]*title="([^"]*)"',
                    li_html
                )
                if pic_a_match:
                    href = pic_a_match.group(1)
                    pic = pic_a_match.group(2)
                    title = pic_a_match.group(3)
                else:
                    continue
            else:
                pic = pic_a_match.group(1)
                href = pic_a_match.group(2)
                title = pic_a_match.group(3)

            vid_match = re.search(r'/detail/(\d+)\.html', href)
            if not vid_match:
                continue
            vid = vid_match.group(1)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            # 解码 HTML 实体
            pic = pic.replace('&amp;', '&')

            # 状态: <span class="note text-bg-r">
            remark = ''
            note_match = re.search(r'<span\s+class="note[^"]*">(.*?)</span>', li_html, re.S)
            if note_match:
                remark = re.sub(r'<[^>]+>', '', note_match.group(1)).strip()

            # 演员: <div class="subtitle ...">
            actor = ''
            sub_match = re.search(r'<div\s+class="subtitle[^"]*">(.*?)</div>', li_html, re.S)
            if sub_match:
                actor = re.sub(r'<[^>]+>', '', sub_match.group(1)).strip()

            videos.append({
                'vod_id': vid,
                'vod_name': title,
                'vod_pic': pic,
                'vod_remarks': remark,
                'vod_actor': actor,
            })

        return videos

    def _getTotalPages(self, html, tid):
        """从分页区获取总页数"""
        tail_match = re.search(
            r'<a[^>]*href="/genre/' + re.escape(tid) + r'-(\d+)\.html"[^>]*>尾頁</a>',
            html
        )
        if not tail_match:
            tail_match = re.search(
                r'<a[^>]*href="/genre/' + re.escape(tid) + r'-(\d+)\.html"[^>]*>末页</a>',
                html
            )
        if tail_match:
            return int(tail_match.group(1))
        return 1

    # ========== 必需方法 ==========

    def init(self, extend=''):
        pass

    def getName(self):
        return 'Gimy劇迷'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass
