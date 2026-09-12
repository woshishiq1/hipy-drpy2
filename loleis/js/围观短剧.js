/*
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '围观短剧',
  lang: 'cat'
})
*/

let siteName = '围观短剧';
let siteKey = '';
let siteType = 0;

let UA = "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36";

let rule = {
    host: 'https://api.drama.9ddm.com',
    tagsUrl: '/drama/home/shortVideoTags?version_code=1500&os_type=1',
    searchUrl: '/drama/home/search?version_code=1500&os_type=1',
    detailUrl: '/drama/home/shortVideoDetail?version_code=1500&os_type=1'
};

const DEFAULT_HEADERS = {
    'User-Agent': UA,
    'Content-Type': 'application/json',
    'Accept': 'application/json'
};

function init(cfg) {
    try {
        siteName = (cfg.skey?.split('_')[1] || cfg.skey) || (cfg.key?.split('_')[1] || cfg.key) || '围观短剧';
        siteKey = cfg.skey;
        siteType = cfg.stype;
        console.log(`【${siteName}】初始化完成`);
    } catch (e) {
        console.log(`【${siteName}】初始化失败: ${e.message}`);
    }
}

function safeJSONParse(str, defaultValue = {}) {
    if (!str) return defaultValue;
    if (typeof str === 'object') return str;
    try {
        return JSON.parse(str);
    } catch (e) {
        console.log(`【${siteName}】JSON解析失败: ${e.message}`);
        return defaultValue;
    }
}

// 通用请求函数
async function request(url, options = {}) {
    console.log(`【${siteName}】${options.method || 'GET'} ${url.split('?')[0]}`);
    
    const baseOptions = {
        method: options.method || 'GET',
        headers: { ...DEFAULT_HEADERS, ...options.headers },
        timeout: options.timeout || 15000
    };
    
    let dataStr = '';
    const requestData = options.body || options.data;
    if (requestData) {
        dataStr = typeof requestData === 'string' ? requestData : JSON.stringify(requestData);
        baseOptions.headers['Content-Type'] = baseOptions.headers['Content-Type'] || 'application/json';
    }
    
    for (let key of ['data', 'body']) {
        try {
            const reqOptions = { ...baseOptions, [key]: dataStr };
            const response = await req(url, reqOptions);
            const content = response?.content || response?.data || response;
            
            if (!content) continue;
            
            const data = typeof content === 'object' ? content : safeJSONParse(content);
            
            if (data?.code && data.code !== 200) continue;
            
            console.log(`【${siteName}】${key}成功: ${JSON.stringify(data).substring(0, 300)}`);
            return data;
        } catch (e) {
            console.log(`【${siteName}】${key}异常: ${e.message}`);
        }
    }
    
    console.log(`【${siteName}】全部失败`);
    return null;
}

async function home() {
    let classes = [{ type_name: '全部', type_id: '全部' }];
    let filters = { '全部': [] };
    
    const data = await request(`${rule.host}${rule.tagsUrl}`);
    
    if (data && data.code === 200) {
        // 分类
        if (data.audiences && Array.isArray(data.audiences)) {
            const audienceClasses = data.audiences.map(audience => ({
                type_name: audience,
                type_id: audience
            }));
            classes.push(...audienceClasses);
            
            // 为每个分类创建筛选
            for (const audience of data.audiences) {
                filters[audience] = [];
                
                if (data.tags && Array.isArray(data.tags) && data.tags.length > 0) {
                    const tagValues = [{ n: '全部', v: '' }];
                    data.tags.forEach(tag => {
                        if (tag) tagValues.push({ n: tag, v: tag });
                    });
                    if (tagValues.length > 1) {
                        filters[audience].push({ key: 'tag', name: '标签', value: tagValues });
                    }
                }
                
                if (data.orders && Array.isArray(data.orders) && data.orders.length > 0) {
                    const orderValues = data.orders.map(order => ({ n: order, v: order }));
                    filters[audience].push({ key: 'order', name: '排序', value: orderValues });
                }
            }
        }
    }
    
    return JSON.stringify({ class: classes, filters: filters });
}

async function homeVod() {
    try {
        const result = await category('全部', 1, {}, {});
        const data = typeof result === 'string' ? safeJSONParse(result) : result;
        const list = (data && data.list) ? data.list.slice(0, 12) : [];
        return JSON.stringify({ list: list });
    } catch (e) {
        console.log(`【${siteName}】homeVod失败: ${e.message}`);
        return JSON.stringify({ list: [] });
    }
}

