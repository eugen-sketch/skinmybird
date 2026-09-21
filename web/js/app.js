/**
 * SkinMyBird web editor v0.4 — commercial UI, text-on-aircraft, hangar preview.
 * UI labels in Romanian. Keeps /api/export + /api/export-form contracts.
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
    slogan: "",
    stickerText: "YR-EUG",
    textColor: "#FFFFFF",
    textSize: "M",
    textStyle: "bold",
    textPlacement: "fuselage",
    viewMode: "side",
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
    slogan: "Fly Orange",
    stickerText: "YR-EUG",
    textColor: "#FFFFFF",
    textSize: "M",
    textStyle: "bold",
    textPlacement: "fuselage",
  };

  const CAT_ICON = {
    avion: "✈️",
    elicopter: "🚁",
    balon: "🎈",
  };

  const SIZE_PX = { S: 18, M: 26, L: 36 };

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
    $("text-placement").value = state.textPlacement;
    $("st-stripe").checked = state.stickers.stripe;
    $("st-heart").checked = state.stickers.heart;
    $("st-text").checked = state.stickers.text;
    updateHexLabels();
    syncSegmented("data-size", state.textSize);
    syncSegmented("data-style", state.textStyle);
    syncSegmented("data-place", state.textPlacement);
    syncSegmented("data-view", state.viewMode);
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
    state.textPlacement = $("text-placement").value || "fuselage";
    // custom_text payload: slogan if set, else registration (legacy sticker-text behaviour)
    state.stickerText = state.slogan || state.registration;
    state.stickers.stripe = $("st-stripe").checked;
    state.stickers.heart = $("st-heart").checked;
    state.stickers.text = $("st-text").checked;
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
      {
        type: "custom_text",
        enabled: state.stickers.text,
        text: state.stickerText,
        color: state.textColor,
        size: state.textSize,
        style: state.textStyle,
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
      {
        on: state.stickers.text,
        label: "Text",
        meta: state.textPlacement,
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

  function shade(hex, amt) {
    const n = hex.replace("#", "");
    const num = parseInt(n.length === 3 ? n.split("").map((c) => c + c).join("") : n, 16);
    let r = (num >> 16) + amt;
    let g = ((num >> 8) & 0xff) + amt;
    let b = (num & 0xff) + amt;
    r = Math.max(0, Math.min(255, r));
    g = Math.max(0, Math.min(255, g));
    b = Math.max(0, Math.min(255, b));
    return `rgb(${r},${g},${b})`;
  }

  function drawHangarBg(ctx, W, H) {
    const sky = ctx.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#1a1b22");
    sky.addColorStop(0.45, "#101116");
    sky.addColorStop(1, "#08080a");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, H);

    // soft studio key light
    const glow = ctx.createRadialGradient(W * 0.5, H * 0.2, 20, W * 0.5, H * 0.35, W * 0.55);
    glow.addColorStop(0, "rgba(255,140,60,0.10)");
    glow.addColorStop(0.5, "rgba(255,106,0,0.04)");
    glow.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, W, H);

    // floor
    const floorY = H * 0.78;
    const floor = ctx.createLinearGradient(0, floorY, 0, H);
    floor.addColorStop(0, "rgba(30,32,40,0.9)");
    floor.addColorStop(1, "rgba(12,12,16,1)");
    ctx.fillStyle = floor;
    ctx.fillRect(0, floorY, W, H - floorY);

    // floor grid perspective lines
    ctx.strokeStyle = "rgba(255,255,255,0.04)";
    ctx.lineWidth = 1;
    for (let i = -6; i <= 6; i++) {
      ctx.beginPath();
      ctx.moveTo(W * 0.5 + i * 90, floorY);
      ctx.lineTo(W * 0.5 + i * 160, H);
      ctx.stroke();
    }
    for (let j = 0; j < 5; j++) {
      const y = floorY + (H - floorY) * (j / 5);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }
  }

  function drawGroundShadow(ctx, cx, cy, rw, rh) {
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.beginPath();
    ctx.ellipse(cx, cy, rw, rh, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function textFont(sizeKey, style) {
    const px = SIZE_PX[sizeKey] || SIZE_PX.M;
    const weight = style === "bold" ? "700" : "500";
    return `${weight} ${px}px "Segoe UI", system-ui, sans-serif`;
  }

  function drawAircraftText(ctx, layout) {
    if (!state.stickers.text) return;
    const color = state.textColor || "#FFFFFF";
    const place = state.textPlacement || "fuselage";
    const pos = layout[place] || layout.fuselage;
    if (!pos) return;

    ctx.save();
    ctx.fillStyle = color;
    ctx.textBaseline = "middle";
    ctx.shadowColor = "rgba(0,0,0,0.45)";
    ctx.shadowBlur = 6;
    ctx.shadowOffsetY = 1;

    // Airline title
    ctx.font = textFont(state.textSize, state.textStyle);
    ctx.textAlign = pos.align || "left";
    const airlineY = pos.y;
    ctx.fillText(state.airline || "SkinMyBird", pos.x, airlineY);

    // Slogan under airline when present
    if (state.slogan) {
      const subPx = Math.max(12, (SIZE_PX[state.textSize] || 26) * 0.55);
      ctx.font = `500 ${subPx}px "Segoe UI", system-ui, sans-serif`;
      ctx.globalAlpha = 0.92;
      ctx.fillText(state.slogan, pos.x, airlineY + subPx + 6);
      ctx.globalAlpha = 1;
    }

    // Registration — typically near tail / aft unless placement is belly
    const regPos = layout.registration || layout.tail;
    if (regPos) {
      const regPx = Math.max(11, (SIZE_PX[state.textSize] || 26) * 0.48);
      ctx.font = `600 ${regPx}px "Segoe UI", system-ui, sans-serif`;
      ctx.textAlign = regPos.align || "left";
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.95;
      ctx.fillText(state.registration, regPos.x, regPos.y);
      ctx.globalAlpha = 1;
    }
    ctx.restore();
  }

  function drawAirliner(ctx, W, H, threeQ) {
    const fus = state.colors.fuselage;
    const wing = state.colors.wings;
    const eng = state.colors.engines;
    const tail = state.colors.tail;
    const ox = threeQ ? W * 0.04 : 0;
    const cy = H * 0.52;
    const skew = threeQ ? 0.08 : 0;

    drawGroundShadow(ctx, W * 0.48 + ox, H * 0.76, W * 0.32, H * 0.028);

    // far wing
    ctx.fillStyle = shade(wing, threeQ ? 18 : 8);
    ctx.beginPath();
    ctx.moveTo(W * 0.34 + ox, cy - 8);
    ctx.lineTo(W * 0.18 + ox - (threeQ ? 20 : 0), cy - 105);
    ctx.lineTo(W * 0.26 + ox, cy - 88);
    ctx.lineTo(W * 0.42 + ox, cy + 4);
    ctx.closePath();
    ctx.fill();

    // fuselage body
    const fusX = W * 0.1 + ox;
    const fusW = W * 0.64;
    const fusH = 78;
    ctx.fillStyle = fus;
    roundRect(ctx, fusX, cy - fusH / 2, fusW, fusH, 38);
    ctx.fill();

    // belly highlight
    ctx.fillStyle = shade(fus, 28);
    ctx.globalAlpha = 0.22;
    roundRect(ctx, fusX + 20, cy + 8, fusW * 0.7, 22, 12);
    ctx.fill();
    ctx.globalAlpha = 1;

    // nose
    ctx.fillStyle = fus;
    ctx.beginPath();
    ctx.ellipse(fusX + 4, cy, 40, 37, 0, 0, Math.PI * 2);
    ctx.fill();
    // cockpit glass
    ctx.fillStyle = "#1a2233";
    ctx.beginPath();
    ctx.ellipse(fusX - 6, cy - 6, 18, 16, -0.2, 0, Math.PI * 2);
    ctx.fill();

    // near wing
    ctx.fillStyle = wing;
    ctx.beginPath();
    ctx.moveTo(W * 0.36 + ox, cy + 12);
    ctx.lineTo(W * 0.58 + ox + (threeQ ? 30 : 0), cy + 78);
    ctx.lineTo(W * 0.64 + ox + (threeQ ? 20 : 0), cy + 102);
    ctx.lineTo(W * 0.34 + ox, cy + 38);
    ctx.closePath();
    ctx.fill();
    // wing tip accent
    ctx.fillStyle = shade(wing, 40);
    ctx.beginPath();
    ctx.moveTo(W * 0.62 + ox, cy + 96);
    ctx.lineTo(W * 0.66 + ox, cy + 108);
    ctx.lineTo(W * 0.63 + ox, cy + 100);
    ctx.fill();

    // engines
    ctx.fillStyle = eng;
    roundRect(ctx, W * 0.4 + ox, cy + 30, 74, 44, 18);
    ctx.fill();
    roundRect(ctx, W * 0.51 + ox, cy + 42, 62, 36, 14);
    ctx.fill();
    ctx.fillStyle = shade(eng, 40);
    roundRect(ctx, W * 0.405 + ox, cy + 36, 28, 32, 12);
    ctx.fill();
    roundRect(ctx, W * 0.515 + ox, cy + 46, 24, 26, 10);
    ctx.fill();

    // window row
    ctx.fillStyle = "#152030";
    for (let i = 0; i < 16; i++) {
      const wx = W * 0.2 + ox + i * 30 + skew * i * 2;
      roundRect(ctx, wx, cy - 16, 16, 12, 3);
      ctx.fill();
    }
    // window reflection
    ctx.fillStyle = "rgba(180,210,255,0.15)";
    for (let i = 0; i < 16; i++) {
      const wx = W * 0.2 + ox + i * 30;
      roundRect(ctx, wx + 2, cy - 14, 5, 4, 2);
      ctx.fill();
    }

    // vertical stabilizer
    ctx.fillStyle = tail;
    ctx.beginPath();
    ctx.moveTo(W * 0.7 + ox, cy - 28);
    ctx.lineTo(W * 0.735 + ox, cy - 155);
    ctx.lineTo(W * 0.85 + ox, cy - 150);
    ctx.lineTo(W * 0.78 + ox, cy - 28);
    ctx.closePath();
    ctx.fill();
    // fin highlight
    ctx.fillStyle = shade(tail, 35);
    ctx.globalAlpha = 0.35;
    ctx.beginPath();
    ctx.moveTo(W * 0.72 + ox, cy - 30);
    ctx.lineTo(W * 0.745 + ox, cy - 140);
    ctx.lineTo(W * 0.77 + ox, cy - 138);
    ctx.lineTo(W * 0.74 + ox, cy - 30);
    ctx.fill();
    ctx.globalAlpha = 1;

    // horizontal stabilizer
    ctx.fillStyle = shade(tail, -15);
    ctx.beginPath();
    ctx.moveTo(W * 0.72 + ox, cy);
    ctx.lineTo(W * 0.92 + ox, cy - 22);
    ctx.lineTo(W * 0.92 + ox, cy + 10);
    ctx.lineTo(W * 0.74 + ox, cy + 20);
    ctx.closePath();
    ctx.fill();

    return {
      fuselage: { x: W * 0.28 + ox, y: cy - 4, align: "left" },
      tail: { x: W * 0.76 + ox, y: cy - 95, align: "center" },
      belly: { x: W * 0.4 + ox, y: cy + 28, align: "left" },
      registration: { x: W * 0.66 + ox, y: cy - 8, align: "left" },
      stripeY: cy + 22,
      heart: { x: W * 0.3 + ox, y: cy - 48 },
      logo: { x: W * 0.48 + ox, y: cy + 8 },
      stripeX: W * 0.2 + ox,
      stripeW: W * 0.42,
    };
  }

  function drawHelicopter(ctx, W, H, threeQ) {
    const fus = state.colors.fuselage;
    const wing = state.colors.wings;
    const eng = state.colors.engines;
    const tail = state.colors.tail;
    const cx = W * (threeQ ? 0.42 : 0.45);
    const cy = H * 0.55;

    drawGroundShadow(ctx, cx + 40, H * 0.76, W * 0.28, H * 0.022);

    // rotor disc
    ctx.strokeStyle = shade(wing, 20);
    ctx.lineWidth = 5;
    ctx.globalAlpha = 0.7;
    ctx.beginPath();
    ctx.ellipse(cx, cy - 118, 120, threeQ ? 28 : 95, threeQ ? -0.15 : 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.beginPath();
    ctx.moveTo(cx, cy - 118);
    ctx.lineTo(cx, cy - 42);
    ctx.strokeStyle = wing;
    ctx.lineWidth = 5;
    ctx.stroke();

    // cabin
    ctx.fillStyle = fus;
    roundRect(ctx, cx - 150, cy - 42, 310, 95, 40);
    ctx.fill();
    ctx.fillStyle = shade(fus, 30);
    ctx.globalAlpha = 0.2;
    roundRect(ctx, cx - 140, cy + 10, 260, 28, 12);
    ctx.fill();
    ctx.globalAlpha = 1;

    // boom / tail
    ctx.fillStyle = tail;
    ctx.beginPath();
    ctx.moveTo(cx + 145, cy - 8);
    ctx.lineTo(cx + 300, cy - 18);
    ctx.lineTo(cx + 305, cy + 8);
    ctx.lineTo(cx + 145, cy + 32);
    ctx.closePath();
    ctx.fill();
    // tail rotor
    ctx.strokeStyle = wing;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(cx + 300, cy - 5, 28, 0, Math.PI * 2);
    ctx.stroke();

    // skids
    ctx.fillStyle = eng;
    roundRect(ctx, cx - 90, cy + 50, 180, 14, 6);
    ctx.fill();
    roundRect(ctx, cx - 50, cy + 42, 12, 20, 3);
    ctx.fill();
    roundRect(ctx, cx + 40, cy + 42, 12, 20, 3);
    ctx.fill();

    // cockpit window
    ctx.fillStyle = "#152030";
    roundRect(ctx, cx - 135, cy - 28, 70, 36, 10);
    ctx.fill();

    return {
      fuselage: { x: cx - 40, y: cy, align: "left" },
      tail: { x: cx + 220, y: cy - 5, align: "center" },
      belly: { x: cx, y: cy + 35, align: "center" },
      registration: { x: cx + 160, y: cy + 8, align: "left" },
      heart: { x: cx - 20, y: cy - 55 },
      logo: { x: cx + 40, y: cy - 10 },
      stripeY: cy + 28,
      stripeX: cx - 120,
      stripeW: 220,
    };
  }

  function drawBalloon(ctx, W, H) {
    const fus = state.colors.fuselage;
    const wing = state.colors.wings;
    const eng = state.colors.engines;
    const tail = state.colors.tail;
    const cx = W * 0.5;
    const cy = H * 0.4;

    drawGroundShadow(ctx, cx, H * 0.78, 70, 14);

    // envelope
    ctx.fillStyle = fus;
    ctx.beginPath();
    ctx.ellipse(cx, cy, 150, 180, 0, 0, Math.PI * 2);
    ctx.fill();
    // gores
    ctx.strokeStyle = shade(tail, 0);
    ctx.lineWidth = 3;
    ctx.globalAlpha = 0.55;
    for (let i = -3; i <= 3; i++) {
      ctx.beginPath();
      ctx.ellipse(cx + i * 8, cy, 150, 180, 0, -1.15, 1.15);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    // highlight
    ctx.fillStyle = "rgba(255,255,255,0.12)";
    ctx.beginPath();
    ctx.ellipse(cx - 50, cy - 50, 40, 70, -0.4, 0, Math.PI * 2);
    ctx.fill();

    // skirt
    ctx.fillStyle = wing;
    ctx.beginPath();
    ctx.moveTo(cx - 40, cy + 160);
    ctx.lineTo(cx + 40, cy + 160);
    ctx.lineTo(cx + 52, cy + 220);
    ctx.lineTo(cx - 52, cy + 220);
    ctx.closePath();
    ctx.fill();

    // basket
    ctx.fillStyle = eng;
    roundRect(ctx, cx - 44, cy + 220, 88, 42, 6);
    ctx.fill();
    ctx.strokeStyle = shade(eng, 40);
    ctx.lineWidth = 2;
    ctx.strokeRect(cx - 40, cy + 226, 80, 30);

    return {
      fuselage: { x: cx, y: cy, align: "center" },
      tail: { x: cx, y: cy - 80, align: "center" },
      belly: { x: cx, y: cy + 100, align: "center" },
      registration: { x: cx, y: cy + 140, align: "center" },
      heart: { x: cx + 60, y: cy - 40 },
      logo: { x: cx - 35, y: cy + 30 },
      stripeY: cy + 40,
      stripeX: cx - 80,
      stripeW: 160,
    };
  }

  function drawPreview() {
    readInputs();
    updateSwatches();
    updateLayers();
    const canvas = $("preview");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    drawHangarBg(ctx, W, H);

    const sil = (state.profile && state.profile.silhouette) || "airliner";
    const threeQ = state.viewMode === "threeq";
    let layout;
    if (sil === "helicopter") layout = drawHelicopter(ctx, W, H, threeQ);
    else if (sil === "balloon") layout = drawBalloon(ctx, W, H);
    else layout = drawAirliner(ctx, W, H, threeQ);

    // stripe
    if (state.stickers.stripe && layout) {
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(layout.stripeX, layout.stripeY, layout.stripeW, 9);
      ctx.fillStyle = state.colors.tail;
      ctx.fillRect(layout.stripeX, layout.stripeY + 9, layout.stripeW, 7);
    }

    if (state.stickers.heart && layout && layout.heart) {
      drawHeart(ctx, layout.heart.x, layout.heart.y, 26, "#dc2840");
    }

    drawAircraftText(ctx, layout);

    if (state.soacra && layout && layout.logo) {
      const s = 64;
      ctx.save();
      ctx.beginPath();
      roundRect(ctx, layout.logo.x, layout.logo.y, s, s, 10);
      ctx.clip();
      ctx.drawImage(state.soacra, layout.logo.x, layout.logo.y, s, s);
      ctx.restore();
      ctx.strokeStyle = "rgba(255,255,255,0.25)";
      ctx.lineWidth = 1;
      roundRect(ctx, layout.logo.x, layout.logo.y, s, s, 10);
      ctx.stroke();
    }

    // HUD labels
    ctx.fillStyle = "rgba(255,255,255,0.88)";
    ctx.font = '600 17px "Segoe UI", sans-serif';
    ctx.textAlign = "left";
    ctx.shadowColor = "transparent";
    const title = state.profile ? state.profile.displayName : "Alege un model";
    ctx.fillText(title, 28, 34);
    ctx.font = '13px "Segoe UI", sans-serif';
    ctx.fillStyle = "rgba(180,185,200,0.7)";
    ctx.fillText(`${state.name} · ${state.registration}`, 28, 54);

    // refresh advanced preview if open
    const cfgPrev = $("config-preview");
    if (cfgPrev && !$("advanced-drawer").hidden) {
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
    updateLayers();
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
    state.stickers = { stripe: true, heart: false, text: true };
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
      syncSegmented("data-view", state.viewMode);
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

  syncInputsFromState();
  loadProfiles();
  // Draw empty hangar so canvas isn't blank before selection
  drawPreview();
})();
