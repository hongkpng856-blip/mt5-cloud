// --- script block 0 ---

// --- script block 1 ---
// === EA 診斷報告 ===
let currentReport = null;

async function showReport(magic, symbol) {
    document.getElementById('reportTitle').innerHTML = '<i class="icon-file-chart-column" style="color:var(--accent)"></i> 診斷報告 — Magic ' + magic + ' / ' + symbol;
    document.getElementById('reportModal').style.display = 'block';
    document.getElementById('reportStats').innerHTML = '<div class="loading" style="margin:20px auto"></div>';
    
    try {
        const res = await fetch(`/api/ea-report?magic=${magic}&symbol=${symbol}`);
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        currentReport = data;
        renderReport(data);
    } catch(e) {
        document.getElementById('reportStats').innerHTML = '<span style="color:var(--danger)"><i class="icon-circle-x"></i> ' + e.message + '</span>';
    }
}

function closeReport() {
    document.getElementById('reportModal').style.display = 'none';
}

function renderReport(data) {
    // Stats
    document.getElementById('reportStats').innerHTML = `
        <div class="stat-box"><div class="label">Trades</div><div class="value">${data.total_trades}</div></div>
        <div class="stat-box"><div class="label">Win Rate</div><div class="value" style="color:${data.win_rate>=60?'#3fb950':'#d29922'}">${data.win_rate}%</div></div>
        <div class="stat-box"><div class="label">Profit Factor</div><div class="value">${data.profit_factor===Infinity?'∞':data.profit_factor}</div></div>
        <div class="stat-box"><div class="label">Total P&L</div><div class="value" style="color:${data.total_profit>=0?'#3fb950':'#f85149'}">${data.total_profit>=0?'+':''}$${data.total_profit.toFixed(2)}</div></div>
        <div class="stat-box"><div class="label">Avg Win</div><div class="value" style="color:#3fb950">$${data.avg_win.toFixed(2)}</div></div>
        <div class="stat-box"><div class="label">Avg Loss</div><div class="value" style="color:#f85149">-$${Math.abs(data.avg_loss).toFixed(2)}</div></div>
        <div class="stat-box"><div class="label">Max DD</div><div class="value" style="color:#f85149">${data.max_drawdown_pct.toFixed(1)}%</div></div>
    `;

    // Equity curve
    const eq = data.equity_curve;
    if (eq.length > 0) {
        const vals = eq.map(d => d.cumulative);
        const min = Math.min(...vals);
        const max = Math.max(...vals);
        const range = max - min || 1;
        const chart = document.getElementById('equityChart');
        // Show every Nth label
        const step = Math.max(1, Math.floor(eq.length / 20));
        chart.innerHTML = eq.map((d, i) => {
            const h = ((d.cumulative - min) / range * 100);
            const c = d.cumulative >= 0 ? '#3fb950' : '#f85149';
            return `<div title="${d.time}: $${d.cumulative.toFixed(2)}" style="flex:1;height:${h}%;background:${c};border-radius:2px 2px 0 0;min-height:2px"></div>`;
        }).join('');
        document.getElementById('eqStart').textContent = eq[0].time?.substring(0,10) || '';
        document.getElementById('eqEnd').textContent = eq[eq.length-1].time?.substring(0,10) || '';
    }

    // Distribution
    const dist = data.distribution;
    const maxCount = Math.max(1, ...dist.wins, ...dist.losses);
    document.getElementById('distChart').innerHTML = dist.bins.map((b, i) => `
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px">
            <div style="height:${dist.wins[i]/maxCount*100}%;width:60%;background:#3fb950;border-radius:2px 2px 0 0;min-height:2px" title="Wins: ${dist.wins[i]}"></div>
            <div style="height:${dist.losses[i]/maxCount*100}%;width:60%;background:#f85149;border-radius:2px 2px 0 0;min-height:2px" title="Losses: ${dist.losses[i]}"></div>
            <span style="font-size:9px;color:#8b949e">${b}</span>
        </div>
    `).join('');

    // Monthly P&L
    const months = Object.keys(data.monthly_pnl).sort();
    if (months.length > 0) {
        const mnVals = months.map(m => data.monthly_pnl[m]);
        const mnMax = Math.max(...mnVals.map(Math.abs), 1);
        document.getElementById('monthlyChart').innerHTML = months.map(m => {
            const v = data.monthly_pnl[m];
            const h = Math.abs(v) / mnMax * 100;
            const c = v >= 0 ? '#3fb950' : '#f85149';
            return `<div style="display:flex;flex-direction:column;align-items:center;flex:1 0 50px">
                <div title="${m}: ${v>=0?'+':''}$${v.toFixed(2)}" style="height:${h}%;width:80%;background:${c};border-radius:2px 2px 0 0;min-height:2px"></div>
                <span style="font-size:9px;color:#8b949e;margin-top:2px">${m.substring(5)}</span>
            </div>`;
        }).join('');
    }
}

// Close modal on Escape key
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeReport(); });
// --- script block 2 ---
const socket = io();

// 聽 Agent 嘅安裝結果 (dedup)
let _lastLog = '';
socket.on('install_result', (data) => {
    const msg = data.msg || ('已安裝: ' + data.ea);
    if (msg === _lastLog) return; // skip duplicate
    _lastLog = msg;
    if (data.status === 'ok') {
        showLog('✅ ' + msg, 'log-success');
    } else if (data.status === 'sent') {
        showLog('📡 已發送指令: ' + data.ea, 'log-info');
    } else if (data.status === 'info') {
        showLog(msg, 'log-info');
    } else {
        showLog('❌ ' + (msg || data.ea || 'unknown'), 'log-error');
    }
});

// === EA Config ===
let eaMappings = {};
let runtimeStatus = {};  // ⚠️ 控制層心跳狀態（running/stopped/unknown）
let allSymbols = [];
let analysisData = null;
let heartbeats = {};
let sortOrder = {};
let detectorSignals = {};  // detector :5003 嘅信號資料
let eaDeployStatus = {};   // EA -> 部署狀態（running/stopped）

function getSignalHtml(name, sym, tf) {
    const s = detectorSignals[name];
    if (!s) return '<span style="color:var(--text-dim)">—</span>';
    if (s.signal === 'BUY') return '<span style="color:var(--success)"><i class="icon-trending-up" style="font-size:11px"></i> BUY</span>';
    if (s.signal === 'SELL') return '<span style="color:var(--danger)"><i class="icon-trending-down" style="font-size:11px"></i> SELL</span>';
    if (s.signal === 'PAUSED') return '<span style="color:var(--accent-orange)"><i class="icon-pause-circle" style="font-size:11px"></i> 暫停</span>';
    return '<span style="color:var(--text-muted)"><i class="icon-hourglass" style="font-size:11px"></i> WAIT</span>';
}

async function fetchEAInventory() {
    try {
        // 🚨 2026-08-11 修：移除 AbortSignal.timeout(8000)（可能 timeout → eaDeployStatus 空 → 「已加入」判斷錯）
        // 🚨 2026-08-11 修：唔再 call loadEALibrary/loadEAConfig（每次 render 成個表格 → scroll 卡 — 佢哋自己 poll）
        const res = await fetch('/static/detector/ea_inventory.json?t=' + Date.now());
        const d = await res.json();
        if (d.error) throw new Error(d.error);

        // 存部署狀態：EA名 -> running/stopped
        eaDeployStatus = {};
        d.eas.forEach(ea => {
            eaDeployStatus[ea.name] = {
                deployed: ea.deployed,
                configured: ea.configured,
                config_status: ea.config_status
            };
        });
    } catch(e) {
        // Detector offline — 標記全部停止
        eaDeployStatus = {};
    }
}

