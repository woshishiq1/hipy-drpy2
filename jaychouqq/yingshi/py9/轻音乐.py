# -*- coding: utf-8 -*-
"""
好听轻音乐网 (http://www.htqyy.com/) 影视仓/OK影视/TVBox py 爬虫
站点形态: 音乐分享平台 (非 MacCMS 架构), 全站 HTML 解析 + AJAX 分页
  - 分类: 12 个平级音乐类型 (无子分类), 排序筛选器 (hot/new/rating)
  - 分页: AJAX /genre/musicList/{cateId}?pageIndex={N-1}&pageSize=20&order={sort}
          总数取分类页 PageData.totalCount; 无总数时启发式判断 (返回满页则有下一页)
  - 详情: /m/play/{id} 解析标题/艺人/专辑/发布时间/播放次数/简介/封面/格式
  - 播放: http://s1.htqyy.com/play9/{songId}/{fmt}/1 (mp3 或 m4a, 需 Referer 头)
  - 搜索: /m/searchResult?id={keyword} (AJAX 返回 HTML 片段)
  - 封面: http://i.htqyy.com/img8/{songId//500}/{songId}.jpg (需 Referer)
          专辑封面: http://i.htqyy.com/img8/ZJ/{albumId}.jpg (需 Referer)
  - 图片/音频均需 Referer, 提供 localProxy 代理兜底
依赖: requests (仅此一个, 目标站无 CF 质询)
"""

import re
import sys
import json
import urllib.parse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from requests.packages.urllib3.util.retry import Retry
    requests.packages.urllib3.disable_warnings()
except ImportError:
    requests = None

sys.path.append('..')
from base.spider import Spider  # noqa: E402


