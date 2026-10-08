# coding=utf-8
"""
目标站: 草莓短剧网 (https://www.cmicq.com)
模板: 苹果CMS (MyTheme)
修复: SSL连接重置、图片URL补全、播放列表多线路解析
"""
import re
import sys
import json
import urllib.parse
import time
from bs4 import BeautifulSoup

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def init(self, extend=""):
        self.site_url = "https://www.cmicq.com"
        self.http_url = "http://www.cmicq.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': self.site_url + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        self.categories = [
            {"type_id": "25", "type_name": "重生民国"},
            {"type_id": "26", "type_name": "穿越现代"},
            {"type_id": "27", "type_name": "反转爽剧"},
            {"type_id": "28", "type_name": "言情总裁"},
            {"type_id": "29", "type_name": "现代都市"},
            {"type_id": "30", "type_name": "古装仙侠"},
            {"type_id": "31", "type_name": "悬疑烧脑"},
        ]
        self.filters = {
            "25": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "重生", "v": "重生"}, {"n": "民国", "v": "民国"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}
                ]}
            ],
            "26": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "穿越", "v": "穿越"}, {"n": "现代", "v": "现代"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}
                ]}
            ],
            "27": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "反转", "v": "反转"}, {"n": "爽剧", "v": "爽剧"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}
                ]}
            ],
            "28": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "言情", "v": "言情"}, {"n": "总裁", "v": "总裁"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}
                ]}
            ],
            "29": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "都市", "v": "都市"}, {"n": "现代", "v": "现代"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}
                ]}
            ],
            "30": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "古装", "v": "古装"}, {"n": "仙侠", "v": "仙侠"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}
                ]}
            ],
            "31": [
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "悬疑", "v": "悬疑"}, {"n": "烧脑", "v": "烧脑"}
                ]},
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}
                ]}
            ],
        }

    def _safe_fetch(self, url, headers=None, max_retry=3):
        """带重试的安全请求，自动降级 http/https"""
        if headers is None:
            headers = self.headers
        last_err = None
        for i in range(max_retry):
            try:
                resp = self.fetch(url, headers=headers)
                if resp:
                    return resp
            except Exception as e:
                last_err = e
                # 如果是 SSL 错误，尝试降级到 HTTP
                if url.startswith('https://') and i == 0:
                    try:
                        http_url = url.replace('https://', 'http://', 1)
                        resp = self.fetch(http_url, headers=headers)
                        if resp:
                            return resp
                    except Exception:
                        pass
                time.sleep(0.5)
        return None

    def _fix_url(self, url):
        if not url:
            return ''
        if url.startswith('http'):
            return url
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.site_url + url
        return self.site_url + '/' + url

    def _build_cat_url(self, tid, pg, extend):
        ext = {}
        if extend:
            if isinstance(extend, str):
                try:
                    ext = json.loads(extend)
                except Exception:
                    pass
            elif isinstance(extend, dict):
                ext = extend
        cls = ext.get('class', '')
        year = ext.get('year', '')
        by = ext.get('by', '')
        if not cls and not year and not by:
            if int(pg) <= 1:
                return f"{self.site_url}/duanju/index{tid}.html"
            else:
                return f"{self.site_url}/duanju/index{tid}-{pg}.html"
        else:
            return f"{self.site_url}/vodshow/{tid}-{cls}---{year}---{by}-{pg}.html"

    def _parse_video_list(self, soup, max_count=0):
        video_list = []
        seen = set()
        boxes = soup.select('.myui-vodlist__box')
        for box in boxes:
            a = box.select_one('a.myui-vodlist__thumb')
            if not a:
                continue
            href = a.get('href', '')
            m = re.search(r'/movie/index(\d+)\.html', href)
            if not m:
                continue
            vod_id = m.group(1)
            if vod_id in seen:
                continue
            seen.add(vod_id)
            title = a.get('title', '')
            if not title:
                continue
            pic = self._fix_url(a.get('data-original', '') or a.get('src', ''))
            remark = ''
            remark_elem = a.select_one('.pic-text.text-right')
            if remark_elem:
                remark = remark_elem.get_text(strip=True)
            video_list.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
            if max_count > 0 and len(video_list) >= max_count:
                break
        if not video_list:
            for a_tag in soup.select('a[href*="/movie/index"]'):
                href = a_tag.get('href', '')
                m = re.search(r'/movie/index(\d+)\.html', href)
                if not m:
                    continue
                vod_id = m.group(1)
                if vod_id in seen:
                    continue
                seen.add(vod_id)
                title = a_tag.get('title', '') or a_tag.get_text(strip=True)
                if not title:
                    continue
                pic = self._fix_url(a_tag.get('data-original', '') or a_tag.get('src', ''))
                video_list.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "",
                })
                if max_count > 0 and len(video_list) >= max_count:
                    break
        return video_list

    def _extract_page_info(self, soup, tid, default_page):
        pagecount = default_page
        total = 0
        page_elem = soup.select_one('.page')
        if page_elem:
            for a in page_elem.select('a[href]'):
                href = a.get('href', '')
                mm = re.search(r'/duanju/index%s-(\d+)\.html' % re.escape(str(tid)), href)
                if mm:
                    pagecount = max(pagecount, int(mm.group(1)))
                mm2 = re.search(r'-(\d+)\.html$', href)
                if mm2:
                    pagecount = max(pagecount, int(mm2.group(1)))
                mm3 = re.search(r'[?&]page=(\d+)', href)
                if mm3:
                    pagecount = max(pagecount, int(mm3.group(1)))
            total_text = page_elem.get_text()
            tt = re.search(r'共\s*(\d+)\s*(条|部|个|影片)?', total_text)
            if tt:
                total = int(tt.group(1))
        if not total:
            total = 30 * pagecount
        return pagecount, total

    def homeContent(self, filter):
        url = self.site_url + "/index.html"
        resp = self._safe_fetch(url)
        video_list = []
        if resp:
            soup = BeautifulSoup(resp.text, 'html.parser')
            video_list = self._parse_video_list(soup, max_count=36)
        return {"class": self.categories, "list": video_list, "filters": self.filters}

    def homeVideoContent(self):
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        url = self._build_cat_url(tid, page, extend)
        resp = self._safe_fetch(url)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1, "limit": 30, "total": 0}
        soup = BeautifulSoup(resp.text, 'html.parser')
        video_list = self._parse_video_list(soup)
        pagecount, total = self._extract_page_info(soup, tid, page)
        return {
            "list": video_list,
            "page": page,
            "pagecount": pagecount,
            "limit": 30,
            "total": total
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        url = f"{self.site_url}/movie/index{vod_id}.html"
        resp = self._safe_fetch(url)
        if not resp:
            return {"list": []}
        soup = BeautifulSoup(resp.text, 'html.parser')

        vod_name = vod_id
        title_tag = soup.select_one('title')
        if title_tag:
            raw = title_tag.get_text()
            vod_name = raw.split('-')[0].split('在线观看')[0].strip()
        if not vod_name or vod_name == vod_id:
            h1 = soup.select_one('h1')
            if h1:
                vod_name = h1.get_text(strip=True)

        vod_pic = ''
        for sel in ['.myui-content__thumb img', '.myui-vodlist__thumb img', '.content-thumb img', '.detail-pic img']:
            thumb = soup.select_one(sel)
            if thumb:
                vod_pic = self._fix_url(thumb.get('data-original', '') or thumb.get('src', ''))
                if vod_pic:
                    break
        if not vod_pic:
            for img in soup.select('img[data-original]'):
                src = img.get('data-original', '')
                if 'upload/vod' in src or 'upload' in src:
                    vod_pic = self._fix_url(src)
                    break

        vod_content = ''
        for sel in ['.myui-content__detail .desc', '.myui-content__detail', '.content-detail', '.vod_content', '#content', '.detail-content']:
            elem = soup.select_one(sel)
            if elem:
                vod_content = elem.get_text(' ', strip=True)
                vod_content = re.sub(r'展开全部|收起$', '', vod_content).strip()
                if len(vod_content) > 10:
                    break
        vod_content = re.sub(r'^(简介\s*：\s*)+', '', vod_content).strip()

        vod_actor = vod_director = vod_area = vod_year = ''
        detail = soup.select_one('.myui-content__detail') or soup.select_one('.detail-info') or soup
        if detail:
            for p in detail.select('p'):
                text = p.get_text(strip=True)
                if not text:
                    continue
                if text.startswith('主演') or text.startswith('演员'):
                    vod_actor = text.split('：', 1)[-1].strip() if '：' in text else text[2:].strip()
                elif text.startswith('导演'):
                    vod_director = text.split('：', 1)[-1].strip() if '：' in text else text[2:].strip()
                elif text.startswith('年份') or text.startswith('年代'):
                    vod_year = text.split('：', 1)[-1].strip() if '：' in text else text.replace('年份', '').replace('年代', '').strip()
                elif text.startswith('地区'):
                    vod_area = text.split('：', 1)[-1].strip() if '：' in text else text.replace('地区', '').strip()

        play_from_list = []
        play_url_list = []

        playlist_wrappers = soup.select('.myui-content__list') or soup.select('#playlist') or soup.select('.tab-content') or soup.select('.play-list')
        if not playlist_wrappers:
            playlist_wrappers = [soup]

        for wrapper in playlist_wrappers:
            groups = {}
            for a in wrapper.select('a[href]'):
                href = a.get('href', '')
                if 'javascript' in href or not href:
                    continue
                ep_name = a.get('title', '') or a.get_text(strip=True)
                if not ep_name:
                    continue

                m = re.search(r'/play/index(\d+)-(\d+)-(\d+)\.html', href)
                if m:
                    line = m.group(2)
                    groups.setdefault(line, []).append(f"{ep_name}${self._fix_url(href)}")
                    continue

                m2 = re.search(r'/vodplay/(\d+)-(\d+)-(\d+)\.html', href)
                if m2:
                    line = m2.group(2)
                    groups.setdefault(line, []).append(f"{ep_name}${self._fix_url(href)}")
                    continue

                m3 = re.search(r'/play/(\d+)-(\d+)-(\d+)\.html', href)
                if m3:
                    line = m3.group(2)
                    groups.setdefault(line, []).append(f"{ep_name}${self._fix_url(href)}")
                    continue

                if '/play/' in href or '/vodplay/' in href:
                    groups.setdefault('0', []).append(f"{ep_name}${self._fix_url(href)}")

            if groups:
                for line in sorted(groups.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
                    line_name = f"线路{int(line) + 1}" if str(line).isdigit() else str(line)
                    play_from_list.append(line_name)
                    play_url_list.append('#'.join(groups[line]))

        if not play_url_list:
            play_from_list.append('默认线路')
            play_url_list.append(f"播放${self.site_url}/movie/index{vod_id}.html")

        vod_play_from = '$$$'.join(play_from_list)
        vod_play_url = '$$$'.join(play_url_list)

        result = [{
            "vod_id": vod_id,
            "vod_name": vod_name,
            "vod_pic": vod_pic,
            "vod_content": vod_content,
            "vod_actor": vod_actor,
            "vod_director": vod_director,
            "vod_area": vod_area,
            "vod_year": vod_year,
            "vod_play_from": vod_play_from,
            "vod_play_url": vod_play_url
        }]
        return {"list": result}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.site_url}/search.php?searchword={encoded_key}"
        if page > 1:
            url += f"&page={page}"
        resp = self._safe_fetch(url)
        if not resp:
            return {"list": [], "page": page, "pagecount": 1}
        soup = BeautifulSoup(resp.text, 'html.parser')
        video_list = self._parse_video_list(soup)
        pagecount = 1
        page_elem = soup.select_one('.page')
        if page_elem:
            for a in page_elem.select('a[href]'):
                mm = re.search(r'[?&]page=(\d+)', a.get('href', ''))
                if mm:
                    pagecount = max(pagecount, int(mm.group(1)))
        return {"list": video_list, "page": page, "pagecount": pagecount}

    def playerContent(self, flag, id, vipFlags):
        if id.startswith('http'):
            play_url = id
        elif id.startswith('/'):
            play_url = self.site_url + id
        else:
            play_url = self.site_url + '/' + id
        resp = self._safe_fetch(play_url)
        if not resp:
            return {"parse": 1, "url": play_url, "header": self.headers}
        html = resp.text
        now_match = re.search(r'var\s+now\s*=\s*"([^"]+)"', html)
        if now_match:
            video_url = now_match.group(1)
            if video_url and video_url.startswith('http'):
                return {"parse": 0, "url": video_url, "header": self.headers}
        player_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html)
        if player_match:
            return {"parse": 0, "url": player_match.group(1), "header": self.headers}
        m3u8 = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
        if m3u8:
            return {"parse": 0, "url": m3u8.group(0), "header": self.headers}
        iframe = re.search(r'<iframe[^>]+src="([^"]+)"', html)
        if iframe:
            iframe_url = iframe.group(1)
            if not iframe_url.startswith('http'):
                iframe_url = self.site_url + iframe_url if iframe_url.startswith('/') else self.site_url + '/' + iframe_url
            iframe_resp = self._safe_fetch(iframe_url)
            if iframe_resp:
                iframe_html = iframe_resp.text
                m = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', iframe_html)
                if m:
                    return {"parse": 0, "url": m.group(0), "header": self.headers}
        mac_match = re.search(r'mac_player_config\s*=\s*({.*?})', html, re.DOTALL)
        if mac_match:
            try:
                cfg = json.loads(mac_match.group(1))
                video_url = cfg.get('url', '')
                if video_url and '.m3u8' in video_url:
                    return {"parse": 0, "url": video_url, "header": self.headers}
            except Exception:
                pass
        return {"parse": 1, "url": play_url, "header": self.headers}