async function loadEAConfig() {
    try {
        const res = await fetch('/api/ea-config');
        const data = await res.json();
        eaMappings = data.mappings || {};
        runtimeStatus = data.runtime_status || {};  // ⚠️ 控制層心跳狀態（running/stopped/unknown）
        allSymbols = data.all_symbols || ['EURUSD','GBPUSD','USDJPY','XAUUSD'];

        // 搵出已配對嘅 EA（config 入邊有 symbol 嘅就係）
        const pairedEAs = Object.keys(eaMappings).filter(k =>
            !k.startsWith('_') && !k.endsWith('_tf') && !k.endsWith('_lot') && !k.endsWith('_magic') && !k.endsWith('_status') &&
            eaMappings[k] && typeof eaMappings[k] === 'string'
        );

        const dl = eaMappings['_default_lot'] || 1.00;
        document.getElementById('defaultLot').value = dl;

        // 已刪除嘅 EA
        const removed = eaMappings['_removed'] || [];

        // 過濾：只要未刪除嘅 + 本機有檔案（detector inventory）— MT5 剷除咗就自動消失
        const activeEAs = pairedEAs.filter(name => !removed.includes(name) && eaDeployStatus[name]);

        // 🚨 2026-08-11：配對庫顯示「本機 EA」（未配對都顯示 — 用戶想要）+ 每行有狀態標記（已配對/未配對 — 唔會誤會）
        const localEA = Object.keys(eaDeployStatus).filter(n => !removed.includes(n));
        const allEAs = [...new Set([...activeEAs, ...localEA])];

        // 排序：🟢 運行中喺上面，⚪ 停止中喺下面；已配對優先
        allEAs.sort((a, b) => {
            const da = (eaDeployStatus[a] && eaDeployStatus[a].deployed) ? 1 : 0;
            const db = (eaDeployStatus[b] && eaDeployStatus[b].deployed) ? 1 : 0;
            if (da !== db) return db - da;
            const pa = eaMappings[a] ? 1 : 0;
            const pb = eaMappings[b] ? 1 : 0;
            return pb - pa;
        });

        // 用 analysis data 嘅 magic+symbol 組合自動分配俾 EA
        const combos = analysisData && analysisData.per_ea_by_magic_symbol ? Object.keys(analysisData.per_ea_by_magic_symbol) : [];
        let comboIndex = 0;

        let html = '';
        if (allEAs.length === 0) {
            html = `<tr><td colspan="14" style="text-align:center;padding:30px;color:var(--text-muted)">
                仲未加入任何 EA<br><span style="font-size:12px">去 EA 倉庫 㩒「<i class="icon-plus-circle"></i> 移去配對」開始</span>
            </td></tr>`;
        } else {
            allEAs.forEach(name => {
            let sym = eaMappings[name] || allSymbols[0];
            let magic = eaMappings[name+'_magic'] || '240701';

            // Auto-assign magic+symbol from available combos if not yet configured
            if (!eaMappings[name] && combos.length > 0) {
                const combo = combos[comboIndex % combos.length];
                const [m, s] = combo.split('_', 2);
                magic = m;
                sym = s;
                comboIndex++;
            }
            const tf = eaMappings[name+'_tf'] || 'H1';
            const lot = eaMappings[name+'_lot'] || dl;
            const status = eaMappings[name+'_status'] || 'running';
            const isRunning = status === 'running';
            const isOfficial = ["SMA_Cross","EMA_Cross","RSI_Over","MACD_Cross","Bollinger_Band","Stochastic","ADX_Trend","ATR_Stop","Ichimoku","Parabolic_SAR","Heikin_Ashi","Volume_Spike","Support_Resist","Price_Action","Breakout","Trend_Follow","Scalping_M1","Grid_Trading","Martingale","Hedge_Fund","News_Trader","Swing_Trader","Divergence","Multi_TimeFrame","Correlation","Mean_Reversion","Momentum","Fibonacci","Seasonal","Machine_Learn"].includes(name);
            // ⚠️ 系統檔案（Controller — 網頁控制中樞 — 唔可以剷除/暫停）
            const isSystem = name === 'Controller';

            // 從 analysis 攞 data（match by magic+symbol）
            const msKey = magic + '_' + sym;
            const eaData = analysisData && analysisData.per_ea_by_magic_symbol ? analysisData.per_ea_by_magic_symbol[msKey] : null;
            const trades = eaData ? eaData.trades : 0;
            const wr = eaData ? eaData.win_rate : 0;
            const profit = eaData ? eaData.profit : 0;

            html += `<tr>
                <td><b>${name}</b></td>
                <td><span style="font-size:10px" class="${isSystem?'badge badge-blue':isOfficial?'badge badge-green':'badge badge-gray'}">${isSystem?'系統':isOfficial?'官方':(eaMappings[name]?'自訂':'本機')}</span></td>
                <td style="text-align:center;white-space:nowrap">
                    <div style="font-size:14px;${eaDeployStatus[name]&&eaDeployStatus[name].deployed?'color:var(--success)':'color:var(--text-dim)'}" title="${eaDeployStatus[name]&&eaDeployStatus[name].deployed?'運行中':(eaMappings[name]?'停止中':'未配對')}">${eaDeployStatus[name]&&eaDeployStatus[name].deployed?'<i class="icon-circle" style="color:var(--success);font-size:10px"></i>':'<i class="icon-circle" style="color:var(--text-dim);font-size:10px"></i>'}</div>
                    <div style="font-size:9px;color:#8b949e;margin-top:1px">${eaDeployStatus[name]&&eaDeployStatus[name].deployed?'運行中':(eaMappings[name]?'停止中':'未配對')}</div>
                    ${runtimeStatus[name]?`<div style="font-size:9px;color:${runtimeStatus[name]==='running'?'var(--success)':runtimeStatus[name]==='stopped'?'var(--text-dim)':'#d29922'};margin-top:1px" title="控制層心跳">${runtimeStatus[name]==='running'?'❤ 心跳運行':runtimeStatus[name]==='stopped'?'● 已停止':'◇ 無心跳'}</div>`:''}
                </td>
                <td><select class="ea-magic" data-ea="${name}" style="width:85px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);padding:3px 4px;font-size:12px">${(analysisData&&analysisData.all_magics||['240701']).map(m => `<option ${m===magic?'selected':''} value="${m}">Magic ${m}</option>`).join('')}</select></td>
                <td style="text-align:center;font-size:12px;color:var(--text-dim)" title="部署後顯示所選品種">
                    <span>${sym||'—'}</span>
                    <select class="ea-sym" data-ea="${name}" style="display:none">${allSymbols.map(s => `<option ${s===sym?'selected':''}>${s}</option>`).join('')}</select>
                </td>
                <td><select class="ea-tf" data-ea="${name}">${['M1','M5','M15','M30','H1','H4','D1','W1','MN1'].map(t => `<option ${t===tf?'selected':''}>${t}</option>`).join('')}</select></td>
                <td style="text-align:center;font-weight:600">${getSignalHtml(name, sym, tf)}</td>
                <td style="text-align:center;color:var(--text-muted);font-size:12px">${detectorSignals[name]?detectorSignals[name].sma10:'—'}</td>
                <td style="text-align:center;color:var(--text-muted);font-size:12px">${detectorSignals[name]?detectorSignals[name].sma30:'—'}</td>
                <td style="text-align:center;color:${trades>0?'#e6edf3':'#484f58'}">${trades>0?trades:'—'}</td>
                <td style="text-align:center;color:${wr>=60?'#3fb950':wr>0?'#d29922':'#484f58'}">${wr>0?wr+'%':'—'}</td>
                <td style="text-align:right;color:${profit>0?'#3fb950':profit<0?'#f85149':'#484f58'};font-weight:${profit!==0?'600':'400'}">${profit!==0?(profit>0?'+':'')+'$'+profit.toFixed(2):'—'}</td>
                <td><input type="number" class="ea-lot" data-ea="${name}" value="${lot}" min="0.01" max="100" step="0.01"></td>
                <td>
                    <button class="btn" style="padding:2px 8px;font-size:11px;color:#58a6ff;border-color:#58a6ff" onclick="deployEA('${name}','${sym}','${tf}','${magic}','${lot}')" title="部署到 MT5"><i class="icon-rocket" style="font-size:11px"></i></button>
                    ${!isSystem?`<button class="btn" style="padding:2px 8px;font-size:11px;color:#d29922;border-color:#d29922" onclick="showReport('${magic}','${sym}')" title="診斷報告"><i class="icon-file-chart-column" style="font-size:11px"></i></button>`:''}
                    ${!isSystem?`<button class="btn" style="padding:2px 8px;font-size:11px;${isRunning?'color:#d29922;border-color:#d29922':'color:#3fb950;border-color:#3fb950'}" onclick="toggleEA('${name}')" title="${isRunning?'暫停':'繼續'}">${isRunning?'<i class="icon-pause" style="font-size:11px"></i>':'<i class="icon-play" style="font-size:11px"></i>'}</button>`:''}
                    ${!isSystem?`<button class="btn" style="padding:2px 8px;font-size:11px;color:#f85149;border-color:#f85149" onclick="deleteEA('${name.split('.')[0]}')" title="刪除 ${name}"><i class="icon-trash-2" style="font-size:11px"></i></button>`:''}
                    ${isSystem?'<span style="font-size:10px;color:#58a6ff;margin-left:2px" title="系統控制中樞 — 自動運行"><i class="icon-shield-check" style="font-size:11px"></i></span>':''}
                </td>
            </tr>`;
        });

        } // end else

        document.getElementById('eaTableBody').innerHTML = html;
        document.getElementById('eaCount').textContent = allEAs.length;
    } catch(e) { console.error(e); }
}

