// 前端自动发现后端 — 同服务器时零配置，分离部署时自动记忆
// 也可通过 URL 参数 ?api=http://IP:PORT 临时指定后端
(function() {
  var STORAGE_KEY = 'task_api_base';

  // 1. URL 参数 ?api=...（临时覆盖，用于初始配对）
  var fromUrl = '';
  if (location.search) {
    var m = location.search.match(/[?&]api=([^&]+)/);
    if (m) fromUrl = decodeURIComponent(m[1]);
  }

  // 2. localStorage 中记住的上次成功连接的后端
  function stored() {
    try { return localStorage.getItem(STORAGE_KEY) || ''; } catch(e) { return ''; }
  }
  function remember(base) {
    try { if (base) localStorage.setItem(STORAGE_KEY, base); } catch(e) {}
  }

  window.API_BASE = fromUrl || stored() || '';

  // 构建完整 API URL
  window.getApiUrl = function(path) {
    return (window.API_BASE || '') + path;
  };

  // 请求成功时调用：记住当前后端
  window._apiRemember = function() {
    if (window.API_BASE) remember(window.API_BASE);
  };

  // 后端不可达时调用：尝试降级
  window._apiFallback = function() {
    // 如果配置了特定后端但连不上，尝试当前页面同源
    if (window.API_BASE && window.API_BASE !== location.origin) {
      console.warn('Backend unreachable, falling back to origin:', location.origin);
      window.API_BASE = location.origin;
    }
  };

  // 登录成功后持久化当前后端
  window._apiOnLoginSuccess = function() {
    var base = window.API_BASE || location.origin;
    remember(base);
  };
})();
