# -*- coding: utf-8 -*-
#!/usr/bin/python
# 清纯富婆 – WordPress视频主题TVBox爬虫适配 (集成广告拦截清洗)
import sys, re, json, base64, html, os, threading, time, hashlib
from urllib.parse import quote, unquote, urljoin, urlparse
try:
    from lxml import etree
except ImportError:
    etree = None
try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    requests = None
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def playerContent(self, flag, id, vipFlags): pass
        def searchContent(self, key, quick, pg="1"): pass
        def localProxy(self, param): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass

def fix_url(url, host):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(host, url)
    if url.startswith("http"):
        return url
    return urljoin(host, "/" + url)

def clean_text(text):
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://xn--6-tf2b.qingfupo02.xyz"
        self.name = "qingfupo"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Upgrade-Insecure-Requests": "1"
        }
        self.session = requests.Session() if requests else None
        self.seen_ids = set()
        if self.session:
            self.session.headers.update(self.headers)
            self.session.verify = False

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = self.host + "/"
            if self.session:
                self.session.headers.update({"Referer": self.host + "/"})

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def _fetch(self, url):
        if not self.session:
            return ""
        try:
            r = self.session.get(url, timeout=15, headers=self.headers)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            print(f"[{self.name}] 请求失败: {url} - {e}")
            return ""

    def homeContent(self, filter):
        try:
            classes = [
                {"type_name": "亚洲情色", "type_id": "ya-zhou-qing-se"},
                {"type_name": "巨乳美乳", "type_id": "ju-ru-mei-ru"},
                {"type_name": "福利姬", "type_id": "fu-li-ji"},
                {"type_name": "强奸乱伦", "type_id": "qiang-jian-luan-lun"},
                {"type_name": "国产主播", "type_id": "guo-chan-zhu-bo"},
                {"type_name": "少女萝莉", "type_id": "shao-nv-luo-li"},
                {"type_name": "国产自拍", "type_id": "guo-chan-zi-pai"},
                {"type_name": "重口色情", "type_id": "zhong-kou-se-qing"},
                {"type_name": "中文字幕", "type_id": "zhong-wen-zi-mu"},
                {"type_name": "无码专区", "type_id": "wu-ma-zhuan-qu"},
                {"type_name": "制服诱惑", "type_id": "zhi-fu-you-huo"},
                {"type_name": "卡通动画", "type_id": "ka-tong-dong-hua"},
                {"type_name": "欧美性爱", "type_id": "ou-mei-xing-ai"},
                {"type_name": "女同性恋", "type_id": "nv-tong-xing-lian"},
                {"type_name": "熟女人妻", "type_id": "shu-nv-ren-qi"},
            ]
            filters = {
                "ya-zhou-qing-se": [
                    {"key": "by", "name": "排序", "value": [{"n":"最新","v":"time"},{"n":"热门","v":"hits"},{"n":"评分","v":"score"}]}
                ]
            }
            return {"class": classes, "filters": filters}
        except Exception as e:
            print(f"[{self.name}] 首页失败: {e}")
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            if tid:
                url = f"{self.host}/vtype/{tid}/page/{pg}/" if int(pg) > 1 else f"{self.host}/vtype/{tid}/"
            else:
                url = f"{self.host}/page/{pg}/" if int(pg) > 1 else self.host + "/"

            html_text = self._fetch(url)
            if not html_text:
                return result
            doc = etree.HTML(html_text) if etree else None
            if not doc:
                return result

            items = doc.xpath('//div[contains(@class,"post-item")]')
            print(f"[{self.name}] 分类列表匹配到 {len(items)} 个视频")
            self.seen_ids.clear()

            for item in items:
                try:
                    a_nodes = item.xpath('.//a[contains(@class,"post-link")]')
                    if not a_nodes:
                        continue
                    a = a_nodes[0]
                    href = a.xpath('./@href')[0] if a.xpath('./@href') else ""
                    vid_match = re.search(r'/v/video-(\d+)/', href)
                    if not vid_match:
                        continue
                    vid = vid_match.group(1)
                    if vid in self.seen_ids:
                        continue
                    self.seen_ids.add(vid)

                    title = ""
                    title_nodes = a.xpath('.//div[contains(@class,"post-title-container")]//span/text()')
                    if title_nodes:
                        title = clean_text(title_nodes[0])
                    if not title:
                        alt_nodes = a.xpath('.//div[contains(@class,"post-image")]//img/@alt')
                        if alt_nodes:
                            title = clean_text(alt_nodes[0])

                    pic = ""
                    pic_nodes = a.xpath('.//div[contains(@class,"post-image")]//img/@src')
                    if pic_nodes:
                        pic = fix_url(pic_nodes[0], self.host)
                    if not pic:
                        pic_nodes = a.xpath('.//div[contains(@class,"post-image")]//img/@data-src')
                        if pic_nodes:
                            pic = fix_url(pic_nodes[0], self.host)

                    remark = ""
                    result["list"].append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remark
                    })
                except Exception as e:
                    print(f"[{self.name}] 单条解析失败: {e}")
                    continue

            pagecount = 1
            last_href = doc.xpath('//div[contains(@class,"page-nav")]//a[contains(text(),"尾页")]/@href')
            if last_href:
                m = re.search(r'/page/(\d+)/', last_href[0])
                if m:
                    pagecount = int(m.group(1))
            else:
                pages = doc.xpath('//div[contains(@class,"page-nav")]//a[contains(@class,"page-numbers")]/text()')
                for p in pages:
                    try:
                        n = int(p.strip().replace(',', ''))
                        if n > pagecount:
                            pagecount = n
                    except:
                        pass
                next_href = doc.xpath('//div[contains(@class,"page-nav")]//a[contains(@class,"next")]/@href')
                if next_href and pagecount <= int(pg):
                    m = re.search(r'/page/(\d+)/', next_href[0])
                    if m:
                        pagecount = max(pagecount, int(m.group(1)))

            result["pagecount"] = pagecount
            return result
        except Exception as e:
            print(f"[{self.name}] 分类爬取失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids
            result = {"list": []}
            url = f"{self.host}/v/video-{vid}/"
            html_text = self._fetch(url)
            if not html_text:
                return result

            doc = etree.HTML(html_text) if etree else None
            title = ""
            pic = ""
            content = ""

            if doc:
                title_nodes = doc.xpath('//h1[contains(@class,"title") or contains(@class,"entry-title")]/text()') or doc.xpath('//h1/text()') or doc.xpath('//h2/text()')
                title = clean_text(title_nodes[0]) if title_nodes else ""

                pic_nodes = doc.xpath('//div[contains(@class,"post-image") or contains(@class,"video-poster")]//img/@src') or doc.xpath('//img[contains(@class,"cover") or contains(@class,"poster")]/@src') or doc.xpath('//img[contains(@class,"cover") or contains(@class,"poster")]/@data-original')
                pic = fix_url(pic_nodes[0], self.host) if pic_nodes else ""

                content_nodes = doc.xpath('//div[contains(@class,"entry-content") or contains(@class,"content") or contains(@class,"summary")]//text()')
                if content_nodes:
                    content = clean_text("".join(content_nodes))

            if not title:
                title = vid

            sources = []
            play_urls = []

            if doc:
                video_src = doc.xpath('//video/source/@src') or doc.xpath('//video/@src')
                if video_src:
                    vurl = fix_url(video_src[0], self.host)
                    if '.m3u8' in vurl.lower():
                        vurl = self.源天纹(vurl, self.host)
                    sources.append("默认线路")
                    play_urls.append(f"正片${vurl}")

                if not sources:
                    iframe = doc.xpath('//iframe[contains(@class,"player") or contains(@id,"dplayer") or @id="player"]/@src')
                    if iframe:
                        src = fix_url(iframe[0], self.host)
                        sources.append("默认线路")
                        play_urls.append(f"正片${src}")

                if not sources:
                    dplayer = re.search(r'new\s+DPlayer\(\s*(\{.*?\})\s*\)', html_text, re.DOTALL)
                    if dplayer:
                        try:
                            dp = json.loads(dplayer.group(1))
                            if dp.get("video", {}).get("url"):
                                vurl = fix_url(dp["video"]["url"], self.host)
                                if '.m3u8' in vurl.lower():
                                    vurl = self.源天纹(vurl, self.host)
                                sources.append("默认线路")
                                play_urls.append(f"正片${vurl}")
                        except:
                            pass

                if not sources:
                    eps = doc.xpath('//div[contains(@class,"play-list") or contains(@class,"playlist")]//a[contains(@href,"/v/video-")]')
                    if eps:
                        ep_list = []
                        for ep in eps:
                            ep_title = ep.xpath('./text()')[0] if ep.xpath('./text()') else "播放"
                            ep_href = ep.xpath('./@href')[0] if ep.xpath('./@href') else ""
                            if ep_href:
                                ep_list.append(f"{clean_text(ep_title)}${fix_url(ep_href, self.host)}")
                        if ep_list:
                            sources.append("默认线路")
                            play_urls.append("#".join(ep_list))

                if not sources:
                    for ext in [r'\.m3u8', r'\.mp4', r'\.flv']:
                        m = re.search(rf'(https?://[^\s"\'<>]+{ext}[^\s"\'<>]*)', html_text)
                        if m:
                            vurl = m.group(1)
                            if '.m3u8' in vurl.lower():
                                vurl = self.源天纹(vurl, self.host)
                            sources.append("默认线路")
                            play_urls.append(f"正片${vurl}")
                            break

            if not sources:
                sources.append("默认线路")
                play_urls.append(f"播放${url}")

            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": content,
                "vod_play_from": "$$$".join(sources) if sources else "默认线路",
                "vod_play_url": "$$$".join(play_urls) if play_urls else f"播放${url}"
            })
            return result
        except Exception as e:
            print(f"[{self.name}] 详情解析失败: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
            if self.isVideoFormat(id):
                result["url"] = id
                result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                return result
            if not id.startswith("http"):
                result["url"] = id
                return result

            html_text = self._fetch(id)
            if not html_text:
                result["url"] = id
                return result

            for ext in [r'\.m3u8', r'\.mp4', r'\.flv', r'\.ts']:
                m = re.search(rf'(https?://[^\s"\'<>]+{ext}[^\s"\'<>]*)', html_text)
                if m:
                    vurl = m.group(1)
                    if '.m3u8' in vurl.lower():
                        vurl = self.源天纹(vurl, self.host)
                    result["url"] = vurl
                    result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                    return result

            iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text)
            if iframe:
                src = fix_url(iframe.group(1), self.host)
                result["parse"] = 1
                result["url"] = src
                result["header"] = json.dumps({"Referer": id, "User-Agent": self.headers["User-Agent"]})
                return result

            dplayer = re.search(r'new\s+DPlayer\(\s*(\{.*?\})\s*\)', html_text, re.DOTALL)
            if dplayer:
                try:
                    dp = json.loads(dplayer.group(1))
                    if dp.get("video", {}).get("url"):
                        vurl = fix_url(dp["video"]["url"], self.host)
                        if '.m3u8' in vurl.lower():
                            vurl = self.源天纹(vurl, self.host)
                        result["url"] = vurl
                        result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                        return result
                except:
                    pass

            video = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html_text)
            if video:
                vurl = fix_url(video.group(1), self.host)
                if '.m3u8' in vurl.lower():
                    vurl = self.源天纹(vurl, self.host)
                result["url"] = vurl
                result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                return result

            b64_candidates = re.findall(r'["\']([A-Za-z0-9+/=]{20,})["\']', html_text)
            for b64_str in b64_candidates:
                try:
                    decoded = base64.b64decode(b64_str).decode("utf-8")
                    if decoded.startswith("http"):
                        vurl = decoded
                        if '.m3u8' in vurl.lower():
                            vurl = self.源天纹(vurl, self.host)
                        result["url"] = vurl
                        result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                        return result
                except:
                    continue

            for var_name in ["url", "video", "src", "play_url", "file", "videoUrl", "video_url"]:
                pat = re.search(rf'var\s+{var_name}\s*=\s*["\']([^"\']+)["\']', html_text)
                if pat:
                    val = pat.group(1)
                    if val.startswith("http") or val.startswith("//"):
                        if val.startswith("//"):
                            val = "https:" + val
                        vurl = val
                        if '.m3u8' in vurl.lower():
                            vurl = self.源天纹(vurl, self.host)
                        result["url"] = vurl
                        result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                        return result

            result["url"] = id
            return result
        except Exception as e:
            print(f"[{self.name}] 播放解析失败: {e}")
            return {"parse": 0, "playUrl": "", "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            url = f"{self.host}/?s={quote(key)}"
            if int(pg) > 1:
                url += f"&paged={pg}"

            html_text = self._fetch(url)
            if not html_text:
                return result
            doc = etree.HTML(html_text) if etree else None
            if not doc:
                return result

            items = doc.xpath('//div[contains(@class,"post-item")]')
            print(f"[{self.name}] 搜索匹配到 {len(items)} 个结果")
            self.seen_ids.clear()

            for item in items:
                try:
                    a_nodes = item.xpath('.//a[contains(@class,"post-link")]')
                    if not a_nodes:
                        continue
                    a = a_nodes[0]
                    href = a.xpath('./@href')[0] if a.xpath('./@href') else ""
                    vid_match = re.search(r'/v/video-(\d+)/', href)
                    if not vid_match:
                        continue
                    vid = vid_match.group(1)
                    if vid in self.seen_ids:
                        continue
                    self.seen_ids.add(vid)

                    title = ""
                    title_nodes = a.xpath('.//div[contains(@class,"post-title-container")]//span/text()')
                    if title_nodes:
                        title = clean_text(title_nodes[0])
                    if not title:
                        alt_nodes = a.xpath('.//div[contains(@class,"post-image")]//img/@alt')
                        if alt_nodes:
                            title = clean_text(alt_nodes[0])

                    pic = ""
                    pic_nodes = a.xpath('.//div[contains(@class,"post-image")]//img/@src')
                    if pic_nodes:
                        pic = fix_url(pic_nodes[0], self.host)
                    if not pic:
                        pic_nodes = a.xpath('.//div[contains(@class,"post-image")]//img/@data-src')
                        if pic_nodes:
                            pic = fix_url(pic_nodes[0], self.host)

                    remark = ""
                    result["list"].append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remark
                    })
                except Exception as e:
                    print(f"[{self.name}] 搜索单条失败: {e}")
                    continue

            pagecount = 1
            last_href = doc.xpath('//div[contains(@class,"page-nav")]//a[contains(text(),"尾页")]/@href')
            if last_href:
                m = re.search(r'[?&]paged=(\d+)', last_href[0])
                if m:
                    pagecount = int(m.group(1))
            else:
                next_href = doc.xpath('//div[contains(@class,"page-nav")]//a[contains(@class,"next")]/@href')
                if next_href:
                    m = re.search(r'[?&]paged=(\d+)', next_href[0])
                    if m:
                        pagecount = int(m.group(1))

            result["pagecount"] = pagecount
            return result
        except Exception as e:
            print(f"[{self.name}] 搜索失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

# ==================== 无始经·虚空截流·广告禁地 ====================
    def localProxy(self, param):
        """虚空门 — 横渡混沌，截杀天外邪魔（广告）"""
        try:
            if not isinstance(param, dict):
                param = {}
            pt = param.get('type') or param.get('action') or param.get('do')
            u = param.get('url', '')
            if pt != 'm3u8' or not u:
                return [404, "text/plain", "nf"]
            rf = param.get('referer', '') or (getattr(self, 'host', '') or getattr(self, 'BASE_URL', ''))
            if isinstance(u, list):
                u = u[0]
            if isinstance(rf, list):
                rf = rf[0]
            u = __import__('urllib.parse').parse.unquote(u)
            rf = __import__('urllib.parse').parse.unquote(rf)
            raw = self.神识探(u, rf)
            if not raw:
                return [404, "text/plain", "err"]
            c = self.斩道诀(raw, u, rf)
            return [200, "application/vnd.apple.mpegurl", c.encode("utf-8") if isinstance(c, str) else c, {}]
        except Exception:
            return [404, "text/plain", "err"]

    def 源天纹(self, url, referer):
        """源天纹 — 于URL上刻下大帝阵纹，借道TVBox代理"""
        try:
            if hasattr(self, 'getProxyUrl'):
                b = self.getProxyUrl()
                if '?' not in b:
                    b += '?do=py'
                return b + '&type=m3u8&url=' + __import__('urllib.parse').parse.quote(url, safe='') + '&referer=' + __import__('urllib.parse').parse.quote(referer or getattr(self, 'host', '') or getattr(self, 'BASE_URL', ''), safe='')
        except Exception:
            pass
        return url

    def 神识探(self, url, referer):
        """神识探 — 以帝境神识刺破虚妄，取回m3u8真本"""
        try:
            import requests
            h = {
                "User-Agent": getattr(self, 'headers', {}).get('User-Agent', 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36'),
                "Referer": referer,
            }
            r = requests.get(url, headers=h, timeout=15)
            if r.status_code == 200:
                r.encoding = 'utf-8'
                return r.text
        except Exception:
            pass
        return None

    def 禁地判(self, uri, dur=0, prev=None):
        """禁地判 — 以源天神眼照见广告片段，凡邪魔外道皆无所遁形"""
        u = (uri or '').strip().lower()
        if not u:
            return False
        aw = [
            'ad', 'ads', 'advert', 'advertise', 'advertisement', 'sponsor',
            'pre', 'preroll', chr(29255)+chr(22836), chr(24191)+chr(21578), '/gg/', '_gg', 'gg_', '/adv/',
            '/ad/', '/ads/', 'banner', 'promo', 'commercial'
        ]
        if any(w in u for w in aw):
            return True
        try:
            if 0 < float(dur) <= 1.2:
                return True
        except Exception:
            pass
        return False

    def 天机线(self, uri, base):
        """天机线 — 推演URI命格，抽离域名与龙脉轨迹"""
        try:
            f = __import__('urllib.parse').parse.urljoin(base, uri)
            p = __import__('urllib.parse').parse.urlparse(f)
            ph = __import__('re').sub(r'/[^/]*$', '/', p.path or '/')
            return (p.netloc.lower(), ph.lower())
        except Exception:
            return ('', '')

    def 定龙脉(self, murl):
        """定龙脉 — 锁定主音轨之祖根，凡偏离此脉者皆为旁门"""
        try:
            p = __import__('urllib.parse').parse.urlparse(murl).path
            m = __import__('re').search(r'(\/\d{8}\/[^/]+\/\d+kb\/hls\/)', p)
            if m:
                return m.group(1).lower()
            m = __import__('re').search(r'(\/\d{8}\/[^/]+\/)', p)
            if m:
                return m.group(1).lower()
        except Exception:
            pass
        return ''

    def 轮海卷(self, text):
        """轮海卷 — 将m3u8汪洋分流为道宫、四极、化龙、仙台诸境"""
        ls = [x.strip() for x in (text or '').replace('\r', '').split('\n') if x.strip()]
        hd, sg, tl = [], [], []
        pt = []
        ms = 0
        td = 0
        st = False
        i = 0
        while i < len(ls):
            ln = ls[i]
            if ln.startswith('#EXT-X-MEDIA-SEQUENCE'):
                try:
                    ms = int(ln.split(':', 1)[1])
                except Exception:
                    pass
                if not st:
                    hd.append(ln)
                else:
                    pt.append(ln)
            elif ln.startswith('#EXT-X-TARGETDURATION'):
                try:
                    td = float(ln.split(':', 1)[1])
                except Exception:
                    pass
                if not st:
                    hd.append(ln)
                else:
                    pt.append(ln)
            elif ln.startswith('#EXTINF'):
                st = True
                dr = td or 3.0
                m = __import__('re').search(r'#EXTINF:\s*([\d.]+)', ln)
                if m:
                    try:
                        dr = float(m.group(1))
                    except Exception:
                        pass
                tg = pt + [ln]
                pt = []
                uri = ''
                j = i + 1
                while j < len(ls):
                    if ls[j].startswith('#'):
                        tg.append(ls[j])
                        j += 1
                        continue
                    uri = ls[j]
                    break
                if uri:
                    sg.append({'tags': tg, 'uri': uri, 'dur': dr})
                    i = j
                else:
                    tl.extend(tg)
            elif ln.startswith('#EXT-X-ENDLIST'):
                tl.append(ln)
            elif ln.startswith('#'):
                if st:
                    pt.append(ln)
                else:
                    hd.append(ln)
            else:
                st = True
                dr = td or 3.0
                sg.append({'tags': pt, 'uri': ln, 'dur': dr})
                pt = []
            i += 1
        return hd, sg, tl, ms, td

    def 斩道诀(self, txt, base, referer, skip=25):
        """斩道诀 — 天帝拳出，斩尽广告邪魔，重塑纯净大道"""
        t = (txt or '').replace('\r', '')
        if '#EXT-X-STREAM-INF' in t:
            o = []
            for ln in t.splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                if ln.startswith('#'):
                    o.append(ln)
                else:
                    a = __import__('urllib.parse').parse.urljoin(base, ln)
                    if '.m3u8' in ln.lower():
                        o.append(self.源天纹(a, referer))
                    else:
                        o.append(a)
            return '\n'.join(o) + '\n'

        hd, sg, tl, ms, td = self.轮海卷(t)
        if not sg:
            return t

        mk = self.定龙脉(base)
        st = {}
        for s in sg:
            k = self.天机线(s['uri'], base)
            st[k] = st.get(k, 0.0) + float(s.get('dur') or 0)
        mkk = max(st.items(), key=lambda x: x[1])[0] if st else ('', '')
        tdur = sum(st.values()) or 0
        mdur = st.get(mkk, 0)

        cl = []
        rm = 0
        for idx, s in enumerate(sg):
            k = self.天机线(s['uri'], base)
            fr = idx < 12
            au = __import__('urllib.parse').parse.urljoin(base, s.get('uri', ''))
            ia = self.禁地判(s['uri'], s.get('dur'), s.get('tags'))
            if mk and mk not in __import__('urllib.parse').parse.urlparse(au).path.lower():
                ia = True
            tt = '\n'.join(s.get('tags') or []).upper()
            if fr and 'METHOD=NONE' in tt and mk and mk not in __import__('urllib.parse').parse.urlparse(au).path.lower():
                ia = True
            if (not ia) and fr and tdur > 0 and mdur >= tdur * 0.6:
                if k != mkk and st.get(k, 0) <= 90:
                    ia = True
            if ia:
                rm += 1
                continue
            s['_idx'] = idx
            cl.append(s)

        if rm == 0 and len(sg) > 4:
            ac = 0.0
            ct = 0
            for idx, s in enumerate(sg[:12]):
                k = self.天机线(s['uri'], base)
                if k == mkk and ac >= 3:
                    break
                ac += float(s.get('dur') or td or 3)
                ct = idx + 1
                if ac >= skip:
                    break
            if ct > 0 and ct < len(sg):
                fk = self.天机线(sg[0]['uri'], base)
                if fk != mkk:
                    cl = sg[ct:]
                    rm = ct

        if not cl:
            cl = sg
            rm = 0

        nl = []
        hm = False
        for ln in hd:
            if ln.startswith('#EXTM3U'):
                hm = True
            if ln.startswith('#EXT-X-MEDIA-SEQUENCE') or ln.startswith('#EXT-X-START'):
                continue
            if ln.startswith('#EXT-X-KEY') and 'METHOD=NONE' in ln.upper() and rm > 0:
                continue
            nl.append(ln)
        if not hm:
            nl.insert(0, '#EXTM3U')
        fi = cl[0].get('_idx', rm) if cl else rm
        nl.append(f'#EXT-X-MEDIA-SEQUENCE:{ms + fi}')
        for s in cl:
            for tg in s.get('tags') or []:
                if tg.startswith('#EXT-X-KEY') or tg.startswith('#EXT-X-MAP'):
                    tg = __import__('re').sub(r'URI="([^"]+)"', lambda m: 'URI="' + __import__('urllib.parse').parse.urljoin(base, m.group(1)) + '"', tg)
                nl.append(tg)
            nl.append(__import__('urllib.parse').parse.urljoin(base, s.get('uri', '')))
        if tl:
            for ln in tl:
                if ln.startswith('#EXT-X-ENDLIST'):
                    nl.append(ln)
        elif '#EXT-X-ENDLIST' in t:
            nl.append('#EXT-X-ENDLIST')
        return '\n'.join(nl) + '\n'
