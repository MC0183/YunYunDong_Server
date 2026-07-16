/* ===== State ===== */
let tasks = [];
let currentFilter = 'all';
let deleteTarget = null;
let selectedSid = null;
let _sidGroups = {};
let _currentUser = null;

/* ===== Auth ===== */
function getToken() { return localStorage.getItem('task_token'); }
function setToken(t) { if (t) localStorage.setItem('task_token', t); else localStorage.removeItem('task_token'); }
function isLoggedIn() { return !!getToken(); }
function getApiUrl(path) { return (window.API_BASE || '') + path; }

async function apiFetch(url, opts = {}) {
  const token = getToken();
  const headers = opts.headers || {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!headers['Content-Type'] && opts.body && typeof opts.body === 'string') {
    headers['Content-Type'] = 'application/json';
  }
  opts.headers = headers;
  const r = await window._nativeFetch(getApiUrl(url), opts);
  window._apiRemember();
  if (r.status === 401) {
    setToken(null); showLogin(); throw new Error('未登录');
  }
  return r;
}
window._nativeFetch = window.fetch;

async function doLogin() {
  const user = document.getElementById('loginUser').value.trim();
  const pass = document.getElementById('loginPass').value.trim();
  const errEl = document.getElementById('loginError');
  const btn = document.getElementById('loginBtn');
  if (!user || !pass) { errEl.textContent = '请输入用户名和密码'; return; }
  btn.disabled = true; btn.textContent = '登录中...'; errEl.textContent = '';
  try {
    const r = await window._nativeFetch(getApiUrl('/api/auth/login'), {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username: user, password: pass})
    });
    const d = await r.json();
    if (r.ok) {
      setToken(d.token);
      _currentUser = d.user;
      window._apiOnLoginSuccess();
      hideLogin();
      await init();
    } else {
      errEl.textContent = d.error || '登录失败';
    }
  } catch(e) {
    errEl.textContent = '网络错误: ' + e.message;
  } finally {
    btn.disabled = false; btn.textContent = '登 录';
  }
}

async function doLogout() {
  try { await apiFetch('/api/auth/logout', {method: 'POST'}); } catch(e) {}
  setToken(null);
  _currentUser = null;
  showLogin();
}

function showLogin() {
  document.getElementById('loginPage').classList.remove('hidden');
  document.getElementById('mainContent').innerHTML = '';
}

function hideLogin() {
  document.getElementById('loginPage').classList.add('hidden');
}

async function loadUser() {
  if (!isLoggedIn()) { showLogin(); return null; }
  try {
    const r = await apiFetch('/api/auth/me');
    _currentUser = await r.json();
    return _currentUser;
  } catch(e) {
    showLogin(); return null;
  }
}

/* ===== Router ===== */
function navigate(page) {
  document.querySelectorAll('.nav-link').forEach(a => {
    a.classList.toggle('active', a.dataset.page === page);
  });
  selectedSid = null;
  switch (page) {
    case 'overview': renderOverview(); break;
    case 'tasks': renderTasksPage(); break;
    case 'logs': renderLogsPage(); break;
    case 'requests': renderRequestsPage(); break;
    case 'messages': renderMessagesPage(); break;
    case 'audit': renderAuditPage(); break;
    case 'contacts': renderContactsPage(); break;
  }
}

window.addEventListener('hashchange', () => {
  const page = location.hash.slice(1) || 'overview';
  navigate(page);
});

/* ===== Init ===== */
async function init() {
  // 管理员显示删除申请导航，普通用户显示消息导航
  const navReq = document.getElementById('navRequests');
  if (navReq) navReq.style.display = _currentUser?.role === 'admin' ? '' : 'none';
  const navMsg = document.getElementById('navMessages');
  if (navMsg) navMsg.style.display = _currentUser?.role !== 'admin' ? '' : 'none';
  const navContact = document.getElementById('navContacts');
  if (navContact) navContact.style.display = _currentUser?.role === 'admin' ? '' : 'none';
  // 操作日志仅管理员可见
  document.querySelectorAll('.nav-link[data-page="audit"]').forEach(el => {
    el.style.display = _currentUser?.role === 'admin' ? '' : 'none';
  });

  // 显示用户信息
  const navLinks = document.getElementById('navLinks');
  const existing = navLinks.parentElement.querySelector('.nav-user');
  if (existing) existing.remove();
  const div = document.createElement('div'); div.className = 'nav-user';
  div.innerHTML = `
    <span class="nav-role-badge">${_currentUser?.role === 'admin' ? '管理员' : '用户'}</span>
    <span class="nav-username">${esc(_currentUser?.username||'')}</span>
    <button class="btn btn-sm" onclick="showContactModal()" title="联系方式">📞</button>
    <button class="btn btn-sm" onclick="showChangePwdModal()" title="修改密码">🔑</button>
    <button class="btn btn-sm" onclick="doLogout()" title="退出">🚪</button>
  `;
  navLinks.parentElement.appendChild(div);

  await loadData();
  const page = location.hash.slice(1) || 'overview';
  navigate(page);
}

async function loadData() {
  try {
    const [tr, sr] = await Promise.all([
      apiFetch('/api/tasks').then(r => r.json()),
      apiFetch('/api/stats').then(r => r.json()),
    ]);
    tasks = tr.tasks || [];
    window._cachedStats = sr;
  } catch (e) {
    if (e.message !== '未登录') showToast('加载数据失败', 'error');
  }
}

// 页面加载时检查登录状态
(async function boot() {
  const token = getToken();
  if (token) {
    const u = await loadUser();
    if (u) { hideLogin(); await init(); }
  } else {
    showLogin();
  }
})();

/* ================================================================
   Page: Overview
   ================================================================ */
