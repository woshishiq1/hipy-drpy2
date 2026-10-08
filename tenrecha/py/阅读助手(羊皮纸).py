# coding=utf-8
# !/usr/bin/python


import time
import sys
import hashlib
import base64
import json
import requests
import threading
import socket
import http.server
import socketserver
import urllib.parse
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# ==================== 1. 本地 Web 服务器 ====================

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class NovelHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        spider = getattr(self.server, 'spider', None)
        path_info = urllib.parse.urlparse(self.path)
        path = path_info.path
        query = urllib.parse.parse_qs(path_info.query)
        
        if path == '/read.html':
            self.serve_reader_ui()
        elif path == '/api/chapter':
            self.serve_chapter_data(spider, query)
        else:
            self.send_error(404)

    def serve_reader_ui(self):
        # 羊皮纸风格 HTML
        html = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>阅读器</title>
            <style>
                body {
                    margin: 0; 
                    padding: 20px 16px;
                    /* 【修改点1】羊皮纸背景色 */
                    background-color: #f8f1e3; 
                    /* 【修改点2】深褐色文字 */
                    color: #3e3e3e;
                    font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
                    line-height: 1.8;
                    font-size: 20px;
                    word-wrap: break-word;
                }
                #content-wrapper {
                    max-width: 100%;
                    padding-bottom: 80px;
                }
                h2 {
                    color: #5b4636; /* 深棕色标题 */
                    border-bottom: 2px solid #8c7b75;
                    padding-bottom: 10px;
                    margin-top: 10px;
                    margin-bottom: 30px;
                    font-size: 1.3em;
                    font-weight: bold;
                    text-align: center;
                }
                p {
                    margin-bottom: 1.2em;
                    text-align: justify;
                    text-indent: 2em;
                }
                
                /* 底部控制栏 - 米色磨砂风格 */
                .controls {
                    position: fixed;
                    bottom: 0; left: 0; right: 0;
                    background: rgba(248, 241, 227, 0.95);
                    padding: 15px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-top: 1px solid #d1c7b7;
                    z-index: 999;
                    box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
                }
                .btn {
                    background: #e6dcc8; /* 按钮浅棕色 */
                    color: #5b4636;
                    border: 1px solid #c9bca8; 
                    padding: 10px 25px;
                    border-radius: 20px; 
                    font-size: 16px;
                    cursor: pointer;
                    outline: none;
                    font-weight: bold;
                }
                .btn:active { background: #d1c7b7; }
                
                /* 进度文字 */
                #page-info {
                    font-size: 14px;
                    color: #8c7b75;
                    font-family: monospace;
                }

                /* 加载提示 */
                #loading {
                    position: fixed; top: 50%; left: 50%;
                    transform: translate(-50%, -50%);
                    background: rgba(0,0,0,0.6);
                    color: white; padding: 15px 25px;
                    border-radius: 8px; display: none;
                    z-index: 1000;
                }
            </style>
        </head>
        <body>
            <div id="loading">加载中...</div>
            
            <div id="content-wrapper">
                <h2 id="chapter-title">准备加载...</h2>
                <div id="chapter-text"></div>
            </div>

            <div class="controls">
                <button class="btn" onclick="prevChapter()">上一章</button>
                <span id="page-info">0/0</span>
                <button class="btn" onclick="nextChapter()">下一章</button>
            </div>

            <script>
                const params = new URLSearchParams(window.location.search);
                const bid = params.get('bid');
                let currentIdx = parseInt(params.get('idx') || '0');

                window.onload = function() {
                    loadChapter(currentIdx);
                };

                async function loadChapter(idx) {
                    if(idx < 0) return msg("已经是第一章了");
                    showLoading(true);
                    try {
                        const res = await fetch(`/api/chapter?bid=${bid}&idx=${idx}`);
                        const data = await res.json();
                        
                        if(data.code !== 200) {
                            alert(data.msg || "加载失败");
                            return;
                        }

                        document.getElementById('chapter-title').innerText = data.title;
                        document.getElementById('chapter-text').innerHTML = data.content;
                        document.getElementById('page-info').innerText = (idx + 1) + " / " + data.total;
                        
                        currentIdx = idx;
                        window.scrollTo(0, 0); 
                    } catch(e) {
                        document.getElementById('chapter-text').innerHTML = "<p style='color:red'>网络错误，请重试</p>";
                    } finally {
                        showLoading(false);
                    }
                }

                function prevChapter() { loadChapter(currentIdx - 1); }
                function nextChapter() { loadChapter(currentIdx + 1); }
                function showLoading(show) { document.getElementById('loading').style.display = show ? 'block' : 'none'; }
                function msg(t) { alert(t); }

                document.addEventListener('keydown', function(event) {
                    if (event.keyCode === 37) prevChapter(); 
                    if (event.keyCode === 39) nextChapter(); 
                });
            </script>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def serve_chapter_data(self, spider, query):
        try:
            bid = query.get('bid', [''])[0]
            idx = int(query.get('idx', ['0'])[0])
            chapter_list = spider.book_cache.get(bid, [])
            
            if not chapter_list or idx < 0 or idx >= len(chapter_list):
                self.send_json({'code': 400, 'msg': '章节不存在'})
                return

            current = chapter_list[idx]
            content = spider.fetch_chapter_text(bid, current['cid'])
            
            self.send_json({
                'code': 200,
                'title': current['title'],
                'content': content,
                'total': len(chapter_list)
            })
        except Exception as e:
            self.send_json({'code': 500, 'msg': str(e)})

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def log_message(self, format, *args): pass

