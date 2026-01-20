/* afr-panel.js
 * Amazon Face Recognition Panel (Gallery + ROI + Plates)
 * - Fix camera 403 by fetching camera frame with Authorization header and using blob URLs (no sign_path needed)
 * - Avoid constant full re-render while drawing/renaming ROI
 */

class AfrPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });

    // HA
    this._hass = null;

    // data
    this._facesIndex = null;
    this._gallery = null;
    this._plates = null; // {updated_at, items}
    this._scanCarsEnabled = false;

    // ui state
    this._error = null;
    this._loading = false;

    // upload
    this._uploadName = "";
    this._uploadFile = null;
    this._uploading = false;
    this._uploadError = null;
    this._uploadOk = null;

    // thumbnails (auth -> blob url)
    this._thumbUrls = new Map(); // image_id -> blobUrl
    this._thumbLoading = new Set();

    // tabs
    this._tab = "gallery"; // gallery | roi | plates

    // ROI state
    this._roi = { updated_at: null, by_camera: {} }; // {updated_at, by_camera:{[cameraEntityId]: ROI[]}}
    this._roiCamera = "";
    this._roiSelectedId = null;
    this._roiDrawing = null; // {x0,y0,x1,y1} in px (overlay coords)
    this._roiDrag = null; // {id, mode:'move'|'resize', startX,startY, ox,oy, ow,oh}
    this._roiImgBuster = Date.now();
    this._roiImgSrc = "";        // blob url
    this._roiImgObjectUrl = null; // keep to revoke
    this._roiInteracting = false; // true while drawing/dragging
    this._roiNameEditing = false; // true while typing in roi-name
    this._roiPendingUpdate = null; // stash WS updates while interacting

    // live updates
    this._unsubGallery = null;
    this._unsubPlates = null;
    this._unsubRoi = null;

    // plates inputs
    this._plateInput = "";
    this._plateNameInput = "";

    // render scheduling
    this._rendered = false;
    this._renderQueued = false;

    // i18n (panel-local)
    this._i18nLang = null;
    this._i18nDict = {};
    this._i18nLoading = null; // Promise

    // lifecycle
    this._connectedOnce = false;
    this._initialRefreshQueued = false;
    this._didInitialRefresh = false;
  }

  set hass(hass) {
    this._hass = hass;

    this._ensureI18n();

    // initial loads (only once)
    if (!this._facesIndex && !this._loading) this._loadFacesIndex();
    if (!this._gallery) this._loadGallery();
    if (!this._plates) this._loadPlates();
    if (!this._roi || !this._roi.updated_at) this._loadRoi();

    // subscriptions (only once)
    this._subscribeGallery();
    this._subscribePlates();
    this._subscribeRoi();

    if (!this._rendered) {
      this._rendered = true;
      this._scheduleRender();
    }

    // If the element is already connected, ensure we perform one deterministic
    // refresh after the first hass assignment. This fixes cases where the panel
    // renders before HA websocket/data is ready and the top cards stay empty
    // until a manual browser refresh.
    if (this.isConnected) this._queueInitialRefresh();
  }

  connectedCallback() {
    // HA can assign `hass` before the element is attached to the DOM.
    // We do one extra render + one deterministic refresh once connected.
    if (!this._connectedOnce) this._connectedOnce = true;
    this._scheduleRender();
    this._queueInitialRefresh();
  }


  /* ----------------------------- i18n (panel-local) ----------------------------- */

  _getLang() {
    const h = this._hass;
    const lang = h?.language || h?.locale?.language || (typeof navigator !== 'undefined' ? navigator.language : 'en');
    return String(lang || 'en');
  }

  async _fetchI18nFile(lang) {
    // Files are served by HA static mount: /amazon_face_recognition/frontend/i18n/<lang>.json
    const url = `/amazon_face_recognition/frontend/i18n/${encodeURIComponent(lang)}.json`;
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`i18n fetch failed (${res.status})`);
    const data = await res.json();
    if (!data || typeof data !== 'object') return {};
    return data;
  }

  _ensureI18n() {
    const langFull = this._getLang();
    const lang = langFull.toLowerCase();
    const primary = lang.split(/[-_]/)[0] || 'en';

    // If language did not change, do nothing
    if (this._i18nLang === lang) return;
    this._i18nLang = lang;

    // Start loading (non-blocking)
    this._i18nLoading = (async () => {
      let dict = {};
      try {
        dict = await this._fetchI18nFile(lang);
      } catch (_) {
        try {
          dict = await this._fetchI18nFile(primary);
        } catch (_) {
          try {
            dict = await this._fetchI18nFile('en');
          } catch (_) {
            dict = {};
          }
        }
      }
      this._i18nDict = dict || {};
      this._scheduleRender();
    })();
  }

  _t(key, fallback, vars) {
    const dict = this._i18nDict || {};
    let out = (key && Object.prototype.hasOwnProperty.call(dict, key)) ? dict[key] : null;
    if (typeof out !== 'string' || !out) out = fallback ?? key;
    if (vars && typeof vars === 'object') {
      for (const [k, v] of Object.entries(vars)) {
        out = out.replaceAll(`{${k}}`, String(v));
      }
    }
    return String(out);
  }

    _getEntryIdFromPanels() {
    const panels = this._hass?.panels;
    if (!panels) return null;

    // prova a trovare un pannello che abbia config.entry_id
    for (const k of Object.keys(panels)) {
      const p = panels[k];
      const entryId = p?.config?.entry_id || p?.config?.entryId || null;
      if (!entryId) continue;

      // se il tuo panel è legato al domain, spesso è qui
      if (
        p?.component_name === "amazon_face_recognition" ||
        p?.config?.domain === "amazon_face_recognition" ||
        k === "amazon_face_recognition"
      ) {
        return entryId;
      }
    }

    // fallback: se ce n'è uno solo con entry_id, prendi quello
    const withEntry = Object.values(panels).find((p) => p?.config?.entry_id || p?.config?.entryId);
    return withEntry?.config?.entry_id || withEntry?.config?.entryId || null;
  }


  _qsDeep(pathFn) {
    try {
      return pathFn();
    } catch (e) {
      return null;
    }
  }
  async _openOptions() {
    try {
      // 1) vai alla pagina dell'integrazione
      const url = "/config/integrations/integration/amazon_face_recognition";
      if (typeof this._hass?.navigate === "function") {
        this._hass.navigate(url);
      } else {
        history.pushState(null, "", url);
        window.dispatchEvent(new Event("location-changed", { bubbles: true, composed: true }));
      }

      // 2) aspetta e poi clicca il bottone OPTIONS (quello che apre il popup)
      // retry ~6s
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 100));

        const btn = this._qsDeep(() =>
          document
            .querySelector("body > home-assistant")?.shadowRoot
            ?.querySelector("home-assistant-main")?.shadowRoot
            ?.querySelector("ha-drawer > partial-panel-resolver > ha-panel-config > ha-config-integrations > ha-config-integration-page")?.shadowRoot
            ?.querySelector("hass-subpage > div > div.section > ha-config-entry-row")?.shadowRoot
            ?.querySelector("ha-md-list > ha-md-list-item > ha-icon-button:nth-child(4)")
        );

        if (btn && typeof btn.click === "function") {
          btn.click();
          console.log("[AFR] clicked entry-row options icon (popup should open)");
          return;
        }
      }

      console.warn("[AFR] options icon not found (DOM changed or page not ready)");
    } catch (e) {
      console.error("[AFR] openOptions failed", e);
    }
  }



  _deepQueryAll(selector, root = document) {
    const out = [];
    const pushAll = (node) => {
      if (!node) return;
      try {
        if (node.querySelectorAll) out.push(...node.querySelectorAll(selector));
      } catch {}
      const kids = node.children ? Array.from(node.children) : [];
      for (const el of kids) {
        if (el.shadowRoot) pushAll(el.shadowRoot);
        pushAll(el);
      }
    };
    pushAll(root);
    return out;
  }

  async _clickConfigureOnIntegrationPage() {
    // retry ~4s
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 100));

      const buttons = [
        ...this._deepQueryAll("mwc-button"),
        ...this._deepQueryAll("ha-button"),
        ...this._deepQueryAll("button"),
      ];

      const target = buttons.find((b) => {
        const t = (b.innerText || b.textContent || "").trim().toUpperCase();
        return t === "CONFIGURE" || t === "OPTIONS";
      });

      if (target && typeof target.click === "function") {
        target.click();
        console.log("[AFR] clicked CONFIGURE/OPTIONS button");
        return true;
      }
    }

    console.warn("[AFR] CONFIGURE/OPTIONS button not found (page not ready or selector changed)");
    return false;
  }



  disconnectedCallback() {
    // cleanup object URLs + subscriptions
    try {
      if (this._roiImgObjectUrl) URL.revokeObjectURL(this._roiImgObjectUrl);
    } catch {}
    this._roiImgObjectUrl = null;

    for (const url of this._thumbUrls.values()) {
      try { URL.revokeObjectURL(url); } catch {}
    }
    this._thumbUrls.clear();
    this._thumbLoading.clear();

    try { if (typeof this._unsubGallery === "function") this._unsubGallery(); } catch {}
    try { if (typeof this._unsubPlates === "function") this._unsubPlates(); } catch {}
    try { if (typeof this._unsubRoi === "function") this._unsubRoi(); } catch {}

    this._unsubGallery = null;
    this._unsubPlates = null;
    this._unsubRoi = null;
  }

  

  /* ----------------------------- helpers ----------------------------- */

  _getToken() {
    return this._hass?.auth?.data?.access_token || null;
  }

  _esc(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _scheduleRender() {
    if (this._renderQueued) return;
    this._renderQueued = true;
    requestAnimationFrame(() => {
      this._renderQueued = false;
      this._render();
    });
  }

  _queueInitialRefresh() {
    if (this._didInitialRefresh) return;
    if (this._initialRefreshQueued) return;
    if (!this._hass || !this._hass.connection) return;

    this._initialRefreshQueued = true;

    // Defer to next tick so HA finishes wiring websocket/panels.
    Promise.resolve().then(async () => {
      try {
        // allow one paint
        await new Promise((r) => requestAnimationFrame(() => r()));
        await this._refreshAll();
        this._didInitialRefresh = true;
      } catch (e) {
        // don't block the UI if something goes wrong; user can still use Refresh button
        console.debug("[AFR] initial refresh skipped", e);
      } finally {
        this._initialRefreshQueued = false;
      }
    });
  }

  async _apiJson(method, url, body) {
    const token = this._getToken();
    if (!token) throw new Error("Missing Home Assistant access_token");

    const init = {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      credentials: "same-origin",
      body: body ? JSON.stringify(body) : undefined,
    };

    const res = await fetch(url, init);
    const txt = await res.text();
    let data;
    try {
      data = JSON.parse(txt);
    } catch {
      data = { raw: txt };
    }
    if (!res.ok) throw new Error(data?.message || data?.raw || `${method} failed (${res.status})`);
    return data;
  }

  async _apiDelete(url) {
    return this._apiJson("DELETE", url);
  }

  async _fetchBlob(url) {
    const token = this._getToken();
    if (!token) throw new Error("Missing Home Assistant access_token");
    const res = await fetch(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`GET blob failed (${res.status})`);
    return await res.blob();
  }

  /* ----------------------------- tabs ----------------------------- */

  async _setTab(tab) {
    const t = tab === "roi" ? "roi" : tab === "plates" ? "plates" : "gallery";
    if (this._tab === t) return;
    this._tab = t;

    if (t === "roi") {
      this._ensureRoiCamera();
      await this._setRoiImageSrc(this._roiCamera);
    }

    this._scheduleRender();
  }

  /* ----------------------------- cameras / ROI image ----------------------------- */

  _listCameras() {
    const hass = this._hass;
    if (!hass?.states) return [];
    return Object.keys(hass.states)
      .filter((eid) => eid.startsWith("camera."))
      .sort((a, b) => a.localeCompare(b));
  }

  _ensureRoiCamera() {
    const cams = this._listCameras();
    if (!cams.length) return;
    if (!this._roiCamera || !cams.includes(this._roiCamera)) this._roiCamera = cams[0];
  }

  async _setRoiImageSrc(entityId) {
    if (!this._hass || !entityId) return;

    // Revoke previous URL
    if (this._roiImgObjectUrl) {
      try { URL.revokeObjectURL(this._roiImgObjectUrl); } catch {}
      this._roiImgObjectUrl = null;
    }

    try {
      const t = this._roiImgBuster || Date.now();
      // Fetch with Authorization header -> blob -> objectURL
      const blob = await this._fetchBlob(`/api/camera_proxy/${entityId}?_t=${t}`);
      const url = URL.createObjectURL(blob);
      this._roiImgObjectUrl = url;
      this._roiImgSrc = url;
    } catch (e) {
      console.warn("[AFR] ROI camera frame fetch failed", e);
      this._roiImgSrc = ""; // show broken image placeholder
    }

    this._scheduleRender();
  }

  /* ----------------------------- ROI websocket ----------------------------- */

  async _loadRoi() {
    if (!this._hass) return;
    try {
      const resp = await this._hass.connection.sendMessagePromise({ type: "amazon_face_recognition/get_roi" });
      const payload = resp || {};
      const by_camera = payload.by_camera && typeof payload.by_camera === "object" ? payload.by_camera : {};
      this._roi = { updated_at: payload.updated_at ?? null, by_camera };
      this._ensureRoiCamera();

      // If already in ROI tab and image not loaded, load it
      if (this._tab === "roi" && this._roiCamera && !this._roiImgSrc) {
        await this._setRoiImageSrc(this._roiCamera);
      }

      this._scheduleRender();
    } catch (e) {
      console.warn("[AFR] ROI load error", e);
    }
  }

  _subscribeRoi() {
    if (!this._hass || this._unsubRoi) return;

    this._hass.connection
      .subscribeMessage(
        (msg) => {
          const p = msg?.event?.data;
          if (!p) return;

          // while interacting or editing: stash update, don't re-render
          if (this._roiInteracting || this._roiNameEditing) {
            this._roiPendingUpdate = p;
            return;
          }

          const by_camera = p.by_camera && typeof p.by_camera === "object" ? p.by_camera : {};
          this._roi = { updated_at: p.updated_at ?? null, by_camera };
          this._ensureRoiCamera();
          this._scheduleRender();
        },
        { type: "amazon_face_recognition/subscribe_roi" }
      )
      .then((unsub) => (this._unsubRoi = unsub))
      .catch((e) => console.warn("[AFR] subscribe_roi failed", e));
  }

  _applyPendingRoiUpdateIfAny() {
    if (!this._roiPendingUpdate) return;
    const p = this._roiPendingUpdate;
    this._roiPendingUpdate = null;

    const by_camera = p.by_camera && typeof p.by_camera === "object" ? p.by_camera : {};
    this._roi = { updated_at: p.updated_at ?? null, by_camera };
    this._ensureRoiCamera();
    this._scheduleRender();
  }

  _getRoisForCamera(cam) {
    const bc = this._roi?.by_camera && typeof this._roi.by_camera === "object" ? this._roi.by_camera : {};
    return Array.isArray(bc[cam]) ? bc[cam] : [];
  }

  async _saveRoiForCamera(cam, rois) {
    if (!this._hass) return;

    const bc = this._roi?.by_camera && typeof this._roi.by_camera === "object" ? { ...this._roi.by_camera } : {};
    bc[cam] = rois;

    await this._hass.connection.sendMessagePromise({ type: "amazon_face_recognition/set_roi", by_camera: bc });
    await this._loadRoi(); // keep client in sync
  }

  _pxToNormRect(rectPx, overlayW, overlayH) {
    const clamp01 = (v) => Math.max(0, Math.min(1, v));
    return {
      x: clamp01(rectPx.x / overlayW),
      y: clamp01(rectPx.y / overlayH),
      w: clamp01(rectPx.w / overlayW),
      h: clamp01(rectPx.h / overlayH),
    };
  }

  _normToPxRect(rect, overlayW, overlayH) {
    return {
      x: (rect.x || 0) * overlayW,
      y: (rect.y || 0) * overlayH,
      w: (rect.w || 0) * overlayW,
      h: (rect.h || 0) * overlayH,
    };
  }

  _uuid() {
    return "roi_" + Math.random().toString(16).slice(2) + Date.now().toString(16);
  }

  _roiOverlayRectEl(id) {
    const root = this.shadowRoot;
    if (!root) return null;
    return root.querySelector(`.roi-rect[data-roi-id="${CSS.escape(id)}"]`);
  }

  _roiOnMouseDown(ev) {
    const overlay = ev.currentTarget;
    if (!(overlay instanceof HTMLElement)) return;

    this._roiInteracting = true;
    const rect = overlay.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;

    const t = ev.target;
    const roiEl = t?.closest?.("[data-roi-id]");
    if (roiEl) {
      const id = roiEl.getAttribute("data-roi-id");
      const handle = t?.getAttribute?.("data-handle") || null;
      this._roiSelectedId = id;

      const overlayW = rect.width || 1;
      const overlayH = rect.height || 1;

      const rois = this._getRoisForCamera(this._roiCamera);
      const r = rois.find((a) => a.id === id);
      if (!r) {
        this._roiInteracting = false;
        return;
      }

      const px = this._normToPxRect(r, overlayW, overlayH);
      this._roiDrag = {
        id,
        mode: handle ? "resize" : "move",
        startX: x,
        startY: y,
        ox: px.x,
        oy: px.y,
        ow: px.w,
        oh: px.h,
      };

      this._updateRoiDom(); // highlight selection
      ev.preventDefault();
      return;
    }

    // new rect draw
    this._roiSelectedId = null;
    this._roiDrawing = { x0: x, y0: y, x1: x, y1: y };
    this._updateRoiDom();
    ev.preventDefault();
  }

  async _roiOnMouseUp(ev) {
    const overlay = ev.currentTarget;
    if (!(overlay instanceof HTMLElement)) return;

    const rect = overlay.getBoundingClientRect();
    const overlayW = rect.width || 1;
    const overlayH = rect.height || 1;

    try {
      if (this._roiDrawing) {
        const d = this._roiDrawing;
        const x = Math.min(d.x0, d.x1);
        const y = Math.min(d.y0, d.y1);
        const w = Math.abs(d.x1 - d.x0);
        const h = Math.abs(d.y1 - d.y0);
        this._roiDrawing = null;

        // ignore tiny
        if (w >= 8 && h >= 8) {
          const rois = [...this._getRoisForCamera(this._roiCamera)];
          const id = this._uuid();
          const n = this._pxToNormRect({ x, y, w, h }, overlayW, overlayH);
          rois.push({ id, name: "", ...n });
          this._roiSelectedId = id;
          await this._saveRoiForCamera(this._roiCamera, rois);
        } else {
          this._updateRoiDom();
        }
        return;
      }

      // finalize drag: commit changes to backend
      if (this._roiDrag) {
        this._roiDrag = null;

        // commit current local state
        const rois = [...this._getRoisForCamera(this._roiCamera)];
        await this._saveRoiForCamera(this._roiCamera, rois);
        return;
      }
    } finally {
      this._roiInteracting = false;
      this._applyPendingRoiUpdateIfAny();
    }
  }

  _roiOnMouseMove(ev) {
    const overlay = ev.currentTarget;
    if (!(overlay instanceof HTMLElement)) return;

    const rect = overlay.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;

    if (this._roiDrawing) {
      this._roiDrawing.x1 = x;
      this._roiDrawing.y1 = y;
      this._updateRoiDom();
      return;
    }

    if (!this._roiDrag) return;

    const overlayW = rect.width || 1;
    const overlayH = rect.height || 1;

    const rois = [...this._getRoisForCamera(this._roiCamera)];
    const idx = rois.findIndex((r) => r.id === this._roiDrag.id);
    if (idx < 0) return;

    const dx = x - this._roiDrag.startX;
    const dy = y - this._roiDrag.startY;

    let px = {
      x: this._roiDrag.ox,
      y: this._roiDrag.oy,
      w: this._roiDrag.ow,
      h: this._roiDrag.oh,
    };

    if (this._roiDrag.mode === "move") {
      px.x = this._roiDrag.ox + dx;
      px.y = this._roiDrag.oy + dy;
    } else {
      px.w = Math.max(8, this._roiDrag.ow + dx);
      px.h = Math.max(8, this._roiDrag.oh + dy);
    }

    // clamp within overlay
    px.x = Math.max(0, Math.min(overlayW - px.w, px.x));
    px.y = Math.max(0, Math.min(overlayH - px.h, px.y));
    px.w = Math.max(8, Math.min(overlayW - px.x, px.w));
    px.h = Math.max(8, Math.min(overlayH - px.y, px.h));

    const n = this._pxToNormRect(px, overlayW, overlayH);
    rois[idx] = { ...rois[idx], ...n };

    // update local state without full render
    const bc = { ...(this._roi?.by_camera || {}) };
    bc[this._roiCamera] = rois;
    this._roi = { ...(this._roi || {}), by_camera: bc };

    // update only overlay element
    const el = this._roiOverlayRectEl(rois[idx].id);
    if (el) {
      el.style.left = `${px.x}px`;
      el.style.top = `${px.y}px`;
      el.style.width = `${px.w}px`;
      el.style.height = `${px.h}px`;
    }
  }

  async _roiDeleteSelected() {
    const id = this._roiSelectedId;
    if (!id) return;
    const rois = [...this._getRoisForCamera(this._roiCamera)].filter((r) => r.id !== id);
    this._roiSelectedId = null;
    await this._saveRoiForCamera(this._roiCamera, rois);
  }

  async _roiRename(id, name) {
    const rois = [...this._getRoisForCamera(this._roiCamera)];
    const idx = rois.findIndex((r) => r.id === id);
    if (idx < 0) return;
    rois[idx] = { ...rois[idx], name: String(name || "").trim() };
    await this._saveRoiForCamera(this._roiCamera, rois);
  }

  _updateRoiDom() {
    const root = this.shadowRoot;
    if (!root || this._tab !== "roi") return;

    const overlay = root.getElementById("roi_overlay");
    if (!overlay) return;

    const rect = overlay.getBoundingClientRect();
    const w = rect.width || 1;
    const h = rect.height || 1;
    const rois = this._getRoisForCamera(this._roiCamera);

    overlay.innerHTML = `
      ${rois
        .map((r) => {
          const px = this._normToPxRect(r, w, h);
          const sel = r.id === this._roiSelectedId;
          return `
            <div class="roi-rect ${sel ? "sel" : ""}" data-roi-id="${this._esc(r.id)}" style="left:${px.x}px; top:${px.y}px; width:${px.w}px; height:${px.h}px;">
              <div class="roi-handle" data-handle="br"></div>
            </div>
          `;
        })
        .join("")}
      ${this._roiDrawing
        ? (() => {
            const d = this._roiDrawing;
            const x = Math.min(d.x0, d.x1);
            const y = Math.min(d.y0, d.y1);
            const ww = Math.abs(d.x1 - d.x0);
            const hh = Math.abs(d.y1 - d.y0);
            return `<div class="roi-rect" style="left:${x}px; top:${y}px; width:${ww}px; height:${hh}px;"></div>`;
          })()
        : ""}
    `;

    // also update list selection styles without full render
    root.querySelectorAll("[data-roi-sel]").forEach((el) => {
      const id = el.getAttribute("data-roi-sel");
      if (!id) return;
      if (id === this._roiSelectedId) el.classList.add("sel");
      else el.classList.remove("sel");
    });

    const delBtn = root.getElementById("roi_delete");
    if (delBtn) delBtn.disabled = !this._roiSelectedId;
  }

  _renderRoiTab() {
    this._ensureRoiCamera();
    const cams = this._listCameras();
    if (!cams.length) return `<div class="card"><div class="muted">${this._esc(this._t("roi.no_cameras","No camera.* entities found in Home Assistant."))}</div></div>`;

    const cam = this._roiCamera;
    const rois = this._getRoisForCamera(cam);

    return `
      <div class="card">
        <div class="row">
          <div class="name">${this._esc(this._t("roi.title","ROI Editor"))}</div>
          <div class="spacer"></div>
          <div class="muted">${this._roi?.updated_at ? `Updated: ${this._esc(this._roi.updated_at)}` : ""}</div>
        </div>

        <div class="row" style="gap:12px;">
          <label class="muted">${this._esc(this._t("roi.camera","Camera"))}</label>
          <div class="cam-picker" id="roi_cam_picker">
            <button class="cam-btn" id="roi_cam_btn" type="button">
              <span class="cam-label" id="roi_cam_label"></span>
              <ha-icon icon="mdi:chevron-down"></ha-icon>
            </button>

            <div class="cam-menu" id="roi_cam_menu" hidden>
              <input class="cam-search" id="roi_cam_search" type="text" placeholder="Search camera…" />
              <div class="cam-list" id="roi_cam_list"></div>
            </div>
          </div>


          <button id="roi_refresh_img">${this._esc(this._t("roi.refresh_image","Refresh image"))}</button>
          <div class="spacer"></div>
          <button id="roi_delete" class="danger" ${this._roiSelectedId ? "" : "disabled"}>${this._esc(this._t("roi.delete_selected","Delete selected ROI"))}</button>
        </div>

        <div class="roi-grid">
          <div class="roi-canvas">
            <div class="roi-stage">
              <img id="roi_img" src="${this._esc(this._roiImgSrc || "")}" alt="${this._esc(cam)}" />
              <div id="roi_overlay" class="roi-overlay"></div>
            </div>
            <div class="muted" style="margin-top:8px;">
              ${this._esc(this._t("roi.instructions","Drag on the frame to create an ROI. Drag an ROI to move it. Drag the bottom-right corner to resize it."))}
            </div>
          </div>

          <div class="roi-list">
            <div class="name" style="margin-bottom:8px;">${this._esc(this._t("roi.list_title","Camera ROIs"))}</div>
            ${rois.length ? "" : `<div class="muted">${this._esc(this._t("roi.none","No ROI configured."))}</div>`}
            <div class="roi-items">
              ${rois
                .map((r, i) => {
                  const sel = r.id === this._roiSelectedId;
                  const label = r.name ? this._esc(r.name) : `${this._t("roi.zone","Zone {n}",{n: i+1})}`;
                  return `
                    <div class="roi-item ${sel ? "sel" : ""}" data-roi-sel="${this._esc(r.id)}">
                      <div style="display:flex; align-items:center; justify-content:space-between; gap:8px;">
                        <div>
                          <div class="name">${label}</div>
                          <div class="muted" style="font-size:12px;">id: ${this._esc(r.id)}</div>
                        </div>
                      </div>
                      <input class="roi-name" data-roi-name="${this._esc(r.id)}" type="text" placeholder="${this._esc(this._t("roi.name_optional", "Name (optional)"))}" value="${this._esc(r.name || "")}" />
                    </div>
                  `;
                })
                .join("")}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /* ----------------------------- plates ----------------------------- */

  _normPlate(s) {
    return String(s ?? "").trim().toUpperCase().replaceAll(" ", "").replaceAll("-", "").replaceAll(".", "");
  }

  async _loadPlates() {
    if (!this._hass) return;
    try {
      const resp = await this._hass.connection.sendMessagePromise({ type: "amazon_face_recognition/get_plates" });
      const payload = resp || {};
      this._plates = {
        updated_at: payload.updated_at ?? null,
        items: payload.items && typeof payload.items === "object" ? payload.items : {},
      };
      this._scanCarsEnabled = Boolean(payload.scan_cars);
      this._scheduleRender();
    } catch (e) {
      console.warn("[AFR] Plates load error", e);
    }
  }

  _subscribePlates() {
    if (!this._hass || this._unsubPlates) return;

    this._hass.connection
      .subscribeMessage(
        (msg) => {
          const p = msg?.event?.data;
          if (!p) return;
          this._plates = {
            updated_at: p.updated_at ?? null,
            items: p.items && typeof p.items === "object" ? p.items : {},
          };
          if ("scan_cars" in p) this._scanCarsEnabled = Boolean(p.scan_cars);
          this._scheduleRender();
        },
        { type: "amazon_face_recognition/subscribe_plates" }
      )
      .then((unsub) => (this._unsubPlates = unsub))
      .catch((e) => console.warn("[AFR] subscribe_plates failed", e));
  }

  async _savePlates(items) {
    if (!this._hass) return;
    await this._hass.connection.sendMessagePromise({ type: "amazon_face_recognition/set_plates", items });
    await this._loadPlates();
  }

  _onPlateInput(e) {
    this._plateInput = e?.target?.value || "";
  }

  _onPlateNameInput(e) {
    this._plateNameInput = e?.target?.value || "";
  }

  async _addPlateMapping() {
    const plate = this._normPlate(this._plateInput);
    const name = String(this._plateNameInput || "").trim();

    if (!plate) {
      this._uploadError = this._t("plates.err_plate","Enter a valid plate.");
      this._scheduleRender();
      return;
    }
    if (!name) {
      this._uploadError = this._t("plates.err_name","Enter a name for this plate.");
      this._scheduleRender();
      return;
    }

    const cur = this._plates?.items && typeof this._plates.items === "object" ? { ...this._plates.items } : {};
    cur[plate] = name;

    this._uploadError = null;
    await this._savePlates(cur);

    this._plateInput = "";
    this._plateNameInput = "";
    this._scheduleRender();
  }

  async _deletePlateMapping(plate) {
    const p = this._normPlate(plate);
    const cur = this._plates?.items && typeof this._plates.items === "object" ? { ...this._plates.items } : {};
    delete cur[p];
    await this._savePlates(cur);
    this._scheduleRender();
  }

  _renderPlates() {
    const items = this._plates?.items && typeof this._plates.items === "object" ? this._plates.items : {};
    const keys = Object.keys(items);
    if (!keys.length) return `<div class="muted">${this._esc(this._t("plates.none","No plate → name mappings."))}</div>`;

    return `
      <div class="list">
        ${keys
          .sort((a, b) => a.localeCompare(b))
          .map(
            (plate) => `
              <div class="item">
                <div class="name">${this._esc(plate)}</div>
                <div class="meta">→ ${this._esc(items[plate])}</div>
                <div style="margin-top:8px;">
                  <button class="danger" data-del-plate="${this._esc(plate)}">${this._esc(this._t("plates.remove","Remove"))}</button>
                </div>
              </div>
            `
          )
          .join("")}
      </div>
    `;
  }

  _renderPlatesTab() {
    // UI only: same logic, moved to dedicated tab
    if (this._scanCarsEnabled) {
      return `
        <div class="card">
          <div class="row">
            <div class="name">${this._esc(this._t("plates.title","Map plates → names"))}</div>
            <div class="spacer"></div>
            <div class="muted">${this._plates?.updated_at ? `Updated: ${this._esc(this._plates.updated_at)}` : ""}</div>
          </div>

          <div class="row">
            <input id="plate" type="text" placeholder="${this._esc(this._t("plates.placeholder_plate", "Plate (e.g., DC964JJ)"))}" value="${this._esc(this._plateInput)}" />
            <input id="plate_name" type="text" placeholder="${this._esc(this._t("plates.placeholder_name", "Name (e.g., Mattia)"))}" value="${this._esc(this._plateNameInput)}" />
            <button id="plate_add">${this._esc(this._t("plates.add","Add"))}</button>
          </div>

          ${this._renderPlates()}
          <div class="muted" style="margin-top:8px;">${this._esc(this._t("plates.normalize_hint","Plates are normalized (UPPERCASE, no spaces/separators)."))}</div>
        </div>
      `;
    }

    return `
      <div class="card">
        <div class="row">
          <div class="name">${this._esc(this._t("plates.title","Map plates → names"))}</div>
          <div class="spacer"></div>
          <div class="muted">Abilita “Scan Cars” per usare questa sezione.</div>
        </div>
      </div>
    `;
  }


  /* ----------------------------- gallery ----------------------------- */

  async _loadFacesIndex() {
    if (!this._hass) return;
    this._loading = true;
    this._error = null;
    this._scheduleRender();

    try {
      const resp = await this._hass.connection.sendMessagePromise({ type: "amazon_face_recognition/get_faces_index" });
      this._facesIndex = resp || null;
    } catch (e) {
      this._error = e?.message || String(e);
    } finally {
      this._loading = false;
      this._scheduleRender();
    }
  }

  async _loadGallery() {
    if (!this._hass) return;
    try {
      const resp = await this._hass.connection.sendMessagePromise({ type: "amazon_face_recognition/get_gallery" });
      this._gallery = resp || null;
      this._scheduleRender();
    } catch (e) {
      console.error("[AFR] Gallery error", e);
    }
  }

  async _refreshAll() {
    for (const url of this._thumbUrls.values()) {
      try { URL.revokeObjectURL(url); } catch {}
    }
    this._thumbUrls.clear();
    this._thumbLoading.clear();

    await this._loadFacesIndex();
    await this._loadGallery();
  }

  async _syncFaceGalleryFromS3() {
    if (!this._hass) return;
    try {
      await this._hass.connection.sendMessagePromise({
        type: "amazon_face_recognition/sync_face_gallery",
        force_align: true,
      });
    } catch (e) {
      // If S3 is not configured, this is a no-op.
      console.debug("[AFR] sync_face_gallery failed", e);
    }
  }

  _subscribeGallery() {
    if (!this._hass || this._unsubGallery) return;

    this._hass.connection
      .subscribeMessage(
        (msg) => {
          const g = msg?.event?.data;
          if (!g) return;

          this._gallery = g;

          // purge thumb cache (gallery changed)
          for (const url of this._thumbUrls.values()) {
            try { URL.revokeObjectURL(url); } catch {}
          }
          this._thumbUrls.clear();
          this._thumbLoading.clear();

          this._scheduleRender();
        },
        { type: "amazon_face_recognition/subscribe_gallery" }
      )
      .then((unsub) => (this._unsubGallery = unsub))
      .catch((e) => console.warn("[AFR] subscribe_gallery failed", e));
  }

  _onNameInput(e) {
    this._uploadName = (e?.target?.value || "").trim();
  }

  _onFileInput(e) {
    const files = e?.target?.files;
    this._uploadFile = files && files.length ? files[0] : null;
  }

  async _deleteImage(imageId) {
    try {
      await this._apiDelete(`/api/amazon_face_recognition/gallery/image/${encodeURIComponent(imageId)}`);
      await this._refreshAll();
    } catch (e) {
      this._uploadError = e?.message || String(e);
      this._scheduleRender();
    }
  }

  async _deleteName(name) {
    const ok = confirm(
      "⚠️ ATTENZIONE\n\n" +
        `Se procedi verranno eliminate TUTTE le foto e TUTTI i volti associati a:\n"${name}"\n\n` +
        "L'operazione è irreversibile.\n\nVuoi continuare?"
    );
    if (!ok) return;

    try {
      await this._apiDelete(`/api/amazon_face_recognition/gallery/manage?mode=name&name=${encodeURIComponent(name)}`);
      await this._refreshAll();
    } catch (e) {
      this._uploadError = e?.message || String(e);
      this._scheduleRender();
    }
  }

  async _deleteAll() {
    const ok = confirm(
      "⚠️ ATTENZIONE\n\n" +
        "Se procedi verranno eliminati TUTTI i volti,\n" +
        "tutte le foto locali e tutte le face su AWS Rekognition.\n\n" +
        "Vuoi continuare?"
    );
    if (!ok) return;

    try {
      await this._apiDelete(`/api/amazon_face_recognition/gallery/manage?mode=all`);
      await this._refreshAll();
    } catch (e) {
      this._uploadError = e?.message || String(e);
      this._scheduleRender();
    }
  }

  async _upload() {
    if (!this._hass) return;
    this._uploadError = null;
    this._uploadOk = null;

    const name = (this._uploadName || "").trim();
    if (!name) {
      this._uploadError = "Enter a person name.";
      this._scheduleRender();
      return;
    }
    if (!this._uploadFile) {
      this._uploadError = "Select an image file.";
      this._scheduleRender();
      return;
    }

    this._uploading = true;
    this._scheduleRender();

    try {
      const fd = new FormData();
      fd.append("name", name);
      fd.append("file", this._uploadFile);

      const token = this._getToken();
      if (!token) throw new Error("Missing Home Assistant access_token");

      const res = await fetch("/api/amazon_face_recognition/gallery/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
        credentials: "same-origin",
      });

      const txt = await res.text();
      let data;
      try { data = JSON.parse(txt); } catch { data = { raw: txt }; }

      if (!res.ok) {
        this._uploadError = data?.message || data?.raw || `Upload failed (${res.status})`;
      } else {
        this._uploadOk = this._t("upload.success", `Uploaded: ${data.name} (image_id: ${data.image_id})`, { name: data.name, image_id: data.image_id });
        this._uploadFile = null;

        const fileInput = this.shadowRoot?.getElementById("file");
        if (fileInput) fileInput.value = "";

        await this._refreshAll();
      }
    } catch (e) {
      this._uploadError = e?.message || String(e);
    } finally {
      this._uploading = false;
      this._scheduleRender();
    }
  }

  async _ensureThumb(imageId) {
    if (!this._hass) return;
    if (this._thumbUrls.has(imageId)) return;
    if (this._thumbLoading.has(imageId)) return;

    this._thumbLoading.add(imageId);

    try {
      const blob = await this._fetchBlob(`/api/amazon_face_recognition/gallery/image/${encodeURIComponent(imageId)}`);
      const url = URL.createObjectURL(blob);
      this._thumbUrls.set(imageId, url);
      this._scheduleRender();
    } catch (e) {
      console.warn("[AFR] Thumb fetch error", imageId, e);
    } finally {
      this._thumbLoading.delete(imageId);
    }
  }

  _renderGallery() {
    const g = this._gallery || { persons: {} };
    const persons = g.persons || {};
    const names = Object.keys(persons);

    if (!names.length) return `<div class="muted">${this._esc(this._t("gallery.empty", "No images in gallery."))}</div>`;

    return names
      .sort((a, b) => a.localeCompare(b))
      .map((name) => {
        const items = Array.isArray(persons[name]) ? persons[name] : [];
        return `
          <div class="person">
            <div class="person-h">
              <div>
                <div class="person-name">${this._esc(name)}</div>
                <div class="muted">${this._esc(this._t("gallery.images_count", `${items.length} image(s)`, { count: items.length }))}</div>
              </div>
              <button class="danger" data-del-name="${this._esc(name)}">${this._esc(this._t("buttons.delete_person","Delete person"))}</button>
            </div>

            <div class="thumbs">
              ${items
                .map((it) => {
                  const id = it.image_id;
                  this._ensureThumb(id);
                  const thumbUrl = this._thumbUrls.get(id) || "";

                  return `
                    <div class="thumb">
                      ${
                        thumbUrl
                          ? `<img src="${thumbUrl}" alt="${this._esc(name)}" loading="lazy" />`
                          : `<div class="thumb-ph">${this._esc(this._t("messages.loading","Loading..."))}</div>`
                      }
                      <div class="thumb-meta">
                        <div class="muted">id: ${this._esc(id)}</div>
                        <button class="danger" data-del-img="${this._esc(id)}">🗑️</button>
                      </div>
                    </div>
                  `;
                })
                .join("")}
            </div>
          </div>
        `;
      })
      .join("");
  }

  /* ----------------------------- render ----------------------------- */

  _render() {
    const root = this.shadowRoot;
    if (!root) return;

    const facesPersons = this._facesIndex?.persons || {};
    const faceNames = Object.keys(facesPersons);

    root.innerHTML = `
      <style>
        :host { display:block; padding: 16px; --roi-control-height: 42px; }
        .wrap { max-width: 1200px; margin: 0 auto; }
        .row { display:flex; gap: 10px; align-items:center; flex-wrap: wrap; margin: 10px 0 16px; }
        .spacer { flex: 1; }
        button {
          padding: 8px 12px;
          border-radius: 10px;
          border: 1px solid rgba(255,255,255,0.15);
          background: rgba(255,255,255,0.06);
          color: inherit;
          cursor: pointer;
        }
        button:disabled { opacity: .5; cursor: default; }
        input[type="text"], input[type="file"]{
          padding: 8px 10px;
          border-radius: 10px;
          border: 1px solid rgba(255,255,255,0.15);
          background: rgba(255,255,255,0.04);
          color: inherit;
        }
        input[type="text"]{ min-width: 220px; }
        select {
          /* NOTE: native <select> can be hard to read in dark themes (browser dropdown) */
          padding: 8px 10px;
          border-radius: 10px;
          border: 1px solid rgba(255,255,255,0.15);
          background: rgba(255,255,255,0.04);
          color: inherit;
        }
        ha-combo-box.roi-camera{
          width: 340px;
          max-width: 100%;
        }
        .card {
          border-radius: 16px;
          border: 1px solid rgba(255,255,255,0.10);
          background: rgba(0,0,0,0.15);
          padding: 14px;
          margin-bottom: 14px;
        }
        .err { color: #ff8a8a; margin-top: 8px; white-space: pre-wrap; }
        .ok { color: #9bffb0; margin-top: 8px; white-space: pre-wrap; }
        .muted { opacity:.75; }
        .list { display:grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
        .item { padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.03); }
        .name { font-weight: 600; }
        .meta { opacity: .8; margin-top: 4px; font-size: 13px; }

        .person { margin-top: 12px; }
        .person-h { display:flex; align-items: baseline; justify-content: space-between; margin: 6px 2px; gap: 10px; }
        .person-name { font-weight: 700; }

        .thumb-ph{
          height: 140px;
          display:flex;
          align-items:center;
          justify-content:center;
          opacity:.7;
          background: rgba(0,0,0,0.25);
        }
        .thumbs { display:grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
        .thumb { border-radius: 14px; border: 1px solid rgba(255,255,255,0.10); background: rgba(255,255,255,0.03); overflow:hidden; }
        .thumb img { display:block; width: 100%; height: 140px; object-fit: cover; background: rgba(0,0,0,0.25); }
        .thumb-meta { padding: 8px 10px; font-size: 12px; display:flex; align-items:center; justify-content: space-between; gap: 8px; }

        button.danger { border-color: rgba(255,0,0,0.35); }

        .icon-button {
          background: none;
          border: none;
          cursor: pointer;
          padding: 6px;
          border-radius: 50%;
        }
        .icon-button:hover { background: rgba(255, 255, 255, 0.08); }

        /* folder tabs */
        .folder-tabs {
          display:flex;
          align-items:flex-end;
          gap: 6px;
          margin: 10px 0 16px;
          border-bottom: 1px solid var(--divider-color, rgba(255,255,255,0.18));
        }
        .ftab {
          position: relative;
          padding: 10px 14px;
          border-radius: 12px 12px 0 0;
          border: 1px solid var(--divider-color, rgba(255,255,255,0.18));
          border-bottom-color: var(--divider-color, rgba(255,255,255,0.18));
          background: var(--secondary-background-color, rgba(255,255,255,0.04));
          cursor: pointer;
          user-select: none;
          font-weight: 600;
          color: var(--primary-text-color, inherit);
          line-height: 1;
        }
        .ftab:hover { filter: brightness(1.06); }
        .ftab.active {
          background: var(--card-background-color, rgba(0,0,0,0.15));
          border-bottom-color: transparent;
        }
        .ftab.active::after {
          content: "";
          position: absolute;
          left: 10px;
          right: 10px;
          bottom: -1px;
          height: 2px;
          border-radius: 2px;
          background: var(--primary-color, currentColor);
        }


        /* ROI */
        .roi-grid { display:grid; grid-template-columns: 2fr 1fr; gap: 14px; }
        @media (max-width: 900px) { .roi-grid { grid-template-columns: 1fr; } }
        .roi-stage { position: relative; width: 100%; border-radius: 14px; overflow:hidden; border: 1px solid rgba(255,255,255,0.10); background: rgba(0,0,0,0.25); }
        .roi-stage img { display:block; width: 100%; height: auto; }
        .roi-overlay { position:absolute; inset:0; cursor: crosshair; }
        .roi-rect {
          position:absolute;
          border: 2px solid rgba(0, 200, 255, 0.95);
          background: rgba(0, 200, 255, 0.10);
          border-radius: 8px;
          box-sizing: border-box;
        }
        .roi-rect.sel { border-color: rgba(255, 200, 0, 0.95); background: rgba(255, 200, 0, 0.10); }
        .roi-handle {
          position:absolute;
          width: 14px;
          height: 14px;
          right: -7px;
          bottom: -7px;
          border-radius: 50%;
          background: rgba(255,255,255,0.9);
          border: 1px solid rgba(0,0,0,0.3);
          cursor: nwse-resize;
        }
        .roi-list { border-radius: 16px; border: 1px solid rgba(255,255,255,0.10); background: rgba(255,255,255,0.03); padding: 12px; }
        .roi-items { display:flex; flex-direction: column; gap: 10px; }
        .roi-item { padding: 10px; border-radius: 14px; border: 1px solid rgba(255,255,255,0.08); background: rgba(0,0,0,0.18); cursor: pointer; }
        .roi-item.sel { border-color: rgba(255, 200, 0, 0.45); }
        .roi-name { width: -webkit-fill-available; margin-top: 8px; }

        /* Premium camera picker */
        .cam-picker { position: relative; width: 340px; max-width: 100%; }
        .cam-btn{
          width: 100%;
          display:flex; align-items:center; justify-content:space-between; gap:10px;
          padding: 10px 12px;
          border-radius: 12px;
          border: 1px solid rgba(255,255,255,0.14);
          background: rgba(255,255,255,0.06);
        }
        .cam-label{ overflow:hidden; text-overflow: ellipsis; white-space: nowrap; text-align:left; }

        .cam-menu{
          position:absolute;
          top: calc(100% + 8px);
          left: 0;
          right: 0;
          z-index: 50;
          border-radius: 14px;
          border: 1px solid rgba(255,255,255,0.14);
          background: rgba(15,15,15,0.98);
          box-shadow: 0 12px 32px rgba(0,0,0,0.45);
          overflow: hidden;
        }
        .cam-search{
          width: 100%;
          border: none;
          outline: none;
          padding: 10px 12px;
          background: rgba(255,255,255,0.04);
        }
        .cam-list{ max-height: 320px; overflow:auto; padding: 6px; }
        .cam-item{
          display:flex; flex-direction:column; gap:2px;
          padding: 10px 10px;
          border-radius: 12px;
          cursor: pointer;
        }
        .cam-item:hover{ background: rgba(255,255,255,0.06); }
        .cam-item .muted{ font-size: 12px; opacity: .75; }
        .cam-item.active{ outline: 1px solid rgba(255,200,0,0.45); background: rgba(255,200,0,0.08); }

        /* ROI controls uniform height */
        .roi-camera,
        #roi_refresh_img,
        #roi_delete {
          height: var(--roi-control-height);
          min-height: var(--roi-control-height);
          box-sizing: border-box;
        }

        /* Button vertical centering */
        #roi_refresh_img,
        #roi_delete {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          padding: 0 14px; /* no vertical padding */
        }

        /* Select / picker text alignment */
        .roi-camera {
          padding: 0 12px;
          line-height: calc(var(--roi-control-height) - 2px);
        }

        /* Same border radius feel */
        .roi-camera,
        #roi_refresh_img,
        #roi_delete {
          border-radius: 12px;
        }

        /* Slight visual balance */
        #roi_refresh_img {
          margin-left: 4px;
        }
        #roi_delete {
          margin-left: auto;
        }



      </style>

      <div class="wrap">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom: 12px;">
          <div style="font-size: 20px; font-weight: 600;">Amazon Face Recognition</div>

          <button class="icon-button" id="open_options" title="${this._esc(this._t("buttons.configure", "Configure"))}">
            <ha-icon icon="mdi:cog"></ha-icon>
          </button>

        </div>


        <div class="folder-tabs" role="tablist" aria-label="AFR tabs">
          <div class="ftab ${this._tab === "gallery" ? "active" : ""}" data-tab="gallery" role="tab" aria-selected="${this._tab === "gallery"}">${this._esc(this._t("tabs.gallery","Gallery"))}</div>
          <div class="ftab ${this._tab === "roi" ? "active" : ""}" data-tab="roi" role="tab" aria-selected="${this._tab === "roi"}">${this._esc(this._t("tabs.roi","ROI"))}</div>
          <div class="ftab ${this._tab === "plates" ? "active" : ""}" data-tab="plates" role="tab" aria-selected="${this._tab === "plates"}">${this._esc(this._t("tabs.plates","Plates"))}</div>
        </div>

        ${
          this._tab === "roi"
            ? this._renderRoiTab()
            : this._tab === "plates"
              ? this._renderPlatesTab()
              : `
              <div class="card">
                <div class="row">
                  <button id="refresh" ${this._loading ? "disabled" : ""}>${this._esc(this._t("buttons.refresh","Refresh"))}</button>
                  <div class="muted">
                    ${this._facesIndex?.updated_at ? `${this._esc(this._t("labels.faces_updated","Faces updated:"))} ${this._esc(this._facesIndex.updated_at)}` : ""}
                    ${this._gallery?.updated_at ? ` • ${this._esc(this._t("labels.gallery_updated","Gallery updated:"))} ${this._esc(this._gallery.updated_at)}` : ""}
                  </div>
                  <div class="spacer"></div>
                </div>

                ${this._loading ? `<div>${this._esc(this._t("messages.loading","Loading..."))}</div>` : ""}
                ${this._error ? `<div class="err">${this._esc(this._error)}</div>` : ""}

                ${
                  !this._loading && !this._error
                    ? faceNames.length
                      ? `<div class="list">
                          ${faceNames
                            .map((n) => {
                              const c = facesPersons[n]?.count ?? 0;
                              return `<div class="item">
                                <div class="name">${this._esc(n)}</div>
                                <div class="meta">${c} face(s) in collection</div>
                              </div>`;
                            })
                            .join("")}
                        </div>`
                      : `<div>${this._esc(this._t("messages.no_faces","No faces in collection."))}</div>`
                    : ""
                }
              </div>

              <div class="card">
                <div class="row">
                  <div class="name">${this._esc(this._t("upload.title","Upload training photos"))}</div>
                  <div class="spacer"></div>
                </div>

                <div class="row">
                  <input id="name" type="text" placeholder="${this._esc(this._t("upload.placeholder_name", "Person name (ExternalImageId)"))}" value="${this._esc(this._uploadName)}" />
                  <input id="file" type="file" accept="image/jpeg,image/png" />
                  <button id="upload" ${this._uploading ? "disabled" : ""}>${this._uploading ? this._esc(this._t("upload.uploading","Uploading...")) : this._esc(this._t("upload.button","Upload"))}</button>
                </div>

                ${this._uploadError ? `<div class="err">${this._esc(this._uploadError)}</div>` : ""}
                ${this._uploadOk ? `<div class="ok">${this._esc(this._uploadOk)}</div>` : ""}
                <div class="muted">${this._esc(this._t("upload.hint","${this._t('upload.hint','Saved into training_cache and indexed in Rekognition.')}"))}</div>
              </div>

              <div class="card">
                <div class="row">
                  <div class="name">${this._esc(this._t("gallery.title","Gallery (local cache)"))}</div>
                  <div class="spacer"></div>
                  <button id="delete_all" class="danger">${this._esc(this._t("buttons.clear_all","Clear all"))}</button>
                </div>

                ${this._renderGallery()}
              </div>
            `
        }
      </div>
    `;


    const opt = root.getElementById("open_options");
    if (opt) opt.onclick = () => this._openOptions();


    // bindings common
    const btn = root.getElementById("refresh");
    if (btn) btn.onclick = async () => {
      await this._syncFaceGalleryFromS3();
      await this._refreshAll();
    };

    const delAll = root.getElementById("delete_all");
    if (delAll) delAll.onclick = () => this._deleteAll();

    // tabs
    root.querySelectorAll("[data-tab]").forEach((el) => {
      el.onclick = () => this._setTab(el.getAttribute("data-tab"));
    });

    // upload inputs
    const nameInput = root.getElementById("name");
    if (nameInput) nameInput.oninput = (e) => this._onNameInput(e);

    const fileInput = root.getElementById("file");
    if (fileInput) fileInput.onchange = (e) => this._onFileInput(e);

    const uploadBtn = root.getElementById("upload");
    if (uploadBtn) uploadBtn.onclick = () => this._upload();

    // deletes
    root.querySelectorAll("[data-del-img]").forEach((el) => {
      el.onclick = () => this._deleteImage(el.getAttribute("data-del-img"));
    });
    root.querySelectorAll("[data-del-name]").forEach((el) => {
      el.onclick = () => this._deleteName(el.getAttribute("data-del-name"));
    });

    // plates bindings
    const plateInput = root.getElementById("plate");
    if (plateInput) plateInput.oninput = (e) => this._onPlateInput(e);

    const plateNameInput = root.getElementById("plate_name");
    if (plateNameInput) plateNameInput.oninput = (e) => this._onPlateNameInput(e);

    const plateAdd = root.getElementById("plate_add");
    if (plateAdd) plateAdd.onclick = () => this._addPlateMapping();

    root.querySelectorAll("[data-del-plate]").forEach((el) => {
      el.onclick = () => this._deletePlateMapping(el.getAttribute("data-del-plate"));
    });

    // ROI tab bindings (IMPORTANT: do AFTER innerHTML)
    if (this._tab === "roi") {
      // Premium camera picker
    const btn = root.getElementById("roi_cam_btn");
    const menu = root.getElementById("roi_cam_menu");
    const labelEl = root.getElementById("roi_cam_label");
    const search = root.getElementById("roi_cam_search");
    const list = root.getElementById("roi_cam_list");

    if (btn && menu && labelEl && search && list) {
      const cams = this._listCameras();
      this._ensureRoiCamera();

      const renderList = (q) => {
        const qq = String(q || "").toLowerCase().trim();
        const filtered = !qq
          ? cams
          : cams.filter((id) => {
              const fn = this._hass?.states?.[id]?.attributes?.friendly_name || "";
              return id.toLowerCase().includes(qq) || String(fn).toLowerCase().includes(qq);
            });

        list.innerHTML = filtered.map((id) => {
          const fn = this._hass?.states?.[id]?.attributes?.friendly_name || id;
          const active = id === this._roiCamera ? "active" : "";
          return `
            <div class="cam-item ${active}" data-cam="${this._esc(id)}">
              <div class="name">${this._esc(fn)}</div>
              <div class="muted">${this._esc(id)}</div>
            </div>
          `;
        }).join("");

        list.querySelectorAll("[data-cam]").forEach((el) => {
          el.onclick = async () => {
            const v = el.getAttribute("data-cam");
            if (!v || v === this._roiCamera) {
              menu.hidden = true;
              return;
            }
            this._roiCamera = v;
            this._roiSelectedId = null;
            menu.hidden = true;
            await this._setRoiImageSrc(this._roiCamera);
            this._scheduleRender();
          };
        });
      };

      const updateLabel = () => {
        const fn = this._hass?.states?.[this._roiCamera]?.attributes?.friendly_name || this._roiCamera || "";
        labelEl.textContent = fn || "Select camera…";
      };

      updateLabel();
      renderList("");

      btn.onclick = () => {
        menu.hidden = !menu.hidden;
        if (!menu.hidden) {
          search.value = "";
          renderList("");
          setTimeout(() => search.focus(), 0);
        }
      };

      search.oninput = () => renderList(search.value);

      // close on outside click
      const onDocClick = (ev) => {
        if (!root.contains(ev.target)) {
          menu.hidden = true;
          document.removeEventListener("click", onDocClick, true);
        }
      };
      if (!menu.hidden) document.addEventListener("click", onDocClick, true);
      btn.addEventListener("click", () => document.addEventListener("click", onDocClick, true), { once: true });
    }









      const img = root.getElementById("roi_img");
      if (img) {
        img.onload = () => this._updateRoiDom();
      }

      const sel = root.getElementById("roi_camera");
      if (sel) {
        const cams = this._listCameras();

        sel.innerHTML = cams
          .map((id) => {
            const fn = this._hass?.states?.[id]?.attributes?.friendly_name || id;
            const selected = id === this._roiCamera ? "selected" : "";
            return `<option value="${this._esc(id)}" ${selected}>${this._esc(fn)}</option>`;
          })
          .join("");

        sel.onchange = async () => {
          const v = String(sel.value || "");
          if (!v || v === this._roiCamera) return;
          this._roiCamera = v;
          this._roiSelectedId = null;
          await this._setRoiImageSrc(this._roiCamera);
          this._scheduleRender();
        };
      }


      const refreshImg = root.getElementById("roi_refresh_img");
      if (refreshImg) {
        refreshImg.onclick = async () => {
          this._roiImgBuster = Date.now();
          await this._setRoiImageSrc(this._roiCamera);
        };
      }

      const delBtn = root.getElementById("roi_delete");
      if (delBtn) delBtn.onclick = () => this._roiDeleteSelected();

      const overlay = root.getElementById("roi_overlay");
      if (overlay) {
        overlay.onmousedown = (ev) => this._roiOnMouseDown(ev);
        overlay.onmousemove = (ev) => this._roiOnMouseMove(ev);
        overlay.onmouseup = (ev) => this._roiOnMouseUp(ev);
        overlay.onmouseleave = (ev) => this._roiOnMouseUp(ev);

        // initial draw after DOM is ready
        requestAnimationFrame(() => this._updateRoiDom());
      }

      // list selection
      root.querySelectorAll("[data-roi-sel]").forEach((el) => {
        el.onclick = () => {
          this._roiSelectedId = el.getAttribute("data-roi-sel");
          this._updateRoiDom();
        };
      });

      // rename: avoid render while typing
      root.querySelectorAll("[data-roi-name]").forEach((el) => {
        el.onfocus = () => { this._roiNameEditing = true; };
        el.onblur = () => {
          this._roiNameEditing = false;
          this._applyPendingRoiUpdateIfAny();
        };
        el.onchange = () => this._roiRename(el.getAttribute("data-roi-name"), el.value);
      });
    }
  }
}

customElements.define("afr-panel", AfrPanel);