async function renderOverview() {
  const el = document.getElementById('mainContent');
  const s = window._cachedStats || await apiFetch('/api/stats').then(r => r.json());
  const ok = s.total_success || 0;
  const fail = s.total_fail || 0;
  const rate = (ok + fail) > 0 ? ((ok / (ok + fail)) * 100).toFixed(1) : '—';
  const maxItems = tasks.filter(t => t.enabled !== false).slice(0, 8);

  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2>📊 概览</h2>
        <div class="page-subtitle">步道乐跑 · 自动化调度系统</div>
      </div>
    </div>
    <div class="stats-grid">
      <div class="stat-card stat-tasks"><div class="stat-value">${s.total_tasks}</div><div class="stat-label">总任务</div></div>
      <div class="stat-card stat-enabled"><div class="stat-value">${s.enabled}</div><div class="stat-label">已启用</div></div>
      <div class="stat-card stat-disabled"><div class="stat-value">${s.disabled}</div><div class="stat-label">已禁用</div></div>
      <div class="stat-card stat-success"><div class="stat-value">${ok}</div><div class="stat-label">本地成功</div></div>
      <div class="stat-card stat-fail"><div class="stat-value">${fail}</div><div class="stat-label">本地失败</div></div>
      <div class="stat-card stat-rate"><div class="stat-value">${rate}%</div><div class="stat-label">成功率</div></div>
      <div class="stat-card stat-server"><div class="stat-value">${s.server_total_runs}</div><div class="stat-label">服务器总次数</div></div>
      <div class="stat-card stat-km"><div class="stat-value">${s.server_total_km}</div><div class="stat-label">总里程(km)</div></div>
    </div>
    <div class="overview-bottom">
      ${_currentUser?.role === 'admin' ? `
      <div class="overview-card">
        <h3>已启用任务</h3>
        ${maxItems.length ? maxItems.map(t => `
          <div class="task-mini-item">
            <span><span class="mini-id">${esc(t.id)}</span> · <span class="mini-school">${esc(t.school)}</span></span>
            <span>${t.run_stats?.success||0}/${t.run_stats?.total||0}</span>
          </div>
        `).join('') : '<div style="color:#666;font-size:13px;">暂无任务</div>'}
      </div>
      <div class="overview-card">
        <h3>学校分布</h3>
        ${(s.schools||[]).map(sc => {
          const cnt = tasks.filter(t => t.school === sc).length;
          return `<div class="task-mini-item"><span>${esc(sc)}</span><span>${cnt} 个任务</span></div>`;
        }).join('') || '<div style="color:#666;font-size:13px;">暂无数据</div>'}
      </div>` : ''}
    </div>
  `;
}

/* ================================================================
   Page: Tasks
   ================================================================ */
async function renderTasksPage() {
  const el = document.getElementById('mainContent');
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2>📋 任务管理</h2>
        <div class="page-subtitle">管理所有跑步任务 · 共 ${tasks.length} 条</div>
      </div>
      <div class="page-actions">
        <button class="btn btn-primary" onclick="fetchAllStats()" id="fetchAllBtn">
          <span class="icon">📡</span> 拉取全部
        </button>
        <button class="btn" onclick="showAddModal()">
          <span class="icon">➕</span> 添加任务
        </button>
      </div>
    </div>
    <div class="toolbar">
      ${_currentUser?.role === 'admin' ? `
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" placeholder="搜索任务 ID、学校、设备..." oninput="renderTaskTable()">
      </div>
      <div class="filter-tabs">
        <button class="filter-btn active" data-f="all" onclick="setFilter('all')">全部</button>
        <button class="filter-btn" data-f="enabled" onclick="setFilter('enabled')">启用</button>
        <button class="filter-btn" data-f="disabled" onclick="setFilter('disabled')">禁用</button>
        <button class="filter-btn" data-f="error" onclick="setFilter('error')">异常</button>
      </div>` : '<div></div>'}
    </div>
    <div class="table-wrapper">
      <table><thead><tr>
        <th>任务 ID</th><th>学校</th><th>设备</th><th>计划时间</th>
        <th>状态</th><th>本地执行</th><th>服务器记录</th><th>最后运行</th><th>操作</th>
      </tr></thead><tbody id="taskBody"></tbody></table>
      <div class="table-footer" id="tableFooter"></div>
    </div>
  `;
  renderTaskTable();
}

