# 站点：https://www.freeokk.lol  （FreeOK - 追剧也很卷；官方域名 freeokk.pro，最新域名 freeok.ink）
# 路线：MacCMS v10 的「采集 API」直取（HTML 只是外壳，别去解 DOM）：
#   数据全在 /api.php/provide/vod/ —— ac=list/detail、t=分类、pg=页码、wd=搜索、ids=详情
#   实测：ac=list&pg=1 → pagecount=4604 / total=92076 / limit=20（真分页，直接可用）
#        ac=detail&t=1&pg=2 → pagecount=2150；ac=detail&wd=斗罗&pg=2 → pagecount=3 / total=49
# 生成：2026-11-24   作者：Doubao
# 依赖：requests（壳端自带）+ base.spider；json / re / time / urllib 均为标准库，无 lxml / bs4
# 接口：homeContent / homeVideoContent / categoryContent / detailContent / searchContent / playerContent / localProxy
# vod_id 协议：纯数字（"934"）；播放 id 直接存 API 给的媒体地址（"第01集$https://…/index.m3u8"）
# 分页来源：API 返回的 pagecount 与 total 就是站点真值（第 1 条合法来源），不做任何推算
# 播放形态（实测同一部剧 6 条线路混排）：
#   1080zyk / dyttm3u8 / ffm3u8 / bfzym3u8 / rym3u8 → 直链 m3u8（5 个 CDN 全部实测 200 + #EXTM3U，无需 Referer）
#   qq / qiyi / youku / mgtv → 官方平台页（v.qq.com / iqiyi / youku / mgtv），只能 parse:1 交壳端解析
# 已知限制：① 站点前置 Cloudflare，实测首页 200/99KB 无挑战页，但被拦时需换域或加代理；
#   ② 官方平台线路（qq/qiyi/youku/mgtv）能否播取决于壳端解析接口，本源只负责拿到官方页；
#   ③ 换域来源是首页「域名弹窗」明文（官方 freeokk.pro / 最新 freeok.ink / 备用 freeokk.lol、freeokk.top），
#     没有独立发布页，所以换域时抓首页弹窗即可。

import json
import random
import re
import time
import urllib.parse

import requests

from base.spider import Spider


