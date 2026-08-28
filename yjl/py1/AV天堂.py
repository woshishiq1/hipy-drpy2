#!/usr/bin/python
# coding=utf-8
import re, json, requests, base64, hashlib
from urllib.parse import quote
from base.spider import Spider

try:
   from Crypto.Cipher import AES
   from Crypto.Util.Padding import unpad
except:
   AES = None

class Spider(Spider):
   def init(self, extend=""):
       self.name = "AV天堂"
       self.author = "提拉米叔"
       self.host = "https://san3le.tt3366.cyou"
       self.header = {
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
           "Referer": self.host + "/",
           "Accept-Language": "zh-CN,zh;q=0.9"
       }
       self.aes_key = b"a9yX32LpQvUt7wBc"
       self.aes_iv = b"N7cPk2Bv38hWqFzM"
       self.home_ids = "1023,1026,1029"

   def getName(self):
       return self.name

   def fix_url(self, url):
       if not url:
           return ""
       if url.startswith("//"):
           return "https:" + url
       if url.startswith("/"):
           return self.host + url
       return url

   def clean_text(self, text):
       if not text:
           return ""
       return re.sub(r"\s+", " ", str(text)).strip()

   def isVideoFormat(self, url):
       if not url:
           return False
       u = url.lower()
       return any(u.endswith(e) for e in [".m3u8", ".mp4", ".avi", ".flv", ".mkv", ".ts"]) or "m3u8" in u

   def decrypt(self, cipher_b64):
       if not cipher_b64 or AES is None:
           return {}
       try:
           raw = base64.b64decode(cipher_b64)
           cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_iv)
           pt = unpad(cipher.decrypt(raw), AES.block_size)
           return json.loads(pt.decode("utf-8"))
       except:
           return {}

   def api(self, path):
       if getattr(self, "author", "") != "提拉米叔":
           return {}
       try:
           r = requests.get(self.host + path, headers=self.header, timeout=15, verify=False)
           if r.status_code != 200:
               return {}
           j = r.json()
           if "cipher" in j:
               data = self.decrypt(j["cipher"])
               return data.get("data", data) if isinstance(data, dict) else {}
           return j.get("data", j)
       except:
           return {}

   def homeContent(self, filter):
       result = {"class": [], "list": []}
       cats = self.api("/api/categories/video")
       clist = cats.get("list", []) if isinstance(cats, dict) else []
       for c in clist:
           try:
               tid = str(c.get("id", ""))
               name = self.clean_text(c.get("name", ""))
               if tid and name:
                   result["class"].append({"type_id": tid, "type_name": name})
           except:
               continue
       blocks = self.api(f"/api/categories/blocks?ids={self.home_ids}&vps=12")
       seen = set()
       blist = blocks.get("list", []) if isinstance(blocks, dict) else []
       for blk in blist:
           for v in (blk.get("videos") or []):
               try:
                   vid = str(v.get("id", ""))
                   if not vid or vid in seen:
                       continue
                   seen.add(vid)
                   result["list"].append({
                       "vod_id": vid,
                       "vod_name": self.clean_text(v.get("title", "")),
                       "vod_pic": self.fix_url(v.get("cover_url", "")),
                       "vod_remarks": self.clean_text(v.get("category", "") or str(v.get("hits", "")))
                   })
               except:
                   continue
       return result

   def homeVideoContent(self):
       return self.homeContent(False)

   def categoryContent(self, tid, pg, filter, extend):
       result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
       page = int(pg) if pg else 1
       data = self.api(f"/api/videos?category_id={tid}&page={page}&ps=20")
       if not isinstance(data, dict):
           return result
       result["total"] = int(data.get("total", 0) or 0)
       result["pagecount"] = int(data.get("pages", 1) or 1)
       result["page"] = int(data.get("page", page) or page)
       result["limit"] = int(data.get("ps", 20) or 20)
       seen = set()
       for v in (data.get("list") or []):
           try:
               vid = str(v.get("id", ""))
               if not vid or vid in seen:
                   continue
               seen.add(vid)
               result["list"].append({
                   "vod_id": vid,
                   "vod_name": self.clean_text(v.get("title", "")),
                   "vod_pic": self.fix_url(v.get("cover_url", "")),
                   "vod_remarks": self.clean_text(v.get("category", "") or str(v.get("hits", "")))
               })
           except:
               continue
       return result

   def detailContent(self, ids):
       result = {"list": []}
       vid = ids[0] if isinstance(ids, list) else str(ids)
       data = self.api(f"/api/movie?id={vid}")
       if not isinstance(data, dict):
           return result
       info = data.get("info") or data
       name = self.clean_text(info.get("title", ""))
       pic = self.fix_url(info.get("cover_url", ""))
       play_url = self.fix_url(info.get("play_url", ""))
       play_from = self.clean_text(info.get("play_from", "") or "直链")
       if not play_url:
           play_url = ""
       vod = {
           "vod_id": str(info.get("id", vid)),
           "vod_name": name,
           "vod_pic": pic,
           "vod_content": self.clean_text(info.get("category", "")),
           "vod_remarks": str(info.get("hits", "")),
           "vod_play_from": play_from if play_url else "",
           "vod_play_url": f"正片${play_url}" if play_url else ""
       }
       result["list"].append(vod)
       return result

   def searchContent(self, key, quick, pg="1"):
       result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
       page = int(pg) if pg else 1
       data = self.api(f"/api/videos?kw={quote(key)}&page={page}&ps=20")
       if not isinstance(data, dict):
           return result
       result["total"] = int(data.get("total", 0) or 0)
       result["pagecount"] = int(data.get("pages", 1) or 1)
       result["page"] = int(data.get("page", page) or page)
       result["limit"] = int(data.get("ps", 20) or 20)
       seen = set()
       for v in (data.get("list") or []):
           try:
               vid = str(v.get("id", ""))
               if not vid or vid in seen:
                   continue
               seen.add(vid)
               result["list"].append({
                   "vod_id": vid,
                   "vod_name": self.clean_text(v.get("title", "")),
                   "vod_pic": self.fix_url(v.get("cover_url", "")),
                   "vod_remarks": self.clean_text(v.get("category", "") or str(v.get("hits", "")))
               })
           except:
               continue
       return result

   def playerContent(self, flag, id, vipFlags):
       url = id
       if not self.isVideoFormat(url):
           data = self.api(f"/api/movie?id={id}")
           info = (data.get("info") or data) if isinstance(data, dict) else {}
           url = self.fix_url(info.get("play_url", ""))
       header = {
           "User-Agent": self.header["User-Agent"],
           "Referer": self.host + "/"
       }
       return {
           "parse": 0,
           "url": url or "",
           "header": header
       }

   def localProxy(self, param):
       return [200, "video/MP2T", b"", 0]
