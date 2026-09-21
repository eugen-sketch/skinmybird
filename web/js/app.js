/* SkinMyBird web UI — live 2D A320 silhouette + Community ZIP export (JSZip) */
(function () {
  const $ = (id) => document.getElementById(id);

  const state = {
    colors: {
      fuselage: "#FF6A00",
      wings: "#111111",
      engines: "#222222",
      tail: "#FF6A00",
    },
    name: "Eugen Orange",
    registration: "YR-EUG",
    stickers: { stripe: true, heart: false, text: true },
    soacra: null, // HTMLImageElement | null
    soacraName: null,
  };

  const EUGEN = {
    fuselage: "#FF6A00",
    wings: "#111111",
    engines: "#222222",
    tail: "#FF6A00",
    name: "Eugen Orange",
    registration: "YR-EUG",
  };

  function syncInputsFromState() {
    $("c-fuselage").value = state.colors.fuselage;
    $("c-wings").value = state.colors.wings;
    $("c-engines").value = state.colors.engines;
    $("c-tail").value = state.colors.tail;
    $("livery-name").value = state.name;
    $("registration").value = state.registration;
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
    state.stickers.stripe = $("st-stripe").checked;
    state.stickers.heart = $("st-heart").checked;
    state.stickers.text = $("st-text").checked;
  }

  function slugify(t) {
    return t
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "") || "livery";
  }

  function buildConfig() {
    readInputs();
    return {
      id: slugify(state.name),
      name: state.name,
      registration: state.registration,
      airline: "SkinMyBird",
      icao: "SMB",
      colors: { ...state.colors },
      stickers: [
        { type: "team_stripe", enabled: state.stickers.stripe },
        { type: "heart", enabled: state.stickers.heart },
        { type: "custom_text", enabled: state.stickers.text, text: state.registration },
      ],
      soacraPhoto: state.soacraName,
    };
  }

  function updateSwatches() {
    const el = $("swatches");
    const entries = [
      ["Fuselage", state.colors.fuselage],
      ["Wings", state.colors.wings],
      ["Engines", state.colors.engines],
      ["Tail", state.colors.tail],
    ];
    el.innerHTML = entries
      .map(
        ([label, c]) =>
          `<span class="swatch"><i style="background:${c}"></i>${label} ${c.toUpperCase()}</span>`
      )
      .join("");
  }

  /** Draw simplified A320 side silhouette with zone fills */
  function drawPreview() {
    readInputs();
    updateSwatches();
    const canvas = $("preview");
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // runway glow
    const g = ctx.createLinearGradient(0, H * 0.7, 0, H);
    g.addColorStop(0, "rgba(61,214,198,0)");
    g.addColorStop(1, "rgba(61,214,198,0.08)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    const y = H * 0.52;
    const scale = 1;

    // Wings (behind fuselage partially)
    ctx.save();
    ctx.translate(W * 0.48, y + 10);
    ctx.fillStyle = state.colors.wings;
    ctx.beginPath();
    ctx.moveTo(-40, 0);
    ctx.lineTo(180, 18);
    ctx.lineTo(200, 28);
    ctx.lineTo(-60, 22);
    ctx.closePath();
    ctx.fill();
    // far wing tip shadow
    ctx.globalAlpha = 0.45;
    ctx.beginPath();
    ctx.moveTo(-20, -8);
    ctx.lineTo(-160, -70);
    ctx.lineTo(-150, -55);
    ctx.lineTo(20, 5);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Engines
    ctx.fillStyle = state.colors.engines;
    roundRect(ctx, W * 0.42, y + 18, 70, 36, 14);
    ctx.fill();
    roundRect(ctx, W * 0.55, y + 22, 62, 32, 12);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,0.15)";
    roundRect(ctx, W * 0.425, y + 26, 22, 20, 10);
    ctx.fill();

    // Fuselage body
    ctx.fillStyle = state.colors.fuselage;
    ctx.beginPath();
    // nose → body → tail boom
    ctx.moveTo(W * 0.12, y);
    ctx.quadraticCurveTo(W * 0.14, y - 38, W * 0.22, y - 42);
    ctx.lineTo(W * 0.72, y - 42);
    ctx.quadraticCurveTo(W * 0.78, y - 40, W * 0.82, y - 10);
    ctx.lineTo(W * 0.82, y + 18);
    ctx.quadraticCurveTo(W * 0.78, y + 38, W * 0.72, y + 38);
    ctx.lineTo(W * 0.22, y + 38);
    ctx.quadraticCurveTo(W * 0.14, y + 30, W * 0.12, y);
    ctx.closePath();
    ctx.fill();

    // Cockpit windows
    ctx.fillStyle = "rgba(20,30,50,0.85)";
    roundRect(ctx, W * 0.18, y - 28, 48, 16, 6);
    ctx.fill();
    // cabin windows
    for (let i = 0; i < 14; i++) {
      const x = W * 0.28 + i * 22;
      roundRect(ctx, x, y - 18, 12, 10, 3);
      ctx.fill();
    }

    // Vertical stabilizer (tail)
    ctx.fillStyle = state.colors.tail;
    ctx.beginPath();
    ctx.moveTo(W * 0.74, y - 40);
    ctx.lineTo(W * 0.78, y - 130);
    ctx.lineTo(W * 0.88, y - 130);
    ctx.lineTo(W * 0.84, y - 40);
    ctx.closePath();
    ctx.fill();
    // horizontal stab
    ctx.beginPath();
    ctx.moveTo(W * 0.76, y - 8);
    ctx.lineTo(W * 0.92, y - 18);
    ctx.lineTo(W * 0.92, y - 4);
    ctx.lineTo(W * 0.78, y + 6);
    ctx.closePath();
    ctx.fill();

    // Team stripe
    if (state.stickers.stripe) {
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(W * 0.26, y + 8, W * 0.46, 8);
      ctx.fillStyle = state.colors.tail;
      ctx.fillRect(W * 0.26, y + 16, W * 0.46, 6);
    }

    // Heart
    if (state.stickers.heart) {
      drawHeart(ctx, W * 0.4, y - 5, 14, "#dc2840");
    }

    // Registration text
    if (state.stickers.text) {
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 20px Segoe UI, sans-serif";
      ctx.fillText(state.registration, W * 0.5, y - 8);
    }

    // Soacră photo decal
    if (state.soacra) {
      const pw = 48;
      const ph = 48;
      ctx.save();
      roundRect(ctx, W * 0.34, y + 20, pw, ph, 6);
      ctx.clip();
      ctx.drawImage(state.soacra, W * 0.34, y + 20, pw, ph);
      ctx.restore();
      ctx.strokeStyle = "rgba(255,255,255,0.5)";
      ctx.lineWidth = 2;
      roundRect(ctx, W * 0.34, y + 20, pw, ph, 6);
      ctx.stroke();
    }

    // Ground shadow
    ctx.fillStyle = "rgba(0,0,0,0.35)";
    ctx.beginPath();
    ctx.ellipse(W * 0.48, H * 0.82, 220 * scale, 14, 0, 0, Math.PI * 2);
    ctx.fill();

    // Label
    ctx.fillStyle = "rgba(143,160,191,0.9)";
    ctx.font = "12px Segoe UI, sans-serif";
    ctx.fillText(state.name + " · Asobo A320neo variation (mock)", 24, 28);
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
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

  /** Create flat PNG albedo as blob via offscreen canvas */
  function makeTexturePng(kind) {
    const size = 512;
    const c = document.createElement("canvas");
    c.width = size;
    c.height = size;
    const ctx = c.getContext("2d");
    if (kind === "fuselage") {
      ctx.fillStyle = state.colors.fuselage;
      ctx.fillRect(0, 0, size, size);
      const tw = Math.floor(size * 0.18);
      ctx.fillStyle = state.colors.tail;
      ctx.fillRect(size - tw, 0, tw, size);
      if (state.stickers.stripe) {
        ctx.fillStyle = "#fff";
        ctx.fillRect(40, size / 2 + 20, size - tw - 60, 16);
        ctx.fillStyle = state.colors.tail;
        ctx.fillRect(40, size / 2 + 36, size - tw - 60, 12);
      }
      if (state.stickers.heart) drawHeart(ctx, size / 3, size / 3, 28, "#dc2840");
      if (state.stickers.text) {
        ctx.fillStyle = "#fff";
        ctx.font = "bold 36px Segoe UI, sans-serif";
        ctx.fillText(state.registration, 100, 100);
      }
      if (state.soacra) {
        ctx.drawImage(state.soacra, size / 2 - 60, size / 2 + 40, 120, 120);
      }
    } else if (kind === "wings") {
      ctx.fillStyle = state.colors.wings;
      ctx.fillRect(0, 0, size, size);
    } else if (kind === "engines") {
      ctx.fillStyle = state.colors.engines;
      ctx.fillRect(0, 0, size, size);
    } else if (kind === "livery") {
      ctx.clearRect(0, 0, size, size);
      if (state.stickers.heart) drawHeart(ctx, size / 2, size / 2, 40, "#dc2840");
    } else if (kind === "texts") {
      ctx.clearRect(0, 0, size, size);
      ctx.fillStyle = "#fff";
      ctx.font = "bold 48px Segoe UI, sans-serif";
      ctx.fillText(state.registration, 40, size / 2);
    }
    // watermark
    if (kind !== "livery" && kind !== "texts") {
      ctx.fillStyle = "rgba(255,255,255,0.25)";
      ctx.font = "14px Segoe UI, sans-serif";
      ctx.fillText("SkinMyBird placeholder PNG — convert to DDS", 12, 24);
    }
    return new Promise((resolve) => c.toBlob((b) => resolve(b), "image/png"));
  }

  function aircraftCfg(slug, textureName, title) {
    return `[VERSION]
major = 1
minor = 0

[VARIATION]
base_container = "..\\\\Asobo_A320_NEO"

[FLTSIM.0]
title = "${title}"
model = ""
panel = ""
sound = ""
texture = "${textureName}"
description = "SkinMyBird custom A320neo livery — ${state.name}. Placeholder PNG textures."
wip_indicator = 0
ui_manufacturer = "Airbus"
ui_type = "A320neo"
ui_variation = "${state.name}"
ui_typerole = "Commercial Airliner"
ui_createdby = "SkinMyBird"
atc_id = "${state.registration}"
atc_airline = "SkinMyBird"
icao_airline = "SMB"
isAirTraffic = 0
isUserSelectable = 1
`;
  }

  function textureCfg() {
    return `[fltsim]
fallback.1=..\\..\\Asobo_A320_NEO\\texture
fallback.2=..\\..\\..\\..\\texture\\DetailMap
fallback.3=..\\..\\..\\..\\texture\\Glass
fallback.4=..\\..\\..\\..\\texture\\Interiors
fallback.5=..\\..\\..\\..\\texture
fallback.6=..\\..\\..\\..\\texture\\Livery
fallback.7=..\\..\\..\\..\\texture\\Planes_Generic
`;
  }

  async function generateZip() {
    if (typeof JSZip === "undefined") {
      alert("JSZip nu s-a încărcat. Verifică rețeaua / CDN.");
      return;
    }
    readInputs();
    const slug = slugify(state.name);
    const packageFolder = `skinmybird-a320neo-${slug}`;
    const aircraftFolder = `skinmybird_a320neo_${slug}`;
    const textureName = slug;
    const title = `Airbus A320 Neo SkinMyBird ${state.name}`;
    const base = `${packageFolder}/SimObjects/Airplanes/${aircraftFolder}`;
    const tex = `${base}/texture.${textureName}`;

    const zip = new JSZip();
    const manifest = {
      dependencies: [],
      content_type: "AIRCRAFT",
      title: `SkinMyBird A320neo — ${state.name}`,
      manufacturer: "Airbus",
      creator: "SkinMyBird",
      package_version: "0.1.0",
      minimum_game_version: "1.7.12",
      release_notes: {
        neutral: {
          LastUpdate: new Date().toISOString().slice(0, 10),
          OlderHistory: "SkinMyBird MVP placeholder PNG textures. Convert to DDS next.",
        },
      },
    };
    zip.file(`${packageFolder}/manifest.json`, JSON.stringify(manifest, null, 2));
    zip.file(`${base}/aircraft.cfg`, aircraftCfg(slug, textureName, title));
    zip.file(`${tex}/texture.cfg`, textureCfg());
    zip.file(
      `${packageFolder}/README_INSTALL_RO.md`,
      `# SkinMyBird — Instalare\n\nCopiază folderul \`${packageFolder}\` în Community, restart MSFS, alege livery **${state.name}**.\n\nTexturi = PNG placeholder → DDS + paintkit pe roadmap.\n`
    );
    zip.file(
      `${tex}/TEXTURES_README.txt`,
      "PLACEHOLDER PNG — replace with DDS from paintkit + texconv.\n"
    );

    const fuselage = await makeTexturePng("fuselage");
    const wings = await makeTexturePng("wings");
    const engines = await makeTexturePng("engines");
    const livery = await makeTexturePng("livery");
    const texts = await makeTexturePng("texts");
    zip.file(`${tex}/A320NEO_AIRFRAME_FUSELAGE_ALBD.png`, fuselage);
    zip.file(`${tex}/A320NEO_AIRFRAME_WINGS_ALBD.png`, wings);
    zip.file(`${tex}/A320NEO_AIRFRAME_ENGINES_ALBD.png`, engines);
    zip.file(`${tex}/A320NEO_AIRFRAME_LIVERY_ALBD.png`, livery);
    zip.file(`${tex}/A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.png`, texts);

    // layout.json after we know file list — rough sizes from blobs
    const content = [];
    const now = Date.now() / 1000;
    const date = Math.floor((now + 11644473600) * 10000000);
    async function addLayout(path, blobOrStr) {
      let size;
      if (typeof blobOrStr === "string") size = new Blob([blobOrStr]).size;
      else size = blobOrStr.size;
      content.push({ path, size, date });
    }
    await addLayout("manifest.json", JSON.stringify(manifest, null, 2));
    await addLayout(`SimObjects/Airplanes/${aircraftFolder}/aircraft.cfg`, aircraftCfg(slug, textureName, title));
    await addLayout(`SimObjects/Airplanes/${aircraftFolder}/texture.${textureName}/texture.cfg`, textureCfg());
    for (const [name, blob] of [
      ["A320NEO_AIRFRAME_FUSELAGE_ALBD.png", fuselage],
      ["A320NEO_AIRFRAME_WINGS_ALBD.png", wings],
      ["A320NEO_AIRFRAME_ENGINES_ALBD.png", engines],
      ["A320NEO_AIRFRAME_LIVERY_ALBD.png", livery],
      ["A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.png", texts],
    ]) {
      await addLayout(`SimObjects/Airplanes/${aircraftFolder}/texture.${textureName}/${name}`, blob);
    }
    zip.file(`${packageFolder}/layout.json`, JSON.stringify({ content }, null, 2));

    const blob = await zip.generateAsync({ type: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${packageFolder}.zip`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function downloadConfig() {
    const cfg = buildConfig();
    const blob = new Blob([JSON.stringify(cfg, null, 2)], { type: "application/json" });
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
    state.stickers = { stripe: true, heart: false, text: true };
    syncInputsFromState();
    drawPreview();
  }

  // Events
  ["c-fuselage", "c-wings", "c-engines", "c-tail", "livery-name", "registration", "st-stripe", "st-heart", "st-text"].forEach(
    (id) => {
      $(id).addEventListener("input", drawPreview);
      $(id).addEventListener("change", drawPreview);
    }
  );

  $("soacra").addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    state.soacraName = file.name;
    const img = new Image();
    img.onload = () => {
      state.soacra = img;
      $("soacra-label").textContent = file.name;
      drawPreview();
    };
    img.src = URL.createObjectURL(file);
  });

  $("btn-preset").addEventListener("click", applyEugen);
  $("btn-generate").addEventListener("click", () => {
    $("btn-generate").disabled = true;
    $("btn-generate").textContent = "Se generează…";
    generateZip()
      .catch((err) => alert("Eroare export: " + err.message))
      .finally(() => {
        $("btn-generate").disabled = false;
        $("btn-generate").textContent = "Generate package (ZIP)";
      });
  });
  $("btn-config").addEventListener("click", downloadConfig);

  syncInputsFromState();
  drawPreview();
})();