function applyAllLots() {
    const val = parseFloat(document.getElementById('defaultLot').value) || 1.00;
    document.querySelectorAll('.ea-lot').forEach(i => i.value = val.toFixed(2));
}

async function saveEAConfig() {
    const mappings = {};
    mappings['_default_lot'] = parseFloat(document.getElementById('defaultLot').value) || 1.00;
    document.querySelectorAll('.ea-sym').forEach(sel => {
        const name = sel.dataset.ea;
        mappings[name] = sel.value;
        mappings[name+'_magic'] = document.querySelector('.ea-magic[data-ea="'+name+'"]').value || '240701';
        mappings[name+'_tf'] = document.querySelector(`.ea-tf[data-ea="${name}"]`).value;
        mappings[name+'_lot'] = parseFloat(document.querySelector(`.ea-lot[data-ea="${name}"]`).value) || 1.00;
    });
    await fetch('/api/ea-config', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({mappings})
    });
    showLog('✅ EA config saved!');

    // 如果 Agent 在線，自動發送安裝指令
    const dashRes = await fetch('/api/dashboard');
    const dashData = await dashRes.json();
    if (dashData.status === 'connected' || dashData.status === 'running') {
        const eaNames = Array.from(document.querySelectorAll('.ea-sym')).map(s => s.dataset.ea);
        socket.emit('agent_install_ea', { agent_id: dashData.agent_id, ea_name: 'all', ea_list: eaNames });
    } else {
        showLog('💡 Agent 離線，連線後會自動同步安裝 EA ✅', 'log-warn');
    }
}

