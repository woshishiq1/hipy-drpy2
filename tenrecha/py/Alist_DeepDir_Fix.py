# coding=utf-8
# !/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
import urllib.request
import urllib.parse

class Spider(Spider):
    def getName(self):
        return "Alist_DeepDir_Fix"

    def init(self, extend=""):
        self.ua = "Mozilla/5.0 (Linux; Android 16; ELI-AN00 Build/HONORELI-AN00) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.7499.192 Mobile Safari/537.36"

    def homeContent(self, filter):
        result = {}
        cateManual = {
            "🌊七米蓝": "https://al.chirmyram.com",
            "🐝组织云盘": "https://w2.apachecn.org/",
            "📽️网呢": "https://pan.clun.top",
            "✨亿苯正经": "https://pan.lm379.cn",
            "🐉神族九帝":"https://alist.shenzjd.com",
            "🍓趣盘":"https://pan.mediy.cn/"
        }
        classes = []
        for k in cateManual:
            classes.append({'type_name': k, "type_flag": "1", 'type_id': cateManual[k]})
        result['class'] = classes
        return result

    def rawPost(self, url, data, headers):
        try:
            params = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=params, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            return json.dumps({"code": 500, "message": str(e)})

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        # 1. 精准提取 Host
        host_match = re.findall(r"(https?://[^/]+)", tid)
        if not host_match: return {"list": [], "total": 0}
        host = host_match[0]
        
        # 2. 核心修复：精准提取相对路径 path
        # 无论 tid 是域名还是多级目录，确保 path 是以 / 开头的标准路径
        path = tid.replace(host, "").strip()
        if not path.startswith('/'):
            path = '/' + path
        # 去掉末尾重复斜杠，保持 API 请求整洁
        if len(path) > 1:
            path = path.rstrip('/')
        
        # 3. 构造 Headers
        hd = {
            "User-Agent": self.ua,
            "Content-Type": "application/json",
            "Referer": host + "/",
            "Origin": host,
            "Accept": "application/json"
        }
        
        # 4. 构造参数
        params = {
            "path": path,
            "password": "",
            "page": int(pg),
            "per_page": 50
        }
        
        videos = []
        try:
            api_url = host.rstrip('/') + "/api/fs/list"
            res_text = self.rawPost(api_url, params, hd)
            jo = json.loads(res_text)
            
            data_obj = jo.get('data')
            if jo.get('code') == 200 and data_obj:
                data_list = data_obj.get('content') if isinstance(data_obj, dict) else data_obj
                if data_list is None: data_list = []
                
                for item in data_list:
                    if not item: continue
                    name = item.get('name', '未知')
                    if name.startswith('.'): continue
                    
                    is_dir = item.get('type') == 1
                    
                    # 5. 核心修复：多级目录拼接逻辑
                    # 确保 new_path 不会出现 // 且完整保留层级
                    if path == "/":
                        new_path = "/" + name
                    else:
                        new_path = path + "/" + name
                    
                    new_tid = host + new_path
                    
                    videos.append({
                        "vod_id": new_tid,
                        "vod_name": name,
                        "vod_tag": "folder" if is_dir else "file",
                        "vod_remarks": "文件夹" if is_dir else self.getSize(item.get('size', 0))
                    })
        except:
            pass

        result['list'] = videos
        result['total'] = len(videos)
        return result

    def detailContent(self, array):
        id = array[0]
        name = id.split('/')[-1]
        name = urllib.parse.unquote(name)
        return {'list': [{"vod_id": id, "vod_name": name, "vod_play_from": "Alist", "vod_play_url": f"{name}${id}"}]}

    def playerContent(self, flag, id, vipFlags):
        result = {}
        host_match = re.findall(r"(https?://[^/]+)", id)
        if not host_match: return {"parse": 0, "url": id}
        host = host_match[0]
        path = id.replace(host, "").strip()
        if not path.startswith('/'): path = '/' + path
        
        hd = {"User-Agent": self.ua, "Content-Type": "application/json", "Referer": host + "/"}
        params = {"path": path, "password": ""}
        
        try:
            api_url = host.rstrip('/') + "/api/fs/get"
            res_text = self.rawPost(api_url, params, hd)
            jo = json.loads(res_text)
            data = jo.get('data')
            if jo.get('code') == 200 and data:
                url = data.get('raw_url', '')
                if url.startswith('/'): url = host.rstrip('/') + url
                result["url"] = url
                provider = data.get('provider', '')
                if 'Baidu' in provider:
                    result["header"] = {"User-Agent": "pan.baidu.com"}
                else:
                    result["header"] = {"User-Agent": self.ua}
            else:
                result["url"] = id
        except:
            result["url"] = id
        result["parse"] = 0
        return result

    def getSize(self, size):
        if size is None: return "0B"
        try:
            size = float(size)
            units = ['B', 'KB', 'MB', 'GB', 'TB']
            n = 0
            while size >= 1024 and n < len(units) - 1:
                size /= 1024
                n += 1
            return f"{round(size, 2)}{units[n]}"
        except:
            return "未知"

    def searchContent(self, key, quick):
        return {'list': []}
