import '../lib/htmlParser.js';
import { Quark, Baidu, UC } from "../lib/pans.js";

// 分类排除关键词
const class_exclude = ['115', '123', '天移', '留言', '关于', '原盘'];

/**
 * 网盘站点域名配置
 * 每个站点对应一组可用域名，用于并发检测
 */
const DOM_CFG = {
    "玩偶": [
        "https://wogg.xxooo.cf",
        "https://woggpan.333232.xyz",
        "https://wogg.heshiheng.top",
        "https://www.wogg.one",
        "https://www.wogg.lol"
    ],
    "至臻": [
        "https://mihdr.top",
        "https://xiaomi666.fun",
        "https://zhizhen8.click",
        "https://www.zhizhen8.click"
    ],
    "蜡笔": [
        "http://xiaocge.fun",
        "http://feimo.fun",
        "https://feimao666.fun",
        "http://feimao888.fun",
        "http://www.labi88.sbs",
        "http://fmao.site",
        "http://fmao.shop",
        "http://xiaocgege.shop"
    ],
    "木偶": [
        "http://123.666291.xyz",
        "https://mogg.5568.eu.org",
        "https://mo.666291.xyz",
        "http://666.666291.xyz",
        "https://mo.muouso.fun"
    ],
    "二小": [
        "https://www.2xiaozhan.top",
        "https://erxiaofn.click",
        "https://www.xhww.net"
    ],
    "多多": [
        "https://tv.yydsys.top",
        "https://tv.yydsys.cc"
    ],
    "虎斑": [
        "http://103.45.162.207:20720",
        "http://xsayang.fun:12512"
    ],
    "欧歌": [
        "https://woog.xn--dkw.xn--6qq986b3xl",
        "https://woog.nxog.eu.org"
    ],
    "闪电": [
        "https://sd.sduc.site"
    ],
    "快映": [
        "http://xsayang.fun:12512"
    ]
};

// 全局变量
let host = '';                                    // 当前可用域名
let ext = '';                                     // 扩展配置
let apitype = '';                                 // API类型: vodshow 或 index.php
let siteName = '网盘';                            // 站点名称
let UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (Chrome/120.0.0.0 Safari/537.36";
let line_order = ['百度', '夸克', '优汐'];        // 线路排序
let downThreads = '32';                           // 下载线程数

let cachedClasses = [];
let cachedFilters = {};

// 站点配置存储对象
const siteConfigs = {};

// ==================== 开关配置 （1=开启，0=关闭）====================
let quarkInfinite = 0;      // 夸克网盘无限画质开关 (1=开启无限画质, 0=关闭)
let quarkOrig = 1;          // 夸克网盘原画开关 (1=开启原画, 0=关闭)
let quarkTransfer = 1;      // 夸克网盘转存开关 (1=开启转存获取画质, 0=关闭)
let enableProxy = 0;        // 全局代理开关 (1=开启代理, 0=关闭)
// ================================================

// 代理配置
let enable_image = 1;                              // 图片代理开关
let proxyimg = 'https://wsrv.nl/?url=';           // 图片代理
let proxyurl = 'http://127.0.0.1:2525/proxy?url='; // 播放代理

const CACHE_NS = 'wanpan_cache';
const CLASS_CACHE_KEY = 'class_data';

// 请求头配置
const headers = {
    'User-Agent': UA,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
};

/**
 * 安全JSON解析
 */
function safeJSONParse(str, defaultValue = {}) {
    if (!str || typeof str === 'object') return str || defaultValue;
    try {
        return JSON.parse(str);
    } catch {
        return defaultValue;
    }
}

/**
 * 统一请求函数
 * @param {string} url - 请求地址
 * @param {object} options - 请求选项
 * @returns {Promise<string|null>} 响应内容
 */
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
    } catch (error) {
        console.error(`Request failed: ${url}`, error);
        return null;
    }
}

/**
 * 映射分辨率名称
 * @param {string} res - 原始分辨率标识
 * @returns {string} 中文分辨率名称
 */
function mapResolution(res) {
    const map = {
        'low': '流畅', 'normal': '标清', 'high': '高清', 'super': '超清',
        '4k': '4K', '2k': '2K', 'hdr': 'HDR', 'dolby_vision': 'HDR',
        'M3U8_AUTO_480': '480P', 'M3U8_AUTO_720': '720P', 'M3U8_AUTO_1080': '1080P',
        'M3U8_AUTO_2K': '2K', 'M3U8_AUTO_4K': '4K'
    };
    return map[res] || res;
}

