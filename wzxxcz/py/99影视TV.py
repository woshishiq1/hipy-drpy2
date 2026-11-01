# coding=utf-8
"""
99影视TV 99itv.cc | TVBox Python 爬虫 
站点结构:
  - 首页        /                                   (多板块卡片)
  - 分类首页    /type/{movie|drama|variety|anime}.html
  - 分类列表    /show/{type}-{area}-{page}-{sort}-{year}.html
  - 详情        /detail/{slug}.html                   (slug 见下方说明)
  - 播放        /userpy/{slug}-{sid}-{nid}.html       (player_aaaa.url 为真实 m3u8)
  - 今日更新    /label/new.html
  - 热榜        /label/hot.html
  - 搜索        /search.html?wd=xx   (被 Cloudflare WAF 屏蔽)
              => 改用站内建议接口 /index.php/ajax/suggest?mid=1&wd=xx
  - 数据接口    /index.php/ajax/data?mid=1&tid=&page=N  (含 detail_link)
"""
import re
import sys
import json
import time
import ssl
import threading
import collections
import urllib.parse
import urllib.request

sys.path.append('..')

try:
    from base.spider import Spider
except ImportError:
    import requests as _rq
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    class _BaseSpider:
        def __init__(self):
            self._session = None

        @property
        def _sess(self):
            if self._session is None:
                self._session = _rq.Session()
                self._session.verify = False
                adapter = _rq.adapters.HTTPAdapter(
                    pool_connections=16, pool_maxsize=16, max_retries=0)
                self._session.mount('https://', adapter)
                self._session.mount('http://', adapter)
            return self._session

        def fetch(self, url, headers=None, **kw):
            timeout = kw.pop('timeout', 15)
            r = self._sess.get(url, headers=headers, timeout=timeout, **kw)
            r.encoding = 'utf-8'
            return r

        def log(self, *a, **kw):
            try:
                print("[99itv]", *a)
            except Exception:
                pass

    Spider = _BaseSpider


HOST = "https://99itv.cc"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
DEFAULT_PIC = HOST + "/99.png"

INTRO_PREFIX = "🍊小橙子为您介绍剧情👉请不要相信视频中的广告，以免上当受骗！"


# ----------------------------------------------------------------------
# 简体 -> 繁体 转换表（站点内容为繁体，搜索需转换关键词）
# ----------------------------------------------------------------------
_SIMPLIFIED = (
    "万与丑专业丛东丝丢两严丧个丰临为丽举么义乌乐乔习乡书买乱争于亏云亘亚产亩亲亵亸亿仅仆从仑仓仪们价众优伙会伛伞伟传伡伣伤伥伦伧伪伫体余佣佥侠侣侥侦侧侨侩侪侬侭俣俦"
    "俨俩俪俫俭债倾偬偻偾偿傤傥傧储傩僞儿兑兖党兰关兴兹养兽冁内冈册写军农冯冲决况冻净凄准凉减凑凛几凤凫凭凯凶击凿刍划刘则刚创删别刬刭刹刽刾刿剀剂剐剑剥剧劝办务劢动励"
    "劲劳势勋勚匀匦匮区医华协单卖占卢卤卧卫却卺厂厅历厉压厌厍厐厕厘厢厣厦厨厩厮县叁参叆叇双发变叙叠台叶号叹叽吁后吓吕吗吣吨听启吴呐呒呓呕呖呗员呙呛呜咏咙咛咝咤咨咸响"
    "哑哒哓哔哕哗哙哜哝哟唛唝唠唡唢唤啓啧啬啭啮啯啰啴啸喂喫喷喽喾嗫嗳嘘嘤嘱噜嚣团园囱围囵国图圆圣圹场坏块坚坛坜坝坞坟坠垄垅垆垒垦垩垫垭垯垱垲垴埘埙埚堑堕塆墙壮声壳壶"
    "壸处备复够头夸夹夺奁奂奋奖奥妆妇妈妩妪妫姗姹娄娅娆娇娈娱娲娴婳婴婵婶媪媭嫒嫔嫱嫺嬀嬷孙学孪宁宝实宠审宪宫宽宾寝对寻导寿将尔尘尝尧尴尸尽层屃屉届属屡屦屿岁岂岖岗岘"
    "岚岛岩岭岳岽岿峃峄峡峣峤峥峦峯崂崃崄崭嵘嵚嵝巅巩巯币帅师帏帐帘帜带帧帮帱帻帼幂干并幺广庄庆庐庑库应庙庞废庼廪开异弃弑张弥弪弯弹强归当录彟彦彨彻征径徕忆忏忧忾怀态"
    "怂怃怄怅怆怜总怼怿恋恒恳恶恸恹恺恻恼恽悦悫悬悭悮悯惊惧惨惩惫惬惭惮惯愠愤愦愿慑慭懑懒懔戆戋戏戗战戬戯户扑托执扩扪扫扬扰抚抛抟抠抡抢护报担拟拢拣拥拦拧拨择挂挚挛挜"
    "挝挞挟挠挡挢挣挤挥挦捝捞损捡换捣据掳掴掷掸掺掼揽揾揿搀搁搂搄搅携摄摅摆摇摈摊撄撑撵撷撸撺擜擞擡攒敌敚敛敩数斋斓斗斩断无旧时旷旸昙昵昼昽显晋晒晓晔晕晖暂暅暧术朴机"
    "杀杂权杠条来杨杩杰极构枞枢枣枥枧枨枪枫枭枱柜柠柽栀栅标栈栉栊栋栌栎栏树栖栗样栾桠桡桢档桤桥桦桧桨桩桪梦梼梾梿检棁棂棱椁椝椟椠椢椤椫椭椮楼榄榅榇榈榉榝槚槛槟槠横樯"
    "樱橥橱橹橼檐檩欢欤欧歼殁殇残殒殓殚殡殴毁毂毕毙毡毵毶氇气氢氩氲汇汉污汤汹沟没沣沤沥沦沧沨沩沪泄泞泪泶泷泸泺泻泼泽泾洁洒洼浃浅浆浇浈浉浊测浍济浏浐浑浒浓浔浕涂涌涚"
    "涛涝涞涟涠涡涢涣涤润涧涨涩淀渊渌渍渎渐渑渔渖渗温游湾湿溁溃溅溆溇滗滚滞滟滠满滢滤滥滦滨滩滪漤潆潇潋潍潙潜潨潴澛澜濑濒灏灭灯灵灾灿炀炉炖炜炝点炼炽烁烂烃烛烟烦烧烨"
    "烩烫烬热焕焖焘煴熏爱爲爷牀牍牦牵牺犊状犷犸犹狈狝狞独狭狮狯狰狱狲猃猎猕猡猪猫猬献獭玑玙玚玛玮环现玱玺珐珑珰珲琎琏琐琼瑶瑷瑸璎瓒瓮瓯电画畅畴疖疗疟疠疡疬疭疮疯疱疴"
    "痈痉痒痖痨痪痫痳痹瘅瘆瘗瘘瘪瘫瘾瘿癞癡癣癫皁皑皱皲盏盐监盖盗盘眍眦眬着睁睐睑睾瞆瞒瞩矫矶矾矿砀码砖砗砚砜砺砻砾础硁硅硕硖硗硙硚确硵硷碍碛碜碱礼祃祎祕祢祯祷祸禀禄"
    "禅离秃秆种积称秽秾稆税稣稳穑穞穷窃窍窎窑窜窝窥窦窭竈竖竞笃笋笔笕笺笼笾筑筚筛筜筝筹筼签筿简箓箦箧箨箩箪箫篑篓篮篯篱簖籁籴类籼粜粝粤粪粮糁糇糉糍紧絷緼縆繮纔纟纠纡"
    "红纣纤纥约级纨纩纪纫纬纭纮纯纰纱纲纳纴纵纶纷纸纹纺纻纼纽纾线绀绁绂练组绅细织终绉绊绋绌绍绎经绐绑绒结绔绕绖绗绘给绚绛络绝绞统绠绡绢绣绤绥绦继绨绩绪绫绬续绮绯绰绱"
    "绲绳维绵绶绷绸绹绺绻综绽绾绿缀缁缂缃缄缅缆缇缈缉缊缋缌缍缎缏缐缑缒缓缔缕编缗缘缙缚缛缜缝缞缟缠缡缢缣缤缥缦缧缨缩缪缫缬缭缮缯缰缱缲缳缴缵罂网罗罚罢罴羁羟羡羣翘翙"
    "翚耢耧耸耻聂聋职聍联聩聪肃肠肤肮肴肾肿胀胁胆胜胧胨胪胫胶脉脍脏脐脑脓脔脚脣脱脶脸腊腌腘腭腻腼腽腾膑膻臜舆舣舰舱舻艰艳艺节芈芗芜芦苁苇苈苋苌苍苎苏苧苹范茎茏茑茔茕"
    "茧荆荐荙荚荛荜荝荞荟荠荡荣荤荥荦荧荨荩荪荫荬荭荮药莅莱莲莳莴莶获莸莹莺莼萚萝萤营萦萧萨葱蒀蒇蒉蒋蒌蒏蓝蓟蓠蓣蓥蓦蔂蔘蔷蔹蔺蔼蔿蕰蕲蕴薮藓藴蘖虏虑虚虫虬虮虱虽虾虿"
    "蚀蚁蚂蚃蚕蚝蚬蛊蛎蛏蛮蛰蛱蛲蛳蛴蜕蜗蜡蝇蝈蝉蝎蝼蝾螀螨蟏衅衆衔补衬衮袄袅袆袜袭袯装裆裈裏裢裣裤裥褛褴襕覈见观觃规觅视觇览觉觊觋觌觍觎觏觐觑觞触觯訚詟誉誊讠计订讣"
    "认讥讦讧讨让讪讫讬训议讯记讱讲讳讴讵讶讷许讹论讻讼讽设访诀证诂诃评诅识诇诈诉诊诋诌词诎诏诐译诒诓诔试诖诗诘诙诚诛诜话诞诟诠诡询诣诤该详诧诨诩诪诫诬语诮误诰诱诲诳"
    "说诵诶请诸诹诺读诼诽课诿谀谁谂调谄谅谆谇谈谉谊谋谌谍谎谏谐谑谒谓谔谕谖谗谘谙谚谛谜谝谞谟谠谡谢谣谤谥谦谧谨谩谪谫谬谭谮谯谰谱谲谳谴谵谶豮贝贞负贠贡财责贤败账货质"
    "贩贪贫贬购贮贯贰贱贲贳贴贵贶贷贸费贺贻贼贽贾贿赀赁赂赃资赅赆赇赈赉赊赋赌赍赎赏赐赑赒赓赔赕赖赗赘赙赚赛赜赝赞赟赠赡赢赣赪赵赶趋趱趸跃跄跖跞践跶跷跸跹跻踊踌踪踬踯"
    "蹑蹒蹰蹿躏躜躯輼车轧轨轩轪轫转轭轮软轰轱轲轳轴轵轶轷轸轹轺轻轼载轾轿辀辁辂较辄辅辆辇辈辉辊辋辌辍辎辏辐辑辒输辔辕辖辗辘辙辚辞辟辩辫边辽达迁过迈运还这进远违连迟迩"
    "迳迹适选逊递逦逻遗遥邓邝邬邮邹邺邻郁郏郐郑郓郦郧郸酂酝酦酰酱酽酾酿醖采释里鈎鉢鉴銮錾鍼钅钆钇针钉钊钋钌钍钎钏钐钑钒钓钔钕钖钗钘钙钚钛钜钝钞钟钠钡钢钣钤钥钦钧钨钩"
    "钪钫钬钭钮钯钰钱钲钳钴钵钶钷钸钹钺钻钼钽钾钿铀铁铂铃铄铅铆铇铈铉铊铋铌铍铎铏铐铑铒铓铔铕铖铗铘铙铚铛铜铝铞铟铠铡铢铣铤铥铦铧铨铩铪铫铬铭铮铯铰铱铲铳铴铵银铷铸铹"
    "铺铻铼铽链铿销锁锂锃锄锅锆锇锈锉锊锋锌锍锎锏锐锑锒锓锔锕锖锗锘错锚锛锜锝锞锟锠锡锢锣锤锥锦锧锨锩锪锫锬锭键锯锰锱锲锳锴锵锶锷锸锹锺锻锼锽锾锿镀镁镂镃镄镅镆镇镈镉"
    "镊镋镌镍镎镏镐镑镒镓镔镕镖镗镘镙镚镛镜镝镞镟镠镡镢镣镤镥镦镧镨镩镪镫镬镭镮镯镰镱镲镳镴镵镶长门闩闪闫闬闭问闯闰闱闲闳间闵闶闷闸闹闺闻闼闽闾闿阀阁阂阃阄阅阆阇阈阉"
    "阊阋阌阍阎阏阐阑阒阓阔阕阖阗阘阙阚阛队阳阴阵阶际陆陇陈陉陕陦陧陨险随隐隶隽难雇雏雠雳雾霁霉霡霭靓靔静靥鞑鞒鞯鞲韦韧韨韩韪韫韬韵页顶顷顸项顺须顼顽顾顿颀颁颂颃预颅"
    "领颇颈颉颊颋颌颍颎颏颐频颒颓颔颕颖颗题颙颚颛颜额颞颟颠颡颢颣颤颥颦颧风飏飐飑飒飓飔飕飖飗飘飙飚飞飨餍饣饤饥饦饧饨饩饪饫饬饭饮饯饰饱饲饳饴饵饶饷饸饹饺饻饼饽饾饿馀"
    "馁馂馃馄馅馆馇馈馉馊馋馌馍馎馏馐馑馒馓馔馕马驭驮驯驰驱驲驳驴驵驶驷驸驹驺驻驼驽驾驿骀骁骂骃骄骅骆骇骈骉骊骋验骍骎骏骐骑骒骓骔骕骖骗骘骙骚骛骜骝骞骟骠骡骢骣骤骥骦"
    "骧髅髋髌鬓鬶魇魉鮎鱼鱽鱾鱿鲀鲁鲂鲃鲄鲅鲆鲇鲈鲉鲊鲋鲌鲍鲎鲏鲐鲑鲒鲓鲔鲕鲖鲗鲘鲙鲚鲛鲜鲝鲞鲟鲠鲡鲢鲣鲤鲥鲦鲧鲨鲩鲪鲫鲬鲭鲮鲯鲰鲱鲲鲳鲴鲵鲶鲷鲸鲹鲺鲻鲼鲽鲾鲿鳀鳁鳂"
    "鳃鳄鳅鳆鳇鳈鳉鳊鳋鳌鳍鳎鳏鳐鳑鳒鳓鳔鳕鳖鳗鳘鳙鳚鳛鳜鳝鳞鳟鳠鳡鳢鳣鳤鸟鸠鸡鸢鸣鸤鸥鸦鸧鸨鸩鸪鸫鸬鸭鸮鸯鸰鸱鸲鸳鸴鸵鸶鸷鸸鸹鸺鸻鸼鸽鸾鸿鹀鹁鹂鹃鹄鹅鹆鹇鹈鹉鹊鹋鹌"
    "鹍鹎鹏鹐鹑鹒鹓鹔鹕鹖鹗鹘鹙鹚鹛鹜鹝鹞鹟鹠鹡鹢鹣鹤鹥鹦鹧鹨鹩鹪鹫鹬鹭鹮鹯鹰鹱鹲鹳鹴鹾麦麪麸麹麺麽黄黉黡黩黪黾鼋鼌鼍鼗鼹齐齑齶齿龀龁龂龃龄龅龆龇龈龉龊龋龌龙龚龛龟"
)

