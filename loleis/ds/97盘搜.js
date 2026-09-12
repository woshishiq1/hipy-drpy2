/*
@header({
  searchable: 1,
  filterable: 0,
  quickSearch: 1,
  title: '网盘搜索[搜]',
  lang: 'ds'
})
*/
import '../lib/htmlParser.js';
import { Quark, Baidu, UC } from "../lib/pans.js";

// ==================== 全局变量 ====================
let siteName = '97网盘搜索', siteKey = '', siteType = 0;
let baseUrl = '';
let DEBUG = 0;  // 默认关闭调试打印

// ==================== 开关配置 （1=开启，0=关闭）====================
let quarkInfinite = 0;      // 夸克网盘无限画质开关 (1=开启无限画质, 0=关闭)
let quarkOrig = 1;          // 夸克网盘原画开关 (1=开启原画, 0=关闭)
let quarkTransfer = 1;      // 夸克网盘转存开关 (1=开启转存获取画质, 0=关闭)
let enableProxy = 0;        // 全局代理开关 (1=开启代理, 0=关闭)
// ================================================

let UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36";

let headers = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
};

let proxyurl = 'http://127.0.0.1:2525/proxy?url=';
let downThreads = '20';

// 网盘图标映射
const diskIconMap = [
    { img: 'https://cnb.cool/zhyadc/YsBox/-/git/raw/main/images/icon_cookie/夸克.png', type: '夸克网盘', pan_type: 2 },
    { img: 'https://cnb.cool/zhyadc/YsBox/-/git/raw/main/images/icon_cookie/百度.png', type: '百度网盘', pan_type: 1 }
];
let defaultImg = `https://cnb.cool/zhyadc/YsBox/-/git/raw/main/images/icon_cookie/网盘搜索.png`;

// API基础地址
let host = 'https://pansoo.cn';

// Cookie缓存
let cachedCookie = null;
let cookieCacheTime = 0;
let COOKIE_CACHE_DURATION = 300000;

// 搜索最大翻页数
let maxPages = 5;

// ==================== 安全JSON解析 ====================
function safeJSONParse(str, defaultValue = {}) {
    if (!str || typeof str === 'object') return str || defaultValue;
    try {
        return JSON.parse(str);
    } catch {
        return defaultValue;
    }
}

// ==================== 统一请求函数 ====================
async function request(url, options = {}) {
    const reqHeaders = { ...headers, ...options.headers };
    let postType = reqHeaders['Content-Type']?.includes('json') ? 'json' :
        reqHeaders['Content-Type']?.includes('form') ? 'form' : '';

    try {
        const response = await req(url, {
            method: options.method || 'GET',
            headers: reqHeaders,
            data: options.data,
            postType: postType,
            timeout: options.timeout || 15000
        });
        return response?.content || response?.data || response;
    } catch {
        return null;
    }
}

// ==================== 画质映射 ====================
function mapResolution(res) {
    const map = {
        'low': '流畅', 'normal': '标清', 'high': '高清', 'super': '超清',
        '4k': '4K', '2k': '2K', 'hdr': 'HDR', 'dolby_vision': 'HDR',
        'M3U8_AUTO_480': '480P', 'M3U8_AUTO_720': '720P', 'M3U8_AUTO_1080': '1080P',
        'M3U8_AUTO_2K': '2K', 'M3U8_AUTO_4K': '4K'
    };
    return map[res] || res;
}