/**
 * 判断分类是否被排除
 * @param {string} className - 分类名称
 * @returns {boolean} 是否被排除
 */
function isClassExcluded(className) {
    if (!className) return false;
    return class_exclude.some(keyword => className.toLowerCase().includes(keyword));
}

/**
 * 初始化函数
 * 加载配置、检测可用域名、获取分类和筛选器
 */
async function init(cfg) {
    ext = cfg.ext || cfg;
    
    // 获取站点名称
    siteName = (cfg.skey?.split('_')[1] || cfg.skey) || (cfg.key?.split('_')[1] || cfg.key) || '网盘';
    
    let quarkCookie = "";
    let baiduCookie = "";
    let ucCookie = "";
    let ucToken = "";
    let selectedConfig = "至臻";
    let siteOrder = "";
    let customLineOrder = null;
    let customThreads = null;
    let customQuarkOriginal = null;
    let customQuarkInfinite = null;
    let customQuarkTransfer = null;
    let customEnableProxy = null;
    let customEnableImage = null;
    let customProxyUrl = null;
    let customProxyImg = null;
    
    // 解析配置参数
    if (cfg) {
        if (typeof ext === 'object') {
            quarkCookie = cfg.quark_cookie || "";
            baiduCookie = cfg.baidu_cookie || "";
            ucCookie = cfg.uc_cookie || "";
            ucToken = cfg.uc_token || "";
            customLineOrder = cfg.line_order || null;
            customThreads = cfg.threads || null; 
            customQuarkOriginal = cfg.quark_original !== undefined ? cfg.quark_original : null;
            customQuarkInfinite = cfg.quark_infinite !== undefined ? cfg.quark_infinite : null;
            customQuarkTransfer = cfg.quark_transfer !== undefined ? cfg.quark_transfer : null;
            customEnableProxy = cfg.enable_proxy !== undefined ? cfg.enable_proxy : null;
            customEnableImage = cfg.enable_image !== undefined ? cfg.enable_image : null;
            customProxyUrl = cfg.proxy_url || null;
            customProxyImg = cfg.proxy_img || null;
        } else if (typeof ext === 'string') {
            const [url, order] = ext.split('$');
            
            const html = await request(url);
            const json = safeJSONParse(html);
            
            quarkCookie = json.quark_cookie || "";
            baiduCookie = json.baidu_cookie || "";
            ucCookie = json.uc_cookie || "";
            ucToken = json.uc_token || "";
            siteOrder = order?.trim() || "";
            customLineOrder = json.line_order || null;
            customThreads = json.threads || null; 
            customQuarkOriginal = json.quark_original !== undefined ? json.quark_original : null;
            customQuarkInfinite = json.quark_infinite !== undefined ? json.quark_infinite : null;
            customQuarkTransfer = json.quark_transfer !== undefined ? json.quark_transfer : null;
            customEnableProxy = json.enable_proxy !== undefined ? json.enable_proxy : null;
            customEnableImage = json.enable_image !== undefined ? json.enable_image : null;
            customProxyUrl = json.proxy_url || null;
            customProxyImg = json.proxy_img || null;
        }
    }
    
    // 应用配置
    line_order = customLineOrder?.length ? customLineOrder : line_order;
    downThreads = customThreads || downThreads;
    quarkOrig = customQuarkOriginal !== null ? customQuarkOriginal : quarkOrig;
    quarkInfinite = customQuarkInfinite !== null ? customQuarkInfinite : quarkInfinite;
    quarkTransfer = customQuarkTransfer !== null ? customQuarkTransfer : quarkTransfer;
    enableProxy = customEnableProxy !== null ? customEnableProxy : enableProxy;
    enable_image = customEnableImage !== null ? customEnableImage : enable_image;
    proxyurl = customProxyUrl || proxyurl;
    proxyimg = customProxyImg || proxyimg;
    
    // 设置网盘Cookie
    if (quarkCookie?.length > 10) Quark.cookie = quarkCookie;
    if (baiduCookie?.length > 10) Baidu.cookie = baiduCookie;
    if (ucCookie?.length > 10) UC.cookie = ucCookie;
    if (ucToken?.length > 10) UC.token = ucToken;
    
    // 匹配站点配置
    if (siteOrder) {
        for (const [key] of Object.entries(DOM_CFG)) {
            if (siteOrder.includes(key)) {
                selectedConfig = key;
                break;
            }
        }
    }
    
    const domains = DOM_CFG[selectedConfig];
    const configId = selectedConfig;
    
    // 初始化主机 - 使用local缓存
    try {
        const cached = await local.get(CACHE_NS, 'domain_' + configId);
        if (cached && domains.includes(cached)) {
            host = cached;
            headers.Referer = host + "/";
        }
    } catch {}
    
    if (!host) {
        try {
            const results = await Promise.any(
                domains.map(async (domain) => {
                    const content = await request(domain, { timeout: 8000 });
                    if (content && content.includes('href')) {
                        return domain;
                    }
                    throw new Error('无效域名');
                })
            );
            
            if (results) {
                host = results;
                headers.Referer = host + "/";
                await local.set(CACHE_NS, 'domain_' + configId, host).catch(() => {});
            }
        } catch (error) {
            host = domains[0]; 
        }
    }
    
    apitype = await getApiType();
    
    if (host) {
        // 尝试从缓存读取分类和筛选器数据
        const cacheKey = `${CLASS_CACHE_KEY}_${configId}`;
        let needUpdate = true;
        
        try {
            const cached = await local.get(CACHE_NS, cacheKey);
            if (cached) {
                const parsed = safeJSONParse(cached);
                const cacheTime = parsed.timestamp || 0;
                const now = Date.now();
                
                // 缓存7天内有效
                if (now - cacheTime < 7 * 24 * 60 * 60 * 1000) {
                    cachedClasses = parsed.classes || [];
                    cachedFilters = parsed.filters || {};
                    
                    // 保存到siteConfigs
                    siteConfigs[siteName] = {
                        classes: cachedClasses,
                        filters: cachedFilters
                    };
                    
                    needUpdate = false;
                }
            }
        } catch {}
        
        if (needUpdate && host) {
            try {
                // 请求首页获取分类
                const html = await request(host);
                const classes = [];
                const seenTypeIds = new Set();
                
                const navItems = pdfa(html, '.nav-menu-items&&li');
                
                navItems.forEach((item) => {
                    const href = pd(item, 'a&&href', host).trim();
                    const typeName = pdfh(item, 'a&&Text').trim();
                    const match = href.match(/\/([^\/]+)\.html$/);
                    
                    // 检查是否在排除列表中
                    if (match && typeName && !seenTypeIds.has(match[1]) && /^\d+$/.test(match[1]) && !isClassExcluded(typeName)) {
                        classes.push({"type_name": typeName, "type_id": match[1]});
                        seenTypeIds.add(match[1]);
                    }
                });
                
                cachedClasses = classes;
                
                if (classes.length > 0) {
                    // 使用 Promise.all 并发获取筛选器
                    const filterPromises = classes.map(async (cls) => {
                        const type_id = cls.type_id;
                        const url = apitype === "vodshow" ? 
                            `${host}/vodshow/${type_id}-----------.html` : 
                            `${host}/index.php/vod/show/id/${type_id}.html`;
                        
                        const html = await request(url);
                        const filters = await getFilters(type_id, html);
                        return { type_id, filters };
                    });
                    
                    const filterResults = await Promise.all(filterPromises);
                    
                    const filters = {};
                    filterResults.forEach(result => {
                        filters[result.type_id] = result.filters;
                    });
                    
                    cachedFilters = filters;
                    
                    // 保存到siteConfigs
                    siteConfigs[siteName] = {
                        classes: cachedClasses,
                        filters: cachedFilters
                    };
                    
                    // 存储到缓存
                    const cacheData = {
                        timestamp: Date.now(),
                        classes: cachedClasses,
                        filters: cachedFilters
                    };
                    await local.set(CACHE_NS, cacheKey, JSON.stringify(cacheData)).catch(() => {});
                }
            } catch (error) {}
        }
    }
    
    return JSON.stringify({});
}

