<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>恒岳量化数据表 · 视觉增强版</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Noto+Sans+SC:wght@400;700;900&display=swap');
        * { font-family: 'Inter', 'Noto Sans SC', sans-serif; transition: background 0.3s, border-color 0.3s; }
        
        :root {
            --bg-body: #020617; --bg-nav: rgba(15, 23, 42, 0.9); --text-main: #f8fafc;
            --card-bg: rgba(30, 41, 59, 0.5); --card-border: rgba(255, 255, 255, 0.1);
            --accent: #10b981;
        }

        .theme-emerald { --bg-body: #022c22; --bg-nav: rgba(6, 78, 59, 0.9); --accent: #34d399; }
        .theme-ocean { --bg-body: #0c4a6e; --bg-nav: rgba(12, 74, 110, 0.9); --accent: #38bdf8; }
        .theme-purple { --bg-body: #2e1065; --bg-nav: rgba(76, 29, 149, 0.9); --accent: #a78bfa; }
        .theme-sunset { --bg-body: #451a03; --bg-nav: rgba(124, 45, 18, 0.9); --accent: #fb923c; }
        .theme-light { --bg-body: #f8fafc; --bg-nav: rgba(255, 255, 255, 0.9); --text-main: #0f172a; --card-bg: #ffffff; --card-border: #e2e8f0; --accent: #059669; }
        .theme-gold { --bg-body: #1c1917; --bg-nav: rgba(41, 37, 36, 0.9); --accent: #fbbf24; }

        body { background-color: var(--bg-body); color: var(--text-main); }
        .glass-card { background: var(--card-bg); border: 1px solid var(--card-border); backdrop-filter: blur(12px); border-radius: 1.5rem; }

        .sticky-t1 { position: sticky; top: 64px; z-index: 50; background: var(--bg-nav); }
        .sticky-t2 { position: sticky; top: 124px; z-index: 49; background: var(--bg-nav); border-bottom: 2px solid var(--card-border); }
        .sticky-col { position: sticky; left: 0; z-index: 40; background: var(--bg-body) !important; border-right: 2px solid var(--card-border); }

        /* 姓名及指标颜色定义 */
        .name-qiao { color: #3b82f6; } /* 蓝色 */
        .name-zeng { color: #10b981; } /* 绿色 */
        .name-yang { color: #fb7185; } /* 粉红色 */

        .metric-col-0 { color: #3b82f6; } .metric-col-1 { color: #8b5cf6; } 
        .metric-col-2 { color: #eab308; } .metric-col-3 { color: #f97316; }
        .metric-col-4 { color: #ec4899; } .metric-col-5 { color: #22c55e; }

        .editable-cell {
            min-width: 50px; padding: 6px; text-align: center; border-radius: 6px;
            font-size: 1rem; font-weight: 800; background: rgba(255,255,255,0.03);
        }
        .editable-cell:focus { outline: 2px solid var(--accent); background: #fff; color: #000 !important; }
        .total-row { background: rgba(16, 185, 129, 0.1); font-weight: 900; border-top: 2px solid var(--accent); }
    </style>
</head>
<body class="min-h-screen">

    <nav class="sticky top-0 z-[100] border-b px-6 py-2 flex items-center justify-between" style="background: var(--bg-nav); border-color: var(--card-border);">
        <div class="flex items-center gap-4">
            <div class="w-9 h-9 bg-emerald-500 rounded-xl flex items-center justify-center text-white font-black text-lg">恒</div>
            <h1 class="text-lg font-black italic tracking-tighter">恒岳轨道交通· 4月数据汇总</h1>
        </div>
        <div class="flex items-center gap-2">
            <select onchange="changeTheme(this.value)" class="bg-slate-800 text-[10px] font-bold border border-slate-700 rounded-lg px-2 py-1.5 outline-none">
                <option value="">🌌 深邃暗影</option>
                <option value="theme-emerald">🌲 翡翠深林</option>
                <option value="theme-ocean">🌊 浩瀚星海</option>
                <option value="theme-purple">🔮 极光幻紫</option>
                <option value="theme-sunset">🌇 落日熔金</option>
                <option value="theme-gold">🪙 奢华暗金</option>
                <option value="theme-light"☀️ 极简日光</option>
            </select>
            <button onclick="saveData()" class="bg-emerald-600 hover:bg-emerald-500 px-4 py-1.5 rounded-lg text-[10px] font-black text-white">同步云端</button>
        </div>
    </nav>

    <main class="max-w-[1600px] mx-auto px-6 py-6">
        <div id="charts-container" class="grid grid-cols-1 gap-6 mb-10"></div>

        <div class="glass-card overflow-hidden">
            <div class="overflow-auto max-h-[600px]">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="sticky-t1">
                            <th class="p-3 sticky-col text-center w-24">日期</th>
                            <th colspan="6" class="p-3 text-center border-x border-white/5 text-blue-400 font-black text-lg italic">乔少龙</th>
                            <th colspan="6" class="p-3 text-center border-x border-white/5 text-emerald-400 font-black text-lg italic">曾士平</th>
                            <th colspan="6" class="p-3 text-center text-rose-400 font-black text-lg italic">杨雨萌</th>
                        </tr>
                        <tr class="sticky-t2 text-[12px] font-black uppercase tracking-wider text-center">
                            <th class="sticky-col"></th>
                            <script>
                                const titles = ['新招呼','邀约','面试','发通过函','发人','留人'];
                                for(let i=0; i<3; i++) titles.forEach((t, idx) => 
                                    document.write(`<th class="p-2 border-r border-white/5 metric-col-${idx}">${t}</th>`)
                                );
                            </script>
                        </tr>
                    </thead>
                    <tbody id="table-body"></tbody>
                    <tfoot id="table-footer"></tfoot>
                </table>
            </div>
        </div>
    </main>

    <script>
        const API_URL = 'https://997.jingtie.tk/api/data';
        let dailyData = {};
        const persons = ['qiao', 'zeng', 'yang'];
        const personNames = ['乔少龙', '曾士平', '杨雨萌'];
        const metricColors = ['#3b82f6', '#8b5cf6', '#eab308', '#f97316', '#ec4899', '#22c55e'];

        Chart.register(ChartDataLabels);

        function changeTheme(cls) {
            document.body.className = 'min-h-screen ' + cls;
            renderDashboards();
        }

        async function initData() {
            try {
                const res = await fetch(API_URL);
                dailyData = res.ok ? await res.json() : generateEmpty();
            } catch (e) { dailyData = generateEmpty(); }
            renderTable();
            renderDashboards();
        }

        function generateEmpty() {
            let d = {}; for(let i=1;i<=30;i++) d[i] = {qiao:Array(6).fill(0), zeng:Array(6).fill(0), yang:Array(6).fill(0)};
            return d;
        }

        function handleInput(cell) {
            const {day, person, metric} = cell.dataset;
            dailyData[day][person][metric] = parseInt(cell.innerText) || 0;
            renderFooter();
            clearTimeout(window.t); window.t = setTimeout(saveData, 2000);
        }

        async function saveData() {
            await fetch(API_URL, { method: 'POST', body: JSON.stringify(dailyData) });
            renderDashboards();
        }

        function renderTable() {
            const tbody = document.getElementById('table-body');
            tbody.innerHTML = '';
            for (let d = 1; d <= 30; d++) {
                let row = `<tr class="hover:bg-white/5 border-b border-white/5">
                    <td class="p-2 sticky-col font-bold text-slate-500 text-center text-xs">${d}日</td>`;
                persons.forEach(p => {
                    for(let i=0; i<6; i++) {
                        const v = dailyData[d][p][i];
                        row += `<td class="p-1 border-r border-white/5">
                            <div contenteditable="true" class="editable-cell metric-col-${i}" 
                            data-day="${d}" data-person="${p}" data-metric="${i}" 
                            oninput="handleInput(this)">${v||''}</div></td>`;
                    }
                });
                tbody.innerHTML += row + '</tr>';
            }
            renderFooter();
        }

        function renderFooter() {
            const tfoot = document.getElementById('table-footer');
            let totals = { qiao: Array(6).fill(0), zeng: Array(6).fill(0), yang: Array(6).fill(0) };
            for (let d = 1; d <= 30; d++) {
                persons.forEach(p => { for(let i=0; i<6; i++) totals[p][i] += (dailyData[d][p][i] || 0); });
            }
            let html = `<tr class="total-row sticky bottom-0 z-50">
                <td class="p-3 sticky-col text-emerald-500 font-black text-center text-xs">月合计</td>`;
            persons.forEach(p => {
                totals[p].forEach((v, i) => {
                    html += `<td class="p-2 text-center border-r border-white/10 metric-col-${i} font-black">${v}</td>`;
                });
            });
            tfoot.innerHTML = html + '</tr>';
        }

        function renderDashboards() {
            const container = document.getElementById('charts-container');
            container.innerHTML = '';
            container.className = "grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10";

            persons.forEach((pid, idx) => {
                let pTotals = Array(6).fill(0);
                for (let d=1; d<=30; d++) for(let i=0; i<6; i++) pTotals[i] += dailyData[d][pid][i];
                
                container.innerHTML += `
                <div class="glass-card p-6 flex items-center gap-4 h-[280px]">
                    <div class="w-24 flex flex-col justify-between h-full py-2 border-r border-white/10 pr-4">
                        ${titles.map((t, i) => `
                            <div class="flex flex-col">
                                <span class="text-[12px] uppercase opacity-40 font-bold">${t}</span>
                                <span class="text-sm font-black metric-col-${i}">${pTotals[i]}</span>
                            </div>
                        `).join('')}
                    </div>

                    <div class="flex-1 h-full min-w-0">
                        <canvas id="chart-${pid}"></canvas>
                    </div>

                    <div class="w-32 flex flex-col justify-center items-end text-right pl-4 border-l border-white/10 h-full">
                        <div class="mb-4">
                            <p class="text-[10px] font-black opacity-40 tracking-widest uppercase">Member</p>
                            <h3 class="text-3xl font-black italic tracking-tighter name-${pid} whitespace-nowrap">${personNames[idx]}</h3>
                        </div>
                        <div class="bg-emerald-500/10 p-3 rounded-2xl border border-emerald-500/20 w-full">
                            <p class="text-[10px] font-bold text-emerald-500 uppercase">Retention</p>
                            <span class="text-4xl font-black italic text-emerald-400">${pTotals[5]}</span>
                        </div>
                    </div>
                </div>`;

                setTimeout(() => {
                    new Chart(document.getElementById(`chart-${pid}`), {
                        type: 'bar',
                        data: {
                            labels: ['新招呼','邀约','面试','发通过函','发人','留人'],
                            datasets: [{ 
                                data: pTotals, 
                                backgroundColor: metricColors, 
                                borderRadius: 6,
                                barPercentage: 0.7
                            }]
                        },
                        options: { 
                            responsive: true, maintainAspectRatio: false,
                            layout: { padding: { top: 30 } }, 
                            plugins: { 
                                legend: { display: false },
                                datalabels: { 
                                    anchor: 'end',
                                    align: 'top',
                                    color: (ctx) => metricColors[ctx.dataIndex],
                                    font: { weight: '900', size: 12 },
                                    formatter: (val) => val > 0 ? val : ''
                                }
                            },
                            scales: { 
                                y: { display: false }, 
                                x: { 
                                    display: false, // 修改：去掉下方显示表头（隐藏X轴标签）
                                    grid: { display: false }
                                } 
                            }
                        }
                    });
                }, 50);
            });
        }

        window.onload = initData;
    </script>
</body>
</html>