// ==================== 远程配置加载 ====================
async function loadRemoteConfig(cfgUrl) {
    try {
        console.log(`[${siteName}] 请求远程配置: ${cfgUrl}`);
        const res = await request(cfgUrl, { timeout: 10000 });
        if (res) {
            const remoteCfg = safeJSONParse(res);
            // 设置Cookie
            if (remoteCfg.quark_cookie?.length > 10) Quark.cookie = remoteCfg.quark_cookie;
            if (remoteCfg.baidu_cookie?.length > 10) Baidu.cookie = remoteCfg.baidu_cookie;
            if (remoteCfg.uc_cookie?.length > 10) UC.cookie = remoteCfg.uc_cookie;
            if (remoteCfg.uc_token?.length > 10) UC.token = remoteCfg.uc_token;
            // 可选：其他配置
            if (remoteCfg.threads) downThreads = remoteCfg.threads;
            if (remoteCfg.enableProxy !== undefined) enableProxy = remoteCfg.enableProxy;
            if (remoteCfg.infinite !== undefined) quarkInfinite = remoteCfg.infinite;
            if (remoteCfg.quark_original !== undefined) quarkOrig = remoteCfg.quark_original;
            if (remoteCfg.quark_transfer !== undefined) quarkTransfer = remoteCfg.quark_transfer;
            console.log(`[${siteName}] 远程配置加载成功`);
            return true;
        }
    } catch (e) {
        console.log(`[${siteName}] 远程配置加载失败: ${e.message}`);
    }
    return false;
}

// ==================== 主程序函数 ====================

async function init(cfg) {
    siteName = cfg.skey?.split('_')[1] || cfg.skey || siteName;
    siteKey = cfg.skey;
    siteType = cfg.stype;
    
    let ext = cfg.ext || cfg;
    if (typeof ext === 'string') ext = decodeURIComponent(ext);
    
    if (typeof ext === 'string') {
        await loadRemoteConfig(ext);
    }
    host = host.endsWith('/') ? host : host + '/';
    
}

function home() {
    return JSON.stringify({
        class: [
            { type_id: 'search', type_name: '这是一个搜索源' }
        ],
    });
}

async function homeVod() {
    return await category('search', 1, null, null);
}

async function category(tid, pg, filter, ext) {
    if (tid === 'search') {
        return JSON.stringify({
            list: [{
                vod_id: 'only_search',
                vod_name: '🔍 网盘资源搜索',
                vod_pic: defaultImg,
            }]
        });
    } 
    return JSON.stringify({ list: [] });
}

/**
 * 详情页 - 获取资源分享链接并解析
 */