function showLog(msg, cls='log-success') {
    const box = document.getElementById('logBox');
    if (!box) return;
    box.classList.add('show');
    const div = document.createElement('div');
    div.className = cls;
    div.textContent = msg;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

// === Dashboard ===
async function loadDashboard() {
    try {
        const res = await fetch('/api/dashboard');
        const d = await res.json();
        document.getElementById('agentId').textContent = d.agent_id || '—';
        document.getElementById('accountLogin').textContent = d.account?.login || '—';
        document.getElementById('accountServer').textContent = d.account?.server || '—';
        document.getElementById('balance').textContent = d.account ? '$'+Number(d.account.balance).toLocaleString() : '—';
        document.getElementById('equity').textContent = d.account ? '$'+Number(d.account.equity).toLocaleString() : '—';

        // Binding status
        const bindEl = document.getElementById('bindingStatus');
        const bindBtn = document.getElementById('bindBtn');
        if (d.bound_account) {
            if (d.account_matched) {
                bindEl.innerHTML = '<i class="icon-check-circle" style="color:var(--success)"></i> ' + d.bound_account + ' <button onclick="toggleBind()" style="font-size:11px;padding:2px 8px;cursor:pointer">解除</button>';
                bindBtn.style.display = 'none';
            } else {
                bindEl.innerHTML = '<i class="icon-alert-triangle" style="color:var(--accent-orange)"></i> 綁定: ' + d.bound_account + ' (當前: ' + (d.account?.login||'無') + ')';
                bindBtn.style.display = 'inline';
            }
        } else {
            bindEl.innerHTML = '— <button onclick="toggleBind()" style="font-size:11px;padding:2px 8px;margin-left:4px;cursor:pointer"><i class="icon-link"></i> 綁定</button>';
        }

        const badge = document.getElementById('statusBadge');
        if (d.status === 'connected' || d.status === 'running') {
            badge.textContent = 'Online'; badge.className = 'badge badge-green';
            heartbeats = d.ea_heartbeats || {};
        } else {
            badge.textContent = 'Offline'; badge.className = 'badge badge-red';
        }

        document.getElementById('posCount').textContent = (d.positions||[]).length;
    } catch(e) {}

    // === Auto-Trade Detector (獨立進程 :5003 — 唯一 detect 來源) ===
    fetchAutoTradeStatus();
}

async function fetchAutoTradeStatus() {
    try {
        const res = await fetch('/static/detector/auto_trade_status.json?t=' + Date.now(), {
            signal: AbortSignal.timeout(5000)
        });
        const d = await res.json();

        // 將信號資料存起嚟，俾配對庫表格用
        detectorSignals = {};
        if (d.results) {
            d.results.forEach(r => {
                detectorSignals[r.ea] = {signal: r.signal, sma10: r.sma10, sma30: r.sma30};
            });
        }
        // 重新渲染配對庫表格（SMA/Signal 欄位）
        loadEAConfig();
    } catch(e) {
        // Detector offline — 清空信號
        detectorSignals = {};
        loadEAConfig();
    }
}

// === Analysis ===
async function loadAnalysis() {
    try {
        const res = await fetch('/api/analysis');
        if (!res.ok) return;
        analysisData = await res.json();
        if (analysisData.error) return;

        const s = analysisData.summary;
        document.getElementById('anTrades').textContent = s.total_trades;
        document.getElementById('anWinRate').textContent = s.win_rate+'%';
        document.getElementById('anProfit').textContent = (s.total_profit>=0?'+':'')+'$'+s.total_profit.toFixed(2);
        document.getElementById('anProfit').style.color = s.total_profit>=0?'#3fb950':'#f85149';
        document.getElementById('anPF').textContent = s.wins&&s.losses ? (s.wins/s.losses).toFixed(2) : '∞';

        // 只更新 summary 數字，唔 rebuild 成個 EA 表（防止 dropdown 彈走）
        _updateEAData(s);

        // Correlation Matrix
        if (analysisData.correlation_matrix && analysisData.correlation_matrix.length > 1) {
            let keys = analysisData.correlation_keys;
            let cm = '<thead><tr><th style="min-width:70px">EA</th>';
            keys.forEach(k => { cm += `<th>${k.length>12?k.substring(0,10)+'..':k}</th>`; });
            cm += '</tr></thead><tbody>';
            analysisData.correlation_matrix.forEach(row => {
                cm += `<tr><td style="font-size:10px">${row.ea.length>12?row.ea.substring(0,10)+'..':row.ea}</td>`;
                keys.forEach(k => {
                    let v = row[k]||0;
                    let c = v>0.5?'#3fb950':v>0?'#2d6a3a':v<-0.5?'#f85149':v<0?'#6a2d2d':'#484f58';
                    cm += `<td style="color:${c};font-weight:${Math.abs(v)>0.5?'600':'400'}">${v.toFixed(2)}</td>`;
                });
                cm += '</tr>';
            });
            document.getElementById('corrTable').innerHTML = cm;
        }
    } catch(e) {}
}

function _updateEAData() {
    // 只更新數字 cells，唔 rebuild 成個 table（防止 dropdown 彈走）
    if (!analysisData || !analysisData.per_ea_by_magic_symbol) return;
    document.querySelectorAll('.ea-sym').forEach(sel => {
        const name = sel.dataset.ea;
        if (!name) return;
        const magic = document.querySelector('.ea-magic[data-ea="'+name+'"]')?.value || '240701';
        const sym = sel.value;
        const msKey = magic + '_' + sym;
        const eaData = analysisData.per_ea_by_magic_symbol[msKey] || {};
        const tr = sel.closest('tr');
        if (!tr) return;
        const cells = tr.querySelectorAll('td');
        // Indices: 0=EA,1=來源,2=Magic,3=Symbol,4=TF,5=Trades,6=Win,7=P&L
        if (cells[5]) {
            const t = eaData.trades || 0;
            cells[5].textContent = t > 0 ? t : '—';
            cells[5].style.color = t > 0 ? '#e6edf3' : '#484f58';
        }
        if (cells[6]) {
            const wr = eaData.win_rate || 0;
            cells[6].textContent = wr > 0 ? wr + '%' : '—';
            cells[6].style.color = wr >= 60 ? '#3fb950' : wr > 0 ? '#d29922' : '#484f58';
        }
        if (cells[7]) {
            const p = eaData.profit || 0;
            cells[7].textContent = p !== 0 ? (p > 0 ? '+' : '') + '$' + p.toFixed(2) : '—';
            cells[7].style.color = p > 0 ? '#3fb950' : p < 0 ? '#f85149' : '#484f58';
            cells[7].style.fontWeight = p !== 0 ? '600' : '400';
        }
    });
}

// === 通知系統（MT5 目錄變化 → toast + 即時更新）===
let seenNotifIds = new Set();

function showToast(message, type, timestamp) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const el = document.createElement('div');
    el.className = 'toast-item ' + (type || '');
    const icon = type === 'deleted' ? '<i class="icon-trash-2" style="color:var(--danger)"></i>'
        : type === 'added' ? '<i class="icon-plus-circle" style="color:var(--success)"></i>'
        : '<i class="icon-refresh-cw" style="color:var(--accent-orange)"></i>';
    const timeStr = timestamp ? new Date(timestamp * 1000).toLocaleTimeString() : '';
    el.innerHTML = icon + '<span>' + message + '</span><span class="toast-time">' + timeStr + '</span>';
    container.appendChild(el);
    // 5 秒後自動消失
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .5s'; setTimeout(() => el.remove(), 500); }, 5000);
    // 最多同時顯示 5 個
    while (container.children.length > 5) container.firstChild.remove();
}

async function fetchNotifications() {
    try {
        const res = await fetch('/static/detector/notifications.json?t=' + Date.now(), {
            signal: AbortSignal.timeout(5000)
        });
        const d = await res.json();
        if (!d.notifications) return;
        let newShown = false;
        d.notifications.forEach(n => {
            if (!seenNotifIds.has(n.id)) {
                seenNotifIds.add(n.id);
                showToast(n.message, n.type, n.time);
                newShown = true;
            }
        });
        // 有新通知 → 即時重新載入 EA 列表（detector 可能未 update static inventory）
        if (newShown) {
            setTimeout(() => { fetchEAInventory(); loadEAConfig(); }, 1500);
        }
    } catch(e) { /* 冇通知檔案就靜默 */ }
}

// === AI 控制警告視窗（網站版）===
let aiControlVisible = false;  // 追蹤視窗狀態（避免重複 show/hide 閃爍）
let minShowUntil = 0;  // 最少顯示時間（防「彈一下」就消失）
let manualDeployActive = false;  // ⚠️ 手動部署鎖定：pollAiControl 唔可以關閉（完成先關）
function showControlModal(actionDesc, detailMsg) {
    const modal = document.getElementById('aiControlModal');
    const prog = document.getElementById('aiControlProg');
    const desc = document.getElementById('aiControlDesc');
    // 🚨 2026-08-11：新操作彈出 → 清舊內容（唔殘留上一個操作資訊 + 按鈕正常 — 用戶投訴）
    const sc0 = document.getElementById('aiControlSteps');
    if (sc0) sc0.innerHTML = '';
    const stop0 = document.getElementById('aiControlStopBtn');
    if (stop0) { stop0.style.display = 'inline-flex'; stop0.disabled = false; }
    const close0 = document.getElementById('aiControlCloseBtn');
    if (close0) close0.style.display = 'none';
    // 🚨 2026-08-10：操作名（prog）隱藏 — 已併入步驟第一條（用戶要求：操作名整合步驟列表 — 同電腦版一致）
    if (prog) { prog.style.display = 'none'; prog.textContent = actionDesc || '正在處理'; prog.style.color = 'inherit'; }
    if (desc) desc.textContent = detailMsg || '請勿移動滑鼠或按鍵盤！';
    if (modal && !aiControlVisible) { modal.classList.add('show'); aiControlVisible = true; }
    // 🚨 2026-08-11：記錄「當前任務」時間戳（poll 用嚟判斷舊 steps 唔顯示 — 新任務開始唔殘留上一個操作）
    window._modalShownAt = Date.now();
    // 🚨 2026-08-12：新任務開始 → 清空步驟區 + 顯示「等待操作開始」
    // 等 poll 讀到「新 steps」（steps 含當前 EA 名）先 render — 唔會顯示舊任務殘留 → 流程閃
    if (sc0) sc0.innerHTML = '<div style="padding:2px 0;color:#71717a;font-size:12px">[等待] 等待操作開始…</div>';
    window._stepsShow = false;  // poll 第一次見新 steps → 顯示
    // 動作開始：最少顯示 3 秒（等 watcher 後續動作接手，唔會「彈一下」）
    minShowUntil = Date.now() + 3000;
}
function hideControlModal() {
    const modal = document.getElementById('aiControlModal');
    if (modal && aiControlVisible) { modal.classList.remove('show'); aiControlVisible = false; }
}

