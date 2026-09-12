# -*- coding: utf-8 -*-
import re
import socket
import threading
import time
import requests
import html as _html
from base.spider import Spider
from Crypto.Cipher import AES
from urllib3 import disable_warnings
from http.server import BaseHTTPRequestHandler, HTTPServer

disable_warnings()

HOST = "https://www.ymvid.com"

# 全局变量
_GLOBAL_M3U8_DATA = ""
_LOCAL_PORT = 0
_TS_BASE_URL = ""  # 🔥 新增：用于动态记录当前视频切片的基础域名/路径

# 心跳全局配置管理
_HEARTBEAT_CONFIG = {
    "active": False,
    "seriesId": "",
    "playTime": "",
    "cookie": "",
    "ua": "",
    "referer": "",
    "browser_code": ""
}


# ==================== 后台守护线程：伪造持续心跳 ====================
def heartbeat_worker():
    """ 每隔 60 秒自动帮播放器上报一次状态，防止服务端拉黑或污染切片 """
    global _HEARTBEAT_CONFIG
    while True:
        if _HEARTBEAT_CONFIG["active"]:
            try:
                url = f"{HOST}/allocate/check_play_status"
                headers = {
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'X-Client-Type': 'web',
                    'Browser-Code': _HEARTBEAT_CONFIG["browser_code"],
                    'Content-Type': 'application/json;charset=UTF-8',
                    'User-Agent': _HEARTBEAT_CONFIG["ua"],
                    'Referer': _HEARTBEAT_CONFIG["referer"],
                    'Cookie': _HEARTBEAT_CONFIG["cookie"],
                    'Origin': HOST
                }
                payload = {
                    "playTime": _HEARTBEAT_CONFIG["playTime"],
                    "seriesId": _HEARTBEAT_CONFIG["seriesId"]
                }
                requests.post(url, json=payload, headers=headers, verify=False, timeout=5)
            except Exception:
                pass 
        time.sleep(60)