/**
 * 获取筛选条件
 * @param {string} type_id - 分类ID
 * @param {string} pageHtml - 页面HTML
 * @returns {Array} 筛选条件列表
 */
async function getFilters(type_id, pageHtml) {
    if (!pageHtml || pageHtml.length < 300) return [];
    const cats = [
        { key: 'cateId', name: '类型', reg: /\/id\/(\d+)/ },
        { key: 'class', name: '剧情' }, { key: 'lang', name: '语言' },
        { key: 'area', name: '地区' }, { key: 'year', name: '时间' }, { key: 'letter', name: '字母' }
    ];
    const sortOpts = { "时间": "time", "人气": "hits", "评分": "score" };
    let filters = [];

    try {
        cats.forEach(cat => {
            const libraryBoxes = pdfa(pageHtml, '.library-box');
            const box = libraryBoxes.find(b => (pdfh(b, 'a&&Text') || '').includes(cat.name));
            if (!box) return;

            const linkItems = pdfa(box, 'div a');
            let values = linkItems.map(a => {
                const n = pdfh(a, "a&&Text") || "全部";
                let v = n;
                if (cat.key === 'cateId') {
                    const href = pd(a, 'a&&href', host);
                    const m = href?.match(cat.reg);
                    v = m?.[1] || n;
                }
                if (/全部|字母/.test(n)) return { n: "全部", v: "" };
                return { n, v };
            }).filter(x => x?.n)
                .filter((item, idx, self) => self.findIndex(i => i.n === item.n) === idx);

            if (values.length > 3) filters.push({ key: cat.key, name: cat.name, value: values });
        });

        const sortVals = Object.entries(sortOpts).map(([n, v]) => ({ n, v }));
        if (sortVals.length) filters.push({ key: "by", name: "排序", value: sortVals });
    } catch {}
    return filters;
}