function renderTaskTable() {
  const q = (document.getElementById('searchInput')?.value || '').toLowerCase();
  const filtered = tasks.filter(t => {
    if (currentFilter === 'enabled' && t.enabled === false) return false;
    if (currentFilter === 'disabled' && t.enabled !== false) return false;
    if (currentFilter === 'error') {
      const ls = (t.run_stats?.last_status || '').toString();
      if (!['1','2','3'].includes(ls) && !(parseInt(ls) > 0)) return false;
    }
    if (q && ![t.id, t.school, t.device_name].some(v => (v||'').toLowerCase().includes(q))) return false;
    return true;
  });

  const tbody = document.getElementById('taskBody');
  const footer = document.getElementById('tableFooter');
  if (!tbody) return;
  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:40px;color:#666;">暂无匹配任务</td></tr>`;
    if (footer) footer.textContent = '';
    return;
  }
  tbody.innerHTML = filtered.map(t => {
    const s = t.run_stats || {};
    const enabled = t.enabled !== false;
    const st = enabled ? '<span class="status-badge status-enabled">● 启用</span>' : '<span class="status-badge status-disabled">● 禁用</span>';
    const sv = s.server_total;
    const svKm = s.server_total_km;
    let svStr = '<span style="color:#666;">—</span>', svExtra = '';
    if (sv !== undefined && sv !== null) {
      svStr = sv + ' 次';
      if (svKm) svExtra = `<div style="font-size:11px;color:#666;">${svKm} km</div>`;
    }
    const ls = (s.last_status || '').toString();
    const icons = {'0':'✅ 成功','1':'❌ Token失效','2':'⚠️ 不合格','3':'🔴 代码错误'};
    const lIcon = icons[ls] || (ls ? '❓ '+ls : '—');
    const tid = t.id || t.username;
    return `<tr>
      <td><div class="task-id">${esc(tid)}</div><div class="school-name">${esc(t.password)}</div></td>
      <td><span class="school-name">${esc(t.school)}</span></td>
      <td><span class="school-name">${esc(t.device_name)}</span></td>
      <td>${esc(t.start_time||'—')}</td>
      <td>${st}</td>
      <td><strong>${s.success||0}/${s.total||0}</strong></td>
      <td>${svStr}${svExtra}</td>
      <td>${s.last_run||'—'}<br><span style="font-size:11px;color:#666;">${lIcon}</span></td>
      <td><div class="actions-cell">
        ${enabled ? `<button class="btn btn-sm" onclick="tog('${tid}',false)" title="禁用">⏸</button>`
                  : `<button class="btn btn-sm" onclick="tog('${tid}',true)" title="启用">▶</button>`}
        <button class="btn btn-sm" onclick="fetchOne('${tid}')" title="拉取服务器数据">📡</button>
        <button class="btn btn-sm" onclick="editTime('${tid}')" title="修改时间">⏰</button>
        ${_currentUser?.role === 'admin'
          ? `<button class="btn btn-sm" onclick="showDel('${tid}')" title="删除">🗑</button>`
          : `<button class="btn btn-sm" onclick="showDeleteRequest('${tid}')" title="申请删除">📋</button>`}
        <button class="btn btn-sm" onclick="openHistory('${tid}')" title="历史记录">📜</button>
        <button class="btn btn-sm" onclick="showYunPwdModal('${tid}')" title="修改云运动密码">🏃</button>
      </div></td>
    </tr>`;
  }).join('');
  if (footer) footer.textContent = `共 ${filtered.length} 条任务（总 ${tasks.length} 条）`;
}

// Task actions (exposed globally for onclick)
function setFilter(f) { currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.toggle('active', b.dataset.f === f));
  renderTaskTable();
}
async function tog(id, en) {
  const r = await apiFetch(`/api/tasks/${enc(id)}`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:en})});
  const d = await r.json();
  if (r.ok) {
    await refresh(); showToast(`已${en?'启用':'禁用'}`, 'success');
  } else if (d.disabled_by_admin) {
    showToast('⛔ 管理员已禁用此账号，请向管理员咨询具体原因','error');
  } else {
    showToast(d.error || '操作失败','error');
  }
}
async function fetchOne(id) {
  const r = await apiFetch(`/api/tasks/${enc(id)}/fetch`, {method:'POST'});
  const d = await r.json();
  if (d.success) showToast(`${id}: 服务器 ${d.total_runs} 次, ${d.total_km} km`,'success');
  else showToast(`${id}: ${d.error||'失败'}`,'error');
  await refresh();
}
async function fetchAllStats() {
  const btn = document.getElementById('fetchAllBtn'); if (!btn) return;
  btn.disabled = true; btn.innerHTML = '⏳ 拉取中...';
  try {
    const r = await apiFetch('/api/tasks/fetch-all', {method:'POST'});
    const d = await r.json();
    const results = d.results || [];
    showToast(`拉取完成: ${results.filter(r=>r.status==='ok').length} 成功`, results.some(r=>r.status!=='ok') ? 'info' : 'success');
    await refresh();
  } catch(e) { showToast('批量拉取失败','error'); }
  finally { btn.disabled = false; btn.innerHTML = '<span class="icon">📡</span> 拉取全部'; }
}
function editTime(id) {
  const t = tasks.find(x => (x.id||x.username) === id);
  const nt = prompt(`修改 ${id} 的计划时间 (HH:MM):`, t?.start_time||'06:00');
  if (nt && /^\d{2}:\d{2}$/.test(nt.trim())) doPut(id, {start_time: nt.trim()});
  else if (nt !== null) showToast('格式错误，请用 HH:MM','error');
}
async function doPut(id, body) {
  await apiFetch(`/api/tasks/${enc(id)}`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  await refresh(); showToast('已更新','success');
}
function showDel(id) { deleteTarget = id; document.getElementById('deleteTaskName').textContent = id; document.getElementById('deleteModal').classList.add('open'); }
function closeDeleteModal() { deleteTarget = null; document.getElementById('deleteModal').classList.remove('open'); }
async function doDelete() {
  if (!deleteTarget) return;
  await apiFetch(`/api/tasks/${enc(deleteTarget)}`, {method:'DELETE'});
  showToast('已删除','success'); closeDeleteModal(); await refresh();
}

/* ===== Delete Request (普通用户) ===== */
let _delReqTaskId = null;
function showDeleteRequest(tid) {
  _delReqTaskId = tid;
  document.getElementById('delReqTaskName').textContent = tid;
  document.getElementById('delReqReason').value = '';
  document.getElementById('deleteRequestModal').classList.add('open');
}
function closeDeleteRequestModal() {
  _delReqTaskId = null;
  document.getElementById('deleteRequestModal').classList.remove('open');
}
async function submitDeleteRequest() {
  if (!_delReqTaskId) return;
  const reason = document.getElementById('delReqReason').value.trim() || '未填写原因';
  try {
    const r = await apiFetch(`/api/tasks/${enc(_delReqTaskId)}/delete-request`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({reason})
    });
    const d = await r.json();
    if (r.ok) {
      showToast(d.message || '申请已提交','success');
      closeDeleteRequestModal();
      await refresh();
    } else {
      showToast(d.error || '提交失败','error');
    }
  } catch(e) {
    showToast('提交失败: '+e.message,'error');
  }
}

