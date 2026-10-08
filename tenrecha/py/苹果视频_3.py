# coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import json
import urllib.parse
import re
import html
import requests
from lxml import etree

class Spider(Spider):

    def getName(self):
        return "苹果视频"

    def init(self, extend=""):
        self.domain_pool = [
            '618600.xyz', '618601.xyz', '618602.xyz', '618603.xyz', '618604.xyz',
            '618605.xyz', '618606.xyz', '618607.xyz', '618608.xyz', '618609.xyz',
            '618610.xyz', '618611.xyz', '618612.xyz', '618613.xyz', '618614.xyz',
            '618615.xyz', '618620.xyz', '618621.xyz', '618622.xyz', '618623.xyz',
            '618624.xyz', '618625.xyz', '618626.xyz', '618627.xyz', '618629.xyz',
            '618630.xyz', '618631.xyz', '618632.xyz', '618633.xyz', '618634.xyz',
            '618635.xyz', '618636.xyz', '618637.xyz', '618639.xyz', '618640.xyz',
            '618641.xyz', '618642.xyz', '618644.xyz', '618645.xyz', '618646.xyz',
            '618647.xyz', '61860120.xyz', '618649.xyz', '618650.xyz', '618651.xyz',
            '618652.xyz', '618653.xyz', '618654.xyz', '618655.xyz', '618660.xyz',
            '618661.xyz', '618662.xyz', '618663.xyz', '618671.xyz', '618672.xyz',
            '618673.xyz', '618674.xyz', '618675.xyz', '618676.xyz', '618677.xyz',
            '61860100.xyz', '6186134.xyz', '6186133.xyz', '6186132.xyz', '6186131.xyz',
            '6186130.xyz', '6186129.xyz', '6186128.xyz', '6186127.xyz', '6186126.xyz',
            '6186125.xyz', '6186124.xyz', '6186123.xyz', '6186122.xyz', '6186121.xyz',
            '6186120.xyz', '6186119.xyz', '6186118.xyz', '6186117.xyz', '6186116.xyz',
            '6186115.xyz', '6186114.xyz', '6186113.xyz', '6186112.xyz', '6186111.xyz',
            '6186110.xyz', '6186109.xyz', '6186108.xyz', '6186107.xyz', '6186106.xyz',
            '6186105.xyz', '6186104.xyz', '6186103.xyz', '6186102.xyz', '6186101.xyz',
        ]
        self.host = self._get_working_domain()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Referer': self.host
        }
        self.category_names = {
            '37': '国产AV', '43': '探花AV', '40': '网黄UP主', '49': '绿帽淫妻',
            '44': '国产传媒', '41': '福利姬', '39': '字幕', '45': '水果派',
            '42': '主播直播', '38': '欧美', '66': 'FC2', '46': '性爱教学',
            '48': '三级片', '47': '动漫'
        }
        self.log(f"苹果视频爬虫初始化完成，主站: {self.host}")

    def _get_working_domain(self):
        import random
        domains = self.domain_pool.copy()
        random.shuffle(domains)
        test_headers = {'User-Agent': 'Mozilla/5.0'}
        for domain in domains:
            url = f"https://{domain}/index.php/vod/type/id/37.html"
            try:
                rsp = requests.get(url, headers=test_headers, timeout=8, verify=False)
                if rsp and rsp.status_code == 200:
                    if 'thumbnail' in rsp.text or 'm3u8' in rsp.text:
                        self.log(f"找到可用域名: {domain}")
                        return f"https://{domain}"
            except:
                continue
        return "https://618600.xyz"

    def html(self, content):
        try:
            return etree.HTML(content)
        except:
            return None

    def log(self, message):
        print(f"[苹果视频] {message}")

    def fetch(self, url, headers=None, method='GET', data=None, timeout=15):
        try:
            if headers is None:
                headers = self.headers
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
            else:
                response = requests.post(url, headers=headers, data=data, timeout=timeout, verify=False, allow_redirects=True)
            return response
        except Exception as e:
            self.log(f"网络请求失败: {url}, 错误: {str(e)}")
            return None

    def _decrypt_title(self, encrypted_text):
        try:
            return ''.join(chr(ord(c) ^ 128) for c in encrypted_text)
        except:
            return encrypted_text

    def _extract_total_pages(self, text):
        """从页面JS变量 const totalPages='xxx' 中提取总页数"""
        try:
            js_match = re.search(r"const totalPages\s*=\s*['\"]?(\d+)['\"]?", text)
            if js_match:
                return int(js_match.group(1))
        except:
            pass
        return None

    def _normalize_pic_url(self, pic_url):
        """修复封面URL - 统一处理各种图片地址格式"""
        if not pic_url:
            return ''
        pic_url = pic_url.strip()
        if pic_url.startswith('//'):
            pic_url = 'https:' + pic_url
        elif pic_url.startswith('/'):
            pic_url = self.host + pic_url
        elif not pic_url.startswith('http'):
            pic_url = self.host + '/' + pic_url
        pic_url = pic_url.replace(' ', '%20')
        return pic_url

    def _extract_videos(self, doc, limit=None):
        videos = []
        elements = doc.xpath('//ul[contains(@class,"thumbnail-group")]//a[contains(@class,"thumbnail")]')
        self.log(f"找到 {len(elements)} 个视频元素")

        for elem in elements:
            try:
                href = elem.xpath('./@href')[0]
                if href.startswith('/'):
                    href = self.host + href

                # 从href解析参数（先解码HTML实体 &amp; → &）
                href_decoded = html.unescape(href)
                parsed = urllib.parse.urlparse(href_decoded)
                params = urllib.parse.parse_qs(parsed.query)
                video_url = params.get('v', [''])[0]
                pic_url = params.get('b', [''])[0]

                # vod_id 用URL编码后的完整href（作为播放页ID）
                vod_id = urllib.parse.quote(href, safe='')

                # 提取标题
                title_elem = elem.xpath('.//span[contains(@class,"title")]/text()')
                if not title_elem:
                    title_elem = elem.xpath('.//img/@alt')
                title = self._decrypt_title(title_elem[0].strip()) if title_elem else '未知标题'

                # 提取图片 - 按优先级尝试多种属性
                if not pic_url:
                    for attr in ['data-original', 'data-src', 'src']:
                        pic_elem = elem.xpath('.//img/@' + attr)
                        if pic_elem:
                            pic_url = pic_elem[0]
                            break

                # 规范化图片URL（修复封面不显示的核心）
                pic_url = self._normalize_pic_url(pic_url)

                videos.append({
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': pic_url,
                    'vod_remarks': '',
                    'vod_year': ''
                })
            except Exception as e:
                self.log(f"提取视频出错: {str(e)}")
                continue

        return videos[:limit] if limit and videos else videos

    def homeContent(self, filter):
        result = {}
        domain = self.host.replace('https://', '')
        classes = []
        for cid, cname in self.category_names.items():
            classes.append({'type_id': f"{domain}_{cid}", 'type_name': cname})
        result['class'] = classes

        try:
            # 首页根路径返回JS空壳，改为访问最新影片页
            home_url = self.host + '/index.php/vod/type/id/36.html'
            rsp = self.fetch(home_url, headers=self.headers)
            if not rsp or rsp.status_code != 200:
                result['list'] = []
                return result
            doc = self.html(rsp.text)
            if not doc:
                result['list'] = []
                return result
            result['list'] = self._extract_videos(doc, limit=20)
        except Exception as e:
            self.log(f"首页获取出错: {str(e)}")
            result['list'] = []
        return result

    def homeVideoContent(self):
        domain = self.host.replace('https://', '')
        classes = []
        for cid, cname in self.category_names.items():
            classes.append({'type_id': f"{domain}_{cid}", 'type_name': cname})
        return {'class': classes}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            parts = tid.split('_', 1)
            if len(parts) < 2:
                return {'list': []}
            domain = parts[0]
            type_id = parts[1]
            url = f"https://{domain}/index.php/vod/type/id/{type_id}.html"
            if pg and pg != '1':
                url = url.replace('.html', f'/page/{pg}.html')

            self.log(f"访问分类URL: {url}")
            rsp = self.fetch(url, headers=self.headers)
            if not rsp or rsp.status_code != 200:
                return {'list': []}

            doc = self.html(rsp.text)
            if not doc:
                return {'list': []}

            videos = self._extract_videos(doc, limit=20)

            pagecount = 5
            total = 100
            page_elements = doc.xpath('//ul[@class="pagination"]/li/a')
            if page_elements:
                try:
                    for elem in page_elements:
                        text = elem.text or ''
                        if '尾' in text or 'last' in text.lower():
                            href = elem.xpath('./@href')[0]
                            page_match = re.search(r'/page/(\d+)\.html', href)
                            if page_match:
                                pagecount = int(page_match.group(1))
                                total = pagecount * 20
                                break
                except:
                    pass
            else:
                # 分页控件为空（JS动态生成），从JS变量提取总页数
                js_pages = self._extract_total_pages(rsp.text)
                if js_pages:
                    pagecount = js_pages
                    total = js_pages * 20

            return {
                'list': videos,
                'page': int(pg),
                'pagecount': pagecount,
                'limit': 20,
                'total': total
            }
        except Exception as e:
            self.log(f"分类内容获取出错: {str(e)}")
            return {'list': []}

    def searchContent(self, key, quick, pg="1"):
        try:
            domain = self.host.replace('https://', '')
            search_url = f"https://{domain}/index.php/vod/search/wd/{urllib.parse.quote(key)}/page/{pg}.html"
            self.log(f"搜索URL: {search_url}")

            rsp = self.fetch(search_url, headers=self.headers)
            if not rsp or rsp.status_code != 200:
                self.log("搜索请求失败")
                return {'list': []}

            doc = self.html(rsp.text)
            if not doc:
                return {'list': []}

            videos = self._extract_videos(doc, limit=20)

            # 从JS变量或分页链接提取总页数
            pagecount = 5
            total = 100
            page_elements = doc.xpath('//ul[@class="pagination"]/li/a')
            if page_elements:
                try:
                    for elem in page_elements:
                        text = elem.text or ''
                        if '尾' in text or 'last' in text.lower():
                            href = elem.xpath('./@href')[0]
                            page_match = re.search(r'/page/(\d+)\.html', href)
                            if page_match:
                                pagecount = int(page_match.group(1))
                                total = pagecount * 20
                                break
                except:
                    pass
            else:
                js_pages = self._extract_total_pages(rsp.text)
                if js_pages:
                    pagecount = js_pages
                    total = js_pages * 20

            return {
                'list': videos,
                'page': int(pg),
                'pagecount': pagecount,
                'limit': 20,
                'total': total
            }
        except Exception as e:
            self.log(f"搜索出错: {str(e)}")
            return {'list': []}

    def detailContent(self, ids):
        """详情页 - 直接从vod_id（编码后的URL）解析参数构造详情"""
        try:
            vid = ids[0]
            # vod_id 是URL编码后的完整播放页URL
            play_url = urllib.parse.unquote(vid)
            self.log(f"详情页解析: {play_url[:120]}...")

            play_url_decoded = html.unescape(play_url)
            parsed = urllib.parse.urlparse(play_url_decoded)
            params = urllib.parse.parse_qs(parsed.query)

            video_url = params.get('v', [''])[0]
            pic_url = params.get('b', [''])[0]

            # 从路径中提取加密标题
            path = urllib.parse.unquote(parsed.path)
            title_match = re.search(r'/([^/]+)\.html$', path)
            if title_match:
                title_encrypted = title_match.group(1).replace(' ', '')
                title = self._decrypt_title(title_encrypted)
            else:
                title = '未知标题'

            # 如果参数中没有封面，尝试从页面提取
            if not pic_url:
                rsp = self.fetch(play_url, headers=self.headers)
                if rsp and rsp.status_code == 200:
                    doc = self.html(rsp.text)
                    if doc:
                        for xpath in ['//meta[@property="og:image"]/@content',
                                      '//div[contains(@class,"video-cover")]//img/@src',
                                      '//div[contains(@class,"poster")]//img/@src',
                                      '//img[contains(@class,"cover")]/@src',
                                      '//img[@class="lazy"]/@data-original',
                                      '//img[@class="lazy"]/@data-src']:
                            pic_elem = doc.xpath(xpath)
                            if pic_elem:
                                pic_url = pic_elem[0]
                                break

            # 规范化封面URL
            pic_url = self._normalize_pic_url(pic_url)

            return {
                'list': [{
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic_url,
                    'vod_remarks': '',
                    'vod_year': '',
                    'vod_play_from': '直接播放',
                    'vod_play_url': f"第1集${play_url}"
                }]
            }
        except Exception as e:
            self.log(f"详情获取出错: {str(e)}")
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        """播放 - 从播放页URL直接提取m3u8"""
        try:
            self.log(f"获取播放链接: {id[:100]}...")

            # id 就是播放页URL（可能URL编码过）
            play_url = urllib.parse.unquote(id)

            # 直接从URL参数提取视频地址（先解码HTML实体）
            play_url_decoded = html.unescape(play_url)
            parsed = urllib.parse.urlparse(play_url_decoded)
            params = urllib.parse.parse_qs(parsed.query)
            video_url = params.get('v', [''])[0]

            if video_url:
                self.log(f"从URL参数提取到视频地址: {video_url[:100]}...")
                return {'parse': 0, 'playUrl': '', 'url': video_url}

            # 如果参数中没有，尝试访问页面提取
            self.log("URL参数无视频链接，尝试访问页面提取")
            rsp = self.fetch(play_url, headers=self.headers)
            if rsp and rsp.status_code == 200:
                # 从页面JS中提取
                video_match = re.search(r'["\']((?:https?:)?//[^"\']+\.m3u8[^"\']*)["\']', rsp.text, re.IGNORECASE)
                if video_match:
                    video_url = video_match.group(1)
                    if video_url.startswith('//'):
                        video_url = 'https:' + video_url
                    self.log(f"从页面提取到视频地址: {video_url[:100]}...")
                    return {'parse': 0, 'playUrl': '', 'url': video_url}

            self.log("无法提取视频，返回原始URL让播放器解析")
            return {'parse': 1, 'playUrl': '', 'url': play_url}
        except Exception as e:
            self.log(f"播放链接获取出错: {str(e)}")
            return {'parse': 1, 'playUrl': '', 'url': id}

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

if __name__ == '__main__':
    from base.spider import Spider as BaseSpider
    BaseSpider.register(Spider())
