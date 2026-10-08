# coding=utf-8
"""
数据源：https://v.qq.com/channel/child 下的儿歌/少儿专辑
功能：分类（专辑）、详情（专辑集数）、播放、搜索、封面抓取
"""
import re, json, html, uuid
import requests
from urllib.parse import parse_qs
from base.spider import Spider


class Spider(Spider):
    def __init__(self):
        # 站点标识
        self.name = "xbeg"
        # 腾讯视频域名
        self.host = "https://v.qq.com"
        # 儿童频道 getPage 接口（专辑列表）
        self.channel_api = "https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/getPage?video_appid=3000010&vversion_platform=2"
        # 搜索API
        self.search_api = "https://pbaccess.video.qq.com/trpc.videosearch.mobile_search.MultiTerminalSearch/MbSearch?vversion_platform=2"
        # 专辑集数列表
        self.album_vids_api = "https://access.video.qq.com/fcgi/PlayVidListReq"
        # 批量获取视频标题/集数/时长
        self.vid_detail_api = "https://union.video.qq.com/fcgi-bin/data"
        # 视频信息/播放地址解析API
        self.video_info_api = "http://vv.video.qq.com/getinfo"
        # 通用请求头
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Content-Type': 'application/json',
            'Origin': self.host,
            'Referer': self.host + '/channel/child'
        }

    def getName(self):
        return self.name

    def init(self, extend=''):
        pass

    # ---------------------- 底层请求工具 ----------------------

    def _get(self, url, params=None):
        """GET请求封装"""
        r = requests.get(url, headers=self.header, params=params, timeout=15)
        r.encoding = 'utf-8'
        return r.text

    def _post_json(self, url, data):
        """POST JSON请求封装"""
        r = requests.post(url, headers=self.header, json=data, timeout=15)
        r.encoding = 'utf-8'
        return r.json()

    def _fix_url(self, url):
        """补全相对URL"""
        if not url:
            return ''
        if url.startswith('//'):
            return 'https:' + url
        if url.startswith('/'):
            return self.host + url
        return url

    def _clean_text(self, text):
        """清洗标题：去高亮标签、HTML实体、空白"""
        if not text:
            return ''
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()

    def _fmt_duration(self, seconds):
        """秒数转 mm:ss"""
        try:
            s = int(seconds)
            return f"{s // 60:02d}:{s % 60:02d}"
        except Exception:
            return ''

    def _extract_vid(self, item):
        """从搜索item中提取vid：优先doc.id，其次dataKey"""
        vid = item.get('doc', {}).get('id')
        if vid:
            return vid
        video_info = item.get('videoInfo', {})
        vd = video_info.get('videoDoc', {})
        data_key = vd.get('dataKey', '')
        parsed = parse_qs(data_key)
        vids = parsed.get('vid', [])
        return vids[0] if vids else None

    def _get_video_basic(self, vid):
        """通过getinfo接口获取标题等基础信息"""
        try:
            url = f"{self.video_info_api}?vids={vid}&platform=101001&charge=0&otype=json"
            text = self._get(url)
            m = re.search(r'QZOutputJson\s*=\s*(\{.*?\});\s*$', text, re.S)
            if not m:
                return {}
            data = json.loads(m.group(1))
            vl = data.get('vl', {})
            vi_list = vl.get('vi', [])
            if not vi_list:
                return {}
            vi = vi_list[0]
            return {
                'title': vi.get('ti', ''),
                'vid': vi.get('vid', '')
            }
        except Exception:
            return {}

    # ---------------------- 专辑列表解析 ----------------------

    def _channel_page_body(self, page_context=None):
        """构造儿童频道 getPage 请求体"""
        return {
            "page_params": {
                "page_type": "channel",
                "page_id": "100150",
                "scene": "channel",
                "new_mark_label_enabled": "1",
                "vl_to_mvl": "",
                "ad_exp_ids": "",
                "ams_cookies": "",
                "ad_trans_data": json.dumps({"ad_request_id": "test", "game_sessions": []}),
                "skip_privacy_types": "0",
                "support_click_scan": "1"
            },
            "page_bypass_params": {
                "params": {
                    "platform_id": "2",
                    "caller_id": "3000010",
                    "data_mode": "default",
                    "user_mode": "default",
                    "specified_strategy": "",
                    "page_type": "channel",
                    "page_id": "100150",
                    "scene": "channel",
                    "new_mark_label_enabled": "1"
                },
                "scene": "channel",
                "app_version": "",
                "abtest_bypass_id": ""
            },
            "page_context": page_context
        }

    def _make_page_context(self, pg):
        """根据页码生成可直接翻页的 page_context"""
        return {
            "page_index": str(pg),
            "sdk_page_ctx": json.dumps({
                "page_offset": pg,
                "page_size": 5,
                "used_module_num": 5
            }),
            "enable_mvl_bypass": "1"
        }

    def _parse_albums_from_card(self, card):
        """递归解析 CardList 中的专辑卡片"""
        albums = []
        params = card.get('params', {})
        cid = params.get('cid')
        title = params.get('title')
        if cid and title:
            pic = (params.get('pic_276x386') or
                   params.get('image_url_vertical') or
                   params.get('ready_image_url') or
                   params.get('image_url') or '')
            albums.append({
                'cid': cid,
                'title': self._clean_text(title),
                'title_pc': self._clean_text(params.get('title_pc', '')),
                'pic': self._fix_url(pic),
                'vid': params.get('vid')
            })
        children_list = card.get('children_list', {})
        lst = children_list.get('list', {}) if children_list else {}
        for child in lst.get('cards', []):
            albums.extend(self._parse_albums_from_card(child))
        return albums

    def _get_channel_albums(self, pg=1):
        """
        获取儿童频道第 pg 页的专辑列表
        返回: (albums, has_next)
        """
        try:
            page_context = None if pg == 1 else self._make_page_context(pg)
            resp = self._post_json(self.channel_api, self._channel_page_body(page_context))
            data = resp.get('data', {})
            cards = data.get('CardList', [])
            albums = []
            for card in cards:
                albums.extend(self._parse_albums_from_card(card))
            # 去重，保持顺序
            seen = set()
            uniq = []
            for a in albums:
                if a['cid'] in seen:
                    continue
                seen.add(a['cid'])
                uniq.append(a)
            has_next = len(uniq) > 0
            return uniq, has_next
        except Exception:
            return [], False

    # ---------------------- 专辑集数获取 ----------------------

    def _get_album_vids(self, cid, page_size=100):
        """根据 cid 获取专辑下所有 vid"""
        vids = []
        try:
            url = (f"{self.album_vids_api}?raw=1&vappid=17174171"
                   f"&vsecret=a06edbd9da3f08db096edab821b3acf3c27ee46e6d57c2fa"
                   f"&page_size={page_size}&type=4&cid={cid}")
            text = self._get(url)
            data = json.loads(text)
            vid_list = data.get('data', {}).get('vid_list', [])
            for item in vid_list:
                vid = item.get('vid')
                if vid:
                    vids.append(vid)
        except Exception:
            pass
        return vids

    def _get_vid_details(self, vids):
        """批量获取 vid 的标题/集数/时长/封面，返回 {vid: {...}}"""
        result = {}
        if not vids:
            return result
        # union 接口单次不宜过长，分批
        chunk_size = 30
        for i in range(0, len(vids), chunk_size):
            chunk = vids[i:i + chunk_size]
            try:
                vid_str = ','.join(chunk)
                url = (f"{self.vid_detail_api}?otype=json&tid=682&appid=20001238"
                       f"&appkey=6c03bbe9658448a4&union_platform=1&idlist={vid_str}")
                text = self._get(url)
                m = re.search(r'QZOutputJson\s*=\s*(\{.*?\});\s*$', text, re.S)
                if not m:
                    continue
                data = json.loads(m.group(1))
                results = data.get('results', [])
                for idx, res in enumerate(results):
                    if idx >= len(chunk):
                        break
                    fields = res.get('fields', {})
                    vid = chunk[idx]
                    result[vid] = {
                        'title': self._clean_text(fields.get('c_title_output') or fields.get('title') or ''),
                        'episode': self._clean_text(fields.get('episode') or ''),
                        'duration': fields.get('duration', 0) or 0,
                        'pic': fields.get('pic160x90', '')
                    }
            except Exception:
                continue
        return result

    # ---------------------- 搜索API调用 ----------------------

    def _do_search(self, query, pagenum=0, filter_value=""):
        """调用腾讯视频移动搜索API"""
        payload = {
            "version": "26022601",
            "clientType": 1,
            "filterValue": filter_value,
            "uuid": str(uuid.uuid4()).upper(),
            "retry": 0,
            "query": query,
            "pagenum": pagenum,
            "isPrefetch": False,
            "pagesize": 30,
            "queryFrom": 0,
            "searchDatakey": "",
            "transInfo": "",
            "isneedQc": True,
            "preQid": "",
            "adClientInfo": "",
            "extraInfo": {
                "isNewMarkLabel": "1",
                "multi_terminal_pc": "1",
                "themeType": "1",
                "sugRelatedIds": "{}",
                "appVersion": "",
                "frontVersion": "26060108"
            },
            "featureList": [
                "DEFAULT_FEFEATURE",
                "PC_SHORT_VIDEOS_WATERFALL",
                "PC_WANT_EPISODE_V2",
                "PC_WANT_EPISODE"
            ]
        }
        try:
            resp = self._post_json(self.search_api, payload)
            return resp.get('data', {}).get('normalList', {})
        except Exception:
            return {}

    def _video_from_item(self, item):
        """从搜索API的一个item中提取单视频列表字段"""
        video_info = item.get('videoInfo')
        if not video_info:
            return None
        vid = self._extract_vid(item)
        if not vid:
            return None
        title = self._clean_text(video_info.get('title', ''))
        if not title:
            title = self._clean_text(video_info.get('seriesTitle', ''))
        pic = video_info.get('imgUrl', '')
        if pic:
            pic = re.sub(r'/\d+$', '', pic)
        remark = video_info.get('views', '')
        time_long = video_info.get('timeLong', 0)
        if time_long:
            remark = f"{remark} {self._fmt_duration(time_long)}"
        return {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": self._fix_url(pic),
            "vod_remarks": remark
        }

    def _album_to_list_item(self, album):
        """把专辑信息转成列表条目，vod_id 用 JSON 保存 cid/标题/封面"""
        info = {
            "cid": album['cid'],
            "title": album['title'],
            "pic": album['pic']
        }
        return {
            "vod_id": json.dumps(info, ensure_ascii=False),
            "vod_name": album['title'],
            "vod_pic": album['pic'],
            "vod_remarks": "专辑"
        }

    # ---------------------- 框架接口：首页分类 ----------------------

    def homeContent(self, filter):
        """返回分类：这里只保留一个儿歌专辑入口"""
        result = {"class": []}
        classes = [
            {"type_name": "幼儿动画", "type_id": "album"}
        ]
        result["class"] = classes
        result["filters"] = {}
        return result

    # ---------------------- 框架接口：首页推荐 ----------------------

    def homeVideoContent(self):
        """首页推荐：取儿童频道第一页专辑"""
        videos = []
        try:
            albums, _ = self._get_channel_albums(pg=1)
            for album in albums[:10]:
                try:
                    videos.append(self._album_to_list_item(album))
                except Exception:
                    pass
        except Exception:
            pass
        return {"list": videos}

    # ---------------------- 框架接口：分类列表 ----------------------

    def categoryContent(self, tid, pg, filter, extend):
        """
        分类内容：按页码返回儿童频道专辑
        tid: 分类ID（已统一为 album）
        pg: 页码，从1开始
        """
        videos = []
        try:
            pg = max(int(pg), 1)
            albums, has_next = self._get_channel_albums(pg=pg)
            for album in albums:
                try:
                    videos.append(self._album_to_list_item(album))
                except Exception:
                    pass
            # 未拿到数据时视为无下一页
            pagecount = pg + 1 if has_next else pg
            return {
                'list': videos,
                'page': pg,
                'pagecount': pagecount,
                'limit': len(videos),
                'total': len(videos)
            }
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    # ---------------------- 框架接口：详情 ----------------------

    def detailContent(self, ids):
        """
        详情页：ids[0] 可能是专辑JSON（cid）或单个 vid
        """
        try:
            vod_id = ids[0]
            # 专辑详情
            if vod_id.startswith('{'):
                info = json.loads(vod_id)
                cid = info.get('cid', '')
                album_title = info.get('title', '')
                pic = info.get('pic', '')
                if not cid:
                    return {'list': []}

                vids = self._get_album_vids(cid)
                if not vids:
                    return {'list': []}

                details = self._get_vid_details(vids)
                play_list = []
                for idx, vid in enumerate(vids):
                    d = details.get(vid, {})
                    ep = d.get('episode') or d.get('title') or str(idx + 1)
                    # 如果标题只是数字，补成“第X集”
                    if re.match(r'^\d+$', str(ep)):
                        ep = f"第{int(ep)}集"
                    play_list.append(f"{ep}${vid}")

                detail = {
                    "vod_id": vod_id,
                    "vod_name": album_title,
                    "vod_pic": self._fix_url(pic),
                    "vod_remarks": f"{len(vids)}集",
                    "vod_content": album_title,
                    "vod_play_from": "动画正片",
                    "vod_play_url": "#".join(play_list),
                    "vod_url": f"{self.host}/x/cover/{cid}.html"
                }
                return {'list': [detail]}

            # 单视频详情（兼容搜索出来的单个视频）
            vid = vod_id
            detail_url = f"{self.host}/x/page/{vid}.html"
            data = self._do_search(vid, pagenum=0)
            target = None
            for item in data.get('itemList', []):
                if self._extract_vid(item) == vid:
                    target = item
                    break

            if target:
                vi = target.get('videoInfo', {})
                vod_name = self._clean_text(vi.get('title', ''))
                pic = vi.get('imgUrl', '')
                if pic:
                    pic = re.sub(r'/\d+$', '', pic)
                vod_remarks = vi.get('views', '')
                time_long = vi.get('timeLong', 0)
                if time_long:
                    vod_remarks += f" {self._fmt_duration(time_long)}"
                uploader = self._clean_text(vi.get('uploader', ''))
                type_name = vi.get('typeName', '')
                vod_content = f"{type_name} {uploader}".strip()
            else:
                basic = self._get_video_basic(vid)
                vod_name = basic.get('title', vid)
                pic = f"http://puui.qpic.cn/vpic_cover/{vid}/{vid}_hz.jpg"
                vod_remarks = ""
                vod_content = ""

            detail = {
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": self._fix_url(pic),
                "vod_remarks": vod_remarks,
                "vod_content": vod_content,
                "vod_play_from": "腾讯视频",
                "vod_play_url": f"正片${vid}",
                "vod_url": detail_url
            }
            return {'list': [detail]}
        except Exception:
            return {'list': []}

    # ---------------------- 框架接口：播放 ----------------------

    def playerContent(self, flag, id, vipFlags):
        """播放解析：id 为 vid"""
        try:
            vid = id
            url = f"{self.video_info_api}?vids={vid}&platform=101001&charge=0&otype=json"
            text = self._get(url)
            m = re.search(r'QZOutputJson\s*=\s*(\{.*?\});\s*$', text, re.S)
            if not m:
                return {"parse": 0, "playUrl": "", "url": ""}
            data = json.loads(m.group(1))
            vl = data.get('vl', {})
            vi_list = vl.get('vi', [])
            if not vi_list:
                return {"parse": 0, "playUrl": "", "url": ""}
            vi = vi_list[0]
            fn = vi.get('fn')
            fvkey = vi.get('fvkey')
            ui_list = vi.get('ul', {}).get('ui', [])
            if not fn or not fvkey or not ui_list:
                return {"parse": 0, "playUrl": "", "url": ""}
            base_url = ui_list[0].get('url', '')
            if base_url and not base_url.endswith('/'):
                base_url += '/'
            real_url = f"{base_url}{fn}?vkey={fvkey}"
            return {
                "parse": 0,
                "playUrl": "",
                "url": real_url,
                "header": json.dumps(self.header)
            }
        except Exception:
            return {"parse": 0, "playUrl": "", "url": ""}

    # ---------------------- 框架接口：搜索 ----------------------

    def searchContent(self, key, quick, pg='1'):
        """搜索：仍按单视频返回（搜索API暂无专辑cid）"""
        videos = []
        try:
            pagenum = max(int(pg) - 1, 0)
            data = self._do_search(key, pagenum=pagenum)
            for item in data.get('itemList', []):
                try:
                    video = self._video_from_item(item)
                    if video:
                        videos.append(video)
                except Exception:
                    pass
            total_num = data.get('totalNum', len(videos))
            return {
                'list': videos,
                'page': int(pg),
                'pagecount': (total_num + 29) // 30 if total_num else 1,
                'limit': len(videos),
                'total': total_num
            }
        except Exception:
            return {'list': [], 'page': 1, 'pagecount': 0, 'limit': 0, 'total': 0}

    # ---------------------- 框架预留接口 ----------------------

    def isVideoFormat(self, url):
        return any(url.lower().endswith(fmt) for fmt in ['.m3u8', '.mp4', '.flv', '.ts'])

    def manualVideoCheck(self):
        pass

    def localProxy(self, params):
        return None

    def destroy(self):
        pass
