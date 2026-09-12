/*
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '聚合知识[知]',
  lang: 'cat'
})
*/

let siteName = '聚合知识', siteKey = '', siteType = 0;

const platformList = [
  { name: '古诗鉴赏', id: 'gushi' },
  { name: '博看听书', id: 'bokan' },
  { name: '科学辟谣', id: 'kepu' }
];

const headers = {
  'User-Agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36'
};

const rule = {
  gushi: { host: 'http://dbfm.taikeji.com', cateApi: '/v1/poemcate', poemApi: '/v1/poem' },
  bokan: { host: 'https://api.bookan.com.cn', bookList: '/voice/book/list', albumUnits: '/voice/album/units', searchApi: 'https://es.bookan.com.cn/api/v3/voice/book' },
  kepu: { host: 'https://piyao.kepuchina.cn', mediaList: '/h5/ajaxGetMediaList', videoDetail: '/h5/videodetail' }
};

const filterOptions = {
  gushi: [{ key: "area", name: "分类", value: [{ "n": "分类", "v": "543" }, { "n": "诗人", "v": "552" }, { "n": "朝代", "v": "547" }] }],
  bokan: [{ key: "area", name: "分类", value: [{ "n": "少年读物", "v": "1305" }, { "n": "儿童文学", "v": "1304" }, { "n": "国学经典", "v": "1320" }, { "n": "文艺少年", "v": "1306" }, { "n": "育儿心经", "v": "1309" }, { "n": "心理哲学", "v": "1310" }, { "n": "青春励志", "v": "1307" }, { "n": "历史小说", "v": "1312" }, { "n": "故事会", "v": "1303" }, { "n": "音乐戏剧", "v": "1317" }, { "n": "相声评书", "v": "1319" }] }],
  kepu: [{ key: "area", name: "分类", value: [{ "n": "科学辟谣", "v": "2" }] }]
};

const ruleFilterDef = {
  gushi: { area: '543' },
  bokan: { area: '1309' },
  kepu: { area: '2' }
};

