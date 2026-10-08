# -*- coding: utf-8 -*-
import sys, json, base64, gzip, urllib.parse, threading, time, concurrent.futures
import warnings
warnings.filterwarnings("ignore")

sys.path.append('..')
try:
 from base.spider import Spider as _B
except ImportError:
 class _B: pass
try:
 import requests
except ImportError:
 requests = None

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# ==================== 配置 ====================
API_DOMAIN = "https://api-al.yuytyr.online"
IMG_DOMAIN = "https://images.yxdesign.art"
PROXY_PORT = 8899

REQ_KEY = base64.b64decode("euZN1Gg3JIwWOEWhmE7C4l5dSSRU34fyuPMXjtuoqVs=")
RESP_KEY = b"db6f7f9e5d7a770e0e3497a7d7a077f5"
IMG_KEY = base64.b64decode("svOEKGb5WD0ezmHE4FXCVQ==")
IMG_IV = base64.b64decode("4B7eYzHTevzHvgVZfWVNIg==")

UA_APP = "Fulao2/Android 2.40; Lenovo TB-J606F"
UA_CDN = "com.ilulutv.fulao2.main.MyApplication/2.40 (Linux;Android 11) ExoPlayerLib/2.11.1"
UA_IMG = "Dalvik/2.1.0 (Linux; U; Android 11; Lenovo TB-J606F Build/RKQ1.210303.002)"

TARGET_CATEGORIES = ["推荐", "H动画", "最新", "抢先看", "中字", "NTR", "火爆", "FC2", "91大神", "传媒"]

X_INFO_LAUNCH = "eyJjcGFnZSI6ImxhdW5jaCIsInBsYXRmb3JtIjoyLCJwcGFnZSI6IiIsInZlcnNpb24iOiIyLjQwIn0="
X_INFO_CENSOR = "eyJjcGFnZSI6ImNlbnNvciIsInBsYXRmb3JtIjoyLCJwcGFnZSI6ImxhdW5jaCIsInZlcnNpb24iOiIyLjQwIn0="
X_INFO_PLAY = "eyJjcGFnZSI6InBsYXkiLCJwbGF0Zm9ybSI6MiwicHBhZ2UiOiJjZW5zb3IiLCJ2ZXJzaW9uIjoiMi40MCJ9"

STREAM_HOSTS = [
 ("VIP高速3", "https://stream.yxdesign.art"),
 ("VIP高速1", "https://stream.lingqi.co"),
 ("VIP高速2", "https://stream-hua.hangbo.xyz"),
 ("海外线路", "https://stream.ass6.store"),
]

QUALITIES = [("480", "高清"), ("240", "标清")]
# ==============================================

_M3U8_CACHE = {}
_CACHE_LOCK = threading.Lock()
_SERVER_STARTED = False

# ==================== 内置 HTTP 服务 ====================

class _Handler(BaseHTTPRequestHandler):
 def log_message(self, fmt, *args):
  pass

 def do_GET(self):
  parsed = urllib.parse.urlparse(self.path)
  qs = urllib.parse.parse_qs(parsed.query)
  try:
   if parsed.path == "/m3u8":
    key = urllib.parse.unquote(qs.get("vid", [""])[0])
    content = ""
    for _ in range(40):
     with _CACHE_LOCK:
      content = _M3U8_CACHE.get(key, "")
     if content:
      break
     time.sleep(0.5)

    if content:
     data = content.encode("utf-8")
     self.send_response(200)
     self.send_header("Content-Type", "application/vnd.apple.mpegurl")
     self.send_header("Content-Length", str(len(data)))
     self.send_header("Cache-Control", "no-cache")
     self.end_headers()
     self.wfile.write(data)
    else:
     self.send_response(404)
     self.end_headers()

   elif parsed.path == "/img":
    url = urllib.parse.unquote(qs.get("url", [""])[0])
    r = requests.get(
     url,
     headers={
      "User-Agent": UA_IMG,
      "Accept-Encoding": "gzip",
      "Connection": "Keep-Alive",
     },
     verify=False,
     timeout=10,
     allow_redirects=True,
    )
    raw = r.content
    try:
     body = unpad(AES.new(IMG_KEY, AES.MODE_CBC, IMG_IV).decrypt(raw), 16)
    except Exception:
     body = raw
    self.send_response(200)
    self.send_header("Content-Type", "image/jpeg")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

   else:
    self.send_response(404)
    self.end_headers()

  except Exception:
   try:
    self.send_response(500)
    self.end_headers()
   except Exception:
    pass

class _ThreadedServer(ThreadingMixIn, HTTPServer):
 daemon_threads = True
 allow_reuse_address = True

def _start_server():
 global _SERVER_STARTED
 if _SERVER_STARTED:
  return
 try:
  srv = _ThreadedServer(("127.0.0.1", PROXY_PORT), _Handler)
  t = threading.Thread(target=srv.serve_forever)
  t.daemon = True
  t.start()
  _SERVER_STARTED = True
  print("[Fulao2] 代理服务已启动 127.0.0.1:" + str(PROXY_PORT))
 except Exception as e:
  print("[Fulao2] 代理服务启动失败: " + str(e))

