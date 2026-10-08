# -*- coding: utf-8 -*-
# @Author  : AI Assistant
# @Time    : 2025/12/30
# @Note    : 91看电视 (极简版) - 已移除台标功能

import hashlib
import time
import requests
import sys
import json
import urllib.parse
import re
import concurrent.futures

# 屏蔽 verify=False 的警告
requests.packages.urllib3.disable_warnings()

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "91_No_Logo"

    def init(self, extend):
        self.base_url = 'http://sjapi1.91kds.cn'
        self.list_api = 'http://sj.91kds.cn/api/get_channel.php'
        
        self.app_version = '2.3.4'
        self.mac_address = 'fu:ck:92:92:ff'
        self.ev_code = '20240918'
        self.ev_detail_code = '20250113'
        self.app_pkg = 'com.jiaoxiang.fangnale'
        
        self.list_sign_suffix = "ahkajfkahlajjaflfakhfakfbuyaozaigaolefuquqikangbuzhu2.3.4fu:ck:92:92:ff"
        self.search_salt_start = "4954af3c86d8bc0b766afee71503d860"
        self.search_salt_end = "f8dd806a73202456eb6e782c1c4aecfc"
        self.decode_append_str = "ahkajfkahlajjaflfakhfakfbuyaozaigaolefuquqikangbuzhu"

        self.headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; TVBox Build/2023)",
            "Accept-Encoding": "gzip",
            "Connection": "Keep-Alive"
        }
        
        # 默认图标
        self.default_pic = "http://www.91kds.org/images/logo.png"

    def getDependence(self):
        return []

    # -------------------------------------------------------------------------
    # 业务逻辑
    # -------------------------------------------------------------------------
    def check_url_info(self, url_info):
        url = url_info['url']
        result = url_info.copy()
        result['elapsed'] = 9999; result['speed'] = 0; result['score'] = -99999
        result['quality_str'] = ""; result['quality_score'] = 0

        if url.startswith('rtp') or url.startswith('udp'): return result

        try:
            st = time.time()
            with requests.get(url, headers=self.headers, timeout=2.0, stream=True, verify=False) as resp:
                ttfb = (time.time() - st) * 1000
                result['elapsed'] = ttfb
                if resp.status_code == 200:
                    chunk_size = 16384
                    limit = 524288
                    downloaded = 0
                    dl_st = time.time()
                    sample = b""
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if not chunk: break
                        downloaded += len(chunk)
                        if len(sample) < 4096: sample += chunk
                        if downloaded >= limit or (time.time() - dl_st) > 1.5: break
                    
                    speed = (downloaded / 1024) / max(time.time() - dl_st, 0.001)
                    result['speed'] = speed
                    
                    s_str = sample.decode('utf-8', errors='ignore')
                    q_val = 100
                    if "RESOLUTION=" in s_str:
                        m = re.search(r'RESOLUTION=(d+)x(d+)', s_str)
                        if m:
                            h = int(m.group(2))
                            if h >= 1080: q_val = 300; result['quality_str'] = "1080P"
                            elif h >= 720: q_val = 200; result['quality_str'] = "720P"
                    
                    result['quality_score'] = q_val
                    base = min(speed / 5, 5000) if speed >= 500 else -50000
                    result['score'] = base + q_val - (max(ttfb - 1000, 0) / 2)
        except: pass
        return result

    def homeContent(self, filter):
        class_str = "央视&卫视&高清&影视&体育&动漫&财经&综艺&教育&新闻&纪录&国际&网络&虎牙&购物"
        classes = [{'type_id': n, 'type_name': n} for n in class_str.split('&')]
        return {'class': classes}

    def homeVideoContent(self):
        return self.categoryContent("fyAll", 1, None, None)

    def categoryContent(self, cid, page, filter, ext):
        target_id = cid if cid != "fyAll" else "fyAll"
        url = f"{self.list_api}?id={target_id}"
        try:
            res = requests.get(url, headers=self.headers, verify=False)
            if res.status_code == 200:
                data_list = res.json()
                videos = []
                for item in data_list:
                    # 直接传空字符串或者默认图，不进行任何匹配
                    videos.append({
                        'vod_id': item.get('ename', ''),
                        'vod_name': item.get('name', ''),
                        'vod_pic': self.default_pic, 
                        'vod_remarks': item.get('rname', '')
                    })
                return {'list': videos}
        except: pass
        return {'list': []}

    def detailContent(self, did):
        ename = did[0]
        source_api_url = self.generate_source_url(ename)
        # 详情页也不显示特定台标
        current_pic = self.default_pic
        raw_lines = [] 
        try:
            res = requests.get(source_api_url, headers=self.headers, verify=False)
            if res.status_code == 200:
                meta = res.json()
                srcs = meta.get('liveSource', [])
                names = meta.get('liveSourceName', [])
                seen = set()
                for i, raw in enumerate(srcs):
                    sname = names[i] if i < len(names) else f"线路{i+1}"
                    u = re.sub(r'^(kdsvod://|kds://)', '', raw)
                    real_u = ""
                    if u.startswith('rtp') or u.startswith('udp'): sname = f"[组播]{sname}"; real_u = u
                    elif 'pwd=jsdecode' in u:
                        real_u = self.decrypt_jsdecode(u)
                        key = real_u.split('?')[1] if '?' in real_u else real_u
                        if key in seen: continue
                        seen.add(key)
                    else:
                        real_u = u.replace('htmlplay://', 'video://').split('#')[0] if u.startswith('htmlplay') else u
                        if '@@' in real_u: real_u = real_u.split('@@')[0]
                    if real_u: raw_lines.append({'name': sname, 'url': real_u})
        except: pass
        
        sorted_lines = []
        if len(raw_lines) > 0:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                future_to_url = {executor.submit(self.check_url_info, line): line for line in raw_lines}
                results = []
                for future in concurrent.futures.as_completed(future_to_url):
                    try:
                        info = future.result()
                        if info['score'] > -90000:
                            tags = []
                            if info['quality_str']: tags.append(info['quality_str'])
                            if info['speed'] > 0: tags.append(f"{int(info['speed'])}K/s")
                            info['name'] = f"[{' '.join(tags)}]{info['name']}" if tags else info['name']
                            results.append(info)
                    except: pass
                results.sort(key=lambda x: x['score'], reverse=True)
                sorted_lines = results
        else: sorted_lines = raw_lines

        play_from = "$$$".join([l['name'] for l in sorted_lines])
        play_url = "$$$".join([f"直播${l['url']}" for l in sorted_lines])
            
        return {"list": [{"vod_id": ename, "vod_name": ename, "vod_play_from": play_from, "vod_play_url": play_url, "vod_pic": current_pic}]}

    def searchContent(self, key, quick, page='1'):
        nwtime = str(int(time.time()))
        src_key = f"{self.search_salt_start}{nwtime}{self.search_salt_end}"
        sign = hashlib.md5(src_key.encode()).hexdigest()
        params = {"id": f"*{key}", "deviceId": "ffffffff-da12-5a9f-0000-00002bc63564", "key": sign, "tm": nwtime, "app": "91ktv", "version": "2.1.3"}
        try:
            res = requests.get("http://sj.91kds.cn/api/get_search.php", params=params, headers=self.headers, verify=False)
            if res.status_code == 200:
                # 搜索结果也不显示特定台标
                return {'list': [{'vod_id': i.get('ename',''), 'vod_name': i.get('name',''), 'vod_pic': self.default_pic, 'vod_remarks': i.get('path','')} for i in res.json()]}
        except: pass
        return {'list': []}

    def playerContent(self, flag, pid, vipFlags):
        return {"url": pid, "header": self.headers, "parse": 0}

    def generate_source_url(self, ename):
        nwtime = str(int(time.time()))
        src_key = f"{ename}{self.list_sign_suffix}{nwtime}{self.ev_code}"
        sign = hashlib.md5(src_key.encode()).hexdigest()
        return f"{self.base_url}/api/get_source.php?ename={ename}&app={self.app_pkg}&version={self.app_version}&mac={self.mac_address}&nwtime={nwtime}&sign={sign}&ev={self.ev_code}"

    def decrypt_jsdecode(self, input_url):
        parts = input_url.split('?')
        base = parts[0]; q = dict(urllib.parse.parse_qsl(parts[1] if len(parts) > 1 else ''))
        vid = q.get('id', ''); bt = q.get('bt', None)
        p = {'app': 'com.jiaoxiang.fangnale', 'version': '2.3.4', 'mac': 'fu:ck:92:92:ff', 'utk': '', 'nwtime': str(int(time.time())), 'ev': self.ev_detail_code}
        s = vid
        for k in ['app', 'version', 'mac', 'utk', 'nwtime', 'ev']: s += (str(p[k]) + self.decode_append_str) if k == 'app' else str(p[k])
        p['sign'] = hashlib.md5(s.encode()).hexdigest()
        fq = [f"id={vid}"]
        if bt: fq.insert(0, f"bt={bt}")
        for k in ['app', 'version', 'mac', 'utk', 'nwtime', 'ev', 'sign']: fq.append(f"{k}={urllib.parse.quote(str(p[k]))}")
        return f"{base}?{'&'.join(fq)}"

if __name__ == '__main__':
    spider = Spider()
    spider.init({})