function init(cfg) {
  siteName = cfg.skey?.split('_')[1] || cfg.skey || '聚合知识';
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

function getDate(time) {
  let date = new Date(parseInt(time) * 1000);
  let y = date.getFullYear();
  let MM = date.getMonth() + 1;
  MM = MM < 10 ? ('0' + MM) : MM;
  let d = date.getDate();
  d = d < 10 ? ('0' + d) : d;
  let h = date.getHours();
  h = h < 10 ? ('0' + h) : h;
  let m = date.getMinutes();
  m = m < 10 ? ('0' + m) : m;
  let s = date.getSeconds();
  s = s < 10 ? ('0' + s) : s;
  return y + '-' + MM + '-' + d + ' ' + h + ':' + m + ':' + s;
}

function getPlatList() { return platformList; }

async function getGushiList(typeId, page) {
  let videos = [];
  try {
    const cateHtml = await request(rule.gushi.host + rule.gushi.cateApi + '?channel=znds&deviceid=d652f03ce6c89719886dc199c0724b19&model=V1990A&packagename=com.monster.tvfm&random=1727208873340&sdkinfo=10&sdkint=29&vcode=2&vname=1.0.1');
    const cateData = safeJSONParse(cateHtml).data;
    for (const a of cateData) {
      if (a.id == typeId) {
        const items = a.items[0]?.items || [];
        videos = items.map(b => ({ vod_id: `gushi@${typeId},${a.items[0].id},${b.id}`, vod_name: b.title || '未知古诗', vod_pic: b.pic || '', vod_remarks: '古诗鉴赏', vod_content: '' }));
        break;
      }
    }
  } catch (e) {}
  return videos;
}

async function getBokanList(typeId, page) {
  let videos = [];
  try {
    const url = `${rule.bokan.host}${rule.bokan.bookList}?instance_id=25304&page=${page}&category_id=${typeId}&num=24`;
    const html = await request(url);
    const data = safeJSONParse(html).data;
    const books = data.list || [];
    videos = books.map(book => ({ vod_id: `bokan@${book.id}`, vod_name: book.name || '未知书籍', vod_pic: book.cover || '', vod_remarks: `博看 | ${book.extra?.author || ''}`, vod_content: book.extra?.description || '' }));
  } catch (e) {}
  return videos;
}

async function getKepuList(typeId, page) {
  let videos = [];
  try {
    const url = `${rule.kepu.host}${rule.kepu.mediaList}?page=${page}&page_type=${typeId}&title=`;
    const html = await request(url);
    const data = safeJSONParse(html).data;
    const list = data.list || [];
    videos = list.map(it => {
      const keywords = it.keywords?.map(i => i.keyword).join('、') || '';
      return { vod_id: `kepu@${it.id}&${getDate(it.discern_time)}&${keywords}&${it.audit_info}&${it.title_pre}&${it.origin}`, vod_name: it.title || '未知视频', vod_pic: it.cover || '', vod_remarks: `科学辟谣 | ${getDate(it.discern_time)}`, vod_content: it.title_pre || '' };
    });
  } catch (e) {}
  return videos;
}

async function getGushiDetail(id) {
  let vod = {};
  try {
    const url = `${rule.gushi.host}${rule.gushi.poemApi}?cateid=${id}&limit=100&page=1`;
    const html = await request(url);
    const data = safeJSONParse(html).data.list || [];
    const playUrls = data.map(it => `${it.title}-${it.dynasty}-${it.author}$${it.source}`).join('#');
    vod = { vod_id: id, vod_name: '古诗选集', vod_pic: '', vod_content: `共${data.length}首古诗`, vod_remarks: '古诗鉴赏', vod_play_from: "古诗鉴赏", vod_play_url: playUrls };
  } catch (e) {}
  return vod;
}

async function getBokanDetail(id) {
  let vod = {};
  try {
    const url = `${rule.bokan.host}${rule.bokan.albumUnits}?album_id=${id}&page=1&num=200&order=1`;
    const html = await request(url);
    const data = safeJSONParse(html).data;
    const list = data.list || [];
    const playUrls = list.map(b => { const name = b.title.trim().replace(/<|>|《|》/g, '').replace(/\$|#/g, ' ').trim(); return `${name}$${b.file}`; }).join('#');
    vod = { vod_id: id, vod_name: '', vod_pic: '', vod_content: '', vod_remarks: `共${list.length}集`, vod_play_from: "博看听书", vod_play_url: playUrls, audio: 1 };
  } catch (e) {}
  return vod;
}

async function getKepuDetail(id) {
  let vod = {};
  try {
    const parts = id.split('&');
    const vodId = parts[0];
    const date = parts[1];
    const keywords = parts[2];
    const actor = parts[3];
    const content = parts[4];
    const origin = parts[5];
    vod = { vod_id: id, vod_name: '科学辟谣视频', vod_pic: '', vod_content: content || '', vod_actor: actor || '', vod_year: date || '', vod_type: origin || '', vod_remarks: `关键词：${keywords || ''}`, vod_play_from: "科学辟谣", vod_play_url: `点击播放$${vodId}` };
  } catch (e) {}
  return vod;
}

async function searchBokan(wd, page) {
  const results = [];
  try {
    const url = `${rule.bokan.searchApi}?instanceId=25304&keyword=${encodeURIComponent(wd)}&pageNum=${page}&limitNum=20`;
    const html = await request(url);
    const data = safeJSONParse(html).data;
    const books = data.list || [];
    results.push(...books.map(book => ({ vod_id: `bokan@${book.id}`, vod_name: book.name || '未知书籍', vod_pic: book.cover || '', vod_remarks: `博看 | ${book.extra?.author || ''}`, vod_content: book.extra?.description || '' })));
  } catch (e) {}
  return results;
}

async function searchKepu(wd, page) {
  const results = [];
  try {
    const url = `${rule.kepu.host}${rule.kepu.mediaList}?page=${page}&page_type=2&title=${encodeURIComponent(wd)}`;
    const html = await request(url);
    const data = safeJSONParse(html).data;
    const list = data.list || [];
    results.push(...list.map(it => { const keywords = it.keywords?.map(i => i.keyword).join('、') || ''; return { vod_id: `kepu@${it.id}&${getDate(it.discern_time)}&${keywords}&${it.audit_info}&${it.title_pre}&${it.origin}`, vod_name: it.title || '未知视频', vod_pic: it.cover || '', vod_remarks: `科学辟谣 | ${getDate(it.discern_time)}`, vod_content: it.title_pre || '' }; }));
  } catch (e) {}
  return results;
}

async function home(filter) {
  const platForms = getPlatList();
  const classes = platForms.map(item => ({ type_name: item.name, type_id: item.id, type_flag: '[CFS][SUBSITE2][FILTERBAR]' }));
  const filters = {};
  platForms.forEach(item => { if (filterOptions[item.id]) filters[item.id] = filterOptions[item.id]; });
  return JSON.stringify({ class: classes, filters: filters });
}

async function homeVod() {
  const platForms = getPlatList();
  const randomPlat = platForms[Math.floor(Math.random() * platForms.length)];
  const randomArea = ruleFilterDef[randomPlat.id]?.area || '';
  const categoryResult = await category(randomPlat.id, 1, { area: randomArea }, {});
  const categoryList = safeJSONParse(categoryResult).list || [];
  return JSON.stringify({ list: categoryList });
}

async function category(tid, pg, filter, extend) {
  const page = pg || 1;
  extend = extend || {};
  const platformItem = platformList.find(p => p.id === tid);
  if (!platformItem) return JSON.stringify({ list: [], page, pagecount: 1, limit: 0, total: 0 });
  const searchKeyword = extend?.custom;
  if (searchKeyword) return await cfs(tid, searchKeyword, pg);
  const area = filter?.area || extend?.area || ruleFilterDef[tid]?.area || '';
  const videos = [];
  switch (tid) {
    case 'gushi': videos.push(...await getGushiList(area, page)); break;
    case 'bokan': videos.push(...await getBokanList(area, page)); break;
    case 'kepu': videos.push(...await getKepuList(area, page)); break;
  }
  return JSON.stringify({ list: videos, page: page, pagecount: page + 1, limit: videos.length, total: videos.length * (page + 1) });
}

async function detail(id) {
  const parts = id.split('@');
  const platform = parts[0];
  const did = parts.slice(1).join('@');
  let vod = {};
  if (platform === 'gushi') vod = await getGushiDetail(did);
  else if (platform === 'bokan') vod = await getBokanDetail(did);
  else if (platform === 'kepu') vod = await getKepuDetail(did);
  return JSON.stringify({ list: [vod] });
}

async function play(flag, id, flags) {
  if (flag.includes('古诗')) return JSON.stringify({ parse: 0, url: id });
  if (flag.includes('博看')) return JSON.stringify({ parse: 0, url: id });
  if (flag.includes('科学辟谣')) {
    try {
      const detailUrl = `${rule.kepu.host}${rule.kepu.videoDetail}?id=${id}`;
      const html = await request(detailUrl);
      let videoUrl = '';
      const srcMatch = html.match(/src="([^"]+\.mp4[^"]*)"/);
      if (srcMatch) videoUrl = srcMatch[1];
      if (!videoUrl) {
        const sourceMatch = html.match(/<source[^>]*src=["']([^"']+)["']/);
        if (sourceMatch) videoUrl = sourceMatch[1];
      }
      return JSON.stringify({ parse: 0, url: videoUrl || '', header: headers });
    } catch (e) {
      return JSON.stringify({ parse: 0, url: id });
    }
  }
  return JSON.stringify({ parse: 0, url: id });
}

async function cfs(siteId, wd, pg) {
  const page = pg || 1;
  let results = [];
  if (siteId === 'gushi') results = [];
  else if (siteId === 'bokan') results = await searchBokan(wd, page);
  else if (siteId === 'kepu') results = await searchKepu(wd, page);
  return JSON.stringify({ list: results, page: page, pagecount: page + 1, limit: results.length, total: results.length * (page + 1) });
}

async function search(wd, quick, pg) {
  const videos = [];
  const page = pg || 1;
  const bokanResults = await searchBokan(wd, page);
  const kepuResults = await searchKepu(wd, page);
  videos.push(...bokanResults, ...kepuResults);
  return JSON.stringify({ list: videos, page: page, pagecount: page + 1, limit: videos.length, total: videos.length * (page + 1) });
}

export function __jsEvalReturn() {
  return { init, home, homeVod, category, detail, play, search };
}