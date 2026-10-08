# -*- coding: utf-8 -*-
import sys, os, json, time, threading, re, urllib.request, urllib.parse, http.cookiejar, traceback, base64, codecs, ssl

try:
    from java import jclass, dynamic_proxy
except ImportError:
    jclass = None
    dynamic_proxy = None

try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object

try:
    import requests
except Exception:
    requests = None

CONFIG = {}
_LOG_BUF = []
_LOG_MAX = 300

# CF cookie 缓存目录（按域名存 json）
CF_COOKIE_DIR = '/storage/emulated/0/tmp/123'

HOST = 'https://supjav.com'
LK_BASE = 'https://lk1.supremejav.com/supjav.php'

UA_DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
UA_MOBILE  = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

CATS = [
    ('__tools', '工具'),   # CF验证 / 日志
    ('__home', '最新'),
    ('__popular', '热门'),
    ('censored-jav', '有码 Censored'),
    ('uncensored-jav', '无码 Uncensored'),
    ('amateur', '素人 Amateur'),
    ('chinese-subtitles', '中文字幕 Chn Sub'),
    ('reducing-mosaic', '破解 Reducing Mosaic'),
    ('english-subtitles', '英文字幕 Eng Sub'),
]

SORTS = [
    {'key': 'sort', 'name': '排序',
     'value': [{'n': '最新', 'v': ''}, {'n': '最多观看', 'v': 'views'}]},
]

# ---------- 动态代理类辅助 ----------
_dialog_proxy_classes = {}

def _ensure_dialog_proxy_classes():
    if _dialog_proxy_classes:
        return _dialog_proxy_classes
    Runnable = jclass("java.lang.Runnable")
    DialogInterface = jclass("android.content.DialogInterface")

    class _RunProxy(dynamic_proxy(Runnable)):
        def run(self):
            fn = getattr(self, "_fn", None)
            if fn is not None:
                try:
                    fn()
                except Exception:
                    pass

    class _ClickProxy(dynamic_proxy(DialogInterface.OnClickListener)):
        def onClick(self, dialog, which):
            fn = getattr(self, "_fn", None)
            if fn is not None:
                try:
                    fn(dialog, which)
                except Exception:
                    pass

    _dialog_proxy_classes["run"] = _RunProxy
    _dialog_proxy_classes["click"] = _ClickProxy
    return _dialog_proxy_classes


def dp2px(act, dp):
    TypedValue = jclass("android.util.TypedValue")
    metrics = act.getResources().getDisplayMetrics()
    return int(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, float(dp), metrics))


