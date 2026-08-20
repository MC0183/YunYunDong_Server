// 前端配置 — 纯前后端分离
// 同服务器时留空，独立部署时改为后端地址
// 也可通过 URL 参数 ?api=http://IP:PORT 首次配对
(function() {
  var STORAGE_KEY = 'task_api_base';

  // URL 参数
  var fromUrl = '';
  if (location.search) {
    var m = location.search.match(/[?&]api=([^&]+)/);
    if (m) fromUrl = decodeURIComponent(m[1]).replace(/\/+$/, '');
    if (fromUrl) {
      try { localStorage.setItem(STORAGE_KEY, fromUrl); } catch(e) {}
      // 去掉 URL 参数
      history.replaceState({}, '', location.pathname + location.hash);
    }
  }

  window.API_BASE = fromUrl || (function() {
    try { return localStorage.getItem(STORAGE_KEY) || ''; } catch(e) { return ''; }
  })();

  window.getApiUrl = function(path) {
    return (window.API_BASE || '') + path;
  };

  // 请求成功时记住后端地址
  window._apiRemember = function() {
    if (window.API_BASE) {
      try { localStorage.setItem(STORAGE_KEY, window.API_BASE); } catch(e) {}
    }
  };

  // 登录页 3 秒后显示配对提示
  window._apiNeedsConfig = false;
  setTimeout(function() {
    if (!window.API_BASE) {
      window._apiNeedsConfig = true;
    }
  }, 3000);
})();
