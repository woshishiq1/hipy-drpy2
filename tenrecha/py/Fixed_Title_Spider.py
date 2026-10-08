# -*- coding: utf-8 -*-
import json
import requests
import re
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

# 禁用 SSL 证书警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def init(self, extend=""): pass
        def fetch(self, url, headers=None): return requests.get(url, headers=headers)

class Spider(Spider):
    def init(self, extend=""):
        self.api = "https://api.736136.com/api/"
        self.search_base = "" 

    def getHeaders(self):
        # 伪装成 iPhone Safari
        return {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Referer": self.api
        }

    def getName(self):
        return "Fixed_Title_Spider"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def _clean_and_load_json(self, text):
        try:
            return json.loads(text)
        except:
            pass
        try:
            match = re.search(r'(\[.*\])', text, re.DOTALL)
            if match: return json.loads(match.group(1))
        except:
            pass
        try:
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match: return json.loads(match.group(1))
        except:
            pass
        return None

    def _fetch_filter_for_category(self, tid):
        try:
            url = f"{self.api}video/get/nav?id={tid}"
            res = requests.get(url, headers=self.getHeaders(), verify=False, timeout=5)
            data = res.json()
            
            filter_list = []
            if 'data' in data and isinstance(data['data'], list):
                value_list = []
                for sub in data['data']:
                    name = sub.get('name')
                    link = sub.get('link') or sub.get('url')
                    if name and link:
                        value_list.append({"n": name, "v": link})
                
                if value_list:
                    filter_list.append({
                        "key": "cateUrl",
                        "name": "分类",
                        "value": value_list
                    })
            return tid, filter_list
        except Exception as e:
            return tid, []

    def homeContent(self, filter):
        result = {}
        classes = []
        filters = {}
        
        try:
            res = requests.get(f"{self.api}video/get/menu", headers=self.getHeaders(), verify=False)
            v_res = res.json()
            
            if 'data' in v_res and isinstance(v_res['data'], dict) and 'url' in v_res['data']:
                 self.search_base = v_res['data']['url']

            data_list = []
            if 'data' in v_res:
                if isinstance(v_res['data'], list):
                    data_list = v_res['data']
                elif isinstance(v_res['data'], dict) and 'data' in v_res['data']:
                    data_list = v_res['data']['data']

            tasks = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                for item in data_list:
                    name = item.get('name', '')
                    if "瓜" in name or "草" in name: continue
                    vid = str(item.get('id', ''))
                    
                    classes.append({'type_name': name, 'type_id': vid})
                    tasks.append(executor.submit(self._fetch_filter_for_category, vid))

                for future in as_completed(tasks):
                    tid, filter_data = future.result()
                    if filter_data:
                        filters[tid] = filter_data
                
        except Exception as e:
            print(f"Menu error: {e}")

        result['class'] = classes
        result['filters'] = filters
        return result

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        videos = []
        
        try:
            final_url = ""
            if extend and 'cateUrl' in extend:
                final_url = extend['cateUrl']
            else:
                nav_url = f"{self.api}video/get/nav?id={tid}"
                nav_res = requests.get(nav_url, headers=self.getHeaders(), verify=False)
                nav_data = nav_res.json()
                if 'data' in nav_data and isinstance(nav_data['data'], list) and len(nav_data['data']) > 0:
                    first_item = nav_data['data'][0]
                    final_url = first_item.get('link') or first_item.get('url')
            
            if not final_url: return {'list': []}

            req_url = f"{final_url}&p={pg}"
            list_res = requests.get(req_url, headers=self.getHeaders(), verify=False)
            list_res.encoding = 'utf-8'
            json_data = self._clean_and_load_json(list_res.text)
            
            data_list = []
            if isinstance(json_data, list) and len(json_data) > 0:
                if isinstance(json_data[0], dict):
                    data_list = json_data[0].get('data')
            elif isinstance(json_data, dict) and 'data' in json_data:
                 d = json_data['data']
                 if isinstance(d, list): data_list = d
                 elif isinstance(d, dict): data_list = d.get('data')

            if data_list:
                for item in data_list:
                    if not isinstance(item, dict): continue
                    title = item.get('title')
                    address = item.get('address')
                    img = item.get('img')
                    if not title or not address: continue

                    # === 修改点 1：ID 中携带标题 ===
                    # 格式: 真实地址###标题
                    combined_id = f"{address}###{title}"

                    videos.append({
                        'vod_id': combined_id,
                        'vod_name': title,
                        'vod_pic': img,
                        'vod_remarks': item.get('time', '')
                    })
        except Exception as e:
            print(f"Category error: {e}")

        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 999
        result['limit'] = 20
        result['total'] = 9999
        return result

    def detailContent(self, ids):
        # === 修改点 2：拆分 ID 和 标题 ===
        did = ids[0]
        title = "未知标题"
        real_url = did
        
        if "###" in did:
            parts = did.split("###")
            real_url = parts[0]
            title = parts[1]
        
        vod = {
            'vod_id': did,
            'vod_name': title, # 这里设置的就是播放页显示的标题
            'vod_pic': '',
            'type_name': '视频',
            'vod_play_from': '直连',
            # 播放列表里只放真实的 URL
            'vod_play_url': f"点击播放${real_url}"
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg="1"):
        if not self.search_base:
             try:
                res = requests.get(f"{self.api}video/get/menu", headers=self.getHeaders(), verify=False).json()
                if 'data' in res and 'url' in res['data']:
                    self.search_base = res['data']['url']
             except: pass
        
        if not self.search_base: return {'list': []}

        url = f"{self.search_base}{key}&p={pg}"
        videos = []
        try:
            res = requests.get(url, headers=self.getHeaders(), verify=False)
            res.encoding = 'utf-8'
            json_data = self._clean_and_load_json(res.text)
            
            data_list = []
            if isinstance(json_data, list) and len(json_data) > 0:
                data_list = json_data[0].get('data')

            if data_list:
                for item in data_list:
                    if not isinstance(item, dict): continue
                    
                    title = item.get('title')
                    address = item.get('address')
                    if not title or not address: continue
                    
                    # 搜索结果同样需要带上标题
                    combined_id = f"{address}###{title}"
                    
                    videos.append({
                        'vod_id': combined_id,
                        'vod_name': title,
                        'vod_pic': item.get('img'),
                        'vod_remarks': item.get('time')
                    })
        except Exception as e:
            pass

        return {'list': videos}

    def playerContent(self, flag, id, vipFlags):
        real_url = ""
        try:
            if "url=" in id:
                match = re.search(r'url=(http.*?)($|&)', id)
                if match:
                    real_url = match.group(1)
            
            if not real_url:
                resp = requests.get(id, headers=self.getHeaders(), verify=False)
                text = resp.text.strip()
                if text.startswith("http"):
                    real_url = text
            
            return {
                'parse': 0, 
                'url': real_url, 
                'header': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            }
        except Exception as e:
            return {'parse': 0, 'url': ''}

    def localProxy(self, param):
        pass
