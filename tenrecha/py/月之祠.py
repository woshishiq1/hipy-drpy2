# coding=utf-8
"""
月之祠 (moonci.com) 爬虫
站点: https://www.moonci.com
框架: MACCMS (conch 模板, 二次元动漫站, 自适应影视仓/TVBox/OK影视 空壳APP)
适配: 分类 / 子分类筛选器(字母·排序) / 分页 / 详情 / 分集线路 / 播放直链 / 搜索 / 封面

-------- 逆向要点(已实爬确认) --------
1. 顶级分类(父分类): 20=新番, 21=番剧, 22=剧场
2. 列表:        /type/{tid}.html        分页 /type/{tid}/page/{n}.html
3. 筛选器:      /browse/{tid}{12段}.html  (MacCMS 12 段, 减号分隔)
     段位(0基, 共12段):
       [0]=area  [1]=?  [2]=by(排序)  [3]=class  [4]=lang
       [5]=letter(字母)  [6]=plot  [7]=state  [8]=page  [9]=tag  [10]=version  [11]=year
     实测: 字母 -> segs[5]; 排序(time/hits/score) -> segs[2]; 分页 -> segs[8]
4. 详情:        /anime/{id}.html        信息块: 片名/主演/导演/年份/地区/类型/语言/状态/简介
5. 分集线路:    详情页 <li data-href="/anime/{id}/play/{sid}-1.html"> 线路名 "X.{n}"
              每集 <a href="/anime/{id}/play/{sid}-{nid}.html">第N集</a>
6. 播放:        /anime/{id}/play/{sid}-{nid}.html 内 var player_aaaa={...}
              encrypt=1 -> url 为百分号编码, unquote 一次即得直链(mp4/m3u8)
7. 搜索:        /search/{wd}{13段}.html   段位0=wd, 分页在 [10]
              分页链接形如 /search/{enc_wd}----------{n}---.html
"""
import re
import json
import sys
import time
import random
from urllib.parse import quote, unquote, urljoin
from lxml import etree

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    # 本地自测兜底：最小化 BaseSpider
    import requests

    class BaseSpider:
        def fetch(self, url, headers=None, timeout=20, verify=False):
            s = requests.Session()
            s.trust_env = False
            return s.get(url, headers=headers, timeout=timeout, verify=verify)

        def html(self, content):
            return etree.HTML(content)