// Poll AI 控制狀態（watcher/agent 操控電腦時 → 網站都彈警告視窗；完成 → 關）
// 網站動作完成後唔即刻 hide — 由呢度統一控制（動作真正做完先消失）
async function pollAiControl() {
    try {
        // 1. 讀 steps
        const sr = await fetch('/api/control-steps?t=' + Date.now(), { signal: AbortSignal.timeout(3000) });
        const sc = document.getElementById('aiControlSteps');
        const stopBtn = document.getElementById('aiControlStopBtn');
        const closeBtn = document.getElementById('aiControlCloseBtn');
        const prog = document.getElementById('aiControlProg');
        
        if (sr.ok) {
            const data = await sr.json();
            const steps = Array.isArray(data) ? data : (data.steps || []);
            
            if (sc && steps.length > 0) {
                // 2. Render steps — 簡單 innerHTML（內容一樣唔重寫）
                var html = '';
                var hasDoing = false, hasFail = false;
                for (var i = 0; i < steps.length; i++) {
                    var s = steps[i], st = s.status || 'pending', txt = s.text || '';
                    var mk, cl;
                    if (txt.indexOf('失敗') >= 0) { mk = '失敗'; cl = '#f87171'; hasFail = true; }
                    else if (st === 'doing') { mk = '進行中'; cl = '#fbbf24'; hasDoing = true; }
                    else if (st === 'done') { mk = '完成'; cl = '#34d399'; }
                    else { mk = '等待'; cl = '#71717a'; }
                    html += '<div style="padding:2px 0;font-size:12px;color:' + cl + '">[' + mk + '] ' + txt + '</div>';
                }
                // 內容一樣 skip（避免 innerHTML 重寫 → 閃）
                if (sc._lastHtml === html) { /* skip */ }
                else { sc._lastHtml = html; sc.innerHTML = html; }
                
                // 3. 按鈕 — 統一處理
                if (stopBtn) stopBtn.style.display = (hasDoing || hasFail) ? 'inline-flex' : 'none';
                if (closeBtn) {
                    var allDone = steps.every(function(s){ return s.status === 'done'; });
                    closeBtn.style.display = (allDone && !hasDoing) ? 'inline-block' : 'none';
                }
                // 4. 標題
                if (prog) {
                    if (hasFail) { prog.textContent = '失敗'; prog.style.color = '#f87171'; prog.style.display = 'block'; }
                    else if (hasDoing) { prog.textContent = '執行中'; prog.style.color = '#fbbf24'; prog.style.display = 'block'; }
                    else { prog.textContent = '已完成'; prog.style.color = '#34d399'; prog.style.display = 'block'; }
                }
            } else if (sc && steps.length === 0) {
                // 冇 steps → 顯示等待（唔清空！舊內容保留）
                if (sc.children.length === 0) {
                    sc.innerHTML = '<div style="padding:2px 0;font-size:12px;color:#71717a">[等待] 等待操作開始…</div>';
                }
            }
        }
        
        // 5. ai_control.json → modal 顯示/隱藏
        const ar = await fetch('/static/detector/ai_control.json?t=' + Date.now(), { signal: AbortSignal.timeout(3000) });
        if (ar.ok) {
            var ad = await ar.json();
            var stale = ad.time && (Date.now()/1000 - ad.time) > 120;
            if (ad.active && !stale) {
                if (!aiControlVisible) { showControlModal(ad.program || 'AI 操控中'); }
            }
        }
    } catch(e) { /* 網絡錯誤 → 唔郁 */ }
}
}

async function manualDismiss() {
    // 手動關閉警告視窗（手動部署 mode — 完成咗/取消咗可以自己關）
    manualDeployActive = false;
    hideControlModal();
}
function emergencyStop() {
    const btn = document.getElementById('aiControlStopBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="icon-loader-2"></i> 停止中...'; }
    (async () => {
        try {
            const res = await fetch('/api/control-guard/stop', { method: 'POST' });
            const d = await res.json();
            showToast((d.success ? '🛑 緊急停止已觸發！AI 操作會即刻中止' : '❌ 緊急停止失敗: ' + (d.error || '')), 'deleted');
        } catch(e) {
            showToast('❌ 緊急停止失敗: ' + e.message, 'deleted');
        }
        if (btn) { btn.disabled = false; btn.innerHTML = '<i class="icon-alert-octagon"></i> 緊急停止'; }
    })();
}

// === 活動記錄（持久化 activity log）===
const activityIconMap = {
    'deploy': '<i class="icon-rocket" style="color:var(--accent)"></i>',
    'ea_delete': '<i class="icon-trash-2" style="color:var(--danger)"></i>',
    'ea_toggle': '<i class="icon-pause-circle" style="color:#d29922"></i>',
    'added': '<i class="icon-plus-circle" style="color:var(--success)"></i>',
    'deleted': '<i class="icon-trash-2" style="color:var(--danger)"></i>',
    'modified': '<i class="icon-refresh-cw" style="color:#d29922"></i>',
    'login': '<i class="icon-log-in" style="color:var(--info)"></i>',
    'db_update': '<i class="icon-database" style="color:var(--text-muted)"></i>',
};
const activityActionLabel = {
    'deploy': '部署', 'ea_delete': '刪除', 'ea_toggle': '暫停/恢復',
    'added': '新增', 'deleted': '刪除', 'modified': '更新', 'login': '登入',
    'db_update': '資料庫更新',
};

// 顯示/隱藏「已更新資料庫」恆常記錄
function toggleDbUpdates() {
    const show = document.getElementById('showDbUpdates').checked;
    localStorage.setItem('showDbUpdates', show ? '1' : '0');
    fetchActivity();
}

async function fetchActivity() {
    try {
        const showDb = localStorage.getItem('showDbUpdates') === '1';
        const cb = document.getElementById('showDbUpdates');
        if (cb) cb.checked = showDb;
        const includeDb = showDb ? '&include_db=1' : '';
        const res = await fetch('/api/activity?t=' + Date.now() + includeDb, { signal: AbortSignal.timeout(5000) });
        const d = await res.json();
        const rows = d.activities || [];
        const tbody = document.querySelector('#activityTable tbody');
        const count = document.getElementById('activityCount');
        if (count) count.textContent = rows.length;
        if (!rows.length) {
            tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;padding:20px;color:var(--text-muted)">暫無活動記錄</td></tr>';
            return;
        }
        tbody.innerHTML = rows.map(a => {
            const icon = activityIconMap[a.action] || '<i class="icon-activity" style="color:var(--text-muted)"></i>';
            const label = activityActionLabel[a.action] || a.action;
            const t = new Date(a.time * 1000);
            const timeStr = t.toLocaleDateString() + ' ' + t.toLocaleTimeString();
            return `<tr>
                <td style="white-space:nowrap;font-size:12px;color:var(--text-muted)">${timeStr}</td>
                <td><span class="badge" style="background:var(--bg-muted);color:var(--text-muted)">${icon} ${label}</span></td>
                <td>${a.message || ''}</td>
            </tr>`;
        }).join('');
    } catch (e) { /* server 未支援就靜默 */ }
}

// Init
loadDashboard();
loadEAConfig();
loadAnalysis();
loadEALibrary();
fetchEAInventory();
fetchNotifications();
fetchActivity();
setInterval(loadDashboard, 5000);
setInterval(loadEAConfig, 10000);  // 配對庫列表+數量自己 poll（唔靠 fetchEAInventory）
setInterval(loadAnalysis, 10000);
setInterval(loadEALibrary, 30000);
setInterval(fetchEAInventory, 10000);
setInterval(fetchNotifications, 5000);
setInterval(fetchActivity, 10000);
setInterval(pollAiControl, 700);  // 🚨 2026-08-12：poll 加快（2 秒 → 0.7 秒 — 捕到每步逐步 — 內容平滑更新唔「彈」）網站警告視窗由 ai_control.json 驅動（電腦操控都彈）

