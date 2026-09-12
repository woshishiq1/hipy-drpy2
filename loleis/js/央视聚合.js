/*
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '聚合央视[视]',
  lang: 'cat'
})
*/

let siteName = '聚合央视', siteKey = '', siteType = 0;

const platformList = [
  { name: '央视新闻', id: 'xinwen' },
  { name: '央视聚场', id: 'juchang' },
  { name: '央视大全', id: 'quan' }
];

const headers = {
  'User-Agent': 'Mozilla/5.0 (Linux; Android 11; M2007J3SC Build/RKQ1.200826.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/77.0.3865.120 MQQBrowser/6.2 TBS/045714 Mobile Safari/537.36'
};

const rule = {
  xinwen: { host: 'http://api.cntv.cn', videoList: '/NewVideo/getVideoListByColumn', playUrl: 'https://cntv.playdreamer.cn/proxy/asp/hls/850/0303000a/3/default/' },
  juchang: { host: 'http://api.cntv.cn', videoList: '/NewVideo/getVideoListByColumn', playUrl: 'https://cntv.playdreamer.cn/proxy/asp/hls/850/0303000a/3/default/' },
  quan: { host: 'https://api.cntv.cn', columnSearch: '/lanmu/columnSearch', videoAlbum: '/list/getVideoAlbumList', albumDetail: '/NewVideo/getVideoListByAlbumIdNew', videoInfo: '/video/videoinfoByGuid', playUrl: 'https://cntv.playdreamer.cn/proxy/asp/hls/850/0303000a/3/default/' }
};

const filterOptions = {
  xinwen: [{ key: "area", name: "分类", value: [{ "n": "新闻直播间", "v": "TOPC1451559129520755" }, { "n": "中国新闻", "v": "TOPC1451539894330405" }, { "n": "朝闻天下", "v": "TOPC1451558496100826" }, { "n": "新闻联播", "v": "TOPC1451528971114112" }, { "n": "晚间新闻", "v": "TOPC1451528792881669" }, { "n": "午夜新闻", "v": "TOPC1451558779639282" }, { "n": "新闻30分", "v": "TOPC1451559097947700" }, { "n": "24小时", "v": "TOPC1451558428005729" }, { "n": "新闻1+1", "v": "TOPC1451559066181661" }, { "n": "海峡两岸", "v": "TOPC1451540328102649" }, { "n": "今日关注", "v": "TOPC1451540389082713" }, { "n": "今日亚洲", "v": "TOPC1451540448405749" }, { "n": "今日环球", "v": "TOPC1571034705435323" }, { "n": "新闻调查", "v": "TOPC1451558819463311" }, { "n": "军事报道", "v": "TOPC1451527941788652" }, { "n": "经济信息联播", "v": "TOPC1451533782742171" }, { "n": "体坛快讯", "v": "TOPC1451550970356385" }, { "n": "焦点访谈", "v": "TOPC1451558976694518" }, { "n": "东方时空", "v": "TOPC1451558532019883" }, { "n": "新闻周刊", "v": "TOPC1451559180488841" }, { "n": "一线", "v": "TOPC1451543462858283" }] }],
  juchang: [{ key: "area", name: "分类", value: [{ "n": "动画大放映", "v": "TOPC1451559025546574" }, { "n": "第一动画乐园", "v": "TOPC1451378857272262" }, { "n": "探索·发现", "v": "TOPC1451557893544236" }, { "n": "动物世界", "v": "TOPC1451378967257534" }, { "n": "人与自然", "v": "TOPC1451525103989666" }, { "n": "自然传奇", "v": "TOPC1451558150787467" }, { "n": "地理·中国", "v": "TOPC1451557421544786" }, { "n": "健康之路", "v": "TOPC1451557646802924" }, { "n": "百家讲坛", "v": "TOPC1451557052519584" }, { "n": "走进科学", "v": "TOPC1451558190239536" }, { "n": "是真的吗", "v": "TOPC1451534366388377" }, { "n": "故事里的中国", "v": "TOPC1451464884159276" }, { "n": "远方的家", "v": "TOPC1451541349400938" }, { "n": "跟着书本去旅行", "v": "TOPC1575253587571324" }, { "n": "今日说法", "v": "TOPC1451464665008914" }, { "n": "开讲啦", "v": "TOPC1451464884159276" }, { "n": "天网", "v": "TOPC1451530382483536" }, { "n": "高端访谈", "v": "TOPC1665739007799851" }, { "n": "对话", "v": "TOPC1514182710380601" }, { "n": "面对面", "v": "TOPC1451559038345600" }, { "n": "等着我", "v": "TOPC1451378757637200" }, { "n": "空中剧院", "v": "TOPC1451558856402351" }, { "n": "精彩音乐汇", "v": "TOPC1451541414450906" }, { "n": "音乐厅", "v": "TOPC1451534421925242" }, { "n": "民歌·中国", "v": "TOPC1451541994820527" }, { "n": "中国电影报道", "v": "TOPC1451354597100320" }, { "n": "星光大道", "v": "TOPC1451467630488780" }, { "n": "星推荐", "v": "TOPC1451469943519994" }, { "n": "方圆剧阵", "v": "TOPC1571217727564820" }, { "n": "正大综艺", "v": "TOPC1650782829200997" }, { "n": "第一时间", "v": "TOPC1451530259915198" }, { "n": "共同关注", "v": "TOPC1451558858788377" }, { "n": "经济半小时", "v": "TOPC1601362002656197" }, { "n": "经济大讲堂", "v": "TOPC1451533652476962" }, { "n": "正点财经", "v": "TOPC1453100395512779" }, { "n": "开门大吉", "v": "TOPC1451465894294259" }, { "n": "生活圈", "v": "TOPC1451546588784893" }, { "n": "生活提示", "v": "TOPC1451526037568184" }] }],
  quan: [{ key: "area", name: "分类", value: [{ "n": "栏目大全", "v": "栏目大全" }, { "n": "特别节目", "v": "特别节目" }, { "n": "纪录片", "v": "纪录片" }, { "n": "电视剧", "v": "电视剧" }, { "n": "动画片", "v": "动画片" }] }]
};

