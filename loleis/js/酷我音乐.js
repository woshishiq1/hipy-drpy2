/*
@header({
  searchable: 2,
  filterable: 1,
  quickSearch: 0,
  title: '酷我[听]',
  author: 'EylinSir',
  '类型': '音乐',
  logo: 'https://pic.qqtf.com/up/2025-11/20251127175478238.png',
  lang: 'cat'
})
*/

let siteName = '酷我', siteKey = '', siteType = 0;
let host = 'http://wapi.kuwo.cn';

function init(cfg) {
  siteName = cfg.skey?.split('_')[1] || cfg.skey || '听海';
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
  const reqHeaders = { 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36', ...options.headers };
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

function sleep(seconds) {
  return new Promise(resolve => setTimeout(resolve, seconds * 1000));
}

function hd(img) {
  if (!img) return '';
  return img.replace('/120/', '/4000/').replace('/500/', '/2160/').replace('/150/', '/1000/').replace('/300/', '/1500/');
}

function generateFilters() {
  return {
    "12": [{ key: "type", name: "专区", value: [{ "n": "国风专区", "v": "12" }, { "n": "老歌专区", "v": "13" }, { "n": "BGM专区", "v": "143" }, { "n": "伤感专区", "v": "147" }] }],
    "2189": [{ key: "type", name: "主题", value: [{ "n": "抖音", "v": "2189" }, { "n": "经典", "v": "1265" }, { "n": "情歌", "v": "2200" }, { "n": "BGM", "v": "2199" }, { "n": "演唱会", "v": "2212" }, { "n": "游戏", "v": "1877" }, { "n": "怀旧", "v": "155" }, { "n": "合唱", "v": "2201" }, { "n": "网络", "v": "621" }, { "n": "儿童", "v": "171" }, { "n": "ACG", "v": "181" }, { "n": "影视", "v": "180" }, { "n": "网红", "v": "1879" }, { "n": "春节", "v": "2190" }, { "n": "翻唱", "v": "1848" }] }],
    "146": [{ key: "type", name: "心情", value: [{ "n": "伤感", "v": "146" }, { "n": "解压", "v": "62" }, { "n": "励志", "v": "58" }, { "n": "开心", "v": "143" }, { "n": "甜蜜", "v": "137" }, { "n": "兴奋", "v": "139" }, { "n": "安静", "v": "67" }, { "n": "思念", "v": "160" }] }],
    "376": [{ key: "type", name: "场景", value: [{ "n": "开车", "v": "376" }, { "n": "运动", "v": "366" }, { "n": "睡眠", "v": "354" }, { "n": "跳舞", "v": "378" }, { "n": "学习", "v": "1876" }, { "n": "清晨", "v": "353" }, { "n": "KTV", "v": "361" }, { "n": "店铺专用", "v": "263" }, { "n": "校园", "v": "382" }, { "n": "旅行", "v": "375" }, { "n": "工作", "v": "386" }, { "n": "广场舞", "v": "334" }, { "n": "通勤", "v": "2202" }, { "n": "宅家", "v": "2203" }, { "n": "Citywalk", "v": "2214" }, { "n": "露营", "v": "2213" }] }],
    "637": [{ key: "type", name: "年代", value: [{ "n": "70后", "v": "637" }, { "n": "80后", "v": "638" }, { "n": "90后", "v": "639" }, { "n": "00后", "v": "640" }] }],
    "393": [{ key: "type", name: "曲风", value: [{ "n": "流行", "v": "393" }, { "n": "DJ", "v": "168" }, { "n": "古风", "v": "127" }, { "n": "佛乐", "v": "220" }, { "n": "轻音乐", "v": "173" }, { "n": "纯音乐", "v": "577" }, { "n": "电子", "v": "391" }, { "n": "喊麦", "v": "216" }, { "n": "3D", "v": "1366" }, { "n": "器乐", "v": "578" }, { "n": "摇滚", "v": "389" }, { "n": "民歌", "v": "1921" }, { "n": "民谣", "v": "392" }, { "n": "古典", "v": "390" }, { "n": "嘻哈", "v": "387" }, { "n": "乡村", "v": "399" }, { "n": "爵士", "v": "397" }, { "n": "R&B", "v": "394" }] }],
    "37": [{ key: "type", name: "语言", value: [{ "n": "华语", "v": "37" }, { "n": "欧美", "v": "35" }, { "n": "韩语", "v": "1093" }, { "n": "粤语", "v": "13" }, { "n": "日语", "v": "1091" }, { "n": "小语种", "v": "12" }] }]
  };
}

async function getLyric(rid) {
  const maxRetries = 20;
  for (let retryCount = 0; retryCount < maxRetries; retryCount++) {
    try {
      let url = `https://kuwo.cn/openapi/v1/www/lyric/getlyric?musicId=${rid}`;
      let html = await request(url);
      if (html) {
        let json = safeJSONParse(html);
        if (json.code === 200 && json.data && json.data.lrclist && json.data.lrclist.length > 0) {
          let lrclist = json.data.lrclist;
          let lyric = lrclist.map(item => {
            let time = parseFloat(item.time) || 0;
            let min = Math.floor(time / 60).toString().padStart(2, '0');
            let sec = Math.floor(time % 60).toString().padStart(2, '0');
            let ms = Math.floor((time % 1) * 100).toString().padStart(2, '0');
            return `[${min}:${sec}.${ms}]${item.lineLyric || ''}`;
          }).join('\n');
          return lyric;
        }
      }
    } catch (e) {}
    if (retryCount < maxRetries - 1) await sleep(0.01);
  }
  return '暂无歌词';
}

async function getUrl(rid, br) {
  let url = `https://nmobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayer_ar_4.4.2.7_B_nuoweida_vh.apk&type=convert_url_with_sign&rid=${rid}&format=flac&br=${br}`;
  let html = await request(url);
  if (html) {
    let j = safeJSONParse(html);
    return j?.data?.url?.trim() || '';
  }
  return '';
}

function home(filter) {
  return JSON.stringify({
    class: [
      { type_id: '12', type_name: '专区' }, { type_id: '2189', type_name: '主题' },
      { type_id: '146', type_name: '心情' }, { type_id: '376', type_name: '场景' },
      { type_id: '637', type_name: '年代' }, { type_id: '393', type_name: '曲风流派' },
      { type_id: '37', type_name: '语言' }
    ],
    filters: generateFilters()
  });
}

async function homeVod() {
  let url = `${host}/api/pc/classify/playlist/getRcmPlayList?pn=1&rn=30&order=hot`;
  let html = await request(url);
  let res = safeJSONParse(html);
  let data = res.data?.data || [];
  let videos = data.map(it => ({ vod_id: (it.id || '').toString(), vod_name: it.name || '未命名歌单', vod_pic: hd(it.img), vod_remarks: '🎧' + (it.listencnt || '0') }));
  return JSON.stringify({ list: videos });
}

async function category(tid, pg, filter, extend) {
  if (pg <= 0 || typeof pg == 'undefined') pg = 1;
  const id = extend?.type || tid;
  let url = `${host}/api/pc/classify/playlist/getTagPlayList?pn=${pg}&rn=30&id=${id}`;
  let html = await request(url);
  let res = safeJSONParse(html);
  let data = res.data?.data || [];
  let videos = data.map(it => ({ vod_id: (it.id || '').toString(), vod_name: it.name || '未命名歌单', vod_pic: hd(it.img), vod_remarks: '🎧' + (it.listencnt || '0') }));
  return JSON.stringify({ page: parseInt(pg), pagecount: 999, limit: 30, total: 999, list: videos });
}

async function detail(id) {
  let input = id.toString();
  
  if (input.indexOf('$') > -1) {
    let s = input.split('$');
    return JSON.stringify({ list: [{ vod_id: s[1], vod_name: s[0], vod_pic: hd(s[2]), vod_play_from: '听海单曲', vod_play_url: s[0] + '$' + s[1], vod_play_pic: hd(s[2]), vod_play_pic_ratio: 1.0 }] });
  }

  const limit = 100;
  let baseUrl = `${host}/api/www/playlist/playListInfo?pid=${input}&rn=${limit}&httpsStatus=1&pn=`;
  let html = await request(baseUrl + '1');
  let json = safeJSONParse(html);
  let data = json.data || {};
  let songs = data.musicList || data.musiclist || [];
  let total = parseInt(data.total || 0);

  if (total > limit) {
    let tasks = [];
    for (let p = 2; p <= Math.min(Math.ceil(total / limit), 5); p++) {
      tasks.push(request(baseUrl + p));
    }
    let results = await Promise.all(tasks);
    results.forEach(r => {
      let d = safeJSONParse(r).data || {};
      songs = songs.concat(d.musicList || d.musiclist || []);
    });
  }

  let playArr = [];
  let songPicArr = [];
  songs.forEach(it => {
    let rid = (it.rid || it.musicrid || '').toString().replace('MUSIC_', '');
    let song = (it.name || '').replace(/&nbsp;/g, ' ');
    let artist = (it.artist || '').replace(/&nbsp;/g, ' ');
    let albumpic = hd(it.albumpic || it.pic);
    let displayName = artist ? `${song} [${artist}]` : song;
    if (rid) {
      playArr.push(`${displayName}$${rid}&&${albumpic}&&${albumpic}`);
      songPicArr.push(albumpic);
    }
  });
  
  const vod = { vod_id: input, vod_name: data.name || '酷我歌单', vod_pic: hd(data.img || data.img500), vod_content: data.info || '', vod_remarks: '听海歌单', vod_play_from: "听海歌单", vod_play_url: playArr.join('#'), vod_play_pic: songPicArr.join('#'), vod_play_pic_ratio: 1.0 };
  
  return JSON.stringify({ list: [vod] });
}

async function play(flag, id, flags) {
  let parts = id.split('&&');
  let firstPart = parts[0] || '';
  let firstParts = firstPart.split('$');
  let songId = firstParts.length > 1 ? firstParts[1] : firstParts[0];
  let albumPic = hd(parts[1]);
  
  if (/\.(m3u8|mp4|m4a|mp3|aac|flac|ogg|mgg)(\?|$)/i.test(songId)) {
    let cleanUrl = songId.split('?')[0];
    return JSON.stringify({ parse: 0, url: cleanUrl, pic: albumPic, cover: albumPic, lrc: '', height: 720 });
  }
  
  const qualities = [{ name: 'FLAC无损', br: '2000k' }, { name: 'HQ高品质', br: '320k' }, { name: '标准品质', br: '192k' }, { name: 'AAC高品', br: '128k' }];
  let urls = [];
  let seenUrls = new Set();
  
  for (let q of qualities) {
    let url = await getUrl(songId, q.br);
    if (url && !url.includes('.mgg')) {
      let cleanUrl = url.split('?')[0];
      if (!seenUrls.has(cleanUrl)) {
        seenUrls.add(cleanUrl);
        urls.push(q.name, cleanUrl);
      }
    }
  }
  
  let lrcPromise = getLyric(songId);
  let picUrl = albumPic;
  if (!picUrl) {
    try {
      let picRes = await request(`http://artistpicserver.kuwo.cn/pic.web?type=rid_pic&pictype=url&size=500&rid=${songId}`);
      picUrl = picRes.trim().replace('/500/', '/2160/');
    } catch (e) {}
  }
  
  let result = { parse: 0, url: urls, header: { 'User-Agent': 'Mozilla/5.0' }, pic: picUrl, cover: picUrl, height: 720 };
  let lrc = await lrcPromise;
  if (lrc && lrc !== '暂无歌词') result.lrc = lrc;
  return JSON.stringify(result);
}

async function search(wd, quick, pg) {
  if (pg <= 0 || typeof pg == 'undefined') pg = 1;
  let searchUrl = `https://search.kuwo.cn/r.s?client=kt&all=${encodeURIComponent(wd)}&pn=${(pg - 1) * 30}&rn=30&vipver=1&ft=music&encoding=utf8&rformat=json&mobi=1`;
  let html = '';
  while (!html) {
    html = await request(searchUrl);
    if (!html) await sleep(0.1);
  }
  let json = safeJSONParse(html.replace(/'/g, '"'));
  let videos = [];
  if (json.abslist) {
    json.abslist.forEach(it => {
      let rid = it.DC_TARGETID || it.MUSICRID?.replace('MUSIC_', '') || '';
      let pic = it.web_albumpic_short ? `http://img1.kuwo.cn/star/albumcover/${it.web_albumpic_short}` : (it.hts_MVPIC || '');
      videos.push({ vod_id: `${it.SONGNAME} - ${it.ARTIST}$${rid}$${pic}`, vod_name: `${it.SONGNAME} - ${it.ARTIST}`, vod_pic: hd(pic), vod_remarks: it.ALBUM || '酷我音乐' });
    });
  }
  return JSON.stringify({ page: parseInt(pg), pagecount: 999, limit: 30, total: 999, list: videos });
}

async function action(action, value) {
  if (action == '最新评论') {
    return JSON.stringify({ action: { type: 'comment', actionId: '最新评论', title: '最新评论', subtitle: '暂不支持评论功能', remarks: '评论功能开发中', list: [{ id: '功能提示', title: '暂不支持评论', subtitle: '', logo: '', content: '酷我音乐评论功能正在开发中...', remarks: '', remarks2: '' }] } });
  }
  return '';
}

export function __jsEvalReturn() {
  return { init, home, homeVod, category, detail, play, search, action };
}