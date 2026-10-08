# -*- coding: utf-8 -*-
"""
=================================================
  羞羞视频 TVBox / OK影视 / 影视仓 标准 Python 源。
=================================================

站点: https://1.xiu5790xiu.cc:8888 (hongtao 框架)
旧域名 1.xiu5556xiu.cc:8888 已失效 (变为地址发布页)

特点:
1. 支持 首页/分类/搜索/详情/播放 全流程。
2. 播放解析详情页 JS 内嵌的 m3u8 直链, sign 每次请求变化, 播放时重新拉取。
3. 站点 HTML 经 URL 编码包裹, 需 unquote 后再解析。
4. 兼容 FongMi/TV (T3) & WebHomeTV / PeekPro (T4)。
5. [v2] 域名失效自动修复: 检测到地址发布页时自动提取并切换到新域名。
"""

import sys
import json
import re
import base64
import html as html_module
import os
import time
import urllib3
from urllib.parse import quote, unquote, parse_qs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as rq

    class Spider:
        def fetch(self, url, headers=None, **kw):
            kw.pop('timeout', None)
            r = rq.get(url, headers=headers, timeout=15, verify=False, **kw)
            r.encoding = 'utf-8'
            return r


class Spider(Spider):
    """
    羞羞视频 Spider
    hongtao 框架, URL编码 HTML 解析
    """

    # 当前域名 (旧域名 xiu5556xiu 已失效, 切换到新域名)
    host = 'https://1.xiu5790xiu.cc:8888'

    # 旧域名 (已变为地址发布页, 用于自动检测和跳转)
    _legacy_host = 'https://1.xiu5556xiu.cc:8888'

    # 地址发布页域名 (旧域名会 301 跳转到这里, 但这里也只是发布页)
    _publish_host = 'https://1.xiu5408xiu.cc'

    # 已知的备用视频站域名 (从发布页提取, 带端口)
    _backup_domains = [
        'https://1.xiu5790xiu.cc:8888',
        'https://1.xiu5793xiu.cc:8888',
        'https://1.xiu5791xiu.cc:8888',
    ]

    # 域名缓存文件
    _cache_file = 'xiuxiu_domain.txt'

    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://1.xiu5790xiu.cc:8888/',
    }

    # 分类列表
    classes = [
        {'type_name': '大陆', 'type_id': '1'},
        {'type_name': '日本', 'type_id': '2'},
        {'type_name': '欧美', 'type_id': '3'},
        {'type_name': '动漫', 'type_id': '4'},
        {'type_name': '综艺', 'type_id': '5'},
        {'type_name': '国产传媒', 'type_id': '6'},
        {'type_name': '偷拍自拍', 'type_id': '7'},
        {'type_name': '日本无码', 'type_id': '10'},
        {'type_name': '中文字幕', 'type_id': '11'},
        {'type_name': '日本杂类', 'type_id': '12'},
        {'type_name': '欧美无码', 'type_id': '19'},
        {'type_name': '黑白专区', 'type_id': '20'},
        {'type_name': '少女动漫', 'type_id': '23'},
        {'type_name': '其他综艺', 'type_id': '28'},
        {'type_name': '成人游戏', 'type_id': '29'},
        {'type_name': '网曝黑料', 'type_id': '30'},
        {'type_name': 'AI脱衣', 'type_id': '31'},
        {'type_name': '绿帽偷情', 'type_id': '35'},
        {'type_name': 'JK萝莉', 'type_id': '36'},
        {'type_name': '强奷迷药', 'type_id': '37'},
        {'type_name': '网红主播', 'type_id': '38'},
        {'type_name': '吃瓜黑料', 'type_id': '39'},
    ]

    # ===================================================================
    #  基础方法
    # ===================================================================

    def getName(self):
        return '羞羞视频'

    def init(self, extend=''):
        if isinstance(extend, list):
            self.extend = ''
        else:
            self.extend = extend or ''
        self._resolve_domain()

    def _is_publish_page(self, text):
        """检测是否为地址发布页（非真实视频内容）"""
        if not text:
            return False
        decoded = unquote(text)
        # 真实视频页一定包含 view/ 链接和 vod-title, 优先判定为非发布页
        if 'view/' in decoded and 'vod-title' in decoded:
            return False
        # 发布页特征: gotoPath 函数 (真实视频页不会有)
        if 'gotoPath' in decoded:
            return True
        # 发布页特征: 标题含"发布页"
        if '发布页' in decoded:
            return True
        # 内容太短且没有视频结构
        if len(decoded) < 15000 and 'view/' not in decoded:
            return True
        return False

    def _resolve_domain(self):
        """启动时检测当前域名是否可用, 如果是发布页则自动切换"""
        # 尝试从缓存读取域名
        cached = ''
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r', encoding='utf-8') as f:
                    cached = f.read().strip()
        except Exception:
            pass

        if cached and cached != self._legacy_host and cached != self._publish_host:
            self.host = cached
            self.header['Referer'] = self.host + '/'
            return

        # 检测当前域名
        try:
            r = self.fetch(self.host + '/', headers=self.header, timeout=15)
            text = r.text if hasattr(r, 'text') else r.content.decode('utf-8', errors='ignore')
            if self._is_publish_page(text):
                print('[WARN] 当前域名为地址发布页, 正在探测可用域名...')
                new_domain = self._find_working_domain()
                if new_domain:
                    self.host = new_domain
                    self.header['Referer'] = self.host + '/'
                    self._save_cache()
                    print('[INFO] 已切换到: %s' % self.host)
            else:
                decoded = unquote(text)
                if 'view/' in decoded:
                    print('[INFO] 域名验证通过: %s' % self.host)
                    self._save_cache()
                else:
                    print('[WARN] 域名内容异常, 尝试备用域名...')
                    new_domain = self._find_working_domain()
                    if new_domain:
                        self.host = new_domain
                        self.header['Referer'] = self.host + '/'
                        self._save_cache()
                        print('[INFO] 已切换到: %s' % self.host)
        except Exception as e:
            print('[WARN] 域名验证异常: %s, 尝试备用域名...' % e)
            new_domain = self._find_working_domain()
            if new_domain:
                self.host = new_domain
                self.header['Referer'] = self.host + '/'
                self._save_cache()
                print('[INFO] 异常恢复, 已切换到: %s' % self.host)

    def _find_working_domain(self):
        """依次探测备用域名, 返回第一个有真实视频内容的域名"""
        for domain in self._backup_domains:
            if domain == self.host:
                continue
            try:
                r = self.fetch(domain + '/', headers=self.header, timeout=10)
                text = r.text if hasattr(r, 'text') else r.content.decode('utf-8', errors='ignore')
                if self._is_publish_page(text):
                    continue
                decoded = unquote(text)
                if 'view/' in decoded and 'vod-title' in decoded:
                    print('[INFO] 找到可用域名: %s' % domain)
                    return domain
            except Exception:
                continue
        # 尝试从发布页提取新域名
        new_domain = self._extract_domain_from_publish_page()
        if new_domain:
            return new_domain
        print('[WARN] 所有备用域名探测失败, 使用默认域名')
        return self._backup_domains[0]

    def _extract_domain_from_publish_page(self):
        """从地址发布页提取最新的视频站域名"""
        try:
            r = self.fetch(self._publish_host + '/', headers=self.header, timeout=10)
            text = r.text if hasattr(r, 'text') else r.content.decode('utf-8', errors='ignore')
            decoded = unquote(text)
            # 发布页中的 gotoPath('https://1.xiuXXXXxiu.cc:8888') 格式
            domains = re.findall(r"gotoPath\('(https?://[^']+:\d+)'", decoded)
            for d in domains:
                try:
                    r2 = self.fetch(d + '/', headers=self.header, timeout=10)
                    text2 = r2.text if hasattr(r2, 'text') else r2.content.decode('utf-8', errors='ignore')
                    decoded2 = unquote(text2)
                    if 'view/' in decoded2 and 'vod-title' in decoded2:
                        print('[INFO] 从发布页提取到新域名: %s' % d)
                        return d
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _save_cache(self):
        try:
            with open(self._cache_file, 'w', encoding='utf-8') as f:
                f.write(self.host)
        except Exception:
            pass

    def isVideoFormat(self, url):
        return any(x in url for x in ['.m3u8', '.mp4', '.flv', '.avi', '.mkv'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ===================================================================
    #  请求封装
    # ===================================================================

    def _fetch_html(self, path):
        """获取页面 HTML, 站点内容经 URL 编码, 需 unquote 还原

        v2: 增加发布页检测, 请求过程中发现域名变为发布页时自动切换
        """
        url = path if path.startswith('http') else self.host + path
        r = self.fetch(url, headers=self.header, timeout=15)
        text = r.text if hasattr(r, 'text') else r.content.decode('utf-8', errors='ignore')

        # v2: 检测是否为地址发布页 (域名失效)
        if self._is_publish_page(text):
            print('[WARN] 请求返回发布页, 正在切换域名...')
            new_domain = self._find_working_domain()
            if new_domain and new_domain != self.host:
                self.host = new_domain
                self.header['Referer'] = self.host + '/'
                self._save_cache()
                # 用新域名重新请求
                new_url = path if path.startswith('http') else self.host + path
                r = self.fetch(new_url, headers=self.header, timeout=15)
                text = r.text if hasattr(r, 'text') else r.content.decode('utf-8', errors='ignore')
                print('[INFO] 已切换到: %s' % self.host)

        # 站点将 HTML 内容 percent-encode 后包裹在 JS 函数调用中
        return unquote(text)

    # ===================================================================
    #  图片处理
    # ===================================================================

    def _wrap_pic(self, pic_url):
        """将图片 URL 通过 localProxy 代理, 确保 Referer 头正确发送"""
        if not pic_url:
            return ''
        pic_url = pic_url.strip()
        if pic_url.startswith(('"', "'")) and pic_url.endswith(('"', "'")):
            pic_url = pic_url[1:-1]
        if not pic_url:
            return ''
        if '127.0.0.1' in pic_url or 'proxy' in pic_url:
            return pic_url
        if pic_url.startswith('//'):
            pic_url = 'https:' + pic_url
        elif not pic_url.startswith(('http://', 'https://')):
            if pic_url.startswith('/'):
                pic_url = self.host + pic_url
            else:
                pic_url = self.host + '/' + pic_url
        # 通过 localProxy 代理图片, 确保发送 Referer 头避免403
        encoded = base64.urlsafe_b64encode(pic_url.encode('utf-8')).decode('utf-8')
        return 'http://127.0.0.1:9978/proxy?do=py&url=' + encoded

    # ===================================================================
    #  首页
    # ===================================================================

    def homeContent(self, filter):
        result = {'class': self.classes}
        if filter:
            result['filters'] = {}
        return result

    def homeVideoContent(self):
        try:
            html = self._fetch_html('/')
            vod_list = self._parse_cards(html)
            return {'list': vod_list[:30]}
        except Exception:
            return {'list': []}

    # ===================================================================
    #  分类内容
    # ===================================================================

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg or 1)
            url = '/category/%s/%d/' % (tid, pg)
            html = self._fetch_html(url)
            vod_list = self._parse_cards(html)

            # 检测下一页链接
            next_pg = pg + 1
            has_next = '/category/%s/%d/' % (tid, next_pg) in html

            if has_next:
                pagecount = next_pg
            else:
                pagecount = pg

            return {
                'page': pg,
                'pagecount': pagecount,
                'limit': len(vod_list),
                'total': pagecount * 12 if pagecount < 999 else 99999,
                'list': vod_list,
            }
        except Exception:
            return {'page': pg, 'pagecount': 1, 'limit': 12, 'total': 0, 'list': []}

    # ===================================================================
    #  详情页
    # ===================================================================

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            html = self._fetch_html('/view/%s' % vod_id)

            # 标题
            vod_name = ''
            title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if title_m:
                vod_name = html_module.unescape(title_m.group(1).strip())

            # 封面图 (支持 data-original / data-src)
            vod_pic = ''
            pic_m = re.search(r'data-(?:original|src)="([^"]+)"', html)
            if pic_m:
                vod_pic = pic_m.group(1)
            vod_pic = self._wrap_pic(vod_pic)

            # 年份 (时间戳)
            vod_year = ''
            time_m = re.search(r'formatDateString\((\d+)\)', html)
            if time_m:
                import time
                ts = int(time_m.group(1))
                vod_year = time.strftime('%Y-%m-%d', time.localtime(ts))

            # 人气
            vod_remarks = ''
            pop_m = re.search(r'\u4eba\u6c23:\s*(\d+)', html)
            if pop_m:
                vod_remarks = '\u4eba\u6c14:' + pop_m.group(1)

            # 播放: 存视频 ID, playerContent 时重新拉取 m3u8 (sign 每次变化)
            play_url = '\u64ad\u653e$%s' % vod_id

            vod = {
                'vod_id': vod_id,
                'vod_name': vod_name,
                'vod_pic': vod_pic,
                'type_name': '\u7f9e\u7f9e\u89c6\u9891',
                'vod_year': vod_year,
                'vod_area': '',
                'vod_actor': '',
                'vod_director': '',
                'vod_content': '',
                'vod_remarks': vod_remarks,
                'vod_play_from': '\u7f9e\u7f9e\u89c6\u9891',
                'vod_play_url': play_url,
            }
            return {'list': [vod]}
        except Exception:
            return {'list': []}

    # ===================================================================
    #  搜索
    # ===================================================================

    def searchContent(self, key, quick, pg=1):
        try:
            pg = int(pg or 1)
            encoded_key = quote(key)
            search_path = '/search/%s/%d/' % (encoded_key, pg)
            html = self._fetch_html(search_path)
            vod_list = self._parse_cards(html)
            return {
                'list': vod_list[:30],
                'page': pg,
            }
        except Exception:
            return {'list': [], 'page': 1}

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    # ===================================================================
    #  播放
    # ===================================================================

    def playerContent(self, flag, id, vipFlags):
        try:
            play_id = str(id or '')
            # 解析播放 ID (即视频 hash)
            if '$' in play_id:
                play_id = play_id.split('$')[-1]

            # 访问详情页获取最新 m3u8 (sign 每次请求变化)
            html = self._fetch_html('/view/%s' % play_id)

            # 从 JS 提取: var url = "https://....m3u8?sign=..."
            m3u8_m = re.search(r'var\s+url\s*=\s*"(https?://[^"]+\.m3u8[^"]*)"', html)
            if m3u8_m:
                return {
                    'parse': 0,
                    'url': m3u8_m.group(1),
                    'header': {
                        'User-Agent': self.header['User-Agent'],
                        'Referer': self.host + '/',
                    },
                }

            # 后备: 直接搜索页面中所有 m3u8 URL
            m3u8_m2 = re.search(r'"(https?://[^"]+\.m3u8[^"]*)"', html)
            if m3u8_m2:
                return {
                    'parse': 0,
                    'url': m3u8_m2.group(1),
                    'header': {
                        'User-Agent': self.header['User-Agent'],
                        'Referer': self.host + '/',
                    },
                }

            # 解析失败
            return {
                'parse': 1,
                'url': self.host + '/view/%s' % play_id,
                'header': {'User-Agent': self.header['User-Agent']},
            }
        except Exception:
            return {}

    # ===================================================================
    #  本地代理 (图片代理)
    # ===================================================================

    def localProxy(self, param):
        """本地代理: 处理图片加载, .dat文件为base64编码的图片"""
        try:
            if isinstance(param, str):
                param_dict = parse_qs(param)
            else:
                param_dict = param

            url = param_dict.get('url', '')
            if isinstance(url, list):
                url = url[0] if url else ''

            if not url:
                return [404, 'text/plain', b'', {}]

            # base64 padding fix
            url += '=' * (-len(url) % 4)
            try:
                url = base64.urlsafe_b64decode(url).decode('utf-8')
            except Exception:
                try:
                    url = base64.b64decode(url).decode('utf-8')
                except Exception:
                    pass

            if not url:
                return [404, 'text/plain', b'', {}]

            headers = {
                'User-Agent': self.header['User-Agent'],
                'Referer': self.host + '/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            }
            r = self.fetch(url, headers=headers, timeout=15)
            content = r.content if hasattr(r, 'content') else r.text.encode('utf-8')

            if not content or len(content) < 10:
                return [404, 'text/plain', b'', {}]

            # .dat文件是base64编码的图片, 尝试解码后返回真实图片字节
            try:
                decoded = base64.b64decode(content)
                if len(decoded) > 10:
                    mime = self._detect_mime(decoded)
                    if mime:
                        return [200, mime, decoded, {'Content-Type': mime, 'Content-Length': str(len(decoded))}]
            except Exception:
                pass

            # 非base64, 直接返回原始字节
            mime = self._detect_mime(content)
            if not mime:
                mime = 'image/jpeg'
            return [200, mime, content, {'Content-Type': mime, 'Content-Length': str(len(content))}]
        except Exception:
            pass
        return [404, 'text/plain', b'', {}]

    def _detect_mime(self, data):
        """从字节头检测图片格式"""
        if not data or len(data) < 4:
            return ''
        if data[:4] == b'\x89PNG':
            return 'image/png'
        if data[:2] == b'\xff\xd8':
            return 'image/jpeg'
        if data[:4] == b'RIFF':
            return 'image/webp'
        if data[:4] == b'GIF8':
            return 'image/gif'
        return ''

    # ===================================================================
    #  卡片解析
    # ===================================================================

    def _parse_cards(self, html):
        """解析视频卡片列表 - hongtao 框架结构

        每个 vod-item 包含:
        - href="/view/{hash}" 链接 (图片+标题各一个)
        - data-original="图片URL"
        - class="vod-title" 标题 (HTML实体编码)
        - secondsToHMS(秒数) 时长
        """
        vod_list = []
        seen = set()

        # 提取所有 /view/{hash} 链接 (每个视频出现2次: 图片+标题)
        view_ids = re.findall(r'href="/view/([a-f0-9]+)"', html)
        unique_ids = list(dict.fromkeys(view_ids))

        # 提取所有图片 (支持 data-original / data-src, 不限 https)
        images = re.findall(r'data-(?:original|src)="([^"]+)"', html)

        # 提取所有标题 (HTML实体编码 &#xXXXX;)
        titles = re.findall(r'class="vod-title"[^>]*>([^<]+)', html)

        # 提取所有时长
        durations = re.findall(r'secondsToHMS\((\d+)\)', html)

        for i, vid in enumerate(unique_ids):
            if vid in seen:
                continue
            seen.add(vid)

            # 标题
            name = ''
            if i < len(titles):
                name = html_module.unescape(titles[i].strip())

            # 图片
            pic_url = ''
            if i < len(images):
                pic_url = images[i]
            pic_url = self._wrap_pic(pic_url)

            # 时长格式化
            remark = ''
            if i < len(durations):
                seconds = int(durations[i])
                if seconds > 0:
                    h, rem = divmod(seconds, 3600)
                    m, s = divmod(rem, 60)
                    if h > 0:
                        remark = '%02d:%02d:%02d' % (h, m, s)
                    else:
                        remark = '%02d:%02d' % (m, s)

            vod_list.append({
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic_url,
                'vod_remarks': remark,
            })

        return vod_list


def test():
    print('=' * 70)
    print('羞羞视频 TVBox 爬虫 - 联网测试')
    print('=' * 70)
    spider = Spider()
    spider.init()

    print('\n--- [1/7] homeContent ---')
    home = spider.homeContent(filter=True)
    print('分类: %d 个' % len(home.get('class', [])))
    for c in home.get('class', [])[:5]:
        print('  %s: %s' % (c['type_id'], c['type_name']))

    print('\n--- [2/7] homeVideoContent ---')
    hv = spider.homeVideoContent()
    print('首页视频: %d 个' % len(hv.get('list', [])))
    for v in hv.get('list', [])[:3]:
        print('  [%s] %s | 备注:%s' % (v['vod_id'], v['vod_name'][:40], v['vod_remarks']))

    print('\n--- [3/7] categoryContent (大陆) ---')
    cat = spider.categoryContent('1', 1, False, {})
    print('大陆: %d 个, 总页: %s' % (len(cat.get('list', [])), cat.get('pagecount')))
    for v in cat.get('list', [])[:3]:
        print('  [%s] %s | 备注:%s' % (v['vod_id'], v['vod_name'][:40], v['vod_remarks']))

    print('\n--- [4/7] categoryContent (日本) ---')
    cat2 = spider.categoryContent('2', 1, False, {})
    print('日本: %d 个, 总页: %s' % (len(cat2.get('list', [])), cat2.get('pagecount')))
    for v in cat2.get('list', [])[:3]:
        print('  [%s] %s | 备注:%s' % (v['vod_id'], v['vod_name'][:40], v['vod_remarks']))

    print('\n--- [5/7] detailContent + 播放测试 ---')
    test_ids = []
    for vlist in [hv.get('list', []), cat.get('list', [])]:
        for v in vlist:
            if v['vod_id'] not in test_ids:
                test_ids.append(v['vod_id'])
            if len(test_ids) >= 3:
                break
        if len(test_ids) >= 3:
            break

    for vid in test_ids[:3]:
        detail = spider.detailContent([vid])
        if not detail.get('list'):
            print('  [FAIL] %s: 详情为空' % vid)
            continue
        d = detail['list'][0]
        print('  [%s] %s' % (vid, d['vod_name'][:50]))
        play = spider.playerContent('羞羞视频', vid, [])
        if play.get('url'):
            print('    播放: %s...' % play['url'][:80])
        else:
            print('    [FAIL] 播放解析失败')

    print('\n--- [6/7] searchContent ---')
    search = spider.searchContent('护士', False, 1)
    print('搜索: %d 个结果' % len(search.get('list', [])))
    for v in search.get('list', [])[:3]:
        print('  [%s] %s' % (v['vod_id'], v['vod_name'][:40]))

    print('\n--- [7/7] 翻页测试 ---')
    cat_pg2 = spider.categoryContent('1', 2, False, {})
    print('大陆第2页: %d 个, 总页: %s' % (len(cat_pg2.get('list', [])), cat_pg2.get('pagecount')))

    print('\n' + '=' * 70)
    print('测试完成')
    print('=' * 70)


if __name__ == '__main__':
    test()