const ruleFilterDef = {
  xinwen: { area: 'TOPC1451559129520755' },
  juchang: { area: 'TOPC1451559025546574' },
  quan: { area: '栏目大全' }
};

function init(cfg) {
  siteName = cfg.skey?.split('_')[1] || cfg.skey || '聚合央视';
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

function getPlatList() { return platformList; }

async function getXinwenList(typeId, page) {
  let videos = [];
  try {
    const url = `${rule.xinwen.host}${rule.xinwen.videoList}?id=${typeId}&n=10&sort=desc&p=${page}&mode=0&serviceId=tvcctv`;
    const html = await request(url);
    const data = safeJSONParse(html);
    const list = data.data?.list || [];
    videos = list.map(item => ({ vod_id: `xinwen@${item.guid}`, vod_name: item.title || '未知视频', vod_pic: item.image || '', vod_remarks: `央视新闻 | ${item.time || ''}`, vod_content: '' }));
  } catch (e) {}
  return videos;
}

async function getJuchangList(typeId, page) {
  let videos = [];
  try {
    const url = `${rule.juchang.host}${rule.juchang.videoList}?id=${typeId}&n=10&sort=desc&p=${page}&mode=0&serviceId=tvcctv`;
    const html = await request(url);
    const data = safeJSONParse(html);
    const list = data.data?.list || [];
    videos = list.map(item => ({ vod_id: `juchang@${item.guid}`, vod_name: item.title || '未知视频', vod_pic: item.image || '', vod_remarks: `央视聚场 | ${item.time || ''}`, vod_content: '' }));
  } catch (e) {}
  return videos;
}

async function getQuanList(typeId, page) {
  let videos = [];
  try {
    const channelMap = { "特别节目": "CHAL1460955953877151", "纪录片": "CHAL1460955924871139", "电视剧": "CHAL1460955853485115", "动画片": "CHAL1460955899450127" };
    
    if (typeId === '栏目大全') {
      const url = `${rule.quan.host}${rule.quan.columnSearch}?p=${page}&n=20&serviceId=tvcctv&t=json`;
      const html = await request(url);
      const data = safeJSONParse(html);
      const docs = data.response?.docs || [];
      videos = docs.map(item => ({ vod_id: `quan@${item.lastVIDE?.videoSharedCode}|${item.column_firstclass}|${item.column_name}|${item.channel_name}|${item.column_brief}|${item.column_logo}|${item.lastVIDE?.videoTitle}|栏目大全`, vod_name: item.column_name || '未知栏目', vod_pic: item.column_logo || '', vod_remarks: `央视大全 | ${item.channel_name || ''}`, vod_content: item.column_brief || '' }));
    } else {
      const params = { p: page, n: 24, serviceId: 'tvcctv', t: 'json', channelid: channelMap[typeId] || '', fc: encodeURIComponent(typeId) };
      const queryString = Object.keys(params).map(key => `${key}=${params[key]}`).join('&');
      const url = `${rule.quan.host}${rule.quan.videoAlbum}?${queryString}`;
      const html = await request(url);
      const data = safeJSONParse(html);
      const list = data.data?.list || [];
      videos = list.map(item => ({ vod_id: `quan@${item.id}|${item.sc}|${item.title}|${item.channel}|${item.brief}|${item.image}|${item.count}|${typeId}`, vod_name: item.title || '未知视频', vod_pic: item.image || '', vod_remarks: `央视大全 | ${item.sc || ''}${item.year ? '·' + item.year : ''}${item.area ? '·' + item.area : ''}`, vod_content: item.brief || '' }));
    }
  } catch (e) {}
  return videos;
}

async function getXinwenDetail(id) {
  return { vod_id: id, vod_name: '', vod_remarks: '', vod_play_from: '央视新闻', vod_play_url: `点击播放$${id}` };
}

async function getJuchangDetail(id) {
  return { vod_id: id, vod_name: '', vod_remarks: '', vod_play_from: '央视聚场', vod_play_url: `点击播放$${id}` };
}

async function getQuanDetail(did) {
  let vod = {};
  try {
    const info = did.split("|");
    const cate = info[7];
    const ctid = info[0];
    const modeMap = { "特别节目": "0", "纪录片": "0", "电视剧": "0", "动画片": "1" };
    const mode = modeMap[cate] || '0';
    const albumUrl = `${rule.quan.host}${rule.quan.albumDetail}?id=${ctid}&serviceId=tvcctv&p=1&n=100&mode=${mode}&pub=1`;
    const html = await request(albumUrl);
    const data = safeJSONParse(html);
    let playUrls = [];
    if (data.errcode === '1001') {
      const videoInfoUrl = `${rule.quan.host}${rule.quan.videoInfo}?guid=${ctid}&serviceId=tvcctv`;
      const vInfoRes = await request(videoInfoUrl);
      const vInfoData = safeJSONParse(vInfoRes);
      const realCtid = vInfoData.ctid;
      const columnUrl = `${rule.quan.host}/NewVideo/getVideoListByColumn?id=${realCtid}&d=&p=1&n=100&sort=desc&mode=0&serviceId=tvcctv&t=json`;
      const colRes = await request(columnUrl);
      const colData = safeJSONParse(colRes);
      playUrls = colData.data?.list || [];
    } else {
      playUrls = data.data?.list || [];
    }
    const playList = playUrls.map(item => { const title = item.title || `第${item.index || '?'}集`; const cleanTitle = title.replace(/\$/g, ''); const guid = item.guid || ''; return `${cleanTitle}$${guid}`; });
    vod = { vod_id: did, vod_name: info[2] || '', vod_pic: info[5] || '', vod_content: info[4] || '', vod_remarks: info[6] ? `共${info[6]}集` : '', vod_play_from: playList.length > 0 ? '央视大全' : '', vod_play_url: playList.length > 0 ? playList.join('#') : '' };
  } catch (e) {}
  return vod;
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
    case 'xinwen': videos.push(...await getXinwenList(area, page)); break;
    case 'juchang': videos.push(...await getJuchangList(area, page)); break;
    case 'quan': videos.push(...await getQuanList(area, page)); break;
  }
  return JSON.stringify({ list: videos, page: page, pagecount: page + 1, limit: videos.length, total: videos.length * (page + 1) });
}

async function detail(id) {
  const parts = id.split('@');
  const platform = parts[0];
  const did = parts.slice(1).join('@');
  let vod = {};
  if (platform === 'xinwen') vod = await getXinwenDetail(did);
  else if (platform === 'juchang') vod = await getJuchangDetail(did);
  else if (platform === 'quan') vod = await getQuanDetail(did);
  return JSON.stringify({ list: [vod] });
}

async function play(flag, id, flags) {
  const playUrl = `${rule.xinwen.playUrl}${id}/850.m3u8`;
  return JSON.stringify({ parse: 0, url: playUrl, header: headers });
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