class Spider(BaseSpider):
    name = '月之祠'
    host = 'https://www.moonci.com'

    # ---------- 顶级分类(父分类) ----------
    CATEGORIES = [
        ('20', '新番'),
        ('21', '番剧'),
        ('22', '剧场'),
    ]

    # 每页卡片数量(用于估算 total)
    PER_PAGE = 36

    _debug = False
    _categories = []

    def _log(self, msg):
        if self._debug:
            print(f'[{self.name}] {msg}')

    # ========== TVBox 固定接口 ==========
    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        if not url:
            return False
        url = url.lower().split('?')[0]
        return any(url.endswith(fmt) for fmt in
                   ['.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.mov', '.wmv'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ---------- HTTP 工具 ----------
    def _get_headers(self, referer=None):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': referer or self.host + '/',
        }

    def _fetch(self, url, referer=None, retries=4, timeout=20):
        """带重试的 GET，返回 (text, final_url)。"""
        last_text, last_url = '', ''
        for attempt in range(retries):
            try:
                if attempt > 0:
                    time.sleep(random.uniform(0.6, 1.4))
                r = self.fetch(url, headers=self._get_headers(referer), timeout=timeout, verify=False)
                if r.status_code == 200:
                    if not r.encoding or r.encoding.lower() in ('iso-8859-1', 'latin-1'):
                        r.encoding = r.apparent_encoding or 'utf-8'
                    return r.text or '', r.url
                self._log(f'请求失败 [{r.status_code}] {url}')
                last_text, last_url = '', url
            except Exception as e:
                self._log(f'请求异常 [{url}]: {e}，重试 {attempt + 1}/{retries}')
                last_text, last_url = '', url
                continue
        return last_text, last_url

    def _fix_url(self, url):
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        if not url.startswith('http'):
            return urljoin(self.host + '/', url)
        return url

    @staticmethod
    def _clean(text):
        if not text:
            return ''
        return re.sub(r'\s+', ' ', text).strip()

    # ---------- 初始化 ----------
    def init(self, extend=''):
        self._categories = [{'type_id': k, 'type_name': v} for k, v in self.CATEGORIES]
        self._log(f'初始化完成，分类 {len(self._categories)} 个')

    # ---------- 筛选器(子分类) ----------
    @staticmethod
    def _build_filters():
        """每个父分类下的筛选器(子分类): 字母 + 排序。
        值 v 直接对应 browse 段位: letter->[5], by->[2]。
        """
        letter_vals = [{'n': '全部', 'v': ''}]
        for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            letter_vals.append({'n': ch, 'v': ch})
        letter_vals.append({'n': '0-9', 'v': '0-9'})

        by_vals = [
            {'n': '全部', 'v': ''},
            {'n': '时间', 'v': 'time'},
            {'n': '人气', 'v': 'hits'},
            {'n': '评分', 'v': 'score'},
        ]
        return [
            {'key': 'letter', 'name': '字母', 'value': letter_vals},
            {'key': 'by', 'name': '排序', 'value': by_vals},
        ]

    def _filters(self):
        f = self._build_filters()
        return {tid: f for tid, _ in self.CATEGORIES}

    # ========== browse / type URL 构造 ==========
    @staticmethod
    def _browse_url(tid, letter='', by='', page=1):
        """构造 /browse/{tid}{12段}.html。段位: letter->[5], by->[2], page->[8]。"""
        segs = [''] * 12
        if by:
            segs[2] = by
        if letter:
            segs[5] = letter
        if page and int(page) > 1:
            segs[8] = str(int(page))
        return f'{Spider.host}/browse/{tid}' + '-'.join(segs) + '.html'

    @staticmethod
    def _search_url(key, page=1):
        """构造 /search/{wd}{13段}.html。段位0=wd, 分页在 [10]。"""
        segs = [''] * 14
        segs[0] = quote(key)
        if page and int(page) > 1:
            segs[10] = str(int(page))
        return f'{Spider.host}/search/' + '-'.join(segs) + '.html'

    # ========== 首页 ==========
    def homeContent(self, filter=False):
        try:
            if not self._categories:
                self.init()
            html, _ = self._fetch(self.host + '/')
            items = self._parse_cards(html) if html else []
            return {
                'class': self._categories,
                'filters': self._filters() if filter else None,
                'list': items,
                'parse': 0,
                'jx': 0,
            }
        except Exception as e:
            self._log(f'homeContent 异常: {e}')
            return {'class': self._categories, 'filters': None, 'list': [], 'parse': 0, 'jx': 0}

    def homeVideoContent(self):
        html, _ = self._fetch(self.host + '/')
        items = self._parse_cards(html) if html else []
        return {'list': items, 'parse': 0, 'jx': 0}

    # ========== 卡片解析(列表/首页/搜索通用) ==========
    def _parse_cards(self, html):
        if not html or len(html) < 600:
            return []
        items = []
        seen = set()
        try:
            root = etree.HTML(html)
        except Exception:
            return items
        for li in root.xpath('//li[contains(@class,"hl-list-item")]'):
            a = li.xpath('.//a[contains(@class,"hl-item-thumb")]')
            if not a:
                continue
            a = a[0]
            href = a.get('href', '')
            m = re.search(r'/anime/(\d+)\.html', href)
            if not m:
                continue
            vod_id = m.group(1)
            if vod_id in seen:
                continue
            seen.add(vod_id)
            title = a.get('title') or (a.get('alt') or '')
            if not title:
                t = a.xpath('.//@title | .//img/@alt')
                title = t[0] if t else ''
            pic = a.get('data-original') or a.get('data-src') or ''
            pic = self._fix_url(pic) if pic else ''
            # 备注: 更新至X集 / 年份 / 状态等
            remarks = ''
            for cand in li.xpath('.//*[contains(@class,"hl-pic-text") or '
                                 'contains(@class,"hl-vod-subtitle") or '
                                 'contains(@class,"hl-remarks") or '
                                 'contains(@class,"hl-item-text")]//text()'):
                cand = self._clean(cand)
                if cand:
                    remarks = cand
                    break
            if not remarks:
                # 退而从 li 文本中抓取状态/年份
                txt = self._clean(' '.join(li.xpath('.//text()')))
                mm = re.search(r'(更新至\d+集|全集|完结|\d{4}年|HD|TV)', txt)
                if mm:
                    remarks = mm.group(1)
            items.append({
                'vod_id': vod_id,
                'vod_name': self._clean(title)[:120],
                'vod_pic': pic,
                'vod_remarks': remarks,
            })
        return items

    # ========== 分类 / 筛选 / 分页 ==========
    def categoryContent(self, tid, pg, flt=False, extend=''):
        try:
            page = int(pg) if pg else 1
            letter, by = '', ''
            if extend:
                if isinstance(extend, str):
                    try:
                        extend = json.loads(extend)
                    except Exception:
                        extend = {}
                if isinstance(extend, dict):
                    letter = str(extend.get('letter', '') or '')
                    by = str(extend.get('by', '') or '')

            url = self._browse_url(tid, letter=letter, by=by, page=page)
            self._log(f'category [{tid}] page={page} letter={letter} by={by} -> {url}')
            html, _ = self._fetch(url)
            items = self._parse_cards(html) if html else []

            pagecount = self._parse_pagecount(html, host_part=f'/browse/{tid}')
            pagecount = max(pagecount, page)
            return {
                'list': items,
                'page': page,
                'pagecount': pagecount,
                'limit': len(items),
                'total': pagecount * (len(items) if items else self.PER_PAGE),
                'parse': 0,
                'jx': 0,
            }
        except Exception as e:
            self._log(f'categoryContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1,
                    'limit': 0, 'total': 0, 'parse': 0, 'jx': 0}

    @staticmethod
    def _parse_pagecount(html, host_part):
        """从分页数字链接推断最大页数。"""
        if not html:
            return 1
        try:
            nums = re.findall(r'>(\d+)</a>', html)
            # 仅统计出现在分页区、且 href 含 host_part 的数字
            cand = []
            for m in re.finditer(r'href="([^"]*' + re.escape(host_part) + r'[^"]*)"[^>]*>(\d+)</a>', html):
                cand.append(int(m.group(2)))
            if cand:
                return max(cand)
            # 兜底: 任意数字链接
            if nums:
                return max(int(n) for n in nums)
        except Exception:
            pass
        return 1

    # ========== 详情 ==========
    def detailContent(self, ids):
        try:
            vod_id = str(ids[0] if isinstance(ids, list) else ids)
            detail_url = f'{self.host}/anime/{vod_id}.html'
            html, _ = self._fetch(detail_url)

            if not html:
                return {'list': [{'vod_id': vod_id, 'vod_name': '获取失败',
                                  'vod_play_from': '默认', 'vod_play_url': ''}],
                        'parse': 0, 'jx': 0}

            return self._parse_detail(vod_id, html)
        except Exception as e:
            self._log(f'detailContent 异常: {e}')
            return {'list': [{'vod_id': str(ids), 'vod_name': '错误',
                              'vod_play_from': '默认', 'vod_play_url': ''}],
                    'parse': 0, 'jx': 0}

    @staticmethod
    def _info(html, *labels):
        """从详情信息块提取 标签：值。值可能位于 <a>/<span> 子标签内。"""
        for label in labels:
            # label 后紧跟 (可选空白) </em>，再捕获到 </li>/</p>/</div> 之前的所有内容，剥标签
            m = re.search(re.escape(label) + r'[：:][^<]*</em>([\s\S]*?)(?:</li>|</p>|</div>|</span>)',
                          html, re.S)
            if m:
                val = re.sub(r'<[^>]+>', ' ', m.group(1))
                val = val.replace('&nbsp;', ' ')
                val = re.sub(r'\s+', ' ', val).strip().strip('/').strip()
                if val and val not in ('内详', '未知', '暂无', ''):
                    return val
        return ''

    def _parse_detail(self, vod_id, html):
        # 标题
        m = re.search(r'<title>(.*?)(?:_|-|—|\|)', html)
        vod_name = self._clean(m.group(1)) if m else ''
        # 封面
        m = re.search(r'data-original="(https?://[^"]+)"', html)
        vod_pic = self._fix_url(m.group(1)) if m else ''
        if not vod_pic:
            m = re.search(r'<meta property="og:image"[^>]*content="([^"]+)"', html)
            if m:
                vod_pic = self._fix_url(m.group(1))

        # 信息块
        name2 = self._info(html, '片名')
        if name2:
            vod_name = name2
        vod_actor = self._info(html, '主演')
        vod_director = self._info(html, '导演')
        vod_year = self._info(html, '年份')
        vod_area = self._info(html, '地区')
        type_name = self._info(html, '类型')
        vod_lang = self._info(html, '语言')
        vod_remarks = self._info(html, '状态', '更新')
        vod_content = self._info(html, '简介')

        # 分集线路: <li data-href="/anime/{id}/play/{sid}-1.html"> + 线路名 span
        lines = {}  # sid -> name
        for li in re.finditer(
                r'data-href="/anime/' + re.escape(vod_id) + r'/play/(\d+)-1\.html"[^>]*>(.*?)</li>',
                html, re.S):
            sid = int(li.group(1))
            block = li.group(2)
            nm = re.search(r'hl-from-X[_.](\d+)[^"]*"[^>]*>([^<]+)<', block)
            if nm:
                name = self._clean(nm.group(2))
            else:
                sm = re.search(r'>([^<]{1,8})</', block)
                name = sm.group(1).strip() if sm else f'X.{sid}'
            lines.setdefault(sid, name)

        # 每集: <a href="/anime/{id}/play/{sid}-{nid}.html">第N集</a>
        eps = {}  # sid -> {nid: (name, url)}  (按 sid+nid 去重，页面会重复渲染集数锚点)
        seen = set()
        for a in re.finditer(
                r'href="/anime/' + re.escape(vod_id) + r'/play/(\d+)-(\d+)\.html"[^>]*>(.*?)</a>',
                html):
            sid = int(a.group(1))
            nid = int(a.group(2))
            if (sid, nid) in seen:
                continue
            seen.add((sid, nid))
            name = re.sub(r'<[^>]+>', '', a.group(3)).replace('&nbsp;', ' ').strip()
            # 仅接受形如「第N集」的集数链接，过滤「立即播放」等干扰锚点
            if not re.search(r'第\s*\d+\s*集', name):
                name = f'第{nid:02d}集'
            eps.setdefault(sid, {})[nid] = (name, f'{self.host}/anime/{vod_id}/play/{sid}-{nid}.html')

        play_from, play_url = [], []
        if lines:
            for sid in sorted(lines.keys()):
                segs = eps.get(sid, {})
                if not segs:
                    continue
                ordered = sorted(segs.items(), key=lambda kv: kv[0])
                play_from.append(lines[sid])
                play_url.append('#'.join(f'{n}${u}' for _, (n, u) in ordered))
        # 兜底: 没有任何线路信息时, 给一个默认播放入口
        if not play_from:
            play_from.append('默认')
            play_url.append(f'正片${self.host}/anime/{vod_id}/play/1-1.html')

        detail = {
            'vod_id': vod_id,
            'vod_name': vod_name or '未知',
            'vod_pic': vod_pic,
            'vod_actor': vod_actor,
            'vod_director': vod_director,
            'vod_year': vod_year,
            'vod_area': vod_area,
            'vod_lang': vod_lang,
            'type_name': type_name,
            'vod_remarks': vod_remarks,
            'vod_content': vod_content,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [detail], 'parse': 0, 'jx': 0}

    # ========== 播放器 ==========
    @staticmethod
    def _decode_player_url(data):
        """按 encrypt 规则 + %uXXXX 转义 解码 player_aaaa 的 url。

        实测三条 CDN 的加密与 Referer 要求：
          - apn.moedot.net   : mp4,  带 Referer 会 400，只能无 Referer
          - play.xfvod.pro   : mp4,  任意 Referer 均可
          - dl.playxf.top    : m3u8, url 含 %uXXXX (JS Unicode 转义)，解码后任意 Referer 均可
        """
        raw = (data.get('url') or '').replace('\\/', '/')
        if not raw:
            return '', ''

        def _u(s):
            # %u65B0 -> 新  (JavaScript 式 Unicode 转义)
            def _repl(m):
                try:
                    return chr(int(m.group(1), 16))
                except Exception:
                    return m.group(0)
            return re.sub(r'%u([0-9a-fA-F]{4})', _repl, s)

        enc = data.get('encrypt', 0)
        if enc == 1:
            real = unquote(_u(raw))
        elif enc == 2:
            try:
                real = unquote(_u(base64.b64decode(raw).decode('utf-8', 'ignore')))
            except Exception:
                real = unquote(_u(raw))
        else:
            real = _u(raw)
        return raw, real

    def playerContent(self, flag, pid, vipFlags=None):
        try:
            pid = str(pid or '')
            # 播放请求头：只带 UA，不带 Referer
            # (apn.moedot.net 带 Referer 直接 400 拒播，无 Referer 反而 200)
            play_header = json.dumps({'User-Agent': self._get_headers()['User-Agent']})

            # 已是直链
            if pid.startswith('http') and self.isVideoFormat(pid):
                return {'parse': 0, 'playUrl': '', 'url': pid,
                        'header': play_header, 'jx': 0}

            play_url = pid if pid.startswith('http') else self._fix_url(pid)
            html, _ = self._fetch(play_url, referer=self.host)
            if not html:
                return {'parse': 1, 'playUrl': '', 'url': play_url,
                        'header': play_header, 'jx': 0}

            data = self._extract_player(html)
            if data:
                raw, real = self._decode_player_url(data)
                if real:
                    real = self._fix_url(real)
                    parse_flag = 0 if self.isVideoFormat(real) else 1
                    return {'parse': parse_flag, 'playUrl': '', 'url': real,
                            'header': play_header, 'jx': 0}

            # 兜底: 把播放页交给 APP 解析
            return {'parse': 1, 'playUrl': '', 'url': play_url,
                    'header': play_header, 'jx': 0}
        except Exception as e:
            self._log(f'playerContent 异常: {e}')
            return {'parse': 0, 'playUrl': '', 'url': '', 'header': '', 'jx': 0}

    @staticmethod
    def _extract_player(html):
        """提取 var player_aaaa = {...}（含嵌套 vod_data，须用 </script> 锚定取到完整 JSON）"""
        try:
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});?\s*</script>', html, re.S)
            if m:
                return json.loads(m.group(1))
        except Exception:
            pass
        return None

    # ========== 搜索 ==========
    def searchContent(self, key, quick, pg='1'):
        try:
            page = int(pg) if pg else 1
            url = self._search_url(key, page)
            self._log(f'search [{key}] page={page} -> {url}')
            html, _ = self._fetch(url)
            items = self._parse_cards(html) if html else []
            pagecount = self._parse_pagecount(html, host_part='/search/')
            pagecount = max(pagecount, page)
            return {
                'list': items,
                'page': page,
                'pagecount': pagecount,
                'limit': len(items),
                'total': pagecount * (len(items) if items else self.PER_PAGE),
                'parse': 0,
                'jx': 0,
            }
        except Exception as e:
            self._log(f'searchContent 异常: {e}')
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1,
                    'limit': 0, 'total': 0, 'parse': 0, 'jx': 0}

    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)

    # ---------- 本地代理(封面防盗链兜底) ----------
    def localProxy(self, param):
        if not param or not param.startswith('http'):
            return None
        try:
            r = self.fetch(param, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': self.host + '/',
            }, timeout=(10, 15), verify=False)
            ct = r.headers.get('Content-Type', 'application/octet-stream')
            return [200, ct, r.content]
        except Exception:
            return None