// 🚨 2026-08-11：配對庫「重新整理」— 即刻刷新 + 警告視窗流程（成功確定 / 失敗紅色+原因+確定）
async function refreshPairingLibrary() {
    // 🚨 即刻彈 modal（唔靠 poll — refresh 太快捕唔到 active）
    showControlModal('重新整理配對庫', '正在刷新最新 EA 資訊...');
    try {
        const res = await fetch('/api/ea-library/refresh', { method: 'POST' });
        const data = await res.json().catch(() => ({}));
        if (data.success) {
            // 🚨 2026-08-11：順序刷新 — 攞最新配對狀態 → 渲染 EA 倉庫（「已加入」/「移去配對」正確）
            // 🚨 2026-08-11 修：fetchEAInventory 要 await（之前冇 await → loadEALibrary 用舊 eaDeployStatus → detect 唔到已加入）
            if (typeof loadEAConfig === 'function') await loadEAConfig();      // 攞 eaMappings（已配對）
            if (typeof fetchEAInventory === 'function') await fetchEAInventory();   // 攞 eaDeployStatus（本機狀態）
            if (typeof loadEALibrary === 'function') await loadEALibrary();   // 渲染 EA 倉庫（狀態正確）
            if (typeof showLog === 'function') showLog('已重新整理配對庫（攞最新資訊）', 'log-info');
        } else {
            if (typeof showLog === 'function') showLog('❌ 重新整理失敗: ' + (data.error || 'unknown'), 'log-error');
        }
    } catch(e) {
        if (typeof showLog === 'function') showLog('❌ 重新整理失敗: ' + e.message, 'log-error');
    }
    // 完成 → steps 有 done（poll 顯示確定 — 唔自動關）
}

// === EA Library ===
async function loadEALibrary() {
    try {
        // 🚨 2026-08-11 修：唔再自動 call loadEAConfig（loadEAConfig 本身每 10 秒 poll — 已經同步 — 避免每次 render 配對庫表格 → scroll 卡）
        // 🚨 2026-08-11：cache-busting（強制攞最新 — 唔用瀏覽器 cache）
        const res = await fetch('/api/ea-library?t=' + Date.now());
        const data = await res.json();

        // 🚨 2026-08-11：自己攞本機狀態（唔靠 fetchEAInventory 全局 — 確保「已加入」判斷一定準 — 用戶投訴）
        let localSet = {};
        try {
            const invRes = await fetch('/static/detector/ea_inventory.json?t=' + Date.now());
            const invD = await invRes.json();
            (invD.eas || []).forEach(ea => { localSet[ea.name] = true; });
        } catch(e) {}

        // 官方 EA
        const official = (data.files || []).filter(f => f.type === 'official');
        document.getElementById('officialCount').textContent = official.length;
        let oHtml = '';
        official.forEach(f => {
            const baseName = f.name.replace(/\.(mq5|ex5)$/i, '');
            // 🚨 2026-08-11 修：已加入 = 本機有檔案（detect 到 = 加入咗 — 用戶理解：「電腦有 EA 就係已加入」）
            // 「移去配對」= 本機冇嗰陣先需要（撳 → 複製去本機 + compile）
            const webHas = !!(eaMappings[baseName] && typeof eaMappings[baseName] === 'string');  // 網頁已配對
            const localHas = !!(eaDeployStatus[baseName] || localSet[baseName]);                  // 本機有檔案
            const added = localHas;
            oHtml += `<tr>
                <td><b>${f.name}</b> <span class="badge badge-green" style="font-size:10px">平台提供</span></td>
                <td style="font-size:12px;color:#8b949e">${f.size}</td>
                <td>${added ? '<span style="color:var(--success);font-size:11px"><i class="icon-check-circle"></i> 已加入</span>'
                    : (webHas ? '<span style="color:#f59e0b;font-size:11px"><i class="icon-alert-triangle"></i> 已加入（本機冇檔案）</span>'
                    : `<button class="btn" style="padding:2px 10px;font-size:11px" onclick="addEAToPairing('${baseName}','${f.name}','官方')"><i class="icon-plus-circle"></i> 移去配對</button>`)}</td>
            </tr>`;
        });
        const offTable = document.querySelector('#officialTable tbody');
        if (offTable) offTable.innerHTML = oHtml || '<tr><td colspan="3" style="text-align:center;padding:20px;color:var(--text-muted)">—</td></tr>';

        // 社群提供嘅 EA（Developer 上傳）— 只顯示，唔會自動加入（自動加入會令刪除咗嘅 EA 復活）
        const communityFiles = (data.files || []).filter(f => f.type === 'community');
        if (communityFiles.length > 0) {
            // 加返落 official table 下面（用分隔線）
            communityFiles.forEach(f => {
                const baseName = f.name.replace(/\.(mq5|ex5)$/i, '');
                const added = eaMappings[baseName] && typeof eaMappings[baseName] === 'string' && !!eaDeployStatus[baseName];
                oHtml += `<tr style="border-top:${communityFiles.indexOf(f)===0?'2px dashed #bb8009':'none'}">
                    <td><b>${f.name}</b> <span class="badge badge-blue" style="font-size:10px">社群提供</span></td>
                    <td style="font-size:12px;color:#8b949e">${f.size}</td>
                    <td>${added ? '<span style="color:var(--success);font-size:11px"><i class="icon-check-circle"></i> 已加入</span>'
                        : `<button class="btn" style="padding:2px 10px;font-size:11px" onclick="addEAToPairing('${baseName}','${f.name}','社群')"><i class="icon-plus-circle"></i> 移去配對</button>`}</td>
                </tr>`;
            });
        }

        // 用戶上傳嘅 EA 直接放 EA 倉庫下面 — 只顯示，唔會自動加入（Bug #62：自動加入令刪除咗嘅 EA 復活）
        const userFiles = (data.files || []).filter(f => f.type === 'user');
        if (userFiles.length > 0) {
            userFiles.forEach(f => {
                const baseName = f.name.replace(/\.(mq5|ex5)$/i, '');
                const added = eaMappings[baseName] && typeof eaMappings[baseName] === 'string' && !!eaDeployStatus[baseName];
                oHtml += `<tr style="border-top:2px dashed #3fb950">
                    <td><b>${f.name}</b> <span class="badge badge-green" style="font-size:10px">用戶上傳</span></td>
                    <td style="font-size:12px;color:#8b949e">${f.size}</td>
                    <td>${added ? '<span style="color:var(--success);font-size:11px"><i class="icon-check-circle"></i> 已加入</span>'
                        : `<button class="btn" style="padding:2px 10px;font-size:11px" onclick="addEAToPairing('${baseName}','${f.name}','用戶')"><i class="icon-plus-circle"></i> 移去配對</button>`}</td>
                </tr>`;
            });
        }
    } catch(e) {}
}

