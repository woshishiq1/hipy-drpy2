# -*- coding: utf-8 -*-
# lujj31.buzz · MacCMS v10 (whosTv女优列表模式+全分类播放修复版)
import sys, re, json, base64, html, os, threading, time, hashlib
from urllib.parse import quote, unquote, urljoin, urlparse

try:
    from lxml import etree
except ImportError:
    etree = None
try:
    import requests
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
        def playerContent(self, flag, id, vipFlags=None): pass
        def searchContent(self, key, quick, pg="1"): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def localProxy(self, param): pass

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


def _extract_from_intermediate(html_text, referer):
    """对中间跳转页二次解析，提取真正的视频地址"""
    m = re.search(r'url:\s*"([^"]+\.m3u8[^"]*)"', html_text)
    if m:
        return m.group(1)
    m = re.search(r'video:\s*\{[^}]*url:\s*"([^"]+)"', html_text)
    if m:
        url = m.group(1)
        if ".m3u8" in url or ".mp4" in url:
            return url
    m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_text)
    if m:
        return m.group(1)
    m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html_text)
    if m:
        return m.group(1)
    m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text)
    if m and requests:
        src = fix_url(m.group(1), referer)
        try:
            r = requests.get(src, headers={"User-Agent": "Mozilla/5.0", "Referer": referer}, timeout=10)
            return _extract_from_intermediate(r.text, src)
        except:
            pass
    for pattern in (
        r'var\s+url\s*=\s*["\']([^"\']+)["\']',
        r'var\s+videoUrl\s*=\s*["\']([^"\']+)["\']',
        r'var\s+play_url\s*=\s*["\']([^"\']+)["\']',
        r'"url"\s*:\s*"([^"]+)"',
    ):
        m = re.search(pattern, html_text)
        if m:
            url = m.group(1)
            if ".m3u8" in url or ".mp4" in url:
                return url
    return ""


