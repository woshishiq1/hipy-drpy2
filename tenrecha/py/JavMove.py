# -*- coding: utf-8 -*-
# TVBox Python Spider for JavMove
# Generated from JS source

import sys
sys.path.append('..')
from base.spider import Spider
import json
import requests
from bs4 import BeautifulSoup
import re
import urllib.parse

class Spider(Spider):
    def __init__(self):
        super().__init__()
        self.site = "https://javmove.com"
        self.UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0.1 Mobile/15E148 Safari/604.1"
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.site
        }

    def getName(self):
        return "JavMove"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        # 判断是否为视频直链格式
        video_formats = ['.mp4', '.m3u8', '.flv', '.avi', '.mkv', '.mov', '.wmv']
        for fmt in video_formats:
            if fmt in url.lower():
                return True
        return False

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        # 返回首页分类和推荐
        result = {}
        classes = []

        # 分类：最新AV、即将上映
        classes.append({"type_id": "release", "type_name": "最新AV"})
        classes.append({"type_id": "upcoming", "type_name": "即将上映"})

        result["class"] = classes
        result["filters"] = {}

        # 获取首页推荐内容（最新AV第一页）
        try:
            url = f"{self.site}/release?page=1"
            rsp = requests.get(url, headers=self.headers, timeout=10)
            rsp.encoding = 'utf-8'
            soup = BeautifulSoup(rsp.text, 'html.parser')

            videos = []
            for article in soup.select("#movie-list article"):
                try:
                    a_tag = article.find('a', rel='bookmark')
                    if not a_tag:
                        continue
                    href = a_tag.get('href', '')

                    h2_tag = article.find('h2')
                    if not h2_tag:
                        continue
                    title = h2_tag.get('title', '').split(" ")[0]

                    img = article.select_one('.movie-image')
                    cover = ''
                    if img:
                        cover = img.get('data-srcset') or img.get('src', '')

                    time_tag = article.find('time')
                    pubdate = ''
                    if time_tag:
                        pubdate = time_tag.get('datetime', '').split('T')[0]

                    videos.append({
                        "vod_id": href,
                        "vod_name": title,
                        "vod_pic": cover,
                        "vod_remarks": pubdate,
                        "vod_pubdate": pubdate
                    })
                except Exception as e:
                    continue

            result["list"] = videos
        except Exception as e:
            result["list"] = []

        return json.dumps(result, ensure_ascii=False)

    def homeVideoContent(self):
        # 首页推荐视频（与homeContent的list一致即可）
        return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        # tid: release / upcoming
        # pg: 页码
        result = {}

        try:
            page = int(pg) if pg else 1
            url = f"{self.site}/{tid}?page={page}"

            rsp = requests.get(url, headers=self.headers, timeout=10)
            rsp.encoding = 'utf-8'
            soup = BeautifulSoup(rsp.text, 'html.parser')

            videos = []
            for article in soup.select("#movie-list article"):
                try:
                    a_tag = article.find('a', rel='bookmark')
                    if not a_tag:
                        continue
                    href = a_tag.get('href', '')

                    h2_tag = article.find('h2')
                    if not h2_tag:
                        continue
                    title = h2_tag.get('title', '').split(" ")[0]

                    img = article.select_one('.movie-image')
                    cover = ''
                    if img:
                        cover = img.get('data-srcset') or img.get('src', '')

                    time_tag = article.find('time')
                    pubdate = ''
                    if time_tag:
                        pubdate = time_tag.get('datetime', '').split('T')[0]

                    videos.append({
                        "vod_id": href,
                        "vod_name": title,
                        "vod_pic": cover,
                        "vod_remarks": pubdate,
                        "vod_pubdate": pubdate
                    })
                except Exception as e:
                    continue

            # 判断是否有下一页（简单判断：如果本页有内容，假设还有下一页）
            has_next = len(videos) > 0

            result["page"] = page
            result["pagecount"] = page + 1 if has_next else page
            result["limit"] = len(videos)
            result["total"] = len(videos)
            result["list"] = videos
        except Exception as e:
            result["page"] = int(pg) if pg else 1
            result["pagecount"] = int(pg) if pg else 1
            result["limit"] = 0
            result["total"] = 0
            result["list"] = []

        return json.dumps(result, ensure_ascii=False)

    def detailContent(self, ids):
        # ids: 视频ID（即href）
        result = {}
        vod_id = ids[0] if isinstance(ids, list) else ids

        try:
            url = f"{self.site}{vod_id}"
            rsp = requests.get(url, headers=self.headers, timeout=10)
            rsp.encoding = 'utf-8'
            soup = BeautifulSoup(rsp.text, 'html.parser')

            # 获取视频基本信息
            title = ''
            cover = ''
            pubdate = ''

            h2_tag = soup.find('h2')
            if h2_tag:
                title = h2_tag.get('title', '').split(" ")[0]

            img = soup.select_one('.movie-image')
            if img:
                cover = img.get('data-srcset') or img.get('src', '')

            time_tag = soup.find('time')
            if time_tag:
                pubdate = time_tag.get('datetime', '').split('T')[0]

            # 获取data-id
            video_player = soup.select_one("#video-player")
            data_id = video_player.get('data-id', '') if video_player else ''

            # 获取播放源分组
            play_from = []
            play_url = []

            format_groups = soup.select(".video-format")

            # 如果没有找到分组，尝试直接构建播放信息
            if not format_groups and data_id:
                play_from.append("默认")
                play_url.append(f"默认${data_id}")
            else:
                # 按格式优先级排序
                format_priority = {"FullHD": 1, "HD": 2, "SD": 3}
                groups = []

                for fmt_div in format_groups:
                    fmt_header = fmt_div.select_one(".video-format-header")
                    fmt_name = fmt_header.get_text(strip=True) if fmt_header else "默认"

                    tracks = []
                    for btn in fmt_div.select(".video-source-btn"):
                        href = btn.get('href', '')
                        title_text = btn.get('title', '')
                        part_match = re.search(r'part\s*(\d+)', title_text, re.I)
                        part_number = int(part_match.group(1)) if part_match else 0

                        # 获取该分段的dataID
                        part_data_id = data_id
                        if href and not href.startswith('#'):
                            try:
                                curl = f"{self.site}{href}"
                                rsp2 = requests.get(curl, headers=self.headers, timeout=10)
                                rsp2.encoding = 'utf-8'
                                soup2 = BeautifulSoup(rsp2.text, 'html.parser')
                                vp = soup2.select_one("#video-player")
                                if vp:
                                    part_data_id = vp.get('data-id', data_id)
                            except:
                                pass

                        tracks.append({
                            "part": part_number,
                            "name": f"part {part_number}",
                            "data_id": part_data_id
                        })

                    # 按part排序
                    tracks.sort(key=lambda x: x["part"])
                    groups.append({"name": fmt_name, "tracks": tracks})

                # 按格式优先级排序
                def get_priority(g):
                    name = g["name"]
                    if re.match(r'^FullHD', name, re.I):
                        return 1
                    if re.match(r'^HD', name, re.I):
                        return 2
                    if re.match(r'^SD', name, re.I):
                        return 3
                    return 999

                groups.sort(key=get_priority)

                for g in groups:
                    play_from.append(g["name"])
                    urls = []
                    for t in g["tracks"]:
                        urls.append(f"{t['name']}${t['data_id']}")
                    play_url.append("#".join(urls))

            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": cover,
                "vod_remarks": pubdate,
                "vod_pubdate": pubdate,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url)
            }

            result["list"] = [vod]
        except Exception as e:
            result["list"] = []

        return json.dumps(result, ensure_ascii=False)

    def playerContent(self, flag, id, vipFlags):
        # flag: 线路名（FullHD/HD/SD等）
        # id: dataID
        result = {}

        try:
            url = f"{self.site}/watch?token={id}"
            headers = {
                "User-Agent": self.UA,
                "Referer": "https://javquick.com/"
            }

            rsp = requests.get(url, headers=headers, timeout=10)

            # 返回的data通常是直链或m3u8地址
            play_url = rsp.text.strip()

            # 判断是否需要解析
            parse = 0 if self.isVideoFormat(play_url) else 1

            result["parse"] = parse
            result["url"] = play_url
            result["header"] = headers
        except Exception as e:
            result["parse"] = 1
            result["url"] = ""
            result["header"] = {}

        return json.dumps(result, ensure_ascii=False)

    def searchContent(self, key, quick):
        result = {}

        try:
            text = urllib.parse.quote(key)
            url = f"{self.site}/search?q={text}&page=1"

            rsp = requests.get(url, headers=self.headers, timeout=10)
            rsp.encoding = 'utf-8'
            soup = BeautifulSoup(rsp.text, 'html.parser')

            videos = []
            for article in soup.select("#movie-list article"):
                try:
                    a_tag = article.find('a', rel='bookmark')
                    if not a_tag:
                        continue
                    href = a_tag.get('href', '')

                    h2_tag = article.find('h2')
                    if not h2_tag:
                        continue
                    title = h2_tag.get('title', '').split(" ")[0]

                    img = article.select_one('.movie-image')
                    cover = ''
                    if img:
                        cover = img.get('data-srcset') or img.get('src', '')

                    time_tag = article.find('time')
                    pubdate = ''
                    if time_tag:
                        pubdate = time_tag.get('datetime', '').split('T')[0]

                    videos.append({
                        "vod_id": href,
                        "vod_name": title,
                        "vod_pic": cover,
                        "vod_remarks": pubdate,
                        "vod_pubdate": pubdate
                    })
                except Exception as e:
                    continue

            result["list"] = videos
        except Exception as e:
            result["list"] = []

        return json.dumps(result, ensure_ascii=False)

    def searchContentPage(self, key, quick, pg):
        # 分页搜索
        result = {}

        try:
            text = urllib.parse.quote(key)
            page = int(pg) if pg else 1
            url = f"{self.site}/search?q={text}&page={page}"

            rsp = requests.get(url, headers=self.headers, timeout=10)
            rsp.encoding = 'utf-8'
            soup = BeautifulSoup(rsp.text, 'html.parser')

            videos = []
            for article in soup.select("#movie-list article"):
                try:
                    a_tag = article.find('a', rel='bookmark')
                    if not a_tag:
                        continue
                    href = a_tag.get('href', '')

                    h2_tag = article.find('h2')
                    if not h2_tag:
                        continue
                    title = h2_tag.get('title', '').split(" ")[0]

                    img = article.select_one('.movie-image')
                    cover = ''
                    if img:
                        cover = img.get('data-srcset') or img.get('src', '')

                    time_tag = article.find('time')
                    pubdate = ''
                    if time_tag:
                        pubdate = time_tag.get('datetime', '').split('T')[0]

                    videos.append({
                        "vod_id": href,
                        "vod_name": title,
                        "vod_pic": cover,
                        "vod_remarks": pubdate,
                        "vod_pubdate": pubdate
                    })
                except Exception as e:
                    continue

            has_next = len(videos) > 0
            result["page"] = page
            result["pagecount"] = page + 1 if has_next else page
            result["limit"] = len(videos)
            result["total"] = len(videos)
            result["list"] = videos
        except Exception as e:
            result["page"] = int(pg) if pg else 1
            result["pagecount"] = int(pg) if pg else 1
            result["limit"] = 0
            result["total"] = 0
            result["list"] = []

        return json.dumps(result, ensure_ascii=False)

    def localProxy(self, param):
        return [200, "video/MP2T", "", ""]