# ==================== 本地精准分流 M3U8 服务器 ====================
class M3U8Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _GLOBAL_M3U8_DATA, _TS_BASE_URL
        
        # 🔥 修复核心：只有显式请求 play.m3u8 时才吐出索引文本
        if "play.m3u8" in self.path:
            if _GLOBAL_M3U8_DATA:
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Connection", "close")
                self.send_header("Access-Control-Allow-Origin", "*")
                encoded = _GLOBAL_M3U8_DATA.encode("utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
            else:
                self.send_response(404)
                self.end_headers()
        
        # 🔥 修复核心：播放器请求真实的视频切片时，将其 302 重定向到远程真实视频服务器
        else:
            # 清洗出切片文件名
            ts_file = self.path.split('?')[0].lstrip('/')
            if ts_file and _TS_BASE_URL:
                # 拼接成真实的远程 TS 切片完整地址
                remote_ts_url = f"{_TS_BASE_URL}/{ts_file}"
                self.send_response(302)
                self.send_header("Location", remote_ts_url)
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

    def log_message(self, format, *args):
        pass


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def start_local_server():
    global _LOCAL_PORT
    _LOCAL_PORT = get_free_port()
    server = HTTPServer(('127.0.0.1', _LOCAL_PORT), M3U8Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    
    t_heartbeat = threading.Thread(target=heartbeat_worker, daemon=True)
    t_heartbeat.start()


start_local_server()


class Spider(Spider):

    def getName(self):
        return "粤漫之家"

    def init(self, extend=""):
        pass

    # ==================== 分类 ====================
    def homeContent(self, filter):
        classes = [
            {"type_id": "c0-s0-v0-l0-t0-y0/time_desc", "type_name": "全部(国/粤)"},
            {"type_id": "c1-s0-v0-l0-t0-y0/time_desc", "type_name": "粤语"},
            {"type_id": "c2-s0-v0-l0-t0-y0/time_desc", "type_name": "国语"},
            {"type_id": "c1-s0-v2-l0-t0-y0/time_desc", "type_name": "粤语·剧场版"},
        ]
        return {"class": classes}

    # ==================== 列表 ====================
    def categoryContent(self, tid, pg, filter, extend):
        curr_pg = int(pg)
        url = f"{HOST}/list/{curr_pg}/{tid}" if curr_pg > 1 else f"{HOST}/list/1/{tid}"
    
        res = requests.get(url, verify=False, timeout=10, headers={
            "User-Agent": "Mozilla/5.0"
        })
        html = res.text
    
        pattern = re.compile(
            r'<div[^>]*el-col-adapt[^>]*>.*?'
            r'href="[^"]*/play/(\d+)"[^>]*>.*?'
            r'<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"[^>]*>.*?'
            r'(?:<span[^>]*tips[^>]*>([^<]*)</span>)?.*?'
            r'</div>\s*</div>\s*</div>',
            re.S
        )
    
        vod_list = []
        seen = set()
    
        for m in pattern.finditer(html):
            vid = m.group(1)
            pic = m.group(2)
            name = m.group(3)
            remark = m.group(4)
    
            if vid in seen:
                continue
            seen.add(vid)
    
            vod_list.append({
                "vod_id": vid,
                "vod_name": name.strip() if name else "未知",
                "vod_pic": pic.strip() if pic else "",
                "vod_remarks": remark.strip() if remark else ""
            })
    
        has_next = bool(re.search(r'class="next"|下一页', html))
    
        return {
            "page": curr_pg,
            "pagecount": curr_pg + (1 if has_next else 0),
            "limit": 18,
            "total": 999,
            "list": vod_list
        }

    # ==================== 详情 ====================
    def detailContent(self, ids):
        vid = ids[0]
        url = f"{HOST}/play/{vid}"
    
        res = requests.get(url, verify=False, timeout=10, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": HOST
        })
        html = res.text
    
        name_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        vod_name = name_match.group(1).strip() if name_match else "未知影片"
    
        content_match = re.search(r'class="intro-detailh"[^>]*>(.*?)</div>', html, re.S)
        vod_content = re.sub(r'<[^>]+>', '', content_match.group(1)).strip() if content_match else "暂无简介"
    
        ep_pattern = re.compile(
            r'<a[^>]*href="[^"]*/play/(\d+)/(\d+)"[^>]*>.*?<em[^>]*>([^<]+)</em>',
            re.S
        )
    
        play_urls = []
        seen = set()
    
        for m in ep_pattern.finditer(html):
            vid = m.group(1)
            sid = m.group(2)
            ep_name = m.group(3).strip()
    
            if sid in seen:
                continue
            seen.add(sid)
    
            play_urls.append(f"{ep_name}$/{vid}/{sid}")
    
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": "",
                "vod_play_from": "默认线路",
                "vod_play_url": "#".join(play_urls),
                "vod_content": vod_content
            }]
        }

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        global _GLOBAL_M3U8_DATA, _LOCAL_PORT, _HEARTBEAT_CONFIG, _TS_BASE_URL
        parts = id.strip("/").split("/")
        if len(parts) != 2:
            return {"parse": 0, "url": "", "header": {}, "msg": f"id格式错误: {id}"}

        vid, sid = parts[0], parts[1]
        page_url = f"{HOST}/play/{vid}/{sid}"

        UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        BROWSER_CODE = "23eba08b88d695ab91292e6358b7db400db021e4ed10799cdd6aafae222c1d6f23b80da12bc0871aa114baef1ac684e6"
        MAGIC_COOKIE = f"lang=zh-CN; browser-code={BROWSER_CODE}"

        sess = requests.Session()
        
        try:
            r1 = sess.get(page_url, verify=False, timeout=10, headers={"User-Agent": UA, "Cookie": MAGIC_COOKIE})
            html = r1.text
        except Exception as e:
            return {"parse": 0, "url": "", "header": {}, "msg": f"播放页请求失败: {e}"}

        play_time_match = re.search(r'playTime\s*[:=]\s*["\']([^"\']+)["\']', html)
        detected_play_time = play_time_match.group(1) if play_time_match else "d6dd31bfdcd3466f832c506db420a0e3"

        enc_match = re.search(r'value\s*=\s*"([^"]+)"', html)
        if not enc_match:
            return {"parse": 0, "url": "", "header": {}, "msg": "enc未找到"}
        enc = enc_match.group(1).strip()

        try:
            key_bytes = "AVSI6788^765idue".encode("utf-8")
            cipher = AES.new(key_bytes, AES.MODE_ECB)
            ct_bytes = bytes.fromhex(enc)
            pt_bytes = cipher.decrypt(ct_bytes)
            
            pad_len = pt_bytes[-1]
            if 1 <= pad_len <= 16 and all(x == pad_len for x in pt_bytes[-pad_len:]):
                pt_bytes = pt_bytes[:-pad_len]

            if b"?t=" in pt_bytes:
                p_parts = pt_bytes.split(b"?t=", 1)
                base_path = p_parts[0].decode("utf-8", errors="ignore").strip().rstrip("/")
                t_raw_str = p_parts[1].decode("utf-8", errors="ignore").strip()
                t_val = "".join(c for c in t_raw_str if c.isalnum())
            else:
                dec_text = pt_bytes.decode("utf-8", errors="ignore").strip()
                p = dec_text.split("?t=")
                base_path = p[0].strip().rstrip("/")
                t_val = "".join(c for c in p[1] if c.isalnum()) if len(p) > 1 else ""
        except Exception as e:
            return {"parse": 0, "url": "", "header": {}, "msg": f"解密环节底层异常: {e}"}

        if not base_path.startswith("/"):
            base_path = "/" + base_path

        alloc = f"{HOST}{base_path}/{sid}?t={t_val}&vId={vid}"

        headers = {
            "User-Agent": UA,
            "Referer": page_url,
            "Origin": HOST,
            "Cookie": MAGIC_COOKIE
        }

        try:
            r2 = sess.get(alloc, headers=headers, verify=False, timeout=10)
            body = r2.text.strip()
        except Exception as e:
            return {"parse": 0, "url": "", "header": {}, "msg": f"分配接口请求失败: {e}"}

        def decrypt_second_layer(hex_data):
            try:
                cipher_inner = AES.new(key_bytes, AES.MODE_ECB)
                ct_inner = bytes.fromhex(hex_data.strip())
                pt_inner = cipher_inner.decrypt(ct_inner)
                pad = pt_inner[-1]
                if 1 <= pad <= 16:
                    pt_inner = pt_inner[:-pad]
                return pt_inner.decode("utf-8", errors="ignore").strip()
            except Exception:
                return ""

        m3u8_content = ""
        if body.startswith("#EXTM3U"):
            m3u8_content = body
        elif re.match(r"^[a-fA-F0-9]+$", body):
            m3u8_content = decrypt_second_layer(body)

        if not m3u8_content.startswith("#EXTM3U"):
            return {"parse": 0, "url": "", "header": {}, "msg": f"未成功解析出M3U8列表结构"}

        # 🔥 新增：动态捕获当前流媒体切片的 Base 域名基础路径，供本地重定向使用
        # 针对不带域名的相对路径切片，补齐远程服务器前缀
        ts_url_match = re.search(r'(https?://[^/\s]+(?:/[^/\s]+)*)/[^/\s]+\.ts', m3u8_content)
        if ts_url_match:
            _TS_BASE_URL = ts_url_match.group(1)
        else:
            # 如果 M3U8 里本身全是相对路径，则默认以分配接口所在目录为基准
            _TS_BASE_URL = alloc.rsplit('/', 1)[0]

        # 激活并注入心跳
        _HEARTBEAT_CONFIG["seriesId"] = str(sid)
        _HEARTBEAT_CONFIG["playTime"] = detected_play_time
        _HEARTBEAT_CONFIG["cookie"] = MAGIC_COOKIE
        _HEARTBEAT_CONFIG["ua"] = UA
        _HEARTBEAT_CONFIG["referer"] = page_url
        _HEARTBEAT_CONFIG["browser_code"] = BROWSER_CODE
        _HEARTBEAT_CONFIG["active"] = True  

        _GLOBAL_M3U8_DATA = m3u8_content
        local_play_url = f"http://127.0.0.1:{_LOCAL_PORT}/play.m3u8"

        return {
            "parse": 0,
            "play": 1,
            "url": local_play_url,
            "header": {
                "User-Agent": UA,
                "Referer": HOST
            }
        }

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg=1):
        curr_pg = int(pg)
        url = f"{HOST}/search?p={curr_pg}&keyword={key}" if curr_pg > 1 else f"{HOST}/search?keyword={key}"
    
        res = requests.get(url, verify=False, timeout=10, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": HOST
        })
        html = res.text
    
        pattern = re.compile(
            r'<div[^>]*item-row[^>]*>.*?'
            r'<a[^>]*href="[^"]*/play/(\d+)"[^>]*>.*?'
            r'<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)".*?>.*?'
            r'<div[^>]*item-title[^>]*>.*?<a[^>]*>([^<]*)</a>',
            re.S
        )
    
        vod_list = []
        seen = set()
    
        for m in pattern.finditer(html):
            vid, pic, alt, title = m.groups()
            if vid in seen:
                continue
            seen.add(vid)
    
            # ✅ 关键修复：解码 HTML 实体 + 去标签
            raw_name = alt or title or ''
            raw_name = _html.unescape(raw_name)          # &lt; → <
            raw_name = re.sub(r'<[^>]+>', '', raw_name)   # 去 <span>
            name = raw_name.strip() or '未知'
    
            vod_list.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic.strip(),
                "vod_remarks": ""
            })
    
        has_next = bool(re.search(r'下一页|class="next"|class="page-next"', html))
    
        return {
            "page": curr_pg,
            "pagecount": curr_pg + (1 if has_next else 0),
            "limit": len(vod_list),
            "total": 999,
            "list": vod_list
        }
    