/**
 * 首页 - 返回分类和筛选器
 */
async function home(filter) {
    let info = getSite(siteName);
    
    if (!info.classes || info.classes.length === 0) {
        info.classes = cachedClasses || [];
    }
    
    return JSON.stringify({
        class: info.classes, 
        filters: info.filters
    });
}

/**
 * 获取视频列表
 * @param {string} html - 页面HTML
 * @returns {Array} 视频列表
 */
function getList(html) {
    const videos = [];
    const items = pdfa(html, ".module-items .module-item");
    
    items.forEach((it) => {
        const name = pdfh(it, "a&&title");
        const pic = pd(it, "img&&data-src", host);
        const desc = pdfh(it, ".module-item-text&&Text");
        const url = pd(it, "a&&href", host);
        
        if (name && url) {
            videos.push({
                "vod_id": url,
                "vod_name": name,
                "vod_pic": proxyImage(pic),
                "vod_remarks": desc || ""
            });
        }
    });
    
    return videos;
}

/**
 * 首页推荐
 */
async function homeVod() {
    const html = await request(host);
    return JSON.stringify({ list: getList(html) });
}

/**
 * 分类页
 */
async function category(tid, pg, filter, extend) {
    const p = pg || 1;
    const fl = extend || {};
    let url = '';
    
    if (apitype === "vodshow") {
        url = `${host}/vodshow/${tid}-${fl.area || ''}-${fl.by || 'time'}-${fl.class || ''}--${fl.letter || ''}---${p}---${fl.year || ''}.html`;
    } else {
        const parts = [
            fl.area ? `area/${fl.area}` : '',
            fl.by ? `by/${fl.by}` : '',
            fl.class ? `class/${fl.class}` : '',
            fl.cateId ? `id/${fl.cateId}` : `id/${tid}`,
            fl.lang ? `lang/${fl.lang}` : '',
            fl.letter ? `letter/${fl.letter}` : '',
            fl.year ? `year/${fl.year}` : ''
        ].filter(Boolean);
        
        url = `${host}/index.php/vod/show/${parts.join('/')}/page/${p}.html`;
    }
    
    const html = await request(url);
    const videos = getList(html);
    return JSON.stringify({list: videos, page: p, pagecount: 999, limit: 20, total: 999});
}

/**
 * 详情页 - 解析视频信息和播放线路
 */
