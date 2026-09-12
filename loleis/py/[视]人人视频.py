"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '丢丢喵',
  lang: 'hipy',
})
"""

# coding=utf-8
# !/usr/bin/python

"""

作者 丢丢喵 内容均从互联网收集而来 仅供交流学习使用 严禁用于商业用途 请于24小时内删除
         ====================Diudiumiao====================

"""

from Crypto.Util.Padding import unpad
from Crypto.Util.Padding import pad
from urllib.parse import unquote
from Crypto.Cipher import ARC4
from urllib.parse import quote
from base.spider import Spider
from Crypto.Cipher import AES
from datetime import datetime
from bs4 import BeautifulSoup
from base64 import b64decode
import urllib.request
import urllib.parse
import datetime
import binascii
import requests
import hashlib
import base64
import time
import json
import time
import hmac
import sys
import re
import os

sys.path.append('..')

xurl = "https://api.rrmj.plus"

xurl1 = "https://m.yichengwlkj.com"

ky_id = "BA21A0F5-7C57-41BA-8665-B7164A131832"

headerx = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.87 Safari/537.36'
          }

class Spider(Spider):

    def getName(self):
        return "丢丢喵"

    def init(self, extend):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeVideoContent(self):
        pass

    def get_sign_and_timestamp(self):
        current_timestamp = self.generate_current_timestamp()
        string_to_sign = self.build_string_to_sign(current_timestamp)
        x_ca_sign = self.calculate_signature(string_to_sign)
        return x_ca_sign, current_timestamp

    def generate_current_timestamp(self):
        return str(int(time.time() * 1000))

    def build_string_to_sign(self, current_timestamp):
        method = "GET"
        url_path = "/m-station/top/home"
        ali_id = ky_id
        ct = "web_pc"
        cv = "1.0.0"
        return "\n".join([method,f"aliId:{ali_id}",f"ct:{ct}",f"cv:{cv}",f"t:{current_timestamp}",url_path])

    def calculate_signature(self, string_to_sign):
        app_secret = "ES513W0B1CsdUrR13Qk5EgDAKPeeKZY"
        secret_bytes = app_secret.encode('utf-8')
        message_bytes = string_to_sign.encode('utf-8')
        signature = hmac.new(secret_bytes, message_bytes, hashlib.sha256).digest()
        return base64.b64encode(signature).decode('utf-8')

    def decrypt_aes_ecb(self, encrypted_data_str):
        key_bytes = self.get_aes_key()
        encrypted_bytes = self.prepare_encrypted_data(encrypted_data_str)
        decrypted_bytes = self.perform_aes_decryption(key_bytes, encrypted_bytes)
        unpadded_data = self.unpad_decrypted_data(decrypted_bytes)
        return self.parse_decrypted_json(unpadded_data)

    def get_aes_key(self):
        key_str = "3b744389882a4067"
        return key_str.encode('utf-8')

    def prepare_encrypted_data(self, encrypted_data_str):
        clean_data = encrypted_data_str.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
        return base64.b64decode(clean_data)

    def perform_aes_decryption(self, key_bytes, encrypted_bytes):
        cipher = AES.new(key_bytes, AES.MODE_ECB)
        return cipher.decrypt(encrypted_bytes)

    def unpad_decrypted_data(self, decrypted_bytes):
        return unpad(decrypted_bytes, AES.block_size)

    def parse_decrypted_json(self, unpadded_data):
        decrypted_str = unpadded_data.decode('utf-8')
        return json.loads(decrypted_str)

    def create_headers(self):
        x_ca_sign, current_timestamp = self.get_sign_and_timestamp()
        return self.build_headers_dict(x_ca_sign, current_timestamp)

    def build_headers_dict(self, x_ca_sign, current_timestamp):
        return {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Origin': xurl1,
            'Pragma': 'no-cache',
            'Referer': xurl1,
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
            'aliId': ky_id,
            'clientType': 'web_pc',
            'clientVersion': '1.0.0',
            'ct': 'web_pc',
            'cv': '1.0.0',
            'deviceId': ky_id,
            'sec-ch-ua': '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            't': current_timestamp,
            'token': '',
            'uet': '9',
            'umid': ky_id,
            'x-ca-sign': x_ca_sign,
                }

    def homeContent(self, filter):
        result = {"class": []}
        headers = self.create_headers()
        data = self.fetch_home_filter_data(headers)
        self.process_filter_items(data, result)
        return result

    def fetch_home_filter_data(self, headers):
        detail = requests.get(f'{xurl}/m-station/drama/get_drama_filter', headers=headers)
        detail.encoding = "utf-8"
        res5 = detail.text
        return self.decrypt_aes_ecb(res5)

    def process_filter_items(self, data, result):
        for vod in data['data'][1]['dramaFilterItemList']:
            name = vod['displayName']
            if self.should_skip_filter_item(name):
                continue
            id = vod['value']
            result["class"].append({"type_id": id, "type_name": name})

    def should_skip_filter_item(self, name):
        skip_names = ["全部"]
        return name in skip_names

    def categoryContent(self, cid, pg, filter, ext):
        videos = []
        page = self.parse_category_page(pg)
        headers = self.create_headers()
        params = self.build_category_params(cid, page)
        data = self.fetch_category_data(headers, params)
        self.process_category_videos(data, videos)
        return self.build_category_result(videos, pg)

    def parse_category_page(self, pg):
        return int(pg) if pg else 1

    def build_category_params(self, cid, page):
        return {'area': '','sort': 'hot','year': '','dramaType': cid,'plotType': '','contentLabel': '','page': page,'rows': 30,}

    def fetch_category_data(self, headers, params):
        detail = requests.post('https://api.rrmj.plus/m-station/drama/drama_filter_search', headers=headers,json=params)
        detail.encoding = "utf-8"
        res5 = detail.text
        return self.decrypt_aes_ecb(res5)

    def process_category_videos(self, data, videos):
        for vod in data['data']:
            video = self.create_category_video_item(vod)
            videos.append(video)

    def create_category_video_item(self, vod):
        name = vod['title']
        id = vod['dramaId']
        pic = vod['coverUrl']
        remark = vod.get('year', '暂无备注')
        return {"vod_id": id,"vod_name": name,"vod_pic": pic,"vod_remarks": remark}

    def build_category_result(self, videos, pg):
        return {'list': videos,'page': pg,'pagecount': 9999,'limit': 90,'total': 999999}

    def generate_sign_and_timestamp(self,url_path, params, method="GET", ali_id=ky_id, ct="web_pc", cv="1.0.0", t=None):
        APP_SECRET = "ES513W0B1CsdUrR13Qk5EgDAKPeeKZY"
        if t is None:
            t = str(int(time.time() * 1000))
        else:
            t = str(t)
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        full_url = url_path
        if query_string:
            full_url += "?" + query_string
        string_to_sign = (f"{method.upper()}\n"f"aliId:{ali_id}\n"f"ct:{ct}\n"f"cv:{cv}\n"f"t:{t}\n"f"{full_url}")
        signature = hmac.new(APP_SECRET.encode('utf-8'),string_to_sign.encode('utf-8'),hashlib.sha256).digest()
        x_ca_sign = base64.b64encode(signature).decode('utf-8')
        return x_ca_sign, t

    def get_sign_and_timestamp_with_drama_id(self, drama_id, url_path="/m-station/drama/page", method="GET",ali_id=ky_id, ct="web_pc", cv="1.0.0"):
        params = {"hsdrOpen": "0", "isAgeLimit": "0", "dramaId": str(drama_id), "quality": "AI4K", "hevcOpen": "0","tria4k": "1"}
        sign, timestamp = self.generate_sign_and_timestamp(url_path, params, method, ali_id, ct, cv)
        return sign, timestamp

    def rrmj_decrypt_v2(self,encrypted_text, new_sign):
        key_str = new_sign[4:20]
        iv_str = "b1da7878016e4e2b"
        key_bytes = key_str.encode('utf-8')
        iv_bytes = iv_str.encode('utf-8')
        ciphertext = base64.b64decode(encrypted_text)
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return decrypted_bytes.decode('utf-8')

    def decrypt_with_params(self, encrypted_data, new_sign_data):
        result = self.rrmj_decrypt_v2(encrypted_data, new_sign_data)
        return result

    def detailContent(self, ids):
        did = ids[0]
        result = {}
        videos = []
        sign, timestamp = self.get_sign_and_timestamp_with_drama_id(did)
        headers = self.build_detail_headers(sign, timestamp)
        params = self.build_detail_params(did)
        data = self.fetch_detail_data(headers, params)
        if not self.has_episodes(data):
            return {'msg': '温馨提示!正片还未上线哦'}
        remarks = self.extract_detail_remarks(data)
        year = self.extract_detail_year(data)
        area = self.extract_detail_area(data)
        bofang = self.build_play_urls(data, did)
        videos.append({"vod_id": did,"vod_remarks": remarks,"vod_year": year,"vod_area": area,"vod_play_from": "人人专线","vod_play_url": bofang})
        result['list'] = videos
        return result

    def build_detail_headers(self, sign, timestamp):
        return {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Origin': xurl1,
            'Pragma': 'no-cache',
            'Referer': xurl1,
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
            'aliId': ky_id,
            'clientType': 'web_pc',
            'clientVersion': '1.0.0',
            'ct': 'web_pc',
            'cv': '1.0.0',
            'deviceId': ky_id,
            'sec-ch-ua': '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            't': timestamp,
            'token': '',
            'uet': '9',
            'umid': ky_id,
            'x-ca-sign': sign,
                }

    def build_detail_params(self, did):
        return {'hsdrOpen': '0','isAgeLimit': '0','dramaId': did,'quality': 'AI4K','hevcOpen': '0','tria4k': '1',}

    def fetch_detail_data(self, headers, params):
        detail = requests.get(f'{xurl}/m-station/drama/page', params=params, headers=headers)
        detail.encoding = "utf-8"
        res5 = detail.text
        return self.decrypt_aes_ecb(res5)

    def has_episodes(self, data):
        return bool(data.get('data', {}).get('episodeList'))

    def extract_detail_remarks(self, data):
        return data.get('data', {}).get('dramaInfo', {}).get('playStatus', '')

    def extract_detail_year(self, data):
        return data.get('data', {}).get('dramaInfo', {}).get('year', '')

    def extract_detail_area(self, data):
        return data.get('data', {}).get('dramaInfo', {}).get('area', '')

    def build_play_urls(self, data, did):
        bofang = ''
        for vod in data['data']['episodeList']:
            name = str(vod['episodeNo'])
            id = f"{did}@{str(vod['id'])}"
            bofang += f"{name}${id}#"
        return bofang[:-1]

    def get_sign_and_timestams(self, path, params_dict):
        current_timestamp = str(int(time.time() * 1000))
        app_secret = "ES513W0B1CsdUrR13Qk5EgDAKPeeKZY"
        method = "GET"
        ali_id = ky_id
        ct = "web_pc"
        cv = "1.0.0"
        sorted_keys = sorted(params_dict.keys())
        query_parts = []
        for k in sorted_keys:
            query_parts.append(f"{k}={params_dict[k]}")
        sorted_query_string = "&".join(query_parts)
        full_path_with_query = f"{path}?{sorted_query_string}"
        string_to_sign = "\n".join([method,f"aliId:{ali_id}",f"ct:{ct}",f"cv:{cv}",f"t:{current_timestamp}",full_path_with_query])
        secret_bytes = app_secret.encode('utf-8')
        message_bytes = string_to_sign.encode('utf-8')
        signature = hmac.new(secret_bytes, message_bytes, hashlib.sha256).digest()
        x_ca_sign = base64.b64encode(signature).decode('utf-8')
        return x_ca_sign, current_timestamp

    def playerContent(self, flag, id, vipFlags):
        fenge = id.split("@")
        request_path = "/m-station/drama/play"
        params = self.build_player_params(fenge)
        x_ca_sign, current_timestamp = self.get_sign_and_timestams(request_path, params)
        headers = self.build_player_headers(x_ca_sign, current_timestamp)
        data = self.fetch_player_data(request_path, params, headers)
        url_value = self.extract_player_url(data)
        new_sign_value = self.extract_new_sign(data)
        decrypted_url = self.decrypt_with_params(url_value, new_sign_value)
        final_url = self.get_final_redirect_url(decrypted_url)
        return self.build_player_result(final_url)

    def build_player_params(self, fenge):
        return {'dramaId': fenge[0],'episodeSid': fenge[1],'hevcOpen': '0','hsdrOpen': '0','quality': 'AI4K','tria4k': '1',}

    def build_player_headers(self, x_ca_sign, current_timestamp):
        return {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'no-cache',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'aliId': ky_id,
            'clientType': 'web_pc',
            'clientVersion': '1.0.0',
            'ct': 'web_pc',
            'cv': '1.0.0',
            'deviceId': ky_id,
            't': current_timestamp,
            'token': '',
            'uet': '9',
            'umid': ky_id,
            'x-ca-sign': x_ca_sign,
                }

    def fetch_player_data(self, request_path, params, headers):
        full_url = f'{xurl}{request_path}'
        detail = requests.get(full_url, params=params, headers=headers)
        detail.encoding = "utf-8"
        res5 = detail.text
        return self.decrypt_aes_ecb(res5)

    def extract_player_url(self, data):
        return data['data']['m3u8']['url']

    def extract_new_sign(self, data):
        return data['data']['newSign']

    def get_final_redirect_url(self, decrypted_url):
        response = requests.get(url=decrypted_url, headers=headerx, allow_redirects=False)
        return response.headers.get('Location')

    def build_player_result(self, final_url):
        return {"parse": 0,"playUrl": '',"url": final_url,"header": headerx}

    def searchContentPage(self, key, quick, pg):
        videos = []
        headers = self.create_headers()
        params = self.build_search_params(key)
        data = self.fetch_search_data(headers, params)
        self.process_search_results(data, videos)
        return self.build_search_result(videos, pg)

    def build_search_params(self, key):
        return {'keywords': key,'size': '20','searchAfter': '',}

    def fetch_search_data(self, headers, params):
        detail = requests.get(f'{xurl}/search/comprehensive/precise-mixed', params=params, headers=headers)
        detail.encoding = "utf-8"
        res5 = detail.text
        return self.decrypt_aes_ecb(res5)

    def process_search_results(self, data, videos):
        for vod in data['data']['fuzzySeasonList']:
            video = self.create_search_video_item(vod)
            videos.append(video)

    def create_search_video_item(self, vod):
        name = vod['title']
        id = vod['id']
        pic = vod['cover']
        remark = vod.get('year', '暂无备注')
        return {"vod_id": id,"vod_name": name,"vod_pic": pic,"vod_remarks": remark}

    def build_search_result(self, videos, pg):
        return {'list': videos,'page': pg,'pagecount': 9999,'limit': 90,'total': 999999}

    def searchContent(self, key, quick, pg="1"):
        return self.searchContentPage(key, quick, '1')

    def localProxy(self, params):
        if params['type'] == "m3u8":
            return self.proxyM3u8(params)
        elif params['type'] == "media":
            return self.proxyMedia(params)
        elif params['type'] == "ts":
            return self.proxyTs(params)
        return None












