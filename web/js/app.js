/**
 * SkinMyBird web editor — multi-aircraft selector + live preview + API export.
 * UI labels in Romanian.
 */
(function () {
  const $ = (id) => document.getElementById(id);

  const state = {
    profiles: [],
    profile: null,
    colors: {
      fuselage: "#FF6A00",
      wings: "#111111",
      engines: "#222222",
      tail: "#FF6A00",
    },
    name: "Eugen Orange",
    registration: "YR-EUG",
    airline: "SkinMyBird",
    stickerText: "YR-EUG",
    stickers: { stripe: true, heart: false, text: true },
    soacra: null,
    soacraName: null,
    soacraFile: null,
    lastPackage: null,
  };

  const EUGEN = {
    fuselage: "#FF6A00",
    wings: "#111111",
    engines: "#222222",
    tail: "#FF6A00",
    name: "Eugen Orange",
    registration: "YR-EUG",
    airline: "SkinMyBird",
    stickerText: "YR-EUG",
  };

  const CAT_ICON = {
    avion: "✈️",
    elicopter: "🚁",
    balon: "🎈",
  };

  function syncInputsFromState() {
    $("c-fuselage").value = state.colors.fuselage;
    $("c-wings").value = state.colors.wings;
    $("c-engines").value = state.colors.engines;
    $("c-tail").value = state.colors.tail;
    $("livery-name").value = state.name;
    $("registration").value = state.registration;
    $("airline").value = state.airline;
    $("sticker-text").value = state.stickerText;
    $("st-stripe").checked = state.stickers.stripe;
    $("st-heart").checked = state.stickers.heart;
    $("st-text").checked = state.stickers.text;
  }

  function readInputs() {
    state.colors.fuselage = $("c-fuselage").value;
    state.colors.wings = $("c-wings").value;
    state.colors.engines = $("c-engines").value;
    state.colors.tail = $("c-tail").value;
    state.name = $("livery-name").value.trim() || "Custom";
    state.registration = $("registration").value.trim() || "SMB-001";
    state.airline = $("airline").value.trim() || "SkinMyBird";
    state.stickerText = $("sticker-text").value.trim() || state.registration;
    state.stickers.stripe = $("st-stripe").checked;
    state.stickers.heart = $("st-heart").checked;
    state.stickers.text = $("st-text").checked;
  }

  function slugify(t) {
    return (
      t
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_|_$/g, "") || "livery"
    );
  }

  function buildConfig() {
    readInputs();
    return {
      id: slugify(state.name),
      name: state.name,
      registration: state.registration,
      airline: state.airline,
      icao: "SMB",
      profile: state.profile ? state.profile.id : "asobo-aircraft-a320-neo",
      colors: { ...state.colors },
      stickers: [
        { type: "team_stripe", enabled: state.stickers.stripe },
        { type: "heart", enabled: state.stickers.heart },
        {
          type: "custom_text",
          enabled: state.stickers.text,
          text: state.stickerText,
        },
      ],
      soacraPhoto: state.soacraName,
    };
  }

  function setStatus(msg, detail) {
    $("status-line").innerHTML = msg;
    const log = $("status-log");
    if (detail) {
      log.hidden = false;
      log.textContent = typeof detail === "string" ? detail : JSON.stringify(detail, null, 2);
    }
  }

  function updateSwatches() {
    const el = $("swatches");
    const entries = [
      ["Corp", state.colors.fuselage],
      ["Aripi", state.colors.wings],
      ["Motoare", state.colors.engines],
      ["Coadă", state.colors.tail],
    ];
    el.innerHTML = entries
      .map(
        ([label, c]) =>
          `<span class="swatch"><i style="background:${c}"></i>${label} ${c.toUpperCase()}</span>`
      )
      .join("");
  }

  function roundRect(ctx, x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.arcTo(x + w, y, x + w, y + h, rr);
    ctx.arcTo(x + w, y + h, x, y + h, rr);
    ctx.arcTo(x, y + h, x, y, rr);
    ctx.arcTo(x, y, x + w, y, rr);
    ctx.closePath();
  }

  function drawHeart(ctx, cx, cy, s, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(cx, cy + s * 0.3);
    ctx.bezierCurveTo(cx, cy, cx - s, cy, cx - s, cy + s * 0.35);
    ctx.bezierCurveTo(cx - s, cy + s * 0.8, cx, cy + s * 1.1, cx, cy + s * 1.4);
    ctx.bezierCurveTo(cx, cy + s * 1.1, cx + s, cy + s * 0.8, cx + s, cy + s * 0.35);
    ctx.bezierCurveTo(cx + s, cy, cx, cy, cx, cy + s * 0.3);
    ctx.fill();
  }

  function drawAirliner(ctx, W, H) {
    const fus = state.colors.fuselage;
    const wing = state.colors.wings;
    const eng = state.colors.engines;
    const tail = state.colors.tail;
    const cy = H * 0.55;
    // wing far
    ctx.fillStyle = wing;
    ctx.beginPath();
    ctx.moveTo(W * 0.35, cy - 10);
    ctx.lineTo(W * 0.22, cy - 90);
    ctx.lineTo(W * 0.28, cy - 70);
    ctx.lineTo(W * 0.42, cy);
    ctx.fill();
    // fuselage
    ctx.fillStyle = fus;
    roundRect(ctx, W * 0.12, cy - 38, W * 0.62, 76, 38);
    ctx.fill();
    // nose
    ctx.beginPath();
    ctx.ellipse(W * 0.12, cy, 36, 36, 0, 0, Math.PI * 2);
    ctx.fill();
    // near wing + engines
    ctx.fillStyle = wing;
    ctx.beginPath();
    ctx.moveTo(W * 0.38, cy + 10);
    ctx.lineTo(W * 0.58, cy + 70);
    ctx.lineTo(W * 0.62, cy + 90);
    ctx.lineTo(W * 0.36, cy + 35);
    ctx.fill();
    ctx.fillStyle = eng;
    roundRect(ctx, W * 0.4, cy + 28, 70, 42, 16);
    ctx.fill();
    roundRect(ctx, W * 0.5, cy + 38, 60, 36, 14);
    ctx.fill();
    // windows
    ctx.fillStyle = "#1e2838";
    for (let i = 0; i < 14; i++) {
      roundRect(ctx, W * 0.2 + i * 32, cy - 18, 18, 14, 4);
      ctx.fill();
    }
    // tail
    ctx.fillStyle = tail;
    ctx.beginPath();
    ctx.moveTo(W * 0.7, cy - 30);
    ctx.lineTo(W * 0.74, cy - 140);
    ctx.lineTo(W * 0.84, cy - 140);
    ctx.lineTo(W * 0.78, cy - 30);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(W * 0.72, cy);
    ctx.lineTo(W * 0.9, cy - 18);
    ctx.lineTo(W * 0.9, cy + 8);
    ctx.lineTo(W * 0.74, cy + 18);
    ctx.fill();
  }

  function drawHelicopter(ctx, W, H) {
    const fus = state.colors.fuselage;
    const wing = state.colors.wings;
    const eng = state.colors.engines;
    const tail = state.colors.tail;
    const cx = W * 0.45;
    const cy = H * 0.55;
    ctx.strokeStyle = wing;
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(cx, cy - 110, 90, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx, cy - 110);
    ctx.lineTo(cx, cy - 40);
    ctx.stroke();
    ctx.fillStyle = fus;
    roundRect(ctx, cx - 140, cy - 40, 300, 90, 36);
    ctx.fill();
    ctx.fillStyle = tail;
    ctx.beginPath();
    ctx.moveTo(cx + 140, cy - 10);
    ctx.lineTo(cx + 280, cy - 5);
    ctx.lineTo(cx + 280, cy + 25);
    ctx.lineTo(cx + 140, cy + 30);
    ctx.fill();
    ctx.fillStyle = eng;
    roundRect(ctx, cx - 40, cy + 45, 90, 28, 8);
    ctx.fill();
    ctx.fillStyle = "#1e2838";
    roundRect(ctx, cx - 120, cy - 25, 55, 30, 8);
    ctx.fill();
  }

  function drawBalloon(ctx, W, H) {
    const fus = state.colors.fuselage;
    const wing = state.colors.wings;
    const eng = state.colors.engines;
    const tail = state.colors.tail;
    const cx = W * 0.5;
    const cy = H * 0.42;
    ctx.fillStyle = fus;
    ctx.beginPath();
    ctx.ellipse(cx, cy, 140, 170, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = tail;
    ctx.lineWidth = 3;
    for (let i = -2; i <= 2; i++) {
      ctx.beginPath();
      ctx.ellipse(cx + i * 6, cy, 140, 170, 0, -1.2, 1.2);
      ctx.stroke();
    }
    ctx.fillStyle = wing;
    ctx.beginPath();
    ctx.moveTo(cx - 35, cy + 150);
    ctx.lineTo(cx + 35, cy + 150);
    ctx.lineTo(cx + 48, cy + 210);
    ctx.lineTo(cx - 48, cy + 210);
    ctx.fill();
    ctx.fillStyle = eng;
    roundRect(ctx, cx - 42, cy + 210, 84, 40, 6);
    ctx.fill();
  }

  function drawPreview() {
    readInputs();
    updateSwatches();
    const canvas = $("preview");
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const sky = ctx.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#0e182c");
    sky.addColorStop(0.55, "#0a1220");
    sky.addColorStop(1, "#070c14");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, H);

    // ground haze
    ctx.fillStyle = "rgba(255,255,255,0.04)";
    ctx.fillRect(0, H * 0.78, W, H * 0.22);

    const sil = (state.profile && state.profile.silhouette) || "airliner";
    if (sil === "helicopter") drawHelicopter(ctx, W, H);
    else if (sil === "balloon") drawBalloon(ctx, W, H);
    else drawAirliner(ctx, W, H);

    if (state.stickers.stripe && sil === "airliner") {
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(W * 0.2, H * 0.55 + 28, W * 0.45, 10);
      ctx.fillStyle = state.colors.tail;
      ctx.fillRect(W * 0.2, H * 0.55 + 38, W * 0.45, 8);
    }
    if (state.stickers.heart) {
      drawHeart(ctx, W * 0.32, H * 0.42, 28, "#dc2840");
    }
    if (state.stickers.text) {
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 28px Segoe UI, sans-serif";
      ctx.fillText(state.stickerText || state.registration, W * 0.22, H * 0.52);
    }
    if (state.soacra) {
      const s = 70;
      ctx.drawImage(state.soacra, W * 0.45, H * 0.58, s, s);
    }

    // labels
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.font = "600 18px Segoe UI, sans-serif";
    const title = state.profile
      ? state.profile.displayName
      : "Alege un model";
    ctx.fillText(title, 24, 36);
    ctx.font = "14px Segoe UI, sans-serif";
    ctx.fillStyle = "rgba(200,210,230,0.7)";
    ctx.fillText(`${state.name} · ${state.registration}`, 24, 58);
  }

  function renderModelCards() {
    const grid = $("model-grid");
    if (!state.profiles.length) {
      grid.innerHTML =
        '<p class="hint-block">Nu am găsit profile. Pornește serverul: <code>python server.py</code></p>';
      return;
    }
    grid.innerHTML = state.profiles
      .map((p) => {
        const icon = CAT_ICON[p.category] || "✈️";
        const mode = p.has_uv ? "UV măsurat" : "whole-albedo";
        const active =
          state.profile && state.profile.id === p.id ? " active" : "";
        return `<button type="button" class="model-card${active}" data-id="${p.id}">
          <span class="mc-icon">${icon}</span>
          <span class="mc-name">${p.displayName}</span>
          <span class="mc-meta">${p.ui_manufacturer || ""} · ${mode}</span>
          <span class="mc-cat">${p.category}</span>
        </button>`;
      })
      .join("");

    grid.querySelectorAll(".model-card").forEach((btn) => {
      btn.addEventListener("click", () => selectProfile(btn.getAttribute("data-id")));
    });
  }

  function selectProfile(id) {
    const p = state.profiles.find((x) => x.id === id);
    if (!p) return;
    state.profile = p;
    $("selector").hidden = true;
    $("editor").hidden = false;
    $("selected-model-label").textContent = `${CAT_ICON[p.category] || ""} ${p.displayName}`;
    $("preview-sub").textContent = `${p.displayName} · ${
      p.has_uv ? "UV" : "whole-albedo stub"
    }`;
    $("mode-badge").textContent = p.has_uv ? "UV + DDS" : "Stub + DDS";
    $("paint-mode-note").innerHTML = p.has_uv
      ? `Profil cu <strong>UV</strong>. Export → <code>*.PNG.DDS</code> BC7.`
      : `UV necunoscut — <strong>whole-albedo</strong> + logo centrat. Vezi ASSUMPTIONS.md.`;
    renderModelCards();
    drawPreview();
    setStatus(
      `Model: <strong>${p.displayName}</strong>. Pictează, apoi Export ZIP.`
    );
  }

  function showSelector() {
    state.profile = null;
    $("selector").hidden = false;
    $("editor").hidden = true;
    renderModelCards();
  }

  async function loadProfiles() {
    try {
      const res = await fetch("/api/profiles");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      state.profiles = data.profiles || [];
      renderModelCards();
      setStatus(`Încărcate <strong>${state.profiles.length}</strong> profile.`);
    } catch (err) {
      // Fallback: static list if opened via plain http.server
      state.profiles = FALLBACK_PROFILES;
      renderModelCards();
      setStatus(
        "API indisponibil — listă statică. Pornește <code>python server.py</code> pentru Export DDS.",
        String(err)
      );
    }
  }

  const FALLBACK_PROFILES = [
    { id: "asobo-aircraft-a320-neo", displayName: "Asobo A320neo", category: "avion", has_uv: true, silhouette: "airliner", ui_manufacturer: "Airbus" },
    { id: "lvfr-airbus-a319-ceo", displayName: "LatinVFR A319 CEO", category: "avion", has_uv: true, silhouette: "airliner", ui_manufacturer: "Airbus" },
    { id: "lvfr-airbus-a321-neo", displayName: "LatinVFR A321neo", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Airbus" },
    { id: "lvfr-a330-900", displayName: "LatinVFR A330-900", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Airbus" },
    { id: "flybywire-aircraft-a320-neo", displayName: "FlyByWire A320neo", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Airbus" },
    { id: "asobo-boeing-787-10", displayName: "Asobo Boeing 787-10", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Boeing" },
    { id: "asobo-aircraft-b7478i", displayName: "Asobo Boeing 747-8i", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Boeing" },
    { id: "pmdg-aircraft-736", displayName: "PMDG 737-600", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Boeing" },
    { id: "hpg-hotair-balloon", displayName: "HPG Hot Air Balloon", category: "balon", has_uv: false, silhouette: "balloon", ui_manufacturer: "HPG" },
    { id: "hpg-airbus-h135", displayName: "HPG Airbus H135", category: "elicopter", has_uv: false, silhouette: "helicopter", ui_manufacturer: "Airbus Helicopters" },
  ];

  function setBusy(busy, label) {
    ["btn-export", "btn-export-2", "btn-install", "btn-install-2"].forEach((id) => {
      const b = $(id);
      if (!b) return;
      b.disabled = busy;
    });
    if (busy) setStatus(label || "Se lucrează…");
  }

  async function doExport() {
    if (!state.profile) {
      alert("Alege mai întâi un model.");
      return;
    }
    readInputs();
    setBusy(true, "Se exportă pachetul Community (DDS)…");
    try {
      const payload = {
        profile_id: state.profile.id,
        name: state.name,
        registration: state.registration,
        airline: state.airline,
        icao: "SMB",
        colors: state.colors,
        stickers: [
          { type: "team_stripe", enabled: state.stickers.stripe },
          { type: "heart", enabled: state.stickers.heart },
          {
            type: "custom_text",
            enabled: state.stickers.text,
            text: state.stickerText,
          },
        ],
        make_zip: true,
        force_png: false,
      };

      let res;
      if (state.soacraFile) {
        const fd = new FormData();
        fd.append("profile_id", payload.profile_id);
        fd.append("name", payload.name);
        fd.append("registration", payload.registration);
        fd.append("airline", payload.airline);
        fd.append("icao", payload.icao);
        fd.append("colors_json", JSON.stringify(payload.colors));
        fd.append("stickers_json", JSON.stringify(payload.stickers));
        fd.append("make_zip", "true");
        fd.append("photo", state.soacraFile);
        res = await fetch("/api/export-form", { method: "POST", body: fd });
      } else {
        res = await fetch("/api/export", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      const data = await res.json();
      if (!res.ok || !data.ok) {
        throw new Error(data.detail || data.error || JSON.stringify(data));
      }
      state.lastPackage = data.package_folder;
      setStatus(
        `Export OK: <strong>${data.package_folder}</strong>` +
          (data.used_dds ? " · DDS BC7" : " · PNG (rulează convert_to_dds pe Windows)") +
          (data.download_zip
            ? ` · <a href="${data.download_zip}">Descarcă ZIP</a>`
            : ""),
        data
      );
      if (data.download_zip) {
        const a = document.createElement("a");
        a.href = data.download_zip;
        a.download = "";
        a.click();
      }
    } catch (err) {
      setStatus("Export eșuat.", String(err));
      alert("Eroare export: " + err.message);
    } finally {
      setBusy(false);
    }
  }

  async function doInstall() {
    if (!state.lastPackage) {
      alert("Exportă mai întâi un pachet, apoi Instalează.");
      return;
    }
    setBusy(true, "Se instalează în Community…");
    try {
      const res = await fetch("/api/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ package_folder: state.lastPackage }),
      });
      const data = await res.json();
      if (data.ok) {
        setStatus(`Instalat: <code>${data.installed}</code>`, data);
      } else {
        setStatus(
          "Install pe acest PC nu e disponibil (cale Community lipsă). Copiază manual folderul din <code>output/</code>.",
          data
        );
        alert(
          (data.hint || data.error || "Community path missing") +
            "\n\nPe Windows: pornește SkinMyBird.bat și apasă din nou Instalează."
        );
      }
    } catch (err) {
      setStatus("Install eșuat.", String(err));
      alert("Eroare install: " + err.message);
    } finally {
      setBusy(false);
    }
  }

  function downloadConfig() {
    const cfg = buildConfig();
    const blob = new Blob([JSON.stringify(cfg, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `skinmybird-${cfg.id}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function applyEugen() {
    Object.assign(state.colors, {
      fuselage: EUGEN.fuselage,
      wings: EUGEN.wings,
      engines: EUGEN.engines,
      tail: EUGEN.tail,
    });
    state.name = EUGEN.name;
    state.registration = EUGEN.registration;
    state.airline = EUGEN.airline;
    state.stickerText = EUGEN.stickerText;
    state.stickers = { stripe: true, heart: false, text: true };
    syncInputsFromState();
    drawPreview();
  }

  // Tabs
  document.querySelectorAll(".tool-tabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tool-tabs .tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const id = tab.getAttribute("data-tab");
      document.querySelectorAll(".tab-panel").forEach((p) => {
        const match = p.id === "tab-" + id;
        p.classList.toggle("active", match);
        p.hidden = !match;
      });
    });
  });

  [
    "c-fuselage",
    "c-wings",
    "c-engines",
    "c-tail",
    "livery-name",
    "registration",
    "airline",
    "sticker-text",
    "st-stripe",
    "st-heart",
    "st-text",
  ].forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.addEventListener("input", drawPreview);
    el.addEventListener("change", drawPreview);
  });

  $("soacra").addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    state.soacraName = file.name;
    state.soacraFile = file;
    const img = new Image();
    img.onload = () => {
      state.soacra = img;
      $("soacra-label").textContent = file.name;
      $("btn-clear-photo").hidden = false;
      drawPreview();
    };
    img.src = URL.createObjectURL(file);
  });

  $("btn-clear-photo").addEventListener("click", () => {
    state.soacra = null;
    state.soacraName = null;
    state.soacraFile = null;
    $("soacra").value = "";
    $("soacra-label").textContent = "Încarcă logo sau poză";
    $("btn-clear-photo").hidden = true;
    drawPreview();
  });

  $("btn-preset").addEventListener("click", applyEugen);
  $("btn-preset-2").addEventListener("click", applyEugen);
  $("btn-export").addEventListener("click", doExport);
  $("btn-export-2").addEventListener("click", doExport);
  $("btn-install").addEventListener("click", doInstall);
  $("btn-install-2").addEventListener("click", doInstall);
  $("btn-config").addEventListener("click", downloadConfig);
  $("btn-change-model").addEventListener("click", showSelector);

  syncInputsFromState();
  loadProfiles();
})();
