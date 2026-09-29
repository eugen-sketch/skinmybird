/**
 * SkinMyBird web editor v0.8.13 — fin logo geometric center (raycast probe) + TAIL19 mid-panel; upright both sides.
 * UI labels in English (worldwide). Keeps /api/export + /api/export-form contracts.
 */
import { Preview3D, resolveGlbMeta } from "./preview3d.js?v=0.8.13";

const $ = (id) => document.getElementById(id);

  // Deep-link: ?plane=<profileId> opens hangar directly (debug + bookmarks)
  function autoSelectFromUrl() {
    try {
      const q = new URLSearchParams(location.search);
      const id = q.get("plane");
      if (!id || !state.profiles.length) return;
      const prof = state.profiles.find((p) => p.id === id);
      if (prof) selectProfile(id);
    } catch (e) {}
  }


  window.addEventListener("skinmybird-model-mode", (ev) => {
    const sub = $("preview-sub");
    if (!sub || !ev.detail) return;
    if (ev.detail.mode === "glb") {
      sub.textContent = "Real 3D model (GLB) · " + (ev.detail.url || "");
      sub.style.color = "#7dffa0";
    } else {
      sub.textContent = "Simple shape (fallback) — GLB not loaded";
      sub.style.color = "#ff8a7a";
    }
  });


  const state = {
    profiles: [],
    profile: null,
    edition: "commercial",
    colors: {
      fuselage: "#f2f4f7",
      nose: "#f2f4f7",
      belly: "#f2f4f7",
      wings: "#1b2430",
      winglet: "#1b2430",
      engines: "#1b2430",
      tail: "#f2f4f7",
      windowband: "#f2f4f7",
    },
    name: "Two-Tone",
    registration: "YR-EUG",
    airline: "SkinMyBird",
    slogan: "",
    stickerText: "",
    textColor: "#1b2430",
    regColor: "#1b2430",
    sloganColor: "#1b2430",
    textSize: "XL",
    textStyle: "bold",
    textFont: "montserrat",
    regFont: "oswald",
    regSize: "M",
    regStyle: "bold",
    sloganFont: "montserrat",
    sloganSize: "L",
    sloganStyle: "bold",
    textPlacement: "fuselage",
    titleZone: "windowband",
    sloganZone: "mid",
    regZone: "aft",
    textPosX: 0,
    textPosY: 0,
    textScale: 200,
    textFlipLeft: false,
    textFlipRight: false,
    stickers: { text: true }, // export compat — no decorative stickers in UI
    stickerSize: "M",
    flags: {
      codes: [],
      placement: "both", // left | right | both | free
      posX: 0,
      posY: 10,
    },
    customTextures: [
      { id: 1, dataUrl: null, name: null, opacity: 100, scale: 100, posX: 0, posY: 0, rotate: 0, side: "both", placement: "tail", tint: "#ffffff", _img: null },
      { id: 2, dataUrl: null, name: null, opacity: 100, scale: 100, posX: 0, posY: 0, rotate: 0, side: "both", placement: "tail", tint: "#ffffff", _img: null },
      { id: 3, dataUrl: null, name: null, opacity: 100, scale: 100, posX: 0, posY: 0, rotate: 0, side: "both", placement: "tail", tint: "#ffffff", _img: null },
    ],
    soacra: null,
    soacraName: null,
    soacraFile: null,
    lastPackage: null,
  };


  const CAT_ICON = {
    avion: "✈️",
    elicopter: "🚁",
    balon: "🎈",
  };

  const CAT_LABEL = {
    avion: "Aircraft",
    elicopter: "Helicopter",
    balon: "Balloon",
  };

  function categoryLabel(cat) {
    return CAT_LABEL[cat] || "Aircraft";
  }

  function syncInputsFromState() {
    $("c-fuselage").value = state.colors.fuselage;
    if ($("c-nose")) $("c-nose").value = state.colors.nose || "#f2f4f7";
    if ($("c-belly")) $("c-belly").value = state.colors.belly || "#f2f4f7";
    $("c-wings").value = state.colors.wings;
    if ($("c-winglet")) $("c-winglet").value = state.colors.winglet || "#1b2430";
    $("c-engines").value = state.colors.engines;
    $("c-tail").value = state.colors.tail;
    if ($("c-windowband")) $("c-windowband").value = state.colors.windowband || state.colors.fuselage || "#f2f4f7";
    $("livery-name").value = state.name;
    $("registration").value = state.registration;
    $("airline").value = state.airline;
    $("slogan").value = state.slogan || "";
    $("text-color").value = state.textColor;
    if ($("reg-color")) $("reg-color").value = state.regColor || state.textColor || "#1b2430";
    if ($("slogan-color")) $("slogan-color").value = state.sloganColor || state.textColor || "#1b2430";
    $("text-size").value = state.textSize;
    $("text-style").value = state.textStyle;
    if ($("text-font")) $("text-font").value = state.textFont || "montserrat";
    if ($("reg-font")) $("reg-font").value = state.regFont || "oswald";
    if ($("slogan-font")) $("slogan-font").value = state.sloganFont || "montserrat";
    if ($("slogan-size")) $("slogan-size").value = state.sloganSize || "L";
    if ($("slogan-style")) $("slogan-style").value = state.sloganStyle || "bold";
    if ($("reg-size")) $("reg-size").value = state.regSize || "M";
    if ($("reg-style")) $("reg-style").value = state.regStyle || "bold";
    if ($("text-placement")) $("text-placement").value = state.textPlacement || "fuselage";
    if ($("title-zone")) $("title-zone").value = state.titleZone || "windowband";
    if ($("slogan-zone")) $("slogan-zone").value = state.sloganZone || "mid";
    if ($("reg-zone")) $("reg-zone").value = state.regZone || "aft";
    if ($("text-pos-x")) $("text-pos-x").value = state.textPosX ?? 0;
    if ($("text-pos-y")) $("text-pos-y").value = state.textPosY ?? 0;
    if ($("text-scale")) $("text-scale").value = state.textScale ?? 200;
    if ($("text-flip-left")) $("text-flip-left").checked = !!state.textFlipLeft;
    if ($("text-flip-right")) $("text-flip-right").checked = !!state.textFlipRight;
    if ($("lab-text-x")) $("lab-text-x").textContent = String(state.textPosX ?? 0);
    if ($("lab-text-y")) $("lab-text-y").textContent = String(state.textPosY ?? 0);
    if ($("lab-text-scale")) $("lab-text-scale").textContent = String(state.textScale ?? 200) + "%";
    updateHexLabels();
    syncSegmented("data-size", state.textSize);
    syncSegmented("data-reg-size", state.regSize || "M");
    syncSegmented("data-reg-style", state.regStyle || "bold");
    syncSegmented("data-style", state.textStyle);
    syncSegmented("data-title-zone", state.titleZone || "windowband");
    syncSegmented("data-slogan-zone", state.sloganZone || "mid");
    syncSegmented("data-slogan-size", state.sloganSize || "L");
    syncSegmented("data-slogan-style", state.sloganStyle || "bold");
    syncSegmented("data-reg-zone", state.regZone || "aft");
    document.querySelectorAll(".flag-check").forEach((el) => {
      el.checked = !!(state.flags && state.flags.codes && state.flags.codes.includes(el.value));
    });
    if ($("flag-placement")) $("flag-placement").value = (state.flags && state.flags.placement) || "both";
    syncSegmented("data-flag-place", (state.flags && state.flags.placement) || "both");
    if ($("flag-pos-x")) $("flag-pos-x").value = (state.flags && state.flags.posX) ?? 0;
    if ($("flag-pos-y")) $("flag-pos-y").value = (state.flags && state.flags.posY) ?? 10;
    if ($("lab-flag-x")) $("lab-flag-x").textContent = String((state.flags && state.flags.posX) ?? 0);
    if ($("lab-flag-y")) $("lab-flag-y").textContent = String((state.flags && state.flags.posY) ?? 10);
    syncFlagCustomPos();
    syncCustomTextureInputs();
  }

  function syncSegmented(attr, value) {
    document.querySelectorAll(`[${attr}]`).forEach((btn) => {
      const v = btn.getAttribute(attr);
      btn.classList.toggle("active", v === value);
    });
  }

  /** Show Free X/Y sliders only when flag placement is "free". */
  function syncFlagCustomPos() {
    const box = $("flag-custom-pos");
    if (!box) return;
    const place = (state.flags && state.flags.placement) || "both";
    const isFree = place === "free";
    box.hidden = !isFree;
    box.setAttribute("aria-hidden", isFree ? "false" : "true");
    ["flag-pos-x", "flag-pos-y"].forEach((id) => {
      const el = $(id);
      if (el) el.disabled = !isFree;
    });
  }

  function updateHexLabels() {
    const map = {
      fuselage: "hex-fuselage",
      nose: "hex-nose",
      belly: "hex-belly",
      wings: "hex-wings",
      winglet: "hex-winglet",
      engines: "hex-engines",
      tail: "hex-tail",
      windowband: "hex-windowband",
    };
    Object.keys(map).forEach((k) => {
      const el = $(map[k]);
      if (el) el.textContent = state.colors[k].toUpperCase();
    });
  }

  function readInputs() {
    state.colors.fuselage = $("c-fuselage").value;
    state.colors.nose = $("c-nose") ? $("c-nose").value : (state.colors.nose || "#f2f4f7");
    state.colors.belly = $("c-belly") ? $("c-belly").value : (state.colors.belly || "#f2f4f7");
    state.colors.wings = $("c-wings").value;
    state.colors.winglet = $("c-winglet") ? $("c-winglet").value : (state.colors.winglet || "#1b2430");
    state.colors.engines = $("c-engines").value;
    state.colors.tail = $("c-tail").value;
    state.colors.windowband = $("c-windowband") ? $("c-windowband").value : (state.colors.windowband || state.colors.fuselage || "#f2f4f7");
    state.name = $("livery-name").value.trim() || "Custom";
    state.registration = $("registration").value.trim() || "SMB-001";
    state.airline = $("airline").value.trim() || "SkinMyBird";
    state.slogan = ($("slogan").value || "").trim();
    state.textColor = $("text-color").value || "#1b2430";
    state.regColor = ($("reg-color") && $("reg-color").value) || state.regColor || state.textColor || "#1b2430";
    state.sloganColor = ($("slogan-color") && $("slogan-color").value) || state.sloganColor || state.textColor || "#1b2430";
    state.textSize = $("text-size").value || "L";
    state.textStyle = $("text-style").value || "bold";
    state.textFont = ($("text-font") && $("text-font").value) || "montserrat";
    state.regFont = ($("reg-font") && $("reg-font").value) || state.regFont || "oswald";
    state.regSize = ($("reg-size") && $("reg-size").value) || state.regSize || "M";
    state.regStyle = ($("reg-style") && $("reg-style").value) || state.regStyle || "bold";
    state.sloganFont = ($("slogan-font") && $("slogan-font").value) || state.sloganFont || "montserrat";
    state.sloganSize = ($("slogan-size") && $("slogan-size").value) || state.sloganSize || "L";
    state.sloganStyle = ($("slogan-style") && $("slogan-style").value) || state.sloganStyle || "bold";
    state.textPlacement = ($("text-placement") && $("text-placement").value) || "fuselage";
    state.titleZone = ($("title-zone") && $("title-zone").value) || state.titleZone || "windowband";
    state.sloganZone = ($("slogan-zone") && $("slogan-zone").value) || state.sloganZone || "mid";
    state.regZone = ($("reg-zone") && $("reg-zone").value) || state.regZone || "aft";
    state.textPosX = $("text-pos-x") ? Number($("text-pos-x").value) : 0;
    state.textPosY = $("text-pos-y") ? Number($("text-pos-y").value) : 0;
    state.textScale = $("text-scale") ? Number($("text-scale").value) : 200;
    state.textFlipLeft = $("text-flip-left") ? $("text-flip-left").checked : false;
    state.textFlipRight = $("text-flip-right") ? $("text-flip-right").checked : false;
    state.stickerText = state.slogan || "";
    state.stickers = state.stickers || {};
    state.stickers.text = true; // always export identity text
    // Flags
    state.flags = state.flags || { codes: [], placement: "both", posX: 0, posY: 10 };
    state.flags.codes = Array.from(document.querySelectorAll(".flag-check:checked")).map((el) => el.value);
    if ($("flag-placement")) state.flags.placement = $("flag-placement").value || "both";
    if ($("flag-pos-x")) {
      const v = Number($("flag-pos-x").value);
      state.flags.posX = Number.isFinite(v) ? v : 0;
    }
    if ($("flag-pos-y")) {
      const v = Number($("flag-pos-y").value);
      state.flags.posY = Number.isFinite(v) ? v : 10;
    }
    if ($("lab-flag-x")) $("lab-flag-x").textContent = String(state.flags.posX);
    if ($("lab-flag-y")) $("lab-flag-y").textContent = String(state.flags.posY);
    readCustomTextureInputs();
    syncFlagCustomPos();
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
    // v0.7.1: decorative stickers removed — export only slogan as custom_text when set
    const list = [];
    list.push({
      type: "custom_text",
      enabled: !!(state.stickerText && String(state.stickerText).trim()),
      text: state.stickerText || "",
      color: state.textColor,
      size: state.textSize,
      style: state.textStyle,
      font: state.textFont,
      placement: state.textPlacement,
    });
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
        regColor: state.regColor,
        sloganColor: state.sloganColor,
        size: state.textSize,
        style: state.textStyle,
        font: state.textFont,
        regFont: state.regFont,
        regSize: state.regSize,
        regStyle: state.regStyle,
        sloganFont: state.sloganFont,
        sloganSize: state.sloganSize,
        sloganStyle: state.sloganStyle,
        placement: state.textPlacement,
        titleZone: state.titleZone,
        sloganZone: state.sloganZone,
        regZone: state.regZone,
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
      ["Fuselage", state.colors.fuselage],
      ["Nose", state.colors.nose],
      ["Belly", state.colors.belly],
      ["Windows", state.colors.windowband],
      ["Wings", state.colors.wings],
      ["Winglets", state.colors.winglet],
      ["Engines", state.colors.engines],
      ["Tail", state.colors.tail],
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
      list.innerHTML = '<li class="layer empty">No model selected</li>';
      return;
    }
    const ctOn = (state.customTextures || []).filter((t) => t && t.dataUrl).length;
    const items = [
      { on: true, label: "Fuselage", meta: state.colors.fuselage, color: state.colors.fuselage },
      { on: true, label: "Nose", meta: state.colors.nose, color: state.colors.nose },
      { on: true, label: "Belly", meta: state.colors.belly, color: state.colors.belly },
      { on: true, label: "Window band", meta: state.colors.windowband, color: state.colors.windowband },
      { on: true, label: "Wings", meta: state.colors.wings, color: state.colors.wings },
      { on: true, label: "Winglets", meta: state.colors.winglet, color: state.colors.winglet },
      { on: true, label: "Engines", meta: state.colors.engines, color: state.colors.engines },
      { on: true, label: "Tail", meta: state.colors.tail, color: state.colors.tail },
      {
        on: !!(state.flags && state.flags.codes && state.flags.codes.length),
        label: "Flags",
        meta: (state.flags && state.flags.codes && state.flags.codes.length)
          ? state.flags.codes.join(", ") + " · " + (state.flags.placement || "both")
          : "",
      },
      {
        on: true,
        label: "Title",
        meta: (state.airline || "") + " · " + (state.titleZone || "windowband") + " · " + (state.textFont || "montserrat"),
      },
      {
        on: !!state.slogan,
        label: "Slogan",
        meta: state.slogan || "",
      },
      {
        on: !!state.registration,
        label: "Registration",
        meta: state.registration || "",
      },
      {
        on: ctOn > 0,
        label: "Custom textures",
        meta: ctOn ? ctOn + " uploaded" : "",
      },
      { on: !!state.soacra, label: "Logo / photo", meta: state.soacraName || "" },
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
        <div>${state.slogan ? "“" + state.slogan + "”" : "No slogan"}</div>
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
        '<div class="empty-state"><div class="empty-icon">✈</div><p>No profiles found. Start the server: <code>python server.py</code></p></div>';
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
          <span class="mc-cat">${categoryLabel(p.category)}</span>
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
      p.has_uv ? "measured UV" : "whole-albedo stub"
    }`;
    $("mode-badge").textContent = p.has_uv ? "UV + DDS" : "Stub + DDS";
    if ($("standin-badge")) {
      try {
        const meta = resolveGlbMeta(p);
        $("standin-badge").hidden = !(meta && meta.standIn);
        if (meta && meta.standIn && meta.note) $("standin-badge").title = meta.note;
      } catch (e) {
        $("standin-badge").hidden = true;
      }
    }
    $("paint-mode-note").innerHTML = p.has_uv
      ? `<strong>UV</strong> profile. Export → <code>*.PNG.DDS</code> BC7.`
      : `Unknown UV — <strong>whole-albedo</strong>. See ASSUMPTIONS.md.`;
    renderModelCards();
    drawPreview();
    setStatus(
      `Model: <strong>${p.displayName}</strong>. Paint, then Export ZIP.`
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

  async function resolveEdition() {
    try {
      let res = await fetch("/api/health");
      if (!res.ok) res = await fetch("/api/edition");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      applyEditionBadge(data.edition || "commercial");
    } catch (err) {
      applyEditionBadge("commercial");
    }
  }

  async function loadProfiles() {
    await resolveEdition();
    try {
      const res = await fetch("/api/profiles");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      state.profiles = data.profiles || [];
      updateProfileCountPill();
      renderModelCards();
      setStatus(`Loaded <strong>${state.profiles.length}</strong> profiles (${state.edition}).`);
      autoSelectFromUrl();
    } catch (err) {
      state.profiles = filterProfilesForEdition(FALLBACK_PROFILES, state.edition);
      updateProfileCountPill();
      renderModelCards();
      autoSelectFromUrl();
      setStatus(
        "API unavailable — static list. Start <code>python server.py</code> for DDS Export.",
        String(err)
      );
    }
  }

  const FALLBACK_PROFILES = [
    { id: "asobo-aircraft-a320-neo", displayName: "Asobo A320neo", category: "avion", has_uv: true, silhouette: "airliner", ui_manufacturer: "Airbus", edition: "commercial" },
    { id: "lvfr-airbus-a319-ceo", displayName: "LatinVFR A319 CEO", category: "avion", has_uv: true, silhouette: "airliner", ui_manufacturer: "Airbus", edition: "commercial" },
    { id: "lvfr-airbus-a321-neo", displayName: "LatinVFR A321neo", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Airbus", edition: "commercial" },
    { id: "lvfr-a330-900", displayName: "LatinVFR A330-900", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Airbus", edition: "commercial" },
    { id: "flybywire-aircraft-a320-neo", displayName: "FlyByWire A320neo", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Airbus", edition: "commercial" },
    { id: "asobo-boeing-787-10", displayName: "Asobo Boeing 787-10", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Boeing", edition: "commercial" },
    { id: "asobo-aircraft-b7478i", displayName: "Asobo Boeing 747-8i", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Boeing", edition: "commercial" },
    { id: "pmdg-aircraft-736", displayName: "PMDG 737-600", category: "avion", has_uv: false, silhouette: "airliner", ui_manufacturer: "Boeing", edition: "commercial" },
    { id: "hpg-hotair-balloon", displayName: "HPG Hot Air Balloon", category: "balon", has_uv: false, silhouette: "balloon", ui_manufacturer: "HPG", edition: "personal" },
    { id: "hpg-airbus-h135", displayName: "HPG Airbus H135", category: "elicopter", has_uv: false, silhouette: "helicopter", ui_manufacturer: "Airbus Helicopters", edition: "personal" },
    { id: "skinmybird-cessna-172-stub", displayName: "Cessna 172 (preview stub)", category: "avion", has_uv: false, silhouette: "ga", ui_manufacturer: "Cessna", edition: "personal" },
  ];

  function filterProfilesForEdition(list, edition) {
    const ed = (edition || "commercial").toLowerCase();
    return (list || []).filter((p) => {
      const tag = (p.edition || "commercial").toLowerCase();
      if (tag === "personal") return ed === "personal";
      return true;
    });
  }

  function applyEditionBadge(edition) {
    state.edition = (edition || "commercial").toLowerCase() === "personal" ? "personal" : "commercial";
    const badge = $("edition-badge");
    if (!badge) return;
    const label = state.edition === "personal" ? "Personal" : "Commercial";
    badge.textContent = label;
    badge.classList.toggle("personal", state.edition === "personal");
    badge.title = state.edition === "personal"
      ? "Personal edition — airliners + helicopter / balloon / GA"
      : "Commercial edition — Airbus + Boeing airliners only";
    document.title = `SkinMyBird — ${label}`;
  }

  function updateProfileCountPill() {
    const pill = $("profile-count-pill");
    if (!pill) return;
    const n = state.profiles.length;
    pill.textContent = `${n} profile${n === 1 ? "" : "s"}`;
  }

  function setBusy(busy, label) {
    ["btn-export", "btn-export-2", "btn-install", "btn-install-2"].forEach((id) => {
      const b = $(id);
      if (!b) return;
      b.disabled = busy;
    });
    if (busy) setStatus(label || "Working…");
  }

  async function doExport() {
    if (!state.profile) {
      alert("Pick a model first.");
      return;
    }
    readInputs();
    setBusy(true, "Exporting Community package (DDS)…");
    try {
      const ct0 = (state.customTextures || []).find((s) => s && s.dataUrl);
      const payload = {
        profile_id: state.profile.id,
        name: state.name,
        registration: state.registration,
        airline: state.airline,
        icao: "SMB",
        colors: state.colors,
        stickers: buildStickersPayload(),
        text: {
          color: state.textColor,
          regColor: state.regColor || state.textColor,
          sloganColor: state.sloganColor || state.textColor,
          size: state.textSize,
          scale: state.textScale,
          font: state.textFont,
          style: state.textStyle,
        },
        textScale: state.textScale ?? 200,
        logoScale: (ct0 && ct0.scale != null) ? ct0.scale : 100,
        make_zip: true,
        force_png: false,
      };

      // Tail logo: prefer customTextures[0], else legacy soacra — NEVER fuselage bake
      const ctLogo = (state.customTextures || []).find((s) => s && s.dataUrl);
      let res;
      if (ctLogo || state.soacraFile) {
        const fd = new FormData();
        fd.append("profile_id", payload.profile_id);
        fd.append("name", payload.name);
        fd.append("registration", payload.registration);
        fd.append("airline", payload.airline);
        fd.append("icao", payload.icao);
        fd.append("colors_json", JSON.stringify(payload.colors));
        fd.append("stickers_json", JSON.stringify(payload.stickers));
        fd.append("text_json", JSON.stringify(payload.text || {}));
        fd.append("textScale", String(payload.textScale ?? 200));
        fd.append("logoScale", String(payload.logoScale ?? 100));
        fd.append("make_zip", "true");
        if (ctLogo && ctLogo.dataUrl) {
          const blob = await (await fetch(ctLogo.dataUrl)).blob();
          const fname = ctLogo.name || "tail-logo.png";
          fd.append("logo", blob, fname);
        } else if (state.soacraFile) {
          fd.append("logo", state.soacraFile);
        }
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
          (data.used_dds ? " · DDS BC7" : " · PNG (run convert_to_dds on Windows)") +
          (data.download_zip
            ? ` · <a href="${data.download_zip}">Download ZIP</a>`
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
      setStatus("Export failed.", String(err));
      alert("Export error: " + err.message);
    } finally {
      setBusy(false);
    }
  }

  async function doInstall() {
    if (!state.lastPackage) {
      alert("Export a package first, then Install.");
      return;
    }
    setBusy(true, "Installing into Community…");
    try {
      const res = await fetch("/api/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ package_folder: state.lastPackage }),
      });
      const data = await res.json();
      if (data.ok) {
        setStatus(`Installed: <code>${data.installed}</code>`, data);
      } else {
        setStatus(
          "Install is not available on this PC (Community path missing). Copy the folder from <code>output/</code> manually.",
          data
        );
        alert(
          (data.hint || data.error || "Community path missing") +
            "\n\nOn Windows: start SkinMyBird.bat and press Install again."
        );
      }
    } catch (err) {
      setStatus("Install failed.", String(err));
      alert("Install error: " + err.message);
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


  function ensureCustomTextureSlot(i) {
    if (!state.customTextures) state.customTextures = [];
    while (state.customTextures.length < 3) {
      const id = state.customTextures.length + 1;
      state.customTextures.push({
        id, dataUrl: null, name: null, opacity: 100, scale: 100, posX: 0, posY: 0,
        rotate: 0, side: "both", placement: "tail", tint: "#ffffff", _img: null,
      });
    }
    return state.customTextures[i];
  }

  function syncCustomTextureInputs() {
    for (let n = 1; n <= 3; n++) {
      const slot = ensureCustomTextureSlot(n - 1);
      const lab = $("ct-label-" + n);
      if (lab) lab.textContent = slot.name || "Drop or click — PNG / JPG for tail";
      const clearBtn = document.querySelector('.ct-clear[data-slot="' + n + '"]');
      if (clearBtn) clearBtn.hidden = !slot.dataUrl;
      const place = document.querySelector('.ct-place[data-slot="' + n + '"]');
      if (place) place.value = "tail";
      const side = document.querySelector('.ct-side[data-slot="' + n + '"]');
      if (side) side.value = slot.side || "both";
      const op = document.querySelector('.ct-opacity[data-slot="' + n + '"]');
      if (op) op.value = slot.opacity ?? 100;
      const sc = document.querySelector('.ct-scale[data-slot="' + n + '"]');
      if (sc) sc.value = slot.scale ?? 100;
      const rot = document.querySelector('.ct-rotate[data-slot="' + n + '"]');
      if (rot) rot.value = slot.rotate ?? 0;
      const px = document.querySelector('.ct-pos-x[data-slot="' + n + '"]');
      if (px) px.value = slot.posX ?? 0;
      const py = document.querySelector('.ct-pos-y[data-slot="' + n + '"]');
      if (py) py.value = slot.posY ?? 0;
      const lop = $("ct-lab-op-" + n); if (lop) lop.textContent = (slot.opacity ?? 100) + "%";
      const lsc = $("ct-lab-sc-" + n); if (lsc) lsc.textContent = (slot.scale ?? 100) + "%";
      const lrot = $("ct-lab-rot-" + n); if (lrot) lrot.textContent = (slot.rotate ?? 0) + "°";
      const lx = $("ct-lab-x-" + n); if (lx) lx.textContent = String(slot.posX ?? 0);
      const ly = $("ct-lab-y-" + n); if (ly) ly.textContent = String(slot.posY ?? 0);
      const tint = document.querySelector('.ct-tint[data-slot="' + n + '"]');
      if (tint) tint.value = slot.tint || "#ffffff";
    }
  }

  function readCustomTextureInputs() {
    for (let n = 1; n <= 3; n++) {
      const slot = ensureCustomTextureSlot(n - 1);
      const place = document.querySelector('.ct-place[data-slot="' + n + '"]');
      // v0.8.13: logos always on tail fin only (hidden placement field for export compat)
      slot.placement = "tail";
      if (place) place.value = "tail";
      const side = document.querySelector('.ct-side[data-slot="' + n + '"]');
      if (side) slot.side = side.value || "both";
      const op = document.querySelector('.ct-opacity[data-slot="' + n + '"]');
      if (op) slot.opacity = Number(op.value) || 100;
      const sc = document.querySelector('.ct-scale[data-slot="' + n + '"]');
      if (sc) slot.scale = Number(sc.value) || 100;
      const rot = document.querySelector('.ct-rotate[data-slot="' + n + '"]');
      if (rot) slot.rotate = Number(rot.value) || 0;
      const px = document.querySelector('.ct-pos-x[data-slot="' + n + '"]');
      if (px) slot.posX = Number(px.value) || 0;
      const py = document.querySelector('.ct-pos-y[data-slot="' + n + '"]');
      if (py) slot.posY = Number(py.value) || 0;
      const tint = document.querySelector('.ct-tint[data-slot="' + n + '"]');
      if (tint) {
        const v = tint.value || "#ffffff";
        // White = no tint (leave image colors alone)
        slot.tint = (v.toLowerCase() === "#ffffff") ? null : v;
      }
    }
  }

  function loadCustomTextureFile(slotIndex, file) {
    const slot = ensureCustomTextureSlot(slotIndex);
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      slot.dataUrl = dataUrl;
      slot.name = file.name;
      slot._img = null;
      slot._pendingImgLoad = false;
      syncCustomTextureInputs();
      // Kick hangar once (may schedule Image load + remount via ensureCustomSlotImage)
      drawPreview();
      const img = new Image();
      img.onload = () => {
        slot._img = img;
        slot._pendingImgLoad = false;
        syncCustomTextureInputs();
        drawPreview();
      };
      img.onerror = () => {
        console.warn("custom texture failed", file.name);
        slot._pendingImgLoad = false;
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
  }

  function clearCustomTexture(slotIndex) {
    const slot = ensureCustomTextureSlot(slotIndex);
    slot.dataUrl = null;
    slot.name = null;
    slot._img = null;
    const fileEl = document.querySelector('.ct-file[data-slot="' + (slotIndex + 1) + '"]');
    if (fileEl) fileEl.value = "";
    syncCustomTextureInputs();
    drawPreview();
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

  document.querySelectorAll("[data-reg-size]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.regSize = btn.getAttribute("data-reg-size");
      if ($("reg-size")) $("reg-size").value = state.regSize;
      syncSegmented("data-reg-size", state.regSize);
      drawPreview();
    });
  });

  document.querySelectorAll("[data-reg-style]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.regStyle = btn.getAttribute("data-reg-style");
      if ($("reg-style")) $("reg-style").value = state.regStyle;
      syncSegmented("data-reg-style", state.regStyle);
      drawPreview();
    });
  });

  document.querySelectorAll("[data-slogan-size]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.sloganSize = btn.getAttribute("data-slogan-size");
      if ($("slogan-size")) $("slogan-size").value = state.sloganSize;
      syncSegmented("data-slogan-size", state.sloganSize);
      drawPreview();
    });
  });
  document.querySelectorAll("[data-slogan-style]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.sloganStyle = btn.getAttribute("data-slogan-style");
      if ($("slogan-style")) $("slogan-style").value = state.sloganStyle;
      syncSegmented("data-slogan-style", state.sloganStyle);
      drawPreview();
    });
  });

  document.querySelectorAll("[data-sticker-size]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.stickerSize = btn.getAttribute("data-sticker-size");
      if ($("sticker-size")) $("sticker-size").value = state.stickerSize;
      syncSegmented("data-sticker-size", state.stickerSize);
      drawPreview();
    });
  });
  document.querySelectorAll("[data-flag-place]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.flags = state.flags || { codes: [], placement: "both", posX: 0, posY: 10 };
      state.flags.placement = btn.getAttribute("data-flag-place");
      if ($("flag-placement")) $("flag-placement").value = state.flags.placement;
      syncSegmented("data-flag-place", state.flags.placement);
      syncFlagCustomPos();
      drawPreview();
    });
  });
  document.querySelectorAll(".flag-check").forEach((el) => {
    el.addEventListener("change", drawPreview);
  });

  document.querySelectorAll(".ct-file").forEach((el) => {
    el.addEventListener("change", (e) => {
      const slot = Number(el.getAttribute("data-slot")) - 1;
      const file = e.target.files && e.target.files[0];
      if (file) loadCustomTextureFile(slot, file);
    });
  });
  document.querySelectorAll(".ct-clear").forEach((el) => {
    el.addEventListener("click", () => {
      clearCustomTexture(Number(el.getAttribute("data-slot")) - 1);
    });
  });
  document.querySelectorAll(".ct-place, .ct-side, .ct-opacity, .ct-scale, .ct-rotate, .ct-pos-x, .ct-pos-y, .ct-tint").forEach((el) => {
    el.addEventListener("input", () => {
      const n = el.getAttribute("data-slot");
      if (el.classList.contains("ct-opacity") && $("ct-lab-op-" + n))
        $("ct-lab-op-" + n).textContent = el.value + "%";
      if (el.classList.contains("ct-scale") && $("ct-lab-sc-" + n))
        $("ct-lab-sc-" + n).textContent = el.value + "%";
      if (el.classList.contains("ct-rotate") && $("ct-lab-rot-" + n))
        $("ct-lab-rot-" + n).textContent = el.value + "°";
      if (el.classList.contains("ct-pos-x") && $("ct-lab-x-" + n))
        $("ct-lab-x-" + n).textContent = el.value;
      if (el.classList.contains("ct-pos-y") && $("ct-lab-y-" + n))
        $("ct-lab-y-" + n).textContent = el.value;
      drawPreview();
    });
    el.addEventListener("change", drawPreview);
  });



  document.querySelectorAll("[data-style]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.textStyle = btn.getAttribute("data-style");
      $("text-style").value = state.textStyle;
      syncSegmented("data-style", state.textStyle);
      drawPreview();
    });
  });
  function bindZoneChips(attr, stateKey, hiddenId, fallback) {
    document.querySelectorAll("[" + attr + "]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const v = btn.getAttribute(attr) || fallback;
        state[stateKey] = v;
        if ($(hiddenId)) $(hiddenId).value = v;
        // Keep legacy textPlacement loosely in sync with title zone
        if (stateKey === "titleZone") {
          state.textPlacement = (v === "tail" || v === "belly") ? v : "fuselage";
          if ($("text-placement")) $("text-placement").value = state.textPlacement;
        }
        syncSegmented(attr, v);
        drawPreview();
      });
    });
  }
  bindZoneChips("data-title-zone", "titleZone", "title-zone", "windowband");
  bindZoneChips("data-slogan-zone", "sloganZone", "slogan-zone", "mid");
  bindZoneChips("data-reg-zone", "regZone", "reg-zone", "aft");
  document.querySelectorAll("[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.viewMode = btn.getAttribute("data-view");
        drawPreview();
    });
  });

  [
    "c-fuselage",
    "c-nose",
    "c-belly",
    "c-wings",
    "c-winglet",
    "c-engines",
    "c-tail",
    "c-windowband",
    "livery-name",
    "registration",
    "airline",
    "slogan",
    "text-color",
    "reg-color",
    "text-font",
    "reg-font",
    "text-pos-x",
    "text-pos-y",
    "text-scale",
    "text-flip-left",
    "text-flip-right",
    "flag-pos-x",
    "flag-pos-y",
  ].forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.addEventListener("input", () => {
      if (id === "text-pos-x" && $("lab-text-x")) $("lab-text-x").textContent = el.value;
      if (id === "text-pos-y" && $("lab-text-y")) $("lab-text-y").textContent = el.value;
      if (id === "text-scale" && $("lab-text-scale")) $("lab-text-scale").textContent = el.value + "%";
      if (id === "flag-pos-x" && $("lab-flag-x")) $("lab-flag-x").textContent = el.value;
      if (id === "flag-pos-y" && $("lab-flag-y")) $("lab-flag-y").textContent = el.value;
      drawPreview();
    });
    el.addEventListener("change", drawPreview);
  });

  // v0.6.1 — highlight paint zone on preview when hovering/focusing a Colors field
  const ZONE_COLOR_IDS = [
    "c-fuselage",
    "c-nose",
    "c-belly",
    "c-wings",
    "c-winglet",
    "c-engines",
    "c-tail",
    "c-windowband",
  ];
  let _zoneHlClearTimer = null;
  function zoneNameFromColorId(id) {
    return id && id.startsWith("c-") ? id.slice(2) : null;
  }
  function setZoneHighlight(zone) {
    const p3 = ensurePreview3D();
    if (p3 && p3.ok && typeof p3.setHighlightedZone === "function") {
      p3.setHighlightedZone(zone);
    }
  }
  function scheduleClearZoneHighlight() {
    if (_zoneHlClearTimer) clearTimeout(_zoneHlClearTimer);
    _zoneHlClearTimer = setTimeout(() => {
      _zoneHlClearTimer = null;
      // Don't clear if focus moved to another zone field
      const ae = document.activeElement;
      if (ae && ae.id && ZONE_COLOR_IDS.includes(ae.id)) {
        setZoneHighlight(zoneNameFromColorId(ae.id));
        return;
      }
      setZoneHighlight(null);
    }, 60);
  }
  ZONE_COLOR_IDS.forEach((id) => {
    const el = $(id);
    if (!el) return;
    const zone = zoneNameFromColorId(id);
    const activate = () => {
      if (_zoneHlClearTimer) {
        clearTimeout(_zoneHlClearTimer);
        _zoneHlClearTimer = null;
      }
      setZoneHighlight(zone);
    };
    el.addEventListener("mouseenter", activate);
    el.addEventListener("focusin", activate);
    el.addEventListener("mouseleave", scheduleClearZoneHighlight);
    el.addEventListener("focusout", scheduleClearZoneHighlight);
    // Label click / span also highlights (color-field is the <label>)
    const field = el.closest(".color-field");
    if (field) {
      field.addEventListener("mouseenter", activate);
      field.addEventListener("mouseleave", scheduleClearZoneHighlight);
      field.addEventListener("focusin", activate);
      field.addEventListener("focusout", scheduleClearZoneHighlight);
    }
  });

  // Optional: click plane → focus that zone's color input
  (function wireZonePickClick() {
    const canvas = $("preview3d");
    if (!canvas) return;
    let downX = 0, downY = 0, downT = 0;
    canvas.addEventListener("pointerdown", (e) => {
      downX = e.clientX;
      downY = e.clientY;
      downT = performance.now();
    });
    canvas.addEventListener("click", (e) => {
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 6) return;
      if (performance.now() - downT > 500) return;
      const p3 = ensurePreview3D();
      if (!p3 || !p3.ok || typeof p3.pickZoneAt !== "function") return;
      const zone = p3.pickZoneAt(e.clientX, e.clientY);
      if (!zone) return;
      const input = $("c-" + zone);
      if (input) {
        input.focus();
        setZoneHighlight(zone);
      }
    });
  })();

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
    $("soacra-label").textContent = "Drop or click — logo / photo";
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
  window.addEventListener("skinmybird-custom-texture-ready", () => {
    try { drawPreview(); } catch (_) {}
  });

  drawPreview();

