/**
 * SkinMyBird web editor v0.4.5 — commercial UI + 3D hangar preview (Three.js).
 * UI labels in Romanian. Keeps /api/export + /api/export-form contracts.
 */
import { Preview3D } from "./preview3d.js";

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
    slogan: "",
    stickerText: "YR-EUG",
    textColor: "#FFFFFF",
    textSize: "M",
    textStyle: "bold",
    textFont: "segoe",
    textPlacement: "fuselage",
    stickers: {
      stripe: true,
      heart: false,
      text: true,
      star: false,
      lightning: false,
      bird: false,
      roundel: false,
      chevron: false,
      checkered: false,
    },
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
    slogan: "Fly Orange",
    stickerText: "YR-EUG",
    textColor: "#FFFFFF",
    textSize: "M",
    textStyle: "bold",
    textFont: "segoe",
    textPlacement: "fuselage",
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
    $("slogan").value = state.slogan || "";
    $("text-color").value = state.textColor;
    $("text-size").value = state.textSize;
    $("text-style").value = state.textStyle;
    if ($("text-font")) $("text-font").value = state.textFont || "segoe";
    $("text-placement").value = state.textPlacement;
    $("st-stripe").checked = !!state.stickers.stripe;
    $("st-heart").checked = !!state.stickers.heart;
    $("st-text").checked = !!state.stickers.text;
    if ($("st-star")) $("st-star").checked = !!state.stickers.star;
    if ($("st-lightning")) $("st-lightning").checked = !!state.stickers.lightning;
    if ($("st-bird")) $("st-bird").checked = !!state.stickers.bird;
    if ($("st-roundel")) $("st-roundel").checked = !!state.stickers.roundel;
    if ($("st-chevron")) $("st-chevron").checked = !!state.stickers.chevron;
    if ($("st-checkered")) $("st-checkered").checked = !!state.stickers.checkered;
    updateHexLabels();
    syncSegmented("data-size", state.textSize);
    syncSegmented("data-style", state.textStyle);
    syncSegmented("data-place", state.textPlacement);
  }

  function syncSegmented(attr, value) {
    document.querySelectorAll(`[${attr}]`).forEach((btn) => {
      const v = btn.getAttribute(attr);
      btn.classList.toggle("active", v === value);
    });
  }

  function updateHexLabels() {
    const map = {
      fuselage: "hex-fuselage",
      wings: "hex-wings",
      engines: "hex-engines",
      tail: "hex-tail",
    };
    Object.keys(map).forEach((k) => {
      const el = $(map[k]);
      if (el) el.textContent = state.colors[k].toUpperCase();
    });
  }

  function readInputs() {
    state.colors.fuselage = $("c-fuselage").value;
    state.colors.wings = $("c-wings").value;
    state.colors.engines = $("c-engines").value;
    state.colors.tail = $("c-tail").value;
    state.name = $("livery-name").value.trim() || "Custom";
    state.registration = $("registration").value.trim() || "SMB-001";
    state.airline = $("airline").value.trim() || "SkinMyBird";
    state.slogan = ($("slogan").value || "").trim();
    state.textColor = $("text-color").value || "#FFFFFF";
    state.textSize = $("text-size").value || "M";
    state.textStyle = $("text-style").value || "bold";
    state.textFont = ($("text-font") && $("text-font").value) || "segoe";
    state.textPlacement = $("text-placement").value || "fuselage";
    // custom_text payload: slogan if set, else registration (legacy sticker-text behaviour)
    state.stickerText = state.slogan || state.registration;
    state.stickers.stripe = $("st-stripe").checked;
    state.stickers.heart = $("st-heart").checked;
    state.stickers.text = $("st-text").checked;
    state.stickers.star = $("st-star") ? $("st-star").checked : false;
    state.stickers.lightning = $("st-lightning") ? $("st-lightning").checked : false;
    state.stickers.bird = $("st-bird") ? $("st-bird").checked : false;
    state.stickers.roundel = $("st-roundel") ? $("st-roundel").checked : false;
    state.stickers.chevron = $("st-chevron") ? $("st-chevron").checked : false;
    state.stickers.checkered = $("st-checkered") ? $("st-checkered").checked : false;
    updateHexLabels();
  }

  function slugify(t) {
    return (
      t
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_|_$/g, "") || "livery"
    );
  }

  function buildStickersPayload() {
    const list = [
      { type: "team_stripe", enabled: state.stickers.stripe },
      { type: "heart", enabled: state.stickers.heart },
      { type: "star", enabled: !!state.stickers.star },
      { type: "lightning", enabled: !!state.stickers.lightning },
      { type: "bird", enabled: !!state.stickers.bird },
      { type: "roundel", enabled: !!state.stickers.roundel },
      { type: "chevron", enabled: !!state.stickers.chevron },
      { type: "checkered", enabled: !!state.stickers.checkered },
      {
        type: "custom_text",
        enabled: state.stickers.text,
        text: state.stickerText,
        color: state.textColor,
        size: state.textSize,
        style: state.textStyle,
        font: state.textFont,
        placement: state.textPlacement,
      },
    ];
    return list;
  }

  function buildConfig() {
    readInputs();
    return {
      id: slugify(state.name),
      name: state.name,
      registration: state.registration,
      airline: state.airline,
      slogan: state.slogan,
      icao: "SMB",
      profile: state.profile ? state.profile.id : "asobo-aircraft-a320-neo",
      colors: { ...state.colors },
      text: {
        color: state.textColor,
        size: state.textSize,
        style: state.textStyle,
        font: state.textFont,
        placement: state.textPlacement,
      },
      stickers: buildStickersPayload(),
      soacraPhoto: state.soacraName,
    };
  }

  function setStatus(msg, detail) {
    $("status-line").innerHTML = msg;
    const log = $("status-log");
    if (detail) {
      log.hidden = false;
      log.textContent =
        typeof detail === "string" ? detail : JSON.stringify(detail, null, 2);
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
          `<span class="swatch"><i style="background:${c}"></i>${label}</span>`
      )
      .join("");
  }

  function updateLayers() {
    const list = $("layer-list");
    if (!state.profile) {
      list.innerHTML = '<li class="layer empty">Niciun model selectat</li>';
      return;
    }
    const items = [
      { on: true, label: "Fuselaj", meta: state.colors.fuselage, color: state.colors.fuselage },
      { on: true, label: "Aripi", meta: state.colors.wings, color: state.colors.wings },
      { on: true, label: "Motoare", meta: state.colors.engines, color: state.colors.engines },
      { on: true, label: "Coadă", meta: state.colors.tail, color: state.colors.tail },
      { on: state.stickers.stripe, label: "Bandă echipă", meta: "" },
      { on: state.stickers.heart, label: "Inimă", meta: "" },
      { on: state.stickers.star, label: "Stea", meta: "" },
      { on: state.stickers.lightning, label: "Fulger", meta: "" },
      { on: state.stickers.bird, label: "Pasăre", meta: "" },
      { on: state.stickers.roundel, label: "Cercuri", meta: "" },
      { on: state.stickers.chevron, label: "Săgeți", meta: "" },
      { on: state.stickers.checkered, label: "Damier", meta: "" },
      {
        on: state.stickers.text,
        label: "Text",
        meta: (state.textFont || "segoe") + " · " + state.textPlacement,
      },
      { on: !!state.soacra, label: "Logo / poză", meta: state.soacraName || "" },
    ];
    list.innerHTML = items
      .map(
        (it) =>
          `<li class="layer"><span class="dot${it.on ? "" : " off"}" style="${
            it.color && it.on ? "background:" + it.color : ""
          }"></span><span>${it.label}</span>${
            it.meta ? `<span class="meta">${it.meta}</span>` : ""
          }</li>`
      )
      .join("");

    const sum = $("id-summary");
    if (sum) {
      sum.innerHTML = `
        <div><strong>${state.name}</strong></div>
        <div>${state.airline} · ${state.registration}</div>
        <div>${state.slogan ? "„" + state.slogan + "”" : "Fără slogan"}</div>
        <div style="margin-top:0.35rem;color:var(--faint)">${
          state.profile.displayName
        }</div>`;
    }
  }


  // ——— 3D hangar preview ———
  let preview3d = null;

  function ensurePreview3D() {
    if (preview3d) return preview3d;
    const canvas = $("preview3d");
    const stage = $("stage");
    const fallback = $("stage-fallback");
    if (!canvas || !stage) return null;
    preview3d = new Preview3D(canvas, stage);
    const ok = preview3d.init();
    if (!ok) {
      canvas.hidden = true;
      if (fallback) fallback.hidden = false;
      const hint = $("stage-hint");
      if (hint) hint.hidden = true;
      return null;
    }
    if (fallback) fallback.hidden = true;
    return preview3d;
  }

  function drawPreview() {
    readInputs();
    updateSwatches();
    updateLayers();

    const p3 = ensurePreview3D();
    if (p3 && p3.ok) {
      if (state.profile) {
        p3.setProfile(state.profile, state);
        const empty = $("stage-empty");
        if (empty) empty.hidden = true;
      } else {
        p3.setProfile(null, state);
        const empty = $("stage-empty");
        if (empty) empty.hidden = false;
      }
    }

    const cfgPrev = $("config-preview");
    if (cfgPrev && $("advanced-drawer") && !$("advanced-drawer").hidden) {
      cfgPrev.textContent = JSON.stringify(buildConfig(), null, 2);
    }
  }

  function renderModelCards() {
    const grid = $("model-grid");
    if (!state.profiles.length) {
      grid.innerHTML =
        '<div class="empty-state"><div class="empty-icon">✈</div><p>Nu am găsit profile. Pornește serverul: <code>python server.py</code></p></div>';
      return;
    }
    grid.innerHTML = state.profiles
      .map((p) => {
        const icon = CAT_ICON[p.category] || "✈️";
        const mode = p.has_uv ? "UV" : "stub";
        const active =
          state.profile && state.profile.id === p.id ? " active" : "";
        return `<button type="button" class="model-card${active}" data-id="${p.id}">
          <div class="mc-top">
            <span class="mc-icon">${icon}</span>
            <span class="mc-mode">${mode}</span>
          </div>
          <span class="mc-name">${p.displayName}</span>
          <span class="mc-meta">${p.ui_manufacturer || "—"}</span>
          <span class="mc-cat">${p.category}</span>
        </button>`;
      })
      .join("");

    grid.querySelectorAll(".model-card").forEach((btn) => {
      btn.addEventListener("click", () =>
        selectProfile(btn.getAttribute("data-id"))
      );
    });
  }

  function selectProfile(id) {
    const p = state.profiles.find((x) => x.id === id);
    if (!p) return;
    state.profile = p;
    $("selector").hidden = true;
    $("editor").hidden = false;
    $("header-model").hidden = false;
    $("header-model-icon").textContent = CAT_ICON[p.category] || "✈️";
    $("header-model-name").textContent = p.displayName;
    $("preview-sub").textContent = `${p.displayName} · ${
      p.has_uv ? "UV măsurat" : "whole-albedo stub"
    }`;
    $("mode-badge").textContent = p.has_uv ? "UV + DDS" : "Stub + DDS";
    $("paint-mode-note").innerHTML = p.has_uv
      ? `Profil cu <strong>UV</strong>. Export → <code>*.PNG.DDS</code> BC7.`
      : `UV necunoscut — <strong>whole-albedo</strong>. Vezi ASSUMPTIONS.md.`;
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
    $("header-model").hidden = true;
    renderModelCards();
    drawPreview();
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
        stickers: buildStickersPayload(),
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
    state.slogan = EUGEN.slogan;
    state.stickerText = EUGEN.stickerText;
    state.textColor = EUGEN.textColor;
    state.textSize = EUGEN.textSize;
    state.textStyle = EUGEN.textStyle;
    state.textPlacement = EUGEN.textPlacement;
    state.textFont = EUGEN.textFont || "segoe";
    state.stickers = {
      stripe: true,
      heart: false,
      text: true,
      star: false,
      lightning: false,
      bird: false,
      roundel: false,
      chevron: false,
      checkered: false,
    };
    syncInputsFromState();
    drawPreview();
    closeMoreMenu();
    setStatus("Preset <strong>Eugen Orange</strong> aplicat.");
  }

  function openAdvanced() {
    closeMoreMenu();
    $("advanced-drawer").hidden = false;
    $("advanced-backdrop").hidden = false;
    $("config-preview").textContent = JSON.stringify(buildConfig(), null, 2);
  }

  function closeAdvanced() {
    $("advanced-drawer").hidden = true;
    $("advanced-backdrop").hidden = true;
  }

  function closeMoreMenu() {
    $("more-menu").hidden = true;
    $("btn-more").setAttribute("aria-expanded", "false");
  }

  // Tabs
  document.querySelectorAll(".tool-tabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tool-tabs .tab").forEach((t) =>
        t.classList.remove("active")
      );
      tab.classList.add("active");
      const id = tab.getAttribute("data-tab");
      document.querySelectorAll(".tab-panel").forEach((p) => {
        const match = p.id === "tab-" + id;
        p.classList.toggle("active", match);
        p.hidden = !match;
      });
    });
  });

  // Segmented controls
  document.querySelectorAll("[data-size]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.textSize = btn.getAttribute("data-size");
      $("text-size").value = state.textSize;
      syncSegmented("data-size", state.textSize);
      drawPreview();
    });
  });
  document.querySelectorAll("[data-style]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.textStyle = btn.getAttribute("data-style");
      $("text-style").value = state.textStyle;
      syncSegmented("data-style", state.textStyle);
      drawPreview();
    });
  });
  document.querySelectorAll("[data-place]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.textPlacement = btn.getAttribute("data-place");
      $("text-placement").value = state.textPlacement;
      syncSegmented("data-place", state.textPlacement);
      drawPreview();
    });
  });
  document.querySelectorAll("[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.viewMode = btn.getAttribute("data-view");
        drawPreview();
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
    "slogan",
    "text-color",
    "text-font",
    "st-stripe",
    "st-heart",
    "st-text",
    "st-star",
    "st-lightning",
    "st-bird",
    "st-roundel",
    "st-chevron",
    "st-checkered",
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

  const drop = $("file-drop");
  if (drop) {
    ["dragenter", "dragover"].forEach((ev) => {
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.add("drag");
      });
    });
    ["dragleave", "drop"].forEach((ev) => {
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.remove("drag");
      });
    });
    drop.addEventListener("drop", (e) => {
      const file = e.dataTransfer && e.dataTransfer.files[0];
      if (!file) return;
      const dt = new DataTransfer();
      dt.items.add(file);
      $("soacra").files = dt.files;
      $("soacra").dispatchEvent(new Event("change"));
    });
  }

  $("btn-clear-photo").addEventListener("click", () => {
    state.soacra = null;
    state.soacraName = null;
    state.soacraFile = null;
    $("soacra").value = "";
    $("soacra-label").textContent = "Trage sau click — logo / poză";
    $("btn-clear-photo").hidden = true;
    drawPreview();
  });

  $("btn-more").addEventListener("click", (e) => {
    e.stopPropagation();
    const menu = $("more-menu");
    const open = menu.hidden;
    menu.hidden = !open;
    $("btn-more").setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.addEventListener("click", (e) => {
    if (!$("more-menu").hidden && !e.target.closest(".menu-wrap")) {
      closeMoreMenu();
    }
  });

  $("btn-preset").addEventListener("click", applyEugen);
  $("btn-advanced").addEventListener("click", openAdvanced);
  $("btn-close-advanced").addEventListener("click", closeAdvanced);
  $("advanced-backdrop").addEventListener("click", closeAdvanced);
  $("btn-export").addEventListener("click", doExport);
  $("btn-export-2").addEventListener("click", doExport);
  $("btn-install").addEventListener("click", doInstall);
  $("btn-install-2").addEventListener("click", doInstall);
  $("btn-config").addEventListener("click", downloadConfig);
  $("btn-change-model").addEventListener("click", showSelector);

  const btnReset = $("btn-reset-camera");
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      const p3 = ensurePreview3D();
      if (p3 && p3.ok) p3.resetCamera();
    });
  }

  syncInputsFromState();
  loadProfiles();
  // Draw empty hangar so canvas isn't blank before selection
  drawPreview();

