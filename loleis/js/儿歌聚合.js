/*
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '聚合儿歌[儿]',
  lang: 'cat'
})
*/

let siteName = '聚合儿歌', siteKey = '', siteType = 0;

const platformList = [
  { name: '贝乐虎', id: 'beilehu' },
  { name: '兔小贝', id: 'tuxiaobei' }
];

const headers = {
  'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1'
};

const rule = {
  beilehu: {
    host: 'https://vd.ubestkid.com',
    api: '/api/v1/bv/video'
  },
  tuxiaobei: {
    host: 'https://www.tuxiaobei.com',
    listApi: '/list/mip-data',
    playUrl: '/play/',
    searchApi: '/search/'
  }
};

const filterOptions = {
  beilehu: [{
    key: "area", name: "分类",
    value: [
      { "n": "最新上架", "v": "65" }, { "n": "人气热播", "v": "113" }, { "n": "经典童谣", "v": "56" },
      { "n": "开心贝乐虎", "v": "137" }, { "n": "律动儿歌", "v": "53" }, { "n": "经典儿歌", "v": "59" },
      { "n": "超级汽车1", "v": "101" }, { "n": "超级汽车第二季", "v": "119" }, { "n": "超级汽车第三季", "v": "136" },
      { "n": "三字经", "v": "95" }, { "n": "幼儿手势舞", "v": "133" }, { "n": "哄睡儿歌", "v": "117" },
      { "n": "英文儿歌", "v": "70" }, { "n": "节日与节气", "v": "116" }, { "n": "恐龙世界", "v": "97" },
      { "n": "动画片儿歌", "v": "55" }, { "n": "流行歌曲", "v": "57" }, { "n": "贝乐虎入园记", "v": "118" },
      { "n": "贝乐虎大百科", "v": "106" }, { "n": "经典古诗", "v": "62" }, { "n": "经典故事", "v": "63" },
      { "n": "萌虎学功夫", "v": "128" }, { "n": "绘本故事", "v": "100" }, { "n": "开心贝乐虎英文版", "v": "121" },
      { "n": "嗨贝乐虎情商动画", "v": "96" }, { "n": "动物音乐派对", "v": "108" }, { "n": "动物音乐派对英文版", "v": "126" },
      { "n": "奇妙的身体", "v": "105" }, { "n": "奇妙的身体英文版", "v": "124" }, { "n": "认知卡片", "v": "64" },
      { "n": "趣味简笔画", "v": "109" }, { "n": "数字儿歌", "v": "78" }, { "n": "识字体验版", "v": "120" },
      { "n": "启蒙系列体验版", "v": "127" }
    ]
  }],
  tuxiaobei: [{
    key: "area", name: "分类",
    value: [
      { "n": "全部", "v": "" }, { "n": "儿歌", "v": "2" }, { "n": "故事", "v": "3" },
      { "n": "公益", "v": "27" }, { "n": "十万个为什么", "v": "9" }, { "n": "安全教育", "v": "28" },
      { "n": "动物奇缘", "v": "29" }, { "n": "弟子规", "v": "7" }, { "n": "古诗", "v": "5" },
      { "n": "三字经", "v": "6" }, { "n": "千字文", "v": "8" }, { "n": "数学", "v": "11" },
      { "n": "英语", "v": "25" }, { "n": "折纸", "v": "24" }
    ]
  }]
};

const ruleFilterDef = {
  beilehu: { area: '56' },
  tuxiaobei: { area: '2' }
};

function init(cfg) {
  siteName = cfg.skey?.split('_')[1] || cfg.skey || '聚合儿歌';
  siteKey = cfg.skey;
  siteType = cfg.stype;
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

function getPlatList() {
  return platformList;
}

async function getBeilehuList(typeId, page) {
  let videos = [];
  try {
    const postData = {
      age: 1,
      appver: "6.1.9",
      egvip_status: 0,
      svip_status: 0,
      vps: 60,
      subcateId: parseInt(typeId),
      p: page
    };
    
    const html = await request(rule.beilehu.host + rule.beilehu.api, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      data: postData
    });
    
    const json = safeJSONParse(html);
    const items = json.result?.items || [];
    
    videos = items.map(item => ({
      vod_id: `beilehu@${item.url}`,
      vod_name: item.title || '未知视频',
      vod_pic: item.image || '',
      vod_remarks: `贝乐虎 | 播放:${item.viewcount || 0}`,
      vod_content: item.description || ''
    }));
  } catch (e) {}
  return videos;
}

async function getTuxiaobeiList(typeId, page) {
  let videos = [];
  try {
    const url = `${rule.tuxiaobei.host}${rule.tuxiaobei.listApi}?typeId=${typeId}&page=${page}&callback=`;
    const html = await request(url, { headers });
    
    const match = html.match(/\((.*?)\);/);
    if (!match) return videos;
    
    const data = safeJSONParse(match[1]).data;
    const items = data.items || [];
    
    videos = items.map(item => ({
      vod_id: `tuxiaobei@${item.video_id}`,
      vod_name: item.name || '未知视频',
      vod_pic: item.image || '',
      vod_remarks: `兔小贝 | ${item.root_category_name || ''} ${item.duration_string || ''}`,
      vod_content: item.description || ''
    }));
  } catch (e) {}
  return videos;
}