_TRADITIONAL = (
    "萬與醜專業叢東絲丟兩嚴喪個豐臨為麗舉麼義烏樂喬習鄉書買亂爭於虧雲亙亞產畝親褻嚲億僅僕從侖倉儀們價眾優夥會傴傘偉傳俥俔傷倀倫傖偽佇體餘傭僉俠侶僥偵側僑儈儕儂儘俁儔"
    "儼倆儷倈儉債傾傯僂僨償儎儻儐儲儺偽兒兌兗黨蘭關興茲養獸囅內岡冊寫軍農馮衝決況凍淨悽準涼減湊凜幾鳳鳧憑凱兇擊鑿芻劃劉則剛創刪別剗剄剎劊㓨劌剴劑剮劍剝劇勸辦務勱動勵"
    "勁勞勢勳勩勻匭匱區醫華協單賣佔盧滷臥衛卻巹廠廳歷厲壓厭厙龎廁釐廂厴廈廚廄廝縣叄參靉靆雙發變敘疊臺葉號嘆嘰籲後嚇呂嗎唚噸聽啟吳吶嘸囈嘔嚦唄員咼嗆嗚詠嚨嚀噝吒諮鹹響"
    "啞噠嘵嗶噦譁噲嚌噥喲嘜嗊嘮啢嗩喚啟嘖嗇囀齧嘓囉嘽嘯餵吃噴嘍嚳囁噯噓嚶囑嚕囂團園囪圍圇國圖圓聖壙場壞塊堅壇壢壩塢墳墜壟壠壚壘墾堊墊埡墶壋塏堖塒壎堝塹墮壪牆壯聲殼壺"
    "壼處備復夠頭誇夾奪奩奐奮獎奧妝婦媽嫵嫗媯姍奼婁婭嬈嬌孌娛媧嫻嫿嬰嬋嬸媼嬃嬡嬪嬙嫻媯嬤孫學孿寧寶實寵審憲宮寬賓寢對尋導壽將爾塵嘗堯尷屍盡層屓屜屆屬屢屨嶼歲豈嶇崗峴"
    "嵐島巖嶺嶽崬巋嶨嶧峽嶢嶠崢巒峰嶗崍嶮嶄嶸嶔嶁巔鞏巰幣帥師幃帳簾幟帶幀幫幬幘幗冪幹並么廣莊慶廬廡庫應廟龐廢廎廩開異棄弒張彌弳彎彈強歸當錄彠彥彲徹徵徑徠憶懺憂愾懷態"
    "慫憮慪悵愴憐總懟懌戀恆懇惡慟懨愷惻惱惲悅愨懸慳悞憫驚懼慘懲憊愜慚憚慣慍憤憒願懾憖懣懶懍戇戔戲戧戰戩戱戶撲託執擴捫掃揚擾撫拋摶摳掄搶護報擔擬攏揀擁攔擰撥擇掛摯攣掗"
    "撾撻挾撓擋撟掙擠揮撏挩撈損撿換搗據擄摑擲撣摻摜攬搵撳攙擱摟揯攪攜攝攄擺搖擯攤攖撐攆擷擼攛㩵擻抬攢敵敓斂斆數齋斕鬥斬斷無舊時曠暘曇暱晝曨顯晉曬曉曄暈暉暫𣈶曖術樸機"
    "殺雜權槓條來楊榪傑極構樅樞棗櫪梘棖槍楓梟檯櫃檸檉梔柵標棧櫛櫳棟櫨櫟欄樹棲慄樣欒椏橈楨檔榿橋樺檜槳樁樳夢檮棶槤檢梲欞稜槨槼櫝槧槶欏樿橢槮樓欖榲櫬櫚櫸樧檟檻檳櫧橫檣"
    "櫻櫫櫥櫓櫞簷檁歡歟歐殲歿殤殘殞殮殫殯毆毀轂畢斃氈毿𣯶氌氣氫氬氳匯漢汙湯洶溝沒灃漚瀝淪滄渢溈滬洩濘淚澩瀧瀘濼瀉潑澤涇潔灑窪浹淺漿澆湞溮濁測澮濟瀏滻渾滸濃潯濜塗湧涗"
    "濤澇淶漣潿渦溳渙滌潤澗漲澀澱淵淥漬瀆漸澠漁瀋滲溫遊灣溼濚潰濺漵漊潷滾滯灩灄滿瀅濾濫灤濱灘澦灠瀠瀟瀲濰溈潛潀瀦瀂瀾瀨瀕灝滅燈靈災燦煬爐燉煒熗點煉熾爍爛烴燭煙煩燒燁"
    "燴燙燼熱煥燜燾熅燻愛為爺床牘犛牽犧犢狀獷獁猶狽獮獰獨狹獅獪猙獄猻獫獵獼玀豬貓蝟獻獺璣璵瑒瑪瑋環現瑲璽琺瓏璫琿璡璉瑣瓊瑤璦璸瓔瓚甕甌電畫暢疇癤療瘧癘瘍癧瘲瘡瘋皰痾"
    "癰痙癢瘂癆瘓癇痲痺癉瘮瘞瘻癟癱癮癭癩痴癬癲皂皚皺皸盞鹽監蓋盜盤瞘眥矓著睜睞瞼睪瞶瞞矚矯磯礬礦碭碼磚硨硯碸礪礱礫礎硜矽碩硤磽磑礄確磠礆礙磧磣鹼禮禡禕秘禰禎禱禍稟祿"
    "禪離禿稈種積稱穢穠穭稅穌穩穡穭窮竊竅窵窯竄窩窺竇窶灶豎競篤筍筆筧箋籠籩築篳篩簹箏籌篔籤篠簡籙簀篋籜籮簞簫簣簍籃籛籬籪籟糴類秈糶糲粵糞糧糝餱粽餈緊縶縕緪韁才糹糾紆"
    "紅紂纖紇約級紈纊紀紉緯紜紘純紕紗綱納紝縱綸紛紙紋紡紵紖紐紓線紺紲紱練組紳細織終縐絆紼絀紹繹經紿綁絨結絝繞絰絎繪給絢絳絡絕絞統綆綃絹繡綌綏絛繼綈績緒綾緓續綺緋綽鞝"
    "緄繩維綿綬繃綢綯綹綣綜綻綰綠綴緇緙緗緘緬纜緹緲緝縕繢緦綞緞緶線緱縋緩締縷編緡緣縉縛縟縝縫縗縞纏縭縊縑繽縹縵縲纓縮繆繅纈繚繕繒韁繾繰繯繳纘罌網羅罰罷羆羈羥羨群翹翽"
    "翬耮耬聳恥聶聾職聹聯聵聰肅腸膚骯餚腎腫脹脅膽勝朧腖臚脛膠脈膾髒臍腦膿臠腳唇脫腡臉臘醃膕顎膩靦膃騰臏羶臢輿艤艦艙艫艱豔藝節羋薌蕪蘆蓯葦藶莧萇蒼薴蘇薴蘋範莖蘢蔦塋煢"
    "繭荊薦薘莢蕘蓽萴蕎薈薺蕩榮葷滎犖熒蕁藎蓀蔭蕒葒葤藥蒞萊蓮蒔萵薟獲蕕瑩鶯蓴蘀蘿螢營縈蕭薩蔥蒕蕆蕢蔣蔞醟藍薊蘺蕷鎣驀虆參薔蘞藺藹蒍薀蘄蘊藪蘚蘊櫱虜慮虛蟲虯蟣蝨雖蝦蠆"
    "蝕蟻螞蠁蠶蠔蜆蠱蠣蟶蠻蟄蛺蟯螄蠐蛻蝸蠟蠅蟈蟬蠍螻蠑螿蟎蠨釁眾銜補襯袞襖嫋褘襪襲襏裝襠褌裡褳襝褲襉褸襤襴核見觀覎規覓視覘覽覺覬覡覿覥覦覯覲覷觴觸觶誾讋譽謄訁計訂訃"
    "認譏訐訌討讓訕訖託訓議訊記訒講諱謳詎訝訥許訛論訩訟諷設訪訣證詁訶評詛識詗詐訴診詆謅詞詘詔詖譯詒誆誄試詿詩詰詼誠誅詵話誕詬詮詭詢詣諍該詳詫諢詡譸誡誣語誚誤誥誘誨誑"
    "說誦誒請諸諏諾讀諑誹課諉諛誰諗調諂諒諄誶談讅誼謀諶諜謊諫諧謔謁謂諤諭諼讒諮諳諺諦謎諞諝謨讜謖謝謠謗諡謙謐謹謾謫譾謬譚譖譙讕譜譎讞譴譫讖豶貝貞負貟貢財責賢敗帳貨質"
    "販貪貧貶購貯貫貳賤賁貰貼貴貺貸貿費賀貽賊贄賈賄貲賃賂贓資賅贐賕賑賚賒賦賭齎贖賞賜贔賙賡賠賧賴賵贅賻賺賽賾贗贊贇贈贍贏贛赬趙趕趨趲躉躍蹌蹠躒踐躂蹺蹕躚躋踴躊蹤躓躑"
    "躡蹣躕躥躪躦軀轀車軋軌軒軑軔轉軛輪軟轟軲軻轤軸軹軼軤軫轢軺輕軾載輊轎輈輇輅較輒輔輛輦輩輝輥輞輬輟輜輳輻輯轀輸轡轅轄輾轆轍轔辭闢辯辮邊遼達遷過邁運還這進遠違連遲邇"
    "逕跡適選遜遞邐邏遺遙鄧鄺鄔郵鄒鄴鄰鬱郟鄶鄭鄆酈鄖鄲酇醞醱醯醬釅釃釀醞採釋裡鉤缽鑑鑾鏨針釒釓釔針釘釗釙釕釷釺釧釤鈒釩釣鍆釹鍚釵鈃鈣鈽鈦鉅鈍鈔鍾鈉鋇鋼鈑鈐鑰欽鈞鎢鉤"
    "鈧鍅鈥鈄鈕鈀鈺錢鉦鉗鈷缽鈳鉕鈽鈸鉞鑽鉬鉭鉀鈿鈾鐵鉑鈴鑠鉛鉚鉋鈰鉉鉈鉍鈮鈹鐸鉶銬銠鉺鋩錏銪鋮鋏鋣鐃銍鐺銅鋁銱銦鎧鍘銖銑鋌銩銛鏵銓鎩鉿銚鉻銘錚銫鉸銥鏟銃鐋銨銀銣鑄鐒"
    "鋪鋙錸鋱鏈鏗銷鎖鋰鋥鋤鍋鋯鋨鏽銼鋝鋒鋅鋶鉲鐧銳銻鋃鋟鋦錒錆鍺鍩錯錨錛錡鎝錁錕錩錫錮鑼錘錐錦鑕鍁錈鍃鉳錟錠鍵鋸錳錙鍥鍈鍇鏘鍶鍔鍤鍬鍾鍛鎪鍠鍰鑀鍍鎂鏤鎡鐨鋂鏌鎮鎛鎘"
    "鑷钂鐫鎳錼鎦鎬鎊鎰鎵鑌鎔鏢鏜鏝鏍鏰鏞鏡鏑鏃鏇鏐鐔钁鐐鏷鑥鐓鑭鐠鑹鏹鐙鑊鐳鐶鐲鐮鐿鑔鑣鑞鑱鑲長門閂閃閆閈閉問闖閏闈閒閎間閔閌悶閘鬧閨聞闥閩閭闓閥閣閡閫鬮閱閬闍閾閹"
    "閶鬩閿閽閻閼闡闌闃闠闊闋闔闐闒闕闞闤隊陽陰陣階際陸隴陳陘陝隯隉隕險隨隱隸雋難僱雛讎靂霧霽黴霢靄靚靝靜靨韃鞽韉韝韋韌韍韓韙韞韜韻頁頂頃頇項順須頊頑顧頓頎頒頌頏預顱"
    "領頗頸頡頰頲頜潁熲頦頤頻頮頹頷頴穎顆題顒顎顓顏額顳顢顛顙顥纇顫顬顰顴風颺颭颮颯颶颸颼颻飀飄飆飈飛饗饜飠飣飢飥餳飩餼飪飫飭飯飲餞飾飽飼飿飴餌饒餉餄餎餃餏餅餑餖餓餘"
    "餒餕餜餛餡館餷饋餶餿饞饁饃餺餾饈饉饅饊饌饢馬馭馱馴馳驅馹駁驢駔駛駟駙駒騶駐駝駑駕驛駘驍罵駰驕驊駱駭駢驫驪騁驗騂駸駿騏騎騍騅騌驌驂騙騭騤騷騖驁騮騫騸驃騾驄驏驟驥驦"
    "驤髏髖髕鬢鬹魘魎鯰魚魛魢魷魨魯魴䰾魺鮁鮃鯰鱸鮋鮓鮒鮊鮑鱟鮍鮐鮭鮚鮳鮪鮞鮦鰂鮜鱠鱭鮫鮮鮺鯗鱘鯁鱺鰱鰹鯉鰣鰷鯀鯊鯇鮶鯽鯒鯖鯪鯕鯫鯡鯤鯧鯝鯢鯰鯛鯨鰺鯴鯔鱝鰈鰏鱨鯷鰮鰃"
    "鰓鱷鰍鰒鰉鰁鱂鯿鰠鰲鰭鰨鰥鰩鰟鰜鰳鰾鱈鱉鰻鰵鱅䲁鰼鱖鱔鱗鱒鱯鱤鱧鱣䲘鳥鳩雞鳶鳴鳲鷗鴉鶬鴇鴆鴣鶇鸕鴨鴞鴦鴒鴟鴝鴛鷽鴕鷥鷙鴯鴰鵂鴴鵃鴿鸞鴻鵐鵓鸝鵑鵠鵝鵒鷳鵜鵡鵲鶓鵪"
    "鵾鵯鵬鵮鶉鶊鵷鷫鶘鶡鶚鶻鶖鷀鶥鶩鷊鷂鶲鶹鶺鷁鶼鶴鷖鸚鷓鷚鷯鷦鷲鷸鷺䴉鸇鷹鸌鸏鸛鸘鹺麥麵麩麴麵麼黃黌黶黷黲黽黿鼂鼉鞀鼴齊齏顎齒齔齕齗齟齡齙齠齜齦齬齪齲齷龍龔龕龜"
)