class Spider(Spider):  # noqa: F811
    name = "好听轻音乐"
    host = "http://www.htqyy.com"

    # ---- 12 个平级音乐分类 (来自首页标签导航, id 11 不存在) ----
    GENRES = [
        ("1", "纯音乐"),
        ("2", "新世纪"),
        ("3", "钢琴曲"),
        ("4", "减压放松"),
        ("5", "中国音乐"),
        ("6", "天籁之音"),
        ("7", "影视原声"),
        ("8", "电子乐"),
        ("9", "背景音乐"),
        ("10", "手机铃声"),
        ("12", "胎教音乐"),
        ("13", "佛乐"),
    ]

    # 音频/图片服务器
    audio_host = "http://s1.htqyy.com"
    play_path = "http://s1.htqyy.com/play9/"
    audio_code = "1"  # 播放 code, 站点固定值
    img_host = "http://i.htqyy.com"

    def __init__(self):
        super().__init__()
        self.setup()

    def init(self, extend=""):
        self.setup()

    # ================= 基础 =================

    def setup(self):
        self.ua = ("Mozilla/5.0 (Linux; Android 11; Mobile) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36")
        self.headers = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.sess = requests.Session() if requests else None
        if self.sess is not None:
            retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
            self.sess.mount("http://", HTTPAdapter(max_retries=retry))
            self.sess.mount("https://", HTTPAdapter(max_retries=retry))
        self.page_size = 20
        self.default_pic = "https://pic.rmb.bdstatic.com/bjh/user/default.png"
        self._genre_counts = {}  # 分类总数缓存
        self.log("init done, site=" + self.host)

    def log(self, msg):
        try:
            sys.stdout.write("[好听轻音乐] " + str(msg) + "\n")
            sys.stdout.flush()
        except Exception:
            pass

    def fetch(self, url, timeout=15, referer=""):
        """带 Referer 的请求: 图片/音频服务器均校验 Referer"""
        if self.sess is None:
            return None
        try:
            hd = dict(self.headers)
            if referer:
                hd["Referer"] = referer
            res = self.sess.get(url, headers=hd, timeout=timeout, verify=False)
            if res.status_code == 200:
                res.encoding = "utf-8"
                return res
        except Exception as e:
            self.log("fetch error: %s url=%s" % (repr(e)[:120], url))
        return None

    # ================= 首页 =================

    def homeContent(self, filter):
        result = {"class": [], "filters": {}}
        for gid, gname in self.GENRES:
            result["class"].append({"type_id": gid, "type_name": gname})
        result["filters"] = self.build_filters()
        # 首页推荐: 纯音乐热门第 1 页
        videos = []
        res = self._fetch_genre_list("1", 1, "hot")
        if res:
            videos = self.parse_music_list(res.text)
        if not videos:
            res = self.fetch(self.host + "/genre/1")
            if res:
                videos = self.parse_music_list(res.text)
        result["list"] = videos[:20]
        return result

    def homeVideoContent(self):
        """OK影视/影视仓 首页推荐 Tab"""
        return self.categoryContent("1", 1, None, None)

    # ================= 分类 (排序 + 分页) =================

    def _fetch_genre_list(self, tid, pg, order):
        """AJAX 分页: /genre/musicList/{cateId}?pageIndex={N-1}&pageSize=20&order={sort}"""
        page_index = pg - 1
        url = "{0}/genre/musicList/{1}?pageIndex={2}&pageSize={3}&order={4}".format(
            self.host, tid, page_index, self.page_size, order)
        return self.fetch(url, referer=self.host + "/genre/" + str(tid))

    def _get_genre_count(self, tid):
        """从分类首页获取总歌曲数 (PageData.totalCount), 结果缓存"""
        tid = str(tid)
        if tid in self._genre_counts:
            return self._genre_counts[tid]
        res = self.fetch(self.host + "/genre/" + tid)
        if res:
            m = re.search(r'PageData\.totalCount\s*=\s*(\d+)', res.text)
            if m:
                count = int(m.group(1))
                self._genre_counts[tid] = count
                return count
        return 0

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1

        # 解析排序参数 (影视仓传 extend 为 dict, OK影视部分版本传 JSON 字符串)
        order = "hot"
        try:
            if extend:
                if isinstance(extend, str):
                    try:
                        extend = json.loads(extend)
                    except Exception:
                        extend = None
                if isinstance(extend, dict) and extend.get("order"):
                    order = str(extend["order"])
        except Exception:
            order = "hot"

        # 拉取 AJAX 列表
        res = self._fetch_genre_list(tid, pg, order)
        videos = []
        if res:
            videos = self.parse_music_list(res.text)

        # 计算总页数
        pagecount = 1
        total = self._get_genre_count(tid)
        if total > 0:
            pagecount = (total + self.page_size - 1) // self.page_size
        elif len(videos) >= self.page_size:
            # 启发式: 返回满页则可能还有下一页
            pagecount = pg + 1
        pagecount = max(pagecount, pg)

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount,
            "limit": self.page_size,
            "total": total if total > 0 else pagecount * self.page_size,
        }

    # ================= 详情 =================

    def detailContent(self, array):
        # 兼容影视仓(传 list) 与 OK影视(部分版本传 str) 两种参数形态
        if isinstance(array, (list, tuple)) and array:
            sid = str(array[0])
        else:
            sid = str(array or "")
        m_id = re.search(r"(\d+)", sid)
        if not m_id:
            return {"list": []}
        sid = m_id.group(1)

        url = self.host + "/m/play/" + sid
        res = self.fetch(url, referer=self.host + "/")
        if not res:
            return {"list": []}
        html = res.text

        info = {
            "vod_id": sid,
            "vod_name": "",
            "vod_pic": self.default_pic,
            "vod_class": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_remarks": "",
            "vod_content": "",
        }

        # 标题: <h1 class="mt mHead ...">清晨 - 班得瑞</h1>
        m = re.search(r'<h1 class="mt[^"]*"[^>]*>([^<]+)</h1>', html)
        if m:
            title = m.group(1).strip()
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                info["vod_name"] = parts[0].strip()
                info["vod_actor"] = parts[1].strip()
            else:
                info["vod_name"] = title

        # 艺术家: <span class="item">艺术家：</span><a ...>班得瑞</a>
        m = re.search(r'艺术家：</span><a[^>]*>([^<]+)</a>', html)
        if m:
            info["vod_actor"] = m.group(1).strip()

        # 播放次数: <span class="item">播放次数：</span><span>181756</span>
        m = re.search(r'播放次数：</span><span>([^<]+)</span>', html)
        if m:
            info["vod_remarks"] = m.group(1).strip() + "次播放"

        # 发布时间: <span class="item">发布时间：</span><span>2014年07月14日</span>
        m = re.search(r'发布时间：</span><span>([^<]+)</span>', html)
        if m:
            date_str = m.group(1).strip()
            ym = re.search(r'(\d{4})', date_str)
            if ym:
                info["vod_year"] = ym.group(1)
            info["vod_remarks"] = date_str

        # 所属专辑: <span class="item">所属专辑：</span><a href="/m/album/1" title="班得瑞轻音乐精选">
        m = re.search(r'所属专辑：</span><a[^>]*href="/m/album/(\d+)"[^>]*title="([^"]*)"', html)
        if m:
            album_id = m.group(1)
            album_name = m.group(2).strip()
            info["vod_class"] = album_name
            info["vod_pic"] = self.img_host + "/img8/ZJ/" + album_id + ".jpg"

        # 封面: media2.pic 优先, 其次 <img class="shadow" src="...">
        m = re.search(r'media2\.pic\s*=\s*"([^"]+)"', html)
        if m:
            pic = m.group(1).strip().split("?")[0]
            if pic.startswith("http"):
                info["vod_pic"] = pic
        else:
            m = re.search(r'<img class="shadow"[^>]*src="([^"]+)"', html)
            if m:
                pic = m.group(1).strip()
                if pic.startswith("http"):
                    info["vod_pic"] = pic

        # 简介: <div class="destWrap">...<p>...</p>...</div>
        m = re.search(r'<div class="destWrap">(.*?)</div>', html, re.S)
        if m:
            desc = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            info["vod_content"] = desc[:2000]

        # 播放: 从 media2 获取格式 (mp3/m4a)
        fmt = "mp3"
        m = re.search(r'fmt:\s*"(\w+)"', html)
        if m:
            fmt = m.group(1)

        # 构造音频直链: http://s1.htqyy.com/play9/{songId}/{fmt}/1
        audio_url = self.play_path + sid + "/" + fmt + "/" + self.audio_code

        info["vod_play_from"] = "酷鱼专线"
        info["vod_play_url"] = "播放$" + audio_url
        return {"list": [info], "parse": 0, "jx": 0}

    # ================= 播放 =================

    def playerContent(self, flag, id, *args, **kwargs):
        """兼容 OK影视(3参) / 影视仓TVBox(4参) 双壳契约:
        - OK影视/FongMi  调 (flag, id, vipFlags)            -> id 即播放地址
        - 影视仓/TVBox   调 (vod_id, source_name, flag, url) -> 播放地址在 args[1]
        """
        if len(args) >= 2:
            play_path = str(args[1] or "")    # 影视仓模式
        else:
            play_path = str(id or "")         # OK影视模式
        if "$" in play_path:
            play_path = play_path.split("$", 1)[1]

        # 从音频 URL 提取 songId 构造 Referer
        referer = self.host + "/"
        m = re.search(r'/play\d+/(\d+)/', play_path)
        if m:
            referer = self.host + "/m/play/" + m.group(1)

        return {
            "parse": 0,
            "url": play_path,
            "header": {
                "User-Agent": self.ua,
                "Referer": referer,
            },
        }

    # ================= 搜索 =================

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1

        kw = urllib.parse.quote(str(key))
        url = self.host + "/m/searchResult?id=" + kw
        res = self.fetch(url, referer=self.host + "/m/search")
        videos = []
        if res:
            videos = self.parse_search_list(res.text)
        return {
            "list": videos,
            "page": pg,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
        }

    def searchContentPage(self, key, quick, page):
        """OK影视 搜索翻页接口"""
        return self.searchContent(key, quick, page)

    # ================= 列表解析工具 =================

    def parse_music_list(self, html):
        """解析 <li class="mItem"> 列表项 (分类页 + AJAX 分页响应通用)
        每项: checkbox value(songId) / title link / artistName / albumName / playCount
        """
        videos = []
        seen = set()
        for box in re.split(r'<li class="mItem">', html)[1:]:
            # song ID: checkbox value
            m_id = re.search(r'value="(\d+)"', box)
            if not m_id:
                continue
            sid = m_id.group(1)
            if sid in seen:
                continue
            seen.add(sid)

            # 标题: <a href="/play/{id}" ... title="{title}">{title}</a>
            m_title = re.search(r'<a href="/play/\d+"[^>]*title="([^"]*)"', box)
            name = m_title.group(1).strip() if m_title else ""
            if not name:
                m_title = re.search(r'<a href="/play/\d+"[^>]*>([^<]+)</a>', box)
                name = m_title.group(1).strip() if m_title else ""
            if not name:
                continue

            # 艺人: <a href="/artist/{id}" title="{name}">
            artist = ""
            m_artist = re.search(r'<a href="/artist/\d+"[^>]*title="([^"]*)"', box)
            if m_artist:
                artist = m_artist.group(1).strip()

            # 专辑: <a href="/album/{id}" title="{name}">
            album_id = ""
            m_album = re.search(r'<a href="/album/(\d+)"', box)
            if m_album:
                album_id = m_album.group(1)

            # 播放次数: <span class="playCount">181719人听过</span>
            remarks = artist
            m_count = re.search(r'<span class="playCount">(\d+)人听过</span>', box)
            if m_count:
                remarks = m_count.group(1) + "次播放"

            # 封面: 优先用专辑封面 (列表项无歌曲封面, 专辑封面更稳定)
            pic = self.default_pic
            if album_id:
                pic = self.img_host + "/img8/ZJ/" + album_id + ".jpg"

            videos.append({
                "vod_id": sid,
                "vod_name": name[:200],
                "vod_pic": pic,
                "vod_remarks": remarks[:60],
            })
        return videos

    def parse_search_list(self, html):
        """解析搜索结果 <ul class="list"><li> 列表项
        每项: <img src="cover"/> / <a href="/m/play/{id}">{title}</a> / <em>{artist}</em>
              <div class="play" data-id="{id}" data-pic="{cover}">
        """
        videos = []
        seen = set()
        for li in re.split(r'<li>', html)[1:]:
            # 提取前先确认是搜索结果项 (非分页导航等)
            if 'data-id=' not in li and '/m/play/' not in li:
                continue

            # song ID: data-id 或 <a href="/m/play/{id}">
            sid = ""
            m_id = re.search(r'data-id="(\d+)"', li)
            if m_id:
                sid = m_id.group(1)
            else:
                m_id = re.search(r'<a href="/m/play/(\d+)"', li)
                if m_id:
                    sid = m_id.group(1)
            if not sid or sid in seen:
                continue
            seen.add(sid)

            # 标题: <a href="/m/play/{id}">{title}</a>
            name = ""
            m_title = re.search(r'<a href="/m/play/\d+">([^<]+)</a>', li)
            if m_title:
                name = m_title.group(1).strip()

            # 艺人: <em>{artist}</em>
            artist = ""
            m_artist = re.search(r'<em>([^<]*)</em>', li)
            if m_artist:
                artist = m_artist.group(1).strip()

            # 封面: data-pic 优先, 其次 <img src="...">
            pic = self.default_pic
            m_pic = re.search(r'data-pic="([^"]+)"', li)
            if m_pic:
                pic = m_pic.group(1).split("?")[0].strip()
            else:
                m_img = re.search(r'<img src="([^"]+)"', li)
                if m_img:
                    pic = m_img.group(1).split("?")[0].strip()

            if not name:
                continue

            videos.append({
                "vod_id": sid,
                "vod_name": name[:200],
                "vod_pic": pic if pic.startswith("http") else self.default_pic,
                "vod_remarks": artist[:60],
            })
        return videos

    # ================= 筛选器 =================

    def build_filters(self):
        """为每个分类生成排序筛选器 (站点无子分类, 排序即为完整筛选器)"""
        sort_options = [
            {"key": "hot", "name": "播放最多"},
            {"key": "new", "name": "最新发布"},
            {"key": "rating", "name": "评分最高"},
        ]
        filters = {}
        for gid, _ in self.GENRES:
            filters[gid] = [{
                "key": "order",
                "name": "排序",
                "value": sort_options,
            }]
        return filters

    # ================= 框架要求方法 =================

    def getName(self):
        return self.name

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        # 标准扩展名 + 站点音频 URL 格式 (/play9/{id}/{fmt}/{code})
        return any(ext in u for ext in [
            ".mp3", ".m4a", ".m3u8", ".mp4", ".flv", ".ts",
            "/mp3/", "/m4a/",
        ])

    def manualVideoCheck(self):
        """播放地址为音频直链可播, 无 VIP 校验需求"""
        return False

    def localProxy(self, param):
        """封面/音频服务器均校验 Referer, 提供本地代理兜底"""
        try:
            url = ""
            if isinstance(param, str):
                url = param
            elif isinstance(param, dict):
                for k in ['url', 'pic', 'img', 'target', 'src', 'image', 'href', 'link', 'path', 'uri']:
                    v = param.get(k)
                    if v:
                        if isinstance(v, list) and v:
                            v = v[0]
                        url = str(v)
                        break
                if not url:
                    for vv in param.values():
                        if isinstance(vv, str) and vv.startswith("http"):
                            url = vv
                            break
            elif isinstance(param, (list, tuple)) and param:
                first = param[0]
                if isinstance(first, dict):
                    for vv in first.values():
                        if isinstance(vv, str) and vv.startswith("http"):
                            url = vv
                            break
                elif isinstance(first, str):
                    url = first

            if not url or not url.startswith("http"):
                return None

            # 根据目标域名确定 Referer
            referer = self.host + "/"
            if "i.htqyy.com" in url:
                m = re.search(r'/(\d+)\.\w+$', url)
                if m:
                    referer = self.host + "/m/play/" + m.group(1)
            elif "s1.htqyy.com" in url:
                m = re.search(r'/play\d+/(\d+)/', url)
                if m:
                    referer = self.host + "/m/play/" + m.group(1)

            r = self.fetch(url, referer=referer)
            if not r:
                return None

            ctype = 'application/octet-stream'
            if hasattr(r, 'headers') and r.headers.get('Content-Type'):
                ctype = r.headers.get('Content-Type').split(';')[0].strip()
            if not ctype.startswith(('image/', 'audio/', 'video/')):
                low = url.lower().split('?')[0]
                ext_map = {
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                    '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp',
                    '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.mp4': 'video/mp4',
                }
                for ext, mt in ext_map.items():
                    if low.endswith(ext):
                        ctype = mt
                        break

            body = getattr(r, 'content', b'')
            if not body and hasattr(r, 'text'):
                body = r.text.encode('utf-8') if isinstance(r.text, str) else r.text
            if not body:
                return None

            extra = (
                "Content-Type: {0}\r\n"
                "Cache-Control: public, max-age=86400\r\n"
                "Content-Length: {1}\r\n"
            ).format(ctype, len(body))
            return [200, ctype, body, extra]
        except Exception:
            return None

    def destroy(self):
        try:
            if self.sess is not None:
                self.sess.close()
        except Exception:
            pass


