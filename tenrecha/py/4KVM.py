# -*- coding: utf-8 -*-
"""
目标站: 4KVM  (道长DR框架格式 - Alpine.js 增强播放解析)
首页: https://www.4kvm.net
"""
import re
import json
import time
import random
import urllib.parse
from bs4 import BeautifulSoup
from base.spider import Spider


class Spider(Spider):
    # 道长格式类属性
    def_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    host = 'https://www.4kvm.net'

    def getName(self):
        return '4KVM'

    def init(self, extend=''):
        try:
            self._fetch('/')
        except:
            pass

    # ---------- 首页 ----------
    def homeContent(self, filter):
        html = self._fetch('/')
        video_list = self._extractList(html) if html else []
        # 返回分类（写死）和列表，可选筛选条件
        return {
            'class': [
                {'type_id': '1', 'type_name': '电影'},
                {'type_id': '2', 'type_name': '电视剧'},
                {'type_id': '3', 'type_name': '动漫'},
            ],
            'list': video_list,
            'filters': self._getFilters()  # 保留动态筛选功能
        }

    def homeVideoContent(self):
        return self.categoryContent('1', 1, {}, {})

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        params = {'classify': tid}
        if extend:
            for k, v in extend.items():
                if v and v != '' and k != 'classify':
                    params[k] = v
        if page > 1:
            params['page'] = page
        query = urllib.parse.urlencode(params)
        html = self._fetch(f'/filter?{query}')
        return {
            'page': page,
            'pagecount': 99,
            'limit': 24,
            'total': 999,
            'list': self._extractList(html) if html else []
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg='1'):
        page = int(pg) if pg else 1
        params = {'q': key}
        if page > 1:
            params['page'] = page
        query = urllib.parse.urlencode(params)
        html = self._fetch(f'/search?{query}')
        return {
            'list': self._extractList(html) if html else [],
            'page': page,
            'pagecount': 1,
            'limit': 24,
            'total': 0
        }

    # ---------- 详情 ----------
    def detailContent(self, ids):
        result = {'list': []}
        vid = ids[0].split(',')[0].strip()
        try:
            html = self._fetch(f'/play/{vid}')
            if not html:
                return result
            soup = BeautifulSoup(html, 'html.parser')
            # 标题
            title_tag = soup.select_one('h1') or soup.select_one('h2')
            vod_name = title_tag.get_text(strip=True) if title_tag else vid
            # 海报
            vod_pic = ''
            img = soup.select_one('img.w-full') or soup.select_one('img[data-src]') or soup.select_one('img[src]')
            if img:
                src = img.get('data-src', '') or img.get('src', '')
                if src and not src.startswith('data:'):
                    vod_pic = self._fixPic(src)
            # 导演/演员/简介
            vod_director = ''
            vod_actor = ''
            vod_content = ''
            info_area = soup.select_one('.rounded-lg div.grid') or soup.select_one('div.grid')
            if info_area:
                txt = info_area.get_text(' ', strip=True)
                dm = re.search(r'导演[：:]\s*([^主\n]+)', txt)
                if dm: vod_director = dm.group(1).strip()
                am = re.search(r'主演[：:]\s*([^剧\n]+)', txt)
                if am: vod_actor = am.group(1).strip()
                cm = re.search(r'(?:剧情)?简介[：:]\s*(.+?)(?:\n|$)', txt)
                if cm: vod_content = cm.group(1).strip()
            # 分集解析（基于 episodeManager）
            play_from, play_url = [], []
            ep_mgr = soup.select_one('[x-data*="episodeManager"]')
            if ep_mgr:
                # 提取所有剧集链接
                eps = ep_mgr.select('a[data-episode][href]')
                if eps:
                    lines = {}
                    for a in eps:
                        line = a.get('data-line', '1')
                        ep = a.get('data-episode', '')
                        href = a.get('href', '')
                        if not href:
                            continue
                        if not href.startswith('http'):
                            href = self.host + href
                        lines.setdefault(line, []).append((int(ep) if ep else 0, href, a.get_text(strip=True)))
                    for line_key in sorted(lines.keys()):
                        line_eps = sorted(lines[line_key], key=lambda x: x[0])
                        ep_strs = []
                        for e in line_eps:
                            ep_strs.append(f'{e[2] or "第"+str(e[0])+"集"}${e[1]}')
                        play_from.append(f'线路{line_key}')
                        play_url.append('#'.join(ep_strs))
            if not play_url:
                play_from.append('播放')
                play_url.append(f'播放${vid}')
            result['list'].append({
                'vod_id': vid,
                'vod_name': vod_name,
                'vod_pic': vod_pic,
                'vod_director': vod_director,
                'vod_actor': vod_actor,
                'vod_content': vod_content,
                'vod_play_from': '$$$'.join(play_from),
                'vod_play_url': '$$$'.join(play_url)
            })
        except Exception as e:
            print(f'详情解析错误: {e}')
        return result

    # ---------- 播放器 (Alpine.js 增强) ----------
    def playerContent(self, flag, id, vipFlags, depth=0):
        try:
            if depth > 3:  # 防止无限递归
                return {
                    'parse': 1,
                    'url': id if id.startswith('http') else f'{self.host}/play/{id}',
                    'header': self.def_headers
                }
            if id.startswith('http'):
                url = id
            else:
                url = f'{self.host}/play/{id}'
            time.sleep(random.uniform(0.3, 0.8))
            html = self._fetch(url)
            if not html:
                return {'parse': 1, 'url': url, 'header': self.def_headers}
            header = {'User-Agent': self.def_headers['User-Agent'], 'Referer': url}

            # ---- 策略1：Alpine.js x-data 播放器 / episodeManager ----
            # 提取 x-data 中的 JSON 对象（处理单引号、尾逗号等）
            xdata_patterns = [
                r'x-data\s*=\s*["\']\s*player\s*\(\s*(\{.*?\})\s*\)\s*["\']',
                r'x-data\s*=\s*["\']\s*(\{[^"\'<>]*?url\s*:\s*["\'][^"\']+[^"\'<>]*?\})\s*["\']',
                r'x-data\s*=\s*["\']\s*episodeManager\s*\(\s*(\{.*?\})\s*\)\s*["\']',
            ]
            for pat in xdata_patterns:
                m = re.search(pat, html, re.S | re.I)
                if m:
                    try:
                        raw = m.group(1)
                        # 简单处理非标准JSON
                        raw = re.sub(r"'", '"', raw)
                        raw = re.sub(r',\s*[,}]', lambda x: x.group(0).replace(',', ''), raw)  # 去掉多余逗号
                        data = json.loads(raw)
                        # 优先获取直接 url
                        pu = data.get('url', '')
                        if pu:
                            if pu.startswith('//'):
                                pu = 'https:' + pu
                            if pu.endswith('.m3u8') or pu.endswith('.mp4'):
                                return {'parse': 0, 'url': pu, 'header': header}
                            elif pu.startswith('http'):
                                return {'parse': 1, 'url': pu, 'header': header}
                        # 其次从 episodes 和 current 中取当前集
                        episodes = data.get('episodes', [])
                        current = data.get('current', data.get('currentIndex', 0))
                        if isinstance(episodes, list) and len(episodes) > 0:
                            idx = int(current) if isinstance(current, (int, str)) and str(current).isdigit() else 0
                            if 0 <= idx < len(episodes):
                                ep = episodes[idx]
                                if isinstance(ep, dict):
                                    ep_url = ep.get('url', '')
                                else:
                                    ep_url = str(ep)
                                if ep_url:
                                    if ep_url.startswith('//'):
                                        ep_url = 'https:' + ep_url
                                    elif not ep_url.startswith('http'):
                                        ep_url = self.host + '/' + ep_url.lstrip('/')
                                    if ep_url.endswith(('.m3u8', '.mp4')):
                                        return {'parse': 0, 'url': ep_url, 'header': header}
                                    else:
                                        # 再次请求该播放页（递归一次）
                                        return self.playerContent(flag, ep_url, vipFlags, depth + 1)
                    except:
                        pass

            # ---- 策略2：传统 player_aaaa ----
            m = re.search(r'player_aaaa\s*=\s*(\{[^;]+\})', html, re.S)
            if m:
                try:
                    pd = json.loads(m.group(1))
                    pu = pd.get('url', '')
                    if pu:
                        if pu.startswith('//'):
                            pu = 'https:' + pu
                        if pu.endswith('.m3u8') or pu.endswith('.mp4'):
                            return {'parse': 0, 'url': pu, 'header': header}
                        if pu.startswith('http'):
                            return {'parse': 1, 'url': pu, 'header': header}
                except:
                    pass

            # ---- 策略3：正则直接匹配 m3u8/mp4 ----
            media_patterns = [
                r'url\s*:\s*["\']([^"\']+\.m3u8)["\']',
                r'url\s*:\s*["\']([^"\']+\.mp4)["\']',
                r'src\s*:\s*["\']([^"\']+\.m3u8)["\']',
                r'["\']([^"\']*\.m3u8[^"\']*)["\']',
                r'video:\s*["\']([^"\']+)["\']',
            ]
            for pat in media_patterns:
                m = re.search(pat, html, re.I)
                if m:
                    pu = m.group(1)
                    if pu.startswith('//'):
                        pu = 'https:' + pu
                    elif not pu.startswith('http'):
                        pu = self.host + '/' + pu.lstrip('/')
                    if pu.endswith('.m3u8') or pu.endswith('.mp4'):
                        return {'parse': 0, 'url': pu, 'header': header}
                    else:
                        return {'parse': 1, 'url': pu, 'header': header}

            # ---- 策略4：iframe ----
            soup = BeautifulSoup(html, 'html.parser')
            iframe = soup.find('iframe')
            if iframe and iframe.get('src'):
                src = iframe['src']
                if src.startswith('//'):
                    src = 'https:' + src
                elif not src.startswith('http'):
                    src = self.host + '/' + src.lstrip('/')
                return {'parse': 1, 'url': src, 'header': header}

            # ---- 策略5：episodeManager 当前激活链接 ----
            ep_mgr = soup.select_one('[x-data*="episodeManager"]')
            if ep_mgr:
                active = ep_mgr.select_one('a.bg-indigo-600, a[class*="bg-indigo"]') or ep_mgr.select_one('a[data-episode]')
                if active and active.get('href'):
                    href = active['href']
                    if href.startswith('//'):
                        href = 'https:' + href
                    elif not href.startswith('http'):
                        href = self.host + href
                    return {'parse': 1, 'url': href, 'header': header}

            # 回退
            return {'parse': 1, 'url': url, 'header': self.def_headers}
        except Exception as e:
            return {'parse': 1, 'url': id, 'header': self.def_headers}

    # ---------- 列表解析 ----------
    def _extractList(self, html):
        if not html:
            return []
        videos = []
        seen = set()
        try:
            soup = BeautifulSoup(html, 'html.parser')
            cards = soup.select('div[data-vod-id]')
            if not cards:
                cards = soup.find_all('a', href=re.compile(r'/play/'))
            for card in cards:
                try:
                    if card.name == 'a' and '/play/' in card.get('href', ''):
                        a = card
                    else:
                        a = card.find('a', href=re.compile(r'/play/'))
                    if not a:
                        continue
                    href = a.get('href', '')
                    vid = href.split('/play/')[-1].strip()
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    # 标题
                    if card.name == 'a':
                        title = card.get('title', '') or card.get_text(strip=True)
                    else:
                        h = card.find('h3') or card.find('h2')
                        title = h.get_text(strip=True) if h else a.get_text(strip=True)
                    if not title:
                        title = vid
                    # 图片
                    pic = ''
                    img = card.find('img') if card.name != 'img' else card
                    if img:
                        src = img.get('data-src', '') or img.get('src', '')
                        if src and not src.startswith('data:'):
                            pic = self._fixPic(src)
                    # 备注
                    remark = ''
                    for cls in ('.pic-text', '.remarks', '.text-green-500', '.text-yellow-400'):
                        tag = card.select_one(cls)
                        if tag:
                            remark = tag.get_text(strip=True)
                            break
                    videos.append({
                        'vod_id': vid,
                        'vod_name': title.strip(),
                        'vod_pic': pic,
                        'vod_remarks': remark
                    })
                except:
                    continue
        except Exception as e:
            print(f'列表解析错误: {e}')
        return videos

    # ---------- 筛选条件（动态） ----------
    def _getFilters(self):
        try:
            html = self._fetch('/filter?classify=1')
            if not html:
                return {}
            soup = BeautifulSoup(html, 'html.parser')
            filters = {}
            sections = soup.select('div.flex.flex-wrap')
            for sec in sections:
                links = sec.select('a[href*="classify="]')
                if len(links) < 2:
                    continue
                # 提取键名和组名
                param_key = None
                group_name = ''
                for a in links:
                    href = a.get('href', '')
                    parsed = urllib.parse.urlparse(href)
                    qs = urllib.parse.parse_qs(parsed.query)
                    for k in qs:
                        if k not in ('classify', 'page', 'sort_by', 'order'):
                            param_key = k
                            first_text = links[0].get_text(strip=True)
                            if '全部' in first_text:
                                group_name = first_text.replace('全部', '').strip()
                            break
                    if param_key:
                        break
                if not param_key or not group_name:
                    continue
                options = []
                for a in links:
                    text = a.get_text(strip=True)
                    href = a.get('href', '')
                    parsed = urllib.parse.urlparse(href)
                    qs = urllib.parse.parse_qs(parsed.query)
                    val = ''
                    if '全部' not in text or text != links[0].get_text(strip=True):
                        val = qs.get(param_key, [''])[0]
                    options.append({'n': text, 'v': val})
                if options:
                    filters[param_key] = {
                        'key': param_key,
                        'name': group_name,
                        'value': options
                    }
            return filters
        except:
            return {}

    # ---------- 工具 ----------
    def _fetch(self, url):
        try:
            if not url.startswith('http'):
                url = self.host + url
            time.sleep(random.uniform(0.3, 0.7))
            rsp = self.fetch(url, headers=self.def_headers, verify=False)
            return rsp.text if rsp and rsp.status_code == 200 else ''
        except:
            return ''

    def _fixPic(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if not u.startswith('http'):
            return self.host + '/' + u.lstrip('/')
        return u.replace('&amp;', '&')

    # ---------- 必需空方法 ----------
    def localProxy(self, param=''):
        return {}
    def isVideoFormat(self, url):
        return url.endswith(('.m3u8', '.mp4', '.flv')) if url else False
    def manualVideoCheck(self):
        return False