_TO_TRAD = dict(zip(_SIMPLIFIED, _TRADITIONAL))
_TO_SIMP = dict(zip(_TRADITIONAL, _SIMPLIFIED))


def s2t(text):
    """简体转繁体（逐字映射，够用且零依赖）"""
    if not text:
        return ""
    return "".join(_TO_TRAD.get(c, c) for c in text)


def _s2t(text):
    return s2t(text)


def _t2s(text):
    """繁体转简体（搜索时站内是繁体、suggest 给的是简体，需要双向归一）"""
    if not text:
        return ""
    return "".join(_TO_SIMP.get(c, c) for c in text)


# JS 的 escape()/旧版 encodeURIComponent() 会产生 %uXXXX 这种非标准转义，
# urllib.parse.unquote 只认 %XX，会把 %u7B2C 原样留下 -> 服务器 400。
# 站内有源（如 c1.rrcdnbf4.com/video/wanjieduzun/%u7B2C01%u96C6/index.m3u8）
# 就是这么转义的，必须先在 "第" 这个层级解掉。
_RE_UESC = re.compile(r"%u([0-9a-fA-F]{4})")


def _unquote_js(url):
    """解码 URL：先处理 JS 风格 %uXXXX，再按标准 %XX 解码。

    注意顺序：必须先把 %uXXXX 换成真正的字符，否则后续 unquote 会把
    "%u7B2C" 里的 "%7B" 当成 "{" 解掉，拼出乱码地址。
    """
    if not url:
        return ""
    s = url
    # %uXXXX -> 字符；两轮足以处理极少数二次转义
    for _ in range(2):
        if "%u" not in s.lower():
            break
        s = _RE_UESC.sub(lambda m: chr(int(m.group(1), 16)), s)
    # 仅解码一次：已解出的中文再解会破坏（如 %E7%AC%AC 才需要解）
    try:
        s = urllib.parse.unquote(s)
    except Exception:
        pass
    return s



# 四大主分类 -> 拼音段（type 为空时使用该段作为默认值）
CLASSES = [
    {"type_id": "movie",   "type_name": "电影"},
    {"type_id": "drama",   "type_name": "电视剧"},
    {"type_id": "variety", "type_name": "综艺"},
    {"type_id": "anime",   "type_name": "动漫"},
]

# 排序段: time / hits / score
_SORTS = [
    {"n": "时间排序", "v": "time"},
    {"n": "人气排序", "v": "hits"},
    {"n": "评分排序", "v": "score"},
]

_YEARS = [{"n": "全部", "v": ""}] + \
         [{"n": str(y), "v": str(y)} for y in range(2026, 1999, -1)]

# 类型段（即 /show/{type}... 的第一段）
# 说明：站点筛选里"類型-全部"的链接是 /show/1------.html、/show/2------.html ...
#      与 /show/movie------.html 结果一致，两者等价；这里用站点原文的数字段，
#      保证与网站链接逐字一致。
_TYPES = {
    "movie": [
        ("1", "全部"), ("action", "动作片"), ("comedys", "喜剧片"),
        ("lover", "爱情片"), ("sciencefiction", "科幻片"),
        ("terror", "恐怖片"), ("plot", "剧情片"), ("war", "战争片"),
        ("suspense", "悬疑片"), ("horror", "惊悚片"),
        ("fantasy", "奇幻片"), ("documentary", "纪录片"),
        ("animated", "动画电影"),
    ],
    "drama": [
        ("2", "全部"), ("china", "陆剧"), ("taiwan", "台湾剧"),
        ("usa", "欧美剧"), ("hkg", "香港剧"), ("japan", "日剧"),
        ("korea", "韩剧"), ("thailand", "泰国剧"),
    ],
    "variety": [
        ("3", "全部"), ("rihanzongyi", "日韩综艺"), ("daluzongyi", "大陆综艺"),
        ("gangtaizongyi", "港台综艺"), ("oumeizongyi", "欧美综艺"),
    ],
    "anime": [
        ("4", "全部"), ("jpanimation", "日本动漫"), ("chanimation", "大陆动漫"),
        ("usanimation", "欧美动漫"),
    ],
}