/* ===== Messages Page (合并操作日志 + 申请结果) ===== */
async function renderMessagesPage() {
  const el = document.getElementById('mainContent');
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2>📬 消息</h2>
        <div class="page-subtitle">与你相关的所有操作记录</div>
      </div>
    </div>
    <div id="messagesList"><div style="text-align:center;padding:60px;color:#666;">加载中...</div></div>
  `;
  try {
    const [auditR, reqR] = await Promise.all([
      apiFetch('/api/audit-logs').then(r => r.json()),
      apiFetch('/api/delete-requests/my').then(r => r.json()),
    ]);
    const logs = (auditR.logs || []).map(l => ({
      time: l.time,
      type: 'audit',
      icon: l.action === '登录' ? '🔑' : l.action === '修改密码' ? '🔑' : l.action === '管理员操作' ? '⚙️' : l.action === '提交删除申请' ? '📋' : l.action === '修改任务' ? '✏️' : l.action === '拉取服务器数据' ? '📡' : l.action === '批量拉取' ? '📡' : l.action === '重置统计' ? '🔄' : l.action === '导入历史记录' ? '📥' : '📝',
      title: l.action,
      detail: l.detail || '',
    }));
    const reqs = (reqR.requests || []).map(r => ({
      time: r.created_at,
      type: 'request',
      icon: r.status === 'pending' ? '⏳' : r.status === 'approved' ? '✅' : '❌',
      title: r.status === 'pending' ? '删除申请待审核' : r.status === 'approved' ? '删除申请已通过' : '删除申请已拒绝',
      detail: `任务 ${r.task_id}: ${r.reason}${r.status !== 'pending' ? ` → ${r.admin_response}` : ''}`,
    }));
    const merged = [...logs, ...reqs].sort((a, b) => b.time.localeCompare(a.time));
    const list = document.getElementById('messagesList');
    if (!merged.length) {
      list.innerHTML = '<div style="text-align:center;padding:60px;color:#666;">暂无消息</div>';
      return;
    }
    list.innerHTML = merged.map(item => `
      <div style="background:#1a1a2e;border:1px solid rgba(255,255,255,0.06);border-radius:12px;padding:14px 16px;margin-bottom:6px;display:flex;align-items:flex-start;gap:10px;">
        <span style="font-size:16px;flex-shrink:0;margin-top:1px;">${item.icon}</span>
        <div style="flex:1;min-width:0;">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <strong style="font-size:13px;">${esc(item.title)}</strong>
            <span style="font-size:11px;color:#666;white-space:nowrap;">${esc(item.time)}</span>
          </div>
          ${item.detail ? `<div style="font-size:12px;color:#aaa;margin-top:2px;">${esc(item.detail)}</div>` : ''}
        </div>
      </div>
    `).join('');
  } catch(e) {
    document.getElementById('messagesList').innerHTML = '<div style="text-align:center;padding:60px;color:#ef4444;">加载失败</div>';
  }
}

/* ===== Audit Log Page ===== */
async function renderAuditPage() {
  const el = document.getElementById('mainContent');
  const isAdmin = _currentUser?.role === 'admin';
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2>📝 操作日志</h2>
        <div class="page-subtitle">${isAdmin ? '所有用户的操作记录' : '我的操作记录'}</div>
      </div>
    </div>
    <div class="table-wrapper">
      <table><thead><tr>
        <th>时间</th>
        ${isAdmin ? '<th>用户</th>' : ''}
        <th>操作</th>
        <th>详情</th>
      </tr></thead><tbody id="auditBody"></tbody></table>
      <div class="table-footer" id="auditFooter"></div>
    </div>
  `;
  try {
    const r = await apiFetch('/api/audit-logs');
    const d = await r.json();
    const logs = d.logs || [];
    const tbody = document.getElementById('auditBody');
    const footer = document.getElementById('auditFooter');
    if (!logs.length) {
      tbody.innerHTML = '<tr><td colspan="'+(isAdmin?4:3)+'" style="text-align:center;padding:40px;color:#666;">暂无操作记录</td></tr>';
      if (footer) footer.textContent = '';
      return;
    }
    tbody.innerHTML = logs.map(l => `
      <tr>
        <td style="font-size:12px;color:#666;white-space:nowrap;">${esc(l.time)}</td>
        ${isAdmin ? `<td><strong>${esc(l.username)}</strong></td>` : ''}
        <td><span class="audit-action">${esc(l.action)}</span></td>
        <td style="color:#aaa;font-size:12px;">${esc(l.detail||'')}</td>
      </tr>
    `).join('');
    if (footer) footer.textContent = `共 ${logs.length} 条记录`;
  } catch(e) {
    document.getElementById('auditBody').innerHTML = '<tr><td colspan="'+(isAdmin?4:3)+'" style="text-align:center;padding:40px;color:#ef4444;">加载失败</td></tr>';
  }
}