async function getBeilehuDetail(url) {
  return {
    vod_id: url,
    vod_name: '贝乐虎视频',
    vod_remarks: '贝乐虎',
    vod_play_from: '贝乐虎',
    vod_play_url: `点击播放$${url}`
  };
}

async function getTuxiaobeiDetail(id) {
  return {
    vod_id: id,
    vod_name: '兔小贝视频',
    vod_remarks: '兔小贝',
    vod_play_from: '兔小贝',
    vod_play_url: `点击播放$${rule.tuxiaobei.host}${rule.tuxiaobei.playUrl}${id}`
  };
}

async function home(filter) {
  const platForms = getPlatList();
  const classes = platForms.map(item => ({ type_name: item.name, type_id: item.id }));
  const filters = {};
  platForms.forEach(item => { if (filterOptions[item.id]) filters[item.id] = filterOptions[item.id]; });
  return JSON.stringify({ class: classes, filters: filters });
}

async function homeVod() {
  try {
    const platForms = getPlatList();
    const randomPlat = platForms[Math.floor(Math.random() * platForms.length)];
    const randomArea = ruleFilterDef[randomPlat.id]?.area || '';
    const categoryResult = await category(randomPlat.id, 1, { area: randomArea }, {});
    const categoryList = safeJSONParse(categoryResult).list || [];
    return JSON.stringify({ list: categoryList.slice(0, 12) });
  } catch (e) {
    return JSON.stringify({ list: [] });
  }
}

async function category(tid, pg, filter, extend) {
  const page = pg || 1;
  extend = extend || {};
  
  const platformItem = platformList.find(p => p.id === tid);
  if (!platformItem) {
    return JSON.stringify({ list: [], page, pagecount: 1, limit: 0, total: 0 });
  }
  
  const searchKeyword = extend?.custom;
  if (searchKeyword) {
    return await cfs(tid, searchKeyword, pg);
  }
  
  const area = filter?.area || extend?.area || ruleFilterDef[tid]?.area || '';
  const videos = [];
  
  try {
    switch (tid) {
      case 'beilehu':
        videos.push(...await getBeilehuList(area, page));
        break;
      case 'tuxiaobei':
        videos.push(...await getTuxiaobeiList(area, page));
        break;
    }
  } catch (e) {}
  
  return JSON.stringify({
    list: videos,
    page: page,
    pagecount: page + 1,
    limit: videos.length,
    total: videos.length * (page + 1)
  });
}

async function detail(id) {
  try {
    const parts = id.split('@');
    const platform = parts[0];
    const did = parts.slice(1).join('@');
    
    let vod = {};
    if (platform === 'beilehu') {
      vod = await getBeilehuDetail(did);
    } else if (platform === 'tuxiaobei') {
      vod = await getTuxiaobeiDetail(did);
    }
    return JSON.stringify({ list: [vod] });
  } catch (e) {
    return JSON.stringify({ list: [] });
  }
}

async function play(flag, id, flags) {
  try {
    if (flag.includes('贝乐虎')) {
      return JSON.stringify({ parse: 0, url: id, header: headers });
    }
    
    if (flag.includes('兔小贝')) {
      try {
        const html = await request(id, { headers });
        let videoUrl = '';
        
        const srcMatch = html.match(/video-src=["']([^"']+)["']/);
        if (srcMatch) videoUrl = srcMatch[1];
        
        if (!videoUrl) {
          const sourceMatch = html.match(/<source[^>]*src=["']([^"']+)["']/);
          if (sourceMatch) videoUrl = sourceMatch[1];
        }
        
        if (!videoUrl) {
          const m3u8Match = html.match(/https?:\/\/[^"']+\.m3u8[^"']*/);
          if (m3u8Match) videoUrl = m3u8Match[0];
        }
        
        if (!videoUrl) {
          return JSON.stringify({ parse: 0, url: id, msg: '未找到播放地址' });
        }
        
        return JSON.stringify({ parse: 0, url: videoUrl, header: headers });
      } catch (e) {
        return JSON.stringify({ parse: 0, url: id, msg: `播放失败: ${e.message}` });
      }
    }
    
    return JSON.stringify({ parse: 0, url: id });
  } catch (e) {
    return JSON.stringify({ parse: 0, url: id, msg: `播放失败: ${e.message}` });
  }
}

async function cfs(siteId, wd, pg) {
  return JSON.stringify({ list: [], page: pg || 1, pagecount: 1, limit: 0, total: 0 });
}

async function search(wd, quick, pg) {
  return JSON.stringify({ list: [], page: pg || 1, pagecount: 1, limit: 0, total: 0 });
}

export function __jsEvalReturn() {
  return { init, home, homeVod, category, detail, play, search };
}