# 地区段（必须与站点原文一致：繁体，顺序亦同）
_AREAS = {
    "movie": ["大陸", "香港", "台灣", "美國", "韓國", "日本", "泰國",
              "印度", "英國", "法國", "德國", "加拿大", "西班牙",
              "俄羅斯", "其它"],
    "variety": ["大陸", "香港", "台灣", "美國", "日本", "韓國"],
}


def _build_filters():
    out = {}
    for c in CLASSES:
        tid = c["type_id"]
        # 类型：站点用数字段表示"全部"（1/2/3/4），这里原样保留
        type_val = [{"n": n, "v": v} for v, n in _TYPES.get(tid, [])]

        # 地区：站点"全部"= 省略地区段
        area_val = [{"n": "全部", "v": ""}]
        for a in _AREAS.get(tid, []):
            area_val.append({"n": a, "v": a})

        # 顺序与站点完全一致：類型 → 地區 → 年份 → 排序
        flt = [
            {"key": "class", "name": "类型", "value": type_val},
            {"key": "year",  "name": "年份", "value": _YEARS},
            {"key": "sort",  "name": "排序", "value": _SORTS},
        ]
        if tid in _AREAS:
            flt.insert(1, {"key": "area", "name": "地区", "value": area_val})
        out[tid] = flt
    return out


FILTERS = _build_filters()


# ===================== 正则 =====================
# 海报卡片（/show 列表页、首页、type 页通用）
_RE_CARD = re.compile(
    r'<a\s+[^>]*href="(/detail/[A-Za-z0-9]+\.html)"[^>]*>'
    r'([\s\S]{0,1200}?)</a>',
    re.S | re.I)

# 卡片内字段
_RE_NOTE = re.compile(r'module-item-note">([\s\S]*?)</div>', re.I)
_RE_TITLE = re.compile(r'module-poster-item-title">([\s\S]*?)</div>', re.I)
_RE_IMG = re.compile(
    r'<img[^>]*?(?:data-original|data-src|src)="([^"]+)"', re.I)

# 卡片型条目（热榜 / label 页）
_RE_CARD2 = re.compile(
    r'<div class="module-card-item[^"]*">([\s\S]*?)'
    r'<div class="module-card-item-footer">',
    re.S | re.I)
_RE_CARD2_LINK = re.compile(r'href="(/detail/[A-Za-z0-9]+\.html)"', re.I)
_RE_CARD2_TITLE = re.compile(r'<strong>([\s\S]*?)</strong>', re.I)
_RE_CARD2_NOTE = re.compile(r'module-item-note">([\s\S]*?)</div>', re.I)
_RE_CARD2_PIC = re.compile(r'data-original="([^"]+)"', re.I)

# 详情页
_RE_H1 = re.compile(r'<h1>([\s\S]*?)</h1>', re.I)
_RE_DETAIL_PIC = re.compile(
    r'module-info-poster[\s\S]{0,400}?<img[^>]*?data-original="([^"]+)"', re.I)
_RE_INTRO = re.compile(
    r'module-info-introduction-content">([\s\S]*?)</div>', re.I)
_RE_ITEM = re.compile(
    r'<span class="module-info-item-title">([^<]*)：</span>'
    r'<div class="module-info-item-content"[^>]*>([\s\S]*?)</div>', re.I)
_RE_TAG = re.compile(
    r'module-info-tag-link"><a title="([^"]*)"[^>]*>', re.I)

# 线路标签（顺序即真实线路顺序）
_RE_TAB = re.compile(
    r'<div class="module-tab-item tab-item[^"]*"(?:\s+data-dropdown-value="([^"]*)")?'
    r'[^>]*>\s*<span>([^<]*)</span>(?:<small>(\d+)</small>)?', re.I)

# 剧集链接
_RE_EP = re.compile(
    r'<a class="module-play-list-link"\s+href="([^"]+)"[^>]*>\s*'
    r'<span>([^<]*)</span>', re.I)

# 单条线路的剧集容器（站内多个 panel 都复用 id="panel1"，按出现顺序切块）
_RE_PANEL = re.compile(r'<div class="module-list[^"]*"', re.I)

# 播放页
_RE_PLAYER = re.compile(r'var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*</script>', re.I)

# 分页
# href 与 class 的顺序在站内并不固定，这里统一放宽为"同一 <a ...> 标签内"
_RE_NEXT = re.compile(
    r'<a\s[^>]*href="([^"]*)"[^>]*>\s*下一[頁页]', re.I)
_RE_LAST = re.compile(
    r'<a\s[^>]*href="([^"]*)"[^>]*>\s*尾[頁页]', re.I)
_RE_PAGE_NUM = re.compile(
    r'<a\s[^>]*href="([^"]*)"[^>]*page-number[^>]*>\s*(\d+)\s*</a>', re.I)

# 路径解析: /show/{type}-{area}--{page}-{sort}--{year}.html
_RE_SHOW_PATH = re.compile(r'/show/([^/]*?)\.html$', re.I)

# 播放页地址：/userpy/{slug}-{线路序号}-{集数}.html
_RE_PLAY_HREF = re.compile(r'/userpy/([^-/]+)-(\d+)-(\d+)\.html', re.I)

# m3u8 变体流（多码率）
_RE_VARIANT = re.compile(r'#EXT-X-STREAM-INF[^\n]*\n([^\n#]+)', re.I)

# 切片序号：0000123.ts / xxx-12.ts（用于推算后续切片，实现滚动预取）


# ======================================================================
# 播放加速：线路测速 + 分片级并发代理
# 站点「無水印」源单连接限速约 100~160 KB/s，1080P 播放必然卡顿；
# 实测同源并发 8 路可达 1100+ KB/s（约 7 倍），因此：
#   1) 详情页对每条线路取首集 m3u8 测速并缓存，播放时按速度选源
#   2) localProxy 对 m3u8 统一改写，切片走本地并发预取，匀速吐给播放器
# ======================================================================
_SEG_SEM = None
_SEG_MEM = {}          # url -> (ts, bytes)
_SEG_MEM_MAX = 240     # 内存缓存切片数（约 100~180MB，够缓冲即可，不必囤太多）
_WINDOW = 30           # 预取窗口：30 片 ≈ 90s 素材
_LOW_WATER = 14        # 连续缓冲低于 14 片（约 42s）就补货：稳态覆盖更厚
_BATCH = 10            # 每次补货片数
_SPEED_MEM = {}        # 线路名 -> 实测速度(KB/s)，跨片复用，避免重复测速
_PAUSE_UNTIL = [0.0]   # 播放器优先：此时刻之前填充线程不出新流量


def _player_first(seconds):
    """播放头要片时把预取压住几秒，把带宽让给播放器"""
    try:
        _PAUSE_UNTIL[0] = max(_PAUSE_UNTIL[0], time.time() + seconds)
    except Exception:
        pass
# 并发数：实测该 CDN 对单连接限死 ~150KB/s，16 路可达 1400~1900KB/s。
# 但因为采用"水位补货"，稳态只用 8~16 路，且绝不与播放头抢带宽。
_PREFETCH = 16
_PREFETCH_BURST = 16   # 起播突发并发，与稳态一致
_SSL_CTX = None


def _ssl_ctx():
    """部分 CDN 用自签/非常见证书链，TLS 校验失败时降级"""
    global _SSL_CTX
    if _SSL_CTX is None:
        try:
            _SSL_CTX = ssl.create_default_context()
            _SSL_CTX.check_hostname = False
            _SSL_CTX.verify_mode = ssl.CERT_NONE
        except Exception:
            _SSL_CTX = None
    return _SSL_CTX


def _ascii_url(url):
    """把含中文等非 ASCII 字符的 URL 重新做 percent-encoding。

    站内有源把集数写在中文明文路径里（.../video/wanjieduzun/第01集/index.m3u8），
    http.client 只吃 ASCII，直接把 str 塞进去会抛
    "'ascii' codec can't encode character ..."。这里保留已有的 %XX
    和 URL 结构字符，只转义非 ASCII 部分。
    """
    try:
        url.encode("ascii")
        return url
    except UnicodeEncodeError:
        pass
    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")


# 无水印源的两个域名 NOT 互为镜像：换域名直接 401（鉴权绑域名）。
# 所以这里不做域名互切，只做"同域名重试"——它的 CDN 偶发抽风
# （连接复位/空响应/超时），重试一两次就能过。
def _mirror_url(url):
    """保留占位：曾经尝试过域名互切，实测 401，已废弃（不再调用）"""
    return url


def _http_get(url, timeout=12, referer="", retries=2):
    """带重试的 GET。

    无水印源的 CDN 会偶发抽风（连接复位/空响应/超时），
    一次失败就把整集判死刑太冤——默认重试 2 次，间隔递增。
    """
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(_ascii_url(url), headers={
                "User-Agent": UA,
                "Referer": referer or HOST + "/",
                "Accept": "*/*",
                "Connection": "close",
            })
            data = urllib.request.urlopen(req, timeout=timeout,
                                          context=_ssl_ctx()).read()
            if data:
                return data
            last = IOError("empty response")
        except Exception as e:
            last = e
        if i < retries:
            time.sleep(0.3 * (i + 1))
    raise last


def _abs(baseurl, seg):
    if not seg:
        return seg
    if seg.startswith("http://") or seg.startswith("https://"):
        return seg
    if seg.startswith("//"):
        return "https:" + seg
    if seg.startswith("/"):
        p = urllib.parse.urlparse(baseurl)
        return "%s://%s%s" % (p.scheme, p.netloc, seg)
    return baseurl.rsplit("/", 1)[0] + "/" + seg


def _speed_probe(m3u8_url, sample=3, timeout=8):
    """返回 (速度KB/s, 是否有效)；只拉前几个切片做样本，开销很小"""
    try:
        t0 = time.time()
        body = _http_get(m3u8_url, timeout=timeout)
        if not body:
            return 0.0, False
        txt = body.decode("utf-8", "ignore")
        # 变体流先下钻一层
        if "#EXT-X-STREAM-INF" in txt:
            mv = _RE_VARIANT.search(txt)
            if mv:
                sub = _abs(m3u8_url, mv.group(1).strip())
                m3u8_url = sub
                body = _http_get(sub, timeout=timeout)
                txt = body.decode("utf-8", "ignore")
        segs = [l.strip() for l in txt.splitlines()
                if l.strip() and not l.startswith("#")]
        if not segs:
            return 0.0, False
        # 首个切片必测；耗时过长直接判慢
        total = 0
        for s in segs[:sample]:
            u = _abs(m3u8_url, s)
            total += len(_http_get(u, timeout=timeout))
        dt = max(time.time() - t0, 0.001)
        return (total / 1024.0) / dt, True
    except Exception:
        return 0.0, False


_INFLIGHT = {}
_INFLIGHT_LOCK = threading.Lock()


