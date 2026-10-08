import re
import json
import requests
import weakref
import threading
from base.spider import Spider
from urllib3 import disable_warnings

disable_warnings()

class Spider(Spider):
    host = "https://8se.me"
    IS_WEB_SHOWING = False
    
    header = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Referer": "https://8se.me/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    def getName(self):
        return "XChina套图修复版"

    def init(self, extend=""):
        self.cached_activity = self._activity()
        self._handler = None
        self._web_ref = self._decor_ref = self._wrapper_ref = None
        self._cmd_cb = None
        self._image_list = []
        self._current_image_index = 0

    def homeContent(self, filter):
        classes = [
            {"type_id": "series-66600a3a227ee", "type_name": "私购流出"},
            {"type_id": "series-64be224b662c0", "type_name": "港模套图"},
            {"type_id": "series-5f1476781eab4", "type_name": "秀人网"},
            {"type_id": "series-64be21c972ca4", "type_name": "国模套图"},
            {"type_id": "series-6660093348354", "type_name": "秀人套图"},
            {"type_id": "series-665f66f97ec4d", "type_name": "街拍AI"}
        ]
        return {"class": classes, "filters": {}, "list": []}

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.host}/photos/{tid}/{pg}.html"
        try:
            res = requests.get(url, headers=self.header, verify=False, timeout=10)
            res.encoding = 'utf-8'
            html = res.text
            
            vod_list = []
            items = re.findall(r'class="item photo".*?href="/photo/id-([^"]+)\.html".*?title="([^"]+)"', html, re.S)
            
            for mid, name in items:
                pic = ""
                img_style = re.search(rf'id-{mid}\.html".*?style="[^"]*background-image:url\([\'"]([^\'"]+)[\'"]\)', html, re.S)
                if img_style:
                    pic = img_style.group(1)
                
                if not pic:
                    img_attr = re.search(rf'id-{mid}\.html".*?(?:data-original|src)="([^"]+)"', html, re.S)
                    if img_attr:
                        pic = img_attr.group(1)
                
                if pic:
                    if pic.startswith("//"):
                        pic = "https:" + pic
                    pic = f"{pic}@Referer=https://8se.me/&User-Agent=Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                
                action_data = json.dumps({
                    "action": "view_album",
                    "mid": mid
                }, ensure_ascii=False)

                vod_list.append({
                    "vod_id": mid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": "高清套图",
                    "action": action_data,
                    "style": {"type": "rect", "ratio": 1.0}
                })
            
            return {
                "page": int(pg),
                "pagecount": 99,
                "limit": 20,
                "total": 999,
                "list": vod_list
            }
        except Exception as e:
            return {"list": []}

    def detailContent(self, ids):
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        return {}

    def searchContent(self, key, quick, pg="1"):
        return {"list": []}

    def action(self, action_str):
        try:
            data = json.loads(action_str) if action_str else {}
            if data.get("action") == "view_album":
                mid = data.get("mid", "")
                if mid:
                    self._show_toast("正在解析套图...")
                    def _async_load():
                        img_list = self._get_album_images(mid)
                        if img_list:
                            self._start_image_viewer(img_list, 0)
                        else:
                            self._show_toast("获取图片链接失败")
                    
                    threading.Thread(target=_async_load, daemon=True).start()
            return {}
        except Exception as e:
            print("action 错误:", e)
            return {}

    def _show_toast(self, msg):
        try:
            act = self.cached_activity or self._activity()
            if act:
                from java import jclass, dynamic_proxy
                from java.lang import Runnable
                Toast = jclass("android.widget.Toast")
                class _ToastRunnable(dynamic_proxy(Runnable)):
                    def run(s):
                        try:
                            Toast.makeText(act, msg, Toast.LENGTH_SHORT).show()
                        except:
                            pass
                act.runOnUiThread(_ToastRunnable())
        except:
            pass

    def _get_album_images(self, mid):
        try:
            detail_url = f"{self.host}/photo/id-{mid}.html"
            res = requests.get(detail_url, headers=self.header, verify=False, timeout=10)
            
            show_id = re.search(r'photoShow\.html\?id=([^"]+)', res.text)
            if not show_id: return []
            
            show_url = f"{self.host}/photoShow.html?id={show_id.group(1)}"
            res_show = requests.get(show_url, headers=self.header, verify=False, timeout=10)
            show_html = res_show.text
            
            total_info = re.search(r'\(1/(\d+)\)', show_html)
            img_info = re.search(r'src="((?:https?:)?//[^"]+/(\d+)\.jpg)"', show_html)
            
            if total_info and img_info:
                total = int(total_info.group(1))
                first_url = img_info.group(1)
                if first_url.startswith("//"):
                    first_url = "https:" + first_url
                prefix_num = img_info.group(2)
                base_url = first_url.replace(f"{prefix_num}.jpg", "")
                return [f"{base_url}{str(i).zfill(len(prefix_num))}.jpg" for i in range(1, total + 1)]
            return []
        except Exception as e:
            print("解析图集链接失败:", e)
            return []

    def _close_image_viewer(self):
        try:
            if self._handler:
                self._handler.removeCallbacksAndMessages(None)
            decor = self._decor_ref[0] if self._decor_ref else None
            wrapper = self._wrapper_ref[0] if self._wrapper_ref else None
            act = self.cached_activity or self._activity()
            
            if decor:
                try:
                    from android.view import View
                    decor.setSystemUiVisibility(View.SYSTEM_UI_FLAG_VISIBLE)
                except:
                    pass
                    
            if act and wrapper:
                from java import dynamic_proxy
                from java.lang import Runnable
                wr = wrapper
                class _RemoveView(dynamic_proxy(Runnable)):
                    def run(_):
                        try:
                            parent = wr.getParent()
                            if parent:
                                parent.removeView(wr)
                        except:
                            pass
                act.runOnUiThread(_RemoveView())
                
            self._web_ref = None
            self._decor_ref = None
            self._wrapper_ref = None
            self._cmd_cb = None
            self._image_list = []
        except Exception as e:
            print("关闭图片查看器错误:", e)
        finally:
            self.IS_WEB_SHOWING = False

    def _goto_image(self, index):
        if 0 <= index < len(self._image_list):
            self._current_image_index = index
            self._update_image_display()

    def _prev_image(self):
        if hasattr(self, "_image_list") and self._image_list:
            self._current_image_index = (self._current_image_index - 1) % len(self._image_list)
            self._update_image_display()

    def _next_image(self):
        if hasattr(self, "_image_list") and self._image_list:
            self._current_image_index = (self._current_image_index + 1) % len(self._image_list)
            self._update_image_display()

    def _update_image_display(self):
        try:
            if not (self._web_ref and self._web_ref[0]):
                return
            idx = self._current_image_index
            js = "showImage(" + str(idx) + ");"
            self._web_ref[0].evaluateJavascript(js, None)
        except Exception as e:
            print("更新图片显示错误:", e)

    def _start_image_viewer(self, images, current_index):
        if self.IS_WEB_SHOWING:
            return
        
        act = self.cached_activity or self._activity()
        if not act:
            self._show_toast("无法获取当前 Activity")
            return

        self.IS_WEB_SHOWING = True
        self._image_list = images
        self._current_image_index = current_index
        
        spider_ref = weakref.ref(self)
        html = self._image_viewer_html(images, current_index)

        from java import jclass, dynamic_proxy
        from java.lang import Runnable

        class _CreateWebView(dynamic_proxy(Runnable)):
            def run(s):
                try:
                    sp = spider_ref()
                    if not sp: return

                    WebView = jclass("android.webkit.WebView")
                    WebViewClient = jclass("android.webkit.WebViewClient")
                    FrameLayout = jclass("android.widget.FrameLayout")
                    Color = jclass("android.graphics.Color")
                    View = jclass("android.view.View")
                    ValueCallback = jclass("android.webkit.ValueCallback")
                    Handler = jclass("android.os.Handler")

                    handler = Handler(act.getMainLooper())
                    sp._handler = handler
                    handler_ref = weakref.ref(handler)

                    dv = act.getWindow().getDecorView()
                    try:
                        dv.setSystemUiVisibility(
                            View.SYSTEM_UI_FLAG_LAYOUT_STABLE |
                            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |
                            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN |
                            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
                            View.SYSTEM_UI_FLAG_FULLSCREEN |
                            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        )
                    except:
                        pass

                    wrapper = FrameLayout(act)
                    web = WebView(act)
                    web.setBackgroundColor(Color.BLACK)

                    # 开启 HTTP 缓存与 DOM 存储，加速二次加载
                    settings = web.getSettings()
                    settings.setJavaScriptEnabled(True)
                    settings.setDomStorageEnabled(True)
                    settings.setAllowFileAccess(True)
                    settings.setAllowContentAccess(True)
                    settings.setCacheMode(-1)  # LOAD_DEFAULT 开启默认缓存
                    settings.setUserAgentString("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

                    try:
                        settings.setMixedContentMode(0)
                    except:
                        pass

                    try:
                        class _SSLWebViewClient(dynamic_proxy(WebViewClient)):
                            def onReceivedSslError(ss, view, handler_ssl, error):
                                try:
                                    handler_ssl.proceed()
                                except:
                                    pass
                        web.setWebViewClient(_SSLWebViewClient())
                    except:
                        web.setWebViewClient(WebViewClient())

                    web.loadDataWithBaseURL("https://8se.me/", html, "text/html", "utf-8", None)

                    mp = FrameLayout.LayoutParams.MATCH_PARENT
                    wrapper.addView(web, FrameLayout.LayoutParams(mp, mp))

                    act.addContentView(wrapper, FrameLayout.LayoutParams(mp, mp))
                    wrapper.bringToFront()
                    web.requestFocus()

                    web_ref = [web]
                    decor_ref = [dv]
                    wrapper_ref = [wrapper]

                    sp._web_ref = web_ref
                    sp._decor_ref = decor_ref
                    sp._wrapper_ref = wrapper_ref

                    class _CommandCallback(dynamic_proxy(ValueCallback)):
                        def onReceiveValue(ss, value):
                            try:
                                sp_inner = spider_ref()
                                w = web_ref[0] if web_ref else None
                                if not (sp_inner and sp_inner.IS_WEB_SHOWING and w):
                                    return
                                v = str(value).strip('"\'') if value else ""
                                if v and v not in ["null", "None", "undefined"]:
                                    w.evaluateJavascript("window.APP_COMMAND=null;", None)
                                    if v == "close_viewer":
                                        sp_inner._close_image_viewer()
                                    elif v.startswith("goto_"):
                                        idx = int(v.split("_")[1])
                                        sp_inner._goto_image(idx)
                                    elif v == "prev":
                                        sp_inner._prev_image()
                                    elif v == "next":
                                        sp_inner._next_image()
                            except Exception as e:
                                print("命令回调错误:", e)

                            try:
                                sp_inner = spider_ref()
                                h_inner = handler_ref()
                                w = web_ref[0] if web_ref else None
                                if sp_inner and sp_inner.IS_WEB_SHOWING and h_inner and w:
                                    class _PollRunnable(dynamic_proxy(Runnable)):
                                        def run(_):
                                            try:
                                                w2 = web_ref[0] if web_ref else None
                                                if w2:
                                                    w2.evaluateJavascript("window.APP_COMMAND", ss)
                                            except:
                                                pass
                                    h_inner.postDelayed(_PollRunnable(), 300)
                            except:
                                pass

                    cb = _CommandCallback()
                    sp._cmd_cb = cb

                    class _StartPoll(dynamic_proxy(Runnable)):
                        def run(_):
                            try:
                                w = web_ref[0]
                                if w:
                                    w.evaluateJavascript("window.APP_COMMAND", cb)
                            except:
                                pass

                    handler.postDelayed(_StartPoll(), 300)

                except Exception as e:
                    print("创建WebView错误:", e)
                    sp = spider_ref()
                    if sp:
                        sp.IS_WEB_SHOWING = False

        act.runOnUiThread(_CreateWebView())

    def _image_viewer_html(self, images, current_index):
        img_json = json.dumps(images, ensure_ascii=False)
        return """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,user-scalable=no">
<meta name="referrer" content="always">
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{background:#000;width:100%;height:100%;overflow:hidden;position:relative;font-family:system-ui,-apple-system,sans-serif}
#top-bar{position:absolute;top:0;left:0;right:0;height:50px;background:rgba(0,0,0,0.75);display:flex;align-items:center;justify-content:space-between;padding:0 15px;z-index:100;color:#fff;font-size:14px}
#info{display:flex;gap:15px;align-items:center}
#resolution{color:#4af626;font-family:monospace;font-size:13px}
#counter{color:#fff;opacity:0.9}
#close-btn{width:36px;height:36px;border-radius:18px;background:rgba(255,255,255,0.2);color:#fff;font-size:20px;border:none;display:flex;align-items:center;justify-content:center}
#close-btn:active{background:rgba(255,255,255,0.4)}
#image-container{position:absolute;top:50px;bottom:60px;left:0;right:0;z-index:1;overflow:hidden}
#image-wrapper{width:100%;height:100%;overflow:hidden;display:flex;align-items:center;justify-content:center;touch-action:none;position:relative}

/* 占位低清图：0毫秒显示，高斯模糊 */
#placeholder-image{position:absolute;width:100%;height:100%;object-fit:contain;filter:blur(10px);transform:scale(1.05);opacity:0.8;transition:opacity 0.2s ease-out;pointer-events:none}

/* 原图：加载完成后平滑淡入 */
#main-image{position:absolute;display:none;transform-origin:center center;max-width:none;max-height:none;pointer-events:none;-webkit-user-select:none;user-select:none;will-change:transform}

#bottom-bar{position:absolute;bottom:0;left:0;right:0;height:60px;background:rgba(0,0,0,0.85);z-index:100;overflow-x:auto;overflow-y:hidden;white-space:nowrap;-webkit-overflow-scrolling:touch}
#thumb-container{display:flex;align-items:center;height:100%;padding:0 10px;gap:10px}
.thumb{width:44px;height:44px;object-fit:cover;border-radius:6px;border:2px solid rgba(255,255,255,0.2);opacity:0.65;flex-shrink:0;background:#1a1a1a;transition:opacity 0.15s,border-color 0.15s}
.thumb.active{border-color:#fff;opacity:1;box-shadow:0 0 8px rgba(255,255,255,0.3)}
.thumb.pressed{opacity:0.8; border-color:#aaa}
#loading{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#fff;font-size:14px;background:rgba(0,0,0,0.6);padding:6px 12px;border-radius:12px;z-index:50;display:none}
#zoom-hint{position:absolute;top:60px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,0.7);color:#fff;padding:8px 16px;border-radius:20px;font-size:12px;opacity:0;transition:opacity 0.3s;z-index:150;pointer-events:none}
</style>
</head>
<body>
<div id="top-bar"><div id="info"><span id="resolution">加载中...</span><span id="counter">0/0</span></div><button id="close-btn">✕</button></div>
<div id="zoom-hint">双击放大 · 双指缩放 · 点击关闭</div>
<div id="image-container">
    <div id="image-wrapper">
        <img id="placeholder-image" src="" style="display:none">
        <img id="main-image" style="display:none">
    </div>
    <div id="loading">加载高清原图...</div>
</div>
<div id="bottom-bar"><div id="thumb-container"></div></div>
<script>
var images=""" + img_json + """;var currentIndex=""" + str(current_index) + """;
var imgObj=document.getElementById("main-image");
var placeholderObj=document.getElementById("placeholder-image");
var wrapper=document.getElementById("image-wrapper");
var resSpan=document.getElementById("resolution");
var counterSpan=document.getElementById("counter");
var loadingDiv=document.getElementById("loading");
var thumbContainer=document.getElementById("thumb-container");
var zoomHint=document.getElementById("zoom-hint");
var closeBtn=document.getElementById("close-btn");
window.APP_COMMAND=null;

var preloadedCache={};
var baseScale=1,userScale=1,rotate=0;
var minScale=0.5,maxScale=5;
var panX=0,panY=0;
var isScaling=false;
var startDist=0;
var startX=0,startY=0;
var lastPanX=0,lastPanY=0;
var hasMoved=false;
var lastTapTime=0;
var tapTimeout=null;

function init(){
    renderAllThumbs();
    showImage(currentIndex);
    setupGestures();
    setTimeout(function(){
        zoomHint.style.opacity='1';
        setTimeout(function(){zoomHint.style.opacity='0'},2500)
    },500)
}

function renderAllThumbs(){
    thumbContainer.innerHTML='';
    for(var i=0; i<images.length; i++){
        var t = document.createElement('img');
        t.className = 'thumb' + (i === currentIndex ? ' active' : '');
        t.dataset.index = i;
        t.src = images[i];

        t.addEventListener('click', function(e){
            e.preventDefault();
            showImage(parseInt(this.dataset.index));
        });

        t.onerror = function(){ this.style.background='#333'; };
        thumbContainer.appendChild(t);
    }
}

// 激进预加载：自动静默加载前后各 3 张图
function preloadAdjacent(idx){
    var range = 3;
    for(var i = idx - range; i <= idx + range; i++){
        if(i >= 0 && i < images.length && !preloadedCache[images[i]]){
            var pImg = new Image();
            pImg.src = images[i];
            preloadedCache[images[i]] = true;
        }
    }
}

function showImage(idx){
    if(idx < 0 || idx >= images.length) return;
    currentIndex = idx;
    userScale = 1; panX = 0; panY = 0; rotate = 0;
    
    var targetUrl = images[idx];

    // 1. 0毫秒先展示模糊占位图，提升视听响应
    placeholderObj.src = targetUrl;
    placeholderObj.style.display = 'block';
    placeholderObj.style.opacity = '0.8';

    loadingDiv.style.display = 'block';
    resSpan.textContent = "加载中...";
    counterSpan.textContent = "图片: " + (currentIndex + 1) + '/' + images.length;
    
    // 立即触发前后 3 张静默预加载
    preloadAdjacent(currentIndex);
    updateActiveThumb();

    // 2. 加载高清原图
    var tempImg = new Image();
    tempImg.onload = function(){
        imgObj.src = targetUrl;
        loadingDiv.style.display = 'none';
        
        // 隐去占位图，显示原图
        placeholderObj.style.opacity = '0';
        setTimeout(function(){ placeholderObj.style.display = 'none'; }, 200);

        imgObj.style.display = 'block';
        
        var w = tempImg.naturalWidth;
        var h = tempImg.naturalHeight;
        resSpan.textContent = w + '×' + h;
        
        var containerW = wrapper.clientWidth || window.innerWidth;
        var containerH = wrapper.clientHeight || window.innerHeight;
        
        if(w > h){
            rotate = 90;
            var rotatedW = h;
            var rotatedH = w;
            baseScale = Math.min(containerW / rotatedW, containerH / rotatedH, 1);
        } else {
            rotate = 0;
            baseScale = Math.min(containerW / w, containerH / h, 1);
        }
        userScale = 1; panX = 0; panY = 0;
        updateTransform();
    };

    tempImg.onerror = function(){
        loadingDiv.textContent = '图片加载失败';
    };

    tempImg.src = targetUrl;
}

function updateTransform(){
    var containerW = wrapper.clientWidth || window.innerWidth;
    var containerH = wrapper.clientHeight || window.innerHeight;
    var w = imgObj.naturalWidth || 1;
    var h = imgObj.naturalHeight || 1;
    var finalScale = baseScale * userScale;
    var renderW = (rotate === 90 ? h : w) * finalScale;
    var renderH = (rotate === 90 ? w : h) * finalScale;
    var maxX = Math.max(0, (renderW - containerW) / 2);
    var maxY = Math.max(0, (renderH - containerH) / 2);
    panX = Math.max(-maxX, Math.min(maxX, panX));
    panY = Math.max(-maxY, Math.min(maxY, panY));
    var transform = 'translate(' + panX + 'px, ' + panY + 'px) scale(' + finalScale + ')';
    if(rotate !== 0){ transform += ' rotate(' + rotate + 'deg)'; }
    imgObj.style.transform = transform;
}

function updateActiveThumb(){
    var thumbs = thumbContainer.querySelectorAll('.thumb');
    for(var i=0; i<thumbs.length; i++){
        thumbs[i].className = 'thumb' + (i === currentIndex ? ' active' : '');
    }
    var activeThumb = thumbContainer.querySelector('.thumb.active');
    if(activeThumb){
        var thumbLeft = activeThumb.offsetLeft;
        var thumbWidth = activeThumb.offsetWidth;
        var containerWidth = thumbContainer.parentElement.clientWidth;
        var scrollLeft = thumbLeft - (containerWidth / 2) + (thumbWidth / 2);
        thumbContainer.parentElement.scrollTo({left: Math.max(0, scrollLeft), behavior: 'smooth'});
    }
}

function setupGestures(){
    wrapper.addEventListener('touchstart', function(e){
        if(e.touches.length === 2){
            isScaling = true;
            startDist = getTouchDistance(e.touches);
            e.preventDefault();
        } else if(e.touches.length === 1){
            isScaling = false;
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            lastPanX = panX;
            lastPanY = panY;
            hasMoved = false;
        }
    }, {passive:false});

    wrapper.addEventListener('touchmove', function(e){
        if(e.touches.length === 2 && isScaling){
            e.preventDefault();
            var dist = getTouchDistance(e.touches);
            if(startDist > 0){
                var scaleDelta = dist / startDist;
                userScale = Math.max(minScale, Math.min(maxScale, userScale * scaleDelta));
                updateTransform();
            }
            startDist = dist;
        } else if(e.touches.length === 1){
            var dx = e.touches[0].clientX - startX;
            var dy = e.touches[0].clientY - startY;
            if(Math.abs(dx) > 5 || Math.abs(dy) > 5){ hasMoved = true; }
            if(userScale > 1){
                e.preventDefault();
                panX = lastPanX + dx;
                panY = lastPanY + dy;
                updateTransform();
            }
        }
    }, {passive:false});

    wrapper.addEventListener('touchend', function(e){
        if(isScaling && e.touches.length < 2){
            isScaling = false;
            startDist = 0;
            return;
        }
        if(userScale === 1 && hasMoved && e.changedTouches.length === 1){
            var dx = e.changedTouches[0].clientX - startX;
            if(Math.abs(dx) > 40){
                if(dx < 0) nextImage();
                else prevImage();
                return;
            }
        }
        if(e.changedTouches.length === 1 && !isScaling && !hasMoved){
            handleTap(e.changedTouches[0].clientX, e.changedTouches[0].clientY);
        }
    }, {passive:true});

    closeBtn.addEventListener('click', function(e){
        e.preventDefault();
        closeViewer();
    });
}

function handleTap(x, y){
    var now = Date.now();
    var wrapperW = wrapper.clientWidth;
    if(now - lastTapTime < 300){
        if(tapTimeout) clearTimeout(tapTimeout);
        if(userScale > 1.05){ userScale = 1; panX = 0; panY = 0; }
        else { userScale = 2.5; panX = 0; panY = 0; }
        updateTransform();
        lastTapTime = 0;
    } else {
        lastTapTime = now;
        tapTimeout = setTimeout(function(){
            if(userScale > 1.05) return;
            if(x < wrapperW / 2){ prevImage(); }
            else { nextImage(); }
        }, 300);
    }
}

function getTouchDistance(touches){
    var dx = touches[0].clientX - touches[1].clientX;
    var dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
}

function prevImage(){
    var idx = currentIndex - 1;
    if(idx < 0) idx = images.length - 1;
    showImage(idx);
}

function nextImage(){
    var idx = currentIndex + 1;
    if(idx >= images.length) idx = 0;
    showImage(idx);
}

function closeViewer(){
    window.APP_COMMAND = 'close_viewer';
}

document.addEventListener('DOMContentLoaded', init);
</script></body></html>"""

    def _activity(self):
        try:
            from java import jclass
            AT = jclass("java.lang.Class").forName("android.app.ActivityThread")
            cur = AT.getMethod("currentActivityThread").invoke(None)
            f = AT.getDeclaredField("mActivities")
            f.setAccessible(True)
            map_obj = f.get(cur)
            values = map_obj.values().toArray() if hasattr(map_obj, "values") else map_obj.toArray()
            for r in values:
                rc = r.getClass()
                pf = rc.getDeclaredField("paused")
                pf.setAccessible(True)
                if not pf.getBoolean(r):
                    af = rc.getDeclaredField("activity")
                    af.setAccessible(True)
                    act = af.get(r)
                    if act:
                        return act
        except:
            pass
        return None
