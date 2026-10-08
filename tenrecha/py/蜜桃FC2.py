# coding=utf-8
import sys
import os
import re
import json
import time
import random
import base64
import hashlib
import tempfile

sys.path.append('..')

try:
    from base.spider import Spider as BaseSpider
except ImportError:  
    import requests as _rq

    class BaseSpider(object):
        def fetch(self, url, headers=None, timeout=20, verify=False, **kw):
            s = _rq.Session()
            s.trust_env = False
            return s.get(url, headers=headers, timeout=timeout, verify=verify, **kw)

        def log(self, msg):
            print(msg)



_MEM = {
    'ts': 0,          # 片单解析完成时间戳
    'items': [],      # 全部条目
    'index': {},      # 番号 -> 条目
    'classes': [],    # 父分类
    'filters': {},    # 父分类 -> 筛选器
    'updated': '',    # 片单更新时间(Last-Modified)
    'probe': {},      # m3u8 时长探测缓存
}


class Spider(BaseSpider):
    name = '蜜桃FC2'
    host = 'https://b2.bttss.cc'

    _PLAYLIST = ('%EF%BC%BB%E8%9C%9C%E6%A1%83%EF%BC%BDFC2-PPV.m3u')
    _RAW = 'https://raw.githubusercontent.com/KAN314go/cc/refs/heads/main/file/' + _PLAYLIST

    # 片单镜像，按序回退(均已实测 200)
    M3U_SOURCES = [
        'https://445569.pages.dev/' + _RAW,
        _RAW,
        'https://cdn.jsdelivr.net/gh/KAN314go/cc@main/file/' + _PLAYLIST,
        'https://gcore.jsdelivr.net/gh/KAN314go/cc@main/file/' + _PLAYLIST,
        'https://ghproxy.net/' + _RAW,
    ]

    UA = ('Mozilla/5.0 (Linux; Android 13; V2154A Build/TP1A.220624.014) AppleWebKit/537.36 '
          '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')

    PER_PAGE = 60
    CACHE_TTL = 6 * 3600
    BATCH = 100              # 片单每批条数(group-title 步长)
    SEG_BATCH = 10           # 每 10 个批次(=1000 条)合成一个父分类

    _debug = False

    # ================= TVBox 固定接口 =================
    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower().split('?')[0]
        return any(u.endswith(x) for x in
                   ['.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.mov', '.mpd'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _log(self, msg):
        if self._debug:
            try:
                self.log('[%s] %s' % (self.name, msg))
            except Exception:
                print('[%s] %s' % (self.name, msg))

    # ================= 初始化 =================
    def init(self, extend=''):
        cfg = {}
        if extend:
            if isinstance(extend, dict):
                cfg = extend
            else:
                try:
                    cfg = json.loads(extend)
                except Exception:
                    cfg = {}
        self.cfg = cfg if isinstance(cfg, dict) else {}
        self.per_page = max(1, int(self.cfg.get('page_size') or self.PER_PAGE))
        self.ttl = max(60, int(self.cfg.get('cache_ttl') or self.CACHE_TTL))
        self.need_probe = self.cfg.get('probe', True) is not False
        self.proxy_line = self.cfg.get('proxy_line', True) is not False
        self.pic_over = (self.cfg.get('pic') or '').strip()
        my = (self.cfg.get('m3u') or '').strip()
        self.sources = ([my] if my else []) + list(self.M3U_SOURCES)
        try:
            self._load()
        except Exception as e:
            self._log('片单加载失败: %s' % e)
        return {}

    def _headers(self, referer=None):
        h = {
            'User-Agent': self.UA,
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        if referer:
            h['Referer'] = referer
        return h

    def _ready(self):
        if not _MEM['items']:
            if not hasattr(self, 'sources'):
                self.init()
            else:
                try:
                    self._load()
                except Exception as e:
                    self._log('片单重载失败: %s' % e)
        return bool(_MEM['items'])

    # ================= 片单获取 / 缓存 =================
    def _cache_path(self):
        tag = hashlib.md5(self.sources[0].encode('utf-8')).hexdigest()[:10]
        return os.path.join(tempfile.gettempdir(), 'mitao_fc2_%s.m3u' % tag)

    def _read_disk(self):
        try:
            p = self._cache_path()
            if os.path.isfile(p) and (time.time() - os.path.getmtime(p)) < self.ttl:
                with open(p, 'rb') as f:
                    raw = f.read()
                if len(raw) > 4096:
                    ts = time.localtime(os.path.getmtime(p))
                    return raw.decode('utf-8', 'ignore'), time.strftime('%Y-%m-%d %H:%M', ts)
        except Exception as e:
            self._log('读磁盘缓存失败: %s' % e)
        return '', ''

    def _write_disk(self, text):
        try:
            with open(self._cache_path(), 'wb') as f:
                f.write(text.encode('utf-8', 'ignore'))
        except Exception as e:
            self._log('写磁盘缓存失败: %s' % e)

    def _download(self):
        """按镜像顺序回退下载片单，返回 (文本, 更新时间)。"""
        for u in self.sources:
            try:
                r = self.fetch(u, headers=self._headers(), timeout=30, verify=False)
                if getattr(r, 'status_code', 0) != 200:
                    self._log('镜像 %s -> HTTP %s' % (u[:48], getattr(r, 'status_code', '?')))
                    continue
                r.encoding = 'utf-8'
                text = r.text or ''
                if len(text) < 4096 or '#EXTM3U' not in text[:512]:
                    self._log('镜像 %s 内容异常(%d 字节)' % (u[:48], len(text)))
                    continue
                lm = ''
                try:
                    lm = r.headers.get('Last-Modified') or r.headers.get('last-modified') or ''
                except Exception:
                    pass
                self._log('片单命中镜像 %s (%.1f KB)' % (u[:48], len(text) / 1024.0))
                return text, self._fmt_lm(lm)
            except Exception as e:
                self._log('镜像 %s 异常: %s' % (u[:48], e))
                continue
        return '', ''

    @staticmethod
    def _fmt_lm(lm):
        if not lm:
            return ''
        for f in ('%a, %d %b %Y %H:%M:%S GMT', '%a, %d %b %Y %H:%M:%S %Z'):
            try:
                return time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.mktime(time.strptime(lm, f))))
            except Exception:
                continue
        return lm

    def _load(self, force=False):
        if not force and _MEM['items'] and (time.time() - _MEM['ts']) < self.ttl:
            return
        text, upd = ('', '') if force else self._read_disk()
        if not text:
            text, upd = self._download()
            if text:
                self._write_disk(text)
        if not text:
            return
        items = self._parse_m3u(text)
        if not items:
            return
        _MEM['items'] = items
        _MEM['index'] = dict((it['name'], it) for it in items)
        _MEM['updated'] = upd or time.strftime('%Y-%m-%d %H:%M')
        _MEM['ts'] = time.time()
        self._build_classes(items)
        self._log('解析完成: %d 条 / %d 个分组 / %d 个父分类'
                  % (len(items), len(set(i['gid'] for i in items)), len(_MEM['classes'])))

    # ================= M3U 解析 =================
    @staticmethod
    def _extinf_name(line):
        """从非标准 #EXTINF 行取名称：优先"最后一个引号之后"，兜底最后一个逗号之后。"""
        tail = ''
        if '"' in line:
            tail = line[line.rindex('"') + 1:]
        tail = tail.strip().lstrip(',').strip()
        if not tail and ',' in line:
            tail = line.rsplit(',', 1)[-1].strip()
        return tail

    @staticmethod
    def _fix_stream(url):
        """修复掺入 HTML 属性碎片的直链(片单缺陷 3b)。"""
        u = (url or '').strip()
        if '"' not in u and "'" not in u and ' ' not in u:
            return u
        m = re.match(r'(https?://[^\s"\']+?/videos/[0-9a-fA-F]{16,64})', u)
        if m:
            h = re.search(r'[?&]h=([0-9a-zA-Z]+)', u)
            tail = re.search(r'/([^/"\'\s]+\.m3u8)', u)
            fn = tail.group(1) if tail else 'g.m3u8'
            return m.group(1) + '/' + fn + ('?h=' + h.group(1) if h else '')
        return re.split(r'["\'\s]', u)[0]

    def _parse_m3u(self, text):
        items = []
        pend = None          # (name, logo, group)
        head_logo = ''
        logo_hits = {}
        for raw in text.splitlines():
            s = raw.strip()
            if not s:
                continue
            if s.startswith('#EXTM3U'):
                m = re.search(r'x-tvg-logo="([^"]*)"', s)
                if m:
                    head_logo = m.group(1)
                continue
            if s.startswith('#EXTINF'):
                logo = ''
                grp = ''
                m = re.search(r'tvg-logo="([^"]*)"', s)
                if m:
                    logo = m.group(1)
                m = re.search(r'group-title="([^"]*)"', s)
                if m:
                    grp = m.group(1)
                pend = (self._extinf_name(s), logo, grp)
                continue
            if s.startswith('%%'):
                # 片单缺陷 3a：第 (040) 批用 "%%番号" 代替 #EXTINF
                pend = (s.lstrip('%').strip(), '', '')
                continue
            if s.startswith('#'):
                continue
            if not pend:
                continue
            name, logo, grp = pend
            pend = None
            url = self._fix_stream(s)
            if not name or not url.startswith('http'):
                continue
            num = re.sub(r'^[A-Za-z]*[-_]?', '', name)
            num = re.sub(r'\D', '', num) or re.sub(r'\D', '', name)
            seq = 0
            real = True
            m = re.match(r'^FC2[-_]?(\d{5})$', name, re.I)
            if m:
                seq = int(m.group(1))     # 5 位为片单自编序号
                real = False
            gid = '%03d' % ((seq + self.BATCH - 1) // self.BATCH) if seq else '000'
            if logo:
                logo_hits[logo] = logo_hits.get(logo, 0) + 1
            items.append({
                'name': name,
                'num': num,
                'seq': seq,
                'real': real,
                'gid': gid,
                # 番号段(父分类)按"每 10 个批次"切分，边界与 group-title 完全对齐，
                # 避免筛选器里的批次被父分类切成两半
                'bk': -1 if gid == '000' else (int(gid) - 1) // self.SEG_BATCH,
                'group': grp or ('(%s) - FC2-PPV' % gid),
                'pic': self.pic_over or logo or head_logo,
                'url': url,
            })
        # 片单缺陷 3a 的那批没有 tvg-logo，用片单主封面回填，避免列表出现空白图
        if not self.pic_over:
            fb = head_logo
            if logo_hits:
                fb = max(logo_hits.items(), key=lambda kv: kv[1])[0]
            if fb:
                for it in items:
                    if not it['pic']:
                        it['pic'] = fb
        return items

    # ================= 父分类 / 筛选器(数据驱动) =================
    def _build_classes(self, items):
        classes = [{'type_id': 'all', 'type_name': '全部'}]
        if any(i['real'] for i in items):
            classes.append({'type_id': 'new', 'type_name': '独家番号'})
        buckets = {}
        for it in items:
            if it['bk'] >= 0:
                buckets.setdefault(it['bk'], []).append(it['seq'])
        for k in sorted(buckets):
            lo, hi = min(buckets[k]), max(buckets[k])
            classes.append({'type_id': 's%02d' % k,
                            'type_name': 'FC2 %05d-%05d' % (lo, hi)})
        _MEM['classes'] = classes
        _MEM['filters'] = dict((c['type_id'], self._filters_for(c['type_id'])) for c in classes)

    def _pool(self, tid):
        items = _MEM['items']
        tid = (tid or 'all').strip()
        if tid == 'all':
            return items
        if tid == 'new':
            return [i for i in items if i['real']]
        m = re.match(r'^s(\d+)$', tid)
        if m:
            k = int(m.group(1))
            return [i for i in items if i['bk'] == k]
        return items

    def _filters_for(self, tid):
        pool = self._pool(tid)
        gids = sorted(set(i['gid'] for i in pool))
        gv = [{'n': '全部', 'v': ''}]
        for g in gids:
            gv.append({'n': '第%s批' % g, 'v': g})
        flt = []
        if len(gids) > 1:
            flt.append({'key': 'group', 'name': '分组', 'value': gv})
        flt.append({'key': 'sort', 'name': '排序', 'value': [
            {'n': '番号升序', 'v': 'asc'},
            {'n': '番号降序', 'v': 'desc'},
            {'n': '随机', 'v': 'rand'},
        ]})
        flt.append({'key': 'tail', 'name': '尾号', 'value':
                    [{'n': '全部', 'v': ''}] + [{'n': str(d), 'v': str(d)} for d in range(10)]})
        return flt

    # ================= 列表卡片 =================
    def _card(self, it):
        return {
            'vod_id': it['name'],
            'vod_name': it['name'],
            'vod_pic': it['pic'],
            'vod_year': _MEM['updated'][:4],
            'vod_remarks': '独家' if it['real'] else '第%s批' % it['gid'],
        }

    @staticmethod
    def _sort_pool(pool, mode):
        if mode == 'desc':
            return sorted(pool, key=lambda x: (-x['seq'], x['name']))
        if mode == 'rand':
            out = list(pool)
            random.Random(int(time.time() // 3600)).shuffle(out)   # 按小时定种，保证翻页稳定
            return out
        return sorted(pool, key=lambda x: (x['seq'] if x['seq'] else -1, x['name']))

    def _page(self, pool, pg):
        try:
            pg = max(1, int(pg or 1))
        except Exception:
            pg = 1
        total = len(pool)
        size = self.per_page
        count = (total + size - 1) // size if total else 1
        pg = min(pg, max(1, count))
        cut = pool[(pg - 1) * size: pg * size]
        return {
            'list': [self._card(i) for i in cut],
            'page': pg,
            'pagecount': max(1, count),
            'limit': size,
            'total': total,
        }

    # ================= 首页 =================
    def homeContent(self, filter=False):
        self._ready()
        return {
            'class': _MEM['classes'],
            'filters': _MEM['filters'] if filter else {},
            'list': self.homeVideoContent().get('list', []),
            'parse': 0,
            'jx': 0,
        }

    def homeVideoContent(self):
        if not self._ready():
            return {'list': []}
        items = _MEM['items']
        reals = [i for i in items if i['real']]
        rest = sorted([i for i in items if not i['real']], key=lambda x: -x['seq'])
        return {'list': [self._card(i) for i in (reals + rest)[:self.per_page]]}

    # ================= 分类列表 + 筛选器 + 分页 =================
    def categoryContent(self, tid, pg='1', filter=False, extend=None):
        if not self._ready():
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': self.PER_PAGE, 'total': 0}
        ex = extend if isinstance(extend, dict) else {}
        pool = self._pool(tid)
        gid = str(ex.get('group') or '').strip()
        if gid:
            pool = [i for i in pool if i['gid'] == gid]
        tail = str(ex.get('tail') or '').strip()
        if tail.isdigit():
            pool = [i for i in pool if i['num'][-1:] == tail]
        pool = self._sort_pool(pool, str(ex.get('sort') or 'asc'))
        return self._page(pool, pg)

    # ================= 详情 =================
    def _probe_m3u8(self, url):
        """拉一次 m3u8 累加 #EXTINF 得到真实时长/分片数(带缓存)。"""
        if url in _MEM['probe']:
            return _MEM['probe'][url]
        info = {'dur': 0.0, 'seg': 0}
        try:
            r = self.fetch(url, headers=self._headers(self.host + '/'), timeout=20, verify=False)
            if getattr(r, 'status_code', 0) == 200:
                r.encoding = 'utf-8'
                ds = [float(x) for x in re.findall(r'#EXTINF:\s*([\d.]+)', r.text or '')]
                info = {'dur': sum(ds), 'seg': len(ds)}
        except Exception as e:
            self._log('时长探测失败: %s' % e)
        _MEM['probe'][url] = info
        return info

    @staticmethod
    def _fmt_dur(sec):
        sec = int(sec or 0)
        if sec <= 0:
            return ''
        h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
        return '%d:%02d:%02d' % (h, m, s) if h else '%d:%02d' % (m, s)

    def _find(self, vid):
        it = _MEM['index'].get(vid)
        if it:
            return it
        q = re.sub(r'\D', '', vid or '')
        if not q:
            return None
        for i in _MEM['items']:
            if i['num'] == q or i['num'].lstrip('0') == q.lstrip('0'):
                return i
        return None

    def detailContent(self, ids):
        if not self._ready() or not ids:
            return {'list': []}
        vid = ids[0] if isinstance(ids, (list, tuple)) else ids
        it = self._find(str(vid))
        if not it:
            return {'list': []}
        host = re.sub(r'^https?://', '', it['url']).split('/')[0]
        info = self._probe_m3u8(it['url']) if self.need_probe else {'dur': 0, 'seg': 0}
        dur = self._fmt_dur(info.get('dur'))

        froms = ['酷鱼专线']
        urls = ['正片$' + it['url']]
        if self.proxy_line:
            purl = self._proxy_url(it['url'])
            if purl:
                froms.append('酷鱼备用线')
                urls.append('正片$' + purl)

        desc = ['番号: %s' % it['name'], '分组: 第%s批' % it['gid']]
        if not it['real']:
            desc.append('片单序号: %d' % it['seq'])
        if dur:
            desc.append('时长: %s (%d 个分片)' % (dur, info.get('seg', 0)))
        desc.append('来源: %s 直链 m3u8(未加密)' % host)
        desc.append('片单更新: %s' % (_MEM['updated'] or '未知'))
        desc.append('说明: 本源取自 M3U 片单，仅含番号/封面/直链，站点侧无演职员等元数据。')

        vod = {
            'vod_id': it['name'],
            'vod_name': it['name'],
            'vod_pic': it['pic'],
            'type_name': 'FC2-PPV 第%s批' % it['gid'],
            'vod_year': _MEM['updated'][:4],
            'vod_area': '日本',
            'vod_lang': '日语',
            'vod_remarks': dur or ('独家番号' if it['real'] else '第%s批' % it['gid']),
            'vod_actor': 'FC2-PPV 投稿者',
            'vod_director': '小撸怡情 大撸伤身 哥保重身体呀 悠着点',
            'vod_content': ' / '.join(desc[:2]) + '\n' + '\n'.join(desc[2:]),
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(urls),
        }
        return {'list': [vod]}

    # ================= 播放 =================
    def playerContent(self, flag, id, vipFlags=None):
        url = (id or '').strip()
        if not url.startswith('http'):
            self._ready()
            it = self._find(url)
            url = it['url'] if it else ''
        return {
            'parse': 0,
            'playUrl': '',
            'url': url,
            'header': json.dumps({'User-Agent': self.UA}),
            'jx': 0,
        }

    # ================= 搜索 =================
    def searchContent(self, key, quick=False, pg='1'):
        if not self._ready():
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': self.PER_PAGE, 'total': 0}
        k = re.sub(r'[^0-9a-zA-Z]', '', (key or '')).lower()
        q = re.sub(r'^(fc2ppv|ppvfc2|fc2|ppv)+', '', k)
        pool = []
        if q.isdigit() and q:
            qs = q.lstrip('0') or '0'
            exact = [i for i in _MEM['items'] if i['num'].lstrip('0') == qs]
            fuzzy = [i for i in _MEM['items'] if q in i['num'] and i not in exact]
            pool = exact + sorted(fuzzy, key=lambda x: (x['seq'] if x['seq'] else -1))
        elif q:
            pool = [i for i in _MEM['items'] if q in i['name'].lower().replace('-', '')]
        elif k:
            pool = [i for i in _MEM['items'] if k in i['name'].lower().replace('-', '')]
        return self._page(pool, pg)

    # ================= 本地代理线路 =================
    def _proxy_url(self, url):
        """把 m3u8 交给 localProxy 重写为绝对分片地址，兼容不发 UA 的播放器。"""
        try:
            base = self.getProxyUrl()
        except Exception:
            return ''
        if not base:
            return ''
        tag = base64.b64encode(url.encode('utf-8')).decode('utf-8').replace('=', '')
        sep = '&' if '?' in base else '?'
        return '%s%stype=m3u8&id=%s' % (base, sep, tag)

    def localProxy(self, param):
        param = param or {}
        if param.get('type') != 'm3u8':
            return [404, 'text/plain', '']
        tag = param.get('id') or ''
        try:
            url = base64.b64decode(tag + '=' * (-len(tag) % 4)).decode('utf-8')
        except Exception:
            url = ''
        if not url.startswith('http'):
            return [404, 'text/plain', '']
        try:
            r = self.fetch(url, headers=self._headers(self.host + '/'), timeout=15, verify=False)
            r.encoding = 'utf-8'
            text = r.text or ''
        except Exception as e:
            self._log('代理拉流失败: %s' % e)
            return [500, 'text/plain', '']
        root = url.split('?')[0].rsplit('/', 1)[0] + '/'
        qs = ('?' + url.split('?', 1)[1]) if '?' in url else ''
        out = []
        for line in text.splitlines():
            s = line.strip()
            if s and not s.startswith('#') and not s.startswith('http'):
                s = root + s.lstrip('/') + qs
            out.append(s)
        return [200, 'application/vnd.apple.mpegurl', '\n'.join(out)]
