# -*- coding: utf-8 -*-
import re
import json
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    # ------------------------------------------------------------
    # 站点配置（默认与枫叶影院一致，可通过 extend 覆盖）
    # ------------------------------------------------------------
    sites = ["https://www.cd-zj.com", "https://maihaolian.com", "https://zzztool.com"]
    base_url = sites[0]          # 默认
    cookie = ""
    debug = False                # 日志开关

    # 二次解析接口映射（基础域名）
    parse_map = {
        'YYNB': 'https://zzrs.mfdyvip.com',
        'JD4K': 'https://fgsrg.hzqingshan.com',
        'JD': 'https://fgsrg.hzqingshan.com',
        'co': 'https://zzrs.mfdyvip.com',
        'knmb': 'https://zzrs.mfdyvip.com',
    }

    # ------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------
    def _log(self, *args):
        if self.debug:
            print("[枫叶影院]", *args)

    def _headers(self, referer=None):
        """构造请求头，默认添加 Referer 和移动端 UA（与JS对齐）"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 Chrome/150.0.0.0 Mobile",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        # 默认 Referer 为 base_url（除非显式传入 None 或空字符串）
        if referer is None:
            headers["Referer"] = self.base_url + "/"
        elif referer:
            headers["Referer"] = referer
        # 若 cookie 存在则添加
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

    def _fetch(self, url, referer=None):
        try:
            if not url.startswith('http'):
                url = self.base_url + url
            rsp = self.fetch(url, headers=self._headers(referer))
            return rsp.text if rsp else ''
        except Exception as e:
            self._log('请求异常', url, e)
            return ''

    def _fix_pic(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        return u.replace('&amp;', '&')

    @staticmethod
    def _parse_extend(extend):
        """兼容多种传入格式：dict / JSON字符串 / URL查询字符串 / 分号分隔 / 管道符"""
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        extend_str = str(extend).strip()
        try:
            return json.loads(extend_str)
        except:
            pass
        if '&' in extend_str:
            d = {}
            for part in extend_str.split('&'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    d[k.strip()] = v.strip()
            if d:
                return d
        if ';' in extend_str:
            d = {}
            for part in extend_str.split(';'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    d[k.strip()] = v.strip()
            if d:
                return d
        if '|' in extend_str:
            keys = ['type', 'area', 'class', 'lang', 'letter', 'orderBy', 'year']
            parts = extend_str.split('|')
            d = {}
            for i, val in enumerate(parts):
                if i < len(keys):
                    d[keys[i]] = val.strip()
            return d
        return {}

    def _error_response(self, err, resp_type='list'):
        """统一错误返回格式"""
        msg = str(err) if err else "未知错误"
        self._log("错误:", msg)
        if resp_type == 'play':
            return {"parse": 0, "msg": msg}
        elif resp_type == 'home':
            return {"class": [], "filters": {}, "msg": msg}
        else:  # list / detail / search
            return {"list": [], "pagecount": 1, "msg": msg}

    # ------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------
    def init(self, extend=""):
        self._log("初始化，extend:", extend)
        if isinstance(extend, str) and extend.strip():
            try:
                extend = json.loads(extend)
            except:
                extend = {}
        if not isinstance(extend, dict):
            extend = {}

        # 站点列表
        if 'sites' in extend and isinstance(extend['sites'], list) and extend['sites']:
            self.sites = extend['sites']
            idx = int(extend.get('sitesIndex', 0))
            if 0 <= idx < len(self.sites):
                self.base_url = self.sites[idx]
        # 直接指定 host（优先级高于 sites）
        if 'host' in extend and extend['host']:
            self.base_url = extend['host'].rstrip('/')
        # Cookie
        if 'cookie' in extend:
            self.cookie = extend['cookie']
        elif 'fyck' in extend:
            try:
                with open(extend['fyck'], 'r', encoding='utf-8') as f:
                    self.cookie = f.read().strip()
                self._log("已从文件读取Cookie:", self.cookie[:20] + "...")
            except Exception as e:
                self._log("读取Cookie文件失败:", e)
        # 若 cookie 仍为空，设置默认值（与JS保持一致）
        if not self.cookie:
            self.cookie = "verify_success=1"
            self._log("使用默认Cookie: verify_success=1")

        self.debug = extend.get('debug', False)
        self._log("当前站点:", self.base_url)

    def getName(self):
        return '枫叶影院'

    # ------------------------------------------------------------
    # 首页（导航 + 筛选器）
    # ------------------------------------------------------------
    def homeContent(self, filter):
        return {
            "class": [
                {'type_id': "/label/qq", 'type_name': "腾讯VIP精选"},
                {'type_id': "/label/bli", 'type_name': "B站VIP精选"},
                {'type_id': "/label/youku", 'type_name': "优酷VIP精选"},
                {"type_id": "2", "type_name": "电视剧"},
                {"type_id": "1", "type_name": "电影"},
                {"type_id": "4", "type_name": "动漫"},
                {"type_id": "3", "type_name": "综艺"},
                {"type_id": "5", "type_name": "热门短剧"},
            ],
            "filters": self._build_filters()
        }

    # ----- 筛选器（动态生成年份）-----
    def _build_filters(self):
        area = [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
                {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"},
                {"n": "日本", "v": "日本"}, {"n": "泰国", "v": "泰国"}, {"n": "新加坡", "v": "新加坡"},
                {"n": "马来西亚", "v": "马来西亚"}, {"n": "印度", "v": "印度"}, {"n": "英国", "v": "英国"},
                {"n": "法国", "v": "法国"}, {"n": "加拿大", "v": "加拿大"}, {"n": "西班牙", "v": "西班牙"},
                {"n": "俄罗斯", "v": "俄罗斯"}, {"n": "其它", "v": "其它"}]

        # 动态年份：从当前年份往前推23年
        current_year = datetime.now().year
        years = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(current_year, current_year - 23, -1)]

        lang = [{"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "英语", "v": "英语"},
                {"n": "粤语", "v": "粤语"}, {"n": "闽南语", "v": "闽南语"}, {"n": "韩语", "v": "韩语"},
                {"n": "日语", "v": "日语"}, {"n": "法语", "v": "法语"}, {"n": "德语", "v": "德语"},
                {"n": "其它", "v": "其它"}]
        sort = [{"n": "时间", "v": "time"}, {"n": "人气", "v": "hits"}, {"n": "评分", "v": "score"}]
        letter = [{"n": "全部", "v": ""}] + [{"n": c, "v": c} for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + [{"n": "0-9", "v": "0-9"}]

        return {
            "2": [
                {"key": "class", "name": "类型",
                 "value": [{"n": "全部", "v": "2"}, {"n": "国产剧", "v": "13"}, {"n": "日韩剧", "v": "15"},
                           {"n": "海外剧", "v": "16"}]},
                {"key": "area", "name": "地区", "value": area},
                {"key": "genre", "name": "剧情", "value": [{"n": v[0], "v": v[1]} for v in
                                                           [("全部", ""), ("古装", "古装"), ("战争", "战争"),
                                                            ("青春偶像", "青春偶像"), ("喜剧", "喜剧"),
                                                            ("家庭", "家庭"), ("犯罪", "犯罪"), ("动作", "动作"),
                                                            ("奇幻", "奇幻"), ("剧情", "剧情"), ("历史", "历史"),
                                                            ("经典", "经典"), ("乡村", "乡村"), ("情景", "情景"),
                                                            ("商战", "商战"), ("网剧", "网剧"), ("其他", "其他")]]},
                {"key": "year", "name": "年份", "value": years},
                {"key": "lang", "name": "语言", "value": lang},
                {"key": "letter", "name": "字母", "value": letter},
                {"key": "sort", "name": "排序", "value": sort},
            ],
            "1": [
                {"key": "class", "name": "类型",
                 "value": [{"n": "全部", "v": "1"}, {"n": "动作片", "v": "6"}, {"n": "喜剧片", "v": "7"},
                           {"n": "恐怖片", "v": "8"}, {"n": "科幻片", "v": "9"}, {"n": "爱情片", "v": "10"},
                           {"n": "剧情片", "v": "11"}, {"n": "战争片", "v": "12"}, {"n": "纪录片", "v": "20"}]},
                {"key": "area", "name": "地区", "value": area},
                {"key": "genre", "name": "剧情", "value": [{"n": v[0], "v": v[1]} for v in
                                                           [("全部", ""), ("喜剧", "喜剧"), ("爱情", "爱情"),
                                                            ("恐怖", "恐怖"), ("动作", "动作"), ("科幻", "科幻"),
                                                            ("剧情", "剧情"), ("战争", "战争"), ("警匪", "警匪"),
                                                            ("犯罪", "犯罪"), ("动画", "动画"), ("奇幻", "奇幻"),
                                                            ("武侠", "武侠"), ("冒险", "冒险"), ("枪战", "枪战"),
                                                            ("悬疑", "悬疑"), ("惊悚", "惊悚"), ("经典", "经典"),
                                                            ("青春", "青春"), ("文艺", "文艺"), ("微电影", "微电影"),
                                                            ("古装", "古装"), ("历史", "历史"), ("运动", "运动"),
                                                            ("农村", "农村"), ("儿童", "儿童"),
                                                            ("网络电影", "网络电影")]]},
                {"key": "year", "name": "年份", "value": years},
                {"key": "lang", "name": "语言", "value": lang},
                {"key": "letter", "name": "字母", "value": letter},
                {"key": "sort", "name": "排序", "value": sort},
            ],
            "4": [
                {"key": "class", "name": "类型",
                 "value": [{"n": "全部", "v": "4"}, {"n": "国产动漫", "v": "25"}, {"n": "日韩动漫", "v": "26"}]},
                {"key": "genre", "name": "剧情", "value": [{"n": v[0], "v": v[1]} for v in
                                                           [("全部", ""), ("情感", "情感"), ("科幻", "科幻"),
                                                            ("热血", "热血"), ("推理", "推理"), ("搞笑", "搞笑"),
                                                            ("冒险", "冒险"), ("奇幻", "奇幻"), ("战斗", "战斗"),
                                                            ("校园", "校园"), ("萝莉", "萝莉"), ("治愈", "治愈"),
                                                            ("原创", "原创"), ("亲子", "亲子"), ("益智", "益智"),
                                                            ("励志", "励志"), ("其他", "其他")]]},
                {"key": "area", "name": "地区",
                 "value": [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
                           {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"},
                           {"n": "日本", "v": "日本"}, {"n": "法国", "v": "法国"}, {"n": "英国", "v": "英国"},
                           {"n": "其它", "v": "其它"}]},
                {"key": "year", "name": "年份", "value": years},
                {"key": "lang", "name": "语言", "value": lang},
                {"key": "letter", "name": "字母", "value": letter},
                {"key": "sort", "name": "排序", "value": sort},
            ],
            "3": [
                {"key": "class", "name": "类型",
                 "value": [{"n": "全部", "v": "3"}, {"n": "大陆综艺", "v": "21"}, {"n": "日韩综艺", "v": "22"}]},
                {"key": "genre", "name": "剧情", "value": [{"n": v[0], "v": v[1]} for v in
                                                           [("全部", ""), ("选秀", "选秀"), ("情感", "情感"),
                                                            ("访谈", "访谈"), ("播报", "播报"), ("音乐", "音乐"),
                                                            ("美食", "美食"), ("旅游", "旅游"), ("搞笑", "搞笑"),
                                                            ("游戏", "游戏"), ("亲子", "亲子"), ("其它", "其它")]]},
                {"key": "area", "name": "地区",
                 "value": [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"},
                           {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"},
                           {"n": "日本", "v": "日本"}, {"n": "英国", "v": "英国"}, {"n": "其它", "v": "其它"}]},
                {"key": "year", "name": "年份", "value": years},
                {"key": "lang", "name": "语言", "value": lang},
                {"key": "letter", "name": "字母", "value": letter},
                {"key": "sort", "name": "排序", "value": sort},
            ],
        }

    # ------------------------------------------------------------
    # 首页视频
    # ------------------------------------------------------------
    def homeVideoContent(self):
        html = self._fetch('/')
        return {"list": self._parse_video_list(html, is_home=True)}

    # ------------------------------------------------------------
    # 分类列表（支持筛选 + 多站点 + 分页）
    # ------------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
            tid = str(tid)
            is_label = tid.startswith('/label')
            extend = self._parse_extend(extend)

            args = {}
            if isinstance(filter, dict):
                args.update({k: str(v) for k, v in filter.items() if v})
            if isinstance(extend, dict):
                args.update({k: str(v) for k, v in extend.items() if v and k not in args})

            type_val = args.get('class', args.get('tid', tid))
            area = args.get('area', '')
            genre = args.get('genre', '')
            year = args.get('year', '')
            lang = args.get('lang', '')
            letter = args.get('letter', '')
            sort = args.get('sort', '')

            if is_label:
                url = f'{tid}/page/{page}.html'
                html = self._fetch(url)
                items = self._parse_video_list(html)
                total = page if len(items) < 24 else page + 2
                return {"list": items, "page": page, "pagecount": total, "limit": 24, "total": total * 24}

            # 确定前缀
            if 'zzztool' in self.base_url:
                prefix = 'list'
            else:
                prefix = 'cupfox-list'

            if not area and not genre and not year and not lang and not letter and not sort:
                url = f'/{prefix}/{type_val}--------{page}---.html'
            else:
                url = f'/{prefix}/{type_val}-{area}-{sort}-{genre}-{lang}-{letter}--{page}---{year}.html'

            self._log('分类URL:', self.base_url + url)
            html = self._fetch(url)
            items = self._parse_video_list(html)

            # 提取总页数
            total = page
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                tail = soup.select_one('a.page-link:contains("尾页")')
                if tail:
                    m = re.search(r'---(\d+)---', tail.get('href', ''))
                    if m:
                        total = int(m.group(1))
                else:
                    tip = soup.select_one('.page-tip')
                    if tip:
                        m = re.search(r'/(\d+)页', tip.get_text())
                        if m:
                            total = int(m.group(1))
                    else:
                        next_links = soup.select('.module-footer .page-next')
                        if next_links:
                            href = next_links[-1].get('href', '')
                            nums = re.findall(r'\d+', href)
                            if len(nums) >= 2:
                                total = int(nums[1])
            if not items:
                total = 0

            return {"list": items, "page": page, "pagecount": total, "limit": 36, "total": 9999}
        except Exception as e:
            return self._error_response(e, 'list')

    # ------------------------------------------------------------
    # 列表解析（支持多种DOM结构，增加安全验证检测）
    # ------------------------------------------------------------
    def _parse_video_list(self, html, is_home=False, is_search=False):
        if not html:
            return []
        # 检测是否触发安全验证
        if "系统安全验证" in html:
            self._log("触发系统安全验证，请更新Cookie")
            return []
        soup = BeautifulSoup(html, 'html.parser')
        videos, seen = [], set()
        is_zzz = 'zzztool' in self.base_url

        if is_zzz:
            cards = soup.select('.module-item')
        else:
            cards = soup.select('a.public-list-exp')

        for el in cards:
            try:
                if is_zzz:
                    a = el.select_one('a')
                    vod_id = a.get('href', '') if a else ''
                    if is_search or is_home:
                        name_tag = el.select_one('.module-card-item-title strong')
                        vod_name = name_tag.get_text(strip=True) if name_tag else ''
                    else:
                        vod_name = a.get('title', '').strip() if a else ''
                        if not vod_name:
                            name_tag = el.select_one('.module-card-item-title strong')
                            vod_name = name_tag.get_text(strip=True) if name_tag else ''
                    img = el.select_one('.module-item-pic img')
                    vod_pic = img.get('data-src', '') if img else ''
                    remarks = el.select_one('.module-item-note')
                    vod_remarks = remarks.get_text(strip=True) if remarks else ''
                    vod_year = vod_remarks
                else:
                    # 标准站点
                    a = el if el.name == 'a' else el.select_one('a.public-list-exp')
                    if not a:
                        continue
                    vod_id = a.get('href', '')
                    if is_search:
                        title_el = soup.select_one(f'a.thumb-txt[href="{vod_id}"]')
                        vod_name = title_el.text.strip() if title_el else ''
                    else:
                        vod_name = a.get('title', '').strip()
                        if not vod_name:
                            img = a.select_one('img')
                            vod_name = img.get('alt', '') if img else ''
                    img = a.select_one('img')
                    vod_pic = self._fix_pic(img.get('data-src', '')) if img else ''
                    remark_el = a.select_one('.ft2') or a.select_one('.public-list-prb')
                    vod_remarks = remark_el.text.strip() if remark_el else ''
                    span = ','.join([s.text for s in a.select('span.public-prt')])
                    vod_year = span

                if not vod_id or not vod_name:
                    continue
                m = re.search(r'/detail/(\d+)\.html', vod_id)
                if m:
                    vod_id = m.group(1)
                else:
                    continue
                if vod_id in seen:
                    continue
                seen.add(vod_id)

                videos.append({
                    "vod_id": vod_id,
                    "vod_name": vod_name.strip(),
                    "vod_pic": vod_pic,
                    "vod_remarks": vod_remarks,
                    "vod_year": vod_year
                })
            except Exception as e:
                self._log('解析条目异常:', e)
                continue
        return videos

    def _parse_search_list(self, html):
        return self._parse_video_list(html, is_search=True)

    # ------------------------------------------------------------
    # 详情页（兼容多站点 + 线路去重）
    # ------------------------------------------------------------
    def detailContent(self, ids):
        result = {"list": []}
        vid = ids[0].split(',')[0].strip()
        try:
            html = self._fetch(f'/detail/{vid}.html')
            if not html:
                return result

            soup = BeautifulSoup(html, 'html.parser')
            is_zzz = 'zzztool' in self.base_url

            if is_zzz:
                # ----- zzztool 结构 -----
                vod_name = soup.select_one('.module-info-heading h1')
                vod_name = vod_name.text.strip() if vod_name else ''
                vod_pic = soup.select_one('.module-item-pic img')
                vod_pic = self._fix_pic(vod_pic.get('data-src', '')) if vod_pic else ''
                director = actor = ''
                for item in soup.select('.module-info-item'):
                    t = item.select_one('.module-info-item-title')
                    c = item.select_one('.module-info-item-content')
                    if not t or not c:
                        continue
                    tt = t.get_text(strip=True)
                    cc = c.get_text(strip=True)
                    if '导演' in tt:
                        director = cc
                    elif '主演' in tt:
                        actor = cc
                vod_content = soup.select_one('.module-info-introduction-content p')
                vod_content = vod_content.get_text(strip=True) if vod_content else ''
                # 播放列表
                play_from, play_url = [], []
                name_counts = {}
                for tab in soup.select('.mx-anthology-tab'):
                    label = tab.select_one('.mx-anthology-tab-label')
                    if label:
                        raw = label.get_text(strip=True)
                        if raw:
                            name_counts[raw] = name_counts.get(raw, 0) + 1
                            if name_counts[raw] > 1:
                                play_from.append(f"{raw}-{name_counts[raw]}")
                            else:
                                play_from.append(raw)
                for panel in soup.select('.mx-anthology-panel'):
                    eps = []
                    for a in panel.select('.mx-anthology-item a'):
                        href = a.get('href', '')
                        title = a.get_text(strip=True)
                        if href and title:
                            eps.append(f"{title}${href}")
                    play_url.append('#'.join(reversed(eps)))

                result["list"].append({
                    "vod_id": vid,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_director": director,
                    "vod_actor": actor,
                    "vod_content": vod_content,
                    "vod_play_from": "$$$".join(play_from),
                    "vod_play_url": "$$$".join(play_url),
                })

            else:
                # ----- 标准结构 -----
                vod_name = soup.select_one('h3.slide-info-title')
                vod_name = vod_name.text.strip() if vod_name else ''
                vod_pic = soup.select_one('img.lazy')
                vod_pic = self._fix_pic(vod_pic.get('data-src', '')) if vod_pic else ''
                vod_director = vod_actor = ''
                for el in soup.select('.slide-info'):
                    text = el.get_text(' ').strip()
                    if text.startswith('导演：'):
                        vod_director = text.replace('导演：', '').strip()
                    elif text.startswith('演员：'):
                        vod_actor = text.replace('演员：', '').strip()
                vod_content = soup.select_one('#height_limit')
                vod_content = vod_content.get_text(' ', strip=True) if vod_content else ''

                play_from, play_url = [], []
                name_counts = {}
                for tab in soup.select('.anthology-tab a.swiper-slide'):
                    raw = re.sub(r'<[^>]+>', '', str(tab)).strip() or tab.get_text(' ', strip=True).strip()
                    if raw:
                        name_counts[raw] = name_counts.get(raw, 0) + 1
                        play_from.append(f"{raw}-{name_counts[raw]}" if name_counts[raw] > 1 else raw)

                tab_blocks = soup.select('.anthology-list-box')
                for block in tab_blocks:
                    eps = []
                    for a in block.select('li a'):
                        href = a.get('href', '')
                        m = re.search(r'/play/(.*?)\.html', href)
                        if m:
                            eps.append(f"{a.text.strip()}${vid}-{m.group(1)}")
                    play_url.append('#'.join(reversed(eps)))

                valid_from = [pf for i, pf in enumerate(play_from) if i < len(play_url)]
                result["list"].append({
                    "vod_id": vid,
                    "vod_name": vod_name,
                    "vod_pic": vod_pic,
                    "vod_director": vod_director,
                    "vod_actor": vod_actor,
                    "vod_content": vod_content,
                    "vod_play_from": "$$$".join(valid_from),
                    "vod_play_url": "$$$".join(play_url),
                })

        except Exception as e:
            return self._error_response(e, 'detail')
        return result

    # ------------------------------------------------------------
    # 搜索（直接调用统一解析）
    # ------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg) if pg else 1
            decoded = urllib.parse.unquote(key)
            if 'zzztool' in self.base_url:
                prefix = 'search'
            else:
                prefix = 'cupfox-search'
            url = f'/{prefix}/{urllib.parse.quote(decoded)}----------{page}---.html'
            html = self._fetch(url)
            items = self._parse_search_list(html)
            total = page if items else 0
            return {"list": items, "page": page, "pagecount": total, "limit": 36, "total": len(items)}
        except Exception as e:
            return self._error_response(e, 'search')

    # ------------------------------------------------------------
    # 播放（封装二次解析）
    # ------------------------------------------------------------
    def _resolve_video_url(self, video_url, play_id=None):
        """二次解析：获取真实播放地址"""
        # 确定解析线路基础域名
        line_key = play_id if play_id else re.split(r'[-_]', video_url)[0]
        base_domain = self.parse_map.get(line_key)
        if not base_domain:
            self._log('未匹配到解析线路，使用默认 JD4K')
            base_domain = self.parse_map.get('JD4K', 'https://fgsrg.hzqingshan.com')

        # 获取 token
        token_url = f'{base_domain}/player/?url={video_url}'
        token_page = self._fetch(token_url, referer=self.base_url)
        if not token_page:
            raise Exception("token 获取失败")

        token = ''
        token_match = re.search(r'data-te="([^"]+)"', token_page)
        if token_match:
            token = token_match.group(1)
        else:
            soup = BeautifulSoup(token_page, 'html.parser')
            el = soup.select_one('#player-data')
            if el:
                token = el.get('data-te', '')
        if not token:
            raise Exception("未找到 token")

        # 请求真实播放地址
        api_url = f'{base_domain}/player/mplayer.php'
        headers = self._headers()
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'

        try:
            if hasattr(self, 'post'):
                resp = self.post(api_url, data={'url': video_url, 'token': token}, headers=headers)
            else:
                resp = requests.post(api_url, data={'url': video_url, 'token': token}, headers=headers, timeout=10)
        except Exception as e:
            raise Exception(f"二次解析请求异常: {e}")

        try:
            if hasattr(resp, 'json'):
                data = resp.json()
            else:
                data = json.loads(resp.text)
        except:
            raise Exception("响应不是合法 JSON")

        final_url = data.get('url', '')
        if not final_url:
            raise Exception("解析结果为空")

        if final_url.startswith('/playproxy.php'):
            final_url = base_domain + final_url
        return final_url

    def playerContent(self, flag, id, vipFlags):
        try:
            # 解析播放id
            if '$' in id:
                parts = id.split('$')
                play_path = parts[-1]
            else:
                play_path = id

            # 直链直接返回
            if play_path.startswith('http') and ('.m3u8' in play_path or '.mp4' in play_path):
                return {"parse": 0, "url": play_path, "header": self._headers()}

            # 构造播放页URL
            if not play_path.startswith('http'):
                if play_path.startswith('/play/'):
                    play_url = self.base_url + play_path
                else:
                    play_url = f'{self.base_url}/play/{play_path}.html'
            else:
                play_url = play_path

            html = self._fetch(play_url)
            if not html:
                return {"parse": 0, "url": "", "msg": "播放页获取失败"}

            # 提取 video_url 和 play_id
            video_url = ''
            play_id = ''

            # 1. player_aaaa JSON
            m = re.search(r'player_aaaa=(.*?)</script>', html, re.S)
            if m:
                try:
                    pd = json.loads(m.group(1))
                    video_url = pd.get('url', '')
                    play_id = pd.get('from', '')
                except:
                    pass

            # 2. <video> 标签
            if not video_url:
                m2 = re.search(r'<video[^>]+src="([^"]+)"', html, re.I)
                if m2:
                    video_url = m2.group(1)

            # 3. <iframe>
            if not video_url:
                m3 = re.search(r'<iframe[^>]+src="([^"]+)"', html, re.I)
                if m3:
                    video_url = m3.group(1)

            # 4. 直接 m3u8 正则
            if not video_url:
                m4 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                if m4:
                    video_url = m4.group(1)

            if not video_url:
                return {"parse": 0, "url": "", "msg": "未找到视频地址"}

            # 直链判断
            if video_url.startswith('http') and ('.m3u8' in video_url or '.mp4' in video_url):
                return {"parse": 0, "url": video_url, "header": self._headers(referer=self.base_url)}

            # 二次解析
            final_url = self._resolve_video_url(video_url, play_id)
            return {"parse": 0, "url": final_url, "header": self._headers(referer=self.base_url)}

        except Exception as e:
            self._log('playerContent 异常:', e)
            # 兜底：返回原始播放页让外部解析
            return {"parse": 1, "url": play_url if 'play_url' in locals() else id}

    # ------------------------------------------------------------
    # 其他必须方法
    # ------------------------------------------------------------
    def localProxy(self, param=''):
        return {}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False


if __name__ == '__main__':
    sp = Spider()
    sp.init()
    # print(sp.categoryContent('1', '1', {}, {}))
    # print(sp.playerContent('', '20067-6-189', []))
