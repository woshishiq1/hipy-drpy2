/*
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '喜马拉雅[听]',
  lang: 'cat',
})
*/
let host = 'https://m.ximalaya.com';
let searchHost = 'https://api.cenguigui.cn';

let siteName = '喜马拉雅', siteKey = '', siteType = 0;

let UA = "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (Chrome/91.0.4472.120 Mobile Safari/537.36)";

const headers = {
    'User-Agent': UA,
    'Accept': 'application/json, text/plain, */*'
};

function init(cfg) {
    siteName = cfg.skey?.split('_')[1] || cfg.skey || '喜马拉雅';
    siteKey = cfg.skey;
    siteType = cfg.stype;
    
    if (cfg && typeof cfg === 'string') {
        host = cfg;
    } else if (cfg && typeof cfg === 'object') {
        const ext = cfg.ext;
        if (ext) {
            host = ext.host || ext.hosturl || ext.url || ext.site || host;
        }
    }
}

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

async function home(filter) {
    const classNames = '有声书&儿童&音乐&相声&娱乐&广播剧&历史&外语';
    const classUrls = 'youshengshu&ertong&yinyue&xiangsheng&yule&guangbojv&lishi&waiyu';
    
    const names = classNames.split('&');
    const urls = classUrls.split('&');
    
    const classes = [];
    for (let i = 0; i < names.length && i < urls.length; i++) {
        classes.push({ type_id: urls[i], type_name: names[i] });
    }
    
    const filters = {};
    classes.forEach(cls => { filters[cls.type_id] = []; });
    
    return JSON.stringify({ class: classes, filters: filters });
}

async function homeVod() {
    return await category('youshengshu', 1, null, {});
}

async function category(tid, pg, filter, extend) {
    const page = pg || 1;
    
    try {
        const url = `${host}/m-revision/page/category/queryCategoryAlbumsByPage?sort=0&pageSize=50&page=${page}&categoryCode=${tid}`;
        const html = await request(url);
        
        if (!html) {
            return JSON.stringify({ list: [], page: page, pagecount: 1, limit: 50, total: 0 });
        }
        
        const data = safeJSONParse(html).data;
        const albumList = data.albumBriefDetailInfos || [];
        const videos = [];
        
        albumList.forEach(it => {
            const vip = it.albumInfo?.albumVipPayType;
            if (vip === 0) {
                const id = `http://mobile.ximalaya.com/mobile/others/ca/album/track/${it.id}/true/0/200?albumId=${it.id}`;
                videos.push({
                    vod_id: id,
                    vod_name: it.albumInfo?.title || '未知标题',
                    vod_pic: `http://imagev2.xmcdn.com/${it.albumInfo?.cover}`,
                    vod_remarks: '免费'
                });
            }
        });
        
        return JSON.stringify({ list: videos, page: page, pagecount: Math.ceil(videos.length / 50) + 1, limit: 50, total: videos.length });
    } catch (e) {
        return JSON.stringify({ list: [], page: page, pagecount: 1, limit: 50, total: 0 });
    }
}

async function detail(id) {
    try {
        const urls = [];
        const albumIdMatch = id.match(/albumId=(\d+)/);
        const albumId = albumIdMatch ? albumIdMatch[1] : '';
        
        const html = await request(id);
        const json = safeJSONParse(html);
        const album = json.album || {};
        let data = json.tracks?.list || [];
        const maxPageId = json.tracks?.maxPageId || 1;
        
        data.forEach(it => {
            if (it.playPathAacv164) {
                urls.push(`${it.title}$${it.playPathAacv164}`);
            }
        });
        
        if (maxPageId > 1) {
            for (let j = 2; j <= maxPageId; j++) {
                const pageUrl = id.replace('/0/', `/${j}/`);
                try {
                    const pageHtml = await request(pageUrl);
                    const pageJson = safeJSONParse(pageHtml);
                    const pageData = pageJson.tracks?.list || [];
                    pageData.forEach(it => {
                        if (it.playPathAacv164) {
                            urls.push(`${it.title}$${it.playPathAacv164}`);
                        }
                    });
                } catch (e) {}
            }
        }
        
        if (urls.length === 0) return JSON.stringify({ list: [] });
        
        const vod = {
            vod_id: id,
            vod_name: album.title || '暂无名称',
            vod_pic: album.coverLarge || '暂无图片',
            vod_content: album.intro || '暂无简介',
            vod_remarks: `共${urls.length}集`,
            vod_play_from: '喜马拉雅',
            vod_play_url: urls.join('#')
        };
        
        return JSON.stringify({ list: [vod] });
    } catch (e) {
        return JSON.stringify({ list: [] });
    }
}

async function play(flag, id, flags) {
    if (!id) {
        return JSON.stringify({ parse: 0, jx: 0, url: '', msg: '播放地址为空', header: {} });
    }
    return JSON.stringify({ parse: 0, jx: 0, url: id, header: {} });
}

async function search(wd, quick, pg = "1") {
    const page = parseInt(pg) || 1;
    
    try {
        const url = `${searchHost}/api/music/ximalaya.php?name=${encodeURIComponent(wd)}`;
        const html = await request(url);
        
        if (!html) {
            return JSON.stringify({ list: [], page: page, pagecount: 0, limit: 20, total: 0 });
        }
        
        const data = safeJSONParse(html).data;
        
        if (!Array.isArray(data)) {
            return JSON.stringify({ list: [], page: page, pagecount: 0, limit: 20, total: 0 });
        }
        
        const videos = data.map(it => {
            const id = `http://mobile.ximalaya.com/mobile/others/ca/album/track/${it.albumId}/true/0/200?albumId=${it.albumId}`;
            return {
                vod_id: id,
                vod_name: it.title || '未知标题',
                vod_pic: it.cover || '',
                vod_remarks: '喜马拉雅'
            };
        }).filter(v => v.vod_id);
        
        return JSON.stringify({ list: videos, page: page, pagecount: 1, limit: videos.length, total: videos.length });
    } catch (e) {
        return JSON.stringify({ list: [], page: page, pagecount: 0, limit: 20, total: 0 });
    }
}

export function __jsEvalReturn() {
    return { init, home, homeVod, category, detail, play, search };
}