class MiniDialog(object):
    def __init__(self, spider=None, config=None):
        cfg = config or {}
        self.spider = spider
        self.width_ratio = float(cfg.get("width_ratio", 0.88))
        self.max_refs = int(cfg.get("max_refs", 60))
        self._refs = []

    def log(self, msg):
        try:
            if self.spider is not None and hasattr(self.spider, "_log"):
                self.spider._log(msg)
                return
        except Exception:
            pass

    def _activity(self):
        try:
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
                    a = af.get(r)
                    if a:
                        return a
        except Exception:
            pass
        return None

    def available(self):
        return not (jclass is None or dynamic_proxy is None)

    def _keep(self, *objs):
        self._refs.extend([o for o in objs if o is not None])
        if len(self._refs) > self.max_refs:
            self._refs = self._refs[-self.max_refs:]

    def run_on_ui(self, ui_fn):
        if not self.available():
            return False
        act = self._activity()
        if not act:
            return False
        p = _ensure_dialog_proxy_classes()

        def _make():
            r = p["run"]()
            r._fn = lambda: ui_fn(act)
            return r

        try:
            r = _make()
            act.getWindow().getDecorView().post(r)
            self._keep(r)
        except Exception:
            Handler = jclass("android.os.Handler")
            Looper = jclass("android.os.Looper")
            r2 = _make()
            Handler(Looper.getMainLooper()).post(r2)
            self._keep(r2)
        return True

    def run_bg(self, fn, *args, **kwargs):
        def _work():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                self.log("后台任务异常: " + str(e))
        t = threading.Thread(target=_work, daemon=True)
        t.start()
        return t

    def _make_click(self, fn, *args):
        p = _ensure_dialog_proxy_classes()
        c = p["click"]()
        c._fn = lambda d, w: fn(d, w, *args)
        self._keep(c)
        return c

    def show_log(self, title="信息", lines=None, text="", height_ratio=0.62):
        body = text or ""
        if lines:
            body = (body + "\n" if body else "") + "\n".join(str(x) for x in lines)

        def on_ui(act):
            Builder = jclass("android.app.AlertDialog$Builder")
            TextView = jclass("android.widget.TextView")
            ScrollView = jclass("android.widget.ScrollView")
            Color = jclass("android.graphics.Color")
            TypedValue = jclass("android.util.TypedValue")

            tv = TextView(act)
            tv.setText(body or "(空)")
            tv.setTextIsSelectable(True)
            tv.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13.0)
            tv.setTextColor(Color.parseColor("#334155"))
            pad = dp2px(act, 12)
            tv.setPadding(pad, pad, pad, pad)

            scroll = ScrollView(act)
            scroll.addView(tv)

            builder = Builder(act)
            builder.setTitle(str(title))
            builder.setView(scroll)
            builder.setPositiveButton("关闭", self._make_click(lambda d, w: d.dismiss() if d else None))
            dialog = builder.create()
            self._keep(dialog, tv, scroll)
            dialog.show()

        return self.run_on_ui(on_ui)

    def toast(self, msg, duration=1):
        def on_ui(act):
            try:
                Toast = jclass("android.widget.Toast")
                Toast.makeText(act, str(msg), int(duration)).show()
            except Exception:
                pass
        return self.run_on_ui(on_ui)


_WV_ANCHOR = {}
_VC_PROXY = None
_RUN_PROXY = None

def _ensure_vc_proxy():
    global _VC_PROXY
    if _VC_PROXY is None:
        VC = jclass('android.webkit.ValueCallback')
        base = dynamic_proxy(VC)
        class _VC(base):
            def onReceiveValue(self, value):
                fn = getattr(self, '_fn', None)
                if fn:
                    fn(value)
        _VC_PROXY = _VC
    return _VC_PROXY

def _ensure_run_proxy():
    global _RUN_PROXY
    if _RUN_PROXY is None:
        R = jclass('java.lang.Runnable')
        base = dynamic_proxy(R)
        class _Run(base):
            def run(self):
                fn = getattr(self, '_fn', None)
                if fn:
                    fn()
        _RUN_PROXY = _Run
    return _RUN_PROXY