/* ===== Delete Requests Page (管理员) ===== */
async function renderRequestsPage() {
  const el = document.getElementById('mainContent');
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2>📋 删除申请</h2>
        <div class="page-subtitle">审批用户提交的删除请求</div>
      </div>
    </div>
    <div class="table-wrapper">
      <table><thead><tr>
        <th>申请ID</th><th>任务</th><th>申请人</th><th>原因</th><th>时间</th><th>状态</th><th>操作</th>
      </tr></thead><tbody id="reqBody"></tbody></table>
      <div class="table-footer" id="reqFooter"></div>
    </div>
  `;
  try {
    const r = await apiFetch('/api/delete-requests');
    const d = await r.json();
    const reqs = d.requests || [];
    const tbody = document.getElementById('reqBody');
    const footer = document.getElementById('reqFooter');
    if (!reqs.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:40px;color:#666;">暂无删除申请</td></tr>';
      if (footer) footer.textContent = '';
      return;
    }
    tbody.innerHTML = reqs.map(req => `
      <tr>
        <td><span style="font-size:12px;color:#666;">${esc(req.id.slice(0,8))}</span></td>
        <td><strong>${esc(req.task_id)}</strong></td>
        <td>${esc(req.username)}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(req.reason)}</td>
        <td style="font-size:12px;color:#666;">${esc(req.created_at)}</td>
        <td>${req.status === 'pending' ? '<span class="status-badge" style="background:rgba(245,158,11,0.1);color:#f59e0b;">⏳ 待审核</span>'
            : req.status === 'approved' ? '<span class="status-badge" style="background:rgba(34,197,94,0.1);color:#22c55e;">✅ 已通过</span>'
            : '<span class="status-badge" style="background:rgba(239,68,68,0.1);color:#ef4444;">❌ 已拒绝</span>'}</td>
        <td>
          ${req.status === 'pending' ? `
            <div class="actions-cell">
              <button class="btn btn-sm" style="background:rgba(34,197,94,0.1);color:#22c55e;border-color:rgba(34,197,94,0.2);" onclick="approveRequest('${req.id}')">✓ 通过</button>
              <button class="btn btn-sm" style="background:rgba(239,68,68,0.1);color:#ef4444;border-color:rgba(239,68,68,0.2);" onclick="rejectRequest('${req.id}')">✗ 拒绝</button>
            </div>` : `<span style="font-size:12px;color:#666;">${esc(req.admin_response)}</span>`}
        </td>
      </tr>
    `).join('');
    if (footer) footer.textContent = `共 ${reqs.length} 条申请`;
  } catch(e) {
    document.getElementById('reqBody').innerHTML = `<tr><td colspan="7" style="text-align:center;padding:40px;color:#ef4444;">加载失败: ${e.message}</td></tr>`;
  }
}

async function approveRequest(reqId) {
  try {
    const r = await apiFetch(`/api/delete-requests/${enc(reqId)}/approve`, {method:'POST'});
    const d = await r.json();
    showToast(d.message || '已批准','success');
    await renderRequestsPage();
    await loadData();
  } catch(e) { showToast('操作失败','error'); }
}

async function rejectRequest(reqId) {
  const reason = prompt('请输入拒绝原因:');
  if (reason === null) return;
  try {
    const r = await apiFetch(`/api/delete-requests/${enc(reqId)}/reject`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({reason: reason.trim() || '管理员拒绝了该申请'})
    });
    const d = await r.json();
    showToast(d.message || '已拒绝','info');
    await renderRequestsPage();
  } catch(e) { showToast('操作失败','error'); }
}

function closeModal(e) { if (e.target.classList.contains('modal-overlay')) e.target.classList.remove('open'); }

/* ===== Change Password ===== */
function showChangePwdModal() {
  document.getElementById('newPwdInput').value = '';
  document.getElementById('changePwdModal').classList.add('open');
}
function closeChangePwdModal() {
  document.getElementById('changePwdModal').classList.remove('open');
}
async function doChangePassword() {
  const newPwd = document.getElementById('newPwdInput').value.trim();
  if (!newPwd || newPwd.length < 4) { showToast('密码至少4位','error'); return; }
  try {
    const r = await apiFetch('/api/auth/change-password', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({new_password: newPwd})
    });
    const d = await r.json();
    if (r.ok) {
      showToast('✅ 网页登录密码已修改','success');
      closeChangePwdModal();
    } else {
      showToast('❌ ' + (d.error||'修改失败'),'error');
    }
  } catch(e) {
    showToast('❌ 请求失败: '+e.message,'error');
  }
}

/* ===== Contact Modal ===== */
const CONTACT_LABELS = {qq:'QQ', wechat:'微信', email:'邮箱', phone:'电话'};
const MAX_CONTACT = 5;
let _contactData = null; // {mine: {qq:[],...}, admin: {qq:[],...}}

async function showContactModal() {
  try {
    const r = await apiFetch('/api/contact');
    _contactData = await r.json();
    renderContactModal();
    document.getElementById('contactModal').classList.add('open');
  } catch(e) { showToast('加载失败','error'); }
}

function renderContactModal() {
  const body = document.getElementById('contactModalBody');
  const mine = _contactData?.mine || {};
  const admin = _contactData?.admin || {};
  let html = '<h4 style="margin-bottom:12px;">我的联系方式</h4>';
  for (const [key, label] of Object.entries(CONTACT_LABELS)) {
    const items = mine[key] || [];
    html += `<div style="margin-bottom:10px;">
      <div style="font-size:13px;font-weight:500;color:#aaa;margin-bottom:4px;">${label}</div>`;
    // 显示已有条目 + 空位（最多5个）
    for (let i = 0; i < MAX_CONTACT; i++) {
      const val = items[i] || '';
      html += `<input type="text" class="input contact-input" data-type="${key}" data-idx="${i}" value="${esc(val)}" placeholder="${label}${i+1}" style="margin-bottom:4px;width:100%;">`;
    }
    html += '</div>';
  }
  // 管理员联系方式（只读 — 非管理员时显示）
  const isAdminUser = _currentUser?.role === 'admin';
  if (!isAdminUser) {
    const hasAdmin = Object.values(admin).some(a => a && a.length);
    if (hasAdmin) {
      html += '<h4 style="margin:16px 0 12px;">管理员联系方式</h4>';
      for (const [key, label] of Object.entries(CONTACT_LABELS)) {
        const items = admin[key] || [];
        if (items.length) {
          html += `<div style="margin-bottom:8px;font-size:13px;"><span style="color:#aaa;">${label}: </span>${items.map(v => `<span style="background:rgba(99,102,241,0.1);padding:2px 8px;border-radius:4px;margin-right:4px;">${esc(v)}</span>`).join('')}</div>`;
        }
      }
    }
  }
  body.innerHTML = html;
}

async function saveContact() {
  const data = {};
  for (const key of Object.keys(CONTACT_LABELS)) {
    const vals = [];
    for (let i = 0; i < MAX_CONTACT; i++) {
      const inp = document.querySelector(`.contact-input[data-type="${key}"][data-idx="${i}"]`);
      if (inp) {
        const v = inp.value.trim();
        if (v) vals.push(v);
      }
    }
    data[key] = vals;
  }
  try {
    const r = await apiFetch('/api/contact', {
      method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)
    });
    const d = await r.json();
    if (r.ok) { showToast('✅ 已保存','success'); closeContactModal(); }
    else { showToast('❌ ' + (d.error||'保存失败'),'error'); }
  } catch(e) { showToast('❌ 保存失败','error'); }
}
function closeContactModal() {
  document.getElementById('contactModal').classList.remove('open');
}

/* ===== Contacts Page (管理员) ===== */
async function renderContactsPage() {
  const el = document.getElementById('mainContent');
  el.innerHTML = `
    <div class="page-header">
      <div>
        <h2>📞 用户联系方式</h2>
        <div class="page-subtitle">所有用户的联系方式（仅管理员可见）</div>
      </div>
    </div>
    <div class="table-wrapper">
      <table><thead><tr>
        <th>学号</th><th>QQ</th><th>微信</th><th>邮箱</th><th>电话</th>
      </tr></thead><tbody id="contactBody"></tbody></table>
      <div class="table-footer" id="contactFooter"></div>
    </div>
  `;
  try {
    const r = await apiFetch('/api/contacts');
    const d = await r.json();
    const contacts = d.contacts || [];
    const tbody = document.getElementById('contactBody');
    const footer = document.getElementById('contactFooter');
    if (!contacts.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:40px;color:#666;">暂无联系方式</td></tr>';
      if (footer) footer.textContent = '';
      return;
    }
    tbody.innerHTML = contacts.map(c => `
      <tr>
        <td><strong>${esc(c.username)}</strong>${c.role === 'admin' ? ' <span style="font-size:10px;color:#818cf8;">管理员</span>' : ''}</td>
        <td>${fmtContactArr(c.qq)}</td>
        <td>${fmtContactArr(c.wechat)}</td>
        <td>${fmtContactArr(c.email)}</td>
        <td>${fmtContactArr(c.phone)}</td>
      </tr>
    `).join('');
    if (footer) footer.textContent = `共 ${contacts.length} 人`;
  } catch(e) {
    document.getElementById('contactBody').innerHTML = '<tr><td colspan="4" style="text-align:center;padding:40px;color:#ef4444;">加载失败</td></tr>';
  }
}

/* ===== Yun Password Modal ===== */
let _yunPwdTaskId = null;
function showYunPwdModal(tid) {
  _yunPwdTaskId = tid;
  document.getElementById('yunPwdInput').value = '';
  document.getElementById('yunPwdModal').classList.add('open');
}
function closeYunPwdModal() {
  _yunPwdTaskId = null;
  document.getElementById('yunPwdModal').classList.remove('open');
}
async function doChangeYunPassword() {
  const pwd = document.getElementById('yunPwdInput').value.trim();
  if (!pwd || pwd.length < 4) { showToast('密码至少4位','error'); return; }
  try {
    const r = await apiFetch(`/api/tasks/${enc(_yunPwdTaskId)}/yun-password`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({yun_password: pwd})
    });
    const d = await r.json();
    if (r.ok) { showToast('✅ 云运动密码已更新，已同步到任务配置','success'); closeYunPwdModal(); }
    else { showToast('❌ ' + (d.error||'修改失败'),'error'); }
  } catch(e) { showToast('❌ 请求失败','error'); }
}

function showAddModal() { document.getElementById('addModal').classList.add('open'); }
function closeAddModal() { document.getElementById('addModal').classList.remove('open'); }
async function doAddTask() {
  try {
  const user = document.getElementById('addUser').value.trim();
  const pass = document.getElementById('addPass').value.trim();
  const school = document.getElementById('addSchool').value.trim();
  if (!user || !pass) { showToast('用户名和密码不能为空','error'); return; }
  const addBtn = document.querySelector('#addModal .btn-primary');
  const origText = addBtn ? addBtn.textContent : '';
  if (addBtn) { addBtn.disabled = true; addBtn.textContent = '验证中...'; }
  try {
    const r = await apiFetch('/api/tasks', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:user,password:pass,school})});
    const d = await r.json();
    if (r.ok) { showToast(d.message||'添加成功','success'); closeAddModal(); document.getElementById('addUser').value=''; document.getElementById('addPass').value=''; await refresh(); }
    else showToast(d.error||'添加失败','error');
  } catch(e) { showToast('请求失败: '+e.message,'error'); }
  finally { if (addBtn) { addBtn.disabled = false; addBtn.textContent = origText; } }
  } catch(e) { showToast('操作失败: '+e.message,'error'); }
}
function closeModal(e) { if (e.target.classList.contains('modal-overlay')) e.target.classList.remove('open'); }

/* ================================================================
   Page: Logs
   ================================================================ */
async function renderLogsPage() {
  const el = document.getElementById('mainContent');
  const isAdmin = _currentUser?.role === 'admin';
  if (isAdmin) {
    // 管理员：学号列表 + 文件列表
    el.innerHTML = `
      <div class="page-header">
        <div>
          <h2>📁 运行日志</h2>
          <div class="page-subtitle">按学号分类查看运行日志</div>
        </div>
      </div>
      <div class="toolbar" style="margin-bottom:16px;">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input type="text" id="logSearchInput" placeholder="搜索学号..." oninput="filterSidList()" style="font-family:inherit;">
        </div>
      </div>
      <div class="logs-layout">
        <div class="logs-sidebar" id="logSidebar">
          <h4>学号列表</h4>
          <div id="sidList"><div style="color:#666;font-size:13px;padding:8px;">加载中...</div></div>
        </div>
        <div class="logs-content" id="logContent">
          <div class="logs-empty">👈 选择一个学号查看日志</div>
        </div>
      </div>
    `;
    await loadSidList();
    if (selectedSid) loadSidLogs(selectedSid);
  } else {
    // 普通用户：直接展示自己的日志文件列表
    const sid = _currentUser?.username;
    el.innerHTML = `
      <div class="page-header">
        <div>
          <h2>📁 运行日志</h2>
          <div class="page-subtitle">${esc(sid)} 的运行日志</div>
        </div>
      </div>
      <div class="logs-content" id="logContent">
        <div class="logs-empty">加载中...</div>
      </div>
    `;
    if (sid) loadSidLogs(sid);
  }
}

async function loadSidList() {
  try {
    const r = await apiFetch('/api/logs');
    const d = await r.json();
    _sidGroups = d.groups || {};
    renderSidList('');
  } catch(e) { showToast('加载日志列表失败','error'); }
}

function renderSidList(filter) {
  const list = document.getElementById('sidList');
  if (!list) return;
  const sids = Object.keys(_sidGroups).filter(s => !filter || s.includes(filter));
  if (!sids.length) { list.innerHTML = '<div style="color:#666;font-size:13px;padding:8px;">暂无匹配学号</div>'; return; }
  list.innerHTML = sids.map(sid => `
    <div class="sid-item ${selectedSid === sid ? 'active' : ''}" onclick="selectSid('${sid}')">
      <span>${esc(sid)}</span>
      <span class="sid-count">${_sidGroups[sid].length}</span>
    </div>
  `).join('');
}

function filterSidList() {
  const q = (document.getElementById('logSearchInput')?.value || '').trim().toUpperCase();
  renderSidList(q);
}

async function selectSid(sid) {
  selectedSid = sid;
  document.querySelectorAll('.sid-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.sid-item').forEach(el => {
    if (el.textContent.trim().startsWith(sid)) el.classList.add('active');
  });
  await loadSidLogs(sid);
}

async function loadSidLogs(sid) {
  const content = document.getElementById('logContent');
  if (!content) return;
  content.innerHTML = '<div class="logs-empty">加载中...</div>';
  try {
    const r = await apiFetch(`/api/logs/${enc(sid)}`);
    const d = await r.json();
    const logs = d.logs || [];
    if (!logs.length) { content.innerHTML = '<div class="logs-empty">该学号暂无日志</div>'; return; }
    content.innerHTML = `<h4>📄 ${esc(sid)} 的日志文件（点击查看详情）</h4>
      ${logs.map((l, i) => `
        <div class="log-file-item" onclick="openLogFile('${enc(sid)}','${enc(l.name)}')">
          <span class="log-file-name">📄 ${esc(l.name)}</span>
          <span class="log-file-meta">${l.mtime} · ${fmtSize(l.size)}</span>
        </div>
      `).join('')}`;
  } catch(e) {
    content.innerHTML = '<div class="logs-empty">加载失败</div>';
    showToast('加载日志失败','error');
  }
}

async function openLogFile(sid, name) {
  const title = document.getElementById('logModalTitle');
  const body = document.getElementById('logModalBody');
  title.textContent = `📄 ${esc(decodeURIComponent(name))}`;
  body.textContent = '加载中...';
  document.getElementById('logModal').classList.add('open');
  try {
    const r = await apiFetch(`/api/logs/${enc(sid)}`);
    const d = await r.json();
    const log = (d.logs || []).find(l => l.name === decodeURIComponent(name));
    body.textContent = log ? log.content : '未找到该日志文件';
  } catch(e) {
    body.textContent = '加载失败: ' + e.message;
  }
}

function closeLogModal() {
  document.getElementById('logModal').classList.remove('open');
}

/* ================================================================
   History Modal
   ================================================================ */
let _historyTaskId = null;

async function openHistory(tid) {
  _historyTaskId = tid;
  document.getElementById('historyTitle').textContent = `📜 ${tid} 历史记录`;
  document.getElementById('historyBody').innerHTML = '<div class="logs-empty">正在获取学期列表...</div>';
  document.getElementById('historyModal').classList.add('open');
  try {
    const r = await apiFetch(`/api/tasks/${enc(tid)}/history/terms`, {method:'POST'});
    const d = await r.json();
    const terms = d.terms || [];
    if (!terms.length) { document.getElementById('historyBody').innerHTML = '<div class="logs-empty">未获取到学期数据</div>'; return; }
    document.getElementById('historyBody').innerHTML = `
      <p style="color:#aaa;font-size:13px;margin-bottom:12px;">选择学期查看跑步记录：</p>
      ${terms.map((t, i) => `
        <div class="history-item" onclick="selectTerm('${tid}','${t.value}')">
          <span class="history-item-title">📅 ${esc(t.key)}</span>
          <span style="font-size:12px;color:#666;">${esc(t.sjd)}</span>
        </div>
      `).join('')}
    `;
  } catch(e) {
    document.getElementById('historyBody').innerHTML = `<div class="logs-empty">获取失败: ${e.message}</div>`;
  }
}

async function selectTerm(tid, tableName) {
  document.getElementById('historyBody').innerHTML = '<div class="logs-empty">正在获取跑步记录...</div>';
  try {
    const r = await apiFetch(`/api/tasks/${enc(tid)}/history/runs`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tableName})});
    const d = await r.json();
    const runs = d.runs || [];
    if (!runs.length) { document.getElementById('historyBody').innerHTML = '<div class="logs-empty">该学期无跑步记录</div>'; return; }
    document.getElementById('historyBody').innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
        <button class="btn btn-sm" onclick="openHistory('${tid}')">← 返回学期列表</button>
        <span style="color:#aaa;font-size:13px;">共 ${runs.length} 条记录</span>
      </div>
      ${runs.map(r => `
        <div class="history-item" onclick="selectRun('${tid}','${tableName}','${r.id}')">
          <span class="history-item-title">🏃 ${esc(r.endTime)}</span>
          <span style="font-size:12px;color:#666;">${esc(r.recordMileage)} 公里</span>
        </div>
      `).join('')}
    `;
  } catch(e) {
    document.getElementById('historyBody').innerHTML = `<div class="logs-empty">获取失败: ${e.message}</div>`;
  }
}