def extract_play(html_text, host, do_deep=True):
    """深度提取视频播放地址，支持MacCMS v10多种播放器"""
    m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;</script>', html_text, re.DOTALL)
    if not m:
        m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html_text, re.DOTALL)
    if m:
        try:
            raw = m.group(1)
            url_m = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            url = url_m.group(1).replace('\\/', '/') if url_m else ""
            encrypt_m = re.search(r'"encrypt"\s*:\s*(\d+)', raw)
            encrypt = int(encrypt_m.group(1)) if encrypt_m else 0
            if encrypt == 2 and url:
                try:
                    url = base64.b64decode(url).decode("utf-8")
                except:
                    pass
            if url:
                if any(x in url for x in [".m3u8", ".mp4", ".flv"]):
                    return url
                if do_deep and requests:
                    try:
                        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": host + "/"}, timeout=15)
                        real = _extract_from_intermediate(r.text, url)
                        if real:
                            return real
                    except Exception as e:
                        print(f"[{host}] 中间页解析失败: {e}")
                return url
        except Exception as e:
            print(f"[{host}] player_aaaa解析失败: {e}")

    m = re.search(r'player_data\s*=\s*(\{.*?\})', html_text, re.DOTALL)
    if m:
        try:
            url = json.loads(m.group(1)).get("url", "")
            if url:
                if any(x in url for x in [".m3u8", ".mp4", ".flv"]):
                    return url
                if do_deep and requests:
                    try:
                        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": host + "/"}, timeout=15)
                        real = _extract_from_intermediate(r.text, url)
                        if real:
                            return real
                    except:
                        pass
                return url
        except:
            pass

    m = re.search(r'var\s*now\s*=\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)
    m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_text)
    if m:
        return m.group(1)
    m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html_text)
    if m:
        return m.group(1)
    m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html_text)
    if m:
        src = fix_url(m.group(1), host)
        try:
            if requests:
                r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                return extract_play(r.text, host, do_deep=False)
        except:
            pass
    m = re.search(r'videoSources\s*:\s*(\[.*?\])', html_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))[0].get("file", "")
        except:
            pass
    m = re.search(r'wvPlayer\.play\s*\(\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)
    m = re.search(r'location\.href\s*=\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)
    m = re.search(r'url\s*:\s*["\']([^"\']+\.m3u8)["\']', html_text)
    if m:
        return m.group(1)
    m = re.search(r'var\s*playurl\s*=\s*["\']([^"\']+)["\']', html_text)
    if m:
        return m.group(1)
    m = re.search(r'MacPlayer\.PlayUrl\s*=\s*["\']([^"\']+)["\']', html_text)
    if m:
        url = m.group(1)
        if url.startswith("//"):
            return "https:" + url
        return fix_url(url, host)
    m = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4|flv))', html_text)
    if m:
        return m.group(1)
    m = re.search(r'"url"\s*:\s*"([^"]+)"', html_text)
    if m:
        url = m.group(1)
        if ".m3u8" in url or ".mp4" in url:
            return url if url.startswith("http") else fix_url(url, host)
    return ""


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self.host = "https://lujj31.buzz"
        self.name = "Lujj31"
        self.s = requests.Session() if requests else None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "sec-ch-ua": "\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"120\""
        }
        self.seen_ids = set()
        if self.s:
            self.s.headers.update(self.headers)

    def init(self, extend=""):
        pass

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        return any(x in url for x in [".m3u8", ".mp4", ".flv", ".ts"])

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [200, "video/MP2T", b"", {}]

    def _fetch(self, url):
        if not self.s:
            return ""
        try:
            r = self.s.get(url, timeout=15, headers=self.headers)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"[{self.name}] 请求失败: {url} - {e}")
            return ""

    # ---------- 女优名字提取 ----------
    def _extract_actress_name(self, title):
        """从视频标题中提取女优名字"""
        if not title:
            return None
        blacklist = {'未知', '演员', '等演员', '等', '中文', '高清', '无码', '国产', '日本', '同意', '泄漏', '流出', '连'}

        def valid(name):
            if not name or len(name) < 2 or len(name) > 5:
                return False
            for bw in blacklist:
                if bw in name:
                    return False
            if re.match(r'^[\u3040-\u309f\u30a0-\u30ff]+$', name):
                return False
            return True

        m = re.search(r'([\u4e00-\u9fff]{2,4})\s+[\u3040-\u309f\u30a0-\u30ff・\u3005]+\s+[A-Z]{2,6}[_-]?\d{2,5}', title)
        if m and valid(m.group(1)):
            return m.group(1)
        m = re.search(r'([\u4e00-\u9fff]{2,4})\s+[A-Z]{2,6}[_-]?\d{2,5}$', title)
        if m and valid(m.group(1)):
            return m.group(1)
        m = re.search(r'^([\u4e00-\u9fff]{2,4})[-\s][A-Z]{2,6}[_-]?\d{2,5}', title)
        if m and valid(m.group(1)):
            return m.group(1)
        m = re.search(r'([\u4e00-\u9fff]{2,4}).*\1\s+[A-Z]{2,6}[_-]?\d{2,5}', title)
        if m and valid(m.group(1)):
            return m.group(1)
        m = re.search(r'\b([A-Z][a-z]{2,7})\s+[A-Z]{2,6}[_-]?\d{2,5}$', title)
        if m and len(m.group(1)) >= 3:
            return m.group(1)
        return None

    def _actress_list(self, pg):
        """女优明星：从 tid=28 视频标题中智能提取女优，返回 folder 列表"""
        result = {"list": [], "page": int(pg), "pagecount": int(pg), "limit": 24, "total": 0}

        url = f"{self.host}/index.php/vod/type/id/28/page/{pg}.html"
        html_text = self._fetch(url)
        if not html_text:
            return result

        doc = etree.HTML(html_text) if etree else None
        if not doc:
            return result

        items = doc.xpath("//li[contains(@class,'stui-vodlist__item')]")
        seen = set()

        for item in items:
            try:
                title_elem = item.xpath(".//h4[contains(@class,'stui-vodlist__title')]/a/text()")
                pic_elem = item.xpath(".//a[contains(@class,'stui-vodlist__thumb')]/@data-original")

                if title_elem:
                    title = clean_text(title_elem[0])
                    name = self._extract_actress_name(title)
                    if name and name not in seen:
                        seen.add(name)
                        pic = pic_elem[0] if pic_elem else ""
                        result["list"].append({
                            "vod_id": f"actress_{name}",
                            "vod_name": name,
                            "vod_pic": pic,
                            "vod_remarks": title[:35] + "..." if len(title) > 35 else title,
                            "vod_tag": "folder"
                        })
            except Exception as e:
                print(f"[{self.name}] 女优提取失败: {e}")
                continue

        has_next = doc.xpath("//a[contains(text(),'下一页')]") or re.search(r'<a[^>]*href=["\'][^"\']*page/\d+["\'][^>]*>下一页</a>', html_text, re.I)
        if has_next:
            result["pagecount"] = int(pg) + 1
        else:
            result["pagecount"] = int(pg)

        result["total"] = len(result["list"])
        print(f"[{self.name}] 女优列表第{pg}页提取到 {len(result['list'])} 位")
        return result

    def _actress_videos(self, actress_name, pg):
        """通过搜索接口查找女优的视频（模仿 whosTv 的 actress 详情页）"""
        result = {"list": [], "page": int(pg), "pagecount": int(pg), "limit": 24, "total": 0}

        # 使用搜索
        search_res = self.searchContent(actress_name, False, pg)
        if search_res and search_res.get("list"):
            result["list"] = search_res["list"]
            result["page"] = search_res.get("page", int(pg))
            result["pagecount"] = search_res.get("pagecount", int(pg))
            result["total"] = search_res.get("total", len(search_res["list"]))
        return result

    def homeContent(self, filter):
        try:
            classes = [
                {"type_name": "国产精品", "type_id": "1"},
                {"type_name": "亚洲综合", "type_id": "2"},
                {"type_name": "工口动漫", "type_id": "4"},
                {"type_name": "cosplay", "type_id": "6"},
                {"type_name": "国产乱伦", "type_id": "7"},
                {"type_name": "91大神", "type_id": "8"},
                {"type_name": "主播网红", "type_id": "9"},
                {"type_name": "清纯学生", "type_id": "10"},
                {"type_name": "国产原创", "type_id": "11"},
                {"type_name": "怀旧AV", "type_id": "12"},
                {"type_name": "日本有码", "type_id": "13"},
                {"type_name": "日本无码", "type_id": "14"},
                {"type_name": "av解说", "type_id": "16"},
                {"type_name": "国产自拍", "type_id": "20"},
                {"type_name": "偷拍偷窥", "type_id": "21"},
                {"type_name": "网曝吃瓜", "type_id": "22"},
                {"type_name": "抖阴短片", "type_id": "23"},
                {"type_name": "日韩主播", "type_id": "24"},
                {"type_name": "中文字幕", "type_id": "25"},
                {"type_name": "AI明星", "type_id": "26"},
                {"type_name": "强奸乱伦", "type_id": "27"},
                {"type_name": "女优明星", "type_id": "28"},
                {"type_name": "VR视角", "type_id": "29"},
                {"type_name": "SM调教", "type_id": "30"},
                {"type_name": "泰国风情", "type_id": "31"},
                {"type_name": "绝色佳人", "type_id": "32"},
                {"type_name": "风俗泡泡浴", "type_id": "33"},
                {"type_name": "时间停止", "type_id": "34"},
                {"type_name": "漫改系列", "type_id": "35"},
                {"type_name": "绝顶潮吹", "type_id": "36"},
                {"type_name": "精品推荐", "type_id": "37"},
                {"type_name": "国产色情", "type_id": "38"},
                {"type_name": "主播直播", "type_id": "39"},
                {"type_name": "制服丝袜", "type_id": "40"},
                {"type_name": "台湾辣妹", "type_id": "41"},
                {"type_name": "网红流出", "type_id": "42"},
                {"type_name": "风情旗袍", "type_id": "43"},
                {"type_name": "多人多P", "type_id": "45"},
                {"type_name": "韩国御姐", "type_id": "46"},
                {"type_name": "闷骚护士", "type_id": "47"},
                {"type_name": "瑜伽裤", "type_id": "48"},
                {"type_name": "古装扮演", "type_id": "49"},
                {"type_name": "过膝袜", "type_id": "50"},
                {"type_name": "兽耳系列", "type_id": "51"},
            ]
            filters = {
                "1": [
                    {"key": "area", "name": "地区", "value": [{"n":"全部","v":""}, {"n":"大陆","v":"大陆"}, {"n":"香港","v":"香港"}, {"n":"台湾","v":"台湾"}, {"n":"日本","v":"日本"}, {"n":"韩国","v":"韩国"}, {"n":"欧美","v":"欧美"}]},
                    {"key": "year", "name": "年份", "value": [{"n":"全部","v":""}, {"n":"2026","v":"2026"}, {"n":"2025","v":"2025"}, {"n":"2024","v":"2024"}, {"n":"2023","v":"2023"}]},
                    {"key": "by", "name": "排序", "value": [{"n":"时间","v":"time"}, {"n":"人气","v":"hits"}, {"n":"评分","v":"score"}]},
                ]
            }
            return {"class": classes, "filters": filters}
        except Exception as e:
            print(f"[{self.name}] 首页失败: {e}")
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("1", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        # ===== 女优明星：返回女优 folder 列表 =====
        if str(tid) == "28":
            return self._actress_list(pg)

        # ===== 女优个人作品页：tid 以 actress_ 开头 =====
        if isinstance(tid, str) and tid.startswith("actress_"):
            actress_name = tid[len("actress_"):]
            return self._actress_videos(actress_name, pg)

        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            area = extend.get("area", "") if extend else ""
            year = extend.get("year", "") if extend else ""
            by = extend.get("by", "time") if extend else "time"
            url = f"{self.host}/index.php/vod/type/id/{tid}/page/{pg}"
            if area:
                url += f"/area/{quote(area)}"
            if year:
                url += f"/year/{year}"
            url += f"/by/{by}.html"
            html_text = self._fetch(url)
            if not html_text:
                return result
            doc = etree.HTML(html_text) if etree else None
            if not doc:
                return result
            items = doc.xpath("//li[contains(@class,'stui-vodlist__item')]")
            if not items:
                items = doc.xpath("//a[contains(@class,'stui-vodlist__thumb')]")
            if not items:
                items = doc.xpath("//a[contains(@href,'/vod/detail/') and .//img]")
            print(f"[{self.name}] 分类列表匹配到 {len(items)} 个视频")
            self.seen_ids.clear()
            for item in items:
                try:
                    title = item.xpath(".//h4[contains(@class,'stui-vodlist__title')]/a/text()")
                    if not title:
                        title = item.xpath(".//a/@title")
                    if not title:
                        title = item.xpath(".//img/@alt")
                    title = clean_text(title[0]) if title else ""
                    href = item.xpath(".//a[contains(@class,'stui-vodlist__thumb')]/@href")
                    if not href:
                        href = item.xpath(".//a/@href")
                    href = href[0] if href else ""
                    vid = re.search(r"/id/(\d+)\.html", href)
                    if not vid:
                        vid = re.search(r"/id/(\d+)", href)
                    vid = vid.group(1) if vid else href
                    if vid in self.seen_ids:
                        continue
                    self.seen_ids.add(vid)
                    pic = item.xpath(".//img/@data-original")
                    if not pic:
                        pic = item.xpath(".//img/@src")
                    if not pic:
                        pic = item.xpath(".//a[contains(@class,'stui-vodlist__thumb')]/@data-original")
                    pic = fix_url(pic[0], self.host) if pic else ""

                    remark = ""
                    remark_elem = item.xpath(".//span[contains(@class,'pic-text')]/text()")
                    if remark_elem:
                        remark = clean_text(remark_elem[0])

                    result["list"].append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remark
                    })
                except Exception as e:
                    print(f"[{self.name}] 单条解析失败: {e}")
                    continue
            pc = re.search(r"pagecount[=:](\d+)", html_text) or re.search(r"共\s*(\d+)\s*页", html_text)
            if pc:
                result["pagecount"] = int(pc.group(1))
            else:
                has_next = re.search(r"""<a[^>]*href=['"][^'"]*page=(\d+)['"][^>]*>下一页</a>""", html_text, re.I) or re.search(r"""<a[^>]*href=['"][^'"]*/page/(\d+)['"][^>]*>下一页</a>""", html_text, re.I)
                if has_next:
                    result["pagecount"] = int(pg) + 1
                else:
                    result["pagecount"] = int(pg)
            return result
        except Exception as e:
            print(f"[{self.name}] 分类爬取失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, list) else ids

            # ===== 女优详情：直接返回该女优的视频列表（与 whosTv.py 逻辑一致）=====
            if isinstance(vid, str) and vid.startswith("actress_"):
                return self.categoryContent(vid, "1", None, None)

            result = {"list": []}
            urls = [
                f"{self.host}/index.php/vod/detail/id/{vid}.html",
                f"{self.host}/index.php/vod/play/id/{vid}.html"
            ]
            html_text = ""
            for u in urls:
                html_text = self._fetch(u)
                if html_text:
                    break
            if not html_text:
                return result
            doc = etree.HTML(html_text) if etree else None
            title = vid
            pic = ""
            content = ""
            if doc:
                title = doc.xpath("//h1/text()") or doc.xpath("//h2/text()") or doc.xpath("//div[contains(@class,'stui-content__detail')]//h3/text()")
                title = clean_text(title[0]) if title else vid
                pic = doc.xpath("//img[contains(@class,'pic') or contains(@class,'cover') or contains(@class,'poster')]/@src")
                if not pic:
                    pic = doc.xpath("//img[contains(@class,'pic') or contains(@class,'cover')]/@data-original")
                pic = fix_url(pic[0], self.host) if pic else ""

                content = doc.xpath("//div[contains(@class,'stui-content__desc') or contains(@class,'desc')]//text()")
                if not content:
                    content = doc.xpath("//p[contains(@class,'desc') or contains(@class,'summary')]//text()")
                if not content:
                    content = doc.xpath("//span[contains(@class,'detail-content')]//text()")
                if not content:
                    content = doc.xpath("//div[contains(@class,'detail')]//p//text()")
                content = "".join(content).strip()
                content = re.sub(r"\s+", " ", content)

            sources = []
            play_urls = []
            if doc:
                panels = doc.xpath("//div[contains(@class,'stui-content__playlist')]")
                if not panels:
                    panels = doc.xpath("//div[contains(@class,'playlist')]")
                if not panels:
                    panels = doc.xpath("//div[contains(@class,'module-tab')]")
                print(f"[{self.name}] 详情页提取到 {len(panels)} 个播放源面板")
                for panel in panels:
                    try:
                        sname = panel.xpath(".//h3/text()") or panel.xpath(".//span[contains(@class,'title')]/text()") or panel.xpath(".//a[contains(@class,'option')]/@title")
                        sname = clean_text(sname[0]) if sname else "默认"
                        eps = panel.xpath(".//a[contains(@href,'/vod/play/')]")
                        if not eps:
                            eps = panel.xpath(".//li/a[contains(@href,'/play/')]")
                        ep_list = []
                        for ep in eps:
                            try:
                                ep_title = ep.xpath("./text()")
                                ep_title = clean_text(ep_title[0]) if ep_title else "播放"
                                ep_href = ep.xpath("./@href")
                                ep_href = ep_href[0] if ep_href else ""
                                ep_list.append(f"{ep_title}${fix_url(ep_href, self.host)}")
                            except:
                                continue
                        if ep_list:
                            sources.append(sname)
                            play_urls.append("#".join(ep_list))
                    except Exception as e:
                        print(f"[{self.name}] 播放源解析失败: {e}")
                        continue
                if not sources:
                    play_links = doc.xpath("//a[contains(@href,'/vod/play/')]/@href")
                    if play_links:
                        seen_href = set()
                        ep_list = []
                        for href in play_links:
                            if href in seen_href:
                                continue
                            seen_href.add(href)
                            ep_list.append(f"正片${fix_url(href, self.host)}")
                        if ep_list:
                            sources.append("默认")
                            play_urls.append("#".join(ep_list))
            if not sources and html_text:
                direct = extract_play(html_text, self.host)
                if direct:
                    sources.append("默认")
                    play_urls.append(f"正片${direct}")
            print(f"[{self.name}] 详情页提取到 {len(sources)} 个播放源, {sum(len(x.split(chr(35))) for x in play_urls)} 个剧集")

            result["list"].append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": content if content else title,
                "vod_play_from": "$$$".join(sources) if sources else "默认",
                "vod_play_url": "$$$".join(play_urls) if play_urls else f"播放${vid}"
            })
            return result
        except Exception as e:
            print(f"[{self.name}] 详情解析失败: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": ""}
            if self.isVideoFormat(id):
                result["url"] = id
                result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                print(f"[{self.name}] 播放解析(直链): {flag} -> {id[:80]}...")
                return result
            if not id.startswith("http"):
                result["url"] = id
                return result

            html_text = self._fetch(id)
            if html_text:
                play_url = extract_play(html_text, self.host)
                if play_url:
                    result["url"] = play_url
                    result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
                    print(f"[{self.name}] 播放解析: {flag} -> {play_url[:80]}...")
                    return result

            result["url"] = id
            result["parse"] = 1
            result["header"] = json.dumps({"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]})
            return result
        except Exception as e:
            print(f"[{self.name}] 播放解析失败: {e}")
            return {"parse": 0, "playUrl": "", "url": id, "header": ""}

    def searchContent(self, key, quick, pg="1"):
        try:
            result = {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
            url = f"{self.host}/index.php/vod/search.html?wd={quote(key)}&page={pg}"
            html_text = self._fetch(url)
            if not html_text:
                return result
            doc = etree.HTML(html_text) if etree else None
            if not doc:
                return result
            items = doc.xpath("//li[contains(@class,'stui-vodlist__item')]")
            if not items:
                items = doc.xpath("//a[contains(@class,'stui-vodlist__thumb')]")
            if not items:
                items = doc.xpath("//a[contains(@href,'/vod/detail/') and .//img]")
            print(f"[{self.name}] 搜索匹配到 {len(items)} 个结果")
            self.seen_ids.clear()
            for item in items:
                try:
                    title = item.xpath(".//h4[contains(@class,'stui-vodlist__title')]/a/text()") or item.xpath(".//a/@title") or item.xpath(".//img/@alt")
                    title = clean_text(title[0]) if title else ""
                    href = item.xpath(".//a[contains(@class,'stui-vodlist__thumb')]/@href") or item.xpath(".//a/@href")
                    href = href[0] if href else ""
                    vid = re.search(r"/id/(\d+)\.html", href)
                    if not vid:
                        vid = re.search(r"/id/(\d+)", href)
                    vid = vid.group(1) if vid else href
                    if vid in self.seen_ids:
                        continue
                    self.seen_ids.add(vid)
                    pic = item.xpath(".//img/@data-original") or item.xpath(".//img/@src") or item.xpath(".//a[contains(@class,'stui-vodlist__thumb')]/@data-original")
                    pic = fix_url(pic[0], self.host) if pic else ""

                    remark = ""
                    remark_elem = item.xpath(".//span[contains(@class,'pic-text')]/text()")
                    if remark_elem:
                        remark = clean_text(remark_elem[0])

                    result["list"].append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": remark
                    })
                except Exception as e:
                    print(f"[{self.name}] 搜索单条失败: {e}")
                    continue
            return result
        except Exception as e:
            print(f"[{self.name}] 搜索失败: {e}")
            return {"list": [], "page": int(pg), "pagecount": 1, "limit": 24, "total": 0}