async function addEAToPairing(baseName, fileName, source) {
    // 顯示 AI 控制警告視窗（網站版 — 處理緊通知 + 緊急停止）
    showControlModal('正在配對 ' + baseName + '，請稍候...');
    // Step 1: 安裝 EA 落本機 MT5 Experts 目錄（配對庫顯示本機已安裝 EA）
    //         server 會等 compile 完成先返回（double-check — 唔會假成功）
    let installData = null;
    try {
        const installRes = await fetch('/api/ea-library/install-local/' + encodeURIComponent(fileName), {
            method: 'POST'
        });
        installData = await installRes.json();
        if (!installData.success) {
            showLog('❌ 安裝失敗: ' + (installData.error || 'unknown'), 'log-error');
            return;
        }
    } catch(e) {
        showLog('❌ 安裝失敗: ' + e.message, 'log-error');
        return;
    }

    // Double-check 結果：compile 失敗要警告用戶 + 提供重試
    if (installData.compile_ok === false) {
        showLog('⚠️ ' + fileName + ' 已複製至本機，但編譯失敗 — MT5 可能未顯示！', 'log-warn');
        // 🚨 2026-08-10：移除原生 confirm（撳取消後狀態混亂 → 兩個按鈕 + 抽搐 — 用戶投訴）
        // 直接失敗流程（警告視窗顯示「編譯失敗」+ 緊急停止 — 用戶自己決定）
        return;
    }

    // Step 2: 寫 config（symbol/magic/tf/lot）
    const res = await fetch('/api/ea-config');
    const data = await res.json();
    let mappings = data.mappings || {};
    const dl = mappings['_default_lot'] || 1.00;

    // Auto-pick unique magic+symbol from analysis
    const analysisRes = await fetch('/api/analysis');
    let combo = { magic: '240701', symbol: 'EURUSD' };
    if (analysisRes.ok) {
        const anData = await analysisRes.json();
        if (anData.per_ea_by_magic_symbol) {
            const combos = Object.keys(anData.per_ea_by_magic_symbol);
            // Find a combo not already used by other EAs
            const usedKeys = new Set();
            for (const k of Object.keys(mappings)) {
                if (!k.startsWith('_') && !k.endsWith('_tf') && !k.endsWith('_lot') && !k.endsWith('_magic') && typeof mappings[k] === 'string') {
                    const m = mappings[k+'_magic'] || '240701';
                    usedKeys.add(m + '_' + mappings[k]);
                }
            }
            for (const c of combos) {
                if (!usedKeys.has(c)) { const [m, s] = c.split('_', 2); combo = { magic: m, symbol: s }; break; }
            }
        }
    }

    mappings[baseName] = mappings[baseName] || combo.symbol;
    mappings[baseName+'_magic'] = mappings[baseName+'_magic'] || combo.magic;
    mappings[baseName+'_tf'] = mappings[baseName+'_tf'] || 'H1';
    mappings[baseName+'_lot'] = mappings[baseName+'_lot'] || dl;

    const saveRes = await fetch('/api/ea-config', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({mappings})
    });
    if (saveRes.ok) {
        loadEALibrary();
        loadEAConfig();
        fetchEAInventory();
        showLog('✅ ' + fileName + ' 已安裝到本機 + 加入配對庫！', 'log-success');
    } else {
        showLog('❌ 加入失敗', 'log-error');
    }
    // 唔即刻 hide — 由 pollAiControl 控制（watcher 可能仲 refresh Navigator）
}

// 重試 compile（之前 compile 失敗之後手動再觸發）
async function retryCompile(baseName) {
    // 重試編譯會操控 MetaEditor（電腦）→ 彈警告視窗
    showControlModal('正在重試編譯 ' + baseName + '，請稍候...');
    try {
        const res = await fetch('/api/ea-library/retry-compile/' + encodeURIComponent(baseName), {
            method: 'POST'
        });
        const data = await res.json();
        if (data.compile_ok) {
            showLog('✅ ' + baseName + ' 重試 compile 成功！', 'log-success');
            loadEALibrary();
            loadEAConfig();
            fetchEAInventory();
            setTimeout(() => { loadEAConfig(); fetchEAInventory(); }, 2000);
        } else {
            showLog('❌ ' + baseName + ' 重試 compile 失敗: ' + (data.message || '未知錯誤'), 'log-error');
        }
    } catch(e) {
        showLog('❌ 重試失敗: ' + e.message, 'log-error');
    }
    // 唔即刻 hide — 由 pollAiControl 控制
}

async function deleteEA(eaName) {
    // 🚨 2026-08-12 修：移除瀏覽器原生 confirm（「確定要刪除？」彈出 → 同警告視窗交替 → 「彈」！— 影片實據：f_007 捕捉到原生 confirm）
    // 直接刪除 — 警告視窗會顯示「開始剷除 XXX」流程（用戶睇到做緊咩 — 唔需要原生確認框）
    showControlModal('正在刪除 ' + eaName + '，請稍候...');
    try {
        // 1. 刪除本機 MQL5/Experts 檔案
        const delRes = await fetch(`/api/ea-library/remove-local/${eaName}`, { method: 'POST' });
        const delData = await delRes.json().catch(() => ({}));
        // 🚨 2026-08-08：remove-local 一定要成功先刪 config（防半刪除狀態 — 檔案喺 config 冇）
        if (!delRes.ok || !delData.success) {
            showLog(`❌ 刪除檔案失敗: ${delData.error || delRes.status}（檔案未刪除 — 保留配對設定）`, 'log-error');
            hideControlModal();
            return;
        }
        // 2. 移除 DB config
        const res = await fetch(`/api/ea-config/${eaName}`, { method: 'DELETE' });
        if (res.ok) {
            showLog(`🗑️ ${eaName} 已刪除（檔案+設定）`, 'log-error');
            // 先等 config 更新（eaMappings）再渲染 EA 倉庫 — 唔可以並行（會用舊值顯示「已加入」）
            await loadEAConfig();
            loadEALibrary();
            fetchEAInventory();
        }
    } catch(e) { console.error(e); }
    // 唔即刻 hide — 由 pollAiControl 控制（watcher 可能仲 refresh Navigator）
}

async function toggleEA(eaName) {
    try {
        const res = await fetch(`/api/ea-config/${eaName}/toggle`, { method: 'POST' });
        if (res.ok) {
            const data = await res.json();
            showLog(`${data.status==='paused'?'⏸️ 已暫停':'▶️ 已繼續'} ${eaName}`, data.status==='paused'?'log-warn':'log-success');
            loadEAConfig();
        }
    } catch(e) { console.error(e); }
}

// ═══ 品種選擇 modal（2026-08-07：部署前揀交易品種）═══
let _pendingDeploy = null;
// 🚨 2026-08-10：只限「確定位置」嘅 symbol（auto_attach _SYM_DOWN 有 Down×N 位置 — 用戶重新確認）
// 1.EURUSD 2.GBPUSD 3.USDCHF 4.USDJPY 5.USDCNH 6.AUDUSD
const SYMBOL_OPTIONS = ['EURUSD', 'GBPUSD', 'USDCHF', 'USDJPY', 'USDCNH', 'AUDUSD'];

function showSymbolPicker(eaName, tf, magic, lot, defaultSym) {
    _pendingDeploy = { eaName, tf, magic, lot };
    document.getElementById('symbolPickerTitle').innerHTML = '<i class="icon-robot" style="color:var(--accent)"></i> ' + eaName + ' → <span style="color:var(--text-dim)">' + (tf || 'H1') + '</span>';
    const sel = document.getElementById('symbolPickerSelect');
    sel.innerHTML = '';
    // 🚨 2026-08-10：只顯示確定位置嘅 symbol（唔好 allSymbols 全部 — 揀咗部署唔到）
    SYMBOL_OPTIONS.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        if (s === defaultSym) opt.selected = true;
        sel.appendChild(opt);
    });
    document.getElementById('symbolPickerModal').style.display = 'flex';
}

