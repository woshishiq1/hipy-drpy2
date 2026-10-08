# 本地资源管理.py - 完整优化版（支持网络歌词封面获取 + 短视频分类 + 彩色图标）
# 优化内容：音频扫描缓存、超时保护、腾讯API歌词获取、网易云API封面获取、短视频API整合

import sys
import re
import json
import os
import base64
import hashlib
import time
import urllib.parse
import sqlite3
import glob
import zlib
import xml.etree.ElementTree as ET
import random
from pathlib import Path
from base.spider import Spider

# ==================== 在线直播配置 ====================
ONLINE_LIVE_SOURCES = [
    {
        "id": "migu_live",
        "name": "咪咕直播",
        "url": "https://gh-proxy.org/https://raw.githubusercontent.com/develop202/migu_video/refs/heads/main/interface.txt",
        "color": "#FF6B6B",
        "remarks": "央视/卫视直播",
        "type": "m3u",
        "ua": "com.android.chrome/3.7.0 (Linux;Android 15)",
        "playerType": 2
    },
    {
        "id": "gongdian_live",
        "name": "宫殿直播",
        "url": "https://gongdian.top/tv/iptv",
        "color": "#4ECDC4",
        "remarks": "宫殿直播源",
        "type": "m3u",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "playerType": 2
    },
    {
        "id": "simple_live",
        "name": "简单直播",
        "url": "http://gh-proxy.org/raw.githubusercontent.com/Supprise0901/TVBox_live/main/live.txt",
        "color": "#6BCB77",
        "remarks": "简单直播源",
        "type": "txt"
    },
    {
        "id": "kulao_tv",
        "name": "裤佬TV直播",
        "url": "https://gh-proxy.org/https://raw.githubusercontent.com/Jsnzkpg/Jsnzkpg/Jsnzkpg/Jsnzkpg1.m3u",
        "color": "#9D65C9",
        "remarks": "裤佬TV直播源",
        "type": "m3u",
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "playerType": 2
    }
]

LIVE_CATEGORY_ID = "online_live"
LIVE_CATEGORY_NAME = "📡 在线直播"
LIVE_CACHE_DURATION = 600

# ==================== 全局请求头自动适配配置 ====================
COMMON_HEADERS_LIST = [
    {
        "name": "Chrome浏览器",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }
    },
    {
        "name": "Firefox浏览器",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            "Connection": "keep-alive"
        }
    },
    {
        "name": "okhttp/3",
        "headers": {
            "User-Agent": "okhttp/3.12.11",
            "Accept": "*/*",
            "Connection": "Keep-Alive"
        }
    },
    {
        "name": "手机浏览器",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }
    },
    {
        "name": "Edge浏览器",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }
    },
    {
        "name": "Safari浏览器",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }
    },
    {
        "name": "Android Chrome",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }
    }
]

DOMAIN_SPECIFIC_HEADERS = {
    "miguvideo.com": [
        {
            "name": "咪咕专用-Android Chrome",
            "headers": {
                "User-Agent": "com.android.chrome/3.7.0 (Linux;Android 15)",
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Referer": "https://www.miguvideo.com/"
            }
        },
        {
            "name": "咪咕专用-okhttp",
            "headers": {
                "User-Agent": "okhttp/3.12.11",
                "Accept": "*/*",
                "Connection": "Keep-Alive",
                "Referer": "https://www.miguvideo.com/"
            }
        }
    ],
    "gongdian.top": [
        {
            "name": "宫殿直播专用",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Referer": "https://gongdian.top/",
                "Connection": "keep-alive"
            }
        }
    ],
    "t.061899.xyz": [
        {
            "name": "t源专用",
            "headers": {
                "User-Agent": "okhttp/3.12.11",
                "Referer": "http://t.061899.xyz/",
                "Accept": "*/*"
            }
        }
    ],
    "rihou.cc": [
        {
            "name": "日后源专用-Chrome",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://rihou.cc:555/",
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive"
            }
        },
        {
            "name": "日后源专用-okhttp",
            "headers": {
                "User-Agent": "okhttp/3.12.11",
                "Referer": "http://rihou.cc:555/",
                "Accept": "*/*",
                "Connection": "Keep-Alive"
            }
        }
    ]
}

# ==================== 路径配置 ====================
ROOT_PATHS = [
    '/storage/emulated/0/',
    '/storage/emulated/0/Movies/',
    '/storage/emulated/0/Music/',
    '/storage/emulated/0/Download/KuwoMusic/music/',
    '/storage/emulated/0/Download/',
    '/storage/emulated/0/DCIM/Camera/',
    '/storage/emulated/0/Pictures/',
    '/storage/emulated/0/Books/',
    '/storage/emulated/0/VodPlus/wwwroot/lz/'
]

PATH_TO_CHINESE = {
    '/storage/emulated/0/': '根目录',
    '/storage/emulated/0/Movies/': '电影',
    '/storage/emulated/0/Music/': '音乐',
    '/storage/emulated/0/Download/KuwoMusic/music/': '酷我音乐',
    '/storage/emulated/0/Download/': '下载',
    '/storage/emulated/0/DCIM/Camera/': '相机',
    '/storage/emulated/0/Pictures/': '图片',
    '/storage/emulated/0/Books/': '小说',
    '/storage/emulated/0/VodPlus/wwwroot/lz/': '老张'
}

# ==================== 数据库兼容配置 ====================
DB_COMPAT_MODE = True
MAX_DB_RESULTS = 50000

print("ℹ️ 本地资源管理加载成功 - 短视频分类版")