# ==================== 本地测试 ====================

if __name__ == '__main__':
    spider = Spider()
    spider.init()

    print('=== 首页 (导航分类 + 排序筛选器) ===')
    home = spider.homeContent(True)
    for c in home.get('class', []):
        filters = home.get('filters', {}).get(c['type_id'], [{}])[0]
        vals = filters.get('value', []) if isinstance(filters, dict) else []
        print('  分类: {0} (id={1}) -> 筛选: {2}'.format(
            c['type_name'], c['type_id'], [v['name'] for v in vals]))
    print('  首页音乐: {0} 个'.format(len(home.get('list', []))))
    for v in home.get('list', [])[:3]:
        print('    {0} (ID: {1}, 封面: {2})'.format(v['vod_name'][:30], v['vod_id'], v['vod_pic'][:60]))

    print('\n=== 分类: 纯音乐(1) 第1页 (热门) ===')
    cat = spider.categoryContent('1', '1', False, None)
    print('  结果: {0} 个, 总页数: {1}, 总数: {2}'.format(
        len(cat.get('list', [])), cat.get('pagecount'), cat.get('total')))
    for v in cat.get('list', [])[:5]:
        print('    {0} (ID: {1}, 封面: {2})'.format(v['vod_name'][:30], v['vod_id'], v['vod_pic'][:60]))

    print('\n=== 分类: 纯音乐(1) 第2页 ===')
    cat2 = spider.categoryContent('1', '2', False, None)
    print('  结果: {0} 个, 总页数: {1}'.format(len(cat2.get('list', [])), cat2.get('pagecount')))
    for v in cat2.get('list', [])[:3]:
        print('    {0} (ID: {1})'.format(v['vod_name'][:30], v['vod_id']))

    print('\n=== 分类+排序: 钢琴曲(3) 最新发布 ===')
    cat3 = spider.categoryContent('3', '1', True, '{"order":"new"}')
    print('  结果: {0} 个'.format(len(cat3.get('list', []))))
    for v in cat3.get('list', [])[:3]:
        print('    {0} (ID: {1})'.format(v['vod_name'][:30], v['vod_id']))

    print('\n=== 详情 ===')
    target = None
    for t in [home.get('list', []), cat.get('list', []), cat2.get('list', []), cat3.get('list', [])]:
        if t:
            target = t[0]
            break
    if target:
        print('  详情: {0} (ID: {1})'.format(target['vod_name'][:30], target['vod_id']))
        detail = spider.detailContent([target['vod_id']])
        if detail.get('list'):
            d = detail['list'][0]
            print('    名称: {0}'.format(d.get('vod_name')[:50]))
            print('    年份: {0}'.format(d.get('vod_year')))
            print('    艺人: {0}'.format(d.get('vod_actor')[:50]))
            print('    分类: {0}'.format(d.get('vod_class')))
            print('    封面: {0}'.format(d.get('vod_pic')[:80]))
            print('    简介: {0}'.format((d.get('vod_content') or '')[:80]))
            print('    播放源: {0}'.format(d.get('vod_play_from')))
            print('    播放URL: {0}'.format((d.get('vod_play_url') or '')[:120]))
            purl = d.get('vod_play_url', '')
            if purl and '$' in purl:
                first_ep = purl.split('$')[-1]
                play = spider.playerContent(d.get('vod_play_from'), first_ep)
                print('    playerContent: parse={0}, url={1}'.format(
                    play.get('parse'), play.get('url', '')[:100]))
                print('    header: {0}'.format(play.get('header')))
                print('    格式可播: {0}'.format(spider.isVideoFormat(play.get('url'))))

    print('\n=== 搜索: 清晨 ===')
    search = spider.searchContent('清晨', False, '1')
    print('  结果: {0} 个'.format(len(search.get('list', []))))
    for v in search.get('list', [])[:5]:
        print('    {0} (ID: {1}, 封面: {2})'.format(v['vod_name'][:30], v['vod_id'], v['vod_pic'][:60]))

    print('\n=== 搜索: 班得瑞 ===')
    search2 = spider.searchContent('班得瑞', False, '1')
    print('  结果: {0} 个'.format(len(search2.get('list', []))))
    for v in search2.get('list', [])[:5]:
        print('    {0} (ID: {1})'.format(v['vod_name'][:30], v['vod_id']))

    print('\n=== 搜索无结果 ===')
    empty = spider.searchContent('qwertyuiop不存在的词xyz', False, '1')
    print('  结果: {0} 个'.format(len(empty.get('list', []))))

    print('\n测试完成!')
