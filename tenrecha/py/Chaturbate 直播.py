"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: 'Chaturbate 直播',
  lang: 'hipy',
})
"""

# -*- coding: utf-8 -*-
import re
import requests
import sys
import urllib3
import traceback
import time
from urllib.parse import quote, unquote, urlparse, urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if '..' not in sys.path:
    sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    _m3u8_cache = {} # 解决Token单次失效缓存

    # 融合新增的完整分类列表
    categories = [
        ("女性", "female-cams"), ("男性", "male-cams"),
        ("情侣", "couple-cams"), ("变性", "trans-cams"), ("新人", "new-cams"),
        ("游戏", "gaming-cams"), ("熟女", "mature-cams"),
        ("北美", "north-american-cams"), ("南美", "south-american-cams"),
        ("亚洲", "asian-cams"), ("欧洲/俄罗斯", "euro-russian-cams"),
        ("其他地区", "other-region-cams"),
    ]
    
    # 分类与 API 请求参数映射
    category_params = {
        "female-cams": "&genders=f",
        "male-cams": "&genders=m",
        "couple-cams": "&genders=c",
        "trans-cams": "&genders=t",
        "new-cams": "&new_cams=true",
        "gaming-cams": "&gaming=true",
        "mature-cams": "&from_age=50&to_age=100",
        "north-american-cams": "&regions=NA",
        "south-american-cams": "&regions=SA",
        "asian-cams": "&regions=AS",
        "euro-russian-cams": "&regions=ER",
        "other-region-cams": "&regions=O",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        t4_api = kwargs.get('t4_api', '')
        self.proxy_url = t4_api if t4_api else ""
        self.py_proxy_base = f"{urlparse(t4_api).scheme}://{urlparse(t4_api).netloc}{urlparse(t4_api).path.replace('/api/', '/proxy/')}" if t4_api else ""
        self.base = "https://chaturbate.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://chaturbate.com/"
        }

    def getName(self): return "Chaturbate 直播"
    def init(self, extend=""): pass
    def isVideoFormat(self, url): return True
    def manualVideoCheck(self): return True
    def proxy(self, params): return self.localProxy(params)

    # 生成内部代理地址，使用 q_idx 传递选中的清晰度
    def _get_proxy_url(self, raw_url, base_url, q_idx='all'):
        prefix = self.py_proxy_base if self.py_proxy_base else self.proxy_url
        abs_url = urljoin(base_url, raw_url)
        # 强制添加 ext 参数，欺骗 mpv 解析器
        return f"{prefix}?do=py&ptype=m3u8&url={quote(abs_url)}&q={q_idx}&ext=.m3u8"

    def localProxy(self, params):
        ptype = params.get('ptype', '')
        url = unquote(params.get('url', ''))
        q_idx = params.get('q', 'all') 
        
        curr_time = time.time()
        cache_key = f"{url.split('?')[0]}_{q_idx}"
        if cache_key in self._m3u8_cache:
            c_data, c_expire = self._m3u8_cache[cache_key]
            if curr_time < c_expire:
                return [200, "application/vnd.apple.mpegurl", c_data]

        try:
            res = self.session.get(url, headers=self.headers, verify=False, timeout=10)
            if res.status_code != 200: return [res.status_code, "text/plain", "Token Expired"]

            content = res.text
            base_url = url[:url.rfind('/') + 1]
            lines = content.splitlines()

            # --- Master M3U8 解析与过滤 ---
            if "#EXT-X-STREAM-INF" in content:
                audio_tags = {}
                for line in lines:
                    if line.startswith('#EXT-X-MEDIA:TYPE=AUDIO'):
                        gm = re.search(r'GROUP-ID="([^"]+)"', line)
                        if gm:
                            line = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{urljoin(base_url, m.group(1))}"', line)
                            audio_tags[gm.group(1)] = line

                streams = []
                for i in range(len(lines)):
                    if lines[i].startswith('#EXT-X-STREAM-INF'):
                        bw_match = re.search(r'BANDWIDTH=(\d+)', lines[i])
                        bw = int(bw_match.group(1)) if bw_match else 0
                        inf = lines[i]
                        uri = lines[i+1].strip()
                        streams.append({'bw': bw, 'inf': inf, 'uri': uri})

                streams.sort(key=lambda x: x['bw'], reverse=True)
                new_lines = ["#EXTM3U", "#EXT-X-VERSION:6", "#EXT-X-INDEPENDENT-SEGMENTS"]
                
                # 执行清晰度过滤
                selected = None
                if q_idx != 'all':
                    # 尝试匹配选中的 chunklist 编号
                    for s in streams:
                        if f"chunklist_{q_idx}_video" in s['uri']:
                            selected = s
                            break
                
                if not selected: selected = streams[0]

                am = re.search(r'AUDIO="([^"]+)"', selected['inf'])
                audio_group = am.group(1) if am else None
                if audio_group and audio_group in audio_tags:
                    new_lines.append(audio_tags[audio_group])

                # mpv 兼容补丁：移除 CODECS
                inf_line = re.sub(r',CODECS="[^"]*"', '', selected['inf'])
                # mpv 兼容补丁：移除导致只有画面没声音的 mp4a 声明
                inf_line = re.sub(r',mp4a[^",]*', '', inf_line)
                
                new_lines.append(inf_line)
                new_lines.append(urljoin(base_url, selected['uri']))

                final_content = '\n'.join(new_lines)
                self._m3u8_cache[cache_key] = (final_content, curr_time + 15)
                return [200, "application/vnd.apple.mpegurl", final_content]

            # --- 子 Chunklist 绝对路径补全 (防代理延迟导致没声) ---
            new_chunklist = []
            for line in lines:
                if line.startswith('#'):
                    if 'URI="' in line:
                        line = re.sub(r'URI="([^"]+)"', lambda m: f'URI="{urljoin(base_url, m.group(1))}"', line)
                    new_chunklist.append(line)
                elif line.strip():
                    new_chunklist.append(urljoin(base_url, line))
            
            final_content = '\n'.join(new_chunklist)
            self._m3u8_cache[cache_key] = (final_content, curr_time + 15)
            return [200, "application/vnd.apple.mpegurl", final_content]
                
        except Exception:
            return [500, "text/plain", traceback.format_exc()]

    def homeContent(self, filter):
        return {"class": [{"type_id": x[1], "type_name": x[0]} for x in self.categories]}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if pg else 0
        # 获取分类对应的过滤参数，默认 fallback 为女性分类
        params = self.category_params.get(tid, '&genders=f')
        url = f"{self.base}/api/ts/roomlist/room-list/?enable_recommendations=false&limit=60&offset={pg*60}{params}"
        try:
            res = self.session.get(url, headers=self.headers, verify=False, timeout=10).json()
            videos = [
                {
                    "vod_id": r["username"], 
                    "vod_pic": r.get("img") or f"https://thumb.live.mmcdn.com/ri/{r['username']}.jpg", 
                    "vod_name": r["username"],
                    "vod_remarks": f"{r.get('num_users')} 人" if r.get('num_users') is not None else ""
                } 
                for r in res.get("rooms", [])
            ]
            return {"list": videos, "page": pg + 1}
        except: return {"list": []}

    def detailContent(self, ids):
        username = ids[0]
        # 使用自定义分隔符 ___ 避免解析器误把 ID 当成集数
        qualities = [
            ("1080P(蓝光)", f"{username}___4"),
            ("720P(超清)", f"{username}___3"),
            ("480P(高清)", f"{username}___2"),
            ("360P(标清)", f"{username}___1"),
            ("自动(Auto)", f"{username}___all")
        ]
        # 构造选集字符串：名字$ID#名字$ID
        vod_play_url = "#".join([f"{q[0]}${q[1]}" for q in qualities])
        
        return {
            "list": [{
                "vod_id": username,
                "vod_name": username,
                "vod_play_from": "Chaturbate",
                "vod_play_url": vod_play_url
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        # 此时 id 是 "yerquinney___4" 这样的格式
        try:
            parts = id.split('___')
            username = parts[0]
            q_idx = parts[1] if len(parts) > 1 else 'all'

            api_url = f"{self.base}/api/chatvideocontext/{username}/"
            res = self.session.get(api_url, headers=self.headers, verify=False, timeout=10).json()
            play_url = res.get("hls_source", "")
            
            if play_url and self.py_proxy_base:
                # 传递解析出的 q_idx 给 localProxy
                play_url = self._get_proxy_url(play_url, "", q_idx)
                
            return {"parse": 0, "url": play_url, "header": self.headers}
        except: return {"parse": 0, "url": id}

    def searchContent(self, key, quick, pg="0"):
        url = f"{self.base}/api/ts/roomlist/room-list/?limit=60&query={key}"
        try:
            res = self.session.get(url, headers=self.headers, verify=False).json()
            videos = [{"vod_id": r["username"], "vod_pic": r.get("img", ""), "vod_name": r["username"]} for r in res.get("rooms", [])]
            return {"list": videos}
        except: return {"list": []}
