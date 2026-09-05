import req from '../../util/req.js';
import crypto from 'crypto';

let host="https://accfanan.x18c87so.work";
let token="eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI2NTgxMjQ2NyIsImlhdCI6MTc4NjY0NjkwOCwibmJmIjoxNzg2NjY0OTIyLCJleHAiOjE5NDQzNDQ5MjJ9.7poZoAttovGH_UnkM0ZKYVjExOVGc8Uh5U62TVVQNuE";
let did="h5_7c768c18bd97473c9f9d23b25c21f";
let imgD="https://wiuuh1425js3.iumigc.com/";
let UA="Mozilla/5.0 (Linux; Android 12; SM-G9750 Build/SP1A.210812.016; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/89.0.4389.72 Mobile Safari/537.36";
let pages={},index={};
let catMap={jx:"4",dm:"2",lifan:"24",rebao:"53",luanlun:"27",guochan:"28",wanghuang:"30",luoli:"52",av:"57",chuanmei:"58",zhongkou:"59",manhua:"5"};
let comicClass={"":"1","最新":"1","热门推荐":"21","韩漫":"2","同人":"6","独家":"17","国漫":"11","日漫":"10","3D":"3","单行本":"7","CG/AI":"15","COS写真":"5","BL":"19"};
function nv(n,v){return{n,v}}
function fv(n,k,a){return{key:k,name:n,value:a}}
let filters={
jx:[
fv("分类","jxType",[nv("全部",""),nv("短视频","short"),nv("小说","fiction")]),
fv("短视频","shortMode",[nv("发现","find"),nv("推荐","rec")]),
fv("剧情","shortPlot",[nv("伦理","42"),nv("少女","43"),nv("泄露","44"),nv("网红","45"),nv("窥视","46"),nv("抖音风","54")]),
fv("小说","fictionType",[nv("普通","1"),nv("有声","2")]),
fv("普通标签","tag1",[nv("学生妹","1"),nv("处女","2"),nv("偷情","3"),nv("淫荡","4"),nv("潜规则","5"),nv("制服丝袜","6"),nv("人妻","7"),nv("3P/多P","8")]),
fv("普通标签","tag1",[nv("车厢","9"),nv("调教","10"),nv("乱伦","11"),nv("强暴","12"),nv("教师","15"),nv("办公室","16"),nv("古典","18"),nv("美女","19")]),
fv("普通标签","tag1",[nv("空姐","27"),nv("另类","564")]),
fv("有声标签","tag2",[nv("音频小说","29"),nv("调教","31"),nv("淫荡","32"),nv("人妻","33"),nv("偷情","34"),nv("学生妹","35"),nv("古典","36"),nv("乱伦","37")]),
fv("有声标签","tag2",[nv("强暴","38"),nv("3P/多P","39"),nv("制服丝袜","40"),nv("教师","41"),nv("办公室","42"),nv("车厢","43"),nv("空姐","54")])
],
dm:[fv("分类","videoTag",[nv("全部",""),nv("同人","同人"),nv("国漫","国漫"),nv("3D","3D"),nv("MMD","MMD"),nv("原神","原神"),nv("崩坏3","崩坏3"),nv("番剧","番剧")])],
rebao:[fv("分类","videoTag",[nv("全部",""),nv("熟女肥逼","熟女肥逼"),nv("人妖伪娘","人妖伪娘"),nv("美胸巨乳","美胸巨乳"),nv("探花偷拍","探花偷拍"),nv("少女萝莉","少女萝莉"),nv("强奸迷奸","强奸迷奸")]),fv("分类","videoTag",[nv("多人群p","多人群p"),nv("调教SM","调教SM"),nv("泄露流出","泄露流出"),nv("媚黑骚逼","媚黑骚逼"),nv("孕妇做爱","孕妇做爱"),nv("校园霸凌","校园霸凌")])],
luanlun:[fv("分类","videoTag",[nv("全部",""),nv("父女","父女"),nv("母子","母子"),nv("兄妹","兄妹"),nv("姐弟","姐弟"),nv("岳母","岳母"),nv("嫂子","嫂子")]),fv("分类","videoTag",[nv("侄女","侄女"),nv("师生","师生"),nv("小姨子","小姨子"),nv("小马拉大车","小马拉大车")])],
guochan:[fv("分类","videoTag",[nv("全部",""),nv("情侣自拍","情侣自拍"),nv("三级片","三级片"),nv("户外露出","户外露出"),nv("颜值女神","颜值女神"),nv("反差婊","反差婊"),nv("明星换脸","明星换脸")]),fv("分类","videoTag",[nv("推油按摩","推油按摩"),nv("网红博主","网红博主"),nv("偷情出轨","偷情出轨"),nv("主播大秀","主播大秀"),nv("真实换妻","真实换妻"),nv("合集盘点","合集盘点")])],
wanghuang:[fv("分类","videoTag",[nv("全部",""),nv("白桃少女","白桃少女"),nv("台北娜娜","台北娜娜"),nv("柚子猫","柚子猫"),nv("桥本香菜","桥本香菜"),nv("饼干姐姐","饼干姐姐"),nv("小欣奈","小欣奈")]),fv("分类","videoTag",[nv("御梦子","御梦子"),nv("捅主任","捅主任"),nv("黑椒盖饭","黑椒盖饭"),nv("冉冉学姐","冉冉学姐"),nv("鸡教练","鸡教练"),nv("唐伯虎","唐伯虎"),nv("咪妮","咪妮")]),fv("分类","videoTag",[nv("玩偶姐姐","玩偶姐姐"),nv("情深叉喔","情深叉喔"),nv("水冰月","水冰月"),nv("米胡桃","米胡桃"),nv("白菜妹妹","白菜妹妹"),nv("二代cc","二代cc")])],
luoli:[fv("分类","videoTag",[nv("全部",""),nv("护士","护士"),nv("白虎嫩妹","白虎嫩妹"),nv("女仆","女仆"),nv("cosplay","cosplay"),nv("洛丽塔","洛丽塔"),nv("JK学生","JK学生")]),fv("分类","videoTag",[nv("丝袜美腿","丝袜美腿"),nv("激情自慰","激情自慰"),nv("空姐","空姐"),nv("泳装","泳装"),nv("职场OL","职场OL"),nv("骚萝破处","骚萝破处")])],
av:[fv("分类","videoTag",[nv("全部",""),nv("最新AV","最新AV"),nv("人妻偷情","人妻偷情"),nv("暗黑迷奸","暗黑迷奸"),nv("日本JK","日本JK"),nv("无码破解","无码破解"),nv("中文AV","中文AV"),nv("FC2","FC2"),nv("重口AV","重口AV")])],
chuanmei:[fv("分类","videoTag",[nv("全部",""),nv("麻豆传媒","麻豆传媒"),nv("jvid","jvid"),nv("蜜桃传媒","蜜桃传媒"),nv("天美传媒","天美传媒"),nv("糖心vlog","糖心vlog")]),fv("分类","videoTag",[nv("性视界","性视界"),nv("91制片厂","91制片厂"),nv("兔子先生","兔子先生"),nv("星空传媒","星空传媒"),nv("大象传媒","大象传媒"),nv("香蕉传媒","香蕉传媒")])],
zhongkou:[fv("分类","videoTag",[nv("全部",""),nv("屎尿","屎尿"),nv("四爱","四爱"),nv("血腥暴力","血腥暴力"),nv("肛交菊花","肛交菊花"),nv("道具","道具"),nv("捆绑","捆绑"),nv("男同真爱","男同真爱"),nv("虐待","虐待"),nv("人兽","人兽"),nv("踩踏虐鸡","踩踏虐鸡"),nv("恋物足交","恋物足交")])],
manhua:[fv("分类","videoTag",[nv("最新",""),nv("热门推荐","热门推荐"),nv("韩漫","韩漫"),nv("同人","同人"),nv("独家","独家"),nv("国漫","国漫"),nv("日漫","日漫"),nv("3D","3D"),nv("单行本","单行本"),nv("CG/AI","CG/AI"),nv("COS写真","COS写真"),nv("BL","BL")])]
};
function md5(s){return crypto.createHash("md5").update(String(s)).digest("hex")}
function hdr(){
let t=String(Date.now());
return{"User-Agent":UA,Accept:"application/json, text/plain, */*",Referer:host+"/",Origin:host,device:"Android",appVersion:"1.9.6","User-Mark":"xhp",deviceId:did,aut:token,t:t,s:md5(t.slice(3,8)),sid:md5(String(Date.now())).slice(0,16)};
}
function dec(enc){
if(!enc||!token)return null;
try{
let k=Buffer.from(token.slice(2,18),"utf8");
let raw=Buffer.from(enc,"base64");
let d=crypto.createDecipheriv("aes-128-cbc",k,k);
let pt=Buffer.concat([d.update(raw),d.final()]).toString("utf8");
if(pt&&(pt[0]==="{"||pt[0]==="["))return JSON.parse(pt);
return pt;
}catch{return null}
}
function hdrGet(hh,k){
if(!hh) return "";
let v="";
if(typeof hh.get==="function") v=hh.get(k)||hh.get(k.toLowerCase())||"";
else v=hh[k]||hh[k.toLowerCase()]||hh["Refresh-Authorization"]||"";
if(Array.isArray(v)) v=v[0];
return v?String(v):"";
}
async function api(path,params,method){
method=method||"GET";
for(let i=0;i<3;i++){
let h=hdr();
let p=Object.assign({},params||{});
p._t=h.t;
let url=host+"/api"+path;
try{
let opt={headers:h,timeout:15e3,validateStatus:()=>!0,maxRedirects:0};
let r;
try{
if(method==="POST") r=await req.post(url,p,opt);
else r=await req.get(url,Object.assign({params:p},opt));
}catch(err){
r=err&&err.response||null;
if(!r) continue;
}
if(!r) continue;
let nt=hdrGet(r.headers,"refresh-authorization");
if(nt) token=nt;
let j=r.data;
if(typeof Buffer!=="undefined"&&Buffer.isBuffer(j)) j=j.toString("utf8");
if(typeof j==="string"){
if(!j){ if(nt) continue; return null }
try{j=JSON.parse(j)}catch{ if(nt) continue; return null }
}
if(!j||typeof j!=="object"){ if(nt) continue; return null }
let code=Number(j.code||0);
if(code===301) continue;
if(code!==200) return null;
if(j.encData){ let d=dec(j.encData); return d!=null?d:null }
return "data" in j ? j.data : j;
}catch{continue}
}
return null;
}
function items(data){
if(Array.isArray(data)) return data;
if(data&&typeof data==="object"){
for(let k of ["data","list","videoList","records"]){
let v=data[k];
if(Array.isArray(v)) return v;
if(v&&typeof v==="object"){
let inner=v.data||v.list;
if(Array.isArray(inner)) return inner;
}
}
}
return [];
}
function domain(data){return data&&typeof data==="object"? (data.domain||"") : ""}
function extVal(extend,key){
let v=extend&&extend[key];
if(Array.isArray(v)) v=v[0]||"";
if(v==null) v="";
return String(v).trim();
}
function pageResult(page,list,total,limit){
limit=limit||20;
let pc=total?Math.ceil(Number(total)/limit):(list&&list.length?page+1:1);
return{page,pagecount:pc,limit,total:total||pc*limit,list:list||[]};
}
function firstPic(pic){
if(Array.isArray(pic)) pic=pic[0]||"";
return pic||"";
}
function absImg(url,dom){
if(!url) return "";
url=firstPic(url);
if(!url) return "";
if(!String(url).startsWith("http")){
let d=dom||imgD;
if(!d.endsWith("/")) d+="/";
url=d+String(url).replace(/^\/+/,"")
}
return String(url);
}
function baseUrl(e){
try{
if(!e||!e.server) return "";
return String(e.server.address().url||"")+String(e.server.prefix||"");
}catch{return ""}
}
function picUrl(e,url,dom){
url=absImg(url,dom);
if(!url) return "";
let b=baseUrl(e);
return b? b+"/pic?url="+encodeURIComponent(url) : url;
}
function m3u8Play(e,videoUrl){
if(!videoUrl) return "";
let path=String(videoUrl);
let apiU=host+"/api/m3u8/h5/decode?path="+encodeURIComponent(path);
let b=baseUrl(e);
return b? b+"/proxy?type=m3u8&url="+encodeURIComponent(apiU) : apiU;
}
function sidOf(prefix,id,name,pic){
return String(prefix||"")+id+"@@@"+""+"@@@"+encodeURIComponent(String(name||""))+"@@@"+encodeURIComponent(String(pic||""));
}
function parseList(e,data,prefix){
let dom=domain(data), list=items(data), res=[], seen=new Set();
for(let it of list){
if(!it||typeof it!=="object") continue;
let vid=String(it.videoId||it.id||"");
if(!vid||seen.has(vid)) continue;
seen.add(vid);
let name=String(it.title||vid);
let pic=firstPic(it.coverImg||"");
let dur=String(it.playTime||"");
if(dur&&/^\d+$/.test(dur)){ let n=parseInt(dur,10); dur=Math.floor(n/60)+":"+String(n%60).padStart(2,"0") }
res.push({vod_id:sidOf(prefix||"",vid,name,pic),vod_name:name,vod_pic:picUrl(e,pic,dom),vod_remarks:dur||""});
}
return res;
}
function cachePut(bucket,page,data){
let raw=items(data).filter(it=>it&&typeof it==="object");
pages[bucket+"|"+page]={domain:domain(data),items:raw};
for(let it of raw){
let iid=String(it.videoId||"");
if(iid) index[iid]=bucket+"|"+page;
}
}
function cacheGet(vid){
let key=index[String(vid)];
if(key&&pages[key]) return pages[key];
for(let k in pages){
let pack=pages[k];
for(let it of pack.items||[]){
if(String(it.videoId||"")===String(vid)) return pack;
}
}
return null;
}
function classes(){
return [
{type_id:"jx",type_name:"精选"},
{type_id:"dm",type_name:"动漫"},
{type_id:"lifan",type_name:"里番"},
{type_id:"rebao",type_name:"热播"},
{type_id:"luanlun",type_name:"乱伦"},
{type_id:"guochan",type_name:"国产"},
{type_id:"wanghuang",type_name:"网黄"},
{type_id:"luoli",type_name:"萝莉"},
{type_id:"av",type_name:"AV"},
{type_id:"chuanmei",type_name:"传媒"},
{type_id:"zhongkou",type_name:"重口"},
{type_id:"manhua",type_name:"漫画"}
];
}
async function homeVideos(e){
let data=await api("/video/getByClassify",{page:1,pageSize:20,classifyId:4,sortType:0,restricted:0});
return parseList(e,data);
}
async function shortCategory(e,page,extend){
let mode=extVal(extend,"shortMode")||"find";
let plot=extVal(extend,"shortPlot");
let data;
if(mode==="rec"){
data=await api("/video/list",{page,pageSize:20,loadType:2});
cachePut("rec",page,data);
}else{
let cid=plot||"42";
data=await api("/video/getByClassify",{page,pageSize:20,classifyId:cid,sortType:1,restricted:0});
cachePut("find_"+cid,page,data);
}
return pageResult(page,parseList(e,data,"s_"),data&&data.total);
}
function fictionParse(e,data){
let dom=domain(data), list=items(data), res=[], seen=new Set();
for(let it of list){
if(!it||typeof it!=="object") continue;
let fid=String(it.fictionId||"");
if(!fid||seen.has(fid)) continue;
seen.add(fid);
let name=String(it.fictionTitle||fid);
let pic=firstPic(it.coverImg||"");
let num=String(it.chapterNewNum||it.chapterNum||"");
let remark=String(it.fictionType)==="2"?"有声":"";
if(num&&/^\d+$/.test(num)) remark=(remark?remark+" ":"")+num+"章";
res.push({vod_id:sidOf("f_",fid,name,pic),vod_name:name,vod_pic:picUrl(e,pic,dom),vod_remarks:remark});
}
return res;
}
async function fictionCategory(e,page,extend){
let ftype=extVal(extend,"fictionType")||"1";
let tag=extVal(extend,ftype==="2"?"tag2":"tag1");
let params={fictionType: /^\d+$/.test(ftype)?parseInt(ftype,10):1,page,pageSize:20};
if(tag&&/^\d+$/.test(tag)) params.tagIds=[parseInt(tag,10)];
let data=await api("/fiction/base/findList",params,"POST");
return pageResult(page,fictionParse(e,data),data&&data.total);
}
function comicParse(e,data){
let dom=domain(data), list=items(data), res=[], seen=new Set();
for(let it of list){
if(!it||typeof it!=="object") continue;
let cid=String(it.comicsId||"");
if(!cid||seen.has(cid)) continue;
seen.add(cid);
let name=String(it.comicsTitle||cid);
let pic=firstPic(it.coverImg||"");
let num=String(it.chapterNewNum||"");
res.push({vod_id:sidOf("c_",cid,name,pic),vod_name:name,vod_pic:picUrl(e,pic,dom),vod_remarks:num&&/^\d+$/.test(num)?num+"话":""});
}
return res;
}
async function comicCategory(e,page,extend){
let vt=extVal(extend,"videoTag");
let cid=comicClass[vt]||"1";
let data=await api("/comics/base/findList",{classId:cid,orderType:0,restricted:0,page,pageSize:20},"POST");
return pageResult(page,comicParse(e,data),data&&data.total);
}
async function shortDetail(e,vid,name,pic){
let clicked=String(vid);
let cached=cacheGet(clicked);
let raw=(cached&&cached.items)||[];
let dom=(cached&&cached.domain)||"";
let seen=new Set(), ordered=[];
for(let it of raw){
if(!it||typeof it!=="object") continue;
let iid=String(it.videoId||"");
if(!iid||seen.has(iid)) continue;
seen.add(iid); ordered.push(it);
}
let head=ordered.filter(it=>String(it.videoId)===clicked);
if(!head.length){
let data=await api("/video/getVideoById",{videoId:clicked});
if(data&&typeof data==="object"&&(data.videoId||data.videoUrl||data.playUrl)){
if(!dom) dom=data.domain||"";
head=[data];
}
}
let tail=ordered.filter(it=>String(it.videoId)!==clicked);
ordered=head.concat(tail);
let parts=[], vname=name, vpic=pic, vcontent="短视频";
for(let it of ordered){
let iid=String(it.videoId||"");
let title=String(it.title||iid).replace(/#/g," ").replace(/\$/g," ");
let line=m3u8Play(e,it.videoUrl||it.playUrl||"");
if(!line) continue;
parts.push(title+"$"+line);
if(iid===clicked){
vname=title;
vpic=firstPic(it.coverImg||vpic);
let tags=it.tagTitles||[];
if(tags.length) vcontent="标签: "+tags.join(" ");
}
}
return{list:[{vod_id:"s_"+vid,vod_name:vname||"短视频",vod_pic:picUrl(e,vpic,dom),vod_content:vcontent,vod_play_from:"短视频",vod_play_url:parts.join("#")}]};
}
async function fictionDetail(e,fid,name,pic){
let data=await api("/fiction/base/info",{fictionId:fid});
let vname=name,vpic=pic,dom="",chapters=[],tags=[],info="",ftype=1;
if(data&&typeof data==="object"){
dom=data.domain||"";
vname=data.fictionTitle||vname;
vpic=data.coverImg||vpic;
chapters=data.chapters||data.chapterList||[];
tags=data.tagList||[];
info=data.info||"";
ftype=data.fictionType||1;
}
let tlist=[];
for(let t of tags){ if(t&&t.title) tlist.push(String(t.title)) }
let content=tlist.length?"标签: "+tlist.join(" "):(String(ftype)==="2"?"有声小说":"小说");
if(info) content=content+"\n"+String(info);
let parts=[];
for(let ch of chapters){
let cid=ch&&ch.chapterId;
if(!cid) continue;
let cn=String(ch.chapterTitle||("第"+(ch.chapterNum||0)+"章")).replace(/#/g," ").replace(/\$/g," ");
parts.push(cn+"$fplay:"+fid+":"+cid);
}
return{list:[{vod_id:"f_"+fid,vod_name:vname,vod_pic:picUrl(e,vpic,dom),vod_content:content,vod_play_from:String(ftype)==="2"?"视频":"小说",vod_play_url:parts.join("#")}]};
}
async function comicDetail(e,cid,name,pic){
let data=await api("/comics/base/info",{comicsId:cid});
let vname=name,vpic=pic,dom="",chapters=[],tags=[];
if(data&&typeof data==="object"){
dom=data.domain||"";
vname=data.comicsTitle||vname;
vpic=data.coverImg||vpic;
chapters=data.chapterList||[];
tags=data.tagList||[];
}
let tlist=[];
for(let t of tags){ if(t&&t.title) tlist.push(String(t.title)) }
let content=tlist.length?"标签: "+tlist.join(" "):"漫画";
let parts=[], chs=chapters.slice(0,20);
for(let ch of chs){
try{
let ci=await api("/comics/base/chapterInfo",{chapterId:ch.chapterId});
let imgs=(ci&&ci.imgList)||[];
let pics=imgs.map(i=>picUrl(e,i,dom)).filter(Boolean).join("&&");
if(!pics) continue;
let cn=String(ch.chapterTitle||("第"+(ch.chapterNum||0)+"话"));
parts.push(cn+"$pics://"+pics);
}catch{}
}
return{list:[{vod_id:"c_"+cid,vod_name:vname,vod_pic:picUrl(e,vpic,dom),vod_content:content,vod_play_from:"图片",vod_play_url:parts.join("#"),vod_tag:"image"}]};
}
function joinUrl(dom,path){
if(!path) return "";
path=String(path);
if(path.startsWith("http://")||path.startsWith("https://")) return path;
let d=String(dom||"");
if(d&&!d.endsWith("/")) d+="/";
return d? d+path.replace(/^\/+/,"") : path;
}
async function fetchTxt(url){
if(!url) return "";
try{
let r=await req.get(url,{headers:{"User-Agent":UA,Referer:host+"/"},timeout:15e3,responseType:"arraybuffer",validateStatus:()=>!0});
if(!r||r.status!==200||!r.data) return "";
let raw=Buffer.from(r.data);
for(let enc of ["utf8","utf-8","gbk","gb2312"]){
try{ return raw.toString(enc) }catch{}
}
return raw.toString("utf8");
}catch{return ""}
}
async function fictionPlay(e,url){
let ps=String(url).split(":");
let fid=ps[1]||"", cid=ps[2]||"";
let ci=await api("/fiction/base/chapterInfo",{chapterId:cid,fictionId:fid});
if(!ci||typeof ci!=="object") return "";
let ftype=String(ci.fictionType||"");
let fic=String(ci.fictionUrl||"");
if(ftype==="1"||(fic.endsWith(".txt")&&!fic.includes(".mp3")&&!fic.includes(".m3u8")&&!fic.includes(".mp4"))){
let play=ci.playPath||"";
let txt=play||joinUrl(ci.domain||"",fic);
return txt;
}
if(fic&&(fic.includes(".m3u8")||fic.includes(".mp4"))) return m3u8Play(e,fic);
if(ci.mp4Domain&&fic) return joinUrl(ci.mp4Domain,fic);
if(ci.playPath) return ci.playPath;
return joinUrl(ci.domain||"",fic);
}
function mimeOf(buf){
if(!buf||buf.length<12) return "";
if(buf[0]===0x89&&buf[1]===0x50&&buf[2]===0x4e&&buf[3]===0x47) return "image/png";
if(buf[0]===0x47&&buf[1]===0x49&&buf[2]===0x46) return "image/gif";
if(buf[0]===0x52&&buf[1]===0x49&&buf[2]===0x46&&buf[3]===0x46&&buf[8]===0x57) return "image/webp";
if(buf[0]===0xff&&buf[1]===0xd8) return "image/jpeg";
return "";
}
function xorImg(buf){
let key=Buffer.from("2020-zq3-888");
let n=Math.min(100,buf.length);
let out=Buffer.from(buf);
for(let i=0;i<n;i++) out[i]^=key[i%key.length];
return out;
}
async function acfInit(e,t){ return {} }
async function acfHome(e,t){
return{class:classes(),filters,list:await homeVideos(e),type:"影视"};
}
async function acfCate(e,t){
let page=parseInt(e.body.page||1,10)||1;
let tid=String(e.body.id||"");
let extend=e.body.filters||{};
if(typeof extend==="string"){ try{extend=JSON.parse(extend)}catch{extend={}} }
extend=extend||{};
if(tid==="manhua") return comicCategory(e,page,extend);
if(tid==="jx"){
let jx=extVal(extend,"jxType");
if(!jx){
if(extVal(extend,"fictionType")||extVal(extend,"tag1")||extVal(extend,"tag2")) jx="fiction";
else if(extVal(extend,"shortMode")||extVal(extend,"shortPlot")) jx="short";
}
if(jx==="short") return shortCategory(e,page,extend);
if(jx==="fiction") return fictionCategory(e,page,extend);
}
let cid=extVal(extend,"classifyId")||catMap[tid]||"";
let vt=extVal(extend,"videoTag");
let data=vt
? await api("/video/tagTitleList",{tagsTitle:vt,page,pageSize:20,sortType:0,restricted:0})
: await api("/video/getByClassify",{page,pageSize:20,sortType:0,restricted:0,classifyId:cid});
return pageResult(page,parseList(e,data),data&&data.total);
}
async function acfDetail(e,t){
let vid=Array.isArray(e.body.id)?e.body.id[0]:e.body.id;
vid=String(vid||"");
let ps=vid.split("@@@");
let rid=ps[0]||vid;
let name=ps[2]?decodeURIComponent(ps[2]):rid;
let pic=ps[3]?decodeURIComponent(ps[3]):"";
if(String(rid).startsWith("c_")) return comicDetail(e,rid.slice(2),name,pic);
if(String(rid).startsWith("f_")) return fictionDetail(e,rid.slice(2),name,pic);
if(String(rid).startsWith("srec_")||String(rid).startsWith("s_")){
let real=String(rid).startsWith("srec_")?rid.slice(5):rid.slice(2);
return shortDetail(e,real,name,pic);
}
let data=await api("/video/getVideoById",{videoId:rid});
let vname=name,vpic=pic,vcontent="",videoUrl="",dom="";
if(data&&typeof data==="object"){
dom=data.domain||"";
vname=data.title||vname;
vpic=firstPic(data.coverImg||vpic);
vcontent=data.description||data.synopsis||"";
videoUrl=data.videoUrl||data.playUrl||"";
let tags=data.tagTitles||[];
if(tags.length) vcontent="标签: "+tags.join(" ")+(vcontent?"\n"+vcontent:"");
}
let line=m3u8Play(e,videoUrl);
return{list:[{vod_id:vid,vod_name:vname,vod_pic:picUrl(e,vpic,dom),vod_content:vcontent,vod_play_from:"AcFanH5",vod_play_url:line?"播放$"+line:""}]};
}
async function acfSearch(e,t){
let key=e.body.wd||"";
let page=parseInt(e.body.page||1,10)||1;
let data=await api("/search/keyWordV2",{searchWord:key,page,pageSize:20});
return pageResult(page,parseList(e,data),data&&data.total);
}
async function acfPlay(e,t){
let url=String(e.body.id||"");
let h={"User-Agent":UA,Referer:host+"/",Origin:host};
if(url.startsWith("fplay:")){
let play=await fictionPlay(e,url);
return{parse:0,url:play||url,header:h};
}
if(url.startsWith("pics://")) return{parse:0,url:url,header:h};
return{parse:0,url:url,header:h};
}
async function acfPic(e,t){
let u=e.query&&e.query.url||"";
if(!u) return t.code(404),t.send("");
try{u=decodeURIComponent(u)}catch{}
try{
let r=await req.get(u,{responseType:"arraybuffer",headers:{"User-Agent":UA,Referer:host+"/"},timeout:15e3,validateStatus:()=>!0});
let data=Buffer.from(r.data||[]);
let ct=mimeOf(data);
if(!ct){ data=xorImg(data); ct=mimeOf(data)||"image/jpeg" }
t.header("Content-Type",ct);
t.header("Cache-Control","public, max-age=86400");
return t.send(data);
}catch{return t.code(502),t.send("")}
}
async function acfProxy(e,t){
let n=e.query||e.body||{};
let pt=n.type||n.do||"";
let u=n.url||"";
if(Array.isArray(u)) u=u[0];
try{u=decodeURIComponent(u)}catch{}
if(!u) return t.code(404),t.header("Content-Type","text/plain"),t.send("nf");
try{
if(pt==="m3u8"){
let r=await req.get(u,{headers:hdr(),timeout:20e3,validateStatus:()=>!0,responseType:"text"});
if(!r||r.status!==200) return t.code(404),t.header("Content-Type","text/plain"),t.send("nf");
let body=typeof r.data==="string"?r.data:String(r.data||"");
let b=baseUrl(e);
let proxy=x=> b+"/proxy?type=ts&url="+encodeURIComponent(x);
body=body.replace(/(URI=")([^"]+)(")/g,(m,a,b2,c)=>a+proxy(b2)+c);
body=body.split(/\r?\n/).map(line=>{
let s=line.trim();
if(s.startsWith("http://")||s.startsWith("https://")) return proxy(s);
return line;
}).join("\n");
t.header("Content-Type","application/vnd.apple.mpegurl;charset=UTF-8");
return t.send(body);
}
if(pt==="ts"){
let r=await req.get(u,{responseType:"arraybuffer",headers:{"User-Agent":UA,Referer:host+"/"},timeout:20e3,validateStatus:()=>!0});
if(!r||r.status!==200) return t.code(404),t.header("Content-Type","text/plain"),t.send("nf");
t.header("Content-Type","video/mp2t");
return t.send(Buffer.from(r.data||[]));
}
return t.code(404),t.header("Content-Type","text/plain"),t.send("nf");
}catch{return t.code(500),t.header("Content-Type","text/plain"),t.send("err")}
}

export default {
  meta: { key: "acfanh5", name: "\u300C\u76F4\u300D\u{1F4FD}\uFE0EAcFanH5", type: 3 },
  api: async (app) => {
    app.post("/init", acfInit);
    app.post("/home", acfHome);
    app.post("/category", acfCate);
    app.post("/detail", acfDetail);
    app.post("/play", acfPlay);
    app.post("/search", acfSearch);
    app.get("/pic", acfPic);
    app.get("/proxy", acfProxy);
    app.post("/proxy", acfProxy);
  }
};