async function category(tid, pg, filter, extend) {
    const videos = [];
    const page = pg || 1;
    
    const tag = (extend && extend.tag) ? extend.tag : "";
    const order = (extend && extend.order) ? extend.order : "";
    
    const orderMap = { "最热": "hot", "最新": "new", "热度": "hot", "时间": "new" };
    let orderValue = orderMap[order] || "";
    
    const postData = {
        audience: tid === '全部' ? "" : tid,
        page: page,
        pageSize: 30,
        searchWord: "",
        subject: tag,
        order: orderValue
    };
    
    console.log(`【${siteName}】分类请求: tid=${tid}, tag=${tag}, order=${order}`);
    
    const data = await request(`${rule.host}${rule.searchUrl}`, {
        method: 'POST',
        body: postData
    });
    
    if (data && data.code === 200 && data.data && Array.isArray(data.data)) {
        for (const it of data.data) {
            if (it && it.oneId) {
                videos.push({
                    vod_id: String(it.oneId),
                    vod_name: it.title || '未知标题',
                    vod_pic: it.vertPoster || it.horizonPoster || '',
                    vod_remarks: `集数:${it.episodeCount || 0} 播放:${it.viewCount || 0}`,
                    vod_content: it.description || '',
                    vod_year: it.publishDate || ''
                });
            }
        }
    } else {
        console.log(`【${siteName}】分类数据异常:`, data?.code);
    }
    
    console.log(`【${siteName}】分类获取到 ${videos.length} 条数据`);
    
    return JSON.stringify({
        list: videos,
        page: page,
        pagecount: page + 1,
        limit: videos.length,
        total: videos.length * (page + 1)
    });
}

async function detail(id) {
    if (!id) return JSON.stringify({ list: [] });
    
    const url = `${rule.host}${rule.detailUrl}&oneId=${encodeURIComponent(id)}&page=1&pageSize=1000`;
    const data = await request(url);
    
    if (data && data.code === 200 && data.data && Array.isArray(data.data)) {
        const episodes = data.data.filter(ep => ep);
        const firstEpisode = episodes[0] || {};
        
        const playItems = [];
        for (let i = 0; i < episodes.length; i++) {
            const episode = episodes[i];
            let playSetting = episode.playSetting || episode.videoClarityList || [];
            
            if (typeof playSetting === 'string') {
                playSetting = safeJSONParse(playSetting, []);
            }
            if (!Array.isArray(playSetting)) playSetting = [];
            
            const clarityInfo = {};
            for (const item of playSetting) {
                if (item && item.url && item.name) {
                    clarityInfo[item.name] = item.url;
                }
            }
            
            if (Object.keys(clarityInfo).length > 0) {
                const episodeNum = episode.playOrder || episode.episodeNumber || (i + 1);
                playItems.push(`第${episodeNum}集$${JSON.stringify(clarityInfo)}`);
            }
        }
        
        const playUrl = playItems.join('#');
        if (!playUrl) return JSON.stringify({ list: [] });
        
        const vod = {
            vod_id: String(id),
            vod_name: firstEpisode.title || '未知剧名',
            vod_pic: firstEpisode.vertPoster || firstEpisode.horizonPoster || '',
            vod_remarks: `共${episodes.length}集`,
            vod_content: firstEpisode.description || '',
            vod_play_from: '围观短剧',
            vod_play_url: playUrl
        };
        
        return JSON.stringify({ list: [vod] });
    }
    
    return JSON.stringify({ list: [] });
}

async function play(flag, id, flags) {
    let clarityInfo = {};
    
    try {
        if (typeof id === 'object') {
            clarityInfo = id;
        } else if (typeof id === 'string') {
            clarityInfo = safeJSONParse(id, {});
        }
    } catch (e) {
        return JSON.stringify({ parse: 0, url: id || '', msg: '播放参数错误' });
    }
    
    const clarityOrder = ['4K', '超清', '1080P', '高清', '720P', '流畅', '480P'];
    const urls = [];
    const added = new Set();
    
    for (const clarity of clarityOrder) {
        const url = clarityInfo[clarity];
        if (url && typeof url === 'string' && url.startsWith('http') && !added.has(clarity)) {
            urls.push(clarity, url);
            added.add(clarity);
        }
    }
    
    if (urls.length > 0) {
        return JSON.stringify({
            parse: 0,
            url: urls,
            header: { 'User-Agent': UA }
        });
    }
    
    if (typeof id === 'string' && id.startsWith('http')) {
        return JSON.stringify({ parse: 0, url: id, header: { 'User-Agent': UA } });
    }
    
    return JSON.stringify({ parse: 0, url: '', msg: '暂无可用播放地址' });
}

async function search(wd, quick, pg) {
    if (!wd || wd.trim() === '') {
        return JSON.stringify({ list: [], page: 1 });
    }
    
    const page = pg || 1;
    const postData = {
        audience: "",
        page: page,
        pageSize: 30,
        searchWord: wd,
        subject: ""
    };
    
    const data = await request(`${rule.host}${rule.searchUrl}`, {
        method: 'POST',
        body: postData,
        timeout: 8000
    });
    
    let videos = [];
    if (data && data.code === 200 && data.data && Array.isArray(data.data)) {
        videos = data.data.filter(it => it && it.oneId).map(it => ({
            vod_id: String(it.oneId),
            vod_name: it.title || '未知标题',
            vod_pic: it.vertPoster || it.horizonPoster || '',
            vod_remarks: `集数:${it.episodeCount || 0} 播放:${it.viewCount || 0}`,
            vod_content: it.description || ''
        }));
    }
    
    return JSON.stringify({
        list: videos,
        page: page,
        pagecount: videos.length === 30 ? page + 1 : page,
        limit: videos.length,
        total: videos.length * page
    });
}

export function __jsEvalReturn() {
    return {
        init: init,
        home: home,
        homeVod: homeVod,
        category: category,
        detail: detail,
        play: play,
        search: search
    };
}