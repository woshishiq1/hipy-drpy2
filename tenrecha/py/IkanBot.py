# -*- coding: utf-8 -*-
import re
import sys
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider
except ImportError:
    class Spider:
        pass

class Spider(Spider):
    def getName(self):
        return "IkanBot"

    def init(self, extend):
        self.home_url = 'https://v.ikanbot.com'
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Referer": "https://v.ikanbot.com/"
        }
        self.mobile_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1",
            "Referer": "https://v.ikanbot.com/"
        }
        self.flag_map = {
            'bfzym3u8':'暴风','1080zyk':'优质','kuaikan':'快看','lzm3u8':'量子','ffm3u8':'非凡',
            'snm3u8':'索尼','qhm3u8':'奇虎','haiwaikan':'海外看','gsm3u8':'光速','zuidam3u8':'最大',
            'bjm3u8':'八戒','wolong':'卧龙','xlm3u8':'新浪','yhm3u8':'樱花','tkm3u8':'天空',
            'jsm3u8':'极速','wjm3u8':'无尽','sdm3u8':'闪电','kcm3u8':'快车','jinyingm3u8':'金鹰',
            'fsm3u8':'飞速','tpm3u8':'淘片','lem3u8':'鱼乐','dbm3u8':'百度','tomm3u8':'番茄',
            'ukm3u8':'U酷','ikm3u8':'爱坤','hnzym3u8':'红牛资源','hnm3u8':'红牛','68zy_m3u8':'68',
            'kdm3u8':'酷点','bdxm3u8':'北斗星','hhm3u8':'豪华','kbm3u8':'快播'
        }
        self.tab_remove = ['wjm3u8','ikm3u8','sdm3u8','M3U8','jinyingm3u8','fsm3u8','ukm3u8']
        self.tab_order = ['bfzym3u8','1080zyk','kuaikan','lzm3u8','ffm3u8','snm3u8','qhm3u8',
                          'gsm3u8','zuidam3u8','bjm3u8','wolong','xlm3u8','yhm3u8']

    def getDependence(self):
        return []

    def homeContent(self, filter):
        classes = [
               {"type_id": "/hot/index-movie-最新.html", "type_name": "最新电影"},
               {"type_id": "/hot/index-movie-热门.html", "type_name": "电影"},
               {"type_id": "/hot/index-tv-热门.html", "type_name": "剧集"}
                 ]
        filter_config = [
            {"key":"tag","name":"标签","value":[
                {"n":"热门","v":"热门"},{"n":"最新","v":"最新"},{"n":"经典","v":"经典"},
                {"n":"豆瓣高分","v":"豆瓣高分"},{"n":"冷门佳片","v":"冷门佳片"},
                {"n":"华语","v":"华语"},{"n":"欧美","v":"欧美"},{"n":"韩国","v":"韩国"},
                {"n":"日本","v":"日本"},{"n":"动作","v":"动作"},{"n":"喜剧","v":"喜剧"},
                {"n":"爱情","v":"爱情"},{"n":"科幻","v":"科幻"},{"n":"悬疑","v":"悬疑"},
                {"n":"恐怖","v":"恐怖"},{"n":"治愈","v":"治愈"}
            ]}
        ]
        filters = {}
        for c in classes:
            filters[c['type_id']] = filter_config
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        return self._parse_list(self.home_url)

    def categoryContent(self, tid, pg, filter, ext):
        # 提取基础类型 (movie/tv)
        match = re.search(r'index-(.*?)-', tid)
        base_type = match.group(1) if match else "movie"
        
        # 确定标签 (热门/最新/自定义)
        tag = "热门"
        if 'tag' in ext:
            tag = ext['tag']
        elif "热门" in tid:
            tag = "热门"
        elif "最新" in tid:
            tag = "最新"
            
        encoded_tag = quote(tag)
        
        # 【关键修复】拼接翻页 URL
        if int(pg) > 1:
            # 格式: /hot/index-movie-热门-p-2.html
            final_path = "/hot/index-{}-{}-p-{}.html".format(base_type, encoded_tag, pg)
        else:
            # 格式: /hot/index-movie-热门.html
            final_path = "/hot/index-{}-{}.html".format(base_type, encoded_tag)
        
        full_url = "{}{}".format(self.home_url, final_path)
        return self._parse_list(full_url)

    def searchContent(self, key, quick, pg='1'):
        # 【关键修复】拼接搜索翻页 URL
        encoded_key = quote(key)
        if int(pg) > 1:
            url = "{}/search?q={}&p={}".format(self.home_url, encoded_key, pg)
        else:
            url = "{}/search?q={}".format(self.home_url, encoded_key)
        return self._parse_list(url)

    def detailContent(self, did):
        vod_id = did[0] if isinstance(did, list) else did
        try:
            url = "{}{}".format(self.home_url, vod_id)
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code != 200: return {'list': []}

            res.encoding = 'utf-8' 
            html = res.text
            
            current_id = re.search(r'id="current_id" value="(\d+)"', html)
            e_token = re.search(r'id="e_token" value="([^"]+)"', html)
            mtype = re.search(r'id="mtype" value="(\d+)"', html)
            mtype_val = mtype.group(1) if mtype else "2"

            play_from = []
            play_url = []
            play_dict = {}

            if current_id and e_token:
                cid = current_id.group(1)
                token_str = e_token.group(1)
                token = self._get_tks(cid, token_str)
                
                api_url = "{}/api/getResN".format(self.home_url)
                params = {"videoId": cid, "mtype": mtype_val, "token": token}
                api_headers = self.mobile_headers.copy()
                api_headers["Referer"] = url 
                
                try:
                    api_res = requests.get(api_url, params=params, headers=api_headers, timeout=5)
                    if api_res.status_code == 200:
                        api_res.encoding = 'utf-8'
                        data = api_res.json()
                        if data.get("data") and data["data"].get("list"):
                            for item in data["data"]["list"]:
                                res_data = item.get("resData")
                                if isinstance(res_data, str):
                                    if res_data.startswith('\\'):
                                        res_data = res_data.replace('\\\\"', '\\"').strip('"')
                                    try:
                                        flag_list = json.loads(res_data)
                                    except: continue
                                else:
                                    flag_list = res_data
                                    
                                if not flag_list: continue

                                urls = []
                                raw_flag = ""
                                
                                for f in flag_list:
                                    flag = f.get("flag")
                                    u = f.get("url")
                                    if not u: continue
                                    if not raw_flag: raw_flag = flag
                                    name = f.get("name", "").strip()
                                    if not name: name = "第{}集".format(len(urls) + 1)
                                    u = u.strip()
                                    urls.append("{}${}".format(name, u))
                                
                                if raw_flag in self.tab_remove: continue
                                if urls and raw_flag:
                                    show_name = self.flag_map.get(raw_flag, raw_flag)
                                    play_dict[raw_flag] = {"show_name": show_name, "urls": "#".join(urls)}

                            for key in self.tab_order:
                                if key in play_dict:
                                    play_from.append(play_dict[key]["show_name"])
                                    play_url.append(play_dict[key]["urls"])
                                    del play_dict[key]
                            for key in play_dict:
                                play_from.append(play_dict[key]["show_name"])
                                play_url.append(play_dict[key]["urls"])
                except: pass

            soup = BeautifulSoup(html, 'html.parser')
            title_tag = soup.find('h2') or soup.find('h1')
            vod_name = title_tag.text.strip() if title_tag else vod_id
            
            vod_pic = ""
            img = soup.find('div', class_='item-root')
            if img and img.find('img'):
                vod_pic = img.find('img').get('data-src') or img.find('img').get('src', '')
            
            vod_content = ""
            desc = soup.find('div', class_='description')
            if desc: vod_content = desc.text.strip()

            return {'list': [{
                'vod_id': vod_id, 'vod_name': vod_name, 'vod_pic': vod_pic,
                'vod_play_from': "$$$".join(play_from), 'vod_play_url': "$$$".join(play_url),
                'vod_content': vod_content
            }]}
        except Exception as e:
            return {'list': []}

    def playerContent(self, flag, pid, vipFlags):
        url = pid
        if "$" in url:
            url = url.split("$")[1]
        return {"url": url, "parse": 0, "jx": 0}

    def _get_tks(self, current_id, e_token):
        if not current_id or not e_token: return ""
        try:
            key = str(current_id)
            if len(key) > 4: key = key[-4:]
            parts = []
            token = str(e_token)
            for char in key:
                digit = int(char)
                pos = (digit % 3) + 1 
                if pos + 8 > len(token): break
                parts.append(token[pos:pos + 8])
                token = token[pos + 8:]
            return "".join(parts)
        except: return ""

    def _parse_list(self, url):
        data = []
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code != 200: return {'list': []}
            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            items = []
            v_list = soup.find('div', class_='v-list')
            if v_list: items = v_list.find_all('div', class_='item')
            if not items: items = soup.find_all('div', class_='media')
            if not items: items = soup.select('a.item-root')
                
            for item in items:
                vod_id = ""
                vod_name = ""
                vod_pic = ""
                vod_remarks = ""
                
                if item.name == 'div' and 'item' in item.get('class', []):
                    a_tag = item.find('a')
                    if not a_tag: continue
                    href = a_tag.get('href', '')
                    if not href.startswith('/play/'): continue
                    vod_id = href
                    p_tag = item.find('p')
                    if p_tag: vod_name = p_tag.text.strip()
                    else:
                        img = item.find('img')
                        if img: vod_name = img.get('alt', '')
                    img = item.find('img')
                    if img: vod_pic = img.get('data-src') or img.get('src', '')
                    rem = item.find('div', class_='text-right')
                    if rem: vod_remarks = rem.text.strip()

                elif item.name == 'div' and 'media' in item.get('class', []):
                    a_tag = item.find('a', class_='title-text')
                    if not a_tag: continue
                    href = a_tag.get('href', '')
                    if not href.startswith('/play/'): continue
                    vod_id = href
                    vod_name = a_tag.text.strip()
                    img = item.find('img', class_='media-object')
                    if img: vod_pic = img.get('data-src') or img.get('src', '')
                    label = item.find('span', class_='label')
                    if label: vod_remarks = label.text.strip()

                elif item.name == 'a':
                    href = item.get('href', '')
                    if not href.startswith('/play/'): continue
                    vod_id = href
                    img = item.find('img')
                    if img:
                        vod_name = img.get('alt', '')
                        vod_pic = img.get('data-src') or img.get('src', '')
                    else: vod_name = item.text.strip()
                    label = item.find('span', class_='label')
                    if label: vod_remarks = label.text.strip()

                if vod_id:
                    data.append({
                        'vod_id': vod_id, 'vod_name': vod_name,
                        'vod_pic': vod_pic, 'vod_remarks': vod_remarks
                    })
        except Exception as e:
            pass
        return {'list': data}