def _seg_fetch(url, timeout=15):
    """带内存缓存 + 同 URL 去重的下载

    去重很关键：预热线程与播放器请求可能同时要同一个 m3u8，
    不去重就会重复下两次、反而更慢。
    """
    now = time.time()
    hit = _SEG_MEM.get(url)
    if hit and now - hit[0] < 120:
        return hit[1]

    with _INFLIGHT_LOCK:
        ev = _INFLIGHT.get(url)
        if ev is None:
            ev = [threading.Event(), None]
            _INFLIGHT[url] = ev
            owner = True
        else:
            owner = False

    if not owner:
        ev[0].wait(timeout)
        if ev[1] is not None:
            return ev[1]

    try:
        data = _http_get(url, timeout=timeout)
        if len(_SEG_MEM) > _SEG_MEM_MAX:
            for k in sorted(_SEG_MEM,
                            key=lambda x: _SEG_MEM[x][0])[:len(_SEG_MEM) // 2]:
                _SEG_MEM.pop(k, None)
        _SEG_MEM[url] = (time.time(), data)
        ev[1] = data
        return data
    finally:
        if owner:
            ev[0].set()
            with _INFLIGHT_LOCK:
                _INFLIGHT.pop(url, None)


def _concurrent_download(urls, workers=_PREFETCH):
    """并发拉取，返回 {url: bytes}，失败的 key 不出现

    用 as_completed 而不是按顺序收：谁先回来先入库，任何一路慢都不会
    拖住后面的切片（对"下一片必须最快"这点至关重要）。
    """
    out = {}
    if not urls:
        return out
    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_seg_fetch, u): u for u in urls}
            for f in as_completed(futs):
                u = futs[f]
                try:
                    out[u] = f.result()
                except Exception:
                    pass
    except Exception:
        pass
    return out