class Spider(Spider):
    # 主域：实测 200/99204B、title=FreeOK - 追剧也很卷，无 CF 挑战页
    HOST = 'https://www.freeokk.lol'
    # 域池：入口 lol → 最新 freeok.ink → 官方 freeokk.pro → 备用 freeokk.top；
    # 四条实测首页字节完全一致（99204B），是同一份数据，不靠 title 判归属（同名停放页很常见）
    DOMS = ['https://www.freeokk.lol', 'https://www.freeok.ink', 'https://www.freeokk.pro',
            'https://www.freeokk.top', 'https://freeokk.lol']
    # 采集 API：MacCMS 标准路径，HTML 首页只是壳；参照 ac=list 的 8 个字段就知道站方就是这套
    API = '/api.php/provide/vod/'
    # 分类 = 首页导航真实 4 个主类（实测 API 里 type_id 只出现 1/2/3/4，没有第 5 类）
    CLASSES = [('1', '电影'), ('2', '剧集'), ('3', '综艺'), ('4', '动漫')]
    # 线路名映射：API 给的是采集源内部代号（dyttm3u8/bfzym3u8…），直接给壳端显示会是乱码感，
    # 必须翻成人话；未收录的代号原样保留，别丢线路
    LINE_NAME = {
        '1080zyk': '1080资源', 'dyttm3u8': '电影天堂', 'ffm3u8': '非凡资源',
        'bfzym3u8': '暴风资源', 'rym3u8': '如意资源',
        'qq': '腾讯官采', 'qiyi': '爱奇艺官采', 'youku': '优酷官采', 'mgtv': '芒果官采',
    }
    # 排序：直链线路在前（1080 优先 = 4K/蓝光置顶），解析线路在后；未列出的直链按 50，官方按 90
    LINE_ORDER = {'1080zyk': 0, 'dyttm3u8': 1, 'ffm3u8': 2, 'bfzym3u8': 3, 'rym3u8': 4}
    OFFICIAL = ('v.qq.com', 'iqiyi.com', 'youku.com', 'mgtv.com', 'bilibili.com',
                'le.com', 'sohu.com', 'miguvideo.com')
    # 首页弹窗噪音域：埋点、图床、推广链接都不是站点镜像
    JUNK = ('aizhantj', 'go2yd', 'alicdn', 'doubanio', 't.me', 'yinghezhinan', 'telegram',
            'qq.com', 'iqiyipic', 'ykimg', 'hitv', 'puui', 'dytt-tupian')
    # 每页条数：API limit 就是 20，取一致才能让 total/pc 与站点对上
    LIMIT = 20
    # 单条播放串上限：壳端 2048B 截断，留 148B 给线路名与分段后缀；
    # 实测《仙逆》168 集 × 6 线路，不分段第 10 集之后就被整段截掉，必须按线路切段
    SEG = 1900
    # API 缓存：列表/详情 300s（壳端翻页复访很密）；API 一次详情可能 77KB，重复打站很明显
    TTL = 300
    # 失败冷却：域级 30s；单条 404/500 只算路径问题，不冷整域（v11.3 冷却粒度）
    COOL = 30
    # 探针上限：弹窗/池最多验 4 个候选域，别在换域时把探测预算一次烧完
    MAXB = 4
    UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
    # 类属性缓存：壳端每次调用都新建实例，写成 self._x 等于每次重打 API（详情 77KB 会明显拖慢）
    _POOL = []
    _BAD = {}
    _CACHE = {}
    _PUBT = 0

    # 源名：壳端源列表显示用，固定站点名
    def getName(self):
        return 'FreeOK'

    # 初始化：只建 session 与 setdefault 绑类缓存，绝不重置（重置=每集重打 API）
    def init(self, extend=''):
        self.extend = extend or ''
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.UA,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        type(self)._POOL = type(self)._POOL or list(self.DOMS)
        for t in ('_BAD', '_CACHE'):
            getattr(type(self), t).setdefault('_t', 0)
        self.base = type(self)._POOL[0]

    # ── 基础工具 ────────────────────────────────────────────────

    # 请求间隔：CF 前置站对连击敏感，1.0~1.4s 抖动既避开限流，也不把 live_check 预算吃光
    def _gap(self):
        time.sleep(random.uniform(1.0, 1.4))

    # 站点头：API 不需要 Referer，但带上更接近浏览器；缺 UA 时 CF 会直接给 403
    def _bh(self, referer=None):
        return {
            'User-Agent': self.UA,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or (self.base + '/'),
        }

    # 域冷却：只给整体不可用写冷却；单条 404 不冷整域（否则一次冷门条目会把整站判死）
    def _mark(self, host):
        type(self)._BAD[host] = time.time() + self.COOL

    # 选可用域：优先没进冷却的池成员；全在冷却里就先刷首页弹窗拿新域，再不行清冷却重来
    def _pick_host(self):
        pool = type(self)._POOL or list(self.DOMS)
        now = time.time()
        for h in pool:
            if float(type(self)._BAD.get(h, 0) or 0) < now:
                return h
        self._from_popup()
        pool = type(self)._POOL or list(self.DOMS)
        for h in pool:
            if float(type(self)._BAD.get(h, 0) or 0) < now:
                return h
        type(self)._BAD.clear()
        return pool[0]

    # 站内「域名弹窗」换域：首页 popup-domain 区块明文写着 官方 freeokk.pro / 最新 freeok.ink /
    # 备用 freeokk.lol、freeokk.top，没有独立发布页，所以换域就抓首页；
    # 30 分钟内只刷一次，且候选必须过活体校验（体积 30KB+ 且含 FreeOK/弹窗特征）
    def _from_popup(self):
        if time.time() - float(type(self)._PUBT or 0) < 1800:
            return
        type(self)._PUBT = time.time()
        for p in (type(self)._POOL or list(self.DOMS)):
            try:
                r = self.session.get(p + '/', headers=self._bh(p + '/'),
                                     timeout=(8, 15), proxies=self.session.proxies or None)
                txt = r.content.decode('utf-8', 'replace')
            except Exception:
                continue
            cand = []
            for d in re.findall(r'(?:https://)?(?:www\.)?((?:freeokk|freeok)\.[a-z]{2,4})', txt):
                if any(j in d for j in self.JUNK) or d in cand:
                    continue
                cand.append(d)
            for d in cand[:self.MAXB]:
                if not d.startswith('www.'):
                    d = 'www.' + d
                h = 'https://' + d
                if h in type(self)._POOL or not self._alive(h):
                    continue
                type(self)._POOL.append(h)
            break

    # 活体校验：首页要过 30KB 且含站点特征；只判 200 会把停放页/跳转壳页当镜像（同名域很多）
    def _alive(self, host):
        try:
            self._gap()
            r = self.session.get(host + '/', headers=self._bh(host + '/'),
                                 timeout=(8, 15), proxies=self.session.proxies or None)
            txt = r.content.decode('utf-8', 'replace')
        except Exception:
            return False
        return len(txt) > 30000 and ('FreeOK' in txt or 'maccms' in txt or 'freeokk' in txt)

    # 统一 API 请求：缓存命中 → 冷却跳过 → 失败换域重试一次。
    # 返回 dict；解析失败（拿到 HTML/空）按域级失败处理，换域重试，绝不在同一域死循环
    def _api(self, **params):
        params.setdefault('ac', 'list')
        key = 'q|' + '&'.join('%s=%s' % (k, params[k]) for k in sorted(params))
        hit = type(self)._CACHE.get(key)
        if hit and time.time() < hit[0]:
            return hit[1]
        url = self.base + self.API + '?' + urllib.parse.urlencode(params)
        data = {}
        for _ in range(2):
            host = urllib.parse.urlparse(self.base).scheme + '://' + \
                (urllib.parse.urlparse(self.base).hostname or '')
            if float(type(self)._BAD.get(host, 0) or 0) > time.time():
                nb = self._pick_host()
                if nb != self.base:
                    self.base = nb
                    url = self.base + self.API + '?' + urllib.parse.urlencode(params)
                continue
            try:
                self._gap()
                r = self.session.get(url, headers=self._bh(self.base + '/'),
                                     timeout=(8, 22), proxies=self.session.proxies or None)
                data = json.loads(r.content.decode('utf-8', 'replace'))
            except Exception:
                data = {}
            if isinstance(data, dict) and ('list' in data or data.get('code') in (1, '1')):
                break
            self._mark(host)
            nb = self._pick_host()
            if nb and nb != self.base:
                self.base = nb
                url = self.base + self.API + '?' + urllib.parse.urlencode(params)
        if isinstance(data, dict) and 'list' in data:
            type(self)._CACHE[key] = (time.time() + self.TTL, data)
            return data
        return {}

    # 去标签 + 还原实体：API 的 vod_content 是 HTML 片段，不清掉会给壳端一堆 <p> 标签
    def _clean(self, s):
        s = re.sub(r'(?is)<[^>]+>', ' ', s or '')
        s = s.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
        s = s.replace('&lt;', '<').replace('&gt;', '>').replace('&#39;', "'")
        return re.sub(r'\s+', ' ', s).strip()

    # 单条条目 → 壳端卡片：ac=list 没有封面/年份，所以本源一律用 ac=detail 取列表（多 40KB 换完整卡片）
    def _row(self, it):
        return {
            'vod_id': str(it.get('vod_id') or ''),
            'vod_name': self._clean(it.get('vod_name') or ''),
            'vod_pic': it.get('vod_pic') or '',
            'vod_remarks': self._clean(it.get('vod_remarks') or ''),
            'vod_year': str(it.get('vod_year') or '')[:4],
            'vod_area': self._clean(it.get('vod_area') or ''),
            'vod_type': self._clean(it.get('vod_class') or it.get('type_name') or ''),
        }

    def _rows(self, data):
        out, seen = [], set()
        for it in (data.get('list') or []):
            i = str(it.get('vod_id') or '')
            if not i or i in seen:
                continue
            seen.add(i)
            out.append(self._row(it))
        return out

    # ── 六接口 ─────────────────────────────────────────────────

    # 首页：4 个真实主分类 + 最新入库 20 条（ac=detail&pg=1，按 vod_time 倒序，站方默认排序就是最新）
    def homeContent(self, filter):
        data = self._api(ac='detail', pg='1')
        cls = [{'type_id': t, 'type_name': n} for t, n in self.CLASSES]
        return {'class': cls, 'filters': {}, 'list': self._rows(data)[:self.LIMIT]}

    # 推荐位：壳端首屏单独调用，复用同一份 API 缓存（同一 key，不会打两次站）
    def homeVideoContent(self):
        return {'list': self._rows(self._api(ac='detail', pg='1'))[:self.LIMIT]}

    # 分类：ac=detail&t={tid}&pg={pg}；pagecount/total 直接取 API 真值（实测 t=1 有 2150 页），
    # 不做「满页 +1」推算——站点本来就给了真页数，推算反而是退步
    def categoryContent(self, tid, pg, filter, extend):
        tid = str(tid or '').strip() or self.CLASSES[0][0]
        try:
            pg = max(1, int(pg))
        except Exception:
            pg = 1
        data = self._api(ac='detail', t=tid, pg=str(pg))
        lst = self._rows(data)[:self.LIMIT]
        pc = int(data.get('pagecount') or 1) or 1
        total = int(data.get('total') or (pc * self.LIMIT))
        return {'page': pg, 'pagecount': pc, 'limit': self.LIMIT,
                'total': max(total, len(lst)), 'list': lst}

    # 详情：ac=detail&ids={vid}，一次拿全（vod_play_from 与 vod_play_url 都是 $$$ 分隔）。
    # 线路按「直链优先 + 1080 置顶」重排，再按 1900B 分段；168 集 × 6 线路实测必须切段，否则 2048B 截断
    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        mid = re.search(r'(\d+)', str(raw) or '')
        if not mid:
            return {'list': []}
        vid = mid.group(1)
        data = self._api(ac='detail', ids=vid)
        lst = data.get('list') or []
        if not lst:
            return {'list': []}
        it = lst[0]
        froms = [x for x in (it.get('vod_play_from') or '').split('$$$') if x]
        urls = [x for x in (it.get('vod_play_url') or '').split('$$$') if x]
        if not froms or not urls:
            return {'list': []}
        # 逐线路整理：MacCMS 的 vod_play_from 就是 sid（线路代号 = 采集源代号），
        # 必须按 sid 分组，不能把不同 sid 的集数拼进同一条线里（混了就是串集/串源）
        groups = []
        for sid, seg in zip(froms, urls):
            eps = []
            for item in seg.split('#'):
                if '$' not in item:
                    continue
                nm, u = item.split('$', 1)
                u = u.strip()
                if not u.startswith('http'):
                    continue
                eps.append((self._clean(nm) or '第%d集' % (len(eps) + 1), u))
            if not eps:
                continue
            groups.append((sid, eps))
        # 排序：直链线路在前、官方解析线路在后；同档位按 LINE_ORDER（sid → 优先级）
        def _key(g):
            sid = g[0]
            if sid in self.LINE_ORDER:
                return self.LINE_ORDER[sid]
            if any(d in (g[1][0][1] if g[1] else '') for d in self.OFFICIAL):
                return 90
            return 50
        groups.sort(key=_key)
        # 线路名：sid 代号翻中文，同名去重加序号；禁词（选择播放源/播放线路等）一律不进线路名
        names, used = [], set()
        for sid, _eps in groups:
            nm = self.LINE_NAME.get(sid, sid)
            if nm in used:
                k = 2
                while '%s%d' % (nm, k) in used:
                    k += 1
                nm = '%s%d' % (nm, k)
            used.add(nm)
            names.append(nm)
        # 分段：每条线路按 SEG 切，段名统一「线路名(1)(2)」；段数必须与 froms 一一对应
        seg_froms, seg_urls = [], []
        for idx, (_f, eps) in enumerate(groups):
            base_nm = names[idx]
            seg, cur = [], 0
            part = 0
            for nm, u in eps:
                if len(nm) > 16:
                    nm = nm[:16]
                need = len(('%s$%s' % (nm, u)).encode('utf-8')) + 1
                if seg and cur + need > self.SEG:
                    part += 1
                    seg_froms.append(base_nm if part == 1 else '%s(%d)' % (base_nm, part))
                    seg_urls.append('#'.join('%s$%s' % (a, b) for a, b in seg))
                    seg, cur = [], 0
                seg.append((nm, u))
                cur += need
            if seg:
                part += 1
                seg_froms.append(base_nm if part == 1 else '%s(%d)' % (base_nm, part))
                seg_urls.append('#'.join('%s$%s' % (a, b) for a, b in seg))
        vod = {
            'vod_id': vid,
            'vod_name': self._clean(it.get('vod_name') or ''),
            'vod_pic': it.get('vod_pic') or '',
            'vod_remarks': self._clean(it.get('vod_remarks') or ''),
            'vod_year': str(it.get('vod_year') or '')[:4],
            'vod_area': self._clean(it.get('vod_area') or ''),
            'vod_type': self._clean(it.get('vod_class') or it.get('type_name') or ''),
            'vod_actor': self._clean(it.get('vod_actor') or ''),
            'vod_director': self._clean(it.get('vod_director') or ''),
            'vod_lang': self._clean(it.get('vod_lang') or ''),
            'vod_content': self._clean(it.get('vod_content') or it.get('vod_blurb') or ''),
            'vod_play_from': '$$$'.join(seg_froms),
            'vod_play_url': '$$$'.join(seg_urls),
        }
        return {'list': [vod]}

    # 搜索：ac=detail&wd={key}&pg={pg}，真分页（实测 wd=斗罗 pagecount=3 / total=49），pagecount 取 API 真值
    def searchContent(self, key, quick, pg='1'):
        kw = (key or '').strip()
        if not kw:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': self.LIMIT, 'total': 0}
        try:
            p = max(1, int(pg))
        except Exception:
            p = 1
        data = self._api(ac='detail', wd=kw, pg=str(p))
        lst = self._rows(data)[:self.LIMIT]
        pc = int(data.get('pagecount') or 1) or 1
        total = int(data.get('total') or (pc * self.LIMIT))
        if str(quick) in ('1', 'True', 'true') and len(lst) > 12:
            lst = lst[:12]
        return {'list': lst, 'page': p, 'pagecount': pc if lst or p == 1 else 1,
                'limit': self.LIMIT, 'total': max(total, len(lst))}

    # 播放：入参是「第01集$https://…/index.m3u8」或纯 URL，先剥 $ 与 #。
    # 判定：直链 m3u8/mp4 → parse:0（5 个采集 CDN 实测 200 + #EXTM3U，且**不带 Referer 就能取**，
    #   带错 Referer 的 CDN 会被 403，所以 media 头只给 UA）；
    #   官方平台页（v.qq/iqiyi/youku/mgtv）→ parse:1，交给壳端解析接口，别把官方页当直链
    def playerContent(self, flag, id, vipFlags):
        pid = str(id or '').split('#')[0].rsplit('$', 1)[-1].strip()
        if not pid:
            return {'parse': 1, 'url': ''}
        if not pid.startswith('http'):
            return {'parse': 1, 'url': self.base + (pid if pid.startswith('/') else '/' + pid)}
        low = pid.split('?')[0].lower()
        host = urllib.parse.urlparse(pid).hostname or ''
        if low.endswith('.m3u8') or low.endswith('.mp4') or low.endswith('.flv'):
            return {'parse': 0, 'url': pid, 'header': {'User-Agent': self.UA}}
        if any(d in host for d in self.OFFICIAL):
            ref = 'https://%s/' % host.split('.')[-2] + '.' + host.split('.')[-1] if host else self.base
            return {'parse': 1, 'url': pid,
                    'header': {'User-Agent': self.UA, 'Referer': ref}}
        # 兜底：站内播放页/其它页，交给壳端打开
        return {'parse': 1, 'url': pid, 'header': {'User-Agent': self.UA,
                                                   'Referer': self.base + '/'}}

    # 图片代理：封面来自十几个图床（yzzyimg / dytt-tupian / iqiyipic / picbf / hitv …），
    # 铁律是**绝不带站点 Referer**（爱奇艺图床带站点 Referer 直接 403 + 349B html）；
    # 空 body 返 404，返回 200 空图壳端会显示灰块
    def localProxy(self, param):
        u = urllib.parse.unquote(str(param or ''))
        if not u.startswith('http'):
            return [404, 'text/plain', b'']
        try:
            r = self.session.get(u, headers={'User-Agent': self.UA,
                                             'Accept': 'image/*,*/*;q=0.8'},
                                 timeout=(6, 15), stream=False,
                                 proxies=self.session.proxies or None)
            body = r.content or b''
            if not body:
                return [404, 'text/plain', b'']
            ctype = (r.headers.get('Content-Type') or 'image/jpeg').split(';')[0]
            if body[:4] == b'\x89PNG':
                ctype = 'image/png'
            elif body[:4] == b'\xff\xd8\xff\xe0' or body[:3] == b'\xff\xd8\xff':
                ctype = 'image/jpeg'
            return [r.status_code if r.status_code in (200, 206) else 200, ctype, body]
        except Exception:
            return [404, 'text/plain', b'']
