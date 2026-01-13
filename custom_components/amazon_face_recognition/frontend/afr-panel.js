class AfrPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });

    this._hass = null;
    this._facesIndex = null;
    this._gallery = null;

    this._error = null;
    this._loading = false;

    this._uploadName = "";
    this._uploadFile = null;
    this._uploading = false;
    this._uploadError = null;
    this._uploadOk = null;

    this._rendered = false;

    // thumbnails (auth -> blob url)
    this._thumbUrls = new Map();     // image_id -> blobUrl
    this._thumbLoading = new Set();  // image_id in flight

    // live updates
    this._unsubGallery = null;
  }

  set hass(hass) {
    this._hass = hass;

    // carica una volta
    if (!this._facesIndex && !this._loading) this._loadFacesIndex();
    if (!this._gallery) this._loadGallery();

    // subscribe una volta
    this._subscribeGallery();

    // non ridisegnare ad ogni hass update
    if (!this._rendered) {
      this._rendered = true;
      this._render();
    }
  }

  _getToken() {
    return this._hass?.auth?.data?.access_token || null;
  }

  async _apiDelete(url) {
    const token = this._getToken();
    if (!token) throw new Error("Missing Home Assistant access_token");

    const res = await fetch(url, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
      credentials: "same-origin",
    });

    const txt = await res.text();
    let data;
    try { data = JSON.parse(txt); } catch { data = { raw: txt }; }

    if (!res.ok) {
      throw new Error(data?.message || data?.raw || `Delete failed (${res.status})`);
    }
    return data;
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
        this._render();
    }
    }


  async _loadFacesIndex() {
    if (!this._hass) return;
    this._loading = true;
    this._error = null;
    this._render();

    try {
      const resp = await this._hass.connection.sendMessagePromise({
        type: "amazon_face_recognition/get_faces_index",
      });
      this._facesIndex = resp;
    } catch (e) {
      this._error = e?.message || String(e);
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _loadGallery() {
    if (!this._hass) return;

    try {
      const resp = await this._hass.connection.sendMessagePromise({
        type: "amazon_face_recognition/get_gallery",
      });
      this._gallery = resp;
      this._render();
    } catch (e) {
      console.error("Gallery error", e);
    }
  }

  async _refreshAll() {
    // pulisci cache thumbnails
    for (const url of this._thumbUrls.values()) URL.revokeObjectURL(url);
    this._thumbUrls.clear();
    this._thumbLoading.clear();

    await this._loadFacesIndex();
    await this._loadGallery();
  }

  _subscribeGallery() {
    if (!this._hass || this._unsubGallery) return;

    this._hass.connection
      .subscribeMessage(
        (msg) => {
          const g = msg?.event?.data;
          if (g) {
            this._gallery = g;

            // pulisci thumbs cache (gallery cambiata)
            for (const url of this._thumbUrls.values()) URL.revokeObjectURL(url);
            this._thumbUrls.clear();
            this._thumbLoading.clear();

            this._render();
          }
        },
        { type: "amazon_face_recognition/subscribe_gallery" }
      )
      .then((unsub) => (this._unsubGallery = unsub))
      .catch((e) => console.warn("subscribe_gallery failed", e));
  }

  _onNameInput(e) {
    this._uploadName = (e.target.value || "").trim();
  }

  _onFileInput(e) {
    const files = e.target.files;
    this._uploadFile = files && files.length ? files[0] : null;
  }

  async _deleteImage(imageId) {
    try {
        await this._apiDelete(`/api/amazon_face_recognition/gallery/image/${encodeURIComponent(imageId)}`);
        await this._refreshAll();
    } catch (e) {
        this._uploadError = e?.message || String(e);
        this._render();
    }
    }

    async _deleteName(name) {
        const ok = confirm(
            "⚠️ ATTENZIONE\n\n" +
            `Se procedi verranno eliminate TUTTE le foto e TUTTI i volti associati a:\n` +
            `"${name}"\n` +
            "l'eoperazione è irreversibile." +
            "Vuoi continuare?"
        );

        if (!ok) return;

        try {
            await this._apiDelete(
            `/api/amazon_face_recognition/gallery/manage?mode=name&name=${encodeURIComponent(name)}`
            );
            await this._refreshAll();
        } catch (e) {
            this._uploadError = e?.message || String(e);
            this._render();
        }
        }


  async _upload() {
    if (!this._hass) return;
    this._uploadError = null;
    this._uploadOk = null;

    const name = (this._uploadName || "").trim();
    if (!name) {
      this._uploadError = "Inserisci un nome persona.";
      this._render();
      return;
    }
    if (!this._uploadFile) {
      this._uploadError = "Seleziona un file immagine.";
      this._render();
      return;
    }

    this._uploading = true;
    this._render();

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
        this._uploadOk = `Caricato: ${data.name} (image_id: ${data.image_id})`;
        this._uploadFile = null;

        const fileInput = this.shadowRoot?.getElementById("file");
        if (fileInput) fileInput.value = "";

        await this._refreshAll();
      }
    } catch (e) {
      this._uploadError = e?.message || String(e);
    } finally {
      this._uploading = false;
      this._render();
    }
  }

  async _ensureThumb(imageId) {
    if (!this._hass) return;
    if (this._thumbUrls.has(imageId)) return;
    if (this._thumbLoading.has(imageId)) return;

    const token = this._getToken();
    if (!token) return;

    this._thumbLoading.add(imageId);

    try {
      const res = await fetch(
        `/api/amazon_face_recognition/gallery/image/${encodeURIComponent(imageId)}`,
        {
          method: "GET",
          headers: { Authorization: `Bearer ${token}` },
          credentials: "same-origin",
        }
      );

      if (!res.ok) return;

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      this._thumbUrls.set(imageId, url);
      this._render();
    } catch (e) {
      console.warn("Thumb fetch error", imageId, e);
    } finally {
      this._thumbLoading.delete(imageId);
    }
  }

  _renderGallery() {
    const g = this._gallery || { persons: {} };
    const persons = g.persons || {};
    const names = Object.keys(persons);

    if (!names.length) {
        return `<div class="muted">Nessuna immagine in gallery.</div>`;
    }

    return names
        .sort((a, b) => a.localeCompare(b))
        .map((name) => {
        const items = Array.isArray(persons[name]) ? persons[name] : [];

        return `
            <div class="person">
            <div class="person-h">
                <div>
                <div class="person-name">${this._esc(name)}</div>
                <div class="muted">${items.length} immagine/i</div>
                </div>

                <button class="danger" data-del-name="${this._esc(name)}">
                Elimina persona
                </button>
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
                            : `<div class="thumb-ph">Caricamento...</div>`
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


  _esc(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  _render() {
    const root = this.shadowRoot;
    if (!root) return;

    const facesPersons = this._facesIndex?.persons || {};
    const faceNames = Object.keys(facesPersons);

    root.innerHTML = `
      <style>
        :host { display:block; padding: 16px; }
        .wrap { max-width: 1200px; margin: 0 auto; }
        h1 { margin: 0 0 12px; font-size: 22px; }
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
        .person-h { display:flex; align-items: baseline; justify-content: space-between; margin: 6px 2px; }
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
        .thumb-meta { padding: 8px 10px; font-size: 12px; }

        button.danger {
          border-color: rgba(255,0,0,0.25);
        }

        button.danger {
            border-color: rgba(255,0,0,0.35);
        }

        .thumb-meta {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }

        .thumb-meta button {
            padding: 6px 10px;
            border-radius: 10px;
        }

      </style>

      <div class="wrap">
        <h1>Amazon Face Recognition — Face Gallery</h1>

        <div class="card">
          <div class="row">
            <button id="refresh" ${this._loading ? "disabled" : ""}>Aggiorna</button>
            <div class="muted">
              ${this._facesIndex?.updated_at ? `Faces updated: ${this._facesIndex.updated_at}` : ""}
              ${this._gallery?.updated_at ? ` • Gallery updated: ${this._gallery.updated_at}` : ""}
            </div>
            <div class="spacer"></div>
          </div>

          ${this._loading ? "<div>Caricamento...</div>" : ""}
          ${this._error ? `<div class="err">${this._esc(this._error)}</div>` : ""}

          ${
            !this._loading && !this._error
              ? (faceNames.length
                  ? `<div class="list">
                      ${faceNames.map((n) => {
                        const c = facesPersons[n]?.count ?? 0;
                        return `<div class="item">
                          <div class="name">${this._esc(n)}</div>
                          <div class="meta">${c} face(s) in collection</div>
                        </div>`;
                      }).join("")}
                    </div>`
                  : "<div>Nessun volto in collection.</div>")
              : ""
          }
        </div>

        <div class="card">
          <div class="row">
            <div class="name">Carica foto per training</div>
            <div class="spacer"></div>
          </div>

          <div class="row">
            <input id="name" type="text" placeholder="Nome persona (ExternalImageId)" value="${this._esc(this._uploadName)}" />
            <input id="file" type="file" accept="image/jpeg,image/png" />
            <button id="upload" ${this._uploading ? "disabled" : ""}>
              ${this._uploading ? "Caricamento..." : "Carica"}
            </button>
          </div>

          ${this._uploadError ? `<div class="err">${this._esc(this._uploadError)}</div>` : ""}
          ${this._uploadOk ? `<div class="ok">${this._esc(this._uploadOk)}</div>` : ""}
          <div class="muted">Salva in training_cache e indicizza su Rekognition.</div>
        </div>

        <div class="card">
          <div class="row">
            <div class="name">Galleria (cache locale)</div>
            <div class="spacer"></div>
            <button id="delete_all" class="danger">Svuota tutto</button>
          </div>

          ${this._renderGallery()}
        </div>
      </div>
    `;


    const delAll = root.getElementById("delete_all");
    if (delAll) delAll.onclick = () => this._deleteAll();

    const btn = root.getElementById("refresh");
    if (btn) btn.onclick = () => this._refreshAll();

    const nameInput = root.getElementById("name");
    if (nameInput) nameInput.oninput = (e) => this._onNameInput(e);

    const fileInput = root.getElementById("file");
    if (fileInput) fileInput.onchange = (e) => this._onFileInput(e);

    const uploadBtn = root.getElementById("upload");
    if (uploadBtn) uploadBtn.onclick = () => this._upload();

    // ✅ DELETE singola immagine (by image_id)
    root.querySelectorAll("[data-del-img]").forEach((el) => {
    el.onclick = () => this._deleteImage(el.getAttribute("data-del-img"));
    });

    // ✅ DELETE persona (by name)
    root.querySelectorAll("[data-del-name]").forEach((el) => {
    el.onclick = () => this._deleteName(el.getAttribute("data-del-name"));
    });

  }
}

customElements.define("afr-panel", AfrPanel);
