import sys, os, re, json, time, base64
from datetime import datetime
from Crypto.Cipher import AES
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "YHDM"

    def init(self, extend=""):
        self.siteUrl = extend if extend else "https://www.857fans.com"
        self.configCache = {}

    def getHeaders(self):
        return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

    def homeContent(self, filter):
        classes = [{"type_id": "guochandongman", "type_name": "国产动漫"}, {"type_id": "ribendongman", "type_name": "日本动漫"}, {"type_id": "dongmandianying", "type_name": "动漫电影"}, {"type_id": "omeidongman", "type_name": "欧美动漫"}]
        rsp = self.fetch(self.siteUrl, headers=self.getHeaders())
        root = self.html(rsp.text)
        vod_list = []
        nodes = root.xpath('//div[contains(@class, "stui-vodlist")]//div[contains(@class, "myui-vodlist__box")]')
        for node in nodes:
            a_tag = node.xpath('.//a[1]')[0]
            pic = a_tag.xpath('./@data-original')[0]
            rem = node.xpath('.//span[contains(@class, "pic-text")]/text()')
            vod_list.append({"vod_id": a_tag.xpath('./@href')[0], "vod_name": a_tag.xpath('./@title')[0], "vod_pic": pic if pic.startswith("http") else self.siteUrl + pic, "vod_remarks": rem[0] if rem else ""})
        return {"class": classes, "list": vod_list}

    def homeVideoContent(self): return self.homeContent(False)

    def categoryContent(self, tid, pg, filter, extend):
        root = self.html(self.fetch(f"{self.siteUrl}/type/{tid}-{pg}.html", headers=self.getHeaders()).text)
        vod_list = []
        for node in root.xpath('//div[contains(@class, "myui-vodlist__box")]'):
            a_tag = node.xpath('.//a[1]')[0]
            pic = a_tag.xpath('./@data-original')[0]
            rem = node.xpath('.//span[contains(@class, "pic-text")]/text()')
            vod_list.append({"vod_id": a_tag.xpath('./@href')[0], "vod_name": a_tag.xpath('./@title')[0], "vod_pic": pic if pic.startswith("http") else self.siteUrl + pic, "vod_remarks": rem[0] if rem else ""})
        return {"list": vod_list}

    def detailContent(self, ids):
        root = self.html(self.fetch(self.siteUrl + ids[0], headers=self.getHeaders()).text)
        sources = root.xpath('//ul[contains(@class, "myui-content__list sort-list")]')
        circuits = root.xpath('//a[starts-with(@href, "#playlist")]')
        vod_play_from, vod_play_url = [], []
        for i in range(len(circuits)):
            name = circuits[i].xpath('./text()')[0]
            if "第一线路" in name:
                vod_play_from.append("84🚋")
                eps = [f"{link.xpath('./text()')[0]}${link.xpath('./@href')[0]}" for link in sources[i].xpath('.//a')]
                vod_play_url.append("#".join(eps))
                break
        dt = "".join(root.xpath('//div[contains(@class, "myui-content__detail")]//text()'))
        vod = {"vod_id": ids[0], "vod_name": root.xpath('//h1[@class="title"]/text()')[0], "type_name": self.regStr(r"类型：(.*?)\s", dt), "vod_area": self.regStr(r"地区：(.*?)\s", dt), "vod_year": self.regStr(r"年份：(.*?)\s", dt), "vod_remarks": self.regStr(r"更新：(.*?)\s", dt), "vod_content": "".join(root.xpath('//div[contains(@class, "col-pd text-collapse")]//span[@class="data"]/text()')), "vod_play_from": "$$$".join(vod_play_from), "vod_play_url": "$$$".join(vod_play_url)}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg='1'):
        root = self.html(self.fetch(f"{self.siteUrl}/search/{key}-------------.html", headers=self.getHeaders()).text)
        vod_list = []
        for node in root.xpath('//li[contains(@class, "clearfix")]'):
            a_tags = node.xpath('.//a')
            if not a_tags: continue
            pic = a_tags[0].xpath('./@data-original')[0]
            rem = node.xpath('.//span[contains(@class, "pic-text")]/text()')
            vod_list.append({"vod_id": a_tags[0].xpath('./@href')[0], "vod_name": a_tags[0].xpath('./@title')[0], "vod_pic": pic if pic.startswith("http") else self.siteUrl + pic, "vod_remarks": rem[0] if rem else ""})
        return {"list": vod_list}

    def playerContent(self, flag, id, vipFlags):
        t = datetime.now().strftime("%Y%m%d")
        cfg_url = f"{self.siteUrl}/static/js/playerconfig.js?t={t}"
        if cfg_url not in self.configCache:
            self.configCache[cfg_url] = json.loads(self.regStr(r"player_list=(.*?),MacPlayerConfig", self.fetch(cfg_url, headers=self.getHeaders()).text))
        p_json = json.loads(self.regStr(r"player_aaaa=(.*?)</script>", self.fetch(self.siteUrl + id, headers=self.getHeaders()).text))
        p_url = self.configCache[cfg_url].get(p_json["from"], {}).get("parse", "") + p_json["url"]
        p_rsp = self.fetch(p_url, headers=self.getHeaders()).text
        cipher = AES.new("57A891D97E332A9D".encode('utf-8'), AES.MODE_CBC, self.regStr(r"bt_token\s*=\s*\"(.*?)\"", p_rsp).encode('utf-8'))
        dec = cipher.decrypt(base64.b64decode(self.regStr(r"getVideoInfo\(\"(.*?)\"", p_rsp)))
        return {"parse": 0, "url": dec[:-dec[-1]].decode('utf-8'), "header": self.getHeaders()}

    def localProxy(self, param): pass
    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def destroy(self): pass