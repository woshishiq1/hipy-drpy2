/*
@header({
  searchable: 1,
  filterable: 0,
  quickSearch: 1,
  title: '网盘资源[搜]',
  lang: 'ds'
})
*/
import '../lib/htmlParser.js';
import { Quark, Baidu, UC } from "../lib/pans.js";

let siteName = '夸克短剧搜索', siteKey = '', siteType = 0;

let quarkInfinite = 0;
let quarkOrig = 1;
let quarkTransfer = 1;
let enableProxy = 0;

let UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36";

let headers = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
};

let proxyurl = 'http://127.0.0.1:2525/proxy?url=';
let downThreads = '20';

let defaultImg = `https://cnb.cool/zhyadc/YsBox/-/git/raw/main/images/icon_cookie/网盘搜索.png`;
let quark_img = `https://cnb.cool/zhyadc/YsBox/-/git/raw/main/images/icon_cookie/夸克.png`;

let host = 'https://api.uuuka.com';
let maxPages = 5;

function safeJSONParse(str, defaultValue = {}) {
    if (!str || typeof str === 'object') return str || defaultValue;
    try {
        return JSON.parse(str);
    } catch {
        return defaultValue;
    }
}

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

function mapResolution(res) {
    const map = {
        'low': '流畅', 'normal': '标清', 'high': '高清', 'super': '超清',
        '4k': '4K', '2k': '2K', 'hdr': 'HDR', 'dolby_vision': 'HDR',
        'M3U8_AUTO_480': '480P', 'M3U8_AUTO_720': '720P', 'M3U8_AUTO_1080': '1080P',
        'M3U8_AUTO_2K': '2K', 'M3U8_AUTO_4K': '4K'
    };
    return map[res] || res;
}

function buildSearchUrl(wd, page) {
    return `${host}/api/search?keyword=${encodeURIComponent(wd)}&content_type=post&page=${page}&limit=100`;
}

async function loadRemoteConfig(cfgUrl) {
    try {
        const res = await request(cfgUrl, { timeout: 10000 });
        if (res) {
            const remoteCfg = safeJSONParse(res);
            if (remoteCfg.quark_cookie?.length > 10) Quark.cookie = remoteCfg.quark_cookie;
            if (remoteCfg.baidu_cookie?.length > 10) Baidu.cookie = remoteCfg.baidu_cookie;
            if (remoteCfg.uc_cookie?.length > 10) UC.cookie = remoteCfg.uc_cookie;
            if (remoteCfg.uc_token?.length > 10) UC.token = remoteCfg.uc_token;
            if (remoteCfg.threads) downThreads = remoteCfg.threads;
            if (remoteCfg.enableProxy !== undefined) enableProxy = remoteCfg.enableProxy;
            if (remoteCfg.infinite !== undefined) quarkInfinite = remoteCfg.infinite;
            if (remoteCfg.quark_original !== undefined) quarkOrig = remoteCfg.quark_original;
            if (remoteCfg.quark_transfer !== undefined) quarkTransfer = remoteCfg.quark_transfer;
            return true;
        }
    } catch (e) {}
    return false;
}

async function init(cfg) {
    siteName = cfg.skey?.split('_')[1] || cfg.skey || siteName;
    siteKey = cfg.skey;
    siteType = cfg.stype;
    
    let ext = cfg.ext || cfg;
    if (typeof ext === 'string') ext = decodeURIComponent(ext);
    if (typeof ext === 'string') {
        await loadRemoteConfig(ext);
    }
    
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

async function detail(id) {
    let parts = id.split('|');
    let shareUrl = parts[0];
    let vod_name = parts[1] || '网盘资源';
    
    let play_from = [];
    let play_url = [];
    let play_pic = [];
    
    if (shareUrl && shareUrl.startsWith('http')) {
        let counters = { '夸克': 1, '百度': 1, '优汐': 1 };
        
        if (/\.quark|pan\.quark/.test(shareUrl)) {
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
        }
        else if (/\.baidu|pan\.baidu/.test(shareUrl)) {
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
        }
        else if (/\.uc|drive\.uc/.test(shareUrl)) {
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
        play_url.push(shareUrl ? `分享链接: ${shareUrl}` : `获取分享链接失败`);
        play_pic.push('');
    }
    
    let vod = {
        vod_id: id,
        vod_name: vod_name,
        vod_pic: '',
        vod_content: `网盘链接: ${shareUrl}`,
        vod_remarks: play_from.length > 0 ? (play_from[0].split('#')[0] + '可播放') : '解析失败',
        vod_play_from: play_from.join('$$$'),
        vod_play_url: play_url.join('$$$'),
        vod_play_pic: play_pic.join('$$$'),
        vod_play_pic_ratio: 1.0
    };
    
    return JSON.stringify({ list: [vod] });
}

async function search(wd, quick, pg) {
    let page = pg || 1;
    
    let apiUrl = buildSearchUrl(wd, page);
    let response = await request(apiUrl, { headers: headers, timeout: 15000 });
    let allList = [];
    
    if (response) {
        try {
            let data = safeJSONParse(response);
            if (data.success && data.data && data.data.items) {
                for (let item of data.data.items) {
                    let title = item.title;
                    let shareUrl = item.source_link;
                    
                    if (!title || !shareUrl) continue;
                    
                    let detailId = `${shareUrl}|${title}`;
                    
                    allList.push({
                        vod_id: detailId,
                        vod_name: title,
                        vod_pic: quark_img,
                        vod_content: `更新时间: ${item.update_time || '未知'}`,
                        vod_remarks: '夸克网盘'
                    });
                }
            }
        } catch (e) {}
    }
    
    let filteredList = allList.filter(item => new RegExp(wd, "i").test(item.vod_name));
    
    return JSON.stringify({
        page: page,
        pagecount: 999,
        limit: filteredList.length,
        total: filteredList.length,
        list: filteredList
    });
}

async function play(flag, id, flags) {
    let ids = id.split('*');
    let urls = [];
    
    const addUrl = (name, u) => { 
        if (u) urls.push(name, proxyUrl(u) + `&thread=${downThreads}`); 
    };
    
    if (flag.startsWith('夸克') && ids.length >= 4) {
        let [shareId, stoken, fid, share_fid_token] = ids;
        let header = { 
            'User-Agent': headers['User-Agent'], 
            'origin': 'https://pan.quark.cn', 
            'referer': 'https://pan.quark.cn/', 
            'Cookie': Quark.cookie 
        };
        
        if (quarkInfinite == 1) {
            const tokenUrls = await Quark.getUrl(shareId, stoken, fid, share_fid_token);
            tokenUrls?.forEach(item => { if (item?.url) addUrl("无限" + (item.name || ''), item.url); });
        }
        
        let shouldTransfer = quarkTransfer;
        if (quarkInfinite != 1 && quarkOrig != 1 && quarkTransfer != 1) {
            shouldTransfer = 1;
        }
        
        if (shouldTransfer == 1) {
            if (quarkOrig == 1) {
                let down = await Quark.getDownload(shareId, stoken, fid, share_fid_token, true);
                if (down && down.error) {
                    const errorMsg = down.message || '未知错误';
                    return JSON.stringify({ parse: 0, msg: `夸克: ${errorMsg}`, header: header });
                }
                if (down?.download_url) addUrl("原画", down.download_url);
            }
            
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

export function __jsEvalReturn() {
    return { init, home, homeVod, category, detail, play, search, proxy };
}