async function selectRun(tid, tableName, runId) {
  document.getElementById('historyBody').innerHTML = '<div class="logs-empty">正在获取详细记录...</div>';
  try {
    const r = await apiFetch(`/api/tasks/${enc(tid)}/history/preview`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tableName,runId})});
    const d = await r.json();
    if (d.success) {
      const s = d.summary || {};
      document.getElementById('historyBody').innerHTML = `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
          <button class="btn btn-sm" onclick="selectTerm('${tid}','${tableName}')">← 返回记录列表</button>
        </div>
        <div style="background:#0a0a14;border-radius:8px;padding:16px;margin-bottom:16px;">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
            <div><span style="color:#666;font-size:12px;">开始时间</span><br>${esc(s.recordStartTime)}</div>
            <div><span style="color:#666;font-size:12px;">结束时间</span><br>${esc(s.recordEndTime)}</div>
            <div><span style="color:#666;font-size:12px;">距离</span><br><strong style="color:#22c55e;">${esc(s.recordMileage)} 公里</strong></div>
            <div><span style="color:#666;font-size:12px;">配速</span><br>${esc(s.recodePace)} /公里</div>
            <div><span style="color:#666;font-size:12px;">步频</span><br>${esc(s.recodeCadence)}</div>
            <div><span style="color:#666;font-size:12px;">用时</span><br>${esc(s.duration)} 秒</div>
            <div><span style="color:#666;font-size:12px;">轨迹点数</span><br>${esc(s.points)} 个</div>
          </div>
        </div>
        <button class="btn btn-primary" onclick="doSaveRun('${tid}','${tableName}','${runId}')" id="saveRunBtn">
          💾 保存到 tasks_fch
        </button>
        <span id="saveResult" style="margin-left:8px;font-size:13px;"></span>
      `;
    } else {
      document.getElementById('historyBody').innerHTML = `<div class="logs-empty">获取失败: ${esc(d.error||'未知错误')}</div>`;
    }
  } catch(e) {
    document.getElementById('historyBody').innerHTML = `<div class="logs-empty">请求失败: ${e.message}</div>`;
  }
}

