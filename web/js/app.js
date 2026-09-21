/**
 * SkinMyBird web editor v0.5.6 — commercial UI + 3D hangar preview (Three.js).
 * UI labels in English (worldwide). Keeps /api/export + /api/export-form contracts.
 */
import { Preview3D, resolveGlbMeta } from "./preview3d.js?v=0.5.6";

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
    colors: {
      fuselage: "#f2f4f7",
      nose: "#f2f4f7",
      belly: "#f2f4f7",
      wings: "#1b2430",
      winglet: "#1b2430",
      engines: "#1b2430",
      tail: "#f2f4f7",
      stabilizer: "#f2f4f7",
      doors: "#f2f4f7",
      windowband: "#f2f4f7",
      accent: "#f2f4f7",
    },
    name: "Two-Tone",
    registration: "YR-EUG",
    airline: "SkinMyBird",
    slogan: "",
    stickerText: "",
    textColor: "#FFFFFF",
    textSize: "M",
    textStyle: "bold",
    textFont: "segoe",
    textPlacement: "fuselage",
    textPosX: 0,
    textPosY: -10,
    textScale: 100,
    textFlipLeft: false,
    textFlipRight: true,
    stickers: {
      stripe: false,
      heart: false,
      text: true,
      star: false,
      lightning: false,
      bird: false,
      roundel: false,
      chevron: false,
      checkered: false,
      smile: false,
      crown: false,
      diamond: false,
      sun: false,
      moon: false,
      flag: false,
      shield: false,
      arrow: false,
      sparkle: false,
      wingbadge: false,
    },
    stickerSize: "M",
    flags: {
      codes: [],
      placement: "both", // left | right | both | free
      posX: 0,
      posY: 10,
    },
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
    if ($("c-stabilizer")) $("c-stabilizer").value = state.colors.stabilizer || state.colors.tail || "#f2f4f7";
    if ($("c-doors")) $("c-doors").value = state.colors.doors || state.colors.fuselage || "#f2f4f7";
    if ($("c-windowband")) $("c-windowband").value = state.colors.windowband || state.colors.fuselage || "#f2f4f7";
    if ($("c-accent")) $("c-accent").value = state.colors.accent || "#f2f4f7";
    $("livery-name").value = state.name;
    $("registration").value = state.registration;
    $("airline").value = state.airline;
    $("slogan").value = state.slogan || "";
    $("text-color").value = state.textColor;
    $("text-size").value = state.textSize;
    $("text-style").value = state.textStyle;
    if ($("text-font")) $("text-font").value = state.textFont || "segoe";
    $("text-placement").value = state.textPlacement;
    if ($("text-pos-x")) $("text-pos-x").value = state.textPosX ?? 0;
    if ($("text-pos-y")) $("text-pos-y").value = state.textPosY ?? -10;
    if ($("text-scale")) $("text-scale").value = state.textScale ?? 100;
    if ($("text-flip-left")) $("text-flip-left").checked = !!state.textFlipLeft;
    if ($("text-flip-right")) $("text-flip-right").checked = state.textFlipRight !== false;
    if ($("lab-text-x")) $("lab-text-x").textContent = String(state.textPosX ?? 0);
    if ($("lab-text-y")) $("lab-text-y").textContent = String(state.textPosY ?? -10);
    if ($("lab-text-scale")) $("lab-text-scale").textContent = String(state.textScale ?? 100) + "%";
    $("st-stripe").checked = !!state.stickers.stripe;
    $("st-heart").checked = !!state.stickers.heart;
    $("st-text").checked = !!state.stickers.text;
    if ($("st-star")) $("st-star").checked = !!state.stickers.star;
    if ($("st-lightning")) $("st-lightning").checked = !!state.stickers.lightning;
    if ($("st-bird")) $("st-bird").checked = !!state.stickers.bird;
    if ($("st-roundel")) $("st-roundel").checked = !!state.stickers.roundel;
    if ($("st-chevron")) $("st-chevron").checked = !!state.stickers.chevron;
    if ($("st-checkered")) $("st-checkered").checked = !!state.stickers.checkered;
    ["smile","crown","diamond","sun","moon","flag","shield","arrow","sparkle","wingbadge"].forEach((k) => {
      const el = $("st-" + k);
      if (el) el.checked = !!state.stickers[k];
    });
    updateHexLabels();
    syncSegmented("data-size", state.textSize);
    syncSegmented("data-style", state.textStyle);
    syncSegmented("data-place", state.textPlacement);
    if ($("sticker-size")) $("sticker-size").value = state.stickerSize || "M";
    syncSegmented("data-sticker-size", state.stickerSize || "M");
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
      stabilizer: "hex-stabilizer",
      doors: "hex-doors",
      windowband: "hex-windowband",
      accent: "hex-accent",
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
    state.colors.stabilizer = $("c-stabilizer") ? $("c-stabilizer").value : (state.colors.stabilizer || state.colors.tail || "#f2f4f7");
    state.colors.doors = $("c-doors") ? $("c-doors").value : (state.colors.doors || state.colors.fuselage || "#f2f4f7");
    state.colors.windowband = $("c-windowband") ? $("c-windowband").value : (state.colors.windowband || state.colors.fuselage || "#f2f4f7");
    state.colors.accent = $("c-accent") ? $("c-accent").value : (state.colors.accent || "#f2f4f7");
    state.name = $("livery-name").value.trim() || "Custom";
    state.registration = $("registration").value.trim() || "SMB-001";
    state.airline = $("airline").value.trim() || "SkinMyBird";
    state.slogan = ($("slogan").value || "").trim();
    state.textColor = $("text-color").value || "#FFFFFF";
    state.textSize = $("text-size").value || "M";
    state.textStyle = $("text-style").value || "bold";
    state.textFont = ($("text-font") && $("text-font").value) || "segoe";
    state.textPlacement = $("text-placement").value || "fuselage";
    state.textPosX = $("text-pos-x") ? Number($("text-pos-x").value) : 0;
    state.textPosY = $("text-pos-y") ? Number($("text-pos-y").value) : -10;
    state.textScale = $("text-scale") ? Number($("text-scale").value) : 100;
    state.textFlipLeft = $("text-flip-left") ? $("text-flip-left").checked : false;
    state.textFlipRight = $("text-flip-right") ? $("text-flip-right").checked : true;
    // custom_text payload: slogan only — registration is its own field (avoid double paint)
    state.stickerText = state.slogan || "";
    state.stickers.stripe = $("st-stripe").checked;
    state.stickers.heart = $("st-heart").checked;
    state.stickers.text = $("st-text").checked;
    state.stickers.star = $("st-star") ? $("st-star").checked : false;
    state.stickers.lightning = $("st-lightning") ? $("st-lightning").checked : false;
    state.stickers.bird = $("st-bird") ? $("st-bird").checked : false;
    state.stickers.roundel = $("st-roundel") ? $("st-roundel").checked : false;
    state.stickers.chevron = $("st-chevron") ? $("st-chevron").checked : false;
    state.stickers.checkered = $("st-checkered") ? $("st-checkered").checked : false;
    ["smile","crown","diamond","sun","moon","flag","shield","arrow","sparkle","wingbadge"].forEach((k) => {
      const el = $("st-" + k);
      state.stickers[k] = el ? el.checked : !!state.stickers[k];
    });
    if ($("sticker-size")) state.stickerSize = $("sticker-size").value || "M";
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
    const kinds = [
      ["team_stripe", "stripe"],
      ["heart", "heart"],
      ["star", "star"],
      ["lightning", "lightning"],
      ["bird", "bird"],
      ["roundel", "roundel"],
      ["chevron", "chevron"],
      ["checkered", "checkered"],
      ["smile", "smile"],
      ["crown", "crown"],
      ["diamond", "diamond"],
      ["sun", "sun"],
      ["moon", "moon"],
      ["flag", "flag"],
      ["shield", "shield"],
      ["arrow", "arrow"],
      ["sparkle", "sparkle"],
      ["wingbadge", "wingbadge"],
    ];
    const list = kinds.map(([type, key]) => ({
      type,
      enabled: !!state.stickers[key],
    }));
    list.push({
      type: "custom_text",
      enabled: !!state.stickers.text && !!(state.stickerText && String(state.stickerText).trim()),
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
      ["Body", state.colors.fuselage],
      ["Nose", state.colors.nose],
      ["Belly", state.colors.belly],
      ["Wings", state.colors.wings],
      ["Winglet", state.colors.winglet],
      ["Stab", state.colors.stabilizer],
      ["Engines", state.colors.engines],
      ["Tail", state.colors.tail],
      ["Doors", state.colors.doors],
      ["Windows", state.colors.windowband],
      ["Accent", state.colors.accent],
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
    const items = [
      { on: true, label: "Fuselage", meta: state.colors.fuselage, color: state.colors.fuselage },
      { on: true, label: "Nose", meta: state.colors.nose, color: state.colors.nose },
      { on: true, label: "Belly", meta: state.colors.belly, color: state.colors.belly },
      { on: true, label: "Wings", meta: state.colors.wings, color: state.colors.wings },
      { on: true, label: "Winglet", meta: state.colors.winglet, color: state.colors.winglet },
      { on: true, label: "Stabilizer", meta: state.colors.stabilizer, color: state.colors.stabilizer },
      { on: true, label: "Engines", meta: state.colors.engines, color: state.colors.engines },
      { on: true, label: "Tail", meta: state.colors.tail, color: state.colors.tail },
      { on: true, label: "Doors", meta: state.colors.doors, color: state.colors.doors },
      { on: true, label: "Window band", meta: state.colors.windowband, color: state.colors.windowband },
      { on: true, label: "Accent", meta: state.colors.accent, color: state.colors.accent },
      { on: state.stickers.stripe, label: "Team stripe", meta: "" },
      { on: state.stickers.heart, label: "Heart", meta: "" },
      { on: state.stickers.star, label: "Star", meta: "" },
      { on: state.stickers.lightning, label: "Lightning", meta: "" },
      { on: state.stickers.bird, label: "Bird", meta: "" },
      { on: state.stickers.roundel, label: "Roundel", meta: "" },
      { on: state.stickers.chevron, label: "Chevron", meta: "" },
      { on: state.stickers.checkered, label: "Checkered", meta: "" },
      { on: state.stickers.smile, label: "Smile", meta: "" },
      { on: state.stickers.crown, label: "Crown", meta: "" },
      { on: state.stickers.diamond, label: "Diamond", meta: "" },
      { on: state.stickers.sun, label: "Sun", meta: "" },
      { on: state.stickers.moon, label: "Moon", meta: "" },
      { on: state.stickers.flag, label: "Pennant", meta: "" },
      { on: state.stickers.shield, label: "Shield", meta: "" },
      { on: state.stickers.arrow, label: "Arrow", meta: "" },
      { on: state.stickers.sparkle, label: "Sparkle", meta: "" },
      { on: state.stickers.wingbadge, label: "Wing badge", meta: "" },
      { on: true, label: "Sticker size", meta: state.stickerSize || "M" },
      {
        on: !!(state.flags && state.flags.codes && state.flags.codes.length),
        label: "Flags",
        meta: (state.flags && state.flags.codes && state.flags.codes.length)
          ? state.flags.codes.join(", ") + " · " + (state.flags.placement || "both")
          : "",
      },
      {
        on: state.stickers.text,
        label: "Text",
        meta: (state.textFont || "segoe") + " · " + state.textPlacement,
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

  async function loadProfiles() {
    try {
      const res = await fetch("/api/profiles");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      state.profiles = data.profiles || [];
      renderModelCards();
      setStatus(`Loaded <strong>${state.profiles.length}</strong> profiles.`);
      autoSelectFromUrl();
    } catch (err) {
      state.profiles = FALLBACK_PROFILES;
      renderModelCards();
      autoSelectFromUrl();
      setStatus(
        "API unavailable — static list. Start <code>python server.py</code> for DDS Export.",
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
    { id: "skinmybird-cessna-172-stub", displayName: "Cessna 172 (preview stub)", category: "avion", has_uv: false, silhouette: "ga", ui_manufacturer: "Cessna" },
  ];

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
    if ($("text-pos-x")) $("text-pos-x").value = state.textPosX ?? 0;
    if ($("text-pos-y")) $("text-pos-y").value = state.textPosY ?? -10;
    if ($("text-scale")) $("text-scale").value = state.textScale ?? 100;
    if ($("text-flip-left")) $("text-flip-left").checked = !!state.textFlipLeft;
    if ($("text-flip-right")) $("text-flip-right").checked = state.textFlipRight !== false;
    if ($("lab-text-x")) $("lab-text-x").textContent = String(state.textPosX ?? 0);
    if ($("lab-text-y")) $("lab-text-y").textContent = String(state.textPosY ?? -10);
    if ($("lab-text-scale")) $("lab-text-scale").textContent = String(state.textScale ?? 100) + "%";
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
    "c-nose",
    "c-belly",
    "c-wings",
    "c-winglet",
    "c-engines",
    "c-tail",
    "c-stabilizer",
    "c-doors",
    "c-windowband",
    "c-accent",
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
    "st-smile",
    "st-crown",
    "st-diamond",
    "st-sun",
    "st-moon",
    "st-flag",
    "st-shield",
    "st-arrow",
    "st-sparkle",
    "st-wingbadge",
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
  drawPreview();