if __name__ == '__main__':
    sp = Spider()
    sp._debug = True
    sp.init()

    print('\n=== 首页 / 分类 ===')
    home = sp.homeContent(True)
    print(f'分类: {len(home.get("class", []))} 个 -> {home.get("class")}')
    print(f'筛选器(新番): {home.get("filters", {}).get("20")}')
    print(f'首页推荐: {len(home.get("list", []))} 个')
    for v in home.get('list', [])[:3]:
        print(f'  {v["vod_name"]} (id={v["vod_id"]}) pic={v["vod_pic"][:60]}')

    print('\n=== 分类: 新番 第1页 ===')
    cat = sp.categoryContent('20', '1', True)
    print(f'结果 {len(cat.get("list", []))} 个, pagecount={cat.get("pagecount")}')
    for v in cat.get('list', [])[:3]:
        print(f'  {v["vod_name"]} (id={v["vod_id"]}) remarks={v.get("vod_remarks")}')

    print('\n=== 分类+筛选: 新番 字母B ===')
    cat2 = sp.categoryContent('20', '1', True, json.dumps({'letter': 'B'}))
    print(f'结果 {len(cat2.get("list", []))} 个')
    for v in cat2.get('list', [])[:5]:
        print(f'  {v["vod_name"]} (id={v["vod_id"]})')

    print('\n=== 分类分页: 新番 第2页 ===')
    cat3 = sp.categoryContent('20', '2', False)
    print(f'结果 {len(cat3.get("list", []))} 个, 与第1页不同? {set(x["vod_id"] for x in cat3.get("list",[])) != set(x["vod_id"] for x in cat.get("list",[]))}')

    print('\n=== 详情: 取第1个 ===')
    first = home['list'][0] if home.get('list') else {'vod_id': '72'}
    det = sp.detailContent([first['vod_id']])
    if det.get('list'):
        d = det['list'][0]
        print(f'  名称: {d.get("vod_name")}')
        print(f'  封面: {d.get("vod_pic", "")[:70]}')
        print(f'  主演: {d.get("vod_actor", "")[:50]}')
        print(f'  导演: {d.get("vod_director", "")[:30]}  年份: {d.get("vod_year")}  地区: {d.get("vod_area")}  类型: {d.get("type_name")}')
        print(f'  状态: {d.get("vod_remarks")}  简介: {(d.get("vod_content") or "")[:60]}')
        print(f'  线路: {d.get("vod_play_from")}')
        print(f'  播放URL样例: {d.get("vod_play_url", "")[:120]}')

    print('\n=== 播放: 逐线路验证全部可解析 ===')
    if det.get('list'):
        d = det['list'][0]
        froms = d['vod_play_from'].split('$$$')
        urls = d['vod_play_url'].split('$$$')
        ok = 0
        for i, fu in enumerate(urls):
            line_name = froms[i] if i < len(froms) else f'线路{i + 1}'
            first_ep = fu.split('#')[0]
            ep_name, ep_url = first_ep.split('$', 1)
            pl = sp.playerContent('', ep_url)
            status = 'OK' if pl.get('parse') == 0 and pl.get('url') else 'FAIL'
            if status == 'OK':
                ok += 1
            print(f'  [{line_name}] {ep_name} -> {status} parse={pl.get("parse")} url={pl.get("url","")[:80]}')
        print(f'  线路可播: {ok}/{len(urls)}')
        print(f'  播放请求头(不含Referer): {pl.get("header","")[:60]}')

    print('\n=== 搜索: 刀剑 ===')
    sres = sp.searchContent('刀剑', False, '1')
    print(f'  结果 {len(sres.get("list", []))} 个, pagecount={sres.get("pagecount")}')
    for v in sres.get('list', [])[:5]:
        print(f'    {v["vod_name"]} (id={v["vod_id"]})')