# ==================== 2. 爬虫主体 ====================

class BaseSpider:
    def init(self, extend=""): pass
    def getName(self): pass
    def getDependence(self): return []
    def isVideoFormat(self, url): pass
    def manualVideoCheck(self): pass
    def homeContent(self, filter): pass
    def homeVideoContent(self): pass
    def categoryContent(self, tid, pg, filter, extend): pass
    def detailContent(self, ids): pass
    def searchContent(self, key, quick): pass
    def playerContent(self, flag, id, vipFlags): pass
    def localProxy(self, params): pass
    def destroy(self): pass

class Spider(BaseSpider):
    server = None
    server_port = 0
    book_cache = {} 
    last_auto_open = {"bid": None, "t": 0}

    def getName(self): return "阅读助手(羊皮纸)"
    def init(self, extend=""): 
        try: self._start_server()
        except: pass
    def destroy(self):
        if self.server:
            self.server.shutdown()
            self.server = None
    def getDependence(self): return []
    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): pass

    def _start_server(self):
        if self.server: return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('127.0.0.1', 0))
            self.server_port = sock.getsockname()[1]
            sock.close()
            self.server = ThreadedHTTPServer(('127.0.0.1', self.server_port), NovelHandler)
            self.server.spider = self
            t = threading.Thread(target=self.server.serve_forever)
            t.daemon = True
            t.start()
        except: pass

    # API
    AES_KEY = b'242ccb8230d709e1'
    SIGN_KEY = "d3dGiJc651gSQ8w1"
    APP_ID = "com.kmxs.reader"
    BASE_HEADERS = {"app-version": "51110","platform": "android","reg": "0","AUTHORIZATION": "","application-id": APP_ID, "net-env": "1","channel": "unknown","qm-params": ""}

    def get_sign(self, params):
        sorted_keys = sorted(params.keys())
        sign_str = "".join([f"{k}={params[k]}" for k in sorted_keys]) + self.SIGN_KEY
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    def get_headers(self):
        headers = self.BASE_HEADERS.copy()
        headers['sign'] = self.get_sign(headers)
        headers["User-Agent"] = "okhttp/3.12.1"
        return headers

    def decrypt_content(self, base64_content):
        try:
            encrypted_bytes = base64.b64decode(base64_content)
            cipher = AES.new(self.AES_KEY, AES.MODE_CBC, encrypted_bytes[:16])
            decrypted = cipher.decrypt(encrypted_bytes[16:])
            try: return unpad(decrypted, AES.block_size).decode('utf-8')
            except: return decrypted.decode('utf-8', 'ignore').strip()
        except: return "解密失败"

    def get_api_url(self, path, params, domain_type="bc"):
        params['sign'] = self.get_sign(params)
        base_url = "https://api-bc.wtzw.com" if domain_type == "bc" else "https://api-ks.wtzw.com"
        if "search" in path: base_url = "https://api-bc.wtzw.com"
        return f"{base_url}{path}", params

    def fetch_chapter_text(self, bid, cid):
        try:
            params = {'id': bid, 'chapterId': cid}
            url, signed = self.get_api_url("/api/v1/chapter/content", params, "ks")
            r = requests.get(url, params=signed, headers=self.get_headers(), timeout=5)
            j = r.json()
            if 'data' in j and 'content' in j['data']:
                raw = self.decrypt_content(j['data']['content'])
                return "".join([f"<p>{line}</p>" for line in raw.split('\n') if line.strip()])
            return f"<p style='color:red'>{j.get('msg', '无法读取')}</p>"
        except Exception as e: return f"<p style='color:red'>{str(e)}</p>"

    # 业务
    def homeContent(self, filter):
        cats = [("玄幻奇幻", "1|202"), ("都市人生", "1|203"), ("武侠仙侠", "1|205"), ("历史军事", "1|56"), ("科幻末世", "1|64"), ("游戏竞技", "1|75"), ("现代言情", "2|1"), ("古代言情", "2|2"), ("幻想言情", "2|4"), ("婚恋情感", "2|6"), ("悬疑推理", "3|262")]
        return {'class': [{"type_name": n, "type_id": i} for n, i in cats], 'filters': {}}
    def homeVideoContent(self): return {'list': []}
    def categoryContent(self, tid, pg, filter, extend):
        try: gender, cat_id = tid.split("|")
        except: gender, cat_id = "1", "202"
        params = {'gender': gender, 'category_id': cat_id, 'need_filters': '1', 'page': pg, 'need_category': '1'}
        url, signed = self.get_api_url("/api/v4/category/get-list", params, "bc")
        try:
            j = requests.get(url, params=signed, headers=self.get_headers()).json()
            videos = []
            for b in (j.get('data', {}).get('books', []) or j.get('books', [])):
                videos.append({"vod_id": str(b.get('id')), "vod_name": b.get('title'), "vod_pic": b.get('image_link'), "vod_remarks": b.get('author')})
            return {'list': videos, 'page': pg, 'pagecount': 999, 'limit': 20, 'total': 9999}
        except: return {'list': []}

    def detailContent(self, ids):
        bid = ids[0]
        params = {'id': bid, 'imei_ip': '2937357107', 'teeny_mode': '0'}
        url, signed = self.get_api_url("/api/v4/book/detail", params, "bc")
        vod = {"vod_id": bid, "vod_name": "加载中", "vod_play_from": "阅读助手"}
        try:
            j = requests.get(url, params=signed, headers=self.get_headers()).json()
            if 'data' in j and 'book' in j['data']:
                info = j['data']['book']
                vod.update({"vod_name": info.get('title'), "vod_pic": info.get('image_link'), "type_name": info.get('category_name'), "vod_remarks": f"{info.get('words_num', '')}字", "vod_content": info.get('intro')})
            
            c_params = {'id': bid}
            c_url, c_signed = self.get_api_url("/api/v1/chapter/chapter-list", c_params, "ks")
            c_j = requests.get(c_url, params=c_signed, headers=self.get_headers()).json()
            
            chapters = []
            display = []
            for idx, item in enumerate(c_j.get('data', {}).get('chapter_lists', [])):
                chapters.append({'cid': str(item['id']), 'title': item['title']})
                display.append(f"{item['title'].replace('$','')}${bid}@@{idx}")
            
            self.book_cache[bid] = chapters
            # ====== 最小修改：进入详情页即自动打开阅读器（第一章） ======
            try:
                now = time.time()
                # 只有当该书未在最近3秒内触发过，才自动弹窗，防止重复
                if self.last_auto_open.get("bid") != bid or (now - self.last_auto_open.get("t", 0)) > 3:
                    self.last_auto_open = {"bid": bid, "t": now}
                    # 启动弹窗打开第0章
                    threading.Thread(target=self._show_popup_dialog, args=(bid, "0")).start()
            except:
                pass
            # ============================================================
            
            
            
            
            vod['vod_play_url'] = "#".join(display)
            return {"list": [vod]}
        except Exception as e:
            vod["vod_content"] = f"Error: {e}"
            return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        params = {'gender': '3', 'imei_ip': '2937357107', 'page': pg, 'wd': key}
        url, signed = self.get_api_url("/api/v5/search/words", params, "bc")
        try:
            j = requests.get(url, params=signed, headers=self.get_headers()).json()
            videos = []
            for b in j.get('data', {}).get('books', []):
                videos.append({"vod_id": str(b.get('id')), "vod_name": b.get('original_title'), "vod_pic": b.get('image_link'), "vod_remarks": b.get('original_author')})
            return {'list': videos, 'page': pg}
        except: return {'list': [], 'page': pg}

    def playerContent(self, flag, id, vipFlags):
        # 启动弹窗
        threading.Thread(target=self._show_popup_dialog, args=(id.split("@@")[0], id.split("@@")[1])).start()
        return {'parse': 0, 'playUrl': '', 'url': 'http://127.0.0.1/dummy', 'header': ''}

    # ================= 弹窗逻辑 =================
    def _show_popup_dialog(self, bid, index):
        def launch():
            try:
                from java import jclass, dynamic_proxy
                from java.lang import Runnable
                JClass = jclass("java.lang.Class")
                AT = JClass.forName("android.app.ActivityThread")
                currentAT = AT.getMethod("currentActivityThread").invoke(None)
                mActivities = AT.getDeclaredField("mActivities")
                mActivities.setAccessible(True)
                values = mActivities.get(currentAT).values()
                try: records = values.toArray()
                except: records = values.getClass().getMethod("toArray").invoke(values)
                act = None
                for r in records:
                    try:
                        rClass = r.getClass()
                        activityField = rClass.getDeclaredField("activity")
                        activityField.setAccessible(True)
                        temp_act = activityField.get(r)
                        if temp_act and not temp_act.isFinishing() and not temp_act.isDestroyed():
                            act = temp_act
                            break
                    except: continue
                if not act: return

                class UiRunner(dynamic_proxy(Runnable)):
                    def __init__(self, func): super().__init__(); self.func = func
                    def run(self):
                        try: self.func()
                        except: pass

                def show():
                    try:
                        Dialog = jclass("android.app.Dialog")
                        WebView = jclass("android.webkit.WebView")
                        ColorDrawable = jclass("android.graphics.drawable.ColorDrawable")
                        Color = jclass("android.graphics.Color")
                        
                        d = Dialog(act)
                        d.requestWindowFeature(1)
                        win = d.getWindow()
                        if win:
                            win.getDecorView().setPadding(0,0,0,0)
                            # 【修改点3】将弹窗底色改为羊皮纸色，防止加载时闪黑屏
                            win.setBackgroundDrawable(ColorDrawable(Color.parseColor("#f8f1e3")))
                            win.setLayout(-1, -1)
                        
                        w = WebView(act)
                        ws = w.getSettings()
                        ws.setJavaScriptEnabled(True)
                        ws.setDomStorageEnabled(True)
                        ws.setSupportZoom(True)
                        ws.setBuiltInZoomControls(True)
                        ws.setDisplayZoomControls(False)
                        ws.setUseWideViewPort(True)
                        ws.setLoadWithOverviewMode(True)
                        
                        # 【修改点4】WebView 背景色同步改为羊皮纸色
                        w.setBackgroundColor(Color.parseColor("#f8f1e3"))
                        w.loadUrl(f"http://127.0.0.1:{self.server_port}/read.html?bid={bid}&idx={index}")
                        
                        d.setContentView(w)
                        d.show()
                    except: pass

                act.runOnUiThread(UiRunner(show))
            except: pass
        threading.Thread(target=launch).start()

    def localProxy(self, params): pass