async function doSaveRun(tid, tableName, runId) {
  const btn = document.getElementById('saveRunBtn');
  const result = document.getElementById('saveResult');
  btn.disabled = true; btn.textContent = '⏳ 保存中...'; result.textContent = '';
  try {
    const r = await apiFetch(`/api/tasks/${enc(tid)}/history/save`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tableName,runId})});
    const d = await r.json();
    if (d.saved) {
      result.innerHTML = '✅ 已保存';
      btn.textContent = '✅ 已保存';
      btn.style.background = '#22c55e';
      btn.style.borderColor = '#22c55e';
    } else {
      result.style.color = '#ef4444';
      result.textContent = '❌ ' + (d.error||'保存失败');
      btn.disabled = false; btn.innerHTML = '💾 重试保存';
    }
  } catch(e) {
    result.style.color = '#ef4444';
    result.textContent = '❌ ' + e.message;
    btn.disabled = false; btn.innerHTML = '💾 重试保存';
  }
}

function closeHistoryModal() {
  document.getElementById('historyModal').classList.remove('open');
  _historyTaskId = null;
}

/* ===== Utils ===== */
function esc(s) { if (s==null) return ''; const d = document.createElement('div'); d.textContent = String(s); return d.innerHTML; }
function enc(s) { return encodeURIComponent(s); }
function fmtSize(b) { if (b<1024) return b+'B'; if (b<1048576) return (b/1024).toFixed(1)+'KB'; return (b/1048576).toFixed(1)+'MB'; }
function fmtContactArr(arr) {
  if (!arr || !arr.length) return '<span style="color:#666;">—</span>';
  return arr.map(v => `<span style="display:inline-block;background:rgba(99,102,241,0.1);padding:2px 8px;border-radius:4px;margin:2px;">${esc(v)}</span>`).join('');
}

function showToast(msg, type='info') {
  const c = document.querySelector('.toast-container') || (()=>{const c=document.createElement('div');c.className='toast-container';document.body.appendChild(c);return c;})();
  const el = document.createElement('div'); el.className=`toast toast-${type}`; el.textContent=msg;
  c.appendChild(el);
  setTimeout(()=>{el.style.opacity='0';el.style.transition='opacity 0.3s';setTimeout(()=>el.remove(),300);},3000);
}

async function refresh() {
  await loadData();
  const page = location.hash.slice(1) || 'overview';
  navigate(page);
}
