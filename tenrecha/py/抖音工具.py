#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频在线解析下载器 v3.3 (纯API版)
======================
完全不需要浏览器/ChromeDriver，直接调用解析接口
适合移动端、服务器等环境

v3.3 修复：
- 图文作品背景音乐丢失（音乐直链藏在 video.play_addr.uri，补提取）
- 查看视频/音乐不能播放（前端播放统一走后端代理，带UA/Referer并跟随重定向）
- 解析按钮旁新增「清除」按钮
v3.2 主通道改为抖音分享页 SSR 直连（参考开源方案 douyin-direct-parser）：
- 短链跳转种 ttwid cookie → 同一会话访问分享页 → 解析 window._ROUTER_DATA
- videoInfoRes.item_list[0] → 视频 play_addr.uri 构造无水印地址 / 图集 images / 音乐
- 多通道依次：抖音SSR直连 → xtdowner(带csrf) → 第三方API → iesdouyin官方接口
"""

import os
import re
import json
import threading
import time
import requests
from flask import Flask, request, jsonify, Response
import urllib.parse
import hashlib
from html import unescape

# ============================================================
# 配置
# ============================================================
APP_TITLE = "视频在线解析下载器"
VERSION = "v3.3"
PORT = 5001
DATE = "2026-09-06"

# 手机UA（抖音分享页对手机UA返回完整数据）
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

# 解析接口 (通过 xtdowner 的后端 API)
PARSE_API_URL = "https://www.xtdowner.com/parse"
# 或者使用备选接口
PARSE_API_BACKUP = "https://api.xtdowner.com/v1/parse"

MEDIA_HOST_HINTS = (
    "douyinstatic.com", "douyinpic.com", "douyin.com",
    "iesdouyin.com", "byteimg.com", "bytecdn.com", "snssdk.com",
    "tiktokcdn.com", "kuaishou.com", "kwaicdn.com", "xhscdn.com",
    "xiaohongshu.com", "weibo.com", "sinaimg.cn", "biliapi.net",
    "bilivideo.com", "bilibili.com", "akamaized.net", "ppio.com",
    "ixigua.com", "ixiguavideo.com", "toutiao.com",
)
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
VID_EXT = (".mp4", ".m3u8", ".mov", ".webm")
AUD_EXT = (".mp3", ".m4a", ".aac", ".flac", ".wav")

_parse_lock = threading.Lock()

# ============================================================
# 工具函数
# ============================================================
def _extract_url(text):
    """从分享文本中提取链接，兼容 v.douyin.com 短链及口令"""
    if not text:
        return ""
    text = text.strip()
    if text.lower().startswith(("http://", "https://")):
        t = re.sub(r"[)，。、；：\]】\s]+$", "", text)
        return t
    # 匹配 http(s):// 开头到空白/中文标点/右括号为止
    m = re.search(r"https?://[^\s，。；、）\]】\"'<>]+", text)
    if m:
        u = m.group(0)
        # 去掉结尾可能的尾部标点（英文句号等）
        u = re.sub(r"[.,;:!?]+$", "", u)
        return u
    return ""

def _resolve_share_url(raw_input):
    """
    解分享链接：跟随重定向拿到最终URL，并提取真实 aweme_id
    返回 (final_url, aweme_id)
    """
    url = _extract_url(raw_input)
    if not url:
        return "", ""
    final_url = url
    try:
        resp = requests.get(
            url, allow_redirects=True, timeout=12,
            headers={"User-Agent": MOBILE_UA,
                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                     "Accept-Language": "zh-CN,zh;q=0.9"})
        if resp and resp.url:
            final_url = resp.url
    except Exception:
        pass
    # 从最终URL提取 aweme_id（多种格式）
    aweme_id = ""
    for pat in (r"/video/(\d+)", r"aweme_id=(\d+)", r"modal_id=(\d+)",
                r"/note/(\d+)", r"/share/video/(\d+)", r"item_ids=(\d+)"):
        m = re.search(pat, final_url)
        if m:
            aweme_id = m.group(1)
            break
    return final_url, aweme_id

def _normalize_media_url(url):
    if not url:
        return ""
    u = url.strip()
    u = u.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return u

def _media_type_from_url(url):
    u = url.lower()
    if "music" in u or "/ies-music/" in u or any(x in u for x in AUD_EXT):
        return "audio"
    if any(x in u for x in VID_EXT):
        return "video"
    if any(x in u for x in IMG_EXT) or "douyinpic" in u or "image" in u:
        return "image"
    return "other"

def _is_real_media(url):
    if not url:
        return False
    u = url
    if u.startswith("/") and not u.startswith("//"):
        return False
    if "xtdowner.com" in u:
        return False
    host = urllib.parse.urlparse(u).netloc.lower()
    if not host:
        return False
    return any(h in host for h in MEDIA_HOST_HINTS)

def _dedup(items):
    seen = set()
    out = []
    for it in items:
        u = it.get("url", "")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

def _sanitize_filename(name, max_len=60):
    if not name:
        return ""
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "", name)
    name = name.replace("xtdowner.com", "")
    for kw in ("更多在线视频解析工具推荐", "查看图片", "查看视频", "播放音乐", "下载图片",
               "下载视频", "下载音乐", "图集图片", "一键下载全部图片", "小天多媒体下载工具",
               "全部链接", "图集文案", "音乐标题", "音乐地址", "备用链接", "视频链接"):
        name = name.replace(kw, "")
    name = re.sub(r"\s{2,}", " ", name)
    name = re.sub(r"^\s*\d+\s+", "", name)
    name = name.strip(" #|-_·,，。. ")
    name = re.sub(r"\s*#\s*", " ", name).strip()
    return name[:max_len] if name else ""

def _extract_media_from_html(html):
    """从 HTML 中提取媒体链接"""
    raw_items = []
    seen_urls = set()
    
    def _add_item(url, name=""):
        url = _normalize_media_url(url)
        if not url or url in seen_urls or not _is_real_media(url):
            return
        seen_urls.add(url)
        raw_items.append({"url": url, "name": _sanitize_filename(name)})
    
    # 提取 onclick 中的链接
    for m in re.finditer(r"downLoadAjaxEvt\s*\(\s*this\s*,\s*'([^']+)'\s*(?:,\s*'([^']*)'\s*)?\)", html):
        _add_item(m.group(1), m.group(2) or "")
    
    # 提取 href 链接
    for m in re.finditer(r'href="(https?://[^"]+)"', html):
        u = m.group(1)
        if _is_real_media(u) and _media_type_from_url(u) != "other":
            _add_item(u, "")
    
    # 提取其他媒体链接
    for m in re.finditer(r'(https?://[^\s"\'<>]+(?:\.mp4|\.mp3|\.m4a|\.jpeg|\.jpg|\.png|\.webp|\.m3u8)[^\s"\'<>]*)', html):
        u = m.group(1)
        if _is_real_media(u):
            _add_item(u, "")
    
    # 提取标题和作者
    m_title = re.search(r'<h1[^>]*>(.*?)</h1>|<h2[^>]*>(.*?)</h2>|class="[^"]*(?:card-title|title|desc)[^"]*"[^>]*>(.*?)<', html, re.S)
    page_title = ""
    if m_title:
        page_title = re.sub(r"<[^>]+>", "", m_title.group(1) or m_title.group(2) or m_title.group(3) or "").strip()
    
    m_author = re.search(r'@([\w\u4e00-\u9fa5]+)', html)
    author = m_author.group(1) if m_author else ""
    
    # 分类
    music, images, videos = [], [], []
    for it in raw_items:
        typ = _media_type_from_url(it["url"])
        if typ == "audio":
            music.append(it)
        elif typ == "image":
            ul = it["url"].lower()
            if any(k in ul for k in ("sc=cover", "cover", "avatar", "music", "tplv-av", "head")):
                continue
            images.append(it)
        elif typ == "video":
            videos.append(it)
    
    music = _dedup(music)
    images = _dedup(images)
    videos = _dedup(videos)
    
    # 处理标题
    all_items = music + images + videos
    title = page_title or ""
    if (not title) or any(k in title for k in ("更多在线", "常见问题", "点击这里", "推荐", "Copyright", "本站")):
        for it in all_items:
            bt = _sanitize_filename(it.get("name", ""))
            if bt and len(bt) >= 2:
                title = bt
                break
    title = _sanitize_filename(title)
    if not title and author:
        title = "@" + author
    
    # 补充文件名扩展名
    for arr, ext in ((images, ".jpg"), (videos, ".mp4"), (music, ".mp3")):
        for it in arr:
            if not it.get("name"):
                it["name"] = (title or "作品") + ext
            if not re.search(r"\.[a-z0-9]{2,5}$", it["name"], re.I):
                it["name"] = it["name"] + ext
    
    total = len(music) + len(images) + len(videos)
    if total == 0:
        return None, "解析无结果"
    
    return {
        "type": "image" if images else ("video" if videos else "audio"),
        "title": title,
        "author": author,
        "music": music,
        "images": images,
        "videos": videos,
    }, "解析成功"


# ============================================================
# 纯 API 解析 (不需要浏览器)
# ============================================================
def _parse_via_xtdowner(raw_input):
    """xtdowner 表单解析（v3.1：必须带 csrf token 否则触发打赏墙）"""
    url = _extract_url(raw_input)
    if not url:
        return False, None, "未识别到有效链接"
    final_url, _aweme_id = _resolve_share_url(raw_input)
    submit_text = final_url if final_url else url

    headers = {
        "User-Agent": MOBILE_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.xtdowner.com",
        "Referer": "https://www.xtdowner.com/video/",
    }

    try:
        session = requests.Session()
        session.headers.update(headers)

        def _get_form_token():
            """访问首页获取 cookie 和 csrfmiddlewaretoken/dyid"""
            try:
                hr = session.get("https://www.xtdowner.com/video/", timeout=15)
                m = re.search(r'name="csrfmiddlewaretoken"[^>]*value="([^"]+)"', hr.text)
                csrf = m.group(1) if m else ""
                m2 = re.search(r'name="dyid"[^>]*value="([^"]*)"', hr.text)
                dyid = m2.group(1) if m2 else ""
                return csrf, dyid
            except Exception:
                return "", ""

        csrf_token, dyid_token = _get_form_token()

        parse_urls = [
            "https://www.xtdowner.com/video/",
            "https://www.xtdowner.com/parse",
            "https://api.xtdowner.com/v1/parse"
        ]

        for parse_url in parse_urls:
            for attempt in range(3):
                try:
                    data = {
                        "csrfmiddlewaretoken": csrf_token,
                        "dyid": dyid_token,
                        "detail": submit_text,
                        "submit": "解析"
                    }
                    resp = session.post(parse_url, data=data, timeout=30, allow_redirects=True)
                    if resp.status_code == 200:
                        html = resp.text
                        if "downLoadAjaxEvt" in html:
                            result, msg = _extract_media_from_html(html)
                            if result:
                                return True, result, msg
                        # 命中打赏墙/限流：刷新token并等待退避后重试
                        if "打赏" in html or "form_download" in html:
                            if attempt < 2:
                                wait_s = 20 * (attempt + 1)  # 20s / 40s
                                time.sleep(wait_s)
                                csrf_token, dyid_token = _get_form_token()
                                continue
                        elif "https://" in html:
                            result, msg = _extract_media_from_html(html)
                            if result:
                                return True, result, msg
                except Exception:
                    pass
                time.sleep(0.5)
        return False, None, "xtdowner 解析失败（可能今日免费次数用尽或触发频率限制）"
    except Exception as e:
        return False, None, f"xtdowner解析异常: {str(e)}"


def _find_key_recursive(obj, key):
    """递归在嵌套 dict/list 中查找包含指定 key 的对象"""
    if isinstance(obj, dict):
        if key in obj:
            return obj
        for v in obj.values():
            r = _find_key_recursive(v, key)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key_recursive(v, key)
            if r:
                return r
    return None


def _parse_via_douyin_ssr(raw_input):
    """
    抖音分享页 SSR 直连解析（v3.2 主通道，参考开源方案 douyin-direct-parser）
    原理：短链跟随跳转种下 ttwid cookie → 同一会话访问分享页
          → 解析 window._ROUTER_DATA 里的 videoInfoRes.item_list[0]
          → 视频用 play_addr.uri 构造无水印地址，图集取 images，音乐取 music
    """
    url = _extract_url(raw_input)
    if not url:
        return False, None, "未识别到有效链接"

    def _try_once():
        s = requests.Session()
        s.headers.update({
            "User-Agent": MOBILE_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.iesdouyin.com/",
        })
        # 1. 短链跟随跳转（种 ttwid cookie，提取作品ID与类型）
        try:
            r0 = s.get(url, allow_redirects=True, timeout=20)
        except Exception:
            return None, "短链跳转失败"
        final = r0.url
        m = re.search(r"/(?:video|note)/(\d{15,})", final)
        if not m:
            return None, "未能从跳转地址提取作品ID"
        aid = m.group(1)
        kind = "note" if "/note/" in final else "video"
        # 2. 用同一会话（带cookie）访问分享页
        try:
            r1 = s.get(f"https://www.iesdouyin.com/share/{kind}/{aid}/", timeout=20)
        except Exception:
            return None, "分享页请求失败"
        html = r1.text
        marker = "window._ROUTER_DATA = "
        start = html.find(marker)
        if start < 0:
            return None, "分享页缺少 _ROUTER_DATA(可能被风控，稍后重试)"
        start += len(marker)
        end = html.find("</script>", start)
        if end < 0:
            return None, "分享页数据不完整"
        raw = html[start:end].strip().rstrip(";")
        try:
            data = json.loads(unescape(raw))
        except Exception:
            try:
                data = json.loads(raw)
            except Exception:
                return None, "_ROUTER_DATA 解析失败"
        # 3. 递归查找 videoInfoRes
        page = _find_key_recursive(data, "videoInfoRes")
        if not page:
            return None, "分享页无视频数据(可能被风控，稍后重试)"
        items = (page.get("videoInfoRes") or {}).get("item_list") or []
        if not items:
            return None, "分享页无作品数据"
        item = items[0]
        if not isinstance(item, dict):
            return None, "作品数据格式异常"

        # 4. 构建结果
        desc = (item.get("desc") or "").strip()
        author = ((item.get("author") or {}).get("nickname") or "").strip()
        videos, images, music = [], [], []

        # ---- 视频（aweme_type=4 或 uri 为短ID格式 v0xxx）----
        video = item.get("video") or {}
        uri = ((video.get("play_addr") or {}).get("uri") or "").strip()
        if uri and "://" not in uri and not uri.startswith("http"):
            # 用 uri 构造无水印播放地址（aweme/v1/play 经典接口）
            for ratio in ("1080p", "720p", "540p"):
                pv = ("https://aweme.snssdk.com/aweme/v1/play/"
                      "?video_id=" + urllib.parse.quote(uri) +
                      "&ratio=" + ratio + "&line=0")
                videos.append({"url": pv, "name": "视频" + ratio + ".mp4"})
            # 带水印直链作为备用
            for u in ((video.get("play_addr") or {}).get("url_list") or []):
                u2 = _normalize_media_url(str(u))
                if u2 and "playwm" in u2:
                    videos.append({"url": u2, "name": "带水印备用.mp4"})
                    break

        # ---- 图集（aweme_type=2 图文作品）----
        for idx, img in enumerate(item.get("images") or []):
            ul = (img.get("url_list") or [])
            if not ul:
                continue
            images.append({"url": _normalize_media_url(str(ul[0])),
                           "name": "图" + str(idx + 1) + ".jpg"})

        # ---- 背景音乐 ----
        mus = item.get("music") or {}
        mus_title = (mus.get("title") or "背景音乐").strip()
        music_found = False
        for u in ((mus.get("play_url") or {}).get("url_list") or []):
            music.append({"url": _normalize_media_url(str(u)),
                          "name": mus_title + ".mp3"})
            music_found = True
            break
        if not music_found:
            # 图文作品的 video.play_addr.uri 可能直接是音乐 mp3 直链
            if uri and ("http://" in uri or "https://" in uri) and \
               (".mp3" in uri or "ies-music" in uri or "/music" in uri):
                music.append({"url": _normalize_media_url(uri),
                              "name": mus_title + ".mp3"})

        total = len(videos) + len(images) + len(music)
        if total == 0:
            return None, "作品数据中未找到媒体链接"

        title = desc or (("@" + author) if author else "作品")
        title = _sanitize_filename(title)
        if images and title:
            for i, it in enumerate(images):
                it["name"] = title + "_" + str(i + 1) + ".jpg"
        return {
            "type": "image" if images else ("video" if videos else "audio"),
            "title": title,
            "author": author,
            "music": music,
            "images": images,
            "videos": videos,
        }, ""

    last_msg = ""
    for i in range(3):
        res, msg = _try_once()
        if res:
            return True, res, "解析成功"
        last_msg = msg
        if i < 2:
            time.sleep(4 + i * 4)  # 4s / 8s 退避
    return False, None, last_msg or "抖音SSR解析失败"


def _parse_via_api(raw_input):
    """多通道解析（v3.2：抖音SSR直连为主，xtdowner/第三方/官方接口兜底）"""
    # 方法1（主通道）: 抖音分享页 SSR 直连
    ok, data, msg = _parse_via_douyin_ssr(raw_input)
    if ok:
        return True, data, msg

    # 方法2: xtdowner 表单（带csrf）
    ok2, data2, msg2 = _parse_via_xtdowner(raw_input)
    if ok2:
        return True, data2, msg2

    # 方法3: 第三方解析 API
    ok3, data3, msg3 = _parse_via_third_party_api(raw_input)
    if ok3:
        return True, data3, msg3

    # 方法4: 抖音官方 iesdouyin iteminfo 接口兜底
    _f, _a = _resolve_share_url(raw_input)
    if _a:
        ok4, data4, msg4 = _parse_via_iesdouyin(_a)
        if ok4:
            return True, data4, msg4
        return False, None, f"{msg}; {msg2}; {msg3}; {msg4}"
    return False, None, f"{msg}; {msg2}; {msg3}"


def _parse_via_third_party_api(raw_input):
    """使用第三方免费解析 API"""
    url = _extract_url(raw_input)
    if not url:
        return False, None, "未识别到有效链接"
    
    # 多个免费解析 API（v3.1：优先抖音官方老接口）
    apis = [
        {
            "url": "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/",
            "method": "GET",
            "params": {"item_ids": url.split("/")[-1]}
        },
        {
            "url": "https://api.anoyi.com/api/douyin",
            "method": "GET",
            "params": {"url": url}
        }
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    for api in apis:
        try:
            if api["method"] == "GET":
                resp = requests.get(api["url"], params=api["params"], headers=headers, timeout=15)
            else:
                resp = requests.post(api["url"], json=api["params"], headers=headers, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                # 尝试提取视频链接
                videos = []
                images = []
                music = []
                # item_list 格式（抖音官方老接口）
                if "item_list" in data and data["item_list"]:
                    item = data["item_list"][0]
                    desc = (item.get("desc") or "").strip()
                    author = ((item.get("author") or {}).get("nickname") or "").strip()
                    vd = item.get("video") or {}
                    pl = ((vd.get("play_addr") or {}).get("url_list")) or []
                    for u in pl:
                        u2 = u.replace("http://", "https://").replace("/playwm/", "/play/")
                        videos.append({"url": u2, "name": "视频.mp4"})
                        break
                    for idx, img in enumerate(item.get("images") or []):
                        ul = (img.get("url_list") or [])
                        if ul:
                            images.append({"url": ul[0].replace("http://", "https://"),
                                           "name": f"图{idx + 1}.jpg"})
                    mus = item.get("music") or {}
                    for u in ((mus.get("play_url") or {}).get("url_list") or []):
                        music.append({"url": u.replace("http://", "https://"),
                                      "name": ((mus.get("title") or "背景音乐").strip() + ".mp3")})
                        break
                    if videos or images or music:
                        title = _sanitize_filename(desc or ("@" + author if author else "作品"))
                        return True, {
                            "type": "image" if images else ("video" if videos else "audio"),
                            "title": title,
                            "author": author,
                            "music": music,
                            "images": images,
                            "videos": videos,
                        }, "解析成功"
                elif "video_data" in data:
                    video_url = data.get("video_data", {}).get("video_url", "")
                    if video_url:
                        videos.append({"url": video_url, "name": "video.mp4"})
                elif "data" in data and "video" in data["data"]:
                    video_url = data["data"].get("video", {}).get("url", "")
                    if video_url:
                        videos.append({"url": video_url, "name": "video.mp4"})
                elif "video_url" in data:
                    videos.append({"url": data["video_url"], "name": "video.mp4"})
                
                if videos:
                    return True, {
                        "type": "video",
                        "title": data.get("title", data.get("desc", "视频")),
                        "author": data.get("author", {}).get("nickname", ""),
                        "music": [],
                        "images": [],
                        "videos": videos
                    }, "解析成功"
        except:
            continue
    
    return False, None, "所有解析方式均失败，请检查链接或稍后重试"


def _parse_via_iesdouyin(aweme_id):
    """
    抖音官方 iesdouyin iteminfo 接口直连解析（v3.1新增）
    支持：视频、图集(图文)、背景音乐
    """
    if not aweme_id:
        return False, None, "未提取到视频ID"
    api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={aweme_id}"
    headers = {
        "User-Agent": MOBILE_UA,
        "Referer": f"https://www.iesdouyin.com/share/video/{aweme_id}/",
        "Accept": "application/json, text/plain, */*",
    }
    try:
        resp = requests.get(api_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return False, None, f"iesdouyin接口返回 {resp.status_code}"
        data = resp.json()
        item_list = data.get("item_list") or []
        if not item_list:
            return False, None, "iesdouyin接口无数据(可能已失效或需cookie)"
        item = item_list[0]
        desc = (item.get("desc") or "").strip()
        author = ((item.get("author") or {}).get("nickname") or "").strip()

        videos, images, music = [], [], []

        # ---- 视频 ----
        video = item.get("video") or {}
        play_list = ((video.get("play_addr") or {}).get("url_list")) or []
        if not play_list:
            play_list = ((video.get("play_addr_lowbr") or {}).get("url_list")) or []
        for u in play_list:
            u2 = u.replace("http://", "https://")
            u2 = u2.replace("/playwm/", "/play/")  # 无水印
            u2 = re.sub(r"&ratio=\d+", "", u2)
            videos.append({"url": u2, "name": "视频.mp4"})
            break  # 取第一个可用地址

        # ---- 图集(图文作品) ----
        for idx, img in enumerate(item.get("images") or []):
            ul = (img.get("url_list") or [])
            if not ul:
                continue
            u3 = ul[0].replace("http://", "https://")
            images.append({"url": u3, "name": f"图{idx + 1}.jpg"})

        # ---- 背景音乐 ----
        mus = item.get("music") or {}
        mus_list = ((mus.get("play_url") or {}).get("url_list")) or []
        for u in mus_list:
            music.append({"url": u.replace("http://", "https://"),
                          "name": ((mus.get("title") or "背景音乐").strip() + ".mp3")})
            break

        total = len(videos) + len(images) + len(music)
        if total == 0:
            return False, None, "接口返回中未找到媒体链接"

        title = desc or (("@" + author) if author else "作品")
        title = _sanitize_filename(title)
        # 图集图片名称带标题
        if images:
            for i, it in enumerate(images):
                if title:
                    it["name"] = f"{title}_{i + 1}.jpg"
        return True, {
            "type": "image" if images else ("video" if videos else "audio"),
            "title": title,
            "author": author,
            "music": music,
            "images": images,
            "videos": videos,
        }, "解析成功"
    except Exception as e:
        return False, None, f"iesdouyin解析异常: {str(e)}"


# ============================================================
# 解析入口
# ============================================================
def parse_media(raw_input):
    url = _extract_url(raw_input)
    if not url:
        return {"ok": False, "msg": "未识别到有效链接，请粘贴完整的视频分享链接或口令"}
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"ok": False, "msg": "链接格式不正确"}
    
    with _parse_lock:
        ok, data, msg = _parse_via_api(raw_input)
    
    if not ok:
        return {"ok": False, "msg": msg}
    return {"ok": True, "data": data, "msg": msg}


# ============================================================
# 下载代理
# ============================================================
def _proxy_download(url, as_download=True):
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    upstream = requests.get(
        url, stream=True, timeout=30,
        headers={"User-Agent": ua,
                 "Referer": "https://www.douyin.com/",
                 "Accept": "*/*"})
    ctype = upstream.headers.get("Content-Type", "application/octet-stream")
    length = upstream.headers.get("Content-Length", "")
    
    def generate():
        try:
            for chunk in upstream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            upstream.close()
    
    headers = {"Content-Type": ctype,
               "Content-Length": length,
               "Cache-Control": "no-cache"}
    if as_download:
        filename = _filename_from_url(url)
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(generate(), headers=headers, direct_passthrough=True)

def _filename_from_url(url):
    base = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))
    if not base or "." not in base:
        base = "download"
    base = re.sub(r"[\\/:*?\"<>|\r\n\t ]+", "_", base)
    return base[:80] or "download"


# ============================================================
# Flask 应用
# ============================================================
app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

TASK_STATE = {"running": False}

@app.route("/api/parse", methods=["POST"])
def api_parse():
    if TASK_STATE["running"]:
        return jsonify({"ok": False, "msg": "正在解析中, 请稍候..."})
    data = request.json or {}
    raw = (data.get("input") or "").strip()
    if not raw:
        return jsonify({"ok": False, "msg": "请粘贴视频链接或分享口令"})
    TASK_STATE["running"] = True
    try:
        result = parse_media(raw)
    finally:
        TASK_STATE["running"] = False
    return jsonify(result)

@app.route("/api/download")
def api_download():
    url = request.args.get("url", "")
    inline = request.args.get("inline", "") == "1"
    if not url or not _is_real_media(url):
        return jsonify({"ok": False, "msg": "无效的下载地址"}), 400
    return _proxy_download(url, as_download=not inline)

@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "version": VERSION, "running": TASK_STATE["running"]})


# ============================================================
# HTML 模板（与之前相同）
# ============================================================
HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>__APP_TITLE__</title>
<style>
:root{
  --bg:#f5f6f8; --card:#ffffff; --line:#e8eaee; --txt:#1f2329;
  --sub:#6b7280; --pri:#3370ff; --pri2:#2b5fd9;
  --ok:#2e9e5b; --ok2:#268b4e; --warn:#e8a13a; --err:#e0483e;
  --radius:12px;
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  background:var(--bg); color:var(--txt); min-height:100vh;
}
.topbar{background:linear-gradient(120deg,#1e6fff,#4a53e6);color:#fff;padding:22px 0 26px;box-shadow:0 2px 14px rgba(30,110,255,.18)}
.wrap{max-width:860px;margin:0 auto;padding:0 18px}
.topbar .logo{font-size:22px;font-weight:700;display:flex;align-items:center;gap:10px;letter-spacing:.5px}
.topbar .logo .dot{width:34px;height:34px;border-radius:9px;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;font-size:20px}
.topbar .sub{opacity:.85;font-size:13px;margin-top:6px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);box-shadow:0 2px 10px rgba(20,30,60,.05);padding:20px;margin-top:-20px}
.search{display:flex;gap:12px;flex-wrap:wrap}
.search input{
  flex:1;min-width:230px;height:48px;border:1.5px solid var(--line);border-radius:var(--radius);
  padding:0 16px;font-size:15px;outline:none;transition:.2s;background:#fbfcfe;
}
.search input:focus{border-color:var(--pri);background:#fff;box-shadow:0 0 0 3px rgba(51,112,255,.12)}
.search button{
  height:48px;padding:0 30px;border:none;border-radius:var(--radius);
  background:var(--pri);color:#fff;font-size:15px;font-weight:600;cursor:pointer;transition:.2s;white-space:nowrap;
}
.search button:hover{background:var(--pri2)}
.search button:disabled{opacity:.55;cursor:not-allowed}

.search button.parse-orange-btn {
    background: #ff7823;
}
.search button.parse-orange-btn:hover {
    background: #e66a1f;
}
.search button.parse-orange-btn:disabled {
    opacity:0.55;
    cursor:not-allowed;
    background:#ff7823;
}

.paste-btn{
  height:48px;padding:0 22px;border:1.5px solid var(--line);border-radius:var(--radius);
  background:#fff;color:var(--txt);font-size:15px;cursor:pointer;transition:.2s;white-space:nowrap;
}
.paste-btn:hover{border-color:var(--pri);color:var(--pri)}
.tips{margin-top:16px;font-size:13px;color:var(--sub);line-height:1.7}
.tips b{color:var(--txt)}
.status{margin-top:16px;font-size:14px;display:none;align-items:center;gap:10px}
.status.show{display:flex}
.spinner{width:18px;height:18px;border:3px solid #d6e0f5;border-top-color:var(--pri);border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.status.err{color:var(--err)}
.status.ok{color:var(--ok)}
.result{margin-top:24px;display:none}
.result.show{display:block}
.meta{background:#f7f9ff;border:1px solid #e4ebfb;border-radius:var(--radius);padding:14px 16px;margin-bottom:18px}
.meta .row{display:flex;align-items:flex-start;gap:8px}
.meta .t{font-size:15px;font-weight:600;line-height:1.5}
.meta .author{font-size:13px;color:var(--sub);margin-top:5px}
.grp{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);margin-bottom:16px;overflow:hidden}
.grp .g-title{display:flex;align-items:center;gap:8px;padding:13px 16px;border-bottom:1px solid var(--line);font-size:15px;font-weight:600;background:#fafbfd}
.grp .g-title .cnt{font-size:12px;font-weight:500;color:var(--sub);background:#eef1f6;padding:2px 9px;border-radius:20px}
.item{display:flex;align-items:center;gap:14px;padding:13px 16px;border-bottom:1px solid var(--line)}
.item:last-child{border-bottom:none}
.item .thumb{width:74px;height:74px;border-radius:10px;background:#f0f2f6;object-fit:cover;flex-shrink:0;cursor:pointer;border:1px solid var(--line)}
.item .thumb.video{background:#eef1f6 center/46px no-repeat url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='46' height='46' viewBox='0 0 24 24' fill='%23b4bccb'><path d='M8 5v14l11-7z'/></svg>")}
.item .thumb.audio{background:#eef1f6 center/44px no-repeat url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='44' height='44' viewBox='0 0 24 24' fill='%23b4bccb'><path d='M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z'/></svg>")}
.item .info{flex:1;min-width:0}
.item .name{font-size:14px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item .ext{font-size:12px;color:var(--sub);margin-top:4px}
.item .ops{display:flex;gap:8px;flex-shrink:0}
.btn{height:34px;padding:0 14px;border-radius:8px;border:none;font-size:13px;font-weight:600;cursor:pointer;transition:.2s;white-space:nowrap;box-shadow:0 1px 3px rgba(20,30,60,.08)}
.btn.gray{background:#fff;border:1px solid var(--line);color:var(--txt)}
.btn.gray:hover{border-color:var(--pri);color:var(--pri)}
.btn.blue{background:var(--pri);color:#fff}
.btn.blue:hover{background:var(--pri2)}
.btn.green{background:var(--ok);color:#fff}
.btn.green:hover{background:var(--ok2)}
.btn:disabled{opacity:.6;cursor:not-allowed}
.btn.sm{padding:0 12px}
.modal{position:fixed;inset:0;background:rgba(10,16,28,.72);display:none;align-items:center;justify-content:center;z-index:100;padding:20px}
.modal.show{display:flex}
.modal .box{background:#0d1220;border-radius:14px;max-width:92vw;max-height:90vh;overflow:auto;position:relative;box-shadow:0 10px 40px rgba(0,0,0,.5)}
.modal .close{position:absolute;top:10px;right:12px;width:34px;height:34px;border:none;border-radius:50%;background:rgba(255,255,255,.14);color:#fff;font-size:20px;cursor:pointer;z-index:2}
.modal video,.modal audio,.modal img{display:block;max-width:88vw;max-height:82vh}
.foot{text-align:center;color:var(--sub);font-size:12px;padding:26px 0 30px;line-height:1.8}
.foot a{color:var(--pri);text-decoration:none}
@media(max-width:560px){
  .item{flex-wrap:wrap}
  .item .ops{width:100%;justify-content:flex-start}
  .search button{flex:1;text-align:center}
}
</style>
</head>
<body>
<div class="topbar">
  <div class="wrap">
    <div class="logo"><span class="dot">▶</span>__APP_TITLE__</div>
    <div class="sub">粘贴视频分享链接 / 口令 → 一键解析无水印视频、图集、音乐 · 免费在线下载</div>
  </div>
</div>

<div class="wrap">
  <div class="card">
    <div class="search">
      <input id="input" placeholder="粘贴抖音/短视频 分享链接或口令, 如: https://v.douyin.com/xxxx/" autocomplete="off">
      <button id="btnPaste" class="paste-btn" title="读取剪贴板">粘贴</button>
      <button id="btnClear">清 除</button>
     <button id="btnParse" class="parse-orange-btn">解 析</button>

      
    </div>
    <div class="tips">
      <b>支持：</b>抖音 / 抖音极速版分享口令、短视频链接、图集(图文)作品、背景音乐。<br>
      <b>示例：</b>粘贴 <code style="color:var(--pri)">8.25 y@t.re GiC:/ 复制打开抖音, 看看【xxx的图文作品】 https://v.douyin.com/xxxx/</code> 整段即可, 自动提取链接。
    </div>
    <div id="status" class="status"><div class="spinner"></div><span id="statusText">正在解析, 请稍候...</span></div>
    <div id="result" class="result"></div>
  </div>

  <div class="foot">
    本工具解析结果均来自公开平台, 仅供个人学习研究使用, 请勿用于商业用途或侵犯原作者权益。<br>
    视频归平台和原作者所有, 本站不存储任何视频/图片/音乐。
  </div>
</div>

<!-- 预览弹窗 -->
<div class="modal" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="box" id="modalBox"><button class="close" onclick="closeModal()">×</button><div id="modalContent"></div></div>
</div>

<script>
const $ = s => document.querySelector(s);
let media = null;

$("#btnPaste").onclick = async () => {
  try {
    const t = await navigator.clipboard.readText();
    if (t && t.trim().length > 3) { $("#input").value = t.trim(); $("#input").focus(); }
    else setStatus("err", "剪贴板为空, 请先复制视频链接");
  } catch (e) {
    setStatus("err", "无法读取剪贴板, 请手动粘贴(部分浏览器需授权)");
  }
};

$("#btnParse").onclick = doParse;
$("#btnClear").onclick = () => {
  $("#input").value = "";
  $("#result").classList.remove("show");
  $("#result").innerHTML = "";
  media = null;
  setStatus("", "");
  $("#input").focus();
};
$("#input").addEventListener("keydown", e => { if (e.key === "Enter") doParse(); });
$("#input").addEventListener("input", () => { $("#result").classList.remove("show"); });

async function doParse() {
  const input = $("#input").value.trim();
  if (!input) { setStatus("err", "请先粘贴视频链接或分享口令"); return; }
  const btn = $("#btnParse");
  btn.disabled = true; btn.textContent = "解析中...";
  $("#result").classList.remove("show");
  setStatus("loading", "正在解析, 请稍候...");
  try {
    const r = await fetch("/api/parse", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({input})
    });
    const j = await r.json();
    if (!j.ok) { setStatus("err", j.msg || "解析失败"); return; }
    setStatus("ok", "解析成功, 可在线查看或下载");
    renderResult(j.data);
  } catch (e) {
    setStatus("err", "请求失败: " + e.message);
  } finally {
    btn.disabled = false; btn.textContent = "解 析";
  }
}

function setStatus(type, msg) {
  const st = $("#status");
  if (!type) { st.className = "status"; $("#statusText").textContent = ""; return; }
  st.className = "status show " + (type === "err" ? "err" : (type === "ok" ? "ok" : ""));
  $("#statusText").textContent = msg;
  if (type !== "loading") { $(".spinner", st); st.querySelector(".spinner") && st.querySelector(".spinner").remove(); }
}

function esc(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function renderResult(d) {
  media = d;
  const r = $("#result");
  let html = "";
  if (d.title || d.author) {
    html += `<div class="meta"><div class="row"><div class="t">${esc(d.title || "媒体作品")}</div></div>`;
    if (d.author) html += `<div class="author">作者：${esc(d.author)}</div>`;
    html += `</div>`;
  }
  if (d.images && d.images.length) {
    html += `<div class="grp"><div class="g-title">🖼️ 图集图片 <span class="cnt">${d.images.length} 张</span></div>`;
    d.images.forEach((it, i) => {
      html += itemHtml("image", it, i, "查看图片", "下载图片");
    });
    html += `<div class="item" style="justify-content:flex-end">
      <button class="btn green" onclick="downAll()">一键下载全部图片</button></div></div>`;
  }
  if (d.videos && d.videos.length) {
    html += `<div class="grp"><div class="g-title">🎬 视频 <span class="cnt">${d.videos.length} 个</span></div>`;
    d.videos.forEach((it, i) => { html += itemHtml("video", it, i, "查看视频", "下载视频"); });
    html += `</div>`;
  }
  if (d.music && d.music.length) {
    html += `<div class="grp"><div class="g-title">🎵 背景音乐 <span class="cnt">${d.music.length} 首</span></div>`;
    d.music.forEach((it, i) => { html += itemHtml("audio", it, i, "播放音乐", "下载音乐"); });
    html += `</div>`;
  }
  r.innerHTML = html;
  r.classList.add("show");
}

function itemHtml(type, it, idx, viewLabel, dlLabel) {
  const cls = type === "video" ? "video" : (type === "audio" ? "audio" : "");
  const viewFn = type === "image" ? `viewMedia('${idx}','image')` : (type === "video" ? `viewMedia('${idx}','video')` : `viewMedia('${idx}','audio')`);
  const copyFn = `copyUrl("${esc(it.url)}")`;
  const thumbImg = type === "image" ? `<img class="thumb" src="/api/download?url=${encodeURIComponent(it.url)}" onclick="${viewFn}" onerror="this.style.display='none'">` : `<div class="thumb ${cls}" onclick="${viewFn}"></div>`;
  return `<div class="item">
    ${thumbImg}
    <div class="info">
      <div class="name">${esc(it.name || "媒体" + (idx + 1))}</div>
      <div class="ext">${esc(extOf(it.url))}</div>
    </div>
    <div class="ops">
      <button class="btn gray" onclick="${copyFn}">点击复制</button>
      <button class="btn blue" onclick="${viewFn}">${viewLabel}</button>
      <button class="btn green" onclick="dl('${idx}','${type}')">${dlLabel}</button>
    </div>
  </div>`;
}

function extOf(url) {
  try { const m = url.split("?")[0].match(/\.([a-z0-9]{2,5})$/i); return m ? m[1].toUpperCase() : "直链"; }
  catch (e) { return "直链"; }
}

function dl(idx, type) {
  const arr = media[typeKey(type)];
  const it = arr[idx];
  const a = document.createElement("a");
  a.href = "/api/download?url=" + encodeURIComponent(it.url);
  a.download = it.name || "download";
  document.body.appendChild(a); a.click(); a.remove();
}

function downAll() {
  if (!media || !media.images) return;
  let auto = 0;
  const imgs = media.images;
  const timer = setInterval(() => {
    if (auto >= imgs.length) { alert("全部图片下载完毕"); clearInterval(timer); return; }
    dl(auto, "image"); auto++;
  }, 900);
}

async function copyUrl(url) {
  try { await navigator.clipboard.writeText(decodeURIComponent(url)); toast("已复制地址"); }
  catch (e) { toast("复制失败"); }
}

function viewMedia(idx, type) {
  const arr = media[typeKey(type)];
  const it = arr[idx];
  openModal(it.url, type);
}

function typeKey(type) {
  if (type === "image") return "images";
  if (type === "video") return "videos";
  if (type === "audio") return "music";
  return type;
}

function openModal(url, type) {
  const box = $("#modalBox");
  // 播放统一走后端代理（自动带UA/Referer并跟随重定向），否则抖音CDN会拒绝播放
  const proxy = "/api/download?inline=1&url=" + encodeURIComponent(url);
  let inner = "";
  if (type === "image") inner = `<img src="${esc(proxy)}">`;
  else if (type === "video") inner = `<video src="${esc(proxy)}" controls autoplay playsinline></video>`;
  else inner = `<audio src="${esc(proxy)}" controls autoplay></audio>`;
  $("#modalContent").innerHTML = inner;
  $("#modal").classList.add("show");
}
function closeModal() {
  const c = $("#modalContent");
  c.innerHTML = ""; $("#modal").classList.remove("show");
}
function toast(t) {
  let el = $("#toast");
  if (!el) { el = document.createElement("div"); el.id = "toast";
    el.style.cssText = "position:fixed;bottom:40px;left:50%;transform:translateX(-50%);background:rgba(20,26,40,.92);color:#fff;padding:10px 20px;border-radius:8px;font-size:14px;z-index:200;transition:.3s;opacity:0";
    document.body.appendChild(el); }
  el.textContent = t; el.style.opacity = "1";
  setTimeout(() => { el.style.opacity = "0"; }, 1600);
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    html = HTML.replace("__APP_TITLE__", APP_TITLE)
    return html


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    print("=" * 52)
    print(f"  {APP_TITLE} {VERSION}")
    print(f"  访问地址: http://127.0.0.1:{PORT}")
    print("  支持: 抖音/抖音极速版 视频·图集·背景音乐 解析 + 在线预览下载")
    print(f"  日期: {DATE}")
    print("=" * 52)
    print("  ✅ 纯API模式，无需浏览器/ChromeDriver")
    print("  📱 支持移动端访问 (Via浏览器等)")
    print("=" * 52)
    
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)