async function detail(id) {
    let html = await request(id);
    
    let vod_name = pdfh(html, '.video-info h1&&Text') || pdfh(html, 'h1&&Text') || '未知名称';
    let type_name = pdfh(html, '.tag-link&&Text') || '未知类型';
    let vod_pic = pd(html, '.lazyload&&data-src', host) || '';
    vod_pic = proxyImage(vod_pic);
    let vod_content = pdfh(html, '.sqjj_a--span&&Text') || pdfh(html, '.video-info-content&&Text') || '暂无简介';
    let vod_remarks = pdfh(html, '.video-info-items:eq(3)&&Text') || '未知';
    let vod_year = pdfh(html, '.tag-link:eq(2)&&Text') || '未知年份';
    let vod_area = pdfh(html, '.tag-link:eq(3)&&Text') || '未知地区';
    let vod_actor = pdfh(html, '.video-info-actor:eq(1)&&Text') || '未知演员';
    let vod_director = pdfh(html, '.video-info-actor:eq(0)&&Text') || '未知导演';
    
    let playFrom = [], playUrl = [], playPic = [];
    let data = pdfa(html, '.module-row-title');
    
    let panCounters = {'夸克': 1, '百度': 1, '优汐': 1};
    let allLines = [];
    
    data.forEach((item) => {
        let text = pdfh(item, 'p&&Text');
        if (text) {
            let link = text.trim();
            if (/\.quark/.test(link)) allLines.push({ type: '夸克', link: link });
            else if (/\.baidu/.test(link)) allLines.push({ type: '百度', link: link });
            else if (/\.uc|drive\.uc\.cn/.test(link)) allLines.push({ type: '优汐', link: link });
        }
    });
    
    for (let item of allLines) {
        if (item.type === '夸克') {
            let shareData = Quark.getShareData(item.link);
            let files = await Quark.getFilesByShareUrl(shareData);
            let lineName = '夸克#' + panCounters.夸克;
            if (files && files.length > 0) {
                let url = files.map(v => {
                    let size = v.size ? ` 【${formatFileSize(v.size)}】` : '';
                    return `${v.file_name}${size}$${[shareData.shareId, v.stoken, v.fid, v.share_fid_token, v.pdir_fid || '', v.subtitle?.fid || '', v.subtitle?.share_fid_token || ''].join('*')}`;
                }).join('#');
                let imgs = files.map(v => proxyImage(v.thumbnail || v.thumb || v.pic || '')).join('#');
                playFrom.push(lineName);
                playUrl.push(url);
                playPic.push(imgs);
                panCounters.夸克++;
            }
        }
        else if (item.type === '百度') {
            let shareData = Baidu.getShareData(item.link);
            if (shareData) {
                let files = await Baidu.getFilesByShareUrl(shareData);
                if (files && files.length > 0) {
                    let lineName = '百度#' + panCounters.百度;
                    let url = files.map(v => {
                        let size = v.size ? ` 【${formatFileSize(v.size)}】` : '';
                        let info = { surl: shareData.surl, pwd: shareData.pwd || '' };
                        return `${v.name}${size}$${[v.path, v.uk, v.shareid, v.fsid, JSON.stringify(info)].join('*')}`;
                    }).join('#');
                    let imgs = files.map(v => proxyImage(v.thumbnail || v.thumb || v.pic || '')).join('#');
                    playFrom.push(lineName);
                    playUrl.push(url);
                    playPic.push(imgs);
                    panCounters.百度++;
                }
            }
        }
        else if (item.type === '优汐') {
            let shareData = UC.getShareData(item.link);
            if (shareData) {
                let files = await UC.getFilesByShareUrl(shareData);
                if (files && files.length > 0) {
                    let lineName = '优汐#' + panCounters.优汐;
                    let url = files.map(v => {
                        let size = v.size ? ` 【${formatFileSize(v.size)}】` : '';
                        return `${v.file_name}${size}$${[shareData.shareId, v.stoken, v.fid, v.share_fid_token, v.subtitle?.fid || '', v.subtitle?.share_fid_token || ''].join('*')}`;
                    }).join('#');
                    let imgs = files.map(v => proxyImage(v.thumbnail || v.thumb || v.pic || '')).join('#');
                    playFrom.push(lineName);
                    playUrl.push(url);
                    playPic.push(imgs);
                    panCounters.优汐++;
                }
            }
        }
    }
    
    // 线路排序和过滤
    if (playFrom.length > 0) {
        let sortedLines = playFrom.map((name, index) => ({
            name, 
            url: playUrl[index], 
            pic: playPic[index],
            type: name.split('#')[0]
        })).sort((a, b) => {
            let aIndex = line_order.indexOf(a.type);
            let bIndex = line_order.indexOf(b.type);
            if (aIndex === -1) aIndex = Infinity;
            if (bIndex === -1) bIndex = Infinity;
            return aIndex - bIndex;
        });
        
        let sorted = sortedLines.filter(line => !/(无名|失效)/.test(line.url));
        
        playFrom = sorted.map(line => line.name);
        playUrl = sorted.map(line => line.url);
        playPic = sorted.map(line => line.pic);
    }
    
    let vod = {
        'vod_id': id,
        'vod_name': vod_name,
        'vod_pic': vod_pic,
        'vod_content': vod_content,
        'vod_remarks': vod_remarks,
        'vod_year': vod_year,
        'vod_area': vod_area,
        'vod_actor': vod_actor,
        'vod_director': vod_director,
        'type_name': type_name,
        'vod_play_from': playFrom.join('$$$'),
        'vod_play_url': playUrl.join('$$$'),
        'vod_play_pic': playPic.join('$$$'),
        'vod_play_pic_ratio': 1.0
    };
    
    return JSON.stringify({ list: [vod] });
}

