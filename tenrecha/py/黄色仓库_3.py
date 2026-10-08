# -*- coding: utf-8 -*-
import re
import json
import urllib.parse
import requests
from pyquery import PyQuery as pq

class Spider:
    def __init__(self):
        self.name = '黄色仓库'
        self.host = 'https://hsck.la'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/115.0 Safari/537.36',
            'Referer': self.host
        }
        self.classes = [
            {"type_name": "麻豆", "type_id": "1"},
            {"type_name": "中字", "type_id": "2"},
            {"type_name": "国产", "type_id": "3"},
            {"type_name": "欧美", "type_id": "4"},
            {"type_name": "日韩", "type_id": "5"},
            {"type_name": "麻豆传媒", "type_id": "search_麻豆"},
            {"type_name": "91制片厂", "type_id": "search_91制片厂"},
            {"type_name": "蜜桃影像", "type_id": "search_蜜桃影像"},
            {"type_name": "果冻传媒", "type_id": "search_果冻传媒"},
            {"type_name": "星空无限", "type_id": "search_星空无限"},
            {"type_name": "天美传媒", "type_id": "search_天美传媒"},
            {"type_name": "精东影业", "type_id": "search_精东影业"},
            {"type_name": "皇家华人", "type_id": "search_皇家华人"},
            {"type_name": "糖心Vlog", "type_id": "search_糖心Vlog"},
            {"type_name": "萝莉社", "type_id": "search_萝莉社"},
            {"type_name": "性视界传媒", "type_id": "search_性视界"},
            {"type_name": "兔子先生", "type_id": "search_兔子先生"},
            {"type_name": "草霉视频", "type_id": "search_草霉视频"},
            {"type_name": "玩偶姐姐", "type_id": "search_玩偶姐姐"},
            {"type_name": "爱豆传媒", "type_id": "search_爱豆传媒"},
            {"type_name": "91茄子", "type_id": "search_91茄子"},
            {"type_name": "扣扣传媒", "type_id": "search_扣扣传媒"},
            {"type_name": "SA国际传媒", "type_id": "search_SA国际传媒"},
            {"type_name": "杏吧原创", "type_id": "search_杏吧"},
            {"type_name": "大象传媒", "type_id": "search_大象传媒"},
            {"type_name": "乌托邦", "type_id": "search_乌托邦"},
            {"type_name": "69传媒", "type_id": "search_69传媒"},
            {"type_name": "成人头条", "type_id": "search_成人头条"},
            {"type_name": "乌鸦传媒", "type_id": "search_乌鸦传媒"},
            {"type_name": "香蕉视频", "type_id": "search_香蕉视频"},
        ]

    def getDependence(self):
        return ['requests', 'pyquery']

    # -------------------- 框架接口 --------------------
    def getName(self): return self.name
    def init(self, extend=""): pass
    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): pass
    def homeContent(self, filter): return {"class": self.classes}
    def homeVideoContent(self): return self.categoryContent("1", "1", False, {})

    # -------------------- 分类 --------------------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            if tid.isdigit():
                url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}.html"
            else:
                wd = tid[7:] if tid.startswith('search_') else tid
                url = f"{self.host}/index.php/vod/search/page/{pg}.html?wd={urllib.parse.quote(wd)}"
            r = requests.get(url, headers=self.headers, timeout=10)
            doc = pq(r.text)
            videos = []
            for li in doc('.stui-vodlist li').items():
                href = li('a').attr('href')
                if not href: continue
                videos.append({
                    "vod_id": href,
                    "vod_name": li('h4').text(),
                    "vod_pic": self._abs(li('a').attr('data-original')),
                    "vod_remarks": li('.pic-text').text()
                })
            return self._page(videos, pg)
        except Exception as e:
            print(f"[categoryContent] {e}")
            return self._page([], pg)

    # -------------------- 搜索 --------------------
    def searchContent(self, key, quick, pg='1'):
        url = f"{self.host}/index.php/vod/search/page/{pg}.html?wd={urllib.parse.quote(key)}"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            doc = pq(r.text)
            videos = []
            for li in doc('.stui-vodlist li').items():
                href = li('a').attr('href')
                if not href: continue
                videos.append({
                    "vod_id": href,
                    "vod_name": li('h4').text(),
                    "vod_pic": self._abs(li('a').attr('data-original')),
                    "vod_remarks": li('.pic-text').text()
                })
            return self._page(videos, pg)
        except Exception as e:
            print(f"[searchContent] {e}")
            return self._page([], pg)

    # -------------------- 详情 --------------------
    def detailContent(self, array):
        vid = array[0] if array[0].startswith('http') else self._abs(array[0])
        try:
            r = requests.get(vid, headers=self.headers, timeout=10)
            html = r.text

            # 提取M3U8
            m3u8 = self._extract_m3u8_from_player(html)
            play_url = m3u8 if m3u8 else vid

            # 清洗标题
            raw_title = pq('h3.title', html).text() or pq('title', html).text()
            title = re.split(r'[-—_]|相关视频|目录', raw_title)[0].strip()

            pic = pq('.stui-vodlist__thumb', html).attr('data-original') or ''
            content = pq('.detail-content', html).text() or title

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._abs(pic),
                "vod_content": content,
                "vod_play_from": self.name,
                "vod_play_url": play_url
            }
            return {"list": [vod]}
        except Exception as e:
            print(f"[detailContent] {e}")
            return {"list": []}

    # -------------------- 播放 --------------------
    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "playUrl": "", "url": id, "header": self.headers} if id.startswith('http') else \
               {"parse": 1, "playUrl": "", "url": id, "header": self.headers}

    # -------------------- 工具 --------------------
    def _abs(self, url):
        return urllib.parse.urljoin(self.host, url) if url and not url.startswith('http') else url or ''

    def _page(self, videos, pg):
        return {"list": videos, "page": int(pg), "pagecount": 9999, "limit": 30, "total": 999999}

    def _extract_m3u8_from_player(self, html):
        try:
            url_match = re.search(r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"', html.replace('\\/', '/'))
            if url_match:
                return url_match.group(1)
        except Exception as e:
            print(f"[快速提取失败] {e}")

        try:
            m = re.search(r'var\s+player_aaaa\s*=\s*({.*?});', html, re.DOTALL)
            if m:
                data = json.loads(m.group(1).replace('\\/', '/').strip())
                url = data.get("url", "")
                if url.endswith(".m3u8"):
                    return url
        except Exception as e:
            print(f"[JSON提取失败] {e}")

        try:
            iframe_match = re.search(r'iframe[^>]*src=["\']([^"\']*?url=([^&"\']+))["\']', html)
            if iframe_match:
                url = urllib.parse.unquote(iframe_match.group(2))
                if url.endswith(".m3u8"):
                    return url
        except Exception as e:
            print(f"[iframe提取失败] {e}")

        print("[警告] 未能提取到M3U8链接")
        return ""

    # -------------------- 配置 --------------------
    config = {"player": {}, "filter": {}}
    header = property(lambda self: self.headers)
    def localProxy(self, param): return {}