class Spider(Spider):

    def getName(self):
        return "99影视"

    def init(self, extend=""):
        try:
            self.extend = json.loads(extend) if extend else {}
        except Exception:
            self.extend = {}

        self.site_url = (self.extend.get("site") or HOST).rstrip("/")
        self.headers = {
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": self.site_url + "/",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_pic = DEFAULT_PIC
        self._play_cache = {}
        self._idx_cache = {}
        self._native_bad = False
        self._warmed = False

        # 本地代理基址（TVBox 会注入；取不到就退回直链，不会影响播放）
        self._seg_seq = {}
        self._seg_index = {}      # 切片url -> (播放列表key, 下标)
        self._playlist = {}       # 播放列表key -> [切片url...]（真实顺序）
        self._fill_state = {}
        self._m3u8_cache = {}
        self._prewarm_evt = {}    # m3u8 -> Event，预热完成信号
        self._variant_of = {}
        self._sid_name = {}
        self._cur_line = ""
        self._proxy_base = ""
        try:
            base = self.getProxyUrl() or ""
            self._proxy_base = base
            if base:
                self.log("proxy base: %s" % base)
        except Exception:
            self._proxy_base = ""

        self.log("init: site=%s" % self.site_url)

    # ------------------------------------------------------------------
    # 基础请求
    # ------------------------------------------------------------------
    def _warm_up(self):
        if self._warmed:
            return
        try:
            self._fetch(self.site_url + "/", timeout=15)
            self._warmed = True
            self.log("预热完成")
        except Exception as e:
            self.log("预热失败: %s" % e)

    def _fetch(self, url, timeout=30, headers=None, allow_redirects=True):
        try:
            h = dict(self.headers)
            if headers:
                h.update(headers)
            try:
                rsp = self.fetch(url, headers=h, timeout=timeout,
                                 allow_redirects=allow_redirects)
            except TypeError:
                rsp = self.fetch(url, headers=h, timeout=timeout)

            text = ""
            if hasattr(rsp, "text"):
                text = rsp.text or ""
            elif hasattr(rsp, "content"):
                text = rsp.content.decode("utf-8", "ignore")
            else:
                text = str(rsp)
            return text
        except Exception as e:
            self.log("fetch FAIL %s -> %s" % (url, e))
            return ""

    def _fetch_json(self, url, timeout=20):
        txt = self._fetch(url, timeout=timeout, headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        })
        if not txt:
            return None
        try:
            return json.loads(txt)
        except Exception:
            self.log("json FAIL %s" % url)
            return None

    def _fix_url(self, url):
        if not url:
            return ""
        url = url.strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        if url.startswith("/"):
            return self.site_url + url
        return urllib.parse.urljoin(self.site_url + "/", url)

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = (s.replace("&nbsp;", " ").replace("\xa0", " ")
              .replace("&amp;", "&").replace("&quot;", '"')
              .replace("&#39;", "'").replace("&lt;", "<")
              .replace("&gt;", ">").replace("&middot;", "·"))
        s = re.sub(r"[ \t\r\f\v]+", " ", s)
        s = re.sub(r"\n{2,}", "\n", s)
        return s.strip()

    # ------------------------------------------------------------------
    # 列表解析
    # ------------------------------------------------------------------
    def _parse_cards(self, html):
        """解析海报卡片，返回 [{vod_id, vod_name, vod_pic, vod_remarks}]"""
        videos = []
        if not html:
            return videos
        seen = set()

        for m in _RE_CARD.finditer(html):
            href = m.group(1)
            inner = m.group(2)
            if href in seen:
                continue

            name = ""
            mt = _RE_TITLE.search(inner)
            if mt:
                name = self._clean(mt.group(1))
            if not name:
                # 回退：<a ... title="xx" ...>
                head = html[m.start():m.start() + 300]
                mt2 = re.search(r'title="([^"]*)"', head)
                if mt2:
                    name = self._clean(mt2.group(1))

            pic = ""
            mp = _RE_IMG.search(inner)
            if mp:
                pic = mp.group(1)
                if "loading.svg" in pic or pic.endswith("/"):
                    pic = ""

            note = ""
            mn = _RE_NOTE.search(inner)
            if mn:
                note = self._clean(mn.group(1))

            if not name:
                continue

            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": note,
            })

        # 补充：热榜/卡片型
        if not videos:
            for m in _RE_CARD2.finditer(html):
                inner = m.group(1)
                ml = _RE_CARD2_LINK.search(inner)
                if not ml:
                    continue
                href = ml.group(1)
                if href in seen:
                    continue
                name = ""
                mt = _RE_CARD2_TITLE.search(inner)
                if mt:
                    name = self._clean(mt.group(1))
                if not name:
                    continue
                pic = ""
                mp = _RE_CARD2_PIC.search(inner)
                if mp:
                    pic = mp.group(1)
                note = ""
                mn = _RE_CARD2_NOTE.search(inner)
                if mn:
                    note = self._clean(mn.group(1))
                seen.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": name,
                    "vod_pic": self._fix_url(pic) or self.default_pic,
                    "vod_remarks": note,
                })

        return videos

    def _split_show_path(self, path):
        """把 /show/xxx.html 拆成 7 段 [type, area, '', page, sort, '', year]"""
        m = _RE_SHOW_PATH.search(path or "")
        if not m:
            return None
        core = m.group(1)
        parts = core.split("-")
        if len(parts) != 7:
            return None
        return parts

    def _page_count(self, html, pg):
        """返回总页数；无法判断时返回 pg+1 以便续翻"""
        if not html:
            return int(pg)
        mx = 0
        for _u, p in _RE_PAGE_NUM.findall(html):
            try:
                mx = max(mx, int(p))
            except Exception:
                pass

        ml = _RE_LAST.search(html)
        if ml:
            parts = self._split_show_path(ml.group(1))
            if parts:
                try:
                    mx = max(mx, int(parts[3] or 0))
                except Exception:
                    pass

        if mx > 0:
            return mx

        # 没有尾页信息：有下一页就 pg+1
        if _RE_NEXT.search(html):
            return int(pg) + 1
        return int(pg)

    # ------------------------------------------------------------------
    # 首页 / 分类
    # ------------------------------------------------------------------
    def homeContent(self, filter=False):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        self._warm_up()
        html = self._fetch(self.site_url + "/", timeout=25)
        self.log("home HTML 长度: %d" % len(html))
        videos = self._parse_cards(html)
        self.log("home 影片: %d" % len(videos))
        return {"list": videos}

    def _build_show_url(self, tid, extend, page):
        """拼装 /show/{type}-{area}-{page}-{sort}-{year}.html

        该站 URL 固定 7 段（用 - 切分）：
            [类型] [地区] [''] [页码] [排序] [''] [年份]
        站点会自动省略"默认值"对应的段，以下为逐条抓取站点自身链接得到的规则：

            默认      /show/movie------.html
            类型      /show/china------.html
            年份      /show/drama------2024.html
            排序      /show/drama----hits--.html
            地区      /show/movie-%E5%A4%A7%E9%99%B8-----.html
            分页      /show/movie---2---.html
            组合      /show/movie-%E5%A4%A7%E9%99%B8--2-hits--2024.html

        关键点：**只有"地区/类型 + 排序"同时出现时才会写 sort 段**；
        纯分页（/show/movie---2---.html）与"仅年份"都不写 sort。
        多写一段会导致该站返回 0 条，这是之前排序错乱的根因。
        """
        type_seg = (extend.get("class") or "").strip() or \
                   {"movie": "movie", "drama": "drama",
                    "variety": "variety", "anime": "anime"}.get(tid, "movie")
        area = (extend.get("area") or "").strip()
        sort = (extend.get("sort") or "").strip()
        year = (extend.get("year") or "").strip()

        area_seg = urllib.parse.quote(area, safe="") if area else ""
        page_seg = str(page) if int(page) > 1 else ""

        # 排序段：站点仅在"非时间排序"或"已选地区"时才显式写
        if sort and sort != "time":
            sort_seg = sort
        elif area_seg:
            sort_seg = "time"
        else:
            sort_seg = ""

        return "%s/show/%s-%s--%s-%s--%s.html" % (
            self.site_url, type_seg, area_seg, page_seg, sort_seg, year)

    def categoryContent(self, tid, pg, filter, extend):
        self._warm_up()
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        if page < 1:
            page = 1

        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}

        ext = {}
        for k, v in extend.items():
            if v in ("", None, "全部"):
                continue
            ext[k] = v

        url = self._build_show_url(tid, ext, page)
        self.log("category: %s" % url)

        html = self._fetch(url, timeout=25)
        self.log("  HTML 长度: %d" % len(html))

        videos = self._parse_cards(html)
        pagecount = self._page_count(html, page)
        self.log("  影片: %d 总页数: %d" % (len(videos), pagecount))

        return {
            "list": videos,
            "page": page,
            "pagecount": pagecount,
            "limit": 40,
            "total": pagecount * 40,
        }

    # ------------------------------------------------------------------
    # 搜索
    # 首选站点原生搜索 /search.html?wd=xx
    # 备选站内建议接口 /index.php/ajax/suggest?mid=1&wd=xx
    # ------------------------------------------------------------------
    def _search_native(self, kw, page):
        """站点原生搜索，返回 (videos, pagecount) 或 (None, 1)"""
        if self._native_bad:
            return None, 1
        url = "%s/search.html?wd=%s" % (
            self.site_url, urllib.parse.quote(kw))
        if page > 1:
            url += "&page=%d" % page
        html = self._fetch(url, timeout=20)
        if not html:
            return None, 1
        # 触发 Cloudflare 托管挑战：本机 IP 被拦，后续不再尝试
        if "Just a moment" in html or "cf_chl_opt" in html or len(html) < 3000:
            self._native_bad = True
            self.log("原生搜索被 WAF 拦截，改用 suggest 接口")
            return None, 1
        if 'module-poster-item' not in html and 'module-card-item' not in html:
            return None, 1
        videos = self._parse_cards(html)
        if not videos:
            return None, 1
        return videos, self._page_count(html, page)

    def _search_suggest(self, kw, page, limit=30):
        """站内建议接口，返回 (videos, pagecount, total)

        实测要点：
          - limit 参数真的生效，limit=100 可一次拿回全部命中（无需翻页）；
          - 接口**不返回 type_id**，所以详情页短码只能靠数据接口按分区定位。
        """
        api = "%s/index.php/ajax/suggest?mid=1&wd=%s&limit=%d" % (
            self.site_url, urllib.parse.quote(kw), limit)
        if page > 1:
            api += "&page=%d" % page
        data = self._fetch_json(api)
        videos = []
        if not data or not isinstance(data, dict) or not data.get("list"):
            return videos, 1, 0

        total = int(data.get("total") or 0)
        pc = int(data.get("pagecount") or 1)
        for it in data["list"]:
            vid = it.get("id")
            name = self._clean(it.get("name") or "")
            if not name:
                continue
            pic = it.get("pic") or ""
            en = it.get("en") or ""
            videos.append({
                # sid: vod_id@拼音@片名 —— 详情时到数据接口查真实短码
                "vod_id": "sid:%s@%s@%s" % (vid, en, name),
                "vod_name": name,
                "vod_pic": self._fix_url(pic) or self.default_pic,
                "vod_remarks": "",
            })
        return videos, (pc if pc > 0 else 1), total

    def searchContent(self, key, quick, pg="1"):
        self._warm_up()
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1

        kw = (key or "").strip()
        if not kw:
            return {"list": [], "page": page, "pagecount": 1,
                    "limit": 30, "total": 0}

        # 站点为繁体，简繁各试一次
        kws = []
        for cand in (kw, s2t(kw)):
            if cand and cand not in kws:
                kws.append(cand)

        # 1) 原生搜索
        for k in kws:
            videos, pagecount = self._search_native(k, page)
            if videos:
                self.log("search(原生) 命中 %s: %d 条" % (k, len(videos)))
                return {
                    "list": videos, "page": page,
                    "pagecount": pagecount, "limit": 40,
                    "total": pagecount * 40,
                }

        # 2) 建议接口兜底
        for k in kws:
            videos, pagecount, total = self._search_suggest(k, page)
            if videos:
                self.log("search(suggest) 命中 %s: %d 条" % (k, len(videos)))
                return {
                    "list": videos, "page": page,
                    "pagecount": pagecount, "limit": 30,
                    "total": total or len(videos),
                }

        self.log("search 无结果: %s" % kw)
        return {"list": [], "page": page, "pagecount": 1,
                "limit": 30, "total": 0}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    # ------------------------------------------------------------------
    # 搜索 id 解析：suggest 的 id -> 详情页 slug
    # 站点的 detail slug 为随机短码，与 vod_id 无换算关系，
    # 因此按「片名」在站内列表页建立索引后匹配，索引带缓存。
    # ------------------------------------------------------------------
    def _resolve_sid(self, vod_id, name=""):
        """把 sid:{id}@{en}@{name} 解析成 /detail/xxx.html

        关键点：站点的详情页 slug 是随机短码（如 /detail/ufk55F.html），
        与 vod_id **没有换算关系**。所以唯一可靠的途径是查站点的
        数据接口 /index.php/ajax/data，它每条都带 detail_link。
        """
        raw = str(vod_id or "").strip()
        vid = ""

        if raw.startswith("sid:"):
            raw = raw[4:]
            parts = raw.split("@")
            vid = parts[0].strip()
            if len(parts) >= 3:
                name = parts[-1].strip()
            elif len(parts) == 2 and not name:
                name = parts[1].strip()
            raw = vid

        if not raw:
            return ""

        # 已是详情路径 / 完整 URL
        if raw.startswith("http"):
            return self._fix_url(raw)
        if raw.startswith("/"):
            return self._fix_url(raw)

        key = "sid:%s" % raw
        if key in self._idx_cache:
            return self._idx_cache[key]

        # 1) 按 id / 片名定位真实详情短码（最可靠）
        link = self._detail_link_by_id(raw, name)
        if link:
            self._idx_cache[key] = link
            return link

        # 2) 仍未命中：不做"直接拼 id"的假猜测（站点短码是随机串，
        #    拼出来必然 404）。name 已在第 1 步里参与定位，这里直接收尾。
        self.log("  详情短码未定位: id=%s name=%s" % (raw, name))
        return ""

    def _detail_link_by_id(self, vid, name=""):
        """按 vod_id / 片名定位详情页（短码随机，只能靠列表页反查）

        站点限制（都实测过）：
          - 详情短码是随机串（/detail/ufk55F.html），与 vod_id 无换算关系；
          - 搜索页 /search* 被 Cloudflare WAF 直接 403；
          - 数据接口 /index.php/ajax/data 的 ids/limit/page 参数基本失效
            （page>=50 后永远返回首页内容，ids 被忽略）。
        因此唯一稳的路是：在分类列表页里按片名找。用年份把总页数从
        上千页压到几十页，再并行扫，通常 1~3s 内能定位。
        """
        try:
            vid = int(vid)
        except Exception:
            vid = 0

        key = "dl:%s:%s" % (vid, name)
        cache = self._idx_cache
        if key in cache:
            return cache[key]

        # 0) 数据接口最新 10 条里常能撞上（新片多），几乎零成本
        try:
            d = json.loads(_http_get(
                "%s/index.php/ajax/data?mid=1&ids=%d" % (self.site_url, vid),
                timeout=12).decode("utf-8", "ignore"))
            for it in (d.get("list") or []):
                if vid and int(it.get("vod_id") or 0) == vid and it.get("detail_link"):
                    u = self._fix_url(it["detail_link"])
                    cache[key] = u
                    return u
        except Exception:
            pass

        if not name:
            return ""

        # 1) 分类列表页按片名扫（年份分片，并行）
        hit = self._scan_by_name(name)
        if hit:
            cache[key] = hit
            return hit
        return ""

    def _scan_by_name(self, name):
        """在分类列表页里按片名匹配（简繁双向归一）

        现实约束（实测）：
          - suggest 的数据源与前台列表页并不完全一致，少量片
            （如"奇幻西游：新世界" id=100027）在列表页里根本不存在；
          - 列表页每页 40 条、每类上千页，全量扫不现实。
        因此策略是"有界 + 快返回"：
          1) 先查已建好的名字索引（首页/今日更新/各类前 8 页）；
          2) 再并行扫各类前若干页（新片都在前面）；
          3) 一旦命中立即返回，并把结果长期缓存；
          4) 整体最多耗 _SCAN_BUDGET 秒，超时就放弃，绝不拖住详情页。
        """
        name = self._clean(name)
        if not name:
            return ""
        ck = "nm:%s" % name
        if ck in self._idx_cache:
            return self._idx_cache[ck]

        want = set()
        for cand in (name, _t2s(name), s2t(name)):
            c = self._clean(cand)
            if c:
                want.add(c)

        def same(a):
            a = self._clean(a or "")
            return bool(a) and (a in want or _t2s(a) in want or s2t(a) in want)

        # 1) 全局名字索引
        idx = self._get_name_index()
        for k, v in list(idx.items()):
            if isinstance(k, str) and k.startswith("name:") and same(k[5:]):
                self._idx_cache[ck] = v
                return v

        types = ("movie", "drama", "variety", "anime")
        years = [""] + [str(y) for y in range(2026, 2000, -1)]

        def probe(args):
            c, yr, p = args
            try:
                u = self._build_show_url(c, {"year": yr} if yr else {}, p)
                for v in self._parse_cards(self._fetch(u, timeout=8)):
                    if same(v.get("vod_name")):
                        return self._fix_url(v["vod_id"])
            except Exception:
                pass
            return ""

        # 先扫"无年份 + 今年"的前 5 页（覆盖绝大多数影片，通常 <2s 命中）
        first = [(c, y, p) for y in years[:2] for c in types for p in range(1, 6)]
        hit = self._run_probes(first, probe, budget=3.0)
        if hit:
            self._idx_cache[ck] = hit
            return hit

        # 再往深处扫一轮（有界），仍不中就直接放弃，绝不让用户干等
        batch = [(c, "", p) for c in types for p in range(6, 13)]
        hit = self._run_probes(batch, probe, budget=3.0)
        if hit:
            self._idx_cache[ck] = hit
            return hit
        return ""

    def _run_probes(self, tasks, probe, budget=5.0):
        """并行探针，命中即返回；整体有硬性时间预算"""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            ex = ThreadPoolExecutor(max_workers=16)
            futs = [ex.submit(probe, t) for t in tasks]
            deadline = time.time() + budget
            try:
                for f in as_completed(futs, timeout=budget):
                    try:
                        r = f.result()
                    except Exception:
                        r = ""
                    if r:
                        for g in futs:
                            g.cancel()
                        return r
                    if time.time() > deadline:
                        break
            except Exception:
                pass
            finally:
                ex.shutdown(wait=False)
        except Exception:
            pass
        return ""

    def _lookup_by_name(self, name):
        """按片名在列表页里找详情页 slug"""
        name = self._clean(name)
        if not name:
            return ""

        key = "name:%s" % name
        if key in self._idx_cache:
            return self._idx_cache[key]

        # 1) 先查已建好的全局索引
        idx = self._get_name_index()
        hit = idx.get(name)
        if hit:
            self._idx_cache[key] = hit
            return hit

        # 2) 用站内 suggest 拿到更精确的名字（可能带后缀），再匹配
        #    仍失败则在扩展页里做一次深搜
        for url in self._deep_scan_urls(name):
            html = self._fetch(url, timeout=20)
            videos = self._parse_cards(html)
            for v in videos:
                if v["vod_name"] == name:
                    full = self._fix_url(v["vod_id"])
                    self._idx_cache[key] = full
                    return full
        return ""

    def _get_name_index(self):
        """首页 + 今日更新 + 四类前若干页 的 片名->详情页 索引（带缓存）"""
        if self._idx_cache.get("__built__"):
            return self._idx_cache

        urls = [self.site_url + "/", self.site_url + "/label/new.html"]
        for c in ("movie", "drama", "variety", "anime"):
            urls.append("%s/show/%s------.html" % (self.site_url, c))
            # 最新内容优先，前 8 页足以覆盖绝大多数搜索目标
            for p in range(2, 9):
                urls.append(self._build_show_url(c, {}, p))

        def _load(u):
            try:
                return self._parse_cards(self._fetch(u, timeout=20))
            except Exception:
                return []

        results = []
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=10) as ex:
                results = list(ex.map(_load, urls))
        except Exception:
            results = [_load(u) for u in urls]

        for videos in results:
            for v in videos:
                nm = v["vod_name"]
                if nm and ("name:%s" % nm) not in self._idx_cache:
                    self._idx_cache["name:%s" % nm] = self._fix_url(v["vod_id"])

        self._idx_cache["__built__"] = True
        self.log("名称索引构建完成: %d 条" % len(
            [k for k in self._idx_cache if k.startswith("name:")]))
        return self._idx_cache

    def _deep_scan_urls(self, name):
        """索引未命中时的补充扫描页（首页、今日更新）"""
        return [self.site_url + "/", self.site_url + "/label/new.html"]

    # ------------------------------------------------------------------
    # 详情
    # ------------------------------------------------------------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        vod_id = str(ids[0])
        url = self._resolve_sid(vod_id)
        if not url:
            self.log("detail: id 无法解析 %s" % vod_id)
            return {"list": []}

        self.log("detail: %s" % url)
        html = self._fetch(url, timeout=25)
        self.log("  HTML 长度: %d" % len(html))
        if not html:
            return {"list": []}

        # 站点 404 / 失效页（module-prompt）
        if 'module-prompt' in html or "居然不在這個頁面" in html:
            self.log("  详情页 404: %s" % url)
            return {"list": []}

        # 标题
        name = ""
        m = _RE_H1.search(html)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = self._clean(m.group(1).split("_")[0].strip())
        if not name:
            name = vod_id

        # 封面
        pic = ""
        m = _RE_DETAIL_PIC.search(html)
        if m:
            pic = self._fix_url(m.group(1))
        if not pic:
            pic = self.default_pic

        # 副标题（又名）
        sub = ""
        # 年份 / 地区标签
        tags = _RE_TAG.findall(html)
        year = tags[0] if len(tags) > 0 else ""
        area = tags[1] if len(tags) > 1 else ""

        # 简介
        content = ""
        m = _RE_INTRO.search(html)
        if m:
            content = self._clean(m.group(1))
        if not content:
            m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*'
                          r'content=["\']([^"\']*)["\']', html, re.I)
            if m:
                content = self._clean(m.group(1))

        # 元信息
        director = ""
        actor = ""
        remark = ""
        for label, val in _RE_ITEM.findall(html):
            label = self._clean(label)
            if label in ("导演", "導演"):
                director = re.sub(r"\s*/\s*", ", ", self._clean(val)).strip(", /")
            elif label in ("主演", "演員", "演员"):
                actor = re.sub(r"\s*/\s*", ", ", self._clean(val)).strip(", /")
            elif label in ("备注", "備註"):
                remark = self._clean(val)
            elif label in ("又名", "別名", "别名"):
                sub = self._clean(val)

        if content:
            content = INTRO_PREFIX + "\n" + content
        else:
            content = INTRO_PREFIX

        # ===== 线路与剧集 =====
        # 站点的「标签线路」与「剧集列表」是两段独立输出：
        #   <div class="module-tab-item tab-item" data-dropdown-value="DY"><span>DY</span><small>538</small></div>
        #   ...（逐条 tab）
        #   <div class="module-list ..." id="panel1"><a class="module-play-list-link" href="/userpy/{slug}-3-1.html">
        #   ...（每个 tab 对应一个 panel，panel 的出现顺序 = tab 顺序）
        #
        # 注意：/userpy/{slug}-{n}-{ep}.html 里的 n **不是**界面顺序，
        # 例如 7 条线时 tab 顺序是 DY,BY,LY,SY,WY,RY,無水印，
        # 而 n 依次是 5,1,2,3,4,6,7（甚至 1..7 混排）。
        # 早先版本用「第 i 个 tab 配第 i 个 n」的位置猜测，电视剧碰巧对得上，
        # 综艺/动漫的 n 顺序是乱的，配错后 线路名↔剧集 完全错位，
        # 点开某一线路拿到的地址属于另一条源 -> 播放直接失败。
        #
        # 正确做法：以 panel 为单位切块，panel 内第一个链接的 n 就是该 tab
        # 真正对应的站内序号；顺序严格取 tab 顺序（= panel 顺序），
        # 与网站界面完全一致。
        tabs = []
        for m in _RE_TAB.finditer(html):
            tname = self._clean(m.group(2))
            if tname:
                tabs.append(tname)

        # 按 panel 切块（每块只含一条线路的剧集）
        blocks = []
        cuts = [m.start() for m in _RE_PANEL.finditer(html)]
        if cuts:
            cuts.append(len(html))
            for i in range(len(cuts) - 1):
                seg = html[cuts[i]:cuts[i + 1]]
                items = []
                for href, ep_name in _RE_EP.findall(seg):
                    href = href.replace("&amp;", "&")
                    items.append((self._clean(ep_name) or "正片",
                                  self._fix_url(href)))
                if items:
                    blocks.append(items)
        if not blocks:
            # 兜底：没有 panel 结构时，按链接出现顺序整体成一条线路
            items = []
            for href, ep_name in _RE_EP.findall(html):
                href = href.replace("&amp;", "&")
                items.append((self._clean(ep_name) or "正片",
                              self._fix_url(href)))
            if items:
                blocks.append(items)

        self.log("  标签线路: %s" % tabs)
        self.log("  剧集块: %d 组 / 共 %d 集"
                 % (len(blocks), sum(len(b) for b in blocks)))

        if not blocks:
            return {"list": []}

        play_from = []
        play_url = []
        for i, items in enumerate(blocks):
            if i < len(tabs):
                alias = tabs[i]
            else:
                alias = "线路%d" % (i + 1)
            # 记下站内序号 -> 线路名，供播放页反查（_line_name）
            mm = re.search(r"-(\d+)-\d+\.html", items[0][1])
            if mm:
                self._sid_name[mm.group(1)] = alias
            play_from.append(alias)
            play_url.append("#".join("%s$%s" % (n, h) for n, h in items))

        # 线路顺序严格与网站一致，不做任何重排、不在线路名上加标注。
        # （早期版本曾按实测速度重排并把速度拼进线路名，显示成
        #   "DY·1920KB/s" 这种怪异样子，且破坏了站点的线路顺序，
        #   已废弃；测速数据只留给内部预取调度用，不上屏。）
        result = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": content,
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": remark or ("%d条线路" % len(play_from)),
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }
        # 副标题
        if sub:
            result["vod_sub"] = sub

        return {"list": [result]}

    # ------------------------------------------------------------------
    # 播放
    # ------------------------------------------------------------------
    def _line_name(self, play_page):
        """从播放页地址推线路名：/userpy/{slug}-{线路序号}-{集数}.html

        线路序号是 1 基的站内编号（7 条线时顺序并不等于界面顺序），
        详情页解析时已把"序号 -> 线路名"存进 _sid_name，这里直接查。
        """
        m = _RE_PLAY_HREF.search(play_page or "")
        if not m:
            return ""
        return self._sid_name.get(m.group(2), "")

    def _prewarm_m3u8(self, m3u8, line=""):
        """后台预热：下钻变体流 + 预建切片映射 + 缓存改写结果 + 记录线路速度

        播放器拿到代理地址后会立刻来取 m3u8。提前算好，首帧就只是一次
        内存读取，而不是"主列表 -> 变体列表"两层串行握手。
        """
        try:
            if not m3u8 or ".m3u8" not in m3u8.lower():
                return
            if m3u8 in self._m3u8_cache:
                return

            ev = threading.Event()
            self._prewarm_evt[m3u8] = ev
            t0 = time.time()
            raw = None
            for _ in range(2):
                try:
                    raw = _seg_fetch(m3u8, timeout=12)
                except Exception:
                    raw = None
                if raw:
                    break
                time.sleep(0.4)
            if not raw:
                return
            txt = raw.decode("utf-8", "ignore")
            real = m3u8
            if "#EXT-X-STREAM-INF" in txt:
                mv = _RE_VARIANT.search(txt)
                if mv:
                    sub = _abs(m3u8, mv.group(1).strip())
                    self._variant_of[m3u8] = sub   # 先登记，让播放器能直接下钻
                    sub_raw = None
                    for _ in range(3):             # 下钻层最容易抽风，多试
                        try:
                            sub_raw = _seg_fetch(sub, timeout=12)
                        except Exception:
                            sub_raw = None
                        if sub_raw:
                            break
                        time.sleep(0.4)
                    if not sub_raw:
                        return
                    txt = sub_raw.decode("utf-8", "ignore")
                    real = sub

            base = self._proxy_base or ""
            out = []
            segs = []
            for raw_line in txt.splitlines():
                t = raw_line.strip()
                if not t:
                    continue
                if t.startswith("#"):
                    out.append(t)
                    continue
                full = _abs(real, t)
                segs.append(full)
                if base:
                    out.append("%s&url=%s" % (base, urllib.parse.quote(full, safe="")))
                else:
                    out.append(full)

            # 建索引：切片名是随机哈希 + sign，只能按真实顺序定位
            if segs:
                head = m3u8
                self._seg_seq[head] = (head, 0, 0, "", None)
                self._playlist[head] = segs
                for _i, _u in enumerate(segs):
                    self._seg_index[_u] = (head, _i)

            body = ("\n".join(out) + "\n").encode("utf-8")
            self._m3u8_cache[m3u8] = (time.time(), body)
            # 变体源文本也缓存：播放器紧接着来要 m3u8 时可直接复用，
            # 省掉"主列表 -> 变体列表"的第二次网络往返（实测省 1~2s）
            if real != m3u8:
                self._m3u8_cache[real + "#SRC"] = (
                    time.time(), txt.encode("utf-8"))
            if len(self._m3u8_cache) > 20:
                for k in sorted(self._m3u8_cache,
                                key=lambda x: self._m3u8_cache[x][0])[:6]:
                    self._m3u8_cache.pop(k, None)

            # 预热只做"解析"，绝不在这里下切片：
            # 播放器几百毫秒内就会来要 m3u8，抢带宽只会让首帧变慢。
            # 线路速度改为播放过程中由填充线程顺手统计（见 _note_speed）。
            self.log("  prewarm 完成 %.2fs 切片%d" % (time.time()-t0, len(segs)))
        except Exception as e:
            self.log("prewarm 失败: %s" % e)
        finally:
            try:
                ev = locals().get("ev")
                if ev is not None:
                    self._prewarm_evt.pop(m3u8, None)
                    ev.set()
            except Exception:
                pass

    def playerContent(self, flag, id, vipFlags):
        play_page = id if str(id).startswith("http") else self._fix_url(id)
        self.log("player: %s" % play_page)

        now = int(time.time())
        if play_page in self._play_cache:
            ts, res = self._play_cache[play_page]
            if now - ts < 600:
                return res

        html = self._fetch(play_page, timeout=25)
        url = self._extract_play_url(html)

        if url:
            # m3u8 走本地代理：切片并发预取，解决单连接限速导致的卡顿
            play_url = url
            if ".m3u8" in url.lower():
                # 记下当前线路名：切片下载时用它统计速度（零额外开销）
                try:
                    self._cur_line = self._line_name(play_page)
                except Exception:
                    self._cur_line = ""
                # 异步预热：下钻变体 + 预建切片映射
                try:
                    threading.Thread(target=self._prewarm_m3u8,
                                     args=(url, self._cur_line),
                                     daemon=True).start()
                except Exception:
                    pass
                try:
                    play_url = (self.getProxyUrl() or "") + "&url=" + \
                        urllib.parse.quote(url, safe="")
                    self.log("  => 走代理加速")
                except Exception:
                    play_url = url

            res = {
                "parse": 0,
                "playUrl": "",
                "url": play_url,
                "header": {
                    "User-Agent": UA,
                    "Referer": self.site_url + "/",
                },
            }
            self._play_cache[play_page] = (now, res)
            self.log("  => 直链: %s" % play_url[:160])
            return res

        # 兜底：交给 TVBox 嗅探/解析
        res = {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": {"User-Agent": UA, "Referer": self.site_url + "/"},
        }
        self._play_cache[play_page] = (now, res)
        self.log("  => 未取到直链，回退解析")
        return res

    def _extract_play_url(self, html):
        if not html:
            return ""
        m = _RE_PLAYER.search(html)
        if not m:
            self.log("  未找到 player_aaaa")
            return ""

        raw = m.group(1)
        try:
            data = json.loads(raw)
        except Exception:
            # 容错：直接抓 url 字段
            mm = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
            if not mm:
                return ""
            val = mm.group(1)
            return _unquote_js(
                val.replace("\\/", "/").replace("\\u0026", "&"))

        val = data.get("url") or ""
        if not val:
            return ""

        val = val.replace("\\/", "/").replace("\\u0026", "&")
        if "%" in val:
            val = _unquote_js(val)
        if val.startswith("//"):
            val = "https:" + val
        if val.startswith("/"):
            val = self.site_url + val
        return val.strip()

    # ------------------------------------------------------------------
    def isVideoFormat(self, url):
        u = (url or "").lower()
        return ".m3u8" in u or ".mp4" in u

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        """本地代理

        两种用途：
          1) m3u8  -> 改写播放列表：切片地址全部指向本代理，
                      并按窗口并发预取，绕开单连接限速（这是卡顿的主因）
          2) ts/图片 -> 直接回源；ts 命中内存缓存则秒出
        """
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url", "")
            else:
                for pair in str(param).split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        if k == "url":
                            url = v
            if not url:
                return [200, "image/jpeg", b"", ""]
            if "%" in url:
                url = _unquote_js(url)
            url = self._fix_url(url)
            base = self._proxy_base or ""

            # ---------- m3u8：改写为代理地址 + 并发预取 ----------
            low = url.lower().split("?")[0]
            orig = url
            if low.endswith(".m3u8"):
                # 改写结果缓存 60s：同一集重开/拖动进度条时直接秒出，
                # 不必再走"主列表 -> 变体列表"两层串行请求
                hit = self._m3u8_cache.get(url)
                if hit and time.time() - hit[0] < 60:
                    self._kick_fill(url)
                    return [200, "application/vnd.apple.mpegurl", hit[1],
                            "Content-Type: application/vnd.apple.mpegurl\r\n"]

                # 预热线程可能正在算同一个列表：等它，别重复请求
                self._await_prewarm(url)

                # ★ 播放器优先（首帧专用）：播放器正在等 m3u8/首片时，
                #   压住预取几秒别跟首帧抢带宽
                _player_first(2.0)

                # 主列表：CDN 抽风就多试几次（_seg_fetch 内部已按 URL 去重，
                # 失败后重新调用会建新的去重槽，等于真重试）
                raw = None
                for _ in range(3):
                    try:
                        raw = _seg_fetch(url, timeout=15)
                    except Exception:
                        raw = None
                    if raw:
                        break
                    time.sleep(0.4)
                if not raw:
                    # 502 让播放器自己重试这一集，比回一个空列表
                    # 让它直接判"播放失败"强得多
                    return [502, "text/plain", b"",
                            "Content-Type: text/plain\r\n"]
                txt = raw.decode("utf-8", "ignore")

                # 变体流：下钻到真正的分片列表（预热已算过就直接用）
                if "#EXT-X-STREAM-INF" in txt:
                    real = self._variant_of.get(url)
                    if not real:
                        mv = _RE_VARIANT.search(txt)
                        if mv:
                            real = _abs(url, mv.group(1).strip())
                    if real:
                        # 变体列表本身也可能已被预热放进缓存，命中则 0 开销
                        sub_url = self._m3u8_cache.get(real + "#SRC")
                        if sub_url:
                            txt = sub_url[1].decode("utf-8", "ignore")
                        else:
                            # 下钻层也要顶住 CDN 抽风：重试 3 次
                            sub_raw = None
                            for _ in range(3):
                                try:
                                    sub_raw = _seg_fetch(real, timeout=15)
                                except Exception:
                                    sub_raw = None
                                if sub_raw:
                                    break
                                time.sleep(0.4)
                            if not sub_raw:
                                return [502, "text/plain", b"",
                                        "Content-Type: text/plain\r\n"]
                            txt = sub_raw.decode("utf-8", "ignore")
                        url = real
                        self._variant_of[orig] = real

                lines = txt.splitlines()
                out = []
                arr = []
                for line in lines:
                    t = line.strip()
                    if not t:
                        continue
                    if t.startswith("#"):
                        out.append(t)
                        continue
                    full = _abs(url, t)
                    arr.append(full)
                    if base:
                        out.append("%s&url=%s" % (
                            base, urllib.parse.quote(full, safe="")))
                    else:
                        out.append(full)

                # ★ 登记"真实播放列表"：该源切片名是随机哈希 + sign 签名，
                #   无法按序号推算，必须直接按住 m3u8 的原始顺序建索引。
                #   这是整条预取链路的地基：_roll_ahead 靠它定位"下一片"。
                if arr:
                    head = url
                    self._seg_seq[head] = (head, 0, 0, "", None)
                    self._playlist[head] = arr
                    for _i, _u in enumerate(arr):
                        self._seg_index[_u] = (head, _i)

                # 起播预取：从第 0 片开始走水位引擎，异步不阻塞
                if base and arr:
                    threading.Thread(target=self._roll_ahead,
                                     args=(arr[0],), daemon=True).start()

                body = ("\n".join(out) + "\n").encode("utf-8")
                self._m3u8_cache[url] = (time.time(), body)
                if len(self._m3u8_cache) > 12:
                    for k in sorted(self._m3u8_cache,
                                    key=lambda x: self._m3u8_cache[x][0])[:4]:
                        self._m3u8_cache.pop(k, None)
                return [200, "application/vnd.apple.mpegurl",
                        body, "Content-Type: application/vnd.apple.mpegurl\r\n"]

            # ---------- 切片 / 图片 ----------
            if ".ts" in low or ".m4s" in low:
                # 命中缓存秒出，这是流畅的关键路径：填充线程已经把片备好了
                hit = _SEG_MEM.get(url)
                if hit and time.time() - hit[0] < 120:
                    self._roll_ahead(url)
                    return [200, "video/mp2t", hit[1], "Content-Type: video/mp2t\r\n"]

                # ★ 播放器优先只作用在首帧（m3u8 阶段）。切片请求**不能**
                #   触发暂停：播放器是顺序拉片的，每片 miss 都暂停的话
                #   填充线程会被永久压住，预取引擎整个失效（实测倒退回
                #   单连接 150KB/s）。带宽协调交给下面的自适应并发档位。
                t0 = time.time()
                data = None
                for _ in range(3):
                    try:
                        data = _seg_fetch(url, timeout=20)
                    except Exception:
                        data = None
                    if data:
                        break
                    time.sleep(0.4)
                if not data:
                    # 两次都失败：给播放器一个明确的 502，让它自己重试这一片，
                    # 比回一坨空数据直接被判"播放失败"强
                    return [502, "video/mp2t", b"",
                            "Content-Type: video/mp2t\r\n"]
                # 顺手记一次真实速度：只记"真正出网"的那次，命中缓存不记
                self._note_speed(getattr(self, "_cur_line", ""),
                                 len(data), time.time() - t0)
                # 缺口补货：告诉填充线程"播放头到这儿了"
                self._roll_ahead(url)
                return [200, "video/mp2t", data, "Content-Type: video/mp2t\r\n"]

            data = _http_get(url, timeout=20)
            return [200, "image/jpeg", data, "Content-Type: image/jpeg\r\n"]
        except Exception as e:
            self.log("proxy ERR %s" % e)
            return [200, "image/jpeg", b"", ""]

    def _kick_fill(self, m3u8):
        """缓存命中时也要把填充线程踢一脚，否则重复打开同一集会不通水"""
        try:
            pl = self._playlist.get(m3u8)
            if pl:
                self._roll_ahead(pl[0])
        except Exception:
            pass

    def _await_prewarm(self, m3u8):
        """若预热线程正在处理同一个 m3u8，就等它算完（最多 8s）

        预热已经发出"主列表 + 变体列表"两次请求，播放器此时若再发一遍，
        就是纯浪费：不仅重复流量，还会让首帧多等一整轮 RTT。
        """
        try:
            ev = self._prewarm_evt.get(m3u8)
            if ev is None:
                return
            ev.wait(8)
        except Exception:
            pass

    def _note_speed(self, key, nbytes, dt):
        """播放过程中顺手统计线路速度，供下次排序用（零额外网络开销）"""
        try:
            if dt <= 0 or nbytes <= 0 or not key:
                return
            sp = (nbytes / 1024.0) / dt
            old = _SPEED_MEM.get(key, 0.0)
            _SPEED_MEM[key] = sp if old <= 0 else (old * 0.7 + sp * 0.3)
        except Exception:
            pass

    def _roll_ahead(self, url):
        """推进播放游标（索引制）

        该源切片名是随机哈希 + sign 签名，**不能按序号推算下一片**，
        所以一切以 m3u8 的真实顺序为准：先建 切片->(列表,下标) 索引，
        再让填充线程沿下标往后取。这是整条加速链能成立的前提。
        """
        try:
            info = self._seg_index.get(url)
            if not info:
                return
            head, idx = info
            playlist = self._playlist.get(head)
            if not playlist:
                return

            st = self._fill_state.get(head)
            if st is None:
                st = {"idx": idx, "lock": threading.Lock(),
                      "wake": threading.Semaphore(0), "started": False,
                      "playlist": playlist}
                self._fill_state[head] = st
            # 游标只前进（拖动进度条回看时也允许后退，但要重排）
            st["idx"] = idx

            if not st["started"]:
                st["started"] = True
                threading.Thread(target=self._fill_worker, args=(st,),
                                 daemon=True).start()
            try:
                st["wake"].release()
            except Exception:
                pass
        except Exception:
            pass

    def _fill_worker(self, st):
        """常驻填充线程：水位控制 + 严格顺序补货

        实测结论（这些数字都来自同一 CDN 的真实测量）：
          - 单连接被限速 ~150KB/s，16 路并发可达 1400~1900KB/s；
          - 但"整窗口无脑预取"反而更卡：并发被摊薄，播放头要的那片
            排在队尾，起播等待从 1.2s 涨到 2.7s+。
          - 因此改为水位制：连续库存 < _LOW_WATER 才出网，一次只补
            _BATCH 片，且严格从缺口处按播放顺序取。播放头永远优先。
        """
        sem = st["wake"]
        pl = st["playlist"]
        total = len(pl)
        idle = 0
        while idle < 180:
            try:
                idx = st["idx"]
                now = time.time()
                # 从游标往后数连续库存（遇到缺口就停，跳着有缓存没意义）
                have = 0
                while have < _WINDOW:
                    j = idx + have
                    if j >= total:
                        break
                    hit = _SEG_MEM.get(pl[j])
                    if not (hit and now - hit[0] < 120):
                        break
                    have += 1

                if have >= _LOW_WATER or idx + have >= total:
                    idle += 1
                    sem.acquire(timeout=2)
                    continue

                # ★ 播放器优先：播放头正在等片（缓存断档）时压住预取，
                #   别跟播放器抢带宽。压住窗口过了就自动恢复。
                if time.time() < _PAUSE_UNTIL[0]:
                    sem.acquire(timeout=0.5)
                    continue

                idle = 0
                start = idx + have
                todo = [pl[k] for k in range(start, min(start + _BATCH, total))]
                if todo:
                    # 并发自适应：限速源（如無水印，单连接 ~150KB/s）开太猛
                    # 只会把家庭宽带打满、播放器反而挤不过去；
                    # 按实测单连接速度降档，快源维持 16 路全速。
                    try:
                        spd = _SPEED_MEM.get(self._cur_line, 0.0)
                    except Exception:
                        spd = 0.0
                    if spd <= 0:
                        workers = max(4, min(_PREFETCH, len(todo) * 2))
                    elif spd < 250:
                        workers = 8
                    elif spd < 600:
                        workers = 12
                    else:
                        workers = _PREFETCH
                    _concurrent_download(todo, workers)
            except Exception:
                idle += 1
                time.sleep(0.2)

    def destroy(self):
        pass

    def close(self):
        self.destroy()
