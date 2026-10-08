# -*- coding: utf-8 -*-
"""
==================================================
@Spider Name : ASMRHoney (asmrhoney.com)
@Description : ASMRHoney - ASMR视频精选站
              数据源：/data/clips.json (2400+视频，直链MP4)
              分类：按语言/标签/创作者 动态分类
              搜索：本地关键词匹配
==================================================
"""
import sys
import re
import json
import time
from urllib.parse import quote

try:
    import requests
except ImportError:
    requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): self.extend = extend
        def getName(self): return "Base"
        def homeContent(self, filter): return {'class': [], 'filters': {}}
        def homeVideoContent(self): return {'list': []}
        def categoryContent(self, tid, pg, filter, extend):
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0}
        def detailContent(self, ids): return {'list': []}
        def playerContent(self, flag, id, vipFlags=None):
            return {'parse': 0, 'playUrl': '', 'url': '', 'header': ''}
        def searchContent(self, key, quick, pg='1'):
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 20, 'total': 0}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def localProxy(self, param): return [404, 'text/plain', b'']
        def destroy(self): pass


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# 语言分类映射
LANG_MAP = {
    "zh": ("lang_zh", "中文ASMR"),
    "ja": ("lang_ja", "日语ASMR"),
    "ko": ("lang_ko", "韩语ASMR"),
    "en": ("lang_en", "英语ASMR"),
    "mixed": ("lang_mixed", "混合语言"),
}

# 标签分类（精选标签）
TAG_CATEGORIES = [
    ("tag_ear_licking", "舔耳", "ear_licking"),
    ("tag_mouth_sounds", "口腔音", "mouth_sounds"),
    ("tag_trigger_sounds", "触发音", "trigger_sounds"),
    ("tag_roleplay", "角色扮演", "roleplay"),
    ("tag_whisper", "耳语", "whisper"),
    ("tag_pantyhose", "丝袜", "pantyhose"),
    ("tag_scratching", "刮擦", "scratching"),
    ("tag_sexy", "性感", "sexy"),
    ("tag_sfw", "SFW全年龄", "sfw"),
    ("tag_nsfw", "NSFW", "nsfw"),
    ("tag_eareating", "耳吃", "eareating"),
    ("tag_tongue", "舌头", "tongue"),
    ("tag_sleep_aid", "助眠", "sleep_aid"),
    ("tag_breathing", "呼吸音", "breathing"),
    ("tag_feet", "足部", "feet"),
    ("tag_kiss", "亲吻", "kiss"),
]

# 分类类型
CATEGORY_TYPES = {
    "lang": "语言分类",
    "tag": "标签分类",
}


