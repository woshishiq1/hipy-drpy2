import sys
import re
import json
import requests
import html
from urllib.parse import unquote, quote
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "高清仓库"

    def init(self, extend=""):
        super().init(extend)
        self.site_url = "http://gqck32.cc"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.site_url
        }

    def fetch(self, url, timeout=10):
        try:
            res = requests.get(url, headers=self.headers, timeout=timeout, verify=False)
            res.encoding = "utf-8"
            return res
        except:
            return None

    def homeContent(self, filter):
        cate_list = [
            {"type_name": "日韩AV", "type_id": "1"},
            {"type_name": "国产系列", "type_id": "2"},
            {"type_name": "欧美", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
            {"type_name": "无码中文字幕", "type_id": "8"},
            {"type_name": "有码中文字幕", "type_id": "9"},
            {"type_name": "日本无码", "type_id": "10"},
            {"type_name": "日本有码", "type_id": "7"},
            {"type_name": "国产视频", "type_id": "15"},
            {"type_name": "吃瓜爆料", "type_id": "25"},
            {"type_name": "欧美高清", "type_id": "21"},
            {"type_name": "动漫剧情", "type_id": "22"}
        ]
        return {"class": cate_list}

    def categoryContent(self, tid, pg, filter, extend):
        if not hasattr(self, 'site_url'): self.init()
        pg = int(pg) if str(pg).isdigit() else 1
        list_url = f"{self.site_url}/vodtype/{tid}.html" if pg == 1 else f"{self.site_url}/vodtype/{tid}-{pg}.html"
        res = self.fetch(list_url)
        if not res or res.status_code == 404:
            list_url = f"{self.site_url}/index.php/vod/type/id/{tid}/page/{pg}.html"
            res = self.fetch(list_url)

        video_list = []
        if res and res.ok:
            pattern = r'class="stui-vodlist__thumb\s+lazyload"\s+href="([^"]+)"\s+title="([^"]+)"\s+data-original="([^"]+)"'
            for href, name, pic in re.findall(pattern, res.text):
                vod_id = re.sub(r'play/(\d+)-\d+-\d+/?', r'detail/\1.html', href)
                video_list.append({
                    "vod_id": vod_id,
                    "vod_name": html.unescape(name).split("'style=")[0].strip(),
                    "vod_pic": pic if pic.startswith("http") else self.site_url + pic,
                    "vod_remarks": ""
                })
        return {"list": video_list, "page": pg, "pagecount": pg + 1, "limit": 20}

    def detailContent(self, ids):
        if not hasattr(self, 'site_url'): self.init()
        vod_url = ids[0] if ids[0].startswith('http') else self.site_url + ids[0]
        res = self.fetch(vod_url)
        if res and res.ok:
            # 1. 清理标题干扰
            name_m = re.search(r'title"><h1>([^<]+)</h1>', res.text)
            vod_name = name_m.group(1).split("'style=")[0].strip() if name_m else "视频详情"
            # 2. 封面
            pic_m = re.search(r'data-original="([^"]+)"', res.text)
            # 3. 选集列表
            play_list = []
            matches = re.findall(r'href="(/vodplay/[^"]+)">([^<]+)</a>', res.text)
            for href, p_name in matches:
                play_list.append(f"{p_name}${href}")
            
            # 兜底：如果没找到选集，直接从 player 变量提取当前集
            if not play_list:
                curr_link = re.search(r'"link":"(\/vodplay\/[^"]+)"', res.text)
                if curr_link:
                    p_url = curr_link.group(1).replace('\\/', '/')
                    play_list.append("立即播放$" + p_url)
            vod = {
                "vod_id": ids[0],
                "vod_name": html.unescape(vod_name),
                "vod_pic": pic_m.group(1) if pic_m else "",
                "vod_play_from": "高清仓库",
                "vod_play_url": "#".join(play_list)
            }
            return {"list": [vod]}
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith('http') else self.site_url + id
        res = self.fetch(url)
        if res and res.ok:
            # 适配源码中的 player_aaaa 变量
            player_json = re.search(r'player_(?:aaaa|data)=(.*?)</script>', res.text)
            if player_json:
                try:
                    data = json.loads(player_json.group(1))
                    return {"parse": 0, "url": unquote(data['url']), "header": self.headers}
                except: pass
        return {"parse": 0, "url": url, "header": self.headers}

    def searchContent(self, key, quick, pg="1"):
        if not hasattr(self, 'site_url'): self.init()
        search_url = f"{self.site_url}/vodsearch/{quote(key)}-------------.html"
        res = self.fetch(search_url)
        video_list = []
        if res and res.ok:
            pattern = r'class="stui-vodlist__thumb\s+lazyload"\s+href="([^"]+)"\s+title="([^"]+)"\s+data-original="([^"]+)"'
            for href, name, pic in re.findall(pattern, res.text):
                video_list.append({
                    "vod_id": href,
                    "vod_name": html.unescape(name).split("'style=")[0].strip(),
                    "vod_pic": pic if pic.startswith("http") else self.site_url + pic,
                    "vod_remarks": ""
                })
        return {"list": video_list}