/* Charity Impact Media: search, share, compare, embed, chart tooltips, opt-in analytics.
   No dependencies, no cookies. Data comes from static JSON built with the site. */
(function () {
  "use strict";
  var BASE = document.body.getAttribute("data-base") || "";
  var PAGE = document.body.getAttribute("data-page") || "";
  var V = (document.querySelector('script[src*="app.js"]') || { src: "" }).src.split("v=")[1] || "";

  // ---- analytics (GoatCounter, only when configured; skipped under DNT / GPC) ----
  var gcMeta = document.querySelector('meta[name="cim-gc"]');
  var dnt = navigator.doNotTrack === "1" || window.doNotTrack === "1" || navigator.globalPrivacyControl === true;
  if (gcMeta && !dnt) {
    var s = document.createElement("script");
    s.async = true; s.src = "https://gc.zgo.at/count.js"; s.setAttribute("data-goatcounter", gcMeta.content);
    document.head.appendChild(s);
  }
  function ev(name) {
    try { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: "ev-" + name, title: name, event: true }); } catch (e) {}
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest("[data-ev]") : null;
    if (t) ev(t.getAttribute("data-ev"));
  });
  // Activation: the visitor reached the scorecard on a charity page.
  var score = document.getElementById("score");
  if (score && "IntersectionObserver" in window) {
    var seen = false;
    new IntersectionObserver(function (es) { es.forEach(function (x) { if (x.isIntersecting && !seen) { seen = true; ev("scorecard_seen"); } }); }, { threshold: 0.4 }).observe(score);
  }

  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function usd(v) {
    if (v == null) return "—";
    var a = Math.abs(v), s;
    if (a >= 1e10) s = "$" + (a / 1e9).toFixed(1) + "B"; else if (a >= 1e9) s = "$" + (a / 1e9).toFixed(2) + "B";
    else if (a >= 1e7) s = "$" + (a / 1e6).toFixed(0) + "M"; else if (a >= 1e6) s = "$" + (a / 1e6).toFixed(1) + "M";
    else if (a >= 1e5) s = "$" + (a / 1e3).toFixed(0) + "K"; else s = "$" + Math.round(a).toLocaleString("en-US");
    return (v < 0 ? "−" : "") + s;
  }
  function usdFull(v) { return v == null ? "—" : "$" + Math.round(v).toLocaleString("en-US"); }
  function pct(x, d) { return x == null ? "—" : (x * 100).toFixed(d == null ? 1 : d) + "%"; }
  function hundred(parts) {
    var tot = parts.reduce(function (a, b) { return a + (b > 0 ? b : 0); }, 0);
    if (tot <= 0) return parts.map(function () { return 0; });
    var raw = parts.map(function (p) { return (p > 0 ? p : 0) / tot * 10000; });
    var base = raw.map(Math.floor), rest = 10000 - base.reduce(function (a, b) { return a + b; }, 0);
    raw.map(function (r, i) { return [r - base[i], i]; }).sort(function (a, b) { return b[0] - a[0]; }).slice(0, rest).forEach(function (x) { base[x[1]]++; });
    return base;
  }
  function cents(c) { return "$" + (c / 100).toFixed(2); }
  function charityUrl(ein) { return BASE + "/charity/" + ein + "/"; }
  function getJSON(url) { return fetch(url, { credentials: "omit" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }

  // ---- search ----
  var index = null, loading = null;
  function loadIndex() {
    if (index) return Promise.resolve(index);
    if (!loading) loading = getJSON(BASE + "/assets/search.json?v=" + V).then(function (d) { index = d.map(function (r) { r.k = norm(r[0] + " " + (r[4] || "")); return r; }); return index; });
    return loading;
  }
  function norm(s) { return String(s).normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/['’.]/g, "").replace(/&/g, " and ").replace(/\bsaint\b/g, "st").replace(/[^a-z0-9]+/g, " ").trim(); }
  function find(q) {
    var digits = q.replace(/[^0-9]/g, "");
    if (digits.length >= 7 && digits.length === q.replace(/[\s-]/g, "").length) {
      return index.filter(function (r) { return r[1].indexOf(digits) === 0; }).slice(0, 8);
    }
    var toks = norm(q).replace(/\bsaint\b/g, "st").split(" ").filter(Boolean);
    if (!toks.length) return [];
    var out = [];
    for (var i = 0; i < index.length && out.length < 8; i++) {
      var k = " " + index[i].k;
      var ok = true;
      for (var j = 0; j < toks.length; j++) { if (k.indexOf(" " + toks[j]) < 0) { ok = false; break; } }
      if (ok) out.push(index[i]);
    }
    return out;
  }
  function wireSearch(input) {
    var list = input.parentNode.querySelector("ul");
    var mode = input.getAttribute("data-mode") || "go";
    var sel = -1, items = [];
    function render() {
      list.innerHTML = "";
      items.forEach(function (r, i) {
        var li = el("li"), a = el("a");
        a.href = charityUrl(r[1]); a.setAttribute("role", "option"); a.setAttribute("aria-selected", i === sel ? "true" : "false");
        a.appendChild(document.createTextNode(r[0]));
        a.appendChild(el("small", null, (r[2] ? r[2] + ", " : "") + r[3] + " · EIN " + r[1].slice(0, 2) + "-" + r[1].slice(2)));
        a.addEventListener("click", function (e) { if (mode === "compare") { e.preventDefault(); addCompare(r[1]); input.value = ""; list.hidden = true; } else ev("search_open"); });
        li.appendChild(a); list.appendChild(li);
      });
      if (!items.length && input.value.trim().length > 1) { var li = el("li"); li.appendChild(el("small", null, "No covered charity matches. The site covers 501(c)(3) charities with $10M+ in revenue.")); list.appendChild(li); }
      list.hidden = !input.value.trim();
    }
    input.addEventListener("focus", function () { loadIndex(); });
    input.addEventListener("input", function () {
      var q = input.value.trim();
      if (!q) { items = []; render(); return; }
      loadIndex().then(function () { items = find(q); sel = -1; render(); });
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { sel = Math.min(items.length - 1, sel + 1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { sel = Math.max(-1, sel - 1); render(); e.preventDefault(); }
      else if (e.key === "Escape") { list.hidden = true; }
      else if (e.key === "Enter") {
        var r = items[sel >= 0 ? sel : 0];
        if (r) { e.preventDefault(); if (mode === "compare") { addCompare(r[1]); input.value = ""; list.hidden = true; } else { ev("search_open"); location.href = charityUrl(r[1]); } }
      }
    });
    document.addEventListener("click", function (e) { if (!input.parentNode.contains(e.target)) list.hidden = true; });
    if (input.hasAttribute("data-autofocus")) {
      var q = new URLSearchParams(location.search).get("q");
      if (q) { input.value = q; input.dispatchEvent(new Event("input")); }
      input.focus();
    }
  }
  Array.prototype.forEach.call(document.querySelectorAll("[data-search]"), wireSearch);

  // ---- share ----
  Array.prototype.forEach.call(document.querySelectorAll("[data-share]"), function (box) {
    var url = box.getAttribute("data-url"), text = box.getAttribute("data-text"), title = box.getAttribute("data-title");
    var enc = encodeURIComponent;
    var links = {
      x: "https://twitter.com/intent/tweet?text=" + enc(text) + "&url=" + enc(url),
      linkedin: "https://www.linkedin.com/sharing/share-offsite/?url=" + enc(url),
      facebook: "https://www.facebook.com/sharer/sharer.php?u=" + enc(url),
      email: "mailto:?subject=" + enc(title) + "&body=" + enc(text + "\n\n" + url)
    };
    Array.prototype.forEach.call(box.querySelectorAll("[data-act]"), function (b) {
      var act = b.getAttribute("data-act");
      if (links[act]) { b.href = links[act]; if (act !== "email") b.target = "_blank"; b.addEventListener("click", function () { ev("share_" + act); }); }
      if (act === "copy") b.addEventListener("click", function () { copy(url, b); ev("share_copy"); });
      if (act === "share") b.addEventListener("click", function () {
        if (navigator.share) navigator.share({ title: title, text: text, url: url }).then(function () { ev("share_native"); }).catch(function () {});
        else { copy(url, b); ev("share_copy"); }
      });
    });
  });
  function copy(s, b) {
    var done = function () { var t = b.textContent; b.textContent = "Copied"; setTimeout(function () { b.textContent = t; }, 1600); };
    if (navigator.clipboard) navigator.clipboard.writeText(s).then(done, function () {}); else { var ta = el("textarea"); ta.value = s; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); done(); } catch (e) {} ta.remove(); }
  }
  Array.prototype.forEach.call(document.querySelectorAll("textarea.embed"), function (t) {
    t.addEventListener("focus", function () { t.select(); });
    t.addEventListener("copy", function () { ev("embed_copy"); });
  });

  // ---- chart hover: crosshair + one tooltip with every series ----
  Array.prototype.forEach.call(document.querySelectorAll(".chart svg"), function (svg) {
    var box = svg.parentNode, xh = svg.querySelector(".xh"), tip = null;
    function show(r) {
      var x = r.getAttribute("data-x");
      xh.setAttribute("x1", x); xh.setAttribute("x2", x); xh.style.visibility = "visible";
      if (!tip) { tip = el("div", "tip"); tip.setAttribute("role", "status"); box.appendChild(tip); }
      tip.innerHTML = "";
      tip.appendChild(el("b", null, r.getAttribute("data-t")));
      var vals = (r.getAttribute("data-v") || "|").split("|");
      [["Revenue", 0, "c1"], ["Expenses", 1, "c2"]].forEach(function (s) {
        var row = el("div"), k = el("span"), i = el("i", s[2]);
        k.appendChild(i); k.appendChild(document.createTextNode(" " + s[0]));
        row.appendChild(el("strong", null, vals[s[1]])); row.appendChild(k); tip.appendChild(row);
      });
      var vb = svg.viewBox.baseVal, scale = svg.getBoundingClientRect().width / vb.width;
      var left = Math.min(box.clientWidth - 170, Math.max(0, x * scale + 12));
      tip.style.left = left + "px"; tip.style.top = "8px"; tip.hidden = false;
    }
    function hide() { xh.style.visibility = "hidden"; if (tip) tip.hidden = true; }
    Array.prototype.forEach.call(svg.querySelectorAll(".hit"), function (r) {
      r.addEventListener("pointerenter", function () { show(r); });
      r.addEventListener("focus", function () { show(r); });
      r.addEventListener("blur", hide);
    });
    svg.addEventListener("pointerleave", hide);
  });

  // ---- compare ----
  var cmpBox = document.querySelector("[data-compare]");
  var cmp = [];
  var MEASURES = [
    ["Latest filing", function (d) { return d.fy; }],
    ["Revenue", function (d) { return usd(d.rev); }], ["Expenses", function (d) { return usd(d.exp); }],
    ["Of $100 spent: programs", function (d) { return d.m.program_share == null ? "—" : cents(hundred([d.m.program_share, d.m.mgmt_share, d.m.fund_share])[0]); }],
    ["Of $100 spent: management", function (d) { return d.m.program_share == null ? "—" : cents(hundred([d.m.program_share, d.m.mgmt_share, d.m.fund_share])[1]); }],
    ["Of $100 spent: fundraising", function (d) { return d.m.program_share == null ? "—" : cents(hundred([d.m.program_share, d.m.mgmt_share, d.m.fund_share])[2]); }],
    ["Fundraising cost per $1 raised", function (d) { return d.m.cost_per_dollar == null ? "—" : "$" + d.m.cost_per_dollar.toFixed(2); }],
    ["Contributions share of revenue", function (d) { return pct(d.m.contrib_share); }],
    ["Government grants share", function (d) { return pct(d.m.gov_share); }],
    ["Highest reported compensation", function (d) { return usdFull(d.m.top_comp); }],
    ["People paid over $100,000", function (d) { return d.m.n_over_100k == null ? "—" : d.m.n_over_100k.toLocaleString("en-US"); }],
    ["Net assets, months of expenses", function (d) { return d.m.months_net_assets == null ? "—" : d.m.months_net_assets.toFixed(1); }]
  ];
  function drawCompare() {
    if (!cmpBox) return;
    cmpBox.innerHTML = "";
    if (!cmp.length) { cmpBox.appendChild(el("p", "src", "Pick charities to compare.")); return; }
    var t = el("table", "tbl cmp"), thead = el("thead"), hr = el("tr");
    hr.appendChild(el("th", null, "Measure"));
    cmp.forEach(function (d, i) {
      var th = el("th"), a = el("a", null, d.n); a.href = charityUrl(d.e); th.appendChild(a);
      var rm = el("button", "btn", "Remove"); rm.type = "button"; rm.style.marginTop = "6px"; rm.style.minHeight = "32px";
      rm.addEventListener("click", function () { cmp.splice(i, 1); sync(); });
      th.appendChild(el("br")); th.appendChild(rm); hr.appendChild(th);
    });
    thead.appendChild(hr); t.appendChild(thead);
    var tb = el("tbody");
    MEASURES.forEach(function (m) {
      var tr = el("tr"); tr.appendChild(el("td", null, m[0]));
      cmp.forEach(function (d) { tr.appendChild(el("td", "r", m[1](d))); });
      tb.appendChild(tr);
    });
    t.appendChild(tb); cmpBox.appendChild(t);
    cmpBox.appendChild(el("p", "src", "Each column is that charity's latest Form 990. Fiscal years can differ; see each charity page for sources."));
  }
  function sync() {
    var q = cmp.map(function (d) { return d.e; }).join(",");
    history.replaceState(null, "", location.pathname + (q ? "?e=" + q : ""));
    drawCompare();
  }
  function addCompare(ein) {
    if (cmp.some(function (d) { return d.e === ein; })) return;
    if (cmp.length >= 3) cmp.shift();
    getJSON(charityUrl(ein) + "data.json?v=" + V).then(function (d) { cmp.push(d); sync(); ev("compare_add"); }).catch(function () {});
  }
  if (cmpBox) {
    var initial = (new URLSearchParams(location.search).get("e") || "").split(",").filter(function (x) { return /^\d{9}$/.test(x); }).slice(0, 3);
    Promise.all(initial.map(function (e) { return getJSON(charityUrl(e) + "data.json?v=" + V).catch(function () { return null; }); }))
      .then(function (ds) { cmp = ds.filter(Boolean); drawCompare(); });
    var cc = document.querySelector('[data-act="copy-compare"]');
    if (cc) cc.addEventListener("click", function () { copy(location.href, cc); ev("compare_copy"); });
  }

  // ---- embed card ----
  var emb = document.querySelector("[data-embed]");
  if (emb) {
    var ein = (new URLSearchParams(location.search).get("ein") || "").replace(/[^0-9]/g, "");
    getJSON(charityUrl(ein) + "data.json?v=" + V).then(function (d) {
      emb.innerHTML = "";
      emb.appendChild(el("h1", null, d.n));
      emb.appendChild(el("p", "src", (d.c ? d.c + ", " : "") + d.s + " · Form 990, " + d.ph));
      if (d.m.program_share != null) {
        var c = hundred([d.m.program_share, d.m.mgmt_share, d.m.fund_share]);
        emb.appendChild(el("p", "hundred", "Of every $100 spent:"));
        var bar = el("div", "bar"); bar.setAttribute("role", "img");
        bar.setAttribute("aria-label", cents(c[0]) + " programs, " + cents(c[1]) + " management, " + cents(c[2]) + " fundraising");
        ["c1", "c2", "c3"].forEach(function (k, i) { if (c[i] > 0) { var sp = el("span", k); sp.style.width = (c[i] / 100) + "%"; bar.appendChild(sp); } });
        emb.appendChild(bar);
        var ul = el("ul", "legend");
        [["Programs", "c1"], ["Management & general", "c2"], ["Fundraising", "c3"]].forEach(function (x, i) {
          var li = el("li"); li.appendChild(el("i", x[1])); li.appendChild(el("span", null, x[0])); li.appendChild(el("b", null, cents(c[i]))); ul.appendChild(li);
        });
        emb.appendChild(ul);
      }
      var facts = el("p", "src", "Revenue " + usd(d.rev) + " · expenses " + usd(d.exp) + (d.m.top_comp ? " · highest reported pay " + usdFull(d.m.top_comp) : ""));
      facts.style.marginTop = "10px"; emb.appendChild(facts);
      var a = el("a", null, "Full breakdown and sources"); a.href = charityUrl(d.e); a.target = "_blank"; a.rel = "noopener";
      var p = el("p", "src"); p.appendChild(a); p.appendChild(document.createTextNode(" · Charity Impact Media")); emb.appendChild(p);
    }).catch(function () { emb.innerHTML = ""; emb.appendChild(el("p", "src", "This charity isn't covered.")); });
  }
})();