function closeSymbolPicker() {
    document.getElementById('symbolPickerModal').style.display = 'none';
    _pendingDeploy = null;
}

function confirmSymbolPick() {
    const sym = document.getElementById('symbolPickerSelect').value;
    const d = _pendingDeploy;
    closeSymbolPicker();
    if (d && sym) {
        doDeployEA(d.eaName, sym, d.tf, d.magic, d.lot);
    }
}

async function deployEA(eaName, symbol, tf, magic, lot) {
    showSymbolPicker(eaName, tf, magic, lot, symbol);
}

async function doDeployEA(eaName, symbol, tf, magic, lot) {
    showControlModal('正在部署 ' + eaName + '，請稍候...');
    // 🚨 2026-08-10：更新配對庫 hidden select（保存部署揀咗嘅 symbol — 之後顯示返）
    const symSel = document.querySelector(`.ea-sym[data-ea="${eaName}"]`);
    if (symSel) symSel.value = symbol;
    // Step 3: HTTP API deploy (更可靠，唔靠 Socket.IO)
    await saveEAConfig();
    
    // Step 2: Check agent status
    const dashRes = await fetch('/api/dashboard');
    const dashData = await dashRes.json();
    if (dashData.status !== 'connected' && dashData.status !== 'running') {
        showLog('❌ Agent 離線，無法部署', 'log-error');
        hideControlModal();
        return;
    }
    
    // Step 3: HTTP API deploy (更可靠，唔靠 Socket.IO)
    try {
        const deployRes = await fetch('/api/deploy', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                ea_name: eaName,
                symbol: symbol,
                tf: tf,
                magic: magic,
                lot: lot
            })
        });
        const deployData = await deployRes.json();
        if (deployData.success) {
            // ⚠️ 手動首次部署（Controller）：警告視窗彈出（含指引 + 緊急停止）→
            // 用戶手動 double-click → 心跳出現 → 警告視窗自動關閉
            if (deployData.manual_action) {
                manualDeployActive = true;  // 鎖定 — pollAiControl 唔可以關閉
                const closeBtn = document.getElementById('aiControlCloseBtn');
                if (closeBtn) closeBtn.style.display = 'block';  // 顯示「關閉視窗」（完成/取消可以自己關）
                showControlModal('請手動完成首次部署（1 秒）', 'MT5 導航 → EA交易 → MT5Cloud → 雙擊 Controller。確定會自動撳！');
                showLog('📌 ' + deployData.message, 'log-info');
                // 心跳 poll：每 2 秒檢查 Controller 心跳 — running → 完成 + 關閉
                const manualStart = Date.now();
                const manualPoll = setInterval(async () => {
                    try {
                        const r = await fetch('/api/ea-config?t=' + Date.now());
                        const d = await r.json();
                        const st = (d.runtime_status || {})['Controller'];
                        if (st === 'running') {
                            clearInterval(manualPoll);
                            manualDeployActive = false;
                            showToast('✅ Controller 已運行 — 全自動化已啟動！', 'added');
                            hideControlModal();
                        } else if (Date.now() - manualStart > 300000) {
                            clearInterval(manualPoll);
                            manualDeployActive = false;
                            showToast('⏰ 5 分鐘未完成 — 請檢查 MT5 或再試', 'deleted');
                            hideControlModal();
                        }
                    } catch(e) { /* 網絡抖動 — 下個 tick 再試 */ }
                }, 2000);
                return;
            }
            showLog(`🚀 ${deployData.message}`, 'log-info');
            // 警告視窗要保持到部署真正完成（watcher auto_attach 完成先關）
            await waitDeployDone(eaName);
        } else {
            showLog('❌ 部署失敗: ' + (deployData.error || 'Unknown'), 'log-error');
        }
    } catch(e) {
        showLog('❌ 部署錯誤: ' + e.message, 'log-error');
    }
    // 唔即刻 hide — 由 pollAiControl 控制
}

// 等部署完成（poll activity log 睇 deploy_result 記錄）— 警告視窗做完動作先消失
async function waitDeployDone(eaName, maxWaitMs = 120000) {
    const start = Date.now();
    const deadline = start + maxWaitMs;
    while (Date.now() < deadline) {
        try {
            const res = await fetch('/api/activity?t=' + Date.now(), { signal: AbortSignal.timeout(5000) });
            const d = await res.json();
            const recent = (d.activities || []).slice(0, 15);
            const done = recent.find(a => a.action === 'deploy_result' && a.ea === eaName);
            if (done) {
                showLog(done.message.includes('成功') ? '✅ ' + done.message : '❌ ' + done.message,
                    done.message.includes('成功') ? 'log-success' : 'log-error');
                break;
            }
        } catch(e) { /* poll 失敗就繼續等 */ }
        await new Promise(r => setTimeout(r, 3000));
    }
    hideControlModal();
}

async function toggleBind() {
    const res = await fetch('/api/bind-account', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: 'bind'})
    });
    const d = await res.json();
    if (d.success) {
        showLog('✅ 已綁定 Account: ' + d.bound_account, 'log-success');
    } else {
        showLog('❌ ' + (d.error || '綁定失敗'), 'log-error');
    }
    loadDashboard();
}

async function uploadEA() {
    const input = document.getElementById('eaUploadInput');
    if (!input.files.length) return;
    const file = input.files[0];
    const form = new FormData();
    form.append('file', file);
    showControlModal('正在上傳 ' + file.name + '，請稍候...');
    try {
        const res = await fetch('/api/ea-library/upload', { method: 'POST', body: form });
        const data = await res.json();
        if (data.success) {
            // Double-check：compile 結果要話俾用戶知（唔可以假成功）
            if (data.compile_ok === false) {
                const shouldRetry = confirm('⚠️ ' + data.filename + ' 已上傳，但編譯失敗！\nMT5 可能未顯示 — 要立即重試編譯嗎？');
                if (shouldRetry) {
                    retryCompile(data.filename.replace(/\.(mq5|ex5)$/i, ''));
                }
            } else {
                alert('✅ ' + data.filename + ' 上傳成功！' + (data.installed_local ? '\n已自動安裝到本機 MT5 配對庫（已編譯 ✅）' : ''));
            }
            loadEALibrary();
            loadEAConfig();
            fetchEAInventory();
            if (data.installed_local) {
                setTimeout(() => { loadEAConfig(); fetchEAInventory(); }, 2000);
            }
        } else {
            alert('❌ ' + (data.error || 'Upload failed'));
        }
    } catch(e) {
        alert('❌ Upload error: ' + e.message);
    }
    // 唔即刻 hide — 由 pollAiControl 控制（watcher 可能仲 refresh Navigator）
    input.value = '';
}

async function devUploadEA() {
    const input = document.getElementById('devUploadInput');
    if (!input.files.length) return;
    const file = input.files[0];
    const form = new FormData();
    form.append('file', file);
    try {
        const res = await fetch('/api/ea-library/dev-upload', { method: 'POST', body: form });
        const data = await res.json();
        if (data.success) {
            alert(`✅ 社群 EA 上傳成功：${data.filename}`);
            loadEALibrary();
        } else {
            alert('❌ ' + (data.error || 'Upload failed'));
        }
    } catch(e) {
        alert('❌ Upload error: ' + e.message);
    }
    input.value = '';
}

// 顯示 dev upload button（如果係 dev 帳號）
(async function() {
    try {
        const res = await fetch('/api/dashboard');
        const d = await res.json();
        if (d.agent_id === 'DEV00001') {
            document.getElementById('devUploadBtn').style.display = 'inline-block';
        }
    } catch(e) {}
})();