# ==================== Spider ====================

class Spider(_B):

 def init(self, e=""):
  self.token = ""
  self.sess = requests.Session()
  self.sess.verify = False
  self.sess.headers.update({
   "user-agent": UA_APP,
   "authorization": "Bearer ",
   "accept-encoding": "gzip",
   "x-info": X_INFO_LAUNCH,})
  _start_server()
  self._get_token()

 def getName(self):
  return "Fulao2"

 def isVideoFormat(self, u):
  return True

 def manualVideoCheck(self):
  return False

 # ==================== 加解密 ====================

 def _encrypt_payload(self, path):
  payload = json.dumps({
   "path": path,
   "device_id": "aeffaaa7-166c-4545-8971-c669ff59f611",
   "utm_medium": "",
   "model": "LENOVOLenovo TB-J606F",
   "universal_id": "3027776cc331ee45",
   "platform": "Android",
   "key": "f7787644a1f6b8e41a580fdfb4501acb9c095dda346567fa82a15c68a55b4ce1",
   "timestamp": "1785928268",
  }, separators=(',', ':'))
  iv = base64.b64decode("B3nBQVSgjRuC09mgsdbgIg==")
  ct = AES.new(REQ_KEY, AES.MODE_CBC, iv).encrypt(pad(payload.encode(), 16))
  return base64.b64encode(iv).decode() + "." + base64.b64encode(ct).decode()

 def _decrypt_resp(self, text):
  try:
   ct = base64.b64decode(text)
   iv = bytes(a ^ b for a, b in zip(
    AES.new(RESP_KEY, AES.MODE_ECB).decrypt(ct[:16]),
    b'{"status":{"code'.ljust(16, b'\x00'),
   ))
   raw = unpad(AES.new(RESP_KEY, AES.MODE_CBC, iv).decrypt(ct), 16)
   if raw[:2] == b'\x1f\x8b':
    raw = gzip.decompress(raw)
   return json.loads(raw.decode())
  except Exception as e:
   print("[decrypt_err] " + str(e))
   return None

 def _decrypt_m3u8(self, text):
  try:
   ct = base64.b64decode(text)
   iv = bytes(a ^ b for a, b in zip(
    AES.new(RESP_KEY, AES.MODE_ECB).decrypt(ct[:16]),
    b'#EXTM3U\n#EXT-X-V',
   ))
   raw = unpad(AES.new(RESP_KEY, AES.MODE_CBC, iv).decrypt(ct), 16)
   if raw[:2] == b'\x1f\x8b':
    raw = gzip.decompress(raw)
   return raw.decode('utf-8', errors='ignore')
  except Exception as e:
   print("[decrypt_m3u8_err] " + str(e))
   return None

 def _api(self, method, path, xinfo=None):
  enc = self._encrypt_payload(path)
  url = API_DOMAIN + "/" + path
  h = {}
  if xinfo:
   h["x-info"] = xinfo
  try:
   if method == "POST":
    h["content-type"] = "application/x-www-form-urlencoded"
    r = self.sess.post(
     url,
     data="payload=" + urllib.parse.quote(enc),
     headers=h,
     timeout=15,
    )
   else:
    r = self.sess.get(
     url + "?payload=" + urllib.parse.quote(enc),
     headers=h,
     timeout=15,
    )
   if r.status_code == 200:
    return self._decrypt_resp(r.text)
   return None
  except Exception as e:
   print("[api_err] " + path + " " + str(e))
   return None

 # ==================== Token ====================

 def _get_token(self):
  data = self._api("POST", "v1/register/token")
  if data and "response" in data:
   resp = data["response"]
   self.token = resp.get("token", resp.get("access_token", ""))
   self.sess.headers["authorization"] = "Bearer " + self.token

 # ==================== 封面 ====================

 def _img_url(self, path):
  if not path:
   return ""
  if path.startswith("http"):
   full = path
  else:
   full = IMG_DOMAIN + ("" if path.startswith("/") else "/") + path
  return (
   "http://127.0.0.1:" + str(PROXY_PORT)
   + "/img?url=" + urllib.parse.quote(full, safe="")
  )

 # ==================== m3u8 获取 ====================

 def _fetch_m3u8(self, vid, h_label, h_host, quality):
  cache_key = vid + "_" + h_label + "_" + quality
  with _CACHE_LOCK:
   if cache_key in _M3U8_CACHE:
    return cache_key
  url = (
   API_DOMAIN + "/v3/media/" + quality + "/" + vid
   + ".m3u8?&token=" + self.token + "&h=" + h_host
  )
  try:
   resp = self.sess.get(url, timeout=20, allow_redirects=True)
   if resp.status_code != 200:
    print("[fetch_m3u8] " + h_label + "-" + quality
    + " 状态码=" + str(resp.status_code))
    return None
   text = self._decrypt_m3u8(resp.text)
   if not text:
    return None
   with _CACHE_LOCK:
    _M3U8_CACHE[cache_key] = text
   print("[fetch_m3u8] " + h_label + "-" + quality + " OK")
   return cache_key
  except Exception as e:
   print("[fetch_m3u8] " + h_label + "-" + quality + " " + str(e))
   return None

 def _play_url(self, cache_key):
  return (
   "http://127.0.0.1:" + str(PROXY_PORT)
   + "/m3u8?vid=" + urllib.parse.quote(cache_key, safe="")
  )

 # ==================== 首页分类 ====================

 def homeContent(self, filter=False):
  data = self._api("GET", "v2/menu/type")
  classes = []
  if data and "response" in data:
   seen = set()
   for group in ["pixeled", "unpixeled"]:
    for item in data["response"].get(group, []):
     t = item.get("title", "")
     if t in TARGET_CATEGORIES and t not in seen:
      seen.add(t)
      classes.append({
       "type_id": str(item["id"]),
       "type_name": t,
      })
  return {"class": classes, "filters": {}}

 def homeVideoContent(self):
  return {"list": []}

 # ==================== 分类列表 ====================

 def categoryContent(self, tid, pg=1, filter=False, extend=None):
  data = self._api("GET", "v1/menu/" + str(tid) + "/layout", xinfo=X_INFO_CENSOR)
  videos = []
  if data and "response" in data:
   for layout in data["response"]:
    items = layout.get("data", [])
    if isinstance(items, dict):
     items = [items]
    if not isinstance(items, list):
     continue
    for v in items:
     vid = v.get("video_id")
     title = v.get("video_title", "")
     if not vid or not title:
      continue
     raw_pic = v.get("cover") or v.get("thumb", "")
     actor = v.get("actor", "")
     if isinstance(actor, list):
      actor = "、".join(actor)
     videos.append({
      "vod_id": str(vid),
      "vod_name": title,
      "vod_pic": self._img_url(raw_pic),
      "vod_remarks": actor,
     })
  return {
   "list": videos,
   "page": pg,
   "pagecount": 99,
   "limit": len(videos) or 20,
  }

 # ==================== 视频详情 ====================

 def detailContent(self, ids):
  vid = str(ids[0])

  # 1. 获取元数据
  info = self._api("GET", "v1/video/info/" + vid, xinfo=X_INFO_PLAY)
  raw_pic = ""
  title = ""
  number = ""
  desc = ""
  actor = ""
  tags = ""
  if info and "response" in info:
   r = info["response"]
   raw_pic = r.get("cover_url") or r.get("cover") or r.get("thumb", "")
   title = r.get("video_title", "")
   number = r.get("video_number", "")
   desc = r.get("video_description", "")
   a = r.get("actor", [])
   actor = "、".join(a) if isinstance(a, list) else str(a)
   tg = r.get("video_tags", [])
   tags = " ".join(tg) if isinstance(tg, list) else str(tg)

  # 2. 同步请求默认线路高清
  default_label = STREAM_HOSTS[0][0]
  default_host = STREAM_HOSTS[0][1]
  default_key = self._fetch_m3u8(vid, default_label, default_host, "480")
  if not default_key:
   default_key = self._fetch_m3u8(vid, default_label, default_host, "240")
  if not default_key:
   print("[detail] 默认线路解析失败 vid=" + vid)
   return {"list": []}

  # 3. 后台并发预热其余组合
  def prefetch_all():
   tasks = []
   for hl, hh in STREAM_HOSTS:
    for q, _ in QUALITIES:
     ck = vid + "_" + hl + "_" + q
     with _CACHE_LOCK:
      if ck not in _M3U8_CACHE:
       tasks.append((vid, hl, hh, q))
   if not tasks:
    return
   with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    futs = [ex.submit(self._fetch_m3u8, *args) for args in tasks]
    concurrent.futures.wait(futs)

  threading.Thread(target=prefetch_all, daemon=True).start()

  # 4. 构造播放列表，每个 key 指向自己的线路/清晰度
  from_parts = []
  url_groups = []

  for h_label, h_host in STREAM_HOSTS:
   parts = []
   for quality, q_label in QUALITIES:
    ck = vid + "_" + h_label + "_" + quality
    parts.append(q_label + "$" + self._play_url(ck))
   from_parts.append(h_label)
   url_groups.append("$$$".join(parts))

  return {"list": [{
   "vod_id": vid,
   "vod_name": title,
   "vod_pic": self._img_url(raw_pic),
   "vod_remarks": number,
   "vod_content": desc or tags,
   "vod_actor": actor,
   "vod_play_from": "$$$".join(from_parts),
   "vod_play_url": ":::".join(url_groups),
  }]}

 # ==================== 播放 ====================

 def playerContent(self, flag, id, vipFlags=None):
  return {
   "parse": 0,
   "url": id,
   "header": json.dumps({
    "User-Agent": UA_CDN,
    "Cookie": "jwt=token",
   }),
  }

 def localProxy(self, param):
  pass

 def searchContent(self, key, quick=False, pg=1):
  return {"list": []}