# ---------- Spider 核心类 ----------
class Spider(BaseSpider):

    def getName(self):
        return 'SupJav'

    def init(self, extend=''):
        global CONFIG
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(ext, dict):
                    CONFIG.update(ext)
            except Exception:
                pass
        self.dlg = MiniDialog(self)
        self._last_wv_ua = ''
        self._cf_restore()

    def destroy(self):
        pass

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def isVideoFormat(self, url):
        return bool(url and re.search(r'\.(m3u8|mp4|ts)(\?|$)', url, re.I))

    # ---------- 日志 ----------
    def _log(self, msg):
        global _LOG_BUF
        line = "[%s] %s" % (time.strftime('%H:%M:%S'), msg)
        _LOG_BUF.append(line)
        if len(_LOG_BUF) > _LOG_MAX:
            _LOG_BUF[:] = _LOG_BUF[-_LOG_MAX:]
        print(line)

    # ---------- CF Cookie 本地文件读写与恢复 ----------
    def _domain(self, url):
        return urllib.parse.urlparse(url).netloc or 'supjav.com'

    def _cf_path(self, domain):
        return os.path.join(CF_COOKIE_DIR, domain + '.json')

    def _cf_load(self, domain='supjav.com'):
        p = self._cf_path(domain)
        if not os.path.exists(p):
            p = self._cf_path('supjav.com')
        try:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                if d.get('cookies'):
                    return d
        except Exception as e:
            self._log('读取 CF cookie 缓存失败: ' + str(e))
        return None

    def _cf_save(self, domain, cookies, ua):
        try:
            os.makedirs(CF_COOKIE_DIR, exist_ok=True)
            with open(self._cf_path(domain), 'w', encoding='utf-8') as f:
                json.dump({'cookies': cookies, 'ua': ua, 'ts': int(time.time())},
                          f, ensure_ascii=False, indent=2)
            self._log('已保存 CF cookie -> ' + self._cf_path(domain))
        except Exception as e:
            self._log('保存 CF cookie 失败: ' + str(e))

    def _cf_restore(self):
        try:
            d = self._cf_load('supjav.com')
            if not (d and d.get('cookies')) or jclass is None:
                return
            cm = jclass('android.webkit.CookieManager').getInstance()
            cm.setAcceptCookie(True)
            for k, v in d['cookies'].items():
                cm.setCookie('https://supjav.com', '%s=%s' % (k, v))
            cm.flush()
            self._log('[恢复] CookieManager 写入并同步完毕')
        except Exception as e:
            self._log('[恢复] 写回 CookieManager 失败: ' + str(e))

    # ---------- 请求相关逻辑 ----------
    def _is_cf(self, text, status=200):
        if not text:
            return True
        low = text.lower()
        return any(m in low for m in [
            'just a moment', 'checking your browser', 'cf-mitigated',
            'challenge-platform', 'enable javascript and cookies to continue',
            'attention required! | cloudflare', 'verify you are human'
        ])

    # 网页 HTML 主抓取通道：绕过 Python TLS 指纹拦截，直接使用 WebView 原生获取
    def _get_html(self, url):
        html, err = self._wv_fetch(url)
        if html and not self._is_cf(html):
            return html
        self._log('WebView 抓取失败或缓存 Cookie 已失效')
        return ''

    def _wv_fetch(self, url, timeout=15):
        if jclass is None or self.dlg is None:
            return None, 'no_jclass'

        cached = self._cf_load(self._domain(url))
        target_ua = (cached.get('ua') if cached else None) or self._last_wv_ua or UA_MOBILE

        evt = threading.Event()
        store = {'html': None, 'err': None}

        def on_ui(act):
            WebView = jclass('android.webkit.WebView')
            WebViewClient = jclass('android.webkit.WebViewClient')
            Handler = jclass('android.os.Handler')
            Looper = jclass('android.os.Looper')

            wv = WebView(act)
            settings = wv.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            settings.setUserAgentString(str(target_ua))

            # 资源减负：默认禁用图片自动加载。
            if not CONFIG.get('images', False):
                settings.setLoadsImagesAutomatically(False)

            wv.setWebViewClient(WebViewClient())
            wv.loadUrl(url)

            def do_cleanup():
                try:
                    wv.stopLoading()
                    wv.loadUrl("about:blank")
                    wv.clearHistory()
                    wv.removeAllViews()
                    wv.destroy()
                except Exception as e:
                    self._log('[wv_fetch] 销毁失败: ' + str(e))

            vc = _ensure_vc_proxy()()
            def _on_val(value):
                try:
                    html = json.loads(value) if isinstance(value, str) else str(value)
                except Exception:
                    html = str(value) if value is not None else ''

                if html and not self._is_cf(html):
                    store['html'] = html
                    evt.set()
                    do_cleanup()

            vc._fn = _on_val
            _WV_ANCHOR[id(vc)] = vc

            handler = Handler(Looper.getMainLooper())
            start_t = time.time()

            def check_loop():
                if evt.is_set():
                    return
                if time.time() - start_t > timeout:
                    store['err'] = 'wv_fetch 超时'
                    evt.set()
                    do_cleanup()
                    return
                try:
                    wv.evaluateJavascript('document.documentElement.outerHTML', vc)
                except Exception as e:
                    store['err'] = 'JS执行失败: ' + str(e)
                    evt.set()
                    do_cleanup()
                    return

                r_next = _ensure_run_proxy()()
                r_next._fn = check_loop
                _WV_ANCHOR[id(r_next)] = r_next
                handler.postDelayed(r_next, 1500)

            r_first = _ensure_run_proxy()()
            r_first._fn = check_loop
            _WV_ANCHOR[id(r_first)] = r_first
            handler.postDelayed(r_first, 2000)

        self.dlg.run_on_ui(on_ui)
        evt.wait(timeout=timeout + 2)
        return store['html'], store['err']

    # 播放api 走 urllib
    def _fetch_url(self, url, referer=None, timeout=12):
        cached = self._cf_load('supjav.com')
        ua = (cached.get('ua') if cached else None) or self._last_wv_ua or UA_DESKTOP
        headers = {
            'User-Agent': ua,
            'Accept': '*/*',
            'Referer': referer or HOST + '/',
        }
        if cached and cached.get('cookies'):
            headers['Cookie'] = '; '.join('%s=%s' % (k, v) for k, v in cached['cookies'].items())

        # 优先用 urllib 发起 API 请求（必须带 Referer / cf cookie，否则解析失败）
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = resp.read()
                return data.decode('utf-8', 'ignore')
        except Exception:
            pass

        # 兜底走 WebView 抓取
        html, _ = self._wv_fetch(url)
        return html or ''

    # ---------- 手动过验证 ----------
    def action(self, action_str):
        if action_str == 'cf::verify':
            if self.dlg is not None:
                self.dlg.run_on_ui(lambda a: self._do_verify(HOST + '/popular?sort=week'))
        elif action_str == 'cf::log':
            if self.dlg is not None:
                self.dlg.show_log('最近日志', lines=list(_LOG_BUF) or ['（暂无日志）'], height_ratio=0.7)
        return {}

    def _do_verify(self, url):
        cached = self._cf_load('supjav.com')
        ua = (cached.get('ua') if cached else None) or UA_DESKTOP
        headers = {'User-Agent': ua, 'Referer': HOST + '/'}

        def on_cookies(cks):
            self._log('验证完成: ' + ', '.join(cks.keys()))
            if cks:
                self._cf_save(self._domain(url), cks, self._last_wv_ua or ua)
                self._cf_restore()
                if self.dlg:
                    self.dlg.toast('Cookie 验证成功并保存！')
        self._verify_dialog(url, headers, on_cookies)

    def _verify_dialog(self, url, base_headers, on_cookies):
        if self.dlg is None or jclass is None:
            on_cookies({})
            return

        def on_ui(act):
            WebView = jclass('android.webkit.WebView')
            WebViewClient = jclass('android.webkit.WebViewClient')
            LinearLayout = jclass('android.widget.LinearLayout')
            TextView = jclass('android.widget.TextView')
            Builder = jclass('android.app.AlertDialog$Builder')
            CookieManager = jclass('android.webkit.CookieManager')
            TypedValue = jclass('android.util.TypedValue')
            pad = int(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 8.0,
                                                act.getResources().getDisplayMetrics()))

            container = LinearLayout(act)
            container.setOrientation(LinearLayout.VERTICAL)
            tip = TextView(act)
            tip.setText('请完成验证（勾选/点击/输入验证码），成功后点「完成」')
            tip.setPadding(pad, pad, pad, pad)
            wv = WebView(act)
            wv.getSettings().setJavaScriptEnabled(True)
            wv.getSettings().setDomStorageEnabled(True)

            HashMap = jclass('java.util.HashMap')
            hm = HashMap()
            for k, v in base_headers.items():
                hm.put(str(k), str(v))

            wv.setWebViewClient(WebViewClient())
            wv.loadUrl(url, hm)
            container.addView(tip)
            container.addView(wv)

            try:
                self._last_wv_ua = str(wv.getSettings().getUserAgentString())
            except Exception:
                self._last_wv_ua = ''

            result = {'cookies': {}}

            def _collect():
                raw = CookieManager.getInstance().getCookie(url) or ''
                out = {}
                for part in raw.split(';'):
                    part = part.strip()
                    if '=' in part:
                        k, v = part.split('=', 1)
                        out[k.strip()] = v
                result['cookies'] = out

            def _finish(d, w):
                _collect()
                try:
                    if dialog is not None:
                        dialog.dismiss()
                except Exception:
                    pass
                on_cookies(result['cookies'])

            builder = Builder(act)
            builder.setTitle('手动过验证')
            builder.setView(container)
            builder.setPositiveButton('完成', self.dlg._make_click(_finish))
            builder.setNegativeButton('取消', self.dlg._make_click(lambda d, w: on_cookies({})))
            dialog = builder.create()
            dialog.show()

        self.dlg.run_on_ui(on_ui)

    # ---------- 分类与页面展示逻辑 ----------
    @staticmethod
    def _entry(action_str, name, remark, style=None):
        e = {'vod_id': action_str, 'vod_name': name, 'vod_pic': '',
             'vod_remarks': remark, 'action': action_str}
        if style:
            e['style'] = style
        return e

    def _cards(self, html):
        out, seen = [], set()
        blocks = re.split(r'<div class="post">', html)[1:]
        for b in blocks:
            m = re.search(r'href="' + re.escape(HOST) + r'/(\d+)\.html"', b)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            t = re.search(r'title="([^"]+)"', b)
            title = t.group(1) if t else ''
            title = (title.replace('&amp;', '&').replace('&#8217;', "'")
                     .replace('&quot;', '"').replace('&#8211;', '-')).strip()
            if not title:
                continue
            seen.add(vid)
            pic = ''
            for pat in (r'<img[^>]+data-original="([^"]+)"',
                        r'<img[^>]+data-src="([^"]+)"',
                        r'<img[^>]+src="(https?://[^"]+)"'):
                pm = re.search(pat, b)
                if pm:
                    pic = pm.group(1)
                    break
            if pic.startswith('//'):
                pic = 'https:' + pic

            code = ''
            cm = re.search(r'\b([A-Z]{2,6}-?\d{2,6}|FC2PPV[\s-]?\d{5,8})\b', title)
            if cm:
                code = cm.group(1)
            out.append({
                'vod_id': HOST + '/' + vid + '.html',
                'vod_name': title[:90],
                'vod_pic': pic,
                'vod_remarks': code,
            })
        return out

    @staticmethod
    def _pagecount(html, cur):
        nums = [int(x) for x in re.findall(r'/page/(\d+)', html)]
        if not nums:
            return cur
        mx = max(nums)
        return mx if 0 < mx <= 5000 else cur

    def homeContent(self, filter):
        classes = [{'type_id': cid, 'type_name': cname} for cid, cname in CATS]
        filters = {}
        for cid, _ in CATS:
            if not cid.startswith('__'):
                filters[cid] = SORTS
        return {'class': classes, 'filters': filters}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, int(pg or 1))
        tid = str(tid).strip()
        ext = extend if isinstance(extend, dict) else {}
        sort = str(ext.get('sort') or '').strip()

        # 工具分类：CF验证 / 日志，列表样式，放在分类最后
        if tid == '__tools':
            items = [
                self._entry('cf::verify', '🔑 CF验证/刷新', '手动过验证并缓存 Cookie', style={'type': 'list'}),
                self._entry('cf::log', '📜 查看日志', '查看最近运行日志', style={'type': 'list'}),
            ]
            return {'page': 1,'pagecount': 1,'limit': len(items),'total': len(items),'list': items,}

        if tid == '__home':
            url = HOST + '/' if page == 1 else HOST + '/page/%d/' % page
        elif tid == '__popular':
            url = (HOST + '/popular/' if page == 1 else HOST + '/popular/page/%d/' % page)
        else:
            base = HOST + '/category/' + tid
            url = base + ('/' if page == 1 else '/page/%d/' % page)
            if sort:
                url += '?sort=' + urllib.parse.quote(sort)

        html = self._get_html(url)
        items = self._cards(html)
        return {'page': page,'pagecount': self._pagecount(html, page),'limit': len(items) or 24,'total': 9999,'list': items,}

    def searchContent(self, key, quick, pg="1"):
        page = max(1, int(pg or 1))
        kw = urllib.parse.quote(str(key))
        url = (HOST + '/?s=' + kw) if page == 1 else (HOST + '/page/%d/?s=%s' % (page, kw))
        html = self._get_html(url)
        items = self._cards(html)
        return {'page': page,'pagecount': self._pagecount(html, page),'limit': len(items) or 24,'total': 9999,'list': items,}

    def detailContent(self, ids):
        url = ids[0] if isinstance(ids, (list, tuple)) else ids
        if not url.startswith('http'):
            url = HOST + '/' + str(url)
        html = self._get_html(url)

        title = ''
        tm = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if tm:
            title = re.sub(r'<[^>]+>', '', tm.group(1)).strip()

        pic = ''
        pm = re.search(r'background-image:\s*url\((https://img\.supjav\.com/[^)]+)\)', html)
        if pm:
            pic = pm.group(1)
        if not pic:
            im = re.search(r'(https://img\.supjav\.com/[^\s"\'<>)]+\.(?:jpg|jpeg|png|webp)[^\s"\'<>)]*)', html, re.I)
            if im:
                pic = im.group(1)

        links = re.findall(r'data-link="([0-9a-f]{40,})"', html)
        names = re.findall(r'data-link="[0-9a-f]{40,}"[^>]*>([^<]{1,12})<', html)
        pairs = []
        for i, lk in enumerate(links):
            nm = names[i].strip() if i < len(names) else ('线路%d' % (i + 1))
            pairs.append((nm, '正片$%s|%s' % (url, lk)))

        # 播放线路排序：名字为 TV 的线路（原先排第一）移到最后
        tv_pairs = [p for p in pairs if p[0].strip().upper().startswith('TV')]
        other_pairs = [p for p in pairs if not p[0].strip().upper().startswith('TV')]
        pairs = other_pairs + tv_pairs

        froms = [p[0] for p in pairs]
        urls = [p[1] for p in pairs]

        vod = {
            'vod_id': url,
            'vod_name': title or 'SupJav Video',
            'vod_pic': pic,
            'vod_play_from': '$$$'.join(froms) if froms else 'SupJav',
            'vod_play_url': '$$$'.join(urls) if urls else ('正片$%s|' % url),
        }
        return {'list': [vod]}

    # ---------- 直链解析核心（参考 sj.py 逻辑，解包/VOE/Streamtape） ----------
    @staticmethod
    def _unpack(text):
        m = re.search(r"}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)", text, re.S)
        if not m:
            return ''
        payload, base, count, keys = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).split('|')
        try:
            payload = payload.encode().decode('unicode_escape')
        except Exception:
            pass
        digits = '0123456789abcdefghijklmnopqrstuvwxyz'

        def enc(num):
            out = ''
            while num > 0:
                out = digits[num % base] + out
                num //= base
            return out or '0'

        table = {}
        for i in range(count):
            if i < len(keys) and keys[i]:
                table[enc(i)] = keys[i]
        return re.sub(r'\b\w+\b', lambda mm: table.get(mm.group(0), mm.group(0)), payload)

    @staticmethod
    def _voe_decode(html):
        m = re.search(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', html or '', re.S)
        if not m:
            return {}
        blk = m.group(1).strip()
        try:
            j = json.loads(blk)
            raw = j[0] if isinstance(j, list) and j else blk
        except Exception:
            raw = blk

        s = str(raw)
        for k in ('@$', '^^', '~@', '%?', '*~', '!!', '#&'):
            s = s.replace(k, '_')
        s = s.replace('_', '')

        def b64d(x):
            x = re.sub(r'[^A-Za-z0-9+/=]', '', x)
            x += '=' * (-len(x) % 4)
            return base64.b64decode(x).decode('utf-8', 'replace')

        try:
            t = b64d(codecs.encode(s, 'rot13'))
            t = ''.join(chr(ord(c) - 3) for c in t)
            t = b64d(t[::-1])
            cfg = json.loads(t)
            return cfg if isinstance(cfg, dict) else {}
        except Exception:
            return {}

    def _extract_stream(self, s2, ref):
        # 1. 明文 M3U8
        hits = re.findall(r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*', s2)
        if hits:
            return hits[0], ''

        # 2. Dean Edwards Packer 解包
        if 'eval(function(p,a,c,k,e' in s2:
            dec = self._unpack(s2)
            hits = re.findall(r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*', dec)
            if hits:
                return hits[0], ''

        # 3. Streamtape
        em = re.search(r'https?://streamtape\.com/e/([A-Za-z0-9]+)', s2)
        if em:
            eurl = 'https://streamtape.com/e/%s/' % em.group(1)
            page = self._fetch_url(eurl, referer=HOST + '/')
            for pat in (r"innerHTML\s*=\s*'([^']+)'\s*\+\s*\('([^']+)'\)\.substring\((\d+)\)",
                        r'innerHTML\s*=\s*"([^"]+)"\s*\+\s*\("([^"]+)"\)\.substring\((\d+)\)'):
                mm = re.search(pat, page or '')
                if not mm:
                    continue
                link = mm.group(1) + mm.group(2)[int(mm.group(3)):]
                if link.startswith('//'):
                    link = 'https:' + link
                if 'dl=' not in link:
                    link += ('&dl=1' if '?' in link else '?dl=1')
                return '', link

        # 4. VOE 混淆流
        tgt = re.findall(r"window\.location\.href\s*=\s*'([^']+)'", s2)
        tgt += re.findall(r'https?://[a-z0-9.-]+/e/[a-z0-9]{8,}', s2)
        if tgt:
            page = self._fetch_url(tgt[0], referer=ref)
            cfg = self._voe_decode(page)
            src = str(cfg.get('source') or '')
            if '.m3u8' in src:
                return src, ''
            dau = str(cfg.get('direct_access_url') or '')
            if dau.startswith('http'):
                return '', dau
            if src.startswith('http'):
                return '', src

        return '', ''

    def playerContent(self, flag, id, vipFlags):
        raw = str(id)
        detail, _, lk = raw.partition('|')
        fail = {'parse': 0, 'playUrl': '', 'url': '', 'jx': 0}

        if not lk:
            return fail

        # 第一步：supjav.php?l=<hex> (带 Referer 请求)
        s1_url = LK_BASE + '?l=' + lk
        s1 = self._fetch_url(s1_url, referer=detail)

        # 提取并反转 OLID
        om = re.search(r"var\s+OLID\s*=\s*'([0-9a-f]{40,})'", s1 or '')
        olid = om.group(1)[::-1] if om else lk[::-1]

        # 第二步：supjav.php?c=<reversed_olid> (带 Referer 请求)
        s2_url = LK_BASE + '?c=' + olid
        s2 = self._fetch_url(s2_url, referer=s1_url)
        if not s2:
            return fail

        # 第三步：抽取 M3U8 或 MP4 直链
        m3u8, direct = self._extract_stream(s2, s1_url)
        play_url = direct or m3u8
        if not play_url:
            return fail

        play_url = play_url.replace('\\/', '/').replace('&amp;', '&')
        cached = self._cf_load('supjav.com')
        ua = (cached.get('ua') if cached else None) or self._last_wv_ua or UA_DESKTOP

        return {'parse': 0, 'url': play_url,'header': {'User-Agent': ua,'Referer': HOST + '/'}}