# ==================== 数据库读取器 ====================
class DatabaseReader:
    """数据库读取器"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_duration = 600
    
    def read_sqlite(self, db_path, limit=50000):
        cache_key = f"{db_path}_{os.path.getmtime(db_path)}_{limit}"
        current_time = time.time()
        
        if cache_key in self.cache and current_time - self.cache_time.get(cache_key, 0) < self.cache_duration:
            print(f"📊 使用缓存数据: {os.path.basename(db_path)}, {len(self.cache[cache_key])} 条记录")
            return self.cache[cache_key]
        
        if not os.path.exists(db_path) or not os.access(db_path, os.R_OK):
            return []
        
        out = []
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA cache_size = 10000")
            cursor.execute("PRAGMA page_size = 4096")
            cursor.execute("PRAGMA mmap_size = 30000000000")
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'android_%'")
            tables = cursor.fetchall()
            
            skip_tables = ['android_metadata', 'db_config', 'meta', 'crawl_state', 'sqlite_sequence']
            
            for table in tables:
                table_name = table[0]
                if table_name in skip_tables:
                    continue
                items = self.parse_table(cursor, conn, table_name, limit)
                if items:
                    out.extend(items)
                if len(out) >= limit:
                    out = out[:limit]
                    break
            
            conn.close()
        except Exception as e:
            print(f"数据库读取错误: {e}")
            return []
        
        self.cache[cache_key] = out
        self.cache_time[cache_key] = current_time
        return out
    
    def parse_table(self, cursor, conn, table, limit):
        res = []
        try:
            cursor.execute(f"PRAGMA table_info(`{table}`)")
            cols = cursor.fetchall()
            col_names = [col[1] for col in cols]
            
            title_field = self.find_best_match(col_names, ['vod_name', 'name', 'title'])
            url_field = self.find_best_match(col_names, ['play_url', 'vod_play_url', 'vod_url', 'url'])
            pic_field = self.find_best_match(col_names, ['image', 'vod_pic', 'pic'])
            remarks_field = self.find_best_match(col_names, ['vod_remarks', 'remarks'])
            
            if not title_field or not url_field:
                return []
            
            cursor.execute(f"SELECT * FROM `{table}` WHERE `{url_field}` IS NOT NULL AND `{url_field}` != '' LIMIT {limit}")
            rows = cursor.fetchall()
            
            for row in rows:
                row_dict = dict(row)
                play_url_raw = str(row_dict.get(url_field, '')).strip()
                if not play_url_raw:
                    continue
                
                title = str(row_dict.get(title_field, '未命名')).strip()
                
                is_multi = '$' in play_url_raw or '#' in play_url_raw or '$$$' in play_url_raw
                
                item = {
                    'name': title,
                    'url': '' if is_multi else play_url_raw,
                    'play_url': play_url_raw if is_multi else '',
                    'pic': row_dict.get(pic_field, '') if pic_field else '',
                    'remarks': row_dict.get(remarks_field, '') if remarks_field else '',
                }
                res.append(item)
        except Exception as e:
            print(f"解析表 {table} 错误: {e}")
        return res
    
    def find_best_match(self, column_names, candidates):
        for cand in candidates:
            for col in column_names:
                if col.lower() == cand.lower():
                    return col
        for cand in candidates:
            for col in column_names:
                if cand.lower() in col.lower():
                    return col
        return None


# ==================== 小说解析器 ====================
class NovelParser:
    """小说文件解析器"""
    
    @staticmethod
    def parse_txt_novel(file_path):
        """解析TXT小说文件"""
        chapters = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            patterns = [
                r'第[一二三四五六七八九十百千万0-9]+章\s*[^\n]{0,50}',
                r'第[一二三四五六七八九十百千万0-9]+节\s*[^\n]{0,50}',
                r'序章\s*[^\n]{0,50}|楔子\s*[^\n]{0,50}|尾声\s*[^\n]{0,50}',
                r'正文\s+第[一二三四五六七八九十百千万0-9]+章',
                r'Chapter\s+[0-9]+[.:]?\s*[^\n]{0,50}'
            ]
            
            matches = []
            for p in patterns:
                for m in re.finditer(p, content, re.MULTILINE):
                    title = m.group().strip()
                    if title and len(title) > 2 and not title.strip().isdigit():
                        matches.append((m.start(), title))
            
            matches = list(set(matches))
            matches.sort(key=lambda x: x[0])
            
            if matches:
                for i, (pos, title) in enumerate(matches):
                    start = pos
                    end = matches[i + 1][0] if i + 1 < len(matches) else len(content)
                    chap_content = content[start:end].strip()
                    chapters.append({
                        'title': title,
                        'content': chap_content,
                        'index': i
                    })
            else:
                chapters.append({
                    'title': os.path.splitext(os.path.basename(file_path))[0],
                    'content': content,
                    'index': 0
                })
        except Exception as e:
            print(f"解析小说失败: {e}")
        return chapters


# ==================== 主爬虫类 ====================
class Spider(Spider):
    def getName(self):
        return "本地资源管理"
    
    def init(self, extend=""):
        super().init(extend)
        self.root_paths = ROOT_PATHS
        self.path_to_chinese = PATH_TO_CHINESE
        
        # 在线直播配置
        self.online_live_sources = ONLINE_LIVE_SOURCES
        self.live_category_id = LIVE_CATEGORY_ID
        self.live_category_name = LIVE_CATEGORY_NAME
        self.live_cache = {}
        self.live_cache_time = {}
        self.live_cache_duration = LIVE_CACHE_DURATION
        
        # 请求头适配
        self.common_headers_list = COMMON_HEADERS_LIST
        self.domain_specific_headers = DOMAIN_SPECIFIC_HEADERS
        self.successful_headers_cache = {}
        
        self.default_colors = [
            "#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#9D65C9", 
            "#FF8C42", "#A2D729", "#FF6B8B", "#45B7D1", "#96CEB4"
        ]
        
        # 文件类型定义
        self.media_exts = ['mp4', 'mkv', 'avi', 'rmvb', 'mov', 'wmv', 'flv', 'm4v', 'ts', 'm3u8']
        self.audio_exts = ['mp3', 'm4a', 'aac', 'flac', 'wav', 'ogg', 'wma', 'ape']
        self.image_exts = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'ico', 'svg', 'heic', 'heif']
        self.list_exts = ['m3u', 'txt', 'json', 'm3u8']
        self.lrc_exts = ['lrc', 'krc', 'qrc', 'yrc', 'trc']
        self.db_exts = ['db', 'sqlite', 'sqlite3', 'db3']
        self.magnet_exts = ['magnets', 'magnet', 'bt', 'torrent', 'mgt']
        self.code_exts = ['php', 'py', 'js', 'css', 'html', 'htm', 'xml', 'sh', 'bash']
        self.archive_exts = ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz']
        
        # ========== 音频优化配置 ==========
        self.max_audio_per_scan = 2000
        self.audio_scan_timeout = 5
        self.enable_online_lyrics = True
        self.enable_online_poster = True
        self.audio_cache_duration = 3600
        
        # 腾讯API配置（歌词）
        self.QQ_OFFICIAL_SEARCH = "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg"
        self.QQ_OFFICIAL_LYRIC = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
        
        # 网易云API配置（封面）
        self.NETESE_SEARCH_API = "https://api.itooi.cn/music/netease/search"
        
        # 网络缓存
        self.audio_list_cache = {}
        self.audio_list_cache_time = {}
        self.network_lyrics_cache = {}
        self.network_cover_cache = {}
        self.song_info_cache = {}
        
        # 调试开关
        self.debug_mode = True
        
        # 预定义的音频目录
        self.priority_audio_dirs = [
            '/storage/emulated/0/Music/',
            '/storage/emulated/0/Download/KuwoMusic/music/',
            '/storage/emulated/0/netease/cloudmusic/Music/',
            '/storage/emulated/0/qqmusic/song/',
            '/storage/emulated/0/MIUI/music/',
            '/storage/emulated/0/Download/',
        ]
        
        self.live_keywords = ['cctv', '卫视', '频道', '直播', '电视台', 'iptv', 'm3u8', 'live', '咪咕', '央卫', '香港', '台湾', '澳门', '体育', '新闻', '音乐', '综合']
        self.novel_keywords = ['第', '章', '节', '卷', '部', '篇', '集', '小说', '故事', '作者']
        
        self.file_icons = {
            'folder': 'https://img.icons8.com/color/96/000000/folder-invoices.png',
            'video': 'https://img.icons8.com/color/96/000000/video.png',
            'video_playlist': 'https://img.icons8.com/color/96/000000/playlist.png',
            'audio': 'https://img.icons8.com/color/96/000000/audio-file.png',
            'audio_playlist': 'https://img.icons8.com/color/96/000000/musical-notes.png',
            'image': 'https://img.icons8.com/color/96/000000/image.png',
            'image_playlist': 'https://img.icons8.com/color/96/000000/image-gallery.png',
            'list': 'https://img.icons8.com/color/96/000000/list.png',
            'lrc': 'https://img.icons8.com/color/96/000000/audio-file.png',
            'database': 'https://img.icons8.com/color/96/000000/database.png',
            'magnet': 'https://img.icons8.com/color/96/000000/magnet.png',
            'novel': 'https://img.icons8.com/color/96/000000/book.png',
            'text': 'https://img.icons8.com/color/96/000000/document.png',
            'file': 'https://img.icons8.com/color/96/000000/file.png',
            'json': 'https://img.icons8.com/color/96/000000/json.png',
            'music_note': 'https://img.icons8.com/color/96/musical-notes.png',
            'lyrics': 'https://img.icons8.com/color/96/000000/audio-file.png',
            'cd': 'https://img.icons8.com/color/96/compact-disc.png',
            'song': 'https://img.icons8.com/color/96/song.png',
            'php': 'https://img.icons8.com/color/96/php.png',
            'python': 'https://img.icons8.com/color/96/python.png',
            'zip': 'https://img.icons8.com/color/96/zip.png',
            'archive': 'https://img.icons8.com/color/96/archive.png',
            'rar': 'https://img.icons8.com/color/96/rar.png',
        }
        
        self.TRANSPARENT_GIF = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
        
        # 前缀常量
        self.V_DIR_PREFIX = 'vdir://'
        self.V_ITEM_PREFIX = 'vitem://'
        self.URL_B64U_PREFIX = 'b64u://'
        self.V_ALL_PREFIX = 'vall://'
        self.A_ALL_PREFIX = 'aall://'
        self.FOLDER_PREFIX = 'folder://'
        self.LIST_PREFIX = 'list://'
        self.PICS_PREFIX = 'pics://'
        self.MP3_PREFIX = 'mp3://'
        self.CAMERA_ALL_PREFIX = 'camall://'
        self.MAGNET_PREFIX = 'magnet://'
        self.LIVE_PREFIX = 'live://'
        self.NOVEL_PREFIX = 'novel://'
        self.TEXT_PREFIX = 'text://'

        self.lrc_cache = {}
        self.m3u8_cache = {}
        self.db_reader = DatabaseReader()
        self.poster_cache = {}
        self.word_lyrics_cache = {}
        self.novel_path_cache = {}
        self.novel_chapters_cache = {}
        self.current_novel = {'encoded_path': None, 'file_path': None, 'chapters': []}
        
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def log(self, msg):
        if self.debug_mode:
            print(f"🔍 [DEBUG] {msg}")

    # ==================== 工具函数 ====================
    
    def b64u_encode(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        encoded = base64.b64encode(data).decode('ascii')
        return encoded.replace('+', '-').replace('/', '_').rstrip('=')
    
    def b64u_decode(self, data):
        data = data.replace('-', '+').replace('_', '/')
        pad = len(data) % 4
        if pad:
            data += '=' * (4 - pad)
        try:
            return base64.b64decode(data).decode('utf-8')
        except:
            return ''
    
    def get_file_ext(self, filename):
        idx = filename.rfind('.')
        if idx == -1:
            return ''
        return filename[idx + 1:].lower()
    
    def is_media_file(self, ext):
        return ext in self.media_exts
    
    def is_audio_file(self, ext):
        return ext in self.audio_exts
    
    def is_image_file(self, ext):
        return ext in self.image_exts
    
    def is_list_file(self, ext):
        return ext in self.list_exts
    
    def is_lrc_file(self, ext):
        return ext in self.lrc_exts
    
    def is_db_file(self, ext):
        return ext in self.db_exts
    
    def is_magnet_file(self, ext):
        return ext in self.magnet_exts
    
    def is_code_file(self, ext):
        return ext in self.code_exts
    
    def is_archive_file(self, ext):
        return ext in self.archive_exts
    
    # ==================== 优化的音频收集方法 ====================
    
    def collect_audios_in_dir(self, dir_path):
        try:
            if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
                return []
            
            current_time = time.time()
            if dir_path in self.audio_list_cache:
                cache_time = self.audio_list_cache_time.get(dir_path, 0)
                if current_time - cache_time < self.audio_cache_duration:
                    return self.audio_list_cache[dir_path]
            
            audios = []
            start_time = current_time
            
            try:
                for name in os.listdir(dir_path):
                    if time.time() - start_time > self.audio_scan_timeout:
                        break
                    
                    if name.startswith('.'):
                        continue
                    
                    full_path = os.path.join(dir_path, name)
                    
                    if os.path.isdir(full_path):
                        continue
                    
                    ext = self.get_file_ext(name)
                    if ext in self.audio_exts:
                        try:
                            if os.access(full_path, os.R_OK):
                                audios.append({
                                    'name': name,
                                    'path': full_path,
                                    'ext': ext,
                                    'mtime': os.path.getmtime(full_path)
                                })
                        except:
                            pass
                        
                        if len(audios) >= self.max_audio_per_scan:
                            break
            except Exception as e:
                self.log(f"扫描异常: {e}")
            
            audios.sort(key=lambda x: x['name'])
            
            self.audio_list_cache[dir_path] = audios
            self.audio_list_cache_time[dir_path] = current_time
            
            return audios
        except Exception as e:
            self.log(f"collect_audios_in_dir错误: {e}")
            return []
    
    # ==================== 歌曲信息提取 ====================
    
    def extract_song_info(self, filename):
        """优化的歌曲信息提取"""
        name = os.path.splitext(filename)[0]
        
        # 移除序号前缀
        name = re.sub(r'^\d+\.\s*', '', name)
        
        # 清理各种格式
        patterns_to_remove = [
            r'【.*?】', r'\[.*?\]', r'\{.*?\}', r'（.*?）',
            r'-\s*(?:320k|128k|192k|HQ|SQ|无损|高品质|高音质)',
            r'-\s*(?:Live|现场版|演唱会|歌词版|伴奏版)',
            r'\s*\(feat\..*?\)', r'\s*\(Feat\..*?\)',
            r'\s*ft\..*$', r'\s*Ft\..*$',
            r'-\d{8,}-\d+$',
            r'-\d+$',
        ]
        for pattern in patterns_to_remove:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        name = re.sub(r'\s+', ' ', name).strip()
        
        artist = ""
        song = name
        
        for sep in [' - ', '-', '–', '—', '：', ':']:
            if sep in name:
                parts = name.split(sep, 1)
                left = parts[0].strip()
                right = parts[1].strip()
                if len(left) < 30 and len(right) > 2:
                    artist, song = left, right
                    self.log(f"[解析] 使用分隔符'{sep}'解析: 歌手={artist}, 歌曲={song}")
                    break
                elif len(right) < 30 and len(left) > 2:
                    artist, song = right, left
                    self.log(f"[解析] 使用分隔符'{sep}'反向解析: 歌手={artist}, 歌曲={song}")
                    break
        
        if not artist and ' - ' in name:
            parts = name.split(' - ', 1)
            song, artist = parts[0].strip(), parts[1].strip()
            self.log(f"[解析] 使用' - '解析: 歌曲={song}, 歌手={artist}")
        
        if not artist:
            feat_match = re.search(r'(.+?)\s*\(feat\.\s*(.+?)\)', name, re.IGNORECASE)
            if feat_match:
                song = feat_match.group(1).strip()
                artist = feat_match.group(2).strip()
                self.log(f"[解析] feat解析: 歌曲={song}, 歌手={artist}")
        
        song = re.sub(r'[《》〈〉『』〔〕]', '', song).strip()
        artist = re.sub(r'热门歌曲.*$', '', artist).strip()
        artist = re.sub(r'：.*$', '', artist).strip()
        
        song = re.sub(r'-\d{8,}-\d+$', '', song)
        song = re.sub(r'-\d+$', '', song)
        
        if len(artist) > 30 and len(song) < 20:
            common_artists = [
                'G.E.M.', '邓紫棋', '周杰伦', '林俊杰', '陈奕迅', '蔡依林', '张惠妹',
                '王菲', '那英', '孙燕姿', '梁静茹', '洋澜一', '海来阿木', '程响'
            ]
            for ca in common_artists:
                if ca in artist:
                    song = artist.replace(ca, '').strip()
                    artist = ca
                    break
        
        self.log(f"[解析] 最终结果: 歌手={artist}, 歌曲={song}")
        return artist, song
    
    # ==================== 腾讯API网络获取（歌词） ====================
    
    def search_qq_song(self, song_name, artist_name=""):
        """搜索QQ音乐获取歌曲信息（用于歌词）"""
        song_name = re.sub(r'-\d{8,}-\d+$', '', song_name)
        song_name = re.sub(r'-\d+$', '', song_name)
        song_name = song_name.strip()
        
        self.log(f"[搜索] 关键词: {song_name}, 歌手: {artist_name}")
        
        cache_key = f"qq_search_{song_name}_{artist_name}"
        if cache_key in self.song_info_cache:
            cache_time = self.song_info_cache.get(cache_key + "_time", 0)
            if time.time() - cache_time < 3600:
                self.log(f"[搜索] 使用缓存")
                return self.song_info_cache[cache_key]
        
        try:
            if artist_name and artist_name not in song_name:
                keyword = f"{song_name} {artist_name}"
            else:
                keyword = song_name
            
            keyword = keyword.strip()
            
            url = f"{self.QQ_OFFICIAL_SEARCH}?is_xml=0&format=json&key={urllib.parse.quote(keyword)}"
            self.log(f"[搜索] 官方URL: {url}")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://y.qq.com/",
                "Accept": "application/json"
            }
            
            resp = self.session.get(url, headers=headers, timeout=10)
            self.log(f"[搜索] 官方状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                songs = data.get('data', {}).get('song', {}).get('itemlist', [])
                self.log(f"[搜索] 官方找到 {len(songs)} 首歌曲")
                
                if songs and len(songs) > 0:
                    best_match = None
                    for song in songs:
                        song_artist = song.get('singer', '')
                        song_name_api = song.get('name', '')
                        if artist_name and artist_name in song_artist:
                            best_match = song
                            break
                        if song_name.lower() in song_name_api.lower():
                            if not best_match:
                                best_match = song
                    
                    if not best_match:
                        best_match = songs[0]
                    
                    song_info = {
                        'name': best_match.get('name', ''),
                        'singer': best_match.get('singer', ''),
                        'mid': best_match.get('mid', ''),
                        'album': best_match.get('album', {}).get('name', '') if isinstance(best_match.get('album'), dict) else best_match.get('album', ''),
                        'interval': best_match.get('interval', 0)
                    }
                    self.log(f"[搜索] 结果: {song_info['name']} - {song_info['singer']}, mid={song_info['mid']}")
                    
                    if song_info['mid']:
                        self.song_info_cache[cache_key] = song_info
                        self.song_info_cache[cache_key + "_time"] = time.time()
                        return song_info
                    
        except Exception as e:
            self.log(f"[搜索] 异常: {e}")
        
        return None
    
    def get_qq_song_lyrics(self, song_mid):
        """获取QQ音乐歌词"""
        self.log(f"[歌词] 获取歌词, mid={song_mid}")
        
        cache_key = f"qq_lyrics_{song_mid}"
        if cache_key in self.network_lyrics_cache:
            cache_time = self.network_lyrics_cache.get(cache_key + "_time", 0)
            if time.time() - cache_time < 86400:
                self.log(f"[歌词] 使用缓存")
                return self.network_lyrics_cache[cache_key]
        
        try:
            url = f"{self.QQ_OFFICIAL_LYRIC}?format=json&nobase64=0&songmid={song_mid}"
            self.log(f"[歌词] 官方URL: {url}")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://y.qq.com/",
                "Origin": "https://y.qq.com"
            }
            
            resp = self.session.get(url, headers=headers, timeout=10)
            self.log(f"[歌词] 官方状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('retcode') == 0:
                    lyrics = data.get('lyric', '')
                    if lyrics:
                        try:
                            lyrics = base64.b64decode(lyrics).decode('utf-8')
                            if lyrics and len(lyrics) > 50:
                                self.log(f"[歌词] 获取成功, 长度={len(lyrics)}")
                                self.network_lyrics_cache[cache_key] = lyrics
                                self.network_lyrics_cache[cache_key + "_time"] = time.time()
                                return lyrics
                        except:
                            pass
                    
        except Exception as e:
            self.log(f"[歌词] 异常: {e}")
        
        return None
    
    # ==================== 网易云API获取封面 ====================
    
    def get_netease_cover(self, song_name, artist_name=""):
        """通过网易云API获取歌曲封面"""
        self.log(f"[网易云封面] 获取封面: {song_name} - {artist_name}")
        
        cache_key = f"net_cover_{song_name}_{artist_name}"
        if cache_key in self.network_cover_cache:
            return self.network_cover_cache[cache_key]
        
        try:
            keyword = song_name
            if artist_name and artist_name not in song_name:
                keyword = f"{song_name} {artist_name}"
            
            url = f"{self.NETESE_SEARCH_API}?keyword={urllib.parse.quote(keyword)}&limit=1"
            self.log(f"[网易云封面] URL: {url}")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json"
            }
            
            resp = self.session.get(url, headers=headers, timeout=8)
            self.log(f"[网易云封面] 状态码: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get('code') == 200:
                    songs = data.get('data', [])
                    if songs and len(songs) > 0:
                        cover = songs[0].get('cover', '')
                        if cover:
                            self.network_cover_cache[cache_key] = cover
                            self.log(f"[网易云封面] 获取成功: {cover[:80]}...")
                            return cover
        except Exception as e:
            self.log(f"[网易云封面] 异常: {e}")
        
        return None
    
    # ==================== 网络歌曲信息获取 ====================
    
    def get_network_song_info(self, song_name, artist_name=""):
        """通过网络获取歌曲信息（歌词用QQ，封面用网易云）"""
        self.log(f"[网络] 获取歌曲信息: {song_name} - {artist_name}")
        
        if len(song_name) < 2 or song_name.isdigit():
            if artist_name and len(artist_name) > 2:
                song_name, artist_name = artist_name, song_name
                self.log(f"[网络] 交换后: 歌曲={song_name}, 歌手={artist_name}")
        
        if len(song_name) > 30:
            for sep in [' - ', '-', '：', ':']:
                if sep in song_name:
                    parts = song_name.split(sep, 1)
                    if len(parts[1]) < len(parts[0]) and len(parts[1]) > 2:
                        song_name = parts[1].strip()
                        self.log(f"[网络] 重新提取歌曲名: {song_name}")
                    break
        
        # 搜索QQ音乐获取mid（用于歌词）
        song_info = self.search_qq_song(song_name, artist_name)
        if not song_info and artist_name and len(artist_name) > 2:
            self.log(f"[网络] 尝试用歌手名搜索: {artist_name}")
            song_info = self.search_qq_song(artist_name, "")
        
        result = {
            'title': song_name,
            'artist': artist_name,
            'album': '',
            'mid': '',
            'duration': 0
        }
        
        if song_info:
            result['title'] = song_info.get('name') or song_name
            result['artist'] = song_info.get('singer') or artist_name
            result['album'] = song_info.get('album') or ''
            result['mid'] = song_info.get('mid') or ''
            result['duration'] = song_info.get('interval') or 0
            self.log(f"[网络] mid={result['mid']}")
        
        # 使用网易云API获取封面
        if self.enable_online_poster:
            cover = self.get_netease_cover(song_name, artist_name)
            if cover:
                result['cover'] = cover
                self.log(f"[网络] 网易云封面获取成功")
        
        # 使用QQ音乐获取歌词
        if result['mid'] and self.enable_online_lyrics:
            lyrics = self.get_qq_song_lyrics(result['mid'])
            if lyrics:
                result['lyrics'] = lyrics
                self.log(f"[网络] 歌词获取成功, 长度={len(lyrics)}")
        
        return result if (result.get('cover') or result.get('lyrics')) else None
    
    # ==================== 本地歌词和封面 ====================
    
    def _get_local_cover(self, file_path):
        audio_dir = os.path.dirname(file_path)
        audio_name = os.path.splitext(os.path.basename(file_path))[0]
        
        cover_names = [
            f"{audio_name}.jpg", f"{audio_name}.jpeg", f"{audio_name}.png",
            f"{audio_name}.JPG", f"{audio_name}.JPEG", f"{audio_name}.PNG",
            "cover.jpg", "cover.jpeg", "cover.png", "folder.jpg", "album.jpg",
            "Cover.jpg", "Folder.jpg", "Album.jpg"
        ]
        
        for cover_name in cover_names:
            cover_path = os.path.join(audio_dir, cover_name)
            if os.path.exists(cover_path) and os.path.isfile(cover_path):
                self.log(f"[本地封面] 找到同目录封面: {cover_name}")
                return f"file://{cover_path}"
        
        return None
    
    def _get_local_lyrics(self, file_path):
        audio_dir = os.path.dirname(file_path)
        audio_name = os.path.splitext(os.path.basename(file_path))[0]
        
        for name in os.listdir(audio_dir):
            if name.startswith('.'):
                continue
            full_path = os.path.join(audio_dir, name)
            if not os.path.isfile(full_path):
                continue
            ext = self.get_file_ext(name)
            if ext in self.lrc_exts:
                lrc_name = os.path.splitext(name)[0]
                if lrc_name == audio_name or lrc_name.lower() == audio_name.lower():
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if content and len(content) > 20:
                                self.log(f"[本地歌词] 找到: {name}")
                                return content
                    except:
                        pass
        
        for subdir in ['Lyrics', 'lyrics', '歌词', 'LRC', 'lrc']:
            lyrics_dir = os.path.join(audio_dir, subdir)
            if os.path.exists(lyrics_dir) and os.path.isdir(lyrics_dir):
                for name in os.listdir(lyrics_dir):
                    if name.startswith('.'):
                        continue
                    full_path = os.path.join(lyrics_dir, name)
                    if not os.path.isfile(full_path):
                        continue
                    ext = self.get_file_ext(name)
                    if ext in self.lrc_exts:
                        lrc_name = os.path.splitext(name)[0]
                        if lrc_name == audio_name or lrc_name.lower() == audio_name.lower():
                            try:
                                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    if content and len(content) > 20:
                                        self.log(f"[本地歌词] 在子目录找到: {name}")
                                        return content
                            except:
                                pass
        
        return None
    
    # ==================== 音频信息添加 ====================
    
    def _add_audio_info_fast(self, result, file_path):
        filename = os.path.basename(file_path)
        artist, song = self.extract_song_info(filename)
        
        self.log(f"[音频] 文件: {filename}")
        self.log(f"[音频] 解析: 歌曲={song}, 歌手={artist}")
        
        result["title"] = song or filename
        result["artist"] = artist or ""
        
        cover_url = self._get_local_cover(file_path)
        if cover_url:
            result["poster"] = cover_url
            self.log(f"[音频] 使用本地封面")
        else:
            self.log(f"[音频] 未找到本地封面")
        
        lyrics = self._get_local_lyrics(file_path)
        if lyrics:
            result["lrc"] = lyrics
            self.log(f"[音频] 使用本地歌词")
        else:
            self.log(f"[音频] 未找到本地歌词")
        
        need_network = (not cover_url and self.enable_online_poster) or (not lyrics and self.enable_online_lyrics)
        
        if need_network and song:
            self.log(f"[音频] 尝试网络获取: {song} - {artist}")
            try:
                net_info = self.get_network_song_info(song, artist)
                if net_info:
                    if not cover_url and net_info.get('cover'):
                        result["poster"] = net_info['cover']
                        self.log(f"[音频] 使用网络封面")
                    
                    if not lyrics and net_info.get('lyrics'):
                        result["lrc"] = net_info['lyrics']
                        self.log(f"[音频] 使用网络歌词, 长度={len(net_info['lyrics'])}")
                    
                    if net_info.get('album'):
                        result["album"] = net_info['album']
                    if net_info.get('duration'):
                        result["duration"] = net_info['duration']
                else:
                    self.log(f"[音频] 网络获取失败")
            except Exception as e:
                self.log(f"[音频] 网络获取异常: {e}")
        
        if not result.get("poster"):
            result["poster"] = self.file_icons.get('music_note')
            self.log(f"[音频] 使用默认封面")
    
    # ==================== 扫描目录 ====================
    
    def scan_directory(self, dir_path):
        try:
            if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
                return []
            
            files = []
            for name in os.listdir(dir_path):
                if name.startswith('.') or name in ['.', '..']:
                    continue
                
                full_path = os.path.join(dir_path, name)
                is_dir = os.path.isdir(full_path)
                ext = self.get_file_ext(name)
                
                files.append({
                    'name': name,
                    'path': full_path,
                    'is_dir': is_dir,
                    'ext': ext,
                    'mtime': os.path.getmtime(full_path) if not is_dir else 0,
                })
            
            files.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            return files
        except:
            return []
    
    def collect_videos_in_dir(self, dir_path):
        files = self.scan_directory(dir_path)
        return [f for f in files if not f['is_dir'] and f['ext'] in self.media_exts]
    
    def collect_images_in_dir(self, dir_path):
        files = self.scan_directory(dir_path)
        return [f for f in files if not f['is_dir'] and f['ext'] in self.image_exts]
    
    def get_file_icon(self, ext, is_dir=False):
        if is_dir:
            return '📁'
        if ext in self.media_exts:
            return '🎬'
        if ext in self.audio_exts:
            return '🎵'
        if ext in self.image_exts:
            return '🖼'
        if ext in self.list_exts:
            return '📋'
        if ext in self.lrc_exts:
            return '📝'
        if ext in self.db_exts:
            return '🗄️'
        if ext in self.magnet_exts:
            return '🧲'
        if ext == 'php':
            return '🐘'
        if ext == 'py':
            return '🐍'
        if ext in self.archive_exts:
            return '🗜️'
        return '📄'
    
    def is_playable_url(self, url):
        u = str(url).lower().strip()
        if not u:
            return False
        
        protocols = [
            'http://', 'https://', 'rtmp://', 'rtsp://', 'udp://', 'rtp://', 
            'file://', 'pics://', 'mp3://', 'magnet:', 'ed2k://', 'thunder://', 'ftp://',
            'vod://', 'bilibili://', 'youtube://', 'rtmps://', 'rtmpt://', 'hls://',
            'http-live://', 'https-live://', 'tvbus://', 'tvbox://', 'live://', 'novel://', 'text://'
        ]
        if any(u.startswith(p) for p in protocols):
            return True
        
        exts = [
            '.mp4', '.mkv', '.avi', '.rmvb', '.mov', '.wmv', '.flv', 
            '.m3u8', '.ts', '.mp3', '.m4a', '.aac', '.flac', '.wav', 
            '.webm', '.ogg', '.m4v', '.f4v', '.3gp', '.mpg', '.mpeg',
            '.m3u', '.pls', '.asf', '.asx', '.wmx'
        ]
        if any(ext in u for ext in exts):
            return True
        
        patterns = [
            'youtu.be/', 'youtube.com/', 'bilibili.com/', 'iqiyi.com/', 
            'v.qq.com/', 'youku.com/', 'tudou.com/', 'mgtv.com/',
            'sohu.com/', 'acfun.cn/', 'douyin.com/', 'kuaishou.com/',
            'huya.com/', 'douyu.com/', 'twitch.tv/', 'live.'
        ]
        return any(p in u for p in patterns)
    
    # ==================== 彩色图标生成 ====================
    
    def _generate_colored_icon(self, color, text):
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
            <rect width="200" height="200" rx="40" ry="40" fill="{color}"/>
            <text x="100" y="140" font-size="120" text-anchor="middle" fill="white" font-family="Arial" font-weight="bold">{text}</text>
        </svg>'''
        return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"
    
    # ==================== JSON文件解析 ====================
    
    def parse_json_file(self, file_path):
        items = []
        try:
            self.log(f"开始解析JSON文件: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(30 * 1024 * 1024)
            
            if content.startswith('\ufeff'):
                content = content[1:]
            
            data = json.loads(content)
            
            if isinstance(data, list):
                item_list = data
                self.log(f"📋 JSON是数组格式，共 {len(item_list)} 项")
            elif isinstance(data, dict):
                if 'vod_play_url' in data:
                    self.log("📺 检测到TVBox单视频格式")
                    return self._handle_vod_format(data, file_path)
                
                if 'vod_play_from' in data and 'vod_play_url' in data:
                    self.log("📺 检测到TVBox多线路格式")
                    return self._handle_multi_line_vod(data, file_path)
                
                possible_keys = ['list', 'data', 'items', 'videos', 'vod', 'results', 'rows']
                item_list = None
                for key in possible_keys:
                    if key in data and isinstance(data[key], list):
                        item_list = data[key]
                        self.log(f"🔑 找到键 '{key}'，包含 {len(item_list)} 项")
                        break
                
                if item_list is None and all(isinstance(v, dict) for v in data.values()):
                    item_list = list(data.values())
                    self.log(f"📚 将字典所有值作为列表，共 {len(item_list)} 项")
                
                if item_list is None:
                    item_list = [data]
                    self.log("📄 将整个字典作为单个项目处理")
            else:
                self.log(f"⚠️ 未知的JSON类型: {type(data)}")
                return items
            
            for idx, item in enumerate(item_list):
                if not isinstance(item, dict):
                    if isinstance(item, str) and self.is_playable_url(item):
                        items.append({
                            'name': f'链接{idx+1}',
                            'url': item,
                            'pic': '',
                            'remarks': ''
                        })
                    continue
                
                name = self._extract_json_field(item, ['name', 'title', 'vod_name', 'video_name', 'show_name'])
                if not name:
                    name = f"项目{idx+1}"
                
                url = self._extract_json_field(item, ['url', 'link', 'play_url', 'video_url', 'vod_url', 'vod_play_url'])
                
                if not url:
                    play_url_raw = self._extract_json_field(item, ['vod_play_url', 'play_url'])
                    if play_url_raw and ('$' in play_url_raw or '#' in play_url_raw):
                        episodes = self._parse_multi_episodes(play_url_raw, name)
                        for ep in episodes:
                            ep_item = {
                                'name': ep['name'],
                                'url': ep['url'],
                                'pic': self._extract_json_field(item, ['pic', 'cover', 'image', 'vod_pic'], True),
                                'remarks': self._extract_json_field(item, ['remarks', 'vod_remarks', 'note'])
                            }
                            items.append(ep_item)
                        continue
                    elif play_url_raw:
                        url = play_url_raw
                
                if not url or not self.is_playable_url(url):
                    continue
                
                pic = self._extract_json_field(item, ['pic', 'cover', 'image', 'vod_pic'], True)
                remarks = self._extract_json_field(item, ['remarks', 'vod_remarks', 'note'])
                
                items.append({
                    'name': name,
                    'url': url,
                    'pic': pic,
                    'remarks': remarks
                })
            
            self.log(f"✅ JSON解析完成: {os.path.basename(file_path)}, 共 {len(items)} 条记录")
            
        except json.JSONDecodeError as e:
            self.log(f"❌ JSON解析失败: {e}")
        except Exception as e:
            self.log(f"❌ JSON解析异常: {e}")
        
        return items
    
    def _handle_vod_format(self, data, file_path):
        items = []
        name = data.get('vod_name') or data.get('name') or os.path.splitext(os.path.basename(file_path))[0]
        play_url = data.get('vod_play_url', '')
        pic = data.get('vod_pic') or data.get('pic') or ''
        remarks = data.get('vod_remarks', '')
        
        if play_url and ('$' in play_url or '#' in play_url):
            episodes = self._parse_multi_episodes(play_url, name)
            for ep in episodes:
                items.append({
                    'name': ep['name'],
                    'url': ep['url'],
                    'pic': pic,
                    'remarks': remarks
                })
        else:
            items.append({
                'name': name,
                'url': play_url,
                'pic': pic,
                'remarks': remarks
            })
        return items
    
    def _handle_multi_line_vod(self, data, file_path):
        items = []
        vod_name = data.get('vod_name') or data.get('name') or os.path.splitext(os.path.basename(file_path))[0]
        vod_pic = data.get('vod_pic') or data.get('pic') or ''
        
        play_from = data.get('vod_play_from', '')
        play_url = data.get('vod_play_url', '')
        
        from_list = play_from.split('$$$') if play_from else ['默认线路']
        url_list = play_url.split('$$$') if play_url else ['']
        
        for from_name, url_group in zip(from_list, url_list):
            if url_group and ('$' in url_group or '#' in url_group):
                episodes = self._parse_multi_episodes(url_group, f"{vod_name}[{from_name}]")
                for ep in episodes:
                    items.append({
                        'name': ep['name'],
                        'url': ep['url'],
                        'pic': vod_pic,
                        'remarks': f'线路:{from_name}'
                    })
        
        return items
    
    def _parse_multi_episodes(self, play_url_raw, base_name):
        episodes = []
        groups = play_url_raw.split('$$$')
        for group_idx, group in enumerate(groups):
            if not group:
                continue
            
            parts = group.split('#')
            for part_idx, part in enumerate(parts):
                if not part:
                    continue
                
                if '$' in part:
                    ep_name, ep_url = part.split('$', 1)
                    episodes.append({
                        'name': ep_name.strip(),
                        'url': ep_url.strip()
                    })
                else:
                    episodes.append({
                        'name': f"{base_name} - 节目{len(episodes)+1}",
                        'url': part.strip()
                    })
        
        return episodes
    
    def _extract_json_field(self, item, field_names, is_image=False):
        for field in field_names:
            if field in item and item[field]:
                value = item[field]
                
                if isinstance(value, dict):
                    for url_field in ['url', 'src', 'path', 'file']:
                        if url_field in value and value[url_field]:
                            return str(value[url_field])
                    if is_image:
                        for img_field in ['large', 'medium', 'small', 'thumb']:
                            if img_field in value and value[img_field]:
                                return str(value[img_field])
                    return str(value)
                
                elif isinstance(value, list) and value:
                    if is_image:
                        first = value[0]
                        if isinstance(first, dict):
                            for url_field in ['url', 'src', 'path']:
                                if url_field in first and first[url_field]:
                                    return str(first[url_field])
                            return str(first)
                        else:
                            return str(first)
                    else:
                        for v in value:
                            if v and isinstance(v, str):
                                return v
                        return str(value[0]) if value else ''
                
                else:
                    return str(value).strip()
        
        return ''
    
    # ==================== 数据库文件解析 ====================
    
    def parse_db_file(self, file_path):
        return self.db_reader.read_sqlite(file_path, MAX_DB_RESULTS)
    
    # ==================== 在线直播 ====================
    
    def _fetch_with_auto_headers(self, url):
        domain = self._get_domain_from_url(url)
        self.log(f"获取直播源: {domain}")
        
        if domain in self.domain_specific_headers:
            for headers_info in self.domain_specific_headers[domain]:
                try:
                    resp = self.session.get(url, headers=headers_info['headers'], timeout=15)
                    if resp.status_code == 200:
                        return resp.text
                except:
                    continue
        
        for headers_info in self.common_headers_list:
            try:
                resp = self.session.get(url, headers=headers_info['headers'], timeout=10)
                if resp.status_code == 200:
                    return resp.text
            except:
                continue
        
        return None
    
    def _get_domain_from_url(self, url):
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            return domain.split(':')[0] if ':' in domain else domain
        except:
            return ""
    
    def _get_live_programs(self, source):
        source_id = source['id']
        current_time = time.time()
        
        if source_id in self.live_cache and current_time - self.live_cache_time.get(source_id, 0) < self.live_cache_duration:
            return self.live_cache[source_id]
        
        content = self._fetch_with_auto_headers(source['url'])
        if not content:
            return []
        
        programs = self._parse_live_content(content, source)
        
        if programs:
            self.live_cache[source_id] = programs
            self.live_cache_time[source_id] = current_time
        
        return programs
    
    def _parse_live_content(self, content, source):
        if source.get('type') == 'txt' or ',#genre#' in content:
            return self._parse_txt_live(content)
        elif content.strip().startswith(('{', '[')):
            return self._parse_json_live(content)
        else:
            return self._parse_m3u_live(content)
    
    def _parse_m3u_live(self, content):
        programs = []
        lines = content.split('\n')
        current_name = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#EXTINF:'):
                name_match = re.search(r',(.+)$', line) or re.search(r'tvg-name="([^"]+)"', line)
                current_name = name_match.group(1).strip() if name_match else None
            elif line and not line.startswith('#') and current_name:
                if self.is_playable_url(line):
                    programs.append({'name': current_name, 'url': line})
                current_name = None
        return programs
    
    def _parse_txt_live(self, content):
        programs = []
        lines = content.split('\n')
        current_cat = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ',#genre#' in line:
                current_cat = line.split(',')[0].strip()
                continue
            if ',' in line:
                parts = line.split(',', 1)
                name = parts[0].strip()
                url = parts[1].strip()
                if self.is_playable_url(url):
                    display_name = f"[{current_cat}] {name}" if current_cat else name
                    programs.append({'name': display_name, 'url': url})
        return programs
    
    def _parse_json_live(self, content):
        programs = []
        try:
            data = json.loads(content)
            items = []
            if isinstance(data, dict):
                for key in ['list', 'data', 'items', 'videos']:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
                if not items:
                    items = [data]
            else:
                items = data
            for item in items:
                if isinstance(item, dict):
                    name = item.get('name') or item.get('title')
                    url = item.get('url') or item.get('play_url')
                    if name and url and self.is_playable_url(url):
                        programs.append({'name': name, 'url': url})
        except:
            pass
        return programs
    
    # ==================== 首页和分类 ====================
    
    def homeContent(self, filter):
        classes = []
        
        for i, path in enumerate(self.root_paths):
            if os.path.exists(path):
                name = self.path_to_chinese.get(path, os.path.basename(path.rstrip('/')) or f'目录{i}')
                classes.append({"type_id": f"root_{i}", "type_name": name})
        
        classes.append({"type_id": "recent", "type_name": "最近添加"})
        classes.append({"type_id": self.live_category_id, "type_name": self.live_category_name})
        # 添加短视频分类
        classes.append({"type_id": "short_video", "type_name": "📱 短视频"})
        
        return {'class': classes}
    
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        
        # 短视频分类
        if tid == "short_video":
            return self._short_video_category_content(pg)
        
        # 短视频源详情
        if tid.startswith("short_video_"):
            encoded_url = tid[len("short_video_"):]
            return self._short_video_source_detail(encoded_url)
        
        if tid == self.live_category_id:
            return self._live_category_content(pg)
        
        if tid == 'recent':
            return self._recent_content(pg)
        
        path = self._resolve_path(tid)
        if not path or not os.path.exists(path) or not os.path.isdir(path):
            return {'list': [], 'page': pg, 'pagecount': 1}
        
        files = self.scan_directory(path)
        total = len(files)
        
        per_page = 50
        start = (pg - 1) * per_page
        end = min(start + per_page, total)
        page_files = files[start:end]
        
        vlist = []
        
        parent_item = self._create_parent_item(path)
        if parent_item:
            vlist.append(parent_item)
        
        for f in page_files:
            item = self._create_file_item(f)
            if item:
                vlist.append(item)
        
        return {
            'list': vlist,
            'page': pg,
            'pagecount': (total + per_page - 1) // per_page,
            'limit': per_page,
            'total': total
        }
    
    def _resolve_path(self, tid):
        if tid.startswith('root_'):
            try:
                idx = int(tid[5:])
                return self.root_paths[idx] if idx < len(self.root_paths) else None
            except:
                return None
        elif tid.startswith(self.FOLDER_PREFIX):
            return self.b64u_decode(tid[len(self.FOLDER_PREFIX):])
        return tid if os.path.exists(tid) else None
    
    def _create_parent_item(self, current_path):
        parent = os.path.dirname(current_path)
        
        for root in self.root_paths:
            if os.path.normpath(current_path) == os.path.normpath(root.rstrip('/')):
                return None
        
        if not parent or parent == current_path:
            return None
        
        for i, root in enumerate(self.root_paths):
            if os.path.normpath(parent) == os.path.normpath(root.rstrip('/')):
                parent_id = f"root_{i}"
                parent_name = self.path_to_chinese.get(root, os.path.basename(parent))
                break
        else:
            parent_id = self.FOLDER_PREFIX + self.b64u_encode(parent)
            parent_name = os.path.basename(parent)
        
        return {
            'vod_id': parent_id,
            'vod_name': f'⬅️ 返回 {parent_name}',
            'vod_pic': self.file_icons['folder'],
            'vod_remarks': '',
            'vod_tag': 'folder',
            'style': {'type': 'list'}
        }
    
    # ==================== 文件项创建 ====================
    
    def _create_file_item(self, f):
        icon = self.get_file_icon(f['ext'], f['is_dir'])
        
        if f['is_dir']:
            return {
                'vod_id': self.FOLDER_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"{icon} {f['name']}",
                'vod_pic': self.file_icons['folder'],
                'vod_remarks': '文件夹',
                'vod_tag': 'folder',
                'style': {'type': 'list'}
            }
        
        if self.is_image_file(f['ext']) or f['ext'].lower() in ['heic', 'heif']:
            return {
                'vod_id': f['path'],
                'vod_name': f"🖼 {f['name']}",
                'vod_pic': f"file://{f['path']}",
                'vod_play_url': f"查看${self.PICS_PREFIX}file://{f['path']}",
                'vod_remarks': '照片',
                'vod_tag': 'image',
                'style': {'type': 'grid', 'ratio': 1},
                'vod_player': '画'
            }
        
        if self.is_audio_file(f['ext']):
            return {
                'vod_id': f['path'],
                'vod_name': f"🎵 {f['name']}",
                'vod_pic': self.file_icons['music_note'],
                'vod_play_url': f"播放${self.MP3_PREFIX + f['path']}",
                'vod_remarks': '音频',
                'vod_tag': 'audio',
                'style': {'type': 'list'}
            }
        
        if self.is_media_file(f['ext']):
            return {
                'vod_id': f['path'],
                'vod_name': f"🎬 {f['name']}",
                'vod_pic': self.file_icons['video'],
                'vod_remarks': '视频',
                'vod_tag': 'video',
                'style': {'type': 'list'}
            }
        
        if self.is_lrc_file(f['ext']):
            return {
                'vod_id': f['path'],
                'vod_name': f"📝 {f['name']}",
                'vod_pic': self.file_icons['lyrics'],
                'vod_remarks': '歌词',
                'vod_tag': 'lrc',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'json':
            return {
                'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"📋 {f['name']}",
                'vod_pic': self.file_icons['json'],
                'vod_play_url': f"查看${self.LIST_PREFIX + self.b64u_encode(f['path'])}",
                'vod_remarks': 'JSON数据',
                'vod_tag': 'json',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'php':
            return {
                'vod_id': self.TEXT_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🐘 {f['name']}",
                'vod_pic': self.file_icons['php'],
                'vod_remarks': 'PHP文件',
                'vod_tag': 'php',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'py':
            return {
                'vod_id': self.TEXT_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🐍 {f['name']}",
                'vod_pic': self.file_icons['python'],
                'vod_remarks': 'Python文件',
                'vod_tag': 'python',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'zip':
            return {
                'vod_id': f['path'],
                'vod_name': f"🗜️ {f['name']}",
                'vod_pic': self.file_icons['zip'],
                'vod_remarks': 'ZIP压缩包',
                'vod_tag': 'zip',
                'style': {'type': 'list'}
            }
        
        if f['ext'] in ['rar', '7z', 'tar', 'gz', 'bz2', 'xz']:
            icon_key = 'rar' if f['ext'] == 'rar' else 'archive'
            return {
                'vod_id': f['path'],
                'vod_name': f"🗜️ {f['name']}",
                'vod_pic': self.file_icons[icon_key],
                'vod_remarks': f'{f["ext"].upper()}压缩包',
                'vod_tag': 'archive',
                'style': {'type': 'list'}
            }
        
        if f['ext'] in ['m3u', 'm3u8']:
            colors = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#9D65C9", "#FF8C42", "#A2D729", "#FF6B8B", "#45B7D1", "#96CEB4"]
            color = colors[hash(f['name']) % len(colors)]
            first_char = f['name'][0].upper() if f['name'] else "M"
            icon_svg = self._generate_colored_icon(color, first_char)
            
            return {
                'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f['name'],
                'vod_pic': icon_svg,
                'vod_play_url': f"播放${self.LIST_PREFIX + self.b64u_encode(f['path'])}",
                'vod_remarks': '直播源',
                'vod_tag': 'live_m3u',
                'style': {'type': 'list'}
            }
        
        if self.is_db_file(f['ext']):
            return {
                'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🗄️ {f['name']}",
                'vod_pic': self.file_icons['database'],
                'vod_remarks': '数据库',
                'vod_tag': 'database',
                'style': {'type': 'list'}
            }
        
        if self.is_magnet_file(f['ext']):
            return {
                'vod_id': self.MAGNET_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🧲 {f['name']}",
                'vod_pic': self.file_icons['magnet'],
                'vod_remarks': '磁力链接',
                'vod_tag': 'magnet',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'txt':
            is_live_source = False
            url_count = 0
            
            try:
                with open(f['path'], 'r', encoding='utf-8', errors='ignore') as ff:
                    content = ff.read(2048)
                    
                    if ',#genre#' in content.lower():
                        is_live_source = True
                    else:
                        lines = content.split('\n')
                        for line in lines[:30]:
                            line = line.strip()
                            line_lower = line.lower()
                            
                            if ',' in line:
                                parts = line.split(',', 1)
                                if len(parts) == 2:
                                    url = parts[1].strip()
                                    if url.startswith(('http://', 'https://')):
                                        if any(ext in url.lower() for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                                            url_count += 1
                                        elif re.match(r'https?://[\d.]+:\d+', url):
                                            url_count += 1
                            
                            elif self.is_playable_url(line):
                                if any(ext in line_lower for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                                    url_count += 1
                            
                            if url_count >= 3:
                                break
            except Exception as e:
                self.log(f"读取TXT文件失败: {e}")
            
            if is_live_source or url_count >= 3:
                colors = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#9D65C9", "#FF8C42", "#A2D729", "#FF6B8B", "#45B7D1", "#96CEB4"]
                color = colors[hash(f['name']) % len(colors)]
                first_char = f['name'][0].upper() if f['name'] else "T"
                icon_svg = self._generate_colored_icon(color, first_char)
                
                return {
                    'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                    'vod_name': f['name'],
                    'vod_pic': icon_svg,
                    'vod_play_url': f"播放${self.LIST_PREFIX + self.b64u_encode(f['path'])}",
                    'vod_remarks': f'直播源 ({url_count}个链接)',
                    'vod_tag': 'live_txt',
                    'style': {'type': 'list'}
                }
            else:
                encoded = self.b64u_encode(f['path'])
                novel_url = f"{self.NOVEL_PREFIX}{encoded}"
                return {
                    'vod_id': novel_url,
                    'vod_name': f"📖 {f['name']}",
                    'vod_pic': self.file_icons['novel'],
                    'vod_play_url': f"阅读${novel_url}",
                    'vod_remarks': '小说',
                    'vod_tag': 'novel',
                    'style': {'type': 'list'},
                    'vod_player': '书'
                }
        
        if f['ext'] in ['xml', 'html', 'htm', 'css', 'js', 'sh', 'bash']:
            return {
                'vod_id': self.TEXT_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"📄 {f['name']}",
                'vod_pic': self.file_icons['text'],
                'vod_remarks': '代码文件',
                'vod_tag': 'code',
                'style': {'type': 'list'}
            }
        
        if f['ext']:
            return {
                'vod_id': f['path'],
                'vod_name': f"📁 {f['name']}",
                'vod_pic': self.file_icons['file'],
                'vod_remarks': f'{f["ext"].upper()}文件',
                'vod_tag': 'unknown',
                'style': {'type': 'list'}
            }
        else:
            return {
                'vod_id': f['path'],
                'vod_name': f"📁 {f['name']}",
                'vod_pic': self.file_icons['file'],
                'vod_remarks': '无扩展名',
                'vod_tag': 'unknown',
                'style': {'type': 'list'}
            }
    
    def _live_category_content(self, pg):
        vlist = []
        
        for idx, source in enumerate(self.online_live_sources):
            programs = self._get_live_programs(source)
            color = source.get('color', self.default_colors[idx % len(self.default_colors)])
            first_char = source['name'][0] if source['name'] else "直"
            icon = self._generate_colored_icon(color, first_char)
            
            remarks = source.get('remarks', '')
            if programs:
                remarks += f" {len(programs)}个节目"
            else:
                remarks += " 加载失败"
            
            vlist.append({
                'vod_id': self.LIVE_PREFIX + self.b64u_encode(source['id']),
                'vod_name': source['name'],
                'vod_pic': icon,
                'vod_remarks': remarks,
                'vod_tag': 'live_source',
                'style': {'type': 'list'},
                'type': 'live'
            })
        
        return {
            'list': vlist,
            'page': pg,
            'pagecount': 1,
            'limit': len(vlist),
            'total': len(vlist)
        }
    
    def _recent_content(self, pg):
        all_files = []
        
        for path in self.root_paths:
            if os.path.exists(path):
                self._scan_recent_files(path, all_files)
        
        all_files.sort(key=lambda x: x['mtime'], reverse=True)
        all_files = all_files[:200]
        
        per_page = 50
        start = (pg - 1) * per_page
        end = min(start + per_page, len(all_files))
        
        vlist = []
        for f in all_files[start:end]:
            item = self._create_recent_item(f)
            if item:
                vlist.append(item)
        
        return {
            'list': vlist,
            'page': pg,
            'pagecount': (len(all_files) + per_page - 1) // per_page,
            'limit': per_page,
            'total': len(all_files)
        }
    
    def _scan_recent_files(self, path, file_list, depth=0, max_depth=2):
        if depth > max_depth:
            return
        
        try:
            for name in os.listdir(path):
                if name.startswith('.'):
                    continue
                
                full_path = os.path.join(path, name)
                
                if os.path.isdir(full_path):
                    self._scan_recent_files(full_path, file_list, depth + 1, max_depth)
                else:
                    ext = self.get_file_ext(name)
                    if (self.is_media_file(ext) or self.is_audio_file(ext) or 
                        self.is_image_file(ext) or self.is_list_file(ext) or
                        self.is_db_file(ext) or self.is_magnet_file(ext) or
                        self.is_code_file(ext) or self.is_archive_file(ext) or
                        ext == 'txt'):
                        
                        mtime = os.path.getmtime(full_path)
                        if time.time() - mtime < 7 * 24 * 3600:
                            file_list.append({
                                'name': name,
                                'path': full_path,
                                'ext': ext,
                                'mtime': mtime,
                            })
        except:
            pass
    
    def _create_recent_item(self, f):
        icon = self.get_file_icon(f['ext'], False)
        
        if self.is_image_file(f['ext']) or f['ext'].lower() in ['heic', 'heif']:
            return {
                'vod_id': self.URL_B64U_PREFIX + self.b64u_encode(self.PICS_PREFIX + "file://" + f['path']),
                'vod_name': f"🖼 {f['name']}",
                'vod_pic': f"file://{f['path']}",
                'vod_play_url': f"查看${self.PICS_PREFIX}file://{f['path']}",
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1},
                'vod_player': '画'
            }
        
        if self.is_audio_file(f['ext']):
            return {
                'vod_id': self.URL_B64U_PREFIX + self.b64u_encode(self.MP3_PREFIX + f['path']),
                'vod_name': f"🎵 {f['name']}",
                'vod_pic': self.file_icons['music_note'],
                'vod_play_url': f"播放${self.MP3_PREFIX + f['path']}",
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if self.is_media_file(f['ext']):
            return {
                'vod_id': f['path'],
                'vod_name': f"🎬 {f['name']}",
                'vod_pic': self.file_icons['video'],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if self.is_lrc_file(f['ext']):
            return {
                'vod_id': f['path'],
                'vod_name': f"📝 {f['name']}",
                'vod_pic': self.file_icons['lyrics'],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if f['ext'] == 'json':
            return {
                'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"📋 {f['name']}",
                'vod_pic': self.file_icons['json'],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if f['ext'] == 'php':
            return {
                'vod_id': self.TEXT_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🐘 {f['name']}",
                'vod_pic': self.file_icons['php'],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if f['ext'] == 'py':
            return {
                'vod_id': self.TEXT_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🐍 {f['name']}",
                'vod_pic': self.file_icons['python'],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if f['ext'] == 'zip':
            return {
                'vod_id': f['path'],
                'vod_name': f"🗜️ {f['name']}",
                'vod_pic': self.file_icons['zip'],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if f['ext'] in ['rar', '7z', 'tar', 'gz', 'bz2', 'xz']:
            icon_key = 'rar' if f['ext'] == 'rar' else 'archive'
            return {
                'vod_id': f['path'],
                'vod_name': f"🗜️ {f['name']}",
                'vod_pic': self.file_icons[icon_key],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if f['ext'] in ['m3u', 'm3u8']:
            colors = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#9D65C9", "#FF8C42", "#A2D729", "#FF6B8B", "#45B7D1", "#96CEB4"]
            color = colors[hash(f['name']) % len(colors)]
            first_char = f['name'][0].upper() if f['name'] else "M"
            icon_svg = self._generate_colored_icon(color, first_char)
            return {
                'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f['name'],
                'vod_pic': icon_svg,
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if self.is_db_file(f['ext']):
            return {
                'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🗄️ {f['name']}",
                'vod_pic': self.file_icons['database'],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if self.is_magnet_file(f['ext']):
            return {
                'vod_id': self.MAGNET_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🧲 {f['name']}",
                'vod_pic': self.file_icons['magnet'],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        if f['ext'] == 'txt':
            is_live = False
            url_count = 0
            try:
                with open(f['path'], 'r', encoding='utf-8', errors='ignore') as ff:
                    content = ff.read(2048)
                    
                    if ',#genre#' in content.lower():
                        is_live = True
                    else:
                        lines = content.split('\n')
                        for line in lines[:30]:
                            line = line.strip()
                            line_lower = line.lower()
                            
                            if ',' in line:
                                parts = line.split(',', 1)
                                if len(parts) == 2:
                                    url = parts[1].strip()
                                    if url.startswith(('http://', 'https://')):
                                        if any(ext in url.lower() for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                                            url_count += 1
                                        elif re.match(r'https?://[\d.]+:\d+', url):
                                            url_count += 1
                            
                            elif self.is_playable_url(line):
                                if any(ext in line_lower for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                                    url_count += 1
                            
                            if url_count >= 3 or is_live:
                                break
            except:
                pass
            
            if is_live or url_count >= 3:
                colors = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#9D65C9", "#FF8C42", "#A2D729", "#FF6B8B", "#45B7D1", "#96CEB4"]
                color = colors[hash(f['name']) % len(colors)]
                first_char = f['name'][0].upper() if f['name'] else "T"
                icon_svg = self._generate_colored_icon(color, first_char)
                return {
                    'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                    'vod_name': f['name'],
                    'vod_pic': icon_svg,
                    'vod_remarks': self._format_time(f['mtime']),
                    'style': {'type': 'grid', 'ratio': 1}
                }
            else:
                encoded = self.b64u_encode(f['path'])
                novel_url = f"{self.NOVEL_PREFIX}{encoded}"
                return {
                    'vod_id': novel_url,
                    'vod_name': f"📖 {f['name']}",
                    'vod_pic': self.file_icons['novel'],
                    'vod_remarks': self._format_time(f['mtime']),
                    'style': {'type': 'grid', 'ratio': 1},
                    'vod_player': '书'
                }
        
        if f['ext'] in ['xml', 'html', 'htm', 'css', 'js', 'sh', 'bash']:
            return {
                'vod_id': self.TEXT_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"📄 {f['name']}",
                'vod_pic': self.file_icons['text'],
                'vod_remarks': self._format_time(f['mtime']),
                'style': {'type': 'grid', 'ratio': 1}
            }
        
        return {
            'vod_id': f['path'],
            'vod_name': f"📁 {f['name']}",
            'vod_pic': self.file_icons['file'],
            'vod_remarks': self._format_time(f['mtime']),
            'style': {'type': 'grid', 'ratio': 1}
        }
    
    def _format_time(self, timestamp):
        diff = time.time() - timestamp
        if diff < 3600:
            return f"{int(diff/60)}分钟前"
        elif diff < 86400:
            return f"{int(diff/3600)}小时前"
        else:
            return time.strftime('%m-%d %H:%M', time.localtime(timestamp))
    
    # ==================== 短视频相关方法 ====================
    
    def _short_video_category_content(self, pg):
        """短视频分类内容 - 带彩色图标"""
        pg = int(pg)
        
        # 短视频API列表 - 每个都有固定的颜色
        short_video_apis = [
    {"name": "🔥 小姐姐1", "url": "http://api.tinise.cn/api/xjjsp", "color": "#FF6B6B"},
           {"name": "🎀 小姐姐2", "url": "http://av.npcq.cn/pc.php?type=video", "color": "#EF5350"},
            {"name": "💃 小姐姐3", "url": "http://api.yujn.cn/api/zzxjj.php?type=video", "color": "#FF69B4"},
            {"name": "🎀 小姐姐4", "url": "http://api.yujn.cn/api/zzxjj.php?type=video", "color": "#EF5350"},
            {"name": "✨ 随机小姐姐聚合", "url": "https://sucyan.top/api/video/?msg=jk", "color": "#9B59B6"},
            {"name": "🎵 抖音小姐姐", "url": "http://api.qemao.com/api/douyin/", "color": "#3498DB"},
            {"name": "👑 高质量美女", "url": "http://www.wudada.online/Api/NewSp", "color": "#E91E63"},
            {"name": "💪 完美身材", "url": "http://api.yujn.cn/api/wmsc.php?type=video", "color": "#FF9800"},
            {"name": "🎭 快手变装", "url": "http://api.yujn.cn/api/ksbianzhuang.php?type=video", "color": "#4CAF50"},
            {"name": "🎬 抖音变装", "url": "http://api.yujn.cn/api/bianzhuang.php?", "color": "#00BCD4"},
            {"name": "🤍 白丝系列", "url": "http://api.yujn.cn/api/baisis.php?type=video", "color": "#9E9E9E"},
            {"name": "👗 美女穿搭", "url": "http://api.yujn.cn/api/chuanda.php?type=video", "color": "#FF5722"},
            {"name": "🎲 随机小姐姐", "url": "http://api.yujn.cn/api/xjj.php?type=video", "color": "#673AB7"},
            {"name": "🖤 黑丝系列", "url": "http://api.yujn.cn/api/heisis.php?type=video", "color": "#3F51B5"},
            {"name": "🤍 黑白丝", "url": "http://api.tinise.cn/api/baisi", "color": "#607D8B"},
            {"name": "⚪ 黑白丝2", "url": "http://api.tinise.cn/api/heisi", "color": "#795548"},
            {"name": "🎓 快手女大学生", "url": "https://api.yujn.cn/api/nvda.php?type=video", "color": "#8BC34A"},
            {"name": "👁️ 抖音瞳瞳系列", "url": "https://api.yujn.cn/api/tongtong.php?type=video", "color": "#FF4081"},
            {"name": "💃 丝滑舞蹈", "url": "http://api.yujn.cn/api/shwd.php?type=video", "color": "#7C4DFF"},
            {"name": "🌟 鞠婧祎系列", "url": "http://api.yujn.cn/api/jjy.php?type=video", "color": "#FFD740"},
            {"name": "🏮 古风类", "url": "http://api.yujn.cn/api/hanfu.php?type=video", "color": "#E65100"},
            {"name": "🎧 慢摇系列", "url": "http://api.yujn.cn/api/manyao.php?type=video", "color": "#00897B"},
            {"name": "👙 吊带系列", "url": "http://api.yujn.cn/api/diaodai.php?type=video", "color": "#F06292"},
            {"name": "🌸 清纯系列", "url": "http://api.yujn.cn/api/qingchun.php?type=video", "color": "#EC407A"},
            {"name": "🎮 COS系列", "url": "http://api.yujn.cn/api/COS.php?type=video", "color": "#AB47BC"},
            {"name": "👧 纯情女高", "url": "http://api.yujn.cn/api/nvgao.php?type=video", "color": "#FFA726"},
            {"name": "📸 街拍系列", "url": "http://api.yujn.cn/api/jiepai.php?type=video", "color": "#26A69A"},
            {"name": "🎀 萝莉系列", "url": "http://api.yujn.cn/api/luoli.php?type=video", "color": "#EF5350"},
            {"name": "🍬 甜妹系列", "url": "http://api.yujn.cn/api/tianmei.php?type=video", "color": "#42A5F5"},
        ]
        
        vlist = []
        
        for idx, api in enumerate(short_video_apis):
            # 使用配置的颜色
            color = api.get('color', self.default_colors[idx % len(self.default_colors)])
            # 提取第一个字符（去掉emoji）
            clean_name = re.sub(r'[^\w\u4e00-\u9fff]', '', api['name'])
            first_char = clean_name[0] if clean_name else "视"
            icon = self._generate_colored_icon(color, first_char)
            
            # 编码URL
            encoded_url = self.b64u_encode(api['url'])
            
            vlist.append({
                'vod_id': f"short_video_{encoded_url}",
                'vod_name': f"📱 {api['name']}",
                'vod_pic': icon,
                'vod_remarks': '点击播放',
                'vod_tag': 'short_video_source',
                'style': {'type': 'list'}
            })
        
        # 添加自定义API入口
        vlist.append({
            'vod_id': 'add_custom_api',
            'vod_name': '➕ 添加自定义API',
            'vod_pic': self._generate_colored_icon("#4ECDC4", "+"),
            'vod_remarks': '点击添加自定义短视频源',
            'vod_tag': 'add_api',
            'style': {'type': 'list'}
        })
        
        self.log(f"短视频分类返回 {len(vlist)} 个源")
        
        return {
            'list': vlist,
            'page': pg,
            'pagecount': 1,
            'limit': len(vlist),
            'total': len(vlist)
        }
    
    def _short_video_source_detail(self, encoded_url):
        """短视频源详情 - 99个视频"""
        self.log(f"短视频源详情请求: {encoded_url}")
        
        try:
            api_url = self.b64u_decode(encoded_url)
            self.log(f"解码后的URL: {api_url}")
        except Exception as e:
            self.log(f"解码失败: {e}")
            return {'list': []}
        
        # 查找API名称和颜色
        api_name = "短视频源"
        api_color = "#FF6B6B"
        short_video_apis = [
            {"name": "🎀 小姐姐1", "url": "http://av.npcq.cn/pc.php?type=video", "color": "#EF5350"},
            {"name": "🔥 小姐姐2", "url": "http://api.tinise.cn/api/xjjsp", "color": "#FF6B6B"},
            {"name": "💃 小姐姐3", "url": "http://api.yujn.cn/api/zzxjj.php?type=video", "color": "#FF69B4"},
            {"name": "🎀 小姐姐4", "url": "http://api.yujn.cn/api/zzxjj.php?type=video", "color": "#EF5350"},
            {"name": "✨ 随机小姐姐聚合", "url": "https://sucyan.top/api/video/?msg=jk", "color": "#9B59B6"},
            {"name": "🎵 抖音小姐姐", "url": "http://api.qemao.com/api/douyin/", "color": "#3498DB"},
            {"name": "👑 高质量美女", "url": "http://www.wudada.online/Api/NewSp", "color": "#E91E63"},
            {"name": "💪 完美身材", "url": "http://api.yujn.cn/api/wmsc.php?type=video", "color": "#FF9800"},
            {"name": "🎭 快手变装", "url": "http://api.yujn.cn/api/ksbianzhuang.php?type=video", "color": "#4CAF50"},
            {"name": "🎬 抖音变装", "url": "http://api.yujn.cn/api/bianzhuang.php?", "color": "#00BCD4"},
            {"name": "🤍 白丝系列", "url": "http://api.yujn.cn/api/baisis.php?type=video", "color": "#9E9E9E"},
            {"name": "👗 美女穿搭", "url": "http://api.yujn.cn/api/chuanda.php?type=video", "color": "#FF5722"},
            {"name": "🎲 随机小姐姐", "url": "http://api.yujn.cn/api/xjj.php?type=video", "color": "#673AB7"},
            {"name": "🖤 黑丝系列", "url": "http://api.yujn.cn/api/heisis.php?type=video", "color": "#3F51B5"},
            {"name": "🤍 黑白丝", "url": "http://api.tinise.cn/api/baisi", "color": "#607D8B"},
            {"name": "⚪ 黑白丝2", "url": "http://api.tinise.cn/api/heisi", "color": "#795548"},
            {"name": "🎓 快手女大学生", "url": "https://api.yujn.cn/api/nvda.php?type=video", "color": "#8BC34A"},
            {"name": "👁️ 抖音瞳瞳系列", "url": "https://api.yujn.cn/api/tongtong.php?type=video", "color": "#FF4081"},
            {"name": "💃 丝滑舞蹈", "url": "http://api.yujn.cn/api/shwd.php?type=video", "color": "#7C4DFF"},
            {"name": "🌟 鞠婧祎系列", "url": "http://api.yujn.cn/api/jjy.php?type=video", "color": "#FFD740"},
            {"name": "🏮 古风类", "url": "http://api.yujn.cn/api/hanfu.php?type=video", "color": "#E65100"},
            {"name": "🎧 慢摇系列", "url": "http://api.yujn.cn/api/manyao.php?type=video", "color": "#00897B"},
            {"name": "👙 吊带系列", "url": "http://api.yujn.cn/api/diaodai.php?type=video", "color": "#F06292"},
            {"name": "🌸 清纯系列", "url": "http://api.yujn.cn/api/qingchun.php?type=video", "color": "#EC407A"},
            {"name": "🎮 COS系列", "url": "http://api.yujn.cn/api/COS.php?type=video", "color": "#AB47BC"},
            {"name": "👧 纯情女高", "url": "http://api.yujn.cn/api/nvgao.php?type=video", "color": "#FFA726"},
            {"name": "📸 街拍系列", "url": "http://api.yujn.cn/api/jiepai.php?type=video", "color": "#26A69A"},
            {"name": "🎀 萝莉系列", "url": "http://api.yujn.cn/api/luoli.php?type=video", "color": "#EF5350"},
            {"name": "🍬 甜妹系列", "url": "http://api.yujn.cn/api/tianmei.php?type=video", "color": "#42A5F5"},
        ]
        
        for api in short_video_apis:
            if api['url'] == api_url:
                api_name = api['name']
                api_color = api.get('color', "#FF6B6B")
                break
        
        # 生成99个视频
        play_urls = []
        for i in range(1, 100):
            # 添加随机参数避免缓存
            rand_url = api_url
            if '?' in rand_url:
                rand_url = f"{rand_url}&_r={random.randint(1, 999999)}&_t={int(time.time())}"
            else:
                rand_url = f"{rand_url}?_r={random.randint(1, 999999)}&_t={int(time.time())}"
            
            play_urls.append(f"视频{i}${rand_url}")
        
        if not play_urls:
            self.log(f"没有生成视频")
            return {'list': []}
        
        # 使用API对应的颜色生成图标
        clean_name = re.sub(r'[^\w\u4e00-\u9fff]', '', api_name)
        first_char = clean_name[0] if clean_name else "视"
        icon = self._generate_colored_icon(api_color, first_char)
        
        vod = {
            'vod_id': f"short_video_{encoded_url}",
            'vod_name': f"📱 {api_name} ({len(play_urls)}个视频)",
            'vod_pic': icon,
            'vod_play_from': '短视频播放',
            'vod_play_url': '#'.join(play_urls),
            'vod_remarks': f'共{len(play_urls)}个视频，上下滑动切换',
            'style': {'type': 'list'},
            'vod_player': '短'
        }
        
        self.log(f"短视频源详情返回: {vod['vod_name']}")
        
        return {'list': [vod]}
    
    def _handle_short_video_play(self, video_url):
        """处理短视频播放"""
        self.log(f"短视频播放请求: {video_url[:100] if len(video_url) > 100 else video_url}")
        
        result = {
            "parse": 0,
            "playUrl": "",
            "url": video_url,
            "header": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.douyin.com/",
                "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8"
            },
            "vod_player": "短"
        }
        
        return result
    
    def _handle_add_custom_api(self):
        """处理添加自定义API（返回一个提示页面）"""
        return {'list': [{
            'vod_id': 'add_custom_api_result',
            'vod_name': '📝 添加自定义API说明',
            'vod_pic': self.file_icons['text'],
            'vod_content': '请在 /storage/emulated/0/custom_video_apis.json 文件中添加自定义API\n\n格式示例：\n[\n  {"name": "我的API", "url": "https://example.com/api", "type": "redirect"}\n]\n\n添加后重启即可生效。',
            'vod_remarks': '配置文件路径: /storage/emulated/0/custom_video_apis.json',
            'style': {'type': 'list'}
        }]}
    
    # ==================== 详情页 ====================
    
    def detailContent(self, ids):
        id_val = ids[0]
        self.log(f"详情页请求: {id_val}")
        
        # 处理短视频源详情 - 必须放在最前面
        if id_val.startswith("short_video_"):
            encoded_url = id_val[len("short_video_"):]
            return self._short_video_source_detail(encoded_url)
        
        # 处理添加自定义API
        if id_val == 'add_custom_api':
            return self._handle_add_custom_api()
        
        if id_val.startswith(self.LIVE_PREFIX):
            source_id = self.b64u_decode(id_val[len(self.LIVE_PREFIX):])
            return self._live_source_detail(source_id)
        
        if id_val.startswith(self.NOVEL_PREFIX):
            encoded = id_val[len(self.NOVEL_PREFIX):]
            file_path = self.b64u_decode(encoded)
            self.novel_path_cache[encoded] = file_path
            vod_data = self._handle_novel_detail(file_path, id_val, encoded)
            if vod_data and "list" in vod_data and len(vod_data["list"]) > 0:
                vod_data["list"][0]["vod_player"] = "书"
            return vod_data
        
        if id_val.startswith(self.TEXT_PREFIX):
            encoded = id_val[len(self.TEXT_PREFIX):]
            file_path = self.b64u_decode(encoded)
            vod_data = self._handle_text_detail(file_path, id_val)
            if vod_data and "list" in vod_data and len(vod_data["list"]) > 0:
                vod_data["list"][0]["vod_player"] = "书"
            return vod_data
        
        if id_val.startswith(self.FOLDER_PREFIX):
            folder_path = self.b64u_decode(id_val[len(self.FOLDER_PREFIX):])
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                return self.categoryContent(folder_path, 1, None, None)
            return {'list': []}
        
        if id_val.startswith(self.PICS_PREFIX + 'slideshow/'):
            dir_path = self.b64u_decode(id_val[len(self.PICS_PREFIX + 'slideshow/'):])
            images = self.collect_images_in_dir(dir_path)
            if not images:
                return {'list': []}
            
            pic_urls = [f"file://{img['path']}" for img in images]
            vod = {
                'vod_id': id_val,
                'vod_name': f"🖼 图片连播 - {os.path.basename(dir_path)} ({len(images)}张)",
                'vod_pic': self.file_icons['image_playlist'],
                'vod_play_from': '图片浏览',
                'vod_play_url': f"浏览${self.PICS_PREFIX + '&&'.join(pic_urls)}",
                'style': {'type': 'list'},
                'vod_player': '画'
            }
            return {'list': [vod]}
        
        if id_val.startswith(self.URL_B64U_PREFIX):
            decoded = self.b64u_decode(id_val[len(self.URL_B64U_PREFIX):])
            if decoded and decoded.startswith(self.PICS_PREFIX):
                return self._handle_pics_detail(decoded, id_val)
        
        if id_val.startswith(self.CAMERA_ALL_PREFIX):
            dir_path = self.b64u_decode(id_val[len(self.CAMERA_ALL_PREFIX):])
            images = self.collect_images_in_dir(dir_path)
            if not images:
                return {'list': []}
            
            pic_urls = [f"file://{img['path']}" for img in images]
            vod = {
                'vod_id': id_val,
                'vod_name': f"🖼 相机照片 ({len(images)}张)",
                'vod_pic': self.file_icons['image_playlist'],
                'vod_play_from': '照片查看',
                'vod_play_url': f"浏览${self.PICS_PREFIX + '&&'.join(pic_urls)}",
                'style': {'type': 'list'},
                'vod_player': '画'
            }
            return {'list': [vod]}
        
        if id_val.startswith(self.MAGNET_PREFIX):
            file_path = self.b64u_decode(id_val[len(self.MAGNET_PREFIX):])
            return self._handle_magnet_detail(file_path, id_val)
        
        if id_val.startswith(self.LIST_PREFIX):
            file_path = self.b64u_decode(id_val[len(self.LIST_PREFIX):])
            return self._handle_list_detail(file_path, id_val)
        
        if id_val.startswith(self.A_ALL_PREFIX):
            dir_path = self.b64u_decode(id_val[len(self.A_ALL_PREFIX):])
            return self._handle_audio_all_detail(dir_path, id_val)
        
        if id_val.startswith(self.V_ALL_PREFIX):
            dir_path = self.b64u_decode(id_val[len(self.V_ALL_PREFIX):])
            return self._handle_video_all_detail(dir_path, id_val)
        
        if not os.path.exists(id_val):
            return {'list': []}
        
        if os.path.isdir(id_val):
            return self.categoryContent(id_val, 1, None, None)
        
        return self._handle_file_detail(id_val)
    
    def _handle_pics_detail(self, decoded, id_val):
        pics_data = decoded[len(self.PICS_PREFIX):]
        
        if '&&' in pics_data:
            pic_urls = pics_data.split('&&')
            return {'list': [{
                'vod_id': id_val,
                'vod_name': f'图片相册 ({len(pic_urls)}张)',
                'vod_pic': pic_urls[0],
                'vod_play_from': '图片查看',
                'vod_play_url': f"浏览${self.PICS_PREFIX + '&&'.join(pic_urls)}",
                'style': {'type': 'list'},
                'vod_player': '画'
            }]}
        else:
            file_name = os.path.basename(pics_data.split('?')[0])
            if pics_data.startswith('file://'):
                file_name = os.path.basename(pics_data[7:])
            
            return {'list': [{
                'vod_id': id_val,
                'vod_name': file_name,
                'vod_pic': pics_data,
                'vod_play_from': '图片查看',
                'vod_play_url': f"查看${self.PICS_PREFIX + pics_data}",
                'style': {'type': 'list'},
                'vod_player': '画'
            }]}
    
    def _handle_magnet_detail(self, file_path, vod_id):
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return {'list': []}
        
        items = self._parse_magnet_file(file_path)
        
        if not items:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    magnet = re.search(r'(magnet:\?[^\s\'"<>]+)', content)
                    if magnet:
                        return {'list': [{
                            'vod_id': vod_id,
                            'vod_name': os.path.basename(file_path),
                            'vod_pic': self.file_icons['magnet'],
                            'vod_play_from': '磁力链接',
                            'vod_play_url': f"{os.path.splitext(os.path.basename(file_path))[0]}${magnet.group(1)}",
                            'style': {'type': 'list'}
                        }]}
            except:
                pass
            
            return {'list': [{
                'vod_id': vod_id,
                'vod_name': os.path.basename(file_path),
                'vod_pic': self.file_icons['magnet'],
                'vod_play_from': '磁力链接',
                'vod_play_url': f"打开文件$file://{file_path}",
                'style': {'type': 'list'}
            }]}
        
        play_urls = [f"{item['name']}${item['url']}" for item in items if item.get('url', '').startswith('magnet:')]
        
        return {'list': [{
            'vod_id': vod_id,
            'vod_name': os.path.basename(file_path),
            'vod_pic': self.file_icons['magnet'],
            'vod_play_from': '磁力链接列表',
            'vod_play_url': '#'.join(play_urls) if play_urls else f"打开文件$file://{file_path}",
            'style': {'type': 'list'}
        }]}
    
    def _parse_magnet_file(self, file_path):
        items = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            magnet_pattern = re.compile(r'(magnet:\?[^\s\'"<>]+)', re.I)
            lines = content.split('\n')
            
            for line in lines[:5000]:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if ',' in line:
                    parts = line.split(',', 1)
                    name = parts[0].strip()
                    magnet = magnet_pattern.search(parts[1])
                    if magnet:
                        items.append({'name': name, 'url': magnet.group(1)})
                else:
                    magnet = magnet_pattern.search(line)
                    if magnet:
                        name = f"磁力{len(items)+1}"
                        items.append({'name': name, 'url': magnet.group(1)})
        except:
            pass
        
        return items
    
    def _handle_list_detail(self, file_path, vod_id):
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return {'list': []}
        
        ext = self.get_file_ext(file_path)
        self.log(f"处理列表文件: {file_path}, 类型: {ext}")
        
        items = []
        
        if ext == 'json':
            items = self.parse_json_file(file_path)
            self.log(f"JSON解析到 {len(items)} 条记录")
        elif self.is_db_file(ext):
            items = self.parse_db_file(file_path)
            self.log(f"数据库解析到 {len(items)} 条记录")
        elif ext in ['m3u', 'm3u8']:
            items = self._parse_m3u_file(file_path)
            self.log(f"M3U解析到 {len(items)} 条记录")
            
            if len(items) > 5:
                return self._format_live_source(items, file_path, vod_id, ext)
        elif ext == 'txt':
            is_live_source = False
            url_count = 0
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(2048)
                    
                    if ',#genre#' in content.lower():
                        is_live_source = True
                    else:
                        lines = content.split('\n')
                        for line in lines[:30]:
                            line = line.strip()
                            if ',' in line:
                                parts = line.split(',', 1)
                                if len(parts) == 2:
                                    url = parts[1].strip()
                                    if self.is_playable_url(url):
                                        if any(ext in url.lower() for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                                            url_count += 1
                                        elif re.match(r'https?://[\d.]+:\d+', url):
                                            url_count += 1
                            elif self.is_playable_url(line):
                                if any(ext in line.lower() for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                                    url_count += 1
            except:
                pass
            
            if is_live_source or url_count >= 3:
                items = self._parse_txt_file(file_path)
                self.log(f"TXT直播源解析到 {len(items)} 条记录")
                return self._format_live_source(items, file_path, vod_id, ext)
            else:
                items = self._parse_txt_file(file_path)
                self.log(f"TXT小说解析到 {len(items)} 条记录")
        
        if not items:
            self.log(f"⚠️ 未解析到任何项目，使用默认播放")
            name = os.path.splitext(os.path.basename(file_path))[0]
            return {'list': [self._create_fallback_vod(file_path, 'list', vod_id, name)]}
        
        play_urls = self._build_play_urls(items)
        
        if not play_urls:
            return {'list': [self._create_fallback_vod(file_path, 'list', vod_id, os.path.splitext(os.path.basename(file_path))[0])]}
        
        pic = items[0].get('pic', '') if items else ''
        if not pic:
            pic = self.file_icons['list']
        
        play_url_str = '#'.join(play_urls)
        
        self.log(f"最终播放URL长度: {len(play_url_str)} 字符")
        
        return {'list': [{
            'vod_id': vod_id,
            'vod_name': os.path.basename(file_path),
            'vod_pic': pic,
            'vod_play_from': '播放列表',
            'vod_play_url': play_url_str,
            'vod_remarks': f'共{len(items)}条',
            'style': {'type': 'list'}
        }]}
    
    def _format_live_source(self, items, file_path, vod_id, ext):
        self.log(f"格式化直播源: {os.path.basename(file_path)}")
        
        channels = {}
        for item in items:
            name = item.get('name', '').strip()
            url = item.get('url', '')
            
            if not name or not url:
                continue
            
            clean_name = re.sub(r'^\[[^\]]+\]\s*', '', name)
            clean_name = re.sub(r'\s*[\[\(（]\s*\d+\s*[\]\)）]\s*$', '', clean_name)
            clean_name = re.sub(r'\s*[线|L|l]ine?\s*\d+$', '', clean_name, flags=re.I)
            clean_name = clean_name.strip()
            
            if clean_name not in channels:
                channels[clean_name] = []
            channels[clean_name].append(url)
        
        if not channels:
            play_urls = self._build_play_urls(items)
            pic = items[0].get('pic', '') if items else self.file_icons['list']
            return {'list': [{
                'vod_id': vod_id,
                'vod_name': os.path.basename(file_path),
                'vod_pic': pic,
                'vod_play_from': '播放列表',
                'vod_play_url': '#'.join(play_urls),
                'vod_remarks': f'共{len(items)}条',
                'style': {'type': 'list'}
            }]}
        
        max_lines = max(len(urls) for urls in channels.values())
        
        original_max_lines = max_lines
        if max_lines > 3:
            self.log(f"⚠️ 线路数 {max_lines} 超过3条，限制为3条")
            max_lines = 3
        
        from_list = []
        url_list = []
        
        for line_idx in range(max_lines):
            line_name = f"线路{line_idx + 1}"
            
            channel_urls = []
            for channel_name, urls in channels.items():
                if line_idx < len(urls):
                    channel_urls.append(f"{channel_name}${urls[line_idx]}")
            
            if channel_urls:
                from_list.append(line_name)
                url_list.append('#'.join(channel_urls))
                self.log(f"{line_name}: {len(channel_urls)}个频道")
        
        if not from_list:
            self.log("⚠️ 没有有效线路，使用原始数据")
            play_urls = self._build_play_urls(items)
            pic = items[0].get('pic', '') if items else self.file_icons['list']
            return {'list': [{
                'vod_id': vod_id,
                'vod_name': os.path.basename(file_path),
                'vod_pic': pic,
                'vod_play_from': '播放列表',
                'vod_play_url': '#'.join(play_urls),
                'vod_remarks': f'共{len(items)}条',
                'style': {'type': 'list'}
            }]}
        
        self.log(f"最终线路: {from_list}")
        
        colors = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#9D65C9", "#FF8C42", "#A2D729", "#FF6B8B", "#45B7D1", "#96CEB4"]
        color = colors[hash(os.path.basename(file_path)) % len(colors)]
        first_char = os.path.basename(file_path)[0].upper() if os.path.basename(file_path) else "L"
        icon_svg = self._generate_colored_icon(color, first_char)
        
        current_date = time.strftime('%Y.%m.%d', time.localtime())
        
        total_channels = len(channels)
        total_programs = sum(len(urls) for urls in channels.values())
        
        remarks = f'更新时间{current_date}'
        if original_max_lines > 3:
            remarks += f' (仅显示前3条线路)'
        
        vod = {
            'vod_id': vod_id,
            'vod_name': os.path.basename(file_path),
            'vod_pic': icon_svg,
            'vod_play_from': '$$$'.join(from_list),
            'vod_play_url': '$$$'.join(url_list),
            'vod_remarks': remarks,
            'vod_content': f'共 {total_channels} 个频道，{total_programs} 条节目线路',
            'style': {'type': 'list'},
            'type': 'live',
            'vod_type': 4,
            'vod_class': 'live',
            'vod_style': {'type': 'live'},
            'playerType': 2
        }
        
        return {'list': [vod]}
    
    def _parse_m3u_file(self, file_path):
        items = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            current_name = None
            for line in lines[:10000]:
                line = line.strip()
                if line.startswith('#EXTINF:'):
                    name_match = re.search(r',(.+)$', line) or re.search(r'tvg-name="([^"]+)"', line)
                    current_name = name_match.group(1).strip() if name_match else None
                elif line and not line.startswith('#'):
                    if self.is_playable_url(line):
                        items.append({
                            'name': current_name or f"线路{len(items)+1}",
                            'url': line
                        })
                    current_name = None
        except:
            pass
        return items
    
    def _parse_txt_file(self, file_path):
        items = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = []
            current_line = ""
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    if current_line:
                        lines.append(current_line)
                        current_line = ""
                    continue
                
                if line.startswith(('http://', 'https://')) and current_line and not current_line.startswith(('http://', 'https://')):
                    current_line = current_line + line
                elif current_line:
                    lines.append(current_line)
                    current_line = line
                else:
                    current_line = line
            
            if current_line:
                lines.append(current_line)
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if ',' in line:
                    parts = line.split(',', 1)
                    name = parts[0].strip()
                    url = parts[1].strip()
                    if self.is_playable_url(url):
                        if '$$$' in url:
                            url = url.split('$$$')[0]
                        items.append({'name': name, 'url': url})
                elif self.is_playable_url(line):
                    url = line
                    if '$$$' in url:
                        url = url.split('$$$')[0]
                    name = f"节目{len(items)+1}"
                    items.append({'name': name, 'url': url})
        except Exception as e:
            self.log(f"解析TXT文件失败: {e}")
        
        return items
    
    def _handle_novel_detail(self, file_path, vod_id, encoded):
        if not os.path.isfile(file_path):
            return {'list': []}
        
        cache_key = f"chapters_{encoded}"
        if cache_key in self.novel_chapters_cache:
            chapters = self.novel_chapters_cache[cache_key]
        else:
            chapters = NovelParser.parse_txt_novel(file_path)
            self.novel_chapters_cache[cache_key] = chapters
        
        self.current_novel = {'encoded_path': encoded, 'file_path': file_path, 'chapters': chapters}
        
        urls = []
        for i, c in enumerate(chapters):
            title = c['title']
            if title and len(title) > 2 and not title.strip().isdigit():
                urls.append(f"{title}$chapter{i}")
        
        return {'list': [{
            'vod_id': vod_id,
            'vod_name': os.path.basename(file_path),
            'vod_pic': self.file_icons['novel'],
            'vod_play_from': '小说章节',
            'vod_play_url': '#'.join(urls),
            'vod_remarks': f'共{len(chapters)}章',
            'style': {'type': 'list'}
        }]}
    
    def _handle_text_detail(self, file_path, vod_id):
        if not os.path.isfile(file_path):
            return {'list': []}
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return {'list': [{
                'vod_id': vod_id,
                'vod_name': os.path.basename(file_path),
                'vod_pic': self.file_icons['text'],
                'vod_play_from': '文本阅读',
                'vod_play_url': f"阅读${vod_id}",
                'vod_content': content[:5000],
                'vod_remarks': f'共{len(content)}字',
                'style': {'type': 'list'}
            }]}
        except Exception as e:
            self.log(f"读取文本失败: {e}")
            return {'list': []}
    
    def _create_fallback_vod(self, file_path, file_type, vod_id, name=None):
        return {
            'vod_id': vod_id,
            'vod_name': os.path.basename(file_path),
            'vod_pic': self.file_icons[file_type],
            'vod_play_from': file_type,
            'vod_play_url': f"{name or os.path.splitext(os.path.basename(file_path))[0]}$file://{file_path}",
            'style': {'type': 'list'}
        }
    
    def _build_play_urls(self, items):
        play_urls = []
        for item in items:
            url = item.get('url') or item.get('play_url', '')
            if url:
                name = item.get('name', '').strip()
                if not name:
                    name = f"节目{len(play_urls)+1}"
                
                name = re.sub(r'[#$]', '', name)
                
                if '$$$' in url:
                    first_url = url.split('$$$')[0]
                    if '$' in first_url:
                        url_parts = first_url.split('$', 1)
                        if len(url_parts) == 2:
                            play_urls.append(f"{name}${url_parts[1]}")
                        else:
                            play_urls.append(f"{name}${first_url}")
                    else:
                        play_urls.append(f"{name}${first_url}")
                else:
                    play_urls.append(f"{name}${url}")
        
        self.log(f"构建了 {len(play_urls)} 个播放URL")
        return play_urls
    
    def _handle_audio_all_detail(self, dir_path, vod_id):
        audios = self.collect_audios_in_dir(dir_path)
        
        if not audios:
            return {'list': []}
        
        audios.sort(key=lambda x: x['name'])
        
        play_urls = []
        for audio in audios:
            name = os.path.splitext(audio['name'])[0]
            if len(name) > 50:
                name = name[:47] + '...'
            play_urls.append(f"{name}${self.MP3_PREFIX + audio['path']}")
        
        return {'list': [{
            'vod_id': vod_id,
            'vod_name': f"🎵 {os.path.basename(dir_path)} ({len(audios)}首)",
            'vod_pic': self.file_icons.get('audio_playlist', self.file_icons.get('music_note')),
            'vod_play_from': '本地音乐',
            'vod_play_url': '#'.join(play_urls),
            'vod_remarks': f'共{len(audios)}首',
            'style': {'type': 'list'}
        }]}
    
    def _handle_video_all_detail(self, dir_path, vod_id):
        videos = self.collect_videos_in_dir(dir_path)
        
        if not videos:
            return {'list': []}
        
        play_urls = [f"{os.path.splitext(v['name'])[0]}$file://{v['path']}" for v in videos]
        
        return {'list': [{
            'vod_id': vod_id,
            'vod_name': f"🎬 视频播放列表 - {os.path.basename(dir_path)} ({len(videos)}集)",
            'vod_pic': self.file_icons['video_playlist'],
            'vod_play_from': '本地视频',
            'vod_play_url': '#'.join(play_urls),
            'vod_remarks': f'共{len(videos)}集',
            'style': {'type': 'list'}
        }]}
    
    def _handle_file_detail(self, file_path):
        name = os.path.basename(file_path)
        ext = self.get_file_ext(name)
        
        vod = {
            'vod_id': file_path,
            'vod_name': name,
            'vod_play_from': '本地播放',
            'vod_play_url': '',
            'style': {'type': 'list'}
        }
        
        if self.is_audio_file(ext):
            return self._handle_audio_file_detail(file_path, name, vod)
        
        if self.is_image_file(ext) or ext.lower() in ['heic', 'heif']:
            dir_path = os.path.dirname(file_path)
            all_images = self.collect_images_in_dir(dir_path)
            
            if len(all_images) > 1:
                clicked_index = -1
                for i, img in enumerate(all_images):
                    if img['path'] == file_path:
                        clicked_index = i
                        break
                
                reordered_images = []
                if clicked_index >= 0:
                    for i in range(clicked_index, len(all_images)):
                        reordered_images.append(all_images[i])
                    for i in range(0, clicked_index):
                        reordered_images.append(all_images[i])
                else:
                    reordered_images = all_images
                
                pic_urls = []
                for img in reordered_images:
                    pic_urls.append(f"file://{img['path']}")
                
                vod.update({
                    'vod_play_url': f"浏览${self.PICS_PREFIX + '&&'.join(pic_urls)}",
                    'vod_name': f"🖼 {name} (当前目录 {len(all_images)}张)",
                    'vod_pic': f"file://{file_path}",
                    'vod_play_from': '图片浏览',
                    'vod_remarks': f'共{len(all_images)}张照片，循环播放',
                    'vod_player': '画'
                })
            else:
                vod.update({
                    'vod_play_url': f"查看${self.PICS_PREFIX}file://{file_path}",
                    'vod_pic': f"file://{file_path}",
                    'vod_name': f"🖼️ {name}",
                    'vod_player': '画'
                })
        elif self.is_media_file(ext):
            dir_path = os.path.dirname(file_path)
            all_videos = self.collect_videos_in_dir(dir_path)
            
            if len(all_videos) > 1:
                clicked_index = -1
                for i, video in enumerate(all_videos):
                    if video['path'] == file_path:
                        clicked_index = i
                        break
                
                reordered_videos = []
                if clicked_index >= 0:
                    for i in range(clicked_index, len(all_videos)):
                        reordered_videos.append(all_videos[i])
                    for i in range(0, clicked_index):
                        reordered_videos.append(all_videos[i])
                else:
                    reordered_videos = all_videos
                
                play_urls = []
                for video in reordered_videos:
                    video_name = os.path.splitext(video['name'])[0]
                    play_urls.append(f"{video_name}$file://{video['path']}")
                
                vod.update({
                    'vod_play_url': '#'.join(play_urls),
                    'vod_name': f"🎬 {name} (当前目录 {len(all_videos)}集)",
                    'vod_pic': self.file_icons['video_playlist'],
                    'vod_play_from': '本地视频',
                    'vod_remarks': f'共{len(all_videos)}集，循环播放'
                })
            else:
                vod.update({
                    'vod_play_url': f"{os.path.splitext(name)[0]}$file://{file_path}",
                    'vod_name': f"🎬 {name}",
                    'vod_pic': self.file_icons['video']
                })
        elif self.is_list_file(ext) or self.is_db_file(ext) or self.is_magnet_file(ext):
            prefix = self.MAGNET_PREFIX if self.is_magnet_file(ext) else self.LIST_PREFIX
            return self.detailContent([prefix + self.b64u_encode(file_path)])
        elif ext == 'php' or ext == 'py':
            return self.detailContent([self.TEXT_PREFIX + self.b64u_encode(file_path)])
        elif ext == 'zip' or ext in ['rar', '7z', 'tar', 'gz', 'bz2', 'xz']:
            vod.update({
                'vod_play_url': f"{os.path.splitext(name)[0]}$file://{file_path}",
                'vod_name': f"🗜️ {name}",
                'vod_pic': self.file_icons['zip'] if ext == 'zip' else self.file_icons['archive'],
                'vod_remarks': f'{ext.upper()}压缩包'
            })
        elif ext == 'txt':
            preview = ''
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    preview = f.read(2048)
            except:
                pass
            
            is_live = False
            url_count = 0
            
            if preview:
                if ',#genre#' in preview.lower():
                    is_live = True
                else:
                    lines = preview.split('\n')
                    for line in lines[:20]:
                        line = line.strip()
                        if ',' in line:
                            parts = line.split(',', 1)
                            if len(parts) == 2:
                                url = parts[1].strip()
                                if url.startswith(('http://', 'https://')):
                                    if any(ext in url.lower() for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                                        url_count += 1
                                    elif re.match(r'https?://[\d.]+:\d+', url):
                                        url_count += 1
                        elif line.startswith(('http://', 'https://')):
                            if any(ext in line.lower() for ext in ['.m3u8', '.mp4', '.flv', '.ts']):
                                url_count += 1
                            elif re.match(r'https?://[\d.]+:\d+', line):
                                url_count += 1
                        
                        if url_count >= 3 or is_live:
                            break
            
            if is_live or url_count >= 3:
                return self.detailContent([self.LIST_PREFIX + self.b64u_encode(file_path)])
            else:
                vod_data = self.detailContent([self.NOVEL_PREFIX + self.b64u_encode(file_path)])
                if vod_data and "list" in vod_data and len(vod_data["list"]) > 0:
                    vod_data["list"][0]["vod_player"] = "书"
                return vod_data
        
        return {'list': [vod]}
    
    def _handle_audio_file_detail(self, file_path, name, vod):
        dir_path = os.path.dirname(file_path)
        all_audios = self.collect_audios_in_dir(dir_path)
        
        if len(all_audios) > 1:
            clicked_index = -1
            for i, audio in enumerate(all_audios):
                if audio['path'] == file_path:
                    clicked_index = i
                    break
            
            reordered_audios = []
            if clicked_index >= 0:
                reordered_audios.extend(all_audios[clicked_index:])
                reordered_audios.extend(all_audios[:clicked_index])
            else:
                reordered_audios = all_audios
            
            if len(reordered_audios) > 500:
                reordered_audios = reordered_audios[:500]
            
            play_urls = []
            for audio in reordered_audios:
                audio_name = os.path.splitext(audio['name'])[0]
                if len(audio_name) > 50:
                    audio_name = audio_name[:47] + '...'
                play_urls.append(f"{audio_name}${self.MP3_PREFIX + audio['path']}")
            
            vod.update({
                'vod_play_url': '#'.join(play_urls),
                'vod_name': f"🎵 {name} (共{len(all_audios)}首)",
                'vod_pic': self.file_icons.get('audio_playlist', self.file_icons.get('music_note')),
                'vod_play_from': '本地音乐',
                'vod_remarks': f'共{len(all_audios)}首'
            })
        else:
            vod.update({
                'vod_play_url': f"{os.path.splitext(name)[0]}${self.MP3_PREFIX + file_path}",
                'vod_name': f"🎵 {name}",
                'vod_pic': self.file_icons.get('music_note', self.file_icons.get('audio'))
            })
        
        return {'list': [vod]}
    
    def _live_source_detail(self, source_id):
        source = next((s for s in self.online_live_sources if s['id'] == source_id), None)
        if not source:
            return {'list': []}
        
        idx = self.online_live_sources.index(source)
        color = source.get('color', self.default_colors[idx % len(self.default_colors)])
        first_char = source['name'][0] if source['name'] else "直"
        icon = self._generate_colored_icon(color, first_char)
        
        programs = self._get_live_programs(source)
        if not programs:
            return {'list': [{
                'vod_id': self.LIVE_PREFIX + self.b64u_encode(source_id),
                'vod_name': source['name'],
                'vod_pic': icon,
                'vod_play_from': '直播源',
                'vod_play_url': '提示$无法获取直播源，请稍后重试',
                'vod_content': f"直播源: {source['url']}\n状态: 获取失败",
                'style': {'type': 'list'},
                'type': 'live',
                'vod_type': 4,
                'vod_class': 'live',
                'vod_style': {'type': 'live'},
                'playerType': source.get('playerType', 2)
            }]}
        
        channels = {}
        for p in programs:
            name = p['name']
            clean_name = re.sub(r'^\[[^\]]+\]\s*', '', name)
            clean_name = re.sub(r'\s*[\[\(（]\s*\d+\s*[\]\)）]\s*$', '', clean_name)
            
            if clean_name not in channels:
                channels[clean_name] = []
            channels[clean_name].append(p['url'])
        
        max_lines = max(len(urls) for urls in channels.values())
        
        original_max_lines = max_lines
        if max_lines > 3:
            self.log(f"⚠️ 线路数 {max_lines} 超过3条，限制为3条")
            max_lines = 3
        
        from_list = []
        url_list = []
        
        for line_idx in range(max_lines):
            line_name = f"线路{line_idx + 1}"
            
            channel_urls = []
            for channel_name, urls in channels.items():
                if line_idx < len(urls):
                    channel_urls.append(f"{channel_name}${urls[line_idx]}")
            
            if channel_urls:
                from_list.append(line_name)
                url_list.append('#'.join(channel_urls))
                self.log(f"{line_name}: {len(channel_urls)}个频道")
        
        if not from_list:
            return {'list': [{
                'vod_id': self.LIVE_PREFIX + self.b64u_encode(source_id),
                'vod_name': source['name'],
                'vod_pic': icon,
                'vod_play_from': '直播源',
                'vod_play_url': '提示$没有可用的线路',
                'vod_content': f"直播源: {source['url']}\n状态: 没有可用的线路",
                'style': {'type': 'list'},
                'type': 'live',
                'vod_type': 4,
                'vod_class': 'live',
                'vod_style': {'type': 'live'},
                'playerType': source.get('playerType', 2)
            }]}
        
        self.log(f"最终线路: {from_list}")
        
        current_date = time.strftime('%Y.%m.%d', time.localtime())
        
        total_channels = len(channels)
        total_programs = sum(len(urls) for urls in channels.values())
        
        remarks = f'更新时间{current_date}'
        if original_max_lines > 3:
            remarks += f' (仅显示前3条线路)'
        
        vod = {
            'vod_id': self.LIVE_PREFIX + self.b64u_encode(source_id),
            'vod_name': source['name'],
            'vod_pic': icon,
            'vod_play_from': '$$$'.join(from_list),
            'vod_play_url': '$$$'.join(url_list),
            'vod_remarks': remarks,
            'vod_content': f"共 {total_channels} 个频道，{total_programs} 条节目线路",
            'vod_style': {'type': 'live'},
            'vod_type': 4,
            'vod_class': 'live',
            'type': 'live',
            'style': {'type': 'live'},
            'playerType': source.get('playerType', 2)
        }
        
        return {'list': [vod]}
    
    # ==================== 播放页 ====================

    def playerContent(self, flag, id, vipFlags):
        self.log(f"播放请求: flag={flag}, id={id[:100] if len(id) > 100 else id}")
        
        # 短视频播放处理
        if flag == '短视频播放':
            result = self._handle_short_video_play(id)
            if 'vod_player' not in result:
                result['vod_player'] = '短'
            return result
        
        if id.startswith(self.PICS_PREFIX):
            return {
                "parse": 0, 
                "playUrl": "", 
                "url": id, 
                "header": {},
                "vod_player": "画"
            }
        
        if id.startswith(self.TEXT_PREFIX):
            encoded = id[len(self.TEXT_PREFIX):]
            file_path = self.b64u_decode(encoded)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                data = {"title": os.path.basename(file_path), "content": content}
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": self.TEXT_PREFIX + json.dumps(data, ensure_ascii=False),
                    "header": "",
                    "content": content,
                    "vod_player": "书"
                }
            except Exception as e:
                self.log(f"读取文本失败: {str(e)}")
                return {"parse": 0, "playUrl": "", "url": "", "header": ""}
        
        if id.startswith(self.MP3_PREFIX):
            return self._handle_mp3_play(id)
        
        if id.startswith(self.NOVEL_PREFIX):
            full_id = id[len(self.NOVEL_PREFIX):]
            
            chapter_index = 0
            encoded_path = full_id
            
            if '#chapter' in full_id:
                parts = full_id.split('#chapter', 1)
                encoded_path = parts[0]
                try:
                    chapter_index = int(parts[1])
                except (ValueError, IndexError):
                    chapter_index = 0
            
            if encoded_path in self.novel_path_cache:
                file_path = self.novel_path_cache[encoded_path]
            else:
                file_path = self.b64u_decode(encoded_path)
                self.novel_path_cache[encoded_path] = file_path
            
            try:
                cache_key = f"chapters_{encoded_path}"
                if cache_key in self.novel_chapters_cache:
                    chapters = self.novel_chapters_cache[cache_key]
                else:
                    chapters = NovelParser.parse_txt_novel(file_path)
                    self.novel_chapters_cache[cache_key] = chapters
                
                if chapters and 0 <= chapter_index < len(chapters):
                    title = chapters[chapter_index]['title']
                    content = chapters[chapter_index]['content']
                else:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    title = os.path.basename(file_path)
                
                data = {"title": title, "content": content}
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": "novel://" + json.dumps(data, ensure_ascii=False),
                    "header": "",
                    "content": content,
                    "vod_player": "书"
                }
            except Exception as e:
                self.log(f"读取小说失败: {str(e)}")
                return {"parse": 0, "playUrl": "", "url": "", "header": ""}
        
        if id.startswith('chapter') and flag == '小说章节' and self.current_novel['chapters']:
            try:
                idx = int(id.replace('chapter', ''))
                if 0 <= idx < len(self.current_novel['chapters']):
                    c = self.current_novel['chapters'][idx]
                    data = {"title": c['title'], "content": c['content']}
                    return {
                        "parse": 0, 
                        "playUrl": "", 
                        "url": "novel://" + json.dumps(data, ensure_ascii=False), 
                        "header": "",
                        "vod_player": "书"
                    }
            except:
                pass
        
        url = id
        if '$' in url:
            parts = url.split('$', 1)
            if len(parts) == 2:
                url = parts[1]
        
        if url.startswith(('http://', 'https://', 'file://')):
            pass
        else:
            try:
                decoded = base64.b64decode(url).decode('utf-8')
                if decoded.startswith(('http://', 'https://', 'file://')):
                    url = decoded
            except:
                pass
        
        if 'dytt-' in url and '/share/' in url and not url.endswith('.m3u8'):
            real_url = self._extract_real_m3u8_url(url)
            if real_url:
                url = real_url
        
        headers = self._build_headers(flag, url)
        
        result = {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": headers
        }
        
        if url.startswith('file://'):
            file_path = url[7:]
            if os.path.exists(file_path) and self.is_audio_file(self.get_file_ext(file_path)):
                self._add_audio_info_fast(result, file_path)
                self.log(f"[播放器] 已添加音频信息: 标题={result.get('title')}, 有歌词={bool(result.get('lrc'))}, 有封面={bool(result.get('poster'))}")
        
        if url.startswith('file://'):
            ext = self.get_file_ext(url[7:])
            if self.is_image_file(ext) or ext.lower() in ['heic', 'heif']:
                result["vod_player"] = "画"
        
        self.log(f"播放器返回: {result}")
        return result

    def _handle_mp3_play(self, id):
        """处理MP3播放 - 每次播放都重新获取歌词和封面"""
        file_path = id.replace(self.MP3_PREFIX, '')
        
        self.log(f"[MP3播放] 文件路径: {file_path}")
        
        if not os.path.exists(file_path):
            test_paths = [
                file_path,
                '/storage/emulated/0/' + file_path.lstrip('/'),
                file_path.replace('//', '/')
            ]
            for test_path in test_paths:
                if os.path.exists(test_path):
                    file_path = test_path
                    self.log(f"[MP3播放] 找到文件: {file_path}")
                    break
            else:
                self.log(f"[MP3播放] 音频文件不存在: {file_path}")
                return {"parse": 0, "playUrl": "", "url": "", "header": {}, "error": "文件不存在"}
        
        if not os.access(file_path, os.R_OK):
            self.log(f"[MP3播放] 音频文件不可读: {file_path}")
            return {"parse": 0, "playUrl": "", "url": "", "header": {}, "error": "文件无法读取"}
        
        play_url = f"http://127.0.0.1:9978/file{file_path}"
        
        result = {
            "parse": 0,
            "playUrl": "",
            "url": play_url,
            "header": {}
        }
        
        if self.is_audio_file(self.get_file_ext(file_path)):
            self._add_audio_info_fast(result, file_path)
            self.log(f"[MP3播放] 已添加音频信息: 标题={result.get('title')}, 歌手={result.get('artist')}, 有歌词={bool(result.get('lrc'))}, 有封面={bool(result.get('poster'))}")
        
        return result

    def _extract_real_m3u8_url(self, page_url):
        if page_url in self.m3u8_cache:
            return self.m3u8_cache[page_url]
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(page_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": base_url + "/",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
            
            response = self.session.get(page_url, headers=headers, timeout=10)
            if response.status_code != 200:
                return None
            
            html = response.text
            
            patterns = [
                r'(https?://[^\s"\']+\.m3u8[^\s"\']*)',
                r'(//[^\s"\']+\.m3u8[^\s"\']*)',
                r'url["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
                r'src["\']?\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    url = matches[0]
                    if url.startswith('//'):
                        url = 'https:' + url
                    elif url.startswith('/'):
                        url = base_url + url
                    self.m3u8_cache[page_url] = url
                    return url
            
            iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
            iframe_match = re.search(iframe_pattern, html, re.IGNORECASE)
            if iframe_match:
                iframe_url = iframe_match.group(1)
                if iframe_url.startswith('//'):
                    iframe_url = 'https:' + iframe_url
                elif iframe_url.startswith('/'):
                    iframe_url = base_url + iframe_url
                elif not iframe_url.startswith('http'):
                    iframe_url = base_url + '/' + iframe_url.lstrip('/')
                return self._extract_real_m3u8_url(iframe_url)
            
            return None
        except Exception as e:
            self.log(f"提取真实地址失败: {e}")
            return None

    def _build_headers(self, flag, url):
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*"
        }
        
        if flag == 'migu_live':
            headers.update({
                "User-Agent": "com.android.chrome/3.7.0 (Linux;Android 15)",
                "Referer": "https://www.miguvideo.com/"
            })
        elif flag == 'gongdian_live':
            headers.update({
                "Referer": "https://gongdian.top/"
            })
        
        if 't.061899.xyz' in domain:
            headers.update({
                "User-Agent": "okhttp/3.12.11",
                "Referer": "http://t.061899.xyz/"
            })
        elif 'rihou.cc' in domain:
            headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://rihou.cc:555/"
            })
        elif 'miguvideo.com' in domain:
            headers.update({
                "User-Agent": "com.android.chrome/3.7.0 (Linux;Android 15)",
                "Referer": "https://www.miguvideo.com/"
            })
        elif 'gongdian.top' in domain:
            headers.update({
                "Referer": "https://gongdian.top/"
            })
        elif 'dytt-film.com' in domain:
            headers.update({
                "Referer": "https://vip.dytt-film.com/",
                "Origin": "https://vip.dytt-film.com"
            })
        elif domain:
            headers["Referer"] = f"https://{domain}/"
        
        if "Range" in headers and '.m3u8' in url:
            del headers["Range"]
        
        return headers
    
    # ==================== 搜索 ====================
    
    def searchContent(self, key, quick, pg=1):
        pg = int(pg)
        results = []
        
        clean_key = re.sub(r'^[📁📂🎬🎵🖼📋📝🗄️🧲📄🖼️🎞️⬅️\s]+', '', key.lower())
        
        for path in self.root_paths:
            if not os.path.exists(path):
                continue
            
            all_files = []
            self._scan_for_search(path, all_files)
            
            for f in all_files:
                if clean_key in f['name'].lower():
                    item = self._create_search_item(f)
                    if item:
                        results.append(item)
        
        results.sort(key=lambda x: (clean_key not in x['vod_name'].lower(), x['vod_name']))
        
        per_page = 50
        start = (pg - 1) * per_page
        end = min(start + per_page, len(results))
        
        return {
            'list': results[start:end],
            'page': pg,
            'pagecount': (len(results) + per_page - 1) // per_page,
            'limit': per_page,
            'total': len(results)
        }
    
    def _scan_for_search(self, path, file_list, depth=0, max_depth=3):
        if depth > max_depth:
            return
        
        try:
            for name in os.listdir(path):
                if name.startswith('.'):
                    continue
                
                full_path = os.path.join(path, name)
                
                if os.path.isdir(full_path):
                    self._scan_for_search(full_path, file_list, depth + 1, max_depth)
                else:
                    file_list.append({
                        'name': name,
                        'path': full_path,
                        'ext': self.get_file_ext(name),
                    })
        except:
            pass
    
    def _create_search_item(self, f):
        if self.is_image_file(f['ext']) or f['ext'].lower() in ['heic', 'heif']:
            return {
                'vod_id': self.URL_B64U_PREFIX + self.b64u_encode(self.PICS_PREFIX + "file://" + f['path']),
                'vod_name': f"🖼 {f['name']}",
                'vod_pic': f"file://{f['path']}",
                'vod_play_url': f"查看${self.PICS_PREFIX}file://{f['path']}",
                'vod_remarks': '',
                'style': {'type': 'grid', 'ratio': 1},
                'vod_player': '画'
            }
        
        if self.is_audio_file(f['ext']):
            return {
                'vod_id': self.URL_B64U_PREFIX + self.b64u_encode(self.MP3_PREFIX + f['path']),
                'vod_name': f"🎵 {f['name']}",
                'vod_pic': self.file_icons['music_note'],
                'vod_play_url': f"播放${self.MP3_PREFIX + f['path']}",
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if self.is_media_file(f['ext']):
            return {
                'vod_id': f['path'],
                'vod_name': f"🎬 {f['name']}",
                'vod_pic': self.file_icons['video'],
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if self.is_lrc_file(f['ext']):
            return {
                'vod_id': f['path'],
                'vod_name': f"📝 {f['name']}",
                'vod_pic': self.file_icons['lyrics'],
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'json':
            return {
                'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"📋 {f['name']}",
                'vod_pic': self.file_icons['json'],
                'vod_play_url': f"查看${self.LIST_PREFIX + self.b64u_encode(f['path'])}",
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'php':
            return {
                'vod_id': self.TEXT_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🐘 {f['name']}",
                'vod_pic': self.file_icons['php'],
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'py':
            return {
                'vod_id': self.TEXT_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🐍 {f['name']}",
                'vod_pic': self.file_icons['python'],
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'zip':
            return {
                'vod_id': f['path'],
                'vod_name': f"🗜️ {f['name']}",
                'vod_pic': self.file_icons['zip'],
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if f['ext'] in ['rar', '7z', 'tar', 'gz', 'bz2', 'xz']:
            icon_key = 'rar' if f['ext'] == 'rar' else 'archive'
            return {
                'vod_id': f['path'],
                'vod_name': f"🗜️ {f['name']}",
                'vod_pic': self.file_icons[icon_key],
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if f['ext'] in ['m3u', 'm3u8']:
            colors = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#9D65C9", "#FF8C42", "#A2D729", "#FF6B8B", "#45B7D1", "#96CEB4"]
            color = colors[hash(f['name']) % len(colors)]
            first_char = f['name'][0].upper() if f['name'] else "M"
            icon_svg = self._generate_colored_icon(color, first_char)
            return {
                'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f['name'],
                'vod_pic': icon_svg,
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if self.is_db_file(f['ext']):
            return {
                'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🗄️ {f['name']}",
                'vod_pic': self.file_icons['database'],
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if self.is_magnet_file(f['ext']):
            return {
                'vod_id': self.MAGNET_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"🧲 {f['name']}",
                'vod_pic': self.file_icons['magnet'],
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        if f['ext'] == 'txt':
            is_live = False
            if any(k in f['name'].lower() for k in self.live_keywords):
                is_live = True
            
            if is_live:
                colors = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#9D65C9", "#FF8C42", "#A2D729", "#FF6B8B", "#45B7D1", "#96CEB4"]
                color = colors[hash(f['name']) % len(colors)]
                first_char = f['name'][0].upper() if f['name'] else "T"
                icon_svg = self._generate_colored_icon(color, first_char)
                return {
                    'vod_id': self.LIST_PREFIX + self.b64u_encode(f['path']),
                    'vod_name': f['name'],
                    'vod_pic': icon_svg,
                    'vod_remarks': '',
                    'style': {'type': 'list'}
                }
            else:
                encoded = self.b64u_encode(f['path'])
                novel_url = f"{self.NOVEL_PREFIX}{encoded}"
                return {
                    'vod_id': novel_url,
                    'vod_name': f"📖 {f['name']}",
                    'vod_pic': self.file_icons['novel'],
                    'vod_remarks': '',
                    'style': {'type': 'list'},
                    'vod_player': '书'
                }
        
        if f['ext'] in ['xml', 'html', 'htm', 'css', 'js', 'sh', 'bash']:
            return {
                'vod_id': self.TEXT_PREFIX + self.b64u_encode(f['path']),
                'vod_name': f"📄 {f['name']}",
                'vod_pic': self.file_icons['text'],
                'vod_remarks': '',
                'style': {'type': 'list'}
            }
        
        return {
            'vod_id': f['path'],
            'vod_name': f"📁 {f['name']}",
            'vod_pic': self.file_icons['file'],
            'vod_remarks': '',
            'style': {'type': 'list'}
        }
    
    # ==================== 缓存清理 ====================
    
    def clear_audio_cache(self):
        """清理音频缓存"""
        self.audio_list_cache.clear()
        self.audio_list_cache_time.clear()
        keys_to_delete = [k for k in self.lrc_cache if k.startswith('fast_lrc_')]
        for key in keys_to_delete:
            del self.lrc_cache[key]
        self.log(f"音频缓存已清理，清理了 {len(keys_to_delete)} 个歌词缓存")
    
    def clear_network_cache(self):
        """清理网络缓存"""
        self.network_lyrics_cache.clear()
        self.network_cover_cache.clear()
        self.song_info_cache.clear()
        self.log("网络缓存已清理")