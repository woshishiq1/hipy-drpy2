<!DOCTYPE html>
<html lang="zh-CN" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>老杨TV - 专属缝合矩阵订阅导航</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
        }
    </script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script async src="//busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js"></script>
</head>
<body class="bg-slate-900 text-slate-200 dark:bg-slate-900 dark:text-slate-200 transition-colors duration-300 min-h-screen flex flex-col items-center justify-between p-4 sm:p-8 font-sans relative overflow-x-hidden" id="main_body">

    <!-- 🌌 1. 科技风渐变光晕与背景网格 -->
    <div class="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div class="absolute -top-40 -left-40 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl"></div>
        <div class="absolute -top-20 -right-20 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl"></div>
        <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-[radial-gradient(#334155_1px,transparent_1px)] [background-size:24px_24px] opacity-20"></div>
    </div>

    <!-- 主卡片容器 -->
    <div class="max-w-3xl w-full bg-slate-800/80 dark:bg-slate-800/80 rounded-3xl p-6 sm:p-8 border border-slate-700/60 shadow-2xl space-y-6 my-auto backdrop-blur-xl relative overflow-hidden transition-all duration-300 z-10" id="main_card">
        
        <!-- 昼夜模式切换按钮 -->
        <button onclick="toggleTheme()" class="absolute top-5 right-5 w-9 h-9 rounded-2xl bg-slate-700/50 hover:bg-slate-600/50 border border-slate-600/50 flex items-center justify-center text-amber-400 transition shadow-inner" title="切换昼夜模式">
            <i class="fa-solid fa-moon text-sm" id="theme_icon"></i>
        </button>

        <!-- Header 品牌标头 -->
        <div class="text-center space-y-2 border-b border-slate-700/60 pb-5">
            <div class="inline-block p-3 bg-slate-700/40 rounded-2xl text-4xl shadow-inner border border-slate-600/40">🦋</div>
            <h1 class="text-2xl sm:text-3xl font-extrabold tracking-wide text-white" id="header_title">老杨TV · 专属矩阵订阅导航</h1>
            <p class="text-xs text-slate-400 font-mono">Core V3.3.1 | Build: 2026-09-01 03:18:06</p>
            
            <div class="flex items-center justify-center gap-2 mt-1">
                <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/60 border border-slate-700/60 text-[11px] text-slate-300">
                    <span class="relative flex h-2 w-2">
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                    </span>
                    <span>边缘节点: <span class="text-emerald-400 font-bold">运行正常</span></span>
                    <span class="text-slate-600">|</span>
                    <span>延迟: <span class="text-emerald-400 font-mono font-bold" id="ping_time">--</span></span>
                </div>
                <button onclick="openChangelogModal()" class="px-3 py-1 rounded-full bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-[11px] text-indigo-300 font-medium transition flex items-center gap-1 shadow-sm">
                    <i class="fa-solid fa-clock-rotate-left"></i>
                    更新日志
                </button>
            </div>
        </div>

        <!-- 1️⃣ 统计与快捷跳转区 -->
        <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2.5 text-center">
            <div class="bg-slate-900/60 p-2.5 rounded-2xl border border-slate-700/50">
                <div class="text-[10px] text-slate-400">点播线路</div>
                <div class="text-base font-bold text-emerald-400 mt-0.5"><span id="count_sites" data-target="553">0</span> <span class="text-[10px] font-normal">个</span></div>
            </div>
            <div class="bg-slate-900/60 p-2.5 rounded-2xl border border-slate-700/50">
                <div class="text-[10px] text-slate-400">直播源站</div>
                <div class="text-base font-bold text-cyan-400 mt-0.5"><span id="count_lives" data-target="58">0</span> <span class="text-[10px] font-normal">个</span></div>
            </div>
            <div class="bg-slate-900/60 p-2.5 rounded-2xl border border-slate-700/50">
                <div class="text-[10px] text-slate-400">解析接口</div>
                <div class="text-base font-bold text-indigo-400 mt-0.5"><span id="count_parses" data-target="27">0</span> <span class="text-[10px] font-normal">个</span></div>
            </div>
            <div class="bg-slate-900/60 p-2.5 rounded-2xl border border-slate-700/50">
                <div class="text-[10px] text-slate-400">当前密锁</div>
                <div class="text-xs font-bold text-amber-400 cursor-pointer select-none transition mt-1"
                     onclick="alert('⚠️ 请前往 Telegram 频道获取。');"
                     title="点击显示/隐藏">
                    🔒 加群获取
                </div>
            </div>
            <div class="bg-slate-900/60 p-2.5 rounded-2xl border border-slate-700/50">
                <div class="text-[10px] text-slate-400">访问总人次</div>
                <div class="text-base font-bold text-rose-400 mt-0.5">
                    <span id="busuanzi_value_site_pv">--</span> <span class="text-[10px] font-normal">次</span>
                </div>
            </div>
            <a href="https://t.me/tvshare23" target="_blank" class="bg-slate-900/60 hover:bg-sky-500/20 p-2.5 rounded-2xl border border-slate-700/50 hover:border-sky-500/40 transition group">
                <div class="text-[10px] text-slate-400 group-hover:text-sky-300">TG 交流群</div>
                <div class="text-xs font-bold text-sky-400 mt-1 truncate"><i class="fa-brands fa-telegram"></i> 群组</div>
            </a>
            <a href="https://t.me/huliys9" target="_blank" class="bg-slate-900/60 hover:bg-sky-500/20 p-2.5 rounded-2xl border border-slate-700/50 hover:border-sky-500/40 transition group">
                <div class="text-[10px] text-slate-400 group-hover:text-sky-300">TG 官方频道</div>
                <div class="text-xs font-bold text-sky-400 mt-1 truncate"><i class="fa-brands fa-telegram"></i> 频道</div>
            </a>
        </div>

        <!-- 跑马灯流动公告栏 -->
        <div class="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-2.5 px-4 flex items-center gap-3 overflow-hidden text-xs text-emerald-300">
            <i class="fa-solid fa-bullhorn text-emerald-400 animate-bounce"></i>
            <div class="overflow-hidden whitespace-nowrap w-full">
                <div class="inline-block animate-[marquee_20s_linear_infinite] hover:[animation-play-state:paused]">
                    📢 声明：本接口仅供技术交流与个人测试使用，数据均来自互联网公共公开源，请于下载后24小时内删除。严禁用于任何商业牟利行为！
                </div>
            </div>
        </div>

        <!-- 📱 适配客户端推荐与下载 (由 settings.json 读取展示) -->
        <div id="software_download_container" class="space-y-3"></div>

        <!-- 2️⃣ 订阅链接列表 -->
        <div class="space-y-3">
            <h2 class="text-sm font-bold text-slate-200 flex items-center gap-2">
                <i class="fa-solid fa-rss text-emerald-400"></i>
                最新可用矩阵订阅链接
            </h2>
            <div class="space-y-3">

                <div class="bg-slate-900/80 rounded-xl p-4 border border-slate-700/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div class="space-y-1 overflow-hidden">
                        <div class="flex items-center gap-2">
                            <span class="font-bold text-white text-sm">老杨TV纯净版</span>
                            <span class="text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 rounded-full font-medium">🏡 客厅纯净</span>
                        </div>
                        <p class="text-xs font-mono text-slate-400 truncate select-all">••••••••••••••••••••••••</p>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        <a href="javascript:openTgBotModal()"  class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium border border-slate-600/60 transition">预览</a>
                        <button onclick="openTgBotModal()" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-emerald-600/20 transition flex items-center gap-1"><i class="fa-regular fa-copy"></i>复制链接</button>
                    </div>
                </div>
                
                <div class="bg-slate-900/80 rounded-xl p-4 border border-slate-700/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div class="space-y-1 overflow-hidden">
                        <div class="flex items-center gap-2">
                            <span class="font-bold text-white text-sm">老杨TV全量版</span>
                            <span class="text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/30 px-2 py-0.5 rounded-full font-medium">🔞 全量推荐</span>
                        </div>
                        <p class="text-xs font-mono text-slate-400 truncate select-all">🔒 私人专属接口（需要前往 Telegram 机器人免费领取）</p>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        <a href="javascript:openTgBotModal()"  class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium border border-slate-600/60 transition">预览</a>
                        <button onclick="openTgBotModal()" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-emerald-600/20 transition flex items-center gap-1"><i class="fa-regular fa-copy"></i>复制链接</button>
                    </div>
                </div>
                
            </div>
        </div>

        <!-- 3️⃣ 打赏支持区域 -->
        
        <div class="bg-slate-900/60 border border-slate-700/60 rounded-xl p-4 text-center space-y-3">
            <p class="text-xs text-slate-300">☕ 如果觉得本专线对你有帮助，欢迎请作者喝杯咖啡支持服务器与域名续费～</p>
            <button onclick="toggleDonate()" class="px-4 py-2 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 rounded-xl text-xs font-bold transition inline-flex items-center gap-1.5 shadow-lg"><i class="fa-solid fa-heart text-rose-500"></i>赞赏支持作者</button>
            <div id="donate_qr_box" class="hidden pt-2 flex flex-col items-center justify-center">
                <img src="https://img.naixiai.cn/2026/07/31/IMG_7036.jpeg" alt="赞赏码" class="w-48 h-48 rounded-xl border-2 border-rose-500/40 shadow-2xl object-cover">
            </div>
        </div>
        

        <!-- 4️⃣ 公告引导区 -->
        <div class="bg-amber-500/10 border border-amber-500/20 rounded-2xl p-4 text-xs space-y-1.5 text-amber-200/90">
            <div class="font-bold text-amber-400 flex items-center gap-1.5">
                <i class="fa-solid fa-triangle-exclamation"></i>
                重要提示与使用说明
            </div>
            <p class="leading-relaxed">
                1. 本专线订阅密码不定期全自动跟进交替。若遇到电视端视频无法加载或断流，请及时更换最新的订阅链接！<br>
                2. 官方交流渠道（加群获取最新密锁/更新通知）：<br>
                   • Telegram 交流群：<a href="https://t.me/tvshare23" target="_blank" class="font-bold text-sky-400 hover:text-sky-300 underline underline-offset-2 transition"><i class="fa-brands fa-telegram"></i> tvshare23</a><br>
                   • Telegram 官方频道：<a href="https://t.me/huliys9" target="_blank" class="font-bold text-sky-400 hover:text-sky-300 underline underline-offset-2 transition"><i class="fa-brands fa-telegram"></i> @huliys9</a>
            </p>
        </div>

    </div>

    <!-- 页脚版权 -->
    <footer class="text-center text-[11px] text-slate-500 py-4 z-10">
        © 2026 老杨TV 版权所有 | 本站仅供交流学习使用！
    </footer>

    <style>
        @keyframes marquee {
            0% { transform: translateX(100%); }
            100% { transform: translateX(-100%); }
        }
    </style>

    <script>
    document.addEventListener('DOMContentLoaded', () => {
        // 🛡️ 扫描 DOM：捕获明文 URL 并用 11 道题的答案分别加密，生成 11 个密文组成的数组存入内存，彻底抹去 HTML 明文
        document.querySelectorAll('[onclick*="openVerifyModal"], [href*="openVerifyModal"]').forEach(el => {
            ['onclick', 'href'].forEach(attr => {
                const val = el.getAttribute(attr);
                if (!val || !val.includes('openVerifyModal')) return;

                const match = val.match(/openVerifyModal\s*\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]\s*\)/);
                if (match && match[1] && (match[1].startsWith('http://') || match[1].startsWith('https://'))) {
                    const rawUrl = match[1];
                    const actionType = match[2];

                    // 💡 动态根据最新的 MATH_DB_ANSWERS 数组生成全部密文阵列
                    const cipherArray = MATH_DB_ANSWERS.map(ansKey => encryptWithKey(rawUrl, ansKey));
                    el.dataset.ciphers = JSON.stringify(cipherArray);
                    el.dataset.actionType = actionType;

                    // 替换 HTML 上的明文，只留触发器
                    if (attr === 'onclick') {
                        el.setAttribute('onclick', `triggerRandomVerify(this)`);
                    } else if (attr === 'href') {
                        el.setAttribute('href', `javascript:void(0)`);
                        el.addEventListener('click', function() { triggerRandomVerify(this); });
                    }
                }
            });
        });

        const start = performance.now();
        fetch(window.location.href, { method: 'HEAD', cache: 'no-store' }).then(() => {
            const duration = Math.round(performance.now() - start);
            const pingEl = document.getElementById('ping_time');
            if (pingEl) pingEl.innerText = duration + 'ms';
        }).catch(() => {
            const pingEl = document.getElementById('ping_time');
            if (pingEl) pingEl.innerText = '15ms';
        });

        animateCount('count_sites');
        animateCount('count_lives');
        animateCount('count_parses');
        loadSoftwareSection();

        if (localStorage.getItem('theme') === 'light') {
            setTheme('light');
        }
    });

    function loadSoftwareSection() {
        // 增加相对路径兜底，解决 Cloudflare Pages 静态节点 404 导致隐藏容器的问题
        fetch('./settings.json?t=' + Date.now())
            .then(res => {
                if (!res.ok) return fetch('/settings.json?t=' + Date.now()).then(r => r.json());
                return res.json();
            })
            .then(cfg => {
                const container = document.getElementById('software_download_container');
                if (!container) return;

                const title = cfg.SOFTWARE_SECTION_TITLE || '💻 适配客户端推荐与下载';
                const msg = cfg.SOFTWARE_CUSTOM_MESSAGE || '';
                const list = cfg.SOFTWARE_DOWNLOAD_LIST || [];

                if (!msg && list.length === 0) return;

                let formattedMsg = (msg || '').split('\\n').join('<br>').split('\n').join('<br>');
                let msgHtml = msg ? `<p class="text-xs text-sky-300 bg-sky-500/10 border border-sky-500/20 rounded-xl p-3 leading-relaxed whitespace-pre-wrap">${formattedMsg}</p>` : '';
                
                let listHtml = '';
                list.forEach(item => {
                    const iconValue = item.icon || 'fa-download';
                    const isImageUrl = iconValue.startsWith('http://') || iconValue.startsWith('https://');
                    
                    const iconHtml = isImageUrl 
                        ? `<img src="${iconValue}" class="w-5 h-5 object-contain rounded-md" alt="icon">`
                        : `<i class="fa-solid ${iconValue} text-sm"></i>`;

                    listHtml += `
                    <div class="bg-slate-900/80 rounded-xl p-3 border border-slate-700/70 flex items-center justify-between gap-3">
                        <div class="flex items-center gap-3 overflow-hidden">
                            <div class="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 flex-shrink-0">
                                ${iconHtml}
                            </div>
                            <div class="truncate">
                                <div class="font-bold text-white text-xs truncate">${item.name || ''}</div>
                                <div class="text-[10px] text-slate-400 truncate">${item.desc || ''}</div>
                            </div>
                        </div>
                        <a href="${item.url || '#'}" target="_blank" class="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-bold shadow-md shadow-sky-600/20 transition flex-shrink-0 flex items-center gap-1">
                            <i class="fa-solid fa-download text-[10px]"></i>下载
                        </a>
                    </div>
                    `;
                });

                container.innerHTML = `
                    <h2 class="text-sm font-bold text-slate-200 flex items-center gap-2">
                        <i class="fa-solid fa-laptop-code text-sky-400"></i>
                        ${title}
                    </h2>
                    ${msgHtml}
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                        ${listHtml}
                    </div>
                `;
            }).catch(e => console.log('未读取到自定义软件配置'));
    }

    function animateCount(id) {
        const el = document.getElementById(id);
        if (!el) return;
        const target = parseInt(el.getAttribute('data-target')) || 0;
        let current = 0;
        const duration = 1000;
        const stepTime = 20;
        const increment = Math.ceil(target / (duration / stepTime)) || 1;

        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                current = target;
                clearInterval(timer);
            }
            el.innerText = current;
        }, stepTime);
    }

    function toggleTheme() {
        const isDark = document.documentElement.classList.contains('dark');
        setTheme(isDark ? 'light' : 'dark');
    }

    function setTheme(mode) {
        const body = document.getElementById('main_body');
        const card = document.getElementById('main_card');
        const icon = document.getElementById('theme_icon');
        const title = document.getElementById('header_title');

        if (mode === 'light') {
            document.documentElement.classList.remove('dark');
            body.className = "bg-slate-100 text-slate-800 min-h-screen flex flex-col items-center justify-between p-4 sm:p-8 font-sans transition-colors duration-300 relative overflow-x-hidden";
            card.className = "max-w-3xl w-full bg-white/80 rounded-3xl p-6 sm:p-8 border border-slate-200 shadow-xl space-y-6 my-auto backdrop-blur-xl relative overflow-hidden transition-all duration-300 z-10";
            icon.className = "fa-solid fa-sun text-sm text-amber-500";
            if (title) title.className = "text-2xl sm:text-3xl font-extrabold tracking-wide text-slate-800";
            localStorage.setItem('theme', 'light');
        } else {
            document.documentElement.classList.add('dark');
            body.className = "bg-slate-900 text-slate-200 min-h-screen flex flex-col items-center justify-between p-4 sm:p-8 font-sans transition-colors duration-300 relative overflow-x-hidden";
            card.className = "max-w-3xl w-full bg-slate-800/80 rounded-3xl p-6 sm:p-8 border border-slate-700/60 shadow-2xl space-y-6 my-auto backdrop-blur-xl relative overflow-hidden transition-all duration-300 z-10";
            icon.className = "fa-solid fa-moon text-sm text-amber-400";
            if (title) title.className = "text-2xl sm:text-3xl font-extrabold tracking-wide text-white";
            localStorage.setItem('theme', 'dark');
        }
    }

    function toggleDonate() {
        const box = document.getElementById('donate_qr_box');
        if (box) box.classList.toggle('hidden');
    }

    function copyUrl(url, isMasked) {
        if (isMasked) {
            alert('⚠️ 当前公开页已开启隐秘保护模式！\n\n请前往 Telegram 交流群或频道获取当前最新密锁订阅链接。');
            return;
        }
        navigator.clipboard.writeText(url).then(() => {
            alert('✨ 订阅链接已成功复制到剪贴板！');
        }).catch(() => {
            const input = document.createElement('input');
            input.value = url;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            alert('✨ 订阅链接已成功复制！');
        });
    }
    </script>

    <!-- 更新日志弹窗 (Changelog Modal) -->
    <div id="changelogModal" class="hidden fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4">
        <div class="bg-slate-800 rounded-3xl border border-slate-700 max-w-lg w-full p-6 shadow-2xl space-y-4 max-h-[80vh] flex flex-col">
            <div class="flex justify-between items-center border-b border-slate-700 pb-3 flex-shrink-0">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-list-check text-emerald-400"></i>
                    矩阵更新与线路变动日志
                </h3>
                <button onclick="closeChangelogModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
            </div>
            
            <div id="changelogContent" class="space-y-4 overflow-y-auto text-xs text-slate-300 pr-1">
                <div class="text-center py-6 text-slate-500"><i class="fa-solid fa-spinner fa-spin"></i> 正在加载最新变动明细...</div>
            </div>

            <div class="pt-2 border-t border-slate-700/60 flex justify-end flex-shrink-0">
                <button onclick="closeChangelogModal()" class="px-4 py-1.5 bg-slate-700 hover:bg-slate-600 text-xs font-medium rounded-xl text-slate-200">关闭</button>
            </div>
        </div>
    </div>
    
    <!-- 🤖 引导前往 Telegram 机器人获取专属订阅弹窗 -->
    <div id="tgBotModal" class="hidden fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4">
        <div class="bg-slate-800 rounded-3xl border border-slate-700 max-w-md w-full p-6 shadow-2xl space-y-5 relative">
            <div class="flex justify-between items-center border-b border-slate-700 pb-3">
                <h3 class="text-sm font-bold text-white flex items-center gap-2">
                    <i class="fa-solid fa-shield-halved text-emerald-400"></i> 全量专属接口领卡引导
                </h3>
                <button onclick="closeTgBotModal()" class="text-slate-400 hover:text-white cursor-pointer"><i class="fa-solid fa-xmark"></i></button>
            </div>
            
            <div class="space-y-3 text-xs leading-relaxed text-slate-300">
                <div class="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-4 space-y-2">
                    <div class="font-bold text-emerald-400 flex items-center gap-2 text-sm">
                        <i class="fa-brands fa-telegram text-base"></i>
                        领取私人专属全量接口
                    </div>
                    <p class="text-slate-300 text-[11px]">
                        为了保障全量版线路稳定性并防止接口被恶意抓取盗用，全量版已全面升级为<b>一人一码私人专属订阅模式</b>。
                    </p>
                </div>

                <div class="bg-slate-900/80 border border-slate-700/70 rounded-2xl p-3.5 space-y-1.5">
                    <div class="font-bold text-amber-400 text-[11px] flex items-center gap-1.5">
                        <i class="fa-solid fa-lightbulb"></i> 如何免费获取？
                    </div>
                    <p class="text-slate-400 text-[11px]">
                        点击下方按钮跳转至 Telegram 官方机器人，向机器人发送命令 <code class="bg-slate-800 text-sky-300 px-1.5 py-0.5 rounded font-mono font-bold">订阅</code>，即可秒下发您的专属全量接口！
                    </p>
                </div>
            </div>

            <div class="flex gap-2 pt-1">
                <button onclick="closeTgBotModal()" class="flex-1 py-2.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-xl text-xs font-bold transition">取消</button>
                <a href="https://t.me/laowang_tv_push_bot" target="_blank" onclick="closeTgBotModal()" class="flex-[2] py-2.5 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-sky-600/20 transition flex items-center justify-center gap-2">
                    <i class="fa-brands fa-telegram text-sm"></i> 打开机器人免费领取
                </a>
            </div>
        </div>
    </div>
    <script>
    let pendingCipher = "";
    let verifyActionType = "copy";
    let currentMathQuestion = null;

    // 🔒 内部算法 Keys：从 settings.json 动态注入
    const MATH_DB_ANSWERS = ["TRUE", "[PLUGIN]", "302", "HTTPS", "X25519", "QUIC", "FAKE-IP", "UTLS", "PREFER-IPV6", "AEAD", "#genre#", "proxy://", "default", "script=", "isVideoFormat"];

    // 🔒 联合题库：从 settings.json 动态注入
    const ALL_MATH_DB = [{"id": 0, "num_str": "01", "cmd": "q1", "q": "Surge 想要对特定 HTTP/2 协议流量强行开启 MITM 解密，需在 [MITM] 下配置 h2 = ____？"}, {"id": 1, "num_str": "02", "cmd": "q2", "q": "Loon 模块化扩展文件(.plugin)中，定义脚本与重写的主标签名称叫什么____？"}, {"id": 2, "num_str": "03", "cmd": "q3", "q": "Shadowrocket 的 URL Rewrite 规则中，用于临时重定向的 HTTP 状态码关键字是____？"}, {"id": 3, "num_str": "04", "cmd": "q4", "q": "Sing-box 中专门用于规避 TLS 握手 SNI 明文特征并依赖 ECH 加密的 DNS 记录类型是____？"}, {"id": 4, "num_str": "05", "cmd": "q5", "q": "Xray 的 VLESS 协议在结合 Reality 传输层时，用作客户端鉴权的椭圆曲线密钥对算法是____？"}, {"id": 5, "num_str": "06", "cmd": "q6", "q": "Tuic v5 协议为了在 UDP 丢包环境下实现快速重传并降低延迟，其底层依托的传输层协议是____？"}, {"id": 6, "num_str": "07", "cmd": "q7", "q": "Clash Meta (mihomo) 想要对本地 DoH 请求防止被 GFW 污染，需开启的 DNS 核心模式是____？"}, {"id": 7, "num_str": "08", "cmd": "q8", "q": "V2Ray 中用于伪装成正常 TLS 流量并动态修改 Client Hello 随机数与指纹的模块是____？"}, {"id": 8, "num_str": "09", "cmd": "q9", "q": "Shadowrocket / Surge 中用于强行阻断并直接拒绝 IPv6 优先解析以防止地址泄漏的设置项是____？"}, {"id": 9, "num_str": "10", "cmd": "q10", "q": "Shadowsocks 2022 协议族为了彻底解决旧版首包重放攻击，在 Header 中强制加入的校验机制是____？"}, {"id": 10, "num_str": "11", "cmd": "q11", "q": "在 M3U 或 TXT 直播源中，用于声明某个分组为“密码保护的隐藏分组”的行后缀标志是____？"}, {"id": 11, "num_str": "12", "cmd": "q12", "q": "Spider 爬虫返回媒体 URL 时，若需交由本身的 proxy() 方法接管二次转发，URL 前缀需使用____协议？"}, {"id": 12, "num_str": "13", "cmd": "q13", "q": "Catchup 追看配置中，若要将计算后的时间参数直接“完全替换”原始播放 URL，type 字段应填____？"}, {"id": 13, "num_str": "14", "cmd": "q14", "q": "M3U 格式中，用于指定解析器 WebView 额外执行 JS 自动点击或去广告的指令行是____？"}, {"id": 14, "num_str": "15", "cmd": "q15", "q": "Spider 类的子类中，用于在 WebView 拦截 URL 后进行人工二次校验“是否为有效媒体 URL”的方法名是____？"}];

    // 🎲 每次点击按钮：从 ALL_MATH_DB 动态题库中随机抽题，渲染弹窗
    function triggerRandomVerify(el) {
        const ciphersJson = el.dataset.ciphers;
        const actionType = el.dataset.actionType || 'copy';

        if (!ciphersJson) return;
        const ciphers = JSON.parse(ciphersJson);

        // 💡 根据当前实际题库 ALL_MATH_DB 的总长度随机抽题
        const randIdx = Math.floor(Math.random() * ALL_MATH_DB.length);
        currentMathQuestion = ALL_MATH_DB[randIdx];

        // 提取该题目对应的密文
        pendingCipher = ciphers[randIdx];
        verifyActionType = actionType;

        // 💡 动态更新提示框中的题号与机器人口令
        const noticeTitleEl = document.getElementById('modalNoticeTitle');
        const noticeDescEl = document.getElementById('modalNoticeDesc');
        if (noticeTitleEl) {
            noticeTitleEl.innerHTML = `当前抽取：<span class="text-amber-300 font-bold">第 ${currentMathQuestion.num_str} 题</span>`;
        }
        if (noticeDescEl) {
            noticeDescEl.innerHTML = `前往 TG 群组发送口令 <button onclick="copyCmd('${currentMathQuestion.cmd}')" class="px-1.5 py-0.5 bg-sky-500/20 hover:bg-sky-500/40 text-amber-300 border border-amber-400/40 rounded font-mono font-bold cursor-pointer transition inline-flex items-center gap-1" title="点击复制口令">${currentMathQuestion.cmd} <i class="fa-regular fa-copy text-[10px]"></i></button> 即可自动获取对应答案。`;
        }

        document.getElementById('verifyAnswerInput').value = '';
        document.getElementById('verifyModal').classList.remove('hidden');

        // 渲染题目到 Canvas 图像画布
        renderMathCanvas(currentMathQuestion.q);
    }

    // 📋 点击按钮一键复制口令函数
    function copyCmd(cmdText) {
        navigator.clipboard.writeText(cmdText).then(() => {
            alert(`✨ 口令 ${cmdText} 已复制！可直接前往 Telegram 群组发送。`);
        }).catch(() => {
            const input = document.createElement('input');
            input.value = cmdText;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            alert(`✨ 口令 ${cmdText} 已复制！`);
        });
    }

    function closeVerifyModal() {
        document.getElementById('verifyModal').classList.add('hidden');
    }

    function renderMathCanvas(text) {
        const canvas = document.getElementById('mathCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#0f172a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.strokeStyle = 'rgba(59, 130, 246, 0.15)';
        ctx.lineWidth = 1;
        for (let i = 0; i < 5; i++) {
            ctx.beginPath();
            ctx.moveTo(Math.random() * canvas.width, Math.random() * canvas.height);
            ctx.lineTo(Math.random() * canvas.width, Math.random() * canvas.height);
            ctx.stroke();
        }

        const fontSize = text.length > 22 ? 12 : 13;
        ctx.font = 'bold ' + fontSize + 'px monospace';
        ctx.fillStyle = '#38bdf8';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        const maxWidth = canvas.width - 24; 
        const chars = text.split('');
        let currentLine = '';
        const lines = [];

        for (let i = 0; i < chars.length; i++) {
            const testLine = currentLine + chars[i];
            const metrics = ctx.measureText(testLine);
            if (metrics.width > maxWidth && i > 0) {
                lines.push(currentLine);
                currentLine = chars[i];
            } else {
                currentLine = testLine;
            }
        }
        lines.push(currentLine);

        const lineHeight = fontSize + 6;
        const startY = (canvas.height / 2) - ((lines.length - 1) * lineHeight / 2);
        
        lines.forEach((l, index) => {
            ctx.fillText(l, canvas.width / 2, startY + (index * lineHeight));
        });
    }

    // 🔒 异或加密
    function encryptWithKey(rawUrl, keyStr) {
        try {
            const keyBytes = new TextEncoder().encode(keyStr.trim().toUpperCase());
            const rawBytes = new TextEncoder().encode(rawUrl);
            const cipherBytes = new Uint8Array(rawBytes.length);
            for (let i = 0; i < rawBytes.length; i++) {
                cipherBytes[i] = rawBytes[i] ^ keyBytes[i % keyBytes.length];
            }
            return btoa(String.fromCharCode(...cipherBytes));
        } catch(e) {
            return "";
        }
    }

    // 🔑 异或解密
    function decryptUrl(cipherBase64, keyStr) {
        try {
            const keyBytes = new TextEncoder().encode(keyStr.trim().toUpperCase());
            const cipherBytes = Uint8Array.from(atob(cipherBase64), c => c.charCodeAt(0));
            const plainBytes = new Uint8Array(cipherBytes.length);
            for (let i = 0; i < cipherBytes.length; i++) {
                plainBytes[i] = cipherBytes[i] ^ keyBytes[i % keyBytes.length];
            }
            return new TextDecoder().decode(plainBytes);
        } catch(e) {
            return "";
        }
    }

    function checkVerifyAnswer() {
        const userAns = document.getElementById('verifyAnswerInput').value.trim();
        if (!userAns) {
            alert("请输入计算结果或答案！");
            return;
        }

        // 用户输入的答案即解密密钥
        const decryptedUrl = decryptUrl(pendingCipher, userAns);

        if (decryptedUrl && (decryptedUrl.startsWith('http://') || decryptedUrl.startsWith('https://'))) {
            closeVerifyModal();
            if (verifyActionType === 'preview') {
                window.open(decryptedUrl, '_blank');
            } else {
                navigator.clipboard.writeText(decryptedUrl).then(() => {
                    alert("✨ 身份验证通过！解密成功，全量版链接已复制到剪贴板！");
                });
            }
        } else {
            alert("❌ 验证失败：答案错误！非资深粉丝禁止获取。");
            document.getElementById('verifyAnswerInput').value = '';
        }
    }

    document.addEventListener('visibilitychange', () => {
        const overlay = document.getElementById('canvasOverlay');
        if (overlay) overlay.style.display = document.hidden ? 'flex' : 'none';
    });

    function openChangelogModal() {
        document.getElementById('changelogModal').classList.remove('hidden');
        loadChangelogData();
    }

    function closeChangelogModal() {
        document.getElementById('changelogModal').classList.add('hidden');
    }

    function loadChangelogData() {
        const container = document.getElementById('changelogContent');
        fetch('./changelog.json?t=' + Date.now())
            .then(res => {
                if (!res.ok) return fetch('/changelog.json?t=' + Date.now()).then(r => r.json());
                return res.json();
            })
            .then(data => {
                if (!data || data.length === 0) {
                    container.innerHTML = '<div class="text-center text-slate-500 py-4">暂无历史变动记录</div>';
                    return;
                }
                let html = '';
                data.forEach(item => {
                    html += `
                    <div class="bg-slate-900/60 p-3.5 rounded-2xl border border-slate-700/60 space-y-2">
                        <div class="flex justify-between items-center border-b border-slate-800 pb-2">
                            <span class="font-bold text-emerald-400">📅 ${item.time}</span>
                            <span class="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-mono">${item.token || item.version || '编译构建'}</span>
                        </div>
                        <div class="space-y-1 text-slate-300 whitespace-pre-wrap leading-relaxed">${item.detail}</div>
                    </div>
                    `;
                });
                container.innerHTML = html;
            })
            .catch(() => {
                container.innerHTML = '<div class="text-center text-amber-400 py-4">无法获取变动明细记录</div>';
            });
    }
    // 🤖 控制 TG 机器人引导弹窗的显隐
    function openTgBotModal() {
        document.getElementById('tgBotModal').classList.remove('hidden');
    }

    function closeTgBotModal() {
        document.getElementById('tgBotModal').classList.add('hidden');
    }
    </script>
</body>
</html>
