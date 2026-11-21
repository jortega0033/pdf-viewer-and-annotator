(function () {
  "use strict";

  var SCALE = 2; // backing-store oversampling on top of devicePixelRatio
  var $ = function (id) { return document.getElementById(id); };

  var els = {
    canvas: $("page-canvas"), text: $("page-text"),
    prev: $("prev-page"), next: $("next-page"), indicator: $("page-indicator"),
    title: $("doc-title"), meta: $("doc-meta"),
    noteTitle: $("note-title"), noteBody: $("note-body"),
    titleCount: $("title-count"), bodyCount: $("body-count"),
    save: $("save-note"), form: $("note-form"),
    status: $("status"), retry: $("retry"),
    conflict: $("conflict"), conflictTitle: $("conflict-title"),
    conflictBody: $("conflict-body"),
    keep: $("conflict-keep"), useSaved: $("conflict-use-saved")
  };

  var state = {
    doc: null,
    page: 1,
    note: null,        // last note object known from the server for state.page
    noteReady: false,  // inputs usable
    busy: false,
    conflict: null,    // current note from a 409, or null
    retryAction: null,
    noteToken: 0
  };

  // ---------- helpers ----------

  function setStatus(msg, kind) {
    els.status.textContent = msg;
    els.status.className = kind || "";
  }

  function showRetry(action) {
    state.retryAction = action;
    els.retry.hidden = !action;
  }

  function errMessage(data, fallback) {
    if (data && data.error && typeof data.error.message === "string") {
      return data.error.message;
    }
    return fallback;
  }

  function request(method, url, body) {
    var opts = { method: method, headers: { "Accept": "application/json" }, cache: "no-store" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(url, opts).then(function (res) {
      return res.text().then(function (txt) {
        var data = null;
        try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = null; }
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function isDirty() {
    if (!state.note || !state.noteReady) { return false; }
    return els.noteTitle.value !== state.note.title || els.noteBody.value !== state.note.body;
  }

  function updateCounters() {
    els.titleCount.textContent = els.noteTitle.value.length + " / 120";
    els.bodyCount.textContent = els.noteBody.value.length + " / 4000";
  }

  function updateControls() {
    var doc = state.doc;
    var locked = state.busy || !!state.conflict;
    els.prev.disabled = !doc || locked || state.page <= 1;
    els.next.disabled = !doc || locked || state.page >= doc.page_count;
    els.noteTitle.disabled = !doc || !state.noteReady || state.busy;
    els.noteBody.disabled = !doc || !state.noteReady || state.busy;
    els.save.disabled = !doc || !state.noteReady || locked;
  }

  // ---------- rendering ----------

  function toCss(c) {
    var a = Array.isArray(c) && c.length === 3 ? c : [0, 0, 0];
    var v = a.map(function (n) {
      n = Number(n) || 0;
      return Math.max(0, Math.min(255, Math.round(n * 255)));
    });
    return "rgb(" + v[0] + "," + v[1] + "," + v[2] + ")";
  }

  function drawPage(page) {
    var dpr = window.devicePixelRatio || 1;
    var cv = els.canvas;
    cv.width = Math.round(page.width * dpr * SCALE);
    cv.height = Math.round(page.height * dpr * SCALE);
    var ctx = cv.getContext("2d");
    if (!ctx) { return; }
    ctx.setTransform(dpr * SCALE, 0, 0, dpr * SCALE, 0, 0);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, page.width, page.height);
    ctx.textBaseline = "alphabetic";
    page.ops.forEach(function (op) {
      var y;
      if (op.op === "rect") {
        y = page.height - op.y - op.h;
        if (op.fill) {
          ctx.fillStyle = toCss(op.fill);
          ctx.fillRect(op.x, y, op.w, op.h);
        }
        if (op.stroke) {
          ctx.strokeStyle = toCss(op.stroke);
          ctx.lineWidth = op.line_width || 1;
          ctx.strokeRect(op.x, y, op.w, op.h);
        }
      } else if (op.op === "text") {
        ctx.fillStyle = toCss(op.fill);
        ctx.font = op.size + 'px Helvetica, Arial, "Liberation Sans", sans-serif';
        ctx.fillText(op.text, op.x, page.height - op.y);
      }
    });
  }

  function describePage(page) {
    els.text.textContent = "";
    page.ops.forEach(function (op) {
      var li = document.createElement("li");
      if (op.op === "text") {
        li.textContent = "Text: " + op.text;
      } else if (op.op === "rect") {
        var kind = op.fill && op.stroke ? "filled and outlined" : (op.fill ? "filled" : "outlined");
        li.textContent = "Rectangle " + op.w + " by " + op.h + " at " + op.x + ", " + op.y + " (" + kind + ")";
      } else {
        return;
      }
      els.text.appendChild(li);
    });
    if (!els.text.firstChild) {
      var empty = document.createElement("li");
      empty.textContent = "This page is empty.";
      els.text.appendChild(empty);
    }
  }

  function renderPage() {
    var doc = state.doc;
    var page = doc.pages[state.page - 1];
    drawPage(page);
    describePage(page);
    var label = "Page " + state.page + " of " + doc.page_count;
    els.canvas.setAttribute("aria-label", label + " preview");
    els.indicator.textContent = label;
    updateControls();
  }

  // ---------- notes ----------

  function setNote(note) {
    state.note = note;
    els.noteTitle.value = note.title;
    els.noteBody.value = note.body;
    updateCounters();
  }

  function loadNote(page) {
    var token = ++state.noteToken;
    state.noteReady = false;
    state.busy = true;
    updateControls();
    setStatus("Loading...");
    showRetry(null);
    return request("GET", "/api/v1/notes/" + page).then(function (r) {
      if (token !== state.noteToken) { return false; }
      state.busy = false;
      if (r.ok && r.data) {
        state.noteReady = true;
        setNote(r.data);
        setStatus("Loaded", "ok");
        updateControls();
        return true;
      }
      setStatus(errMessage(r.data, "Could not load the note (HTTP " + r.status + "). Check the server and retry."), "error");
      showRetry(function () { return loadNote(page); });
      updateControls();
      return false;
    }, function () {
      if (token !== state.noteToken) { return false; }
      state.busy = false;
      setStatus("Network error while loading the note. Check that the server is running, then retry.", "error");
      showRetry(function () { return loadNote(page); });
      updateControls();
      return false;
    });
  }

  function hideConflict() {
    state.conflict = null;
    els.conflict.hidden = true;
    els.conflictTitle.textContent = "";
    els.conflictBody.textContent = "";
  }

  function showConflict(current) {
    state.conflict = current;
    els.conflictTitle.textContent = current.title || "(empty)";
    els.conflictBody.textContent = current.body || "(empty)";
    els.conflict.hidden = false;
    setStatus("Save blocked: this note was changed elsewhere. Choose how to continue.", "error");
    updateControls();
    els.keep.focus();
  }

  // Resolves true on success. baseRevision optional override.
  function save(baseRevision) {
    if (state.busy || !state.noteReady || !state.note) { return Promise.resolve(false); }
    var sent = { title: els.noteTitle.value, body: els.noteBody.value };
    var page = state.page;
    var base = typeof baseRevision === "number" ? baseRevision : state.note.revision;
    state.busy = true;
    showRetry(null);
    updateControls();
    setStatus("Saving...");

    function fail(msg, retryable) {
      state.busy = false;
      setStatus(msg, "error");
      showRetry(retryable ? function () { return save(baseRevision); } : null);
      updateControls();
      return false;
    }

    return request("PUT", "/api/v1/notes/" + page,
      { title: sent.title, body: sent.body, base_revision: base }).then(function (r) {
      if (r.ok && r.data) {
        state.busy = false;
        hideConflict();
        state.note = r.data;
        updateControls();
        if (els.noteTitle.value === sent.title && els.noteBody.value === sent.body) {
          setStatus("Saved revision " + r.data.revision, "ok");
        } else {
          setStatus("Saved revision " + r.data.revision + ". Unsaved changes", "dirty");
        }
        return true;
      }
      if (r.status === 409 && r.data && r.data.current) {
        state.busy = false;
        showConflict(r.data.current);
        return false;
      }
      if (r.status >= 500 || !r.data) {
        return fail(errMessage(r.data, "Server error (HTTP " + r.status + "). Your text is kept. Retry in a moment."), true);
      }
      return fail(errMessage(r.data, "Could not save (HTTP " + r.status + "). Your text is kept."), false);
    }, function () {
      return fail("Network error. Your text is kept. Check that the server is running, then retry.", true);
    });
  }

  function goToPage(p) {
    var doc = state.doc;
    if (!doc || state.busy || state.conflict || p < 1 || p > doc.page_count || p === state.page) {
      return Promise.resolve();
    }
    var ready = isDirty() ? save() : Promise.resolve(true);
    return ready.then(function (ok) {
      if (!ok) { return; }
      state.page = p;
      renderPage();
      return loadNote(p);
    });
  }

  // ---------- events ----------

  function onInput() {
    updateCounters();
    if (isDirty()) {
      setStatus("Unsaved changes", "dirty");
    }
  }

  els.noteTitle.addEventListener("input", onInput);
  els.noteBody.addEventListener("input", onInput);

  els.form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!els.save.disabled) { save(); }
  });

  els.form.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
      e.preventDefault();
      if (!els.save.disabled) { save(); }
    }
  });

  els.prev.addEventListener("click", function () { goToPage(state.page - 1); });
  els.next.addEventListener("click", function () { goToPage(state.page + 1); });

  els.retry.addEventListener("click", function () {
    var action = state.retryAction;
    if (action) { action(); }
  });

  els.keep.addEventListener("click", function () {
    if (!state.conflict) { return; }
    var rev = state.conflict.revision;
    // Allow the save call to proceed while conflict panel is open.
    var cur = state.conflict;
    state.conflict = null;
    save(rev).then(function (ok) {
      if (!ok && !state.conflict) {
        state.conflict = cur; // keep panel usable after a non-conflict failure
        updateControls();
      }
      if (ok) { els.noteTitle.focus(); }
    });
  });

  els.useSaved.addEventListener("click", function () {
    if (!state.conflict) { return; }
    var cur = state.conflict;
    hideConflict();
    setNote(cur);
    setStatus("Showing saved revision " + cur.revision, "ok");
    updateControls();
    els.noteTitle.focus();
  });

  window.addEventListener("beforeunload", function (e) {
    if (isDirty()) {
      e.preventDefault();
      e.returnValue = "";
    }
  });

  // ---------- startup ----------

  function loadDocument() {
    setStatus("Loading...");
    showRetry(null);
    request("GET", "/api/v1/document").then(function (r) {
      if (!r.ok || !r.data || !Array.isArray(r.data.pages) || !r.data.pages.length) {
        setStatus(errMessage(r.data, "Could not load the document (HTTP " + r.status + ")."), "error");
        updateControls();
        return;
      }
      var d = r.data;
      state.doc = d;
      els.title.textContent = d.title;
      els.meta.textContent = d.size_bytes + " bytes, SHA-256 " + String(d.sha256).slice(0, 12);
      state.page = 1;
      renderPage();
      loadNote(1);
    }, function () {
      setStatus("Network error while loading the document. Check that the server is running, then reload.", "error");
      showRetry(loadDocument);
      updateControls();
    });
  }

  updateCounters();
  updateControls();
  loadDocument();
})();
