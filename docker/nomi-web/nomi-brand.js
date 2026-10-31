/* NOMI brand injector: replaces Plane brand marks in the DOM at runtime.
   Loaded from index.html after the app mounts (MutationObserver). */
(function () {
  "use strict";
  if (window.__nomiBrand) return;
  window.__nomiBrand = 2;

  // The theme is injected here as well as via index.html: a browser holding a
  // pre-rebrand HTML shell never sees that tag, so the stylesheet must be
  // applied from the running bundle too.
  if (!document.querySelector('link[href*="nomi-theme"]')) {
    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/assets-nomi/nomi-theme.css";
    (document.head || document.documentElement).appendChild(link);
  }

  var MARK_SVG =
    '<svg width="28" height="28" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="NOMI">' +
    '<rect width="32" height="32" rx="8" fill="currentColor"/><path d="M10 24V8h3.2l6.8 8.8V8H23v16h-3.2l-6.8-8.8V24H10Z" fill="#fff"/></svg>';

  function brandSpan() {
    var wrap = document.createElement("span");
    wrap.className = "nomi-lockup";
    wrap.style.cssText = "display:inline-flex;align-items:center;gap:8px;color:inherit;";
    var icon = document.createElement("span");
    icon.style.cssText =
      "width:28px;height:28px;display:inline-flex;align-items:center;justify-content:center;border-radius:8px;background:#171719;overflow:hidden;";
    var img = document.createElement("img");
    img.src = "/brand/ztrz-mark-white.png";
    img.alt = "";
    img.style.cssText = "width:72%;height:72%;object-fit:contain;";
    icon.appendChild(img);
    var text = document.createElement("span");
    text.style.cssText = "display:flex;flex-direction:column;line-height:1.1;";
    var name = document.createElement("strong");
    name.textContent = "NOMI";
    name.style.cssText = "font-size:14px;font-weight:700;";
    var sub = document.createElement("small");
    sub.textContent = "项目管理系统";
    sub.style.cssText = "font-size:9px;color:#919298;letter-spacing:.12em;";
    text.appendChild(name);
    text.appendChild(sub);
    wrap.appendChild(icon);
    wrap.appendChild(text);
    return wrap;
  }

  // Replace Plane lockup SVGs (the brand mark drawn inline by the bundle).
  // Keys are viewBoxes with whitespace stripped: "0 0 253 53" is the full
  // lockup, "0 0 146 44" the wordmark, "0 0 85 52" the mark alone.
  var LOCKUP_VIEWBOXES = { "0025353": 1, "0014644": 1, "008552": 1 };

  function replaceLockups() {
    if (!document.body) return;
    document.querySelectorAll("svg").forEach(function (svg) {
      try {
        var viewBox = (svg.getAttribute("viewBox") || "").replace(/\s+/g, "");
        if (!LOCKUP_VIEWBOXES[viewBox]) return;
        if (svg.__nomiReplaced) return;
        svg.__nomiReplaced = true;
        var span = brandSpan();
        var width = svg.getBoundingClientRect().width;
        if (width > 40) span.style.maxWidth = width + "px";
        svg.replaceWith(span);
      } catch (e) { /* ignore */ }
    });
  }

  // The auth screens end with a wall of third-party customer logos (Zerodha,
  // Sony, Dolby, Accenture). Drop the whole row, keep the tagline above it.
  function removeClientLogos() {
    if (!document.body) return;
    var rows = [];
    document.querySelectorAll("div[class*='h-7'][class*='flex-1']").forEach(function (cell) {
      if (cell.childElementCount !== 1) return;
      var child = cell.firstElementChild;
      if (!child || child.tagName.toLowerCase() !== "svg") return;
      if ((cell.textContent || "").trim()) return;
      var node = cell.parentElement;
      while (node && node !== document.body) {
        var cls = node.getAttribute("class") || "";
        if (cls.indexOf("flex-wrap") !== -1 && cls.indexOf("justify-center") !== -1) {
          if (!node.__nomiRemoved) { node.__nomiRemoved = true; rows.push(node); }
          return;
        }
        node = node.parentElement;
      }
      cell.style.display = "none";
    });
    rows.forEach(function (row) { row.remove(); });
  }

  // UI strings left untranslated by the upstream zh-CN locale files, mapped
  // at the DOM level so they render in Chinese without touching behaviour.
  var TEXT_MAP = {
    "Your profile": "我的资料",
    Developer: "开发者",
    "Work structure": "工作结构",
    Execution: "执行",
    Administration: "管理",
    "Completed on": "完成于",
    Forum: "论坛",
    "Go to workspace": "前往工作区",
    "Sign up": "注册",
    "Sign in": "登录",
    "Terms of Service": "服务条款",
    "Privacy Policy": "隐私政策",
    Community: "",
    More: "更多",
    Projects: "项目",
    Project: "项目",
    Drafts: "草稿",
    "Your work": "我的工作",
    Stickies: "便签",
    Workspace: "工作区",
    "New work item": "新建工作项",
    "Add project": "添加项目",
    "Create project": "创建项目",
    "Search commands...": "搜索命令…",
    Home: "首页",
  };

  // Relative timestamps ("about 2 hours ago") come from date-fns with its
  // English locale baked into the bundle. Translate the rendered text.
  var RELATIVE_PATTERNS = [
    [/^less than a minute ago$/, "刚刚"],
    [/^a few seconds ago$/, "刚刚"],
    [/^(\d+) seconds? ago$/, "$1 秒前"],
    [/^a minute ago$/, "1 分钟前"],
    [/^about a minute ago$/, "1 分钟前"],
    [/^(\d+) minutes? ago$/, "$1 分钟前"],
    [/^about (\d+) minutes? ago$/, "$1 分钟前"],
    [/^an hour ago$/, "1 小时前"],
    [/^about an hour ago$/, "1 小时前"],
    [/^(\d+) hours? ago$/, "$1 小时前"],
    [/^about (\d+) hours? ago$/, "$1 小时前"],
    [/^a day ago$/, "1 天前"],
    [/^yesterday$/, "昨天"],
    [/^(\d+) days? ago$/, "$1 天前"],
    [/^about a month ago$/, "1 个月前"],
    [/^(\d+) months? ago$/, "$1 个月前"],
    [/^about (\d+) months? ago$/, "$1 个月前"],
    [/^a year ago$/, "1 年前"],
    [/^about a year ago$/, "1 年前"],
    [/^(\d+) years? ago$/, "$1 年前"],
    [/^about (\d+) years? ago$/, "$1 年前"],
    [/^in a minute$/, "1 分钟后"],
    [/^in (\d+) minutes?$/, "$1 分钟后"],
    [/^in an hour$/, "1 小时后"],
    [/^in (\d+) hours?$/, "$1 小时后"],
    [/^in a day$/, "1 天后"],
    [/^in (\d+) days?$/, "$1 天后"],
  ];

  function translateTextNodes() {
    if (!document.body) return;
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    var node;
    var updates = [];
    while ((node = walker.nextNode())) {
      var raw = node.textContent;
      var trimmed = raw.trim();
      if (!trimmed) continue;
      if (Object.prototype.hasOwnProperty.call(TEXT_MAP, trimmed)) {
        updates.push([node, raw, trimmed, TEXT_MAP[trimmed]]);
        continue;
      }
      for (var i = 0; i < RELATIVE_PATTERNS.length; i++) {
        if (RELATIVE_PATTERNS[i][0].test(trimmed)) {
          updates.push([node, raw, trimmed, trimmed.replace(RELATIVE_PATTERNS[i][0], RELATIVE_PATTERNS[i][1])]);
          break;
        }
      }
    }
    updates.forEach(function (entry) {
      var node = entry[0], raw = entry[1], trimmed = entry[2], replacement = entry[3];
      if (!node.parentNode) return;
      if (replacement === "") {
        var parent = node.parentElement;
        if (parent && parent.children.length === 0) parent.remove();
        return;
      }
      node.textContent = raw.split(trimmed).join(replacement);
    });
  }

  // Boot splash: index.html carries a static NOMI lockup so the top-left is
  // branded on the very first paint, before any bundle runs. React's
  // hydration commit removes it long before route data resolves, so keep it
  // alive until real UI exists, then drop it.
  var BOOT_HTML =
    "<div id='nomi-boot' style='position:fixed;top:20px;left:24px;z-index:2147483647;display:flex;align-items:center;gap:8px;pointer-events:none'>" +
    "<span style='width:28px;height:28px;border-radius:8px;background:#171719 url(/brand/ztrz-mark-white.png) center/72% no-repeat;display:inline-block'></span>" +
    "<span style='font-size:14px;font-weight:700;letter-spacing:.02em'>NOMI</span></div>";

  function syncBootSplash() {
    if (!document.body) return;
    var b = document.getElementById("nomi-boot");
    var uiReady = document.querySelector(".nomi-lockup, nav, main, [data-discover], input");
    if (uiReady && b) b.remove();
    else if (!uiReady && !b) {
      var holder = document.createElement("div");
      holder.innerHTML = BOOT_HTML;
      document.body.appendChild(holder.firstChild);
    }
  }

  // The billing/pricing page is a paid-plan upsell with no local function.
  // Its nav entry is hidden by CSS; anyone landing on the URL directly (or
  // via a stale link) is bounced back to the workspace settings root.
  function redirectBilling() {
    if (/\/settings\/billing\/?$/.test(location.pathname)) {
      location.replace(location.pathname.replace(/\/billing\/?$/, "/") + location.search);
    }
  }

  // Remove upstream promotion affordances and stray brand text.
  function purgeUpstream() {
    if (!document.body) return;
    redirectBilling();
    document.querySelectorAll('a[href*="github.com"], a[href*="plane.so"], a[href="#nomi-hidden"]').forEach(function (a) {
      // Legal links (Terms / Privacy) point at plane.so but sit inside a
      // sentence — removing them mid-sentence breaks the copy. Unwrap them
      // instead so the label stays as plain text.
      var label = (a.textContent || "").trim();
      if (/^(服务条款|隐私政策|Terms of Service|Privacy Policy)$/.test(label)) {
        var parent = a.parentNode;
        while (a.firstChild) parent.insertBefore(a.firstChild, a);
        a.remove();
        parent.normalize();
        return;
      }
      a.remove();
    });
    document.querySelectorAll("button, span, div, a").forEach(function (el) {
      var t = (el.textContent || "").trim();
      if (
        t === "Community" ||
        t === "社区版" ||
        t === "Star us on GitHub" ||
        t === "在GitHub上为我们加星" ||
        t === "Join 10,000+ teams building with Plane" ||
        t === "Upgrade to Pro" ||
        t === "Upgrade to Business" ||
        t === "Upgrade to One" ||
        t === "升级到商业版" ||
        t === "升级到更高订阅" ||
        t === "联系销售" ||
        t === "Compare all features"
      ) {
        if (el.children.length === 0) el.remove();
      }
    });
    removeClientLogos();
    syncBootSplash();
  }

  // React Router v7 hydrates the WHOLE document and replaces <body>, which
  // orphans any observer attached to it — observe <html> instead, it is never
  // swapped out from under us.
  var observer = new MutationObserver(function () {
    try {
      replaceLockups();
      purgeUpstream();
      translateTextNodes();
    } catch (e) {
      window.__nomiError = "observer: " + (e && e.message);
    }
  });
  function start() {
    try {
      replaceLockups();
      purgeUpstream();
      translateTextNodes();
      // characterData matters: React updates timestamps by rewriting an
      // existing text node, which a childList-only observer never sees.
      observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
      // Belt and braces: late-rendered lists (recents, widgets) can appear
      // after the observer's first pass and some rows replace their subtree
      // wholesale. Sweep periodically for a while instead of trusting a
      // single mutation stream.
      var sweeps = 0;
      var timer = window.setInterval(function () {
        sweeps += 1;
        try {
          replaceLockups();
          translateTextNodes();
          purgeUpstream();
        } catch (e) {
          window.__nomiError = "sweep: " + (e && e.message);
        }
        if (sweeps >= 20) window.clearInterval(timer);
      }, 1500);
    } catch (e) {
      window.__nomiError = "start: " + (e && e.message);
    }
  }
  if (document.body) start();
  else document.addEventListener("DOMContentLoaded", start);
})();
