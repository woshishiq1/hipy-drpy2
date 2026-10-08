# -*- coding: utf-8 -*-
# by @嗷呜

import re
import sys
import uuid
from base64 import b64decode, b64encode
from concurrent.futures import ThreadPoolExecutor
from pprint import pprint
from Crypto.Cipher import AES
from Crypto.Hash import HMAC, SHA1
from Crypto.Util.Padding import unpad
sys.path.append('..')
from base.spider import Spider
import time
import json


class Spider(Spider):

    def init(self, extend=""):
        pass

    def getName(self):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    host = 'https://vlogic.mfxdf.cn'
    phost='https://vres.kvod6.com'
    # phost='https://vlogic.kvod10.com'

    t = str(int(time.time()) * 1000)

    def homeContent(self, filter):
        data = self.getdata('/v4/config/appInit.capi', {"appId": "kkdy", "os": "android", "userLevel": "0"})
        result = {}
        try:
            modu = self.loadSpider("Wogg")
            hosts=data['urls']['cache']
            self.host = hosts[0] if len(hosts)==1 else modu.host_late(hosts)
        except:
            pass
        vodTabs = data['vodTabs']
        classes = []
        for tab in vodTabs:
            if tab.get("type") not in ["home", "netflix"]:
                classes.append({
                    "type_id": tab.get("name", ""),
                    "type_name": tab.get("text", "")
                })
        filters = {}
        channelListQuery = data['channelListQuery']
        for channel in channelListQuery:
            cid = str(channel.get("channelId"))
            if cid not in [c["type_id"] for c in classes]:
                continue

            filter_array = []
            for item in channel.get("items", []):
                value_array = []
                for data in item.get("data", []):
                    value_array.append({
                        "n": data.get("name", ""),
                        "v": data.get("id", "")
                    })

                if value_array:
                    filter_array.append({
                        "key": item.get("query", ""),
                        "name": value_array[0].get("n", ""),
                        "value": value_array[1:]
                    })

            if filter_array:
                filters[cid] = filter_array

        result["class"] = classes
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        params = {"appId": "kkdy", "os": "android", "userLevel": "2"}
        data = self.getdata('/v4/vod/home.capi', params)
        vlist = []
        for item in data['data']['blocks']:
            if item.get('data', None) and isinstance(item['data'], list):
                if 'vod/detail?vodId=' in item['data'][0].get('url', None):
                    vlist=self.getlist(item['data'])
        return {'list': vlist}

    def categoryContent(self, tid, pg, filter, extend):
        params = {"appId": "kkdy", "area": extend.get("area", ""), "category": extend.get("category", ""), "channelId": tid, "language": "", "next": f"{'' if pg == '1' else f'page={pg}'}", "os": "android", "sort": extend.get("sort", ""), "userLevel": "2", "year": extend.get("year", "")}
        data = self.getdata('/vod/channel/list.capi', params)
        result = {}
        result['list'] = self.getlist(data['data']['items'])
        result['page'] = pg
        result['pagecount'] = 9999
        result['limit'] = 90
        result['total'] = 999999
        return result

    def detailContent(self, ids):
        params = {"appId":"kkdy","os": "android","userLevel": "2","vodId":ids[0]}
        data = self.getdata('/v2/vod/detail.capi', params)
        data = data['data']
        vod = {
            'vod_name': data.get('title'),
            'type_name': data.get('channelName'),
            'vod_year': data.get('premiereDate'),
            'vod_remarks': data.get('bottomLabel'),
            'vod_content': data.get('summary')
        }
        pname=[]
        purl=[]
        tasks = []
        for i in data['playSources']:
            pname.append(i['name'])
            if len(i['list'])>0:
                purl.append(self.dlist(i['list']))
            else:
                tasks.append({"appId": "kkdy","episodeVodId": str(i['episodeVodId']),"os": "android","siteId": i['siteId'],"userLevel": "2","vodId": ids[0]})
        if tasks:
            with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
                results = executor.map(self.mflist, tasks)
                for result in results:
                    if result:
                        purl.append(result)
                    else:
                        purl.append("")
        vod['vod_play_from']='$$$'.join(pname)
        vod['vod_play_url']='$$$'.join(purl)
        return {'list':[vod]}

    def searchContent(self, key, quick, pg="1"):
        params = {
            "appId": "kkdy",
              "channelId": "0",
              "k": key,
              "next": f"page={pg}",
              "os": "android",
              "userChannel": "c1",
              "userLevel": "2"
            }
        if pg == "1" or not pg:params['next'] =''
        data = self.getdata('/vod/search/query', params)
        vlist = self.getlist(data['data']['items'])
        return {'list': vlist, 'page': pg}

    def playerContent(self, flag, id, vipFlags):
        return {'parse':0,'url':id,'header': {'User-Agent':'com.stub.StubApp/3.3.1 (Linux;Android 11) ExoPlayerLib/2.18.1'}}

    def localProxy(self, param):
        pass

    def aes(self, encrypted_text):
        key = "ayt5wy5afwmwrpb19k9s3psx3dymyd0n".encode('utf-8')
        iv = "b3t069ijy7pirw0jayt5wy5afwmwrpb1".encode('utf-8')
        encrypted_data = b64decode(encrypted_text)
        cipher = AES.new(key, AES.MODE_CBC, iv[:16])
        decrypted_data = cipher.decrypt(encrypted_data)
        unpadded_data = unpad(decrypted_data, AES.block_size)
        result = unpadded_data.decode('utf-8')
        return result

    def getsign(self, path, query_params, device_info):
        message = f"get|{path}|{query_params}|{self.t}|{device_info}|"
        key = "ksggsr4tp6difdo1c3im8fqd3g"
        message_bytes = message.encode('utf-8')
        key_bytes = key.encode('utf-8')
        h = HMAC.new(key_bytes, digestmod=SHA1)
        h.update(message_bytes)
        signature = h.hexdigest()
        return signature

    def getHeaders(self, path, query_params):
        uid = str(uuid.uuid4())
        deviceid = "730bd3c2d2941505"
        devicecreatedat = "1735803745796"
        userid = "17246016"
        deviceinfo = {"brand": "Xiaomi", "model": "M2012K10C", "type": "phone", "resolutionX": "1080",
                      "resolutionY": "2272", "orientation": "1", "osName": "android", "osVersion": "11",
                      "osLevel": "30", "abi": "arm64-v8a,armeabi-v7a,armeabi", "androidId": deviceid, "uuid": uid,
                      "gaid": ""}
        hdeviceinfo = b64encode(json.dumps(deviceinfo).encode('utf-8')).decode('utf-8')
        x_token = "MTcyNDYwMTZ8MTczNTc0NDg3OXxiNjcyM2Y0NmMzY2YwNGU1OGMwOGU5NzMyZTQyY2U4ODE1ZjM2M2FmZTRiOGZiYTI3YzU3N2M1NzI1NjQzNzc3"
        headers = {
            'User-Agent': 'com.sbskk.k17/3.3.1 Dalvik/2.1.0 (Linux; U; Android 11; M2012K10C Build/RP1A.200720.011)',
            'x-cdn': '1',
            'x-token': x_token,
            'appid': 'kkdy',
            'os': 'android',
            'appversion': '3.3.1',
            'package': 'com.sbskk.k17',
            'deviceid': deviceid,
            'devicecreatedat': devicecreatedat,
            'userid': userid,
            'deviceinfo': hdeviceinfo,
            'channelid': 'c1',
            'x-d-video': '1',
            'st': '2',
            'ts': self.t,
            'sign': self.getsign(path, query_params,f'appId=kkdy&deviceCreatedAt={devicecreatedat}&deviceId={deviceid}&st=2&userId={userid}'),
        }
        return headers

    def js(self, param):
        return '&'.join(f"{k}={v}" for k, v in param.items())

    def getdata(self, path, params):
        query_params = self.js(params)
        headers = self.getHeaders(path, query_params)
        data = self.fetch(f'{self.host}{path}?{query_params}', headers=headers).content
        tdata = self.aes(b64encode(data).decode('utf-8'))
        return json.loads(tdata)

    def getlist(self,data):
        vlist = []
        ph = {
            'User-Agent': 'okhttp/4.10.0',
            'group': 'vod1',
            'imageindex': '0',
        }
        ph='@'.join(f"{k}={v}" for k, v in ph.items())
        for i in data:
            img=self.phost+i.get('imagePath').replace('vod','vod1/vod')+'@'+ph
            vlist.append({
                'vod_id': i.get('id'),
                'vod_name': re.sub(r'<[^>]+>', '', i.get('title')),
                'vod_pic': img,
                'vod_year': i.get('topLeftLabel'),
                'vod_remarks': i.get('bottomLabel')}
            )
        return vlist

    def mflist(self, body):
        data = self.getdata('/v2/vod/episodes.capi', body)
        return self.dlist(data['data'])

    def dlist(self, data):
        vlist = []
        for j in data:
            try:
                # 尝试添加到列表
                vlist.append(j['title'] + '$' + j['playUrls'][0]['url'])
            except Exception as e:
                # 如果有错误，打印 j 和错误信息
                print(f"Error with item: {j}")
                print(f"Error message: {e}")
        return '#'.join(vlist)


if __name__ == "__main__":
    sp = Spider()
    # formatJo = sp.init([])
    # formatJo = sp.homeContent(False)  # 主页，等于真表示启用筛选
    # formatJo = sp.homeVideoContent()  # 主页视频
    # formatJo = sp.searchContent("斗罗",False,'2') # 搜索{"area":"大陆","by":"hits","class":"国产","lg":"国语"}
    formatJo = sp.categoryContent('2', '1', False, {})  # 分类
    # formatJo = sp.detailContent(['228147'])  # 详情
    # formatJo = sp.playerContent("","https://www.yingmeng.net/vodplay/140148-2-1.html",{}) # 播放
    # formatJo = sp.localProxy({"":"https://www.yingmeng.net/vodplay/140148-2-1.html"}) # 播放
    pprint(formatJo)
