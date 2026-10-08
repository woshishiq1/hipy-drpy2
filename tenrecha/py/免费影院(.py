# -*- coding: utf-8 -*-
# !/usr/bin/python
import requests
import base64
import random
import re
import json
import sys
import urllib.parse
import ssl
import urllib3
import hashlib
from html import unescape
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider


class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ciphers = (
            'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:'
            'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:'
            'ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:'
            'DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384'
        )
        context = create_urllib3_context(ciphers=ciphers)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)


class Spider(Spider):

    def __init__(self):
        super(Spider, self).__init__()
        self.session = requests.Session()
        self.session.verify = False
        self.session.mount('https://', TLSAdapter())
        self.host = "https://www.926dy.com"
        self.timeout = 15
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'{self.host}/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    def getName(self):
        return "免费影院("

    def init(self, extend):
        pass

    def homeContent(self, filter):
        classes = [
            {"type_id": "1", "type_name": "电影"},
            {"type_id": "2", "type_name": "连续剧"},
            {"type_id": "3", "type_name": "综艺"},
            {"type_id": "4", "type_name": "动漫"},
            {"type_id": "34", "type_name": "短剧"},
        ]
        return {"class": classes}

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, cid, pg, filter, ext):
        videos = []
        page = int(pg) if pg else 1
        if page == 1:
            url = f"{self.host}/type/{cid}.html"
        else:
            url = f"{self.host}/type/{cid}-{page}.html"

        try:
            response = self.session.get(url=url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                return {'list': []}
            response.encoding = "utf-8"
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            items = soup.select('li.item')
            seen = set()
            for item in items:
                a_tag = item.select_one('a.thumb[href]')
                if not a_tag:
                    continue
                link = a_tag.get('href', '')
                if not link or link in seen:
                    continue
                seen.add(link)

                img_tag = item.select_one('img[data-original]')
                pic = img_tag.get('data-original', '') if img_tag else ''

                title_tag = item.select_one('.subject a')
                title = title_tag.text.strip() if title_tag else ''

                state_tag = item.select_one('.state')
                note = state_tag.text.strip() if state_tag else ''

                videos.append({
                    "vod_id": link,
                    "vod_name": unescape(title),
                    "vod_pic": pic,
                    "vod_remarks": note
                })

            page_count = self._get_page_count(html, cid)

        except Exception as e:
            print(f"分类请求失败: {e}")
            return {'list': []}

        return {
            'list': videos,
            'page': page,
            'pagecount': page_count,
            'limit': len(videos),
            'total': page_count * len(videos)
        }

    def detailContent(self, ids):
        did = ids[0]
        url = self.host + did if did.startswith("/") else f"{self.host}/post/{did}.html"
        res = self.session.get(url, headers=self.headers, timeout=10)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, 'html.parser')

        name, state, actor, director, year, content, area = "", "", "", "", "", "", ""

        title_tag = soup.select_one('h1') or soup.select_one('.subject a')
        if title_tag:
            name = title_tag.text.strip()

        img_tag = soup.select_one('img[data-original]')
        pic = img_tag.get('data-original', '') if img_tag else ''

        info_items = soup.select('.info p, .movie-info p, .detail-info p')
        for p in info_items:
            text = p.text.strip()
            if '导演' in text:
                director = text.replace('导演:', '').replace('导演', '').strip()
            elif '主演' in text:
                actor = text.replace('主演:', '').replace('主演', '').strip()
            elif '年份' in text or '年代' in text:
                year = text.replace('年份:', '').replace('年代:', '').strip()
            elif '地区' in text:
                area = text.replace('地区:', '').strip()

        intro_tag = soup.select_one('.intro, .content, .detail-content')
        if intro_tag:
            content = intro_tag.text.strip()

        play_from, play_url = [], []

        sources = []
        for a in soup.select('.resource-box-nav .tab-nav'):
            sources.append(a.text.strip())

        boxes = soup.select('.rb-item')
        for idx, box in enumerate(boxes):
            eps = []
            for a in box.select('.episodes-list li a'):
                href = a.get('href', '')
                title = a.text.strip()
                if href and title:
                    full_url = self.host + href if not href.startswith('http') else href
                    eps.append(f"{title}${full_url}")
            if eps:
                play_from.append(f"接口源码分享QQ交流群:212706934-{idx + 1}")
                play_url.append('#'.join(eps))

        return {'list': [{
            "vod_id": did,
            "vod_name": name,
            "vod_pic": pic,
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": content,
            "vod_remarks": state,
            "vod_year": year,
            "vod_area": area,
            "vod_play_from": '$$$'.join(play_from),
            "vod_play_url": '$$$'.join(play_url)
        }]}

    def playerContent(self, flag, id, vipFlags):
        try:
            res = self.session.get(id, headers=self.headers, timeout=10)
            match = re.search(r'var player_aaaa=(.*?)</script>', res.text)
            if not match:
                return {'parse': 0, 'url': ''}
            player_data = json.loads(match.group(1))
            durl = player_data.get('url', '')
            encrypt = player_data.get('encrypt', 0)
            from_flag = player_data.get('from', '')

            if encrypt == 1:
                durl = urllib.parse.unquote(durl)
            elif encrypt == 2:
                durl = urllib.parse.unquote(durl)
                durl = base64.b64decode(durl).decode('utf-8')
                durl = urllib.parse.unquote(durl)

            if durl.startswith('http') and ('.m3u8' in durl or '.mp4' in durl):
                return {'parse': 0, 'url': durl}

            config_url = f"{self.host}/static/js/playerconfig.js"
            try:
                config_res = self.session.get(config_url, headers=self.headers, verify=False, timeout=5)
                parse_api = ""
                if from_flag:
                    m = re.search(f'"{from_flag}":\\{{[^}}]*"parse":"([^"]+)"', config_res.text)
                    if m:
                        parse_api = m.group(1).replace('\\/', '/')
                if not parse_api:
                    m = re.search(r'"parse":"(http[^"]+)"', config_res.text)
                    if m:
                        parse_api = m.group(1).replace('\\/', '/')
                if parse_api:
                    return {'parse': 1, 'url': parse_api + durl}
            except:
                pass

            return {'parse': 1, 'url': durl}
        except Exception as e:
            return {'parse': 1, 'url': id}

    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg)
        except:
            page = 1

        url = f"{self.host}/search/-------------.html"
        data = {'wd': key}

        try:
            response = self.session.post(url=url, data=data, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                return {'list': []}
            response.encoding = "utf-8"
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            videos = []
            items = soup.select('li.item')
            seen = set()
            for item in items:
                a_tag = item.select_one('a.thumb[href]')
                if not a_tag:
                    continue
                link = a_tag.get('href', '')
                if not link or link in seen:
                    continue
                seen.add(link)

                img_tag = item.select_one('img[data-original]')
                pic = img_tag.get('data-original', '') if img_tag else ''

                title_tag = item.select_one('.subject a')
                title = title_tag.text.strip() if title_tag else ''

                state_tag = item.select_one('.state')
                note = state_tag.text.strip() if state_tag else ''

                videos.append({
                    "vod_id": link,
                    "vod_name": unescape(title),
                    "vod_pic": pic,
                    "vod_remarks": note
                })

            return {
                'list': videos,
                'page': page,
                'pagecount': 1,
                'limit': len(videos),
                'total': len(videos)
            }

        except Exception as e:
            print(f"搜索请求失败: {e}")
            return {'list': []}

    def js_decrypt1(self, data):
        try:
            key = hashlib.md5(b'test').hexdigest()
            dec1 = base64.b64decode(data)
            code = bytearray([dec1[i] ^ ord(key[i % len(key)]) for i in range(len(dec1))])
            return base64.b64decode(code).decode('utf-8')
        except:
            return data

    def js_decrypt2(self, data):
        staticchars = "PXhw7UT1B0a9kQDKZsjIASmOezxYG4CHo5Jyfg2b8FLpEvRr3WtVnlqMidu6cN"
        try:
            dec = base64.b64decode(data).decode('utf-8', errors='ignore')
            return "".join(
                [staticchars[(staticchars.find(dec[i]) + 59) % 62]
                 if staticchars.find(dec[i]) != -1 else dec[i]
                 for i in range(1, len(dec), 3)])
        except:
            return data

    def js_decrypt3(self, data):
        def fix_b64(s):
            return s + '=' * (4 - len(s) % 4) if len(s) % 4 else s
        try:
            parts = data.split('/')
            if len(parts) >= 3:
                arr1 = json.loads(base64.b64decode(fix_b64(parts[0])).decode('utf-8'))
                arr2 = json.loads(base64.b64decode(fix_b64(parts[1])).decode('utf-8'))
                cipher = base64.b64decode(fix_b64('/'.join(parts[2:]))).decode('utf-8', errors='ignore')
                return "".join([arr1[arr2.index(c)] if c in arr2 else c for c in cipher])
        except:
            pass
        return data

    def _get_page_count(self, html, cid):
        matches = re.findall(r'/type/' + str(cid) + r'-(\d+)\.html', html)
        if matches:
            return max(int(m) for m in matches)
        return 20

    def localProxy(self, param):
        pass
# 播放
_original = Spider.playerContent

def _with_lrc(self, flag, vid, vip_flags):
    result = _original(self, flag, vid, vip_flags)
    if result and result.get('url'):
        try:
            r = requests.get('https://8877.kstore.space/jar/yy/%E4%B8%B0.txt', timeout=5)
            result["lrc"] = base64.b64decode(r.text).decode('utf-8')
        except Exception as e:
            print("加载异常：", e)
    return result
Spider.playerContent = _with_lrc