class Spider(BaseSpider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host = "https://asmrhoney.com"
        self.session = None
        self._clips_cache = None
        self._clips_cache_time = 0
        self._cache_ttl = 3600  # 缓存1小时
        self._audio_cache = None
        self._audio_cache_time = 0

    def getName(self):
        return "ASMRHoney"

    def init(self, extend=""):
        self.setExtendInfo(extend)
        if requests:
            self.session = requests.Session()
            self.session.headers.update({
                "User-Agent": UA,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": self.host + "/",
            })
            self.session.verify = False

    def setExtendInfo(self, extend=""):
        if isinstance(extend, dict):
            self.extend_cfg = extend
        elif extend and isinstance(extend, str):
            try:
                self.extend_cfg = json.loads(extend)
            except Exception:
                self.extend_cfg = {}
        else:
            self.extend_cfg = {}
        self.host = str(self.extend_cfg.get("host") or self.host).rstrip("/")

    def destroy(self):
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:mp4|m3u8|mp3|m4a|flv|mkv|ts)(?:\?|$)", str(url), re.I))

    def manualVideoCheck(self):
        return False

    # ==================== 数据加载 ====================

    def _load_clips(self, force=False):
        """加载 clips.json，带内存缓存"""
        now = time.time()
        if (not force) and self._clips_cache and (now - self._clips_cache_time) < self._cache_ttl:
            return self._clips_cache

        try:
            url = f"{self.host}/data/clips.json"
            if self.session:
                r = self.session.get(url, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    clips = data.get("clips", [])
                    # 只保留已发布的
                    clips = [c for c in clips if c.get("status") == "published"]
                    # 按发布时间倒序
                    clips.sort(key=lambda c: c.get("publishedAt", ""), reverse=True)
                    self._clips_cache = clips
                    self._clips_cache_time = now
                    return clips
            else:
                import urllib.request, ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers={
                    "User-Agent": UA,
                    "Referer": self.host + "/",
                    "Accept": "application/json",
                })
                resp = urllib.request.urlopen(req, context=ctx, timeout=30)
                data = json.loads(resp.read().decode("utf-8"))
                clips = data.get("clips", [])
                clips = [c for c in clips if c.get("status") == "published"]
                clips.sort(key=lambda c: c.get("publishedAt", ""), reverse=True)
                self._clips_cache = clips
                self._clips_cache_time = now
                return clips
        except Exception:
            pass

        # 返回空列表
        if self._clips_cache is None:
            self._clips_cache = []
            self._clips_cache_time = now
        return self._clips_cache

    def _load_audio(self, force=False):
        """加载 audio.json（音频专辑）"""
        now = time.time()
        if (not force) and self._audio_cache and (now - self._audio_cache_time) < self._cache_ttl:
            return self._audio_cache

        try:
            url = f"{self.host}/data/audio.json"
            if self.session:
                r = self.session.get(url, timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    self._audio_cache = data
                    self._audio_cache_time = now
                    return data
            else:
                import urllib.request, ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers={
                    "User-Agent": UA, "Referer": self.host + "/",
                })
                resp = urllib.request.urlopen(req, context=ctx, timeout=20)
                data = json.loads(resp.read().decode("utf-8"))
                self._audio_cache = data
                self._audio_cache_time = now
                return data
        except Exception:
            pass
        return {"albums": [], "tracks": []}

    # ==================== 分类 ====================

    def homeContent(self, filter=False):
        classes = []
        filters = {}

        # 1. 语言分类
        for lang_key, (tid, name) in LANG_MAP.items():
            classes.append({"type_id": tid, "type_name": name})

        # 2. 标签分类
        for tid, name, _ in TAG_CATEGORIES:
            classes.append({"type_id": tid, "type_name": name})

        # 3. 音频分类
        classes.append({"type_id": "audio_albums", "type_name": "音频专辑"})
        classes.append({"type_id": "audio_tracks", "type_name": "音频单曲"})

        # 4. 最新/热门
        classes.insert(0, {"type_id": "latest", "type_name": "最新更新"})

        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        """首页推荐 = 最新更新"""
        clips = self._load_clips()
        items = self._clips_to_vod_list(clips[:24])
        return {"list": items}

    # ==================== 分类列表 ====================

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = max(1, self._page(pg))
        page_size = 20

        clips = self._load_clips()
        filtered = []

        # 最新
        if tid == "latest":
            filtered = clips

        # 语言分类
        elif tid.startswith("lang_"):
            lang_key = tid.replace("lang_", "", 1)
            filtered = [c for c in clips if c.get("language") == lang_key]

        # 标签分类
        elif tid.startswith("tag_"):
            tag_key = tid.replace("tag_", "", 1)
            # TAG_CATEGORIES 中查找原始标签名
            original_tag = None
            for t_tid, _, orig in TAG_CATEGORIES:
                if t_tid == tid:
                    original_tag = orig
                    break
            if original_tag:
                filtered = [c for c in clips if original_tag in c.get("tags", [])]
            else:
                # 兜底：直接匹配
                filtered = [c for c in clips if tag_key in c.get("tags", [])]

        # 音频专辑
        elif tid == "audio_albums":
            data = self._load_audio()
            albums = data.get("albums", [])
            total = len(albums)
            start = (page - 1) * page_size
            end = start + page_size
            page_albums = albums[start:end]
            items = self._albums_to_vod_list(page_albums)
            pagecount = max(1, (total + page_size - 1) // page_size)
            return {
                "list": items, "page": page,
                "pagecount": pagecount, "limit": page_size, "total": total,
            }

        # 音频单曲
        elif tid == "audio_tracks":
            data = self._load_audio()
            tracks = data.get("tracks", [])
            total = len(tracks)
            start = (page - 1) * page_size
            end = start + page_size
            page_tracks = tracks[start:end]
            items = self._tracks_to_vod_list(page_tracks)
            pagecount = max(1, (total + page_size - 1) // page_size)
            return {
                "list": items, "page": page,
                "pagecount": pagecount, "limit": page_size, "total": total,
            }

        else:
            filtered = clips

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        page_clips = filtered[start:end]

        items = self._clips_to_vod_list(page_clips)
        pagecount = max(1, (total + page_size - 1) // page_size)

        return {
            "list": items, "page": page,
            "pagecount": pagecount, "limit": page_size, "total": total,
        }

    # ==================== 详情 ====================

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)

        clips = self._load_clips()

        # 视频详情：clip slug
        if not vod_id.startswith("audio:") and not vod_id.startswith("album:"):
            clip = self._find_clip(clips, vod_id)
            if clip:
                vod = self._clip_to_vod_detail(clip)
                return {"list": [vod]}

        # 音频专辑
        if vod_id.startswith("album:"):
            album_slug = vod_id.replace("album:", "", 1)
            data = self._load_audio()
            for album in data.get("albums", []):
                if album.get("slug") == album_slug:
                    vod = self._album_to_vod_detail(album, data.get("tracks", []))
                    return {"list": [vod]}

        # 音频单曲
        if vod_id.startswith("audio:"):
            track_slug = vod_id.replace("audio:", "", 1)
            data = self._load_audio()
            for track in data.get("tracks", []):
                if track.get("slug") == track_slug:
                    vod = self._track_to_vod_detail(track)
                    return {"list": [vod]}

        return {"list": []}

    # ==================== 搜索 ====================

    def searchContent(self, key, quick=False, pg="1"):
        page = max(1, self._page(pg))
        page_size = 20

        if not key or not key.strip():
            return {"list": [], "page": page, "pagecount": 1, "limit": page_size, "total": 0}

        key_lower = key.strip().lower()
        clips = self._load_clips()

        results = []
        for clip in clips:
            score = 0
            # 标题匹配（权重最高）
            title = str(clip.get("title", "")).lower()
            if key_lower in title:
                score += 100
            # 创作者匹配
            creator = str(clip.get("creator", "")).lower()
            if key_lower in creator:
                score += 50
            # 标签匹配
            tags = [t.lower() for t in clip.get("tags", [])]
            if any(key_lower in t for t in tags):
                score += 30
            # 描述匹配
            desc = str(clip.get("description", "")).lower()
            if key_lower in desc:
                score += 10

            if score > 0:
                results.append((score, clip))

        # 按得分降序
        results.sort(key=lambda x: x[0], reverse=True)
        matched_clips = [r[1] for r in results]

        total = len(matched_clips)
        start = (page - 1) * page_size
        end = start + page_size
        page_clips = matched_clips[start:end]

        items = self._clips_to_vod_list(page_clips)
        pagecount = max(1, (total + page_size - 1) // page_size)

        return {
            "list": items, "page": page,
            "pagecount": pagecount, "limit": page_size, "total": total,
        }

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags=None):
        safe = {"parse": 0, "playUrl": "", "url": "", "header": ""}
        try:
            play_url = str(id or "")

            # 已经是直链
            if play_url.startswith("http") and self.isVideoFormat(play_url):
                return {
                    "parse": 0, "playUrl": "", "url": play_url,
                    "header": json.dumps({
                        "User-Agent": UA,
                        "Referer": self.host + "/",
                        "Origin": self.host,
                    }, ensure_ascii=False),
                }

            # clip slug -> 查视频地址
            if play_url and not play_url.startswith("http"):
                clips = self._load_clips()
                clip = self._find_clip(clips, play_url)
                if clip:
                    video_url = clip.get("videoUrl") or clip.get("video480Url") or ""
                    if video_url:
                        return {
                            "parse": 0, "playUrl": "", "url": video_url,
                            "header": json.dumps({
                                "User-Agent": UA,
                                "Referer": self.host + "/",
                                "Origin": self.host,
                            }, ensure_ascii=False),
                        }

                # 音频单曲
                if play_url.startswith("audio:"):
                    track_slug = play_url.replace("audio:", "", 1)
                    data = self._load_audio()
                    for track in data.get("tracks", []):
                        if track.get("slug") == track_slug:
                            audio_url = track.get("audioUrl", "")
                            if audio_url:
                                return {
                                    "parse": 0, "playUrl": "", "url": audio_url,
                                    "header": json.dumps({
                                        "User-Agent": UA,
                                        "Referer": self.host + "/",
                                    }, ensure_ascii=False),
                                }

        except Exception:
            pass

        return safe

    # ==================== 本地代理 ====================

    def localProxy(self, param):
        url = param.get("url") or param.get("pic") or ""
        if isinstance(url, list):
            url = url[0] if url else ""
        if not url:
            return [404, "text/plain", b""]

        try:
            if not url.startswith("http"):
                if not url.startswith("/"):
                    url = "/" + url
                url = self.host + url
            if self.session:
                r = self.session.get(url, headers={
                    "User-Agent": UA,
                    "Referer": self.host + "/",
                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                }, timeout=15)
                if r.status_code == 200 and r.content:
                    ct = r.headers.get("Content-Type", "image/jpeg")
                    return [200, ct, r.content]
        except Exception:
            pass
        return [404, "text/plain", b""]

    # ==================== 辅助方法 ====================

    @staticmethod
    def _page(pg):
        try:
            v = int(str(pg or "").strip())
            return v if v > 0 else 1
        except (ValueError, TypeError):
            return 1

    @staticmethod
    def _find_clip(clips, slug):
        """根据slug查找clip"""
        if not slug:
            return None
        # 去掉前缀
        if slug.startswith("clip:"):
            slug = slug[5:]
        for c in clips:
            if c.get("slug") == slug:
                return c
        return None

    def _clips_to_vod_list(self, clips):
        """clip列表转VOD列表"""
        items = []
        for clip in clips:
            slug = clip.get("slug", "")
            title = clip.get("title", "") or slug
            cover = clip.get("coverUrl") or clip.get("coverWebpUrl") or ""
            duration = clip.get("duration", 0)
            creator = clip.get("creator", "")

            # 备注：时长 + 创作者
            remarks = ""
            if creator:
                remarks = creator
            if duration:
                mins = duration // 60
                secs = duration % 60
                if remarks:
                    remarks += f" | {mins}:{secs:02d}"
                else:
                    remarks = f"{mins}:{secs:02d}"

            items.append({
                "vod_id": slug,
                "vod_name": title,
                "vod_pic": cover,
                "vod_remarks": remarks,
            })
        return items

    def _clip_to_vod_detail(self, clip):
        """clip转VOD详情"""
        slug = clip.get("slug", "")
        title = clip.get("title", "") or slug
        cover = clip.get("coverUrl") or clip.get("coverWebpUrl") or ""
        duration = clip.get("duration", 0)
        creator = clip.get("creator", "")
        description = clip.get("description", "")
        tags = clip.get("tags", [])
        language = clip.get("language", "")
        published = clip.get("publishedAt", "")[:10]
        video_url = clip.get("videoUrl", "")
        video_480 = clip.get("video480Url", "")

        # 播放源
        play_from_list = []
        play_url_list = []

        # 原画线路
        if video_url:
            play_from_list.append("原画")
            play_url_list.append(f"{title}${video_url}")

        # 480P线路
        if video_480:
            play_from_list.append("480P")
            play_url_list.append(f"{title}${video_480}")

        # 语言名
        lang_name = {
            "zh": "中文", "ja": "日语", "ko": "韩语",
            "en": "英语", "mixed": "混合"
        }.get(language, language)

        # 时长格式化
        duration_str = ""
        if duration:
            mins = duration // 60
            secs = duration % 60
            duration_str = f"{mins}分{secs:02d}秒"

        vod = {
            "vod_id": slug,
            "vod_name": title,
            "vod_pic": cover,
            "vod_director": "",
            "vod_actor": creator,
            "vod_year": published,
            "vod_area": lang_name,
            "vod_content": description or title,
            "vod_remarks": duration_str,
            "vod_play_from": "$$$".join(play_from_list),
            "vod_play_url": "$$$".join(play_url_list),
            "vod_tag": ",".join(tags),
        }
        return vod

    def _albums_to_vod_list(self, albums):
        """专辑转列表"""
        items = []
        for album in albums:
            slug = album.get("slug", "")
            title = album.get("title", "") or slug
            cover = album.get("coverUrl") or ""
            track_count = album.get("trackCount", 0)
            total_duration = album.get("totalDuration", 0)

            remarks = f"{track_count}首"
            if total_duration:
                hours = total_duration // 3600
                mins = (total_duration % 3600) // 60
                remarks += f" | {hours}小时{mins}分"

            items.append({
                "vod_id": f"album:{slug}",
                "vod_name": title,
                "vod_pic": cover,
                "vod_remarks": remarks,
            })
        return items

    def _tracks_to_vod_list(self, tracks):
        """音频单曲转列表"""
        items = []
        for track in tracks:
            slug = track.get("slug", "")
            title = track.get("title", "") or slug
            cover = track.get("coverUrl") or ""
            duration = track.get("duration", 0)
            creator = track.get("creator", "")

            remarks = creator or ""
            if duration:
                mins = duration // 60
                secs = duration % 60
                if remarks:
                    remarks += f" | {mins}:{secs:02d}"
                else:
                    remarks = f"{mins}:{secs:02d}"

            items.append({
                "vod_id": f"audio:{slug}",
                "vod_name": title,
                "vod_pic": cover,
                "vod_remarks": remarks,
            })
        return items

    def _album_to_vod_detail(self, album, all_tracks):
        """专辑转详情（专辑 = 多个音轨）"""
        slug = album.get("slug", "")
        title = album.get("title", "") or slug
        cover = album.get("coverUrl") or ""
        creator = album.get("creator", "")
        track_count = album.get("trackCount", 0)
        total_duration = album.get("totalDuration", 0)
        published = str(album.get("publishedAt", ""))[:10]

        # 查找属于该专辑的音轨（通过creator匹配，因为数据中没有明确的专辑关联字段）
        # 注意：实际数据中track没有album字段，这里显示全部音轨
        album_tracks = [t for t in all_tracks if t.get("creator") == creator]
        if not album_tracks:
            album_tracks = all_tracks[:10]

        eps = []
        for track in album_tracks:
            t_slug = track.get("slug", "")
            t_title = track.get("title", "") or t_slug
            t_url = track.get("audioUrl", "")
            if t_url:
                eps.append(f"{t_title}${t_url}")

        # 如果没有找到音轨，至少保留专辑信息
        if not eps:
            eps.append(f"{title}$")

        vod = {
            "vod_id": f"album:{slug}",
            "vod_name": title,
            "vod_pic": cover,
            "vod_director": "",
            "vod_actor": creator,
            "vod_year": published,
            "vod_area": "音频",
            "vod_content": album.get("title_en", "") or title,
            "vod_remarks": f"{track_count}首 | 总时长{total_duration // 60}分",
            "vod_play_from": "音频",
            "vod_play_url": "#".join(eps),
        }
        return vod

    def _track_to_vod_detail(self, track):
        """音频单曲转详情"""
        slug = track.get("slug", "")
        title = track.get("title", "") or slug
        cover = track.get("coverUrl") or ""
        creator = track.get("creator", "")
        duration = track.get("duration", 0)
        audio_url = track.get("audioUrl", "")
        published = str(track.get("publishedAt", ""))[:10]

        duration_str = ""
        if duration:
            mins = duration // 60
            secs = duration % 60
            duration_str = f"{mins}分{secs:02d}秒"

        vod = {
            "vod_id": f"audio:{slug}",
            "vod_name": title,
            "vod_pic": cover,
            "vod_director": "",
            "vod_actor": creator,
            "vod_year": published,
            "vod_area": "音频",
            "vod_content": track.get("title_en", "") or title,
            "vod_remarks": duration_str,
            "vod_play_from": "音频",
            "vod_play_url": f"{title}${audio_url}" if audio_url else "",
        }
        return vod