/**
 * 搜索
 */
async function search(wd, quick, pg) {
    const p = pg || 1;
    let url = apitype === "vodshow" 
        ? `${host}/vodsearch/${wd}----------${p}---.html`
        : `${host}/index.php/vod/search/page/${p}/wd/${encodeURIComponent(wd)}.html`;
    
    const html = await request(url);
    if (!html) return JSON.stringify({ list: [], page: p, pagecount: 0, limit: 20, total: 0 });
    
    const data = pdfa(html, '.module-items .module-search-item');
    const videos = [];
    
    data.forEach((it) => {
        const name = pdfh(it, '.video-info&&a&&title');
        if (!name) return;
        let pic = pd(it, 'img&&data-src', host) || '';
        pic = proxyImage(pic);
        const desc = pdfh(it, '.module-item-text') || "";
        let url = pd(it, '.video-info&&a&&href', host) || '';
        videos.push({ "vod_id": url, "vod_name": name, "vod_pic": pic, "vod_remarks": desc });
    });
    
    const filteredResults = videos.filter(item => (item.vod_name || '').toLowerCase().includes(wd.toLowerCase()));
    
    return JSON.stringify({ list: filteredResults, page: p, pagecount: 10, limit: 20, total: 100 });
}

/**
 * 播放 - 获取视频播放链接
 */
async function play(flag, id, flags) {
    let ids = id.split('*');
    let urls = [];
    
    const addUrl = (name, u) => { 
        if (u) {
            let finalUrl = u;
            if (enableProxy == 1 && proxyurl) {
                finalUrl = proxyurl + encodeURIComponent(u);
            }
            urls.push(name, finalUrl + `&threads=${downThreads}`); 
        }
    };
    
    // 夸克网盘
    if (flag.startsWith('夸克') && ids.length >= 4) {
        let [shareId, stoken, fid, share_fid_token] = ids;
        let header = { 
            'User-Agent': UA, 
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
    
    return JSON.stringify({ parse: 0, msg: `解析分享链接失败, 分享链接可能已失效`, header: headers });
}

/**
 * 获取API类型
 */
async function getApiType() {
    if (!host) return "index.php";
    try {
        const content = await request(host, { timeout: 3000 });
        return content?.includes('vodshow') ? "vodshow" : "index.php";
    } catch {
        return "index.php";
    }
}

/**
 * 格式化文件大小
 */
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
        bytes /= 1024;
        i++;
    }
    return bytes.toFixed(2) + ' ' + units[i];
}

/**
 * 图片代理
 */
function proxyImage(url) {
    if (!url) return '';
    url = url.replace(/(https?:\/\/[^/]+\/)+/g, '$1');
    if (enable_image != 1) return url;
    if (/zy|xinlangtupian/.test(url)) {
        return proxyimg + encodeURIComponent(url);
    }
    return url;
}

/**
 * 获取站点配置
 */
function getSite(name) {
    const config = siteConfigs[name];
    if (config) {
        return {
            classes: config.classes || [],
            filters: config.filters || {}
        };
    }
    
    return {
        classes: cachedClasses || [],
        filters: cachedFilters || {}
    };
}

export function __jsEvalReturn() {
    return {
        init: init,
        home: home,
        homeVod: homeVod,
        category: category,
        detail: detail,
        play: play,
        search: search,
    }
}