async function detail(id) {
    // 解码并解析 JSON
    let detailObj;
    try {
        let decoded = decodeURIComponent(id);
        detailObj = safeJSONParse(decoded);
    } catch (e) {
        // 兼容旧格式（如果还有用竖线分隔的旧数据）
        let parts = id.split('|');
        detailObj = {
            rid: parts[0],
            name: parts[1] || '网盘资源',
            type: parts[2] || '2'
        };
    }
    
    let resourceId = detailObj.rid;
    let vod_name = detailObj.name;
    let panType = detailObj.type;
    
    log('详情', `${resourceId} - ${vod_name} - panType:${panType}`);
    
    let play_from = [];
    let play_url = [];
    let play_pic = [];
    
    let cookie = await getDynamicCookie();
    let apiHeaders = {
        "User-Agent": headers["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Referer": `https://pansoo.cn/`
    };
    if (cookie) apiHeaders["Cookie"] = cookie;
    
    let checkUrl = `${host}/api/check_resource_status?resource_id=${resourceId}&pan_type=${panType}`;
    let response = await request(checkUrl, { headers: apiHeaders, timeout: 15000 });
    
    let shareUrl = null;
    if (response) {
        try {
            let data = safeJSONParse(response);
            if (data.share_url) shareUrl = data.share_url;
        } catch (e) {}
    }
    
    if (shareUrl && shareUrl.startsWith('http')) {
        let counters = { '夸克': 1, '百度': 1, '优汐': 1 };
        
        if (/pan.quark.cn/.test(shareUrl)) {
            let shareData = Quark.getShareData(shareUrl);
            if (shareData) {
                let files = await Quark.getFilesByShareUrl(shareData);
                if (files?.length) {
                    let url = files.map(v => {
                        let size = v.size ? ` 【${formatSize(v.size)}】` : '';
                        return `${v.file_name}${size}$${[shareData.shareId, v.stoken, v.fid, v.share_fid_token, v.pdir_fid || '', v.subtitle?.fid || '', v.subtitle?.share_fid_token || ''].join('*')}`;
                    }).join('#');
                    let imgs = files.map(v => v.thumbnail || v.thumb || v.pic || '').join('#');
                    play_from.push(`夸克#${counters['夸克']++}`);
                    play_url.push(url);
                    play_pic.push(imgs);
                }
            }
        } else if (/pan.baidu.com/.test(shareUrl)) {
            let shareData = Baidu.getShareData(shareUrl);
            if (shareData) {
                let files = await Baidu.getFilesByShareUrl(shareData);
                if (files?.length) {
                    let url = files.map(v => {
                        let size = v.size ? ` 【${formatSize(v.size)}】` : '';
                        let info = { surl: shareData.surl, pwd: shareData.pwd || '' };
                        return `${v.name}${size}$${[v.path, v.uk, v.shareid, v.fsid, JSON.stringify(info)].join('*')}`;
                    }).join('#');
                    let imgs = files.map(v => v.thumbnail || v.thumb || v.pic || '').join('#');
                    play_from.push(`百度#${counters['百度']++}`);
                    play_url.push(url);
                    play_pic.push(imgs);
                }
            }
        } else if (/drive.uc.cn|\.uc/.test(shareUrl)) {
            let shareData = UC.getShareData(shareUrl);
            if (shareData) {
                let files = await UC.getFilesByShareUrl(shareData);
                if (files?.length) {
                    let url = files.map(v => {
                        let size = v.size ? ` 【${formatSize(v.size)}】` : '';
                        return `${v.file_name}${size}$${[shareData.shareId, v.stoken, v.fid, v.share_fid_token, v.subtitle?.fid || '', v.subtitle?.share_fid_token || ''].join('*')}`;
                    }).join('#');
                    let imgs = files.map(v => v.thumbnail || v.thumb || v.pic || '').join('#');
                    play_from.push(`优汐#${counters['优汐']++}`);
                    play_url.push(url);
                    play_pic.push(imgs);
                }
            }
        }
    }
    
    if (play_from.length === 0) {
        play_from.push('提示');
        play_url.push(shareUrl ? `分享链接: ${shareUrl}` : `获取分享链接失败，资源ID: ${resourceId}`);
        play_pic.push('');
    }
    
    // 构建简介内容，加入网盘链接
    let contentParts = [`资源ID: ${resourceId}`, `网盘类型: ${getPanTypeName(parseInt(panType))}`];
    if (shareUrl) {
        contentParts.push(`网盘链接: ${shareUrl}`);
    }
    let vod_content = contentParts.join(' | ');
    
    let vod = {
        vod_id: id,
        vod_name: vod_name,
        vod_pic: '',
        vod_content: vod_content,
        vod_remarks: play_from.length > 0 ? (play_from[0].split('#')[0] + '可播放') : '解析失败',
        vod_play_from: play_from.join('$$$'),
        vod_play_url: play_url.join('$$$'),
        vod_play_pic: play_pic.join('$$$'),
        vod_play_pic_ratio: 1.0
    };
    
    return JSON.stringify({ list: [vod] });
}

/**
 * 搜索 - 批量并发请求 + 关键词匹配过滤
 */
async function search(wd, quick, pg) {
    let page = pg || 1;
    log('搜索', `${wd} - page${page}`);
    
    let cookie = await getDynamicCookie();
    let searchHeaders = {
        "User-Agent": headers["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Referer": `https://pansoo.cn/search?q=${encodeURIComponent(wd)}&type=online`
    };
    if (cookie) searchHeaders["Cookie"] = cookie;
    
    // 构建批量请求
    let urls = [];
    for (let p = page; p < page + maxPages; p++) {
        urls.push({
            url: `${host}/api/search?keyword=${encodeURIComponent(wd)}&pan_types=1,2&page=${p}&limit=30&file_type=video`,
            options: { headers: searchHeaders, timeout: 15000 }
        });
    }
    
    let results = await batchFetch(urls);
    let allList = [];
    
    for (let content of results) {
        if (!content) continue;
        try {
            let data = safeJSONParse(content);
            if (data.status === 'success' && data.results) {
                for (let resource of data.results) {
                    let title = resource.title;
                    if (!title || title.length < 2) continue;
                    
                    let panType = resource.pan_type;
                    // 如果 pan_type 无效，默认使用 2（夸克网盘）
                    if (panType === undefined || panType === null || panType === '') {
                        panType = 2;
                    }
                    
                    // 使用 JSON 编码构建 detailId，避免标题中的特殊字符（如 |）导致解析错误
                    let detailObj = {
                        rid: resource.resource_id,
                        name: title,
                        type: panType
                    };
                    let detailId = encodeURIComponent(JSON.stringify(detailObj));
                    
                    allList.push({
                        vod_id: detailId,
                        vod_name: title,
                        vod_pic: getDiskIconByPanType(panType),
                        vod_content: resource.text_content || '',
                        vod_remarks: `${getPanTypeName(panType)}${resource.file_size && resource.file_size !== '未知大小' ? ' | ' + resource.file_size : ''}`
                    });
                }
            }
        } catch (e) {}
    }
    
    // 关键词过滤
    let filteredList = allList.filter(item => new RegExp(wd, "i").test(item.vod_name));
    log('搜索结果', `${filteredList.length}/${allList.length}`);
    
    return JSON.stringify({
        page: page,
        pagecount: maxPages,
        limit: filteredList.length,
        total: filteredList.length,
        list: filteredList
    });
}

/**
 * 播放 
 */
async function play(flag, id, flags) {
    let ids = id.split('*');
    let urls = [];
    
    const addUrl = (name, u) => { 
        if (u) urls.push(name, proxyUrl(u) + `&thread=${downThreads}`); 
    };
    
    // 夸克网盘
    if (flag.startsWith('夸克') && ids.length >= 4) {
        let [shareId, stoken, fid, share_fid_token] = ids;
        let header = { 
            'User-Agent': headers['User-Agent'], 
            'origin': 'https://pan.quark.cn', 
            'referer': 'https://pan.quark.cn/', 
            'Cookie': Quark.cookie 
        };
        
        // 无限画质（免转存直链）
        if (quarkInfinite == 1) {
            const tokenUrls = await Quark.getUrl(shareId, stoken, fid, share_fid_token);
            tokenUrls?.forEach(item => { if (item?.url) addUrl("无限" + (item.name || ''), item.url); });
        }
        
        // 转存逻辑（原画和多分辨率）
        let shouldTransfer = quarkTransfer;
        if (quarkInfinite != 1 && quarkOrig != 1 && quarkTransfer != 1) {
            shouldTransfer = 1;
        }
        
        if (shouldTransfer == 1) {
            // 原画
            if (quarkOrig == 1) {
                let down = await Quark.getDownload(shareId, stoken, fid, share_fid_token, true);
                if (down && down.error) {
                    const errorMsg = down.message || '未知错误';
                    return JSON.stringify({ parse: 0, msg: `夸克: ${errorMsg}`, header: header });
                }
                if (down?.download_url) addUrl("原画", down.download_url);
            }
            
            // 转码画质
            let transcoding = await Quark.getLiveTranscoding(shareId, stoken, fid, share_fid_token);
            if (transcoding?.length) {
                transcoding.filter(t => t.accessable).forEach(t => {
                    if (t?.video_info?.url) {
                        addUrl(mapResolution(t.resolution), t.video_info.url);
                    }
                });
            }
        }
        
        if (urls.length) {
            return JSON.stringify({ parse: 0, url: urls, header: header });
        }
    }
    
    // 百度网盘
    if (flag.startsWith('百度') && ids.length >= 5) {
        let [path, uk, shareid, fsid, shareDataStr] = ids;
        let shareData = safeJSONParse(shareDataStr);
        
        let original = await Baidu.getAppShareUrl(path, uk, shareid, fsid, shareData);
        if (original && !original.error) {
            addUrl("原画", original);
        } else {
            const errorMsg = original?.message || '获取链接失败，请检查Cookie是否有效';
            return JSON.stringify({ parse: 0, msg: `百度: ${errorMsg}`, header: headers });
        }
        
        if (urls.length) {
            return JSON.stringify({ 
                parse: 0, 
                url: urls, 
                header: { "User-Agent": 'netdisk;P2SP;2.2.91.136;android-android;' } 
            });
        }
    }
    
    // 优汐网盘
    if (flag.startsWith('优汐') && ids.length >= 4) {
        let [shareId, stoken, fid, share_fid_token] = ids;
        
        let down = await UC.getDownload(shareId, stoken, fid, share_fid_token, true);
        if (down && down.error) {
            const errorMsg = down.message || '未知错误';
            return JSON.stringify({ parse: 0, msg: `优汐: ${errorMsg}`, header: headers });
        }
        if (down?.length) {
            down.forEach(item => { if (item?.url) addUrl(mapResolution(item.name), item.url); });
        }
        
        if (urls.length) {
            return JSON.stringify({ parse: 0, url: urls });
        }
    }
    
    // 直接链接
    if (id.startsWith('http')) {
        urls.push('原画', proxyUrl(id) + `&thread=${downThreads}`);
        return JSON.stringify({ parse: 0, url: urls });
    }
    return JSON.stringify({ parse: 0, msg: `解析分享链接失败, 分享链接可能已失效`, header: headers });
    
}

// ==================== Cookie获取函数 ====================

async function getDynamicCookie() {
    let now = Date.now();
    if (cachedCookie && cookieCacheTime > now) return cachedCookie;
    
    try {
        // 使用 req 直接请求，以便获取响应头
        const response = await req(host, { 
            method: 'GET',
            headers: { "User-Agent": headers["User-Agent"] }, 
            timeout: 10000 
        });
        
        let cookie = null;
        if (response && response.headers) {
            let setCookie = response.headers['set-cookie'] || response.headers['Set-Cookie'];
            if (setCookie) {
                // 处理可能是数组的情况
                let cookieStr = Array.isArray(setCookie) ? setCookie.join('; ') : setCookie;
                let match = cookieStr.match(/(__cf_bm=[^;]+)/);
                if (match) cookie = match[1];
            }
        }
        if (cookie) {
            cachedCookie = cookie;
            cookieCacheTime = now + COOKIE_CACHE_DURATION;
        }
        return cookie;
    } catch (e) {
        return null;
    }
}

// ==================== 工具函数 ====================

function log(tag, msg) {
    if (DEBUG) console.log(`【${siteName}-${tag}】 ${msg}`);
}

function getDiskIconByPanType(panType) {
    let matched = diskIconMap.find(item => item.pan_type === parseInt(panType));
    return matched ? matched.img : defaultImg;
}

function getPanTypeName(panType) {
    let matched = diskIconMap.find(item => item.pan_type === parseInt(panType));
    return matched ? matched.type : '网盘资源';
}

function formatSize(bytes) {
    let size = typeof bytes === 'string' ? parseInt(bytes, 10) : bytes;
    if (!size || isNaN(size) || size <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
    return size.toFixed(2) + ' ' + units[i];
}

function proxyUrl(url) {
    if (!url) return '';
    if (enableProxy && proxyurl) return proxyurl + encodeURIComponent(url);
    return url;
}

async function proxy(params) {
    let url = params.url;
    return [302, '', '', { 'Location': url }];
}

// ==================== 导出 ====================
export function __jsEvalReturn() {
    return { init, home, homeVod, category, detail, play, search, proxy };
}