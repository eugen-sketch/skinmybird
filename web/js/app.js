/**
 * SkinMyBird web editor — A320neo livery preview + browser ZIP export.
 *
 * UV RULES (see ASSUMPTIONS.md / exporter.export.A320NEO_TEXTS_UV):
 * - Airline titles → LIVERY_TEXTS side-title slots (NOT fuselage albedo / roof).
 * - Tail logos → LIVERY_TEXTS neo_logo_upper/lower slots.
 * - List thumbnails → Asobo-style 3/4 aircraft on light studio background.
 * Browser ZIP still emits PNG; convert to BC7 *.PNG.DDS before flight.
 */
/* SkinMyBird web UI — Canva-like editor, live A320neo preview, Community ZIP */
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
    stickerText: "YR-EUG",
    stickers: { stripe: true, heart: false, text: true },
    soacra: null,
    soacraName: null,
  };

  const EUGEN = {
    fuselage: "#FF6A00",
    wings: "#111111",
    engines: "#222222",
    tail: "#FF6A00",
    name: "Eugen Orange",
    registration: "YR-EUG",
    stickerText: "YR-EUG",
  };

  function syncInputsFromState() {
    $("c-fuselage").value = state.colors.fuselage;
    $("c-wings").value = state.colors.wings;
    $("c-engines").value = state.colors.engines;
    $("c-tail").value = state.colors.tail;
    $("livery-name").value = state.name;
    $("registration").value = state.registration;
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
      airline: "SkinMyBird",
      icao: "SMB",
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

  function updateSwatches() {
    const el = $("swatches");
    const entries = [
      ["Fuselaj", state.colors.fuselage],
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

  /** Improved A320neo side-profile silhouette */
  function drawPreview() {
    readInputs();
    updateSwatches();
    const canvas = $("preview");
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Sky / night ramp
    const sky = ctx.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#0e182c");
    sky.addColorStop(0.55, "#0a1220");
    sky.addColorStop(1, "#070c14");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, H);

    // Soft teal glow on tarmac
    const g = ctx.createRadialGradient(W * 0.5, H * 0.88, 10, W * 0.5, H * 0.9, W * 0.45);
    g.addColorStop(0, "rgba(61,214,198,0.14)");
    g.addColorStop(1, "rgba(61,214,198,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    const y = H * 0.55;

    // Ground shadow
    ctx.fillStyle = "rgba(0,0,0,0.4)";
    ctx.beginPath();
    ctx.ellipse(W * 0.48, H * 0.82, 260, 16, 0, 0, Math.PI * 2);
    ctx.fill();

    // Far wing (swept, above)
    ctx.fillStyle = state.colors.wings;
    ctx.beginPath();
    ctx.moveTo(W * 0.4, y - 6);
    ctx.lineTo(W * 0.18, y - 110);
    ctx.lineTo(W * 0.22, y - 95);
    ctx.quadraticCurveTo(W * 0.36, y - 40, W * 0.46, y + 2);
    ctx.closePath();
    ctx.fill();
    // Winglet hint
    ctx.beginPath();
    ctx.moveTo(W * 0.18, y - 110);
    ctx.lineTo(W * 0.155, y - 130);
    ctx.lineTo(W * 0.175, y - 118);
    ctx.closePath();
    ctx.fill();

    // Near wing (below fuselage)
    ctx.beginPath();
    ctx.moveTo(W * 0.42, y + 10);
    ctx.lineTo(W * 0.72, y + 38);
    ctx.lineTo(W * 0.74, y + 52);
    ctx.lineTo(W * 0.4, y + 28);
    ctx.closePath();
    ctx.fill();

    // Engines (CFM-style underwing pods)
    ctx.fillStyle = state.colors.engines;
    roundRect(ctx, W * 0.4, y + 20, 78, 40, 18);
    ctx.fill();
    roundRect(ctx, W * 0.54, y + 26, 68, 34, 15);
    ctx.fill();
    // Intake rings
    ctx.fillStyle = "rgba(255,255,255,0.12)";
    roundRect(ctx, W * 0.405, y + 28, 24, 24, 12);
    ctx.fill();
    roundRect(ctx, W * 0.545, y + 32, 20, 20, 10);
    ctx.fill();
    ctx.strokeStyle = "rgba(0,0,0,0.35)";
    ctx.lineWidth = 2;
    roundRect(ctx, W * 0.4, y + 20, 78, 40, 18);
    ctx.stroke();

    // Fuselage (tube + pointed nose + tapered tailcone)
    ctx.fillStyle = state.colors.fuselage;
    ctx.beginPath();
    ctx.moveTo(W * 0.1, y);
    ctx.quadraticCurveTo(W * 0.11, y - 34, W * 0.18, y - 40);
    ctx.lineTo(W * 0.7, y - 42);
    ctx.quadraticCurveTo(W * 0.78, y - 38, W * 0.82, y - 8);
    ctx.lineTo(W * 0.83, y + 16);
    ctx.quadraticCurveTo(W * 0.78, y + 38, W * 0.7, y + 38);
    ctx.lineTo(W * 0.2, y + 36);
    ctx.quadraticCurveTo(W * 0.12, y + 28, W * 0.1, y);
    ctx.closePath();
    ctx.fill();

    // Belly shade
    ctx.fillStyle = "rgba(0,0,0,0.12)";
    ctx.beginPath();
    ctx.moveTo(W * 0.16, y + 10);
    ctx.quadraticCurveTo(W * 0.45, y + 22, W * 0.78, y + 8);
    ctx.lineTo(W * 0.78, y + 34);
    ctx.quadraticCurveTo(W * 0.45, y + 42, W * 0.16, y + 32);
    ctx.closePath();
    ctx.fill();

    // Cockpit windows (A320 angled look)
    ctx.fillStyle = "rgba(18, 28, 48, 0.92)";
    ctx.beginPath();
    ctx.moveTo(W * 0.175, y - 28);
    ctx.lineTo(W * 0.235, y - 30);
    ctx.lineTo(W * 0.245, y - 14);
    ctx.lineTo(W * 0.17, y - 12);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "rgba(120, 170, 220, 0.15)";
    ctx.fill();

    // Cabin windows
    ctx.fillStyle = "rgba(20,30,50,0.88)";
    for (let i = 0; i < 16; i++) {
      const x = W * 0.27 + i * 24;
      roundRect(ctx, x, y - 16, 11, 9, 3);
      ctx.fill();
    }

    // Passenger doors hints
    ctx.strokeStyle = "rgba(0,0,0,0.2)";
    ctx.lineWidth = 1.5;
    roundRect(ctx, W * 0.25, y - 32, 14, 52, 3);
    ctx.stroke();
    roundRect(ctx, W * 0.68, y - 32, 14, 52, 3);
    ctx.stroke();

    // Vertical stabilizer (A320 fin)
    ctx.fillStyle = state.colors.tail;
    ctx.beginPath();
    ctx.moveTo(W * 0.72, y - 40);
    ctx.lineTo(W * 0.76, y - 145);
    ctx.lineTo(W * 0.88, y - 145);
    ctx.quadraticCurveTo(W * 0.9, y - 130, W * 0.86, y - 40);
    ctx.closePath();
    ctx.fill();
    // Fin leading edge shade
    ctx.fillStyle = "rgba(255,255,255,0.08)";
    ctx.beginPath();
    ctx.moveTo(W * 0.72, y - 40);
    ctx.lineTo(W * 0.76, y - 145);
    ctx.lineTo(W * 0.785, y - 145);
    ctx.lineTo(W * 0.74, y - 40);
    ctx.closePath();
    ctx.fill();

    // Horizontal stabilizer
    ctx.fillStyle = state.colors.tail;
    ctx.beginPath();
    ctx.moveTo(W * 0.74, y - 6);
    ctx.lineTo(W * 0.93, y - 20);
    ctx.lineTo(W * 0.94, y - 6);
    ctx.lineTo(W * 0.76, y + 8);
    ctx.closePath();
    ctx.fill();

    // APU exhaust hint
    ctx.fillStyle = "rgba(0,0,0,0.35)";
    roundRect(ctx, W * 0.805, y - 2, 14, 10, 3);
    ctx.fill();

    // Nose gear / main gear simple
    ctx.strokeStyle = "rgba(180,190,210,0.55)";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(W * 0.22, y + 36);
    ctx.lineTo(W * 0.22, y + 58);
    ctx.moveTo(W * 0.48, y + 36);
    ctx.lineTo(W * 0.48, y + 62);
    ctx.stroke();
    ctx.fillStyle = "#222";
    ctx.beginPath();
    ctx.arc(W * 0.22, y + 62, 7, 0, Math.PI * 2);
    ctx.arc(W * 0.46, y + 66, 9, 0, Math.PI * 2);
    ctx.arc(W * 0.5, y + 66, 9, 0, Math.PI * 2);
    ctx.fill();

    // Team stripe
    if (state.stickers.stripe) {
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(W * 0.26, y + 10, W * 0.44, 7);
      ctx.fillStyle = state.colors.tail;
      ctx.fillRect(W * 0.26, y + 17, W * 0.44, 5);
    }

    // Heart
    if (state.stickers.heart) {
      drawHeart(ctx, W * 0.38, y - 4, 13, "#dc2840");
    }

    // Registration / custom text
    if (state.stickers.text) {
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 22px Segoe UI, system-ui, sans-serif";
      ctx.fillText(state.stickerText || state.registration, W * 0.48, y - 6);
    }

    // Photo decal
    if (state.soacra) {
      const pw = 52;
      const ph = 52;
      const dx = W * 0.33;
      const dy = y + 18;
      ctx.save();
      roundRect(ctx, dx, dy, pw, ph, 6);
      ctx.clip();
      ctx.drawImage(state.soacra, dx, dy, pw, ph);
      ctx.restore();
      ctx.strokeStyle = "rgba(255,255,255,0.55)";
      ctx.lineWidth = 2;
      roundRect(ctx, dx, dy, pw, ph, 6);
      ctx.stroke();
    }

    // Title overlay
    ctx.fillStyle = "rgba(232,238,252,0.95)";
    ctx.font = "600 18px Segoe UI, system-ui, sans-serif";
    ctx.fillText(state.name, 28, 36);
    ctx.fillStyle = "rgba(143,160,191,0.95)";
    ctx.font = "13px Segoe UI, system-ui, sans-serif";
    ctx.fillText(
      state.registration + " · Asobo A320neo · SkinMyBird",
      28,
      56
    );
  }

  function makeTexturePng(kind) {
    const size = 2048;
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
        ctx.fillRect(80, size / 2 + 40, size - tw - 120, 28);
        ctx.fillStyle = state.colors.tail;
        ctx.fillRect(80, size / 2 + 68, size - tw - 120, 22);
      }
      if (state.stickers.heart) drawHeart(ctx, size / 3, size / 3, 55, "#dc2840");
      if (state.stickers.text) {
        ctx.fillStyle = "#fff";
        ctx.font = "bold 96px Segoe UI, sans-serif";
        ctx.fillText(state.stickerText || state.registration, 280, 280);
      }
      if (state.soacra) {
        ctx.drawImage(state.soacra, size / 2 - 140, size / 2 + 100, 280, 280);
      }
    } else if (kind === "wings") {
      ctx.fillStyle = state.colors.wings;
      ctx.fillRect(0, 0, size, size);
    } else if (kind === "engines") {
      ctx.fillStyle = state.colors.engines;
      ctx.fillRect(0, 0, size, size);
    } else if (kind === "livery") {
      ctx.clearRect(0, 0, size, size);
      if (state.stickers.heart) drawHeart(ctx, size / 2, size / 2, 80, "#dc2840");
    } else if (kind === "texts") {
      ctx.clearRect(0, 0, size, size);
      ctx.fillStyle = "#fff";
      ctx.font = "bold 120px Segoe UI, sans-serif";
      ctx.fillText(state.registration, 80, size / 2);
    }
    return new Promise((resolve) => c.toBlob((b) => resolve(b), "image/png"));
  }

  function canvasToJpegBlob(quality) {
    return new Promise((resolve) => {
      const src = $("preview");
      const c = document.createElement("canvas");
      c.width = 720;
      c.height = 404;
      const ctx = c.getContext("2d");
      ctx.fillStyle = "#0a101c";
      ctx.fillRect(0, 0, c.width, c.height);
      ctx.drawImage(src, 0, 0, c.width, c.height);
      c.toBlob((b) => resolve(b), "image/jpeg", quality || 0.88);
    });
  }

  function aircraftCfg(textureName, title) {
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
kb_checklists = ""
kb_reference = ""
description = "SkinMyBird custom A320neo livery — ${state.name}. Convert PNG→BC7 DDS before flight."
wip_indicator = 0
ui_manufacturer = "Airbus"
ui_type = "A320neo"
ui_variation = "${state.name}"
ui_typerole = "Commercial Airliner"
ui_createdby = "SkinMyBird"
atc_id = "${state.registration}"
atc_airline = "SkinMyBird"
atc_flight_number = "1"
icao_airline = "SMB"
isAirTraffic = 0
isUserSelectable = 1
`;
  }

  function textureCfg() {
    return `[fltsim]
fallback.1=..\\..\\..\\..\\texture\\DetailMap
fallback.2=..\\..\\..\\..\\texture\\Glass
fallback.3=..\\..\\..\\..\\texture\\Interiors
fallback.4=..\\..\\..\\..\\texture
fallback.5=..\\texture
fallback.6=..\\..\\Asobo_A320_NEO\\texture
`;
  }

  async function generateZip() {
    if (typeof JSZip === "undefined") {
      alert("JSZip nu s-a încărcat. Verifică rețeaua / CDN.");
      return;
    }
    readInputs();
    drawPreview();
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
      package_version: "0.2.0",
      minimum_game_version: "1.7.12",
      release_notes: {
        neutral: {
          LastUpdate: new Date().toISOString().slice(0, 10),
          OlderHistory:
            "Browser ZIP: PNG 2K + thumbnails. Convert to BC7 *.PNG.DDS with convert_to_dds / Python exporter before flight.",
        },
      },
    };
    const acCfg = aircraftCfg(textureName, title);
    const txCfg = textureCfg();
    const readme = `# SkinMyBird — Instalare

Copiază folderul \`${packageFolder}\` în **Community**, restart MSFS, alege **${state.name}**.

## IMPORTANT
MSFS 2020 are nevoie de texturi \`*.PNG.DDS\` (BC7), nu PNG simplu.
Acest ZIP din browser include PNG 2K + thumbnail-uri.
Pe PC rulează \`convert_to_dds.ps1\` din pachet SAU pe box:
\`python -m exporter.export --preset eugen-orange --zip\`

Fără DDS → fuselaj alb/albastru default.
`;

    zip.file(`${packageFolder}/manifest.json`, JSON.stringify(manifest, null, 2));
    zip.file(`${base}/aircraft.cfg`, acCfg);
    zip.file(`${tex}/texture.cfg`, txCfg);
    zip.file(`${packageFolder}/README_INSTALL_RO.md`, readme);
    zip.file(
      `${packageFolder}/convert_to_dds.ps1`,
      `# Convert PNG → BC7 *.PNG.DDS (MSFS Community)
$ErrorActionPreference = 'Stop'
$Texconv = $env:SKINMYBIRD_TEXCONV
if (-not $Texconv) { $Texconv = 'texconv.exe' }
$TexDir = Join-Path $PSScriptRoot 'SimObjects\\Airplanes\\${aircraftFolder}\\texture.${textureName}'
Get-ChildItem $TexDir -Filter '*.png' | ForEach-Object {
  & $Texconv -f BC7_UNORM -y -o $TexDir $_.FullName
  $dds = Join-Path $TexDir ($_.BaseName + '.dds')
  if (-not (Test-Path $dds)) { $dds = Join-Path $TexDir ($_.BaseName + '.DDS') }
  $dest = Join-Path $TexDir ($_.BaseName + '.PNG.DDS')
  Move-Item -Force $dds $dest
  @{ Version=2; SourceFileName=(Split-Path $dest -Leaf); Flags=@('FL_BITMAP_COMPRESSION','FL_BITMAP_MIPMAP') } |
    ConvertTo-Json | Set-Content ($dest + '.json') -Encoding UTF8
  Remove-Item $_.FullName -Force
}
Write-Host 'Gata. Regenerare layout.json recomandată via exporter Python.'
`
    );

    const fuselage = await makeTexturePng("fuselage");
    const wings = await makeTexturePng("wings");
    const engines = await makeTexturePng("engines");
    const livery = await makeTexturePng("livery");
    const texts = await makeTexturePng("texts");
    const thumb = await canvasToJpegBlob(0.88);
    // small thumb
    const smallBlob = await new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        const c = document.createElement("canvas");
        c.width = 256;
        c.height = 144;
        c.getContext("2d").drawImage(img, 0, 0, 256, 144);
        c.toBlob((b) => resolve(b), "image/jpeg", 0.85);
      };
      img.src = URL.createObjectURL(thumb);
    });

    zip.file(`${tex}/A320NEO_AIRFRAME_FUSELAGE_ALBD.png`, fuselage);
    zip.file(`${tex}/A320NEO_AIRFRAME_WINGS_ALBD.png`, wings);
    zip.file(`${tex}/A320NEO_AIRFRAME_ENGINES_ALBD.png`, engines);
    zip.file(`${tex}/A320NEO_AIRFRAME_LIVERY_ALBD.png`, livery);
    zip.file(`${tex}/A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.png`, texts);
    zip.file(`${tex}/thumbnail.jpg`, thumb);
    zip.file(`${tex}/thumbnail_small.jpg`, smallBlob);

    const content = [];
    const now = Date.now() / 1000;
    const date = Math.floor((now + 11644473600) * 10000000);
    async function addLayout(path, blobOrStr) {
      const size =
        typeof blobOrStr === "string"
          ? new Blob([blobOrStr]).size
          : blobOrStr.size;
      content.push({ path, size, date });
    }
    await addLayout("manifest.json", JSON.stringify(manifest, null, 2));
    await addLayout(`SimObjects/Airplanes/${aircraftFolder}/aircraft.cfg`, acCfg);
    await addLayout(
      `SimObjects/Airplanes/${aircraftFolder}/texture.${textureName}/texture.cfg`,
      txCfg
    );
    for (const [name, blob] of [
      ["A320NEO_AIRFRAME_FUSELAGE_ALBD.png", fuselage],
      ["A320NEO_AIRFRAME_WINGS_ALBD.png", wings],
      ["A320NEO_AIRFRAME_ENGINES_ALBD.png", engines],
      ["A320NEO_AIRFRAME_LIVERY_ALBD.png", livery],
      ["A320NEO_AIRFRAME_LIVERY_TEXTS_ALBD.png", texts],
      ["thumbnail.jpg", thumb],
      ["thumbnail_small.jpg", smallBlob],
    ]) {
      await addLayout(
        `SimObjects/Airplanes/${aircraftFolder}/texture.${textureName}/${name}`,
        blob
      );
    }
    zip.file(`${packageFolder}/layout.json`, JSON.stringify({ content }, null, 2));

    const blob = await zip.generateAsync({ type: "blob", compression: "DEFLATE" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${packageFolder}.zip`;
    a.click();
    URL.revokeObjectURL(a.href);
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
    state.stickerText = EUGEN.stickerText;
    state.stickers = { stripe: true, heart: false, text: true };
    syncInputsFromState();
    drawPreview();
  }

  function setBusy(busy) {
    ["btn-generate", "btn-generate-2"].forEach((id) => {
      const b = $(id);
      if (!b) return;
      b.disabled = busy;
      b.textContent = busy ? "Se generează…" : "Descarcă pachet ZIP";
    });
  }

  async function onGenerate() {
    setBusy(true);
    try {
      await generateZip();
    } catch (err) {
      alert("Eroare export: " + (err && err.message ? err.message : err));
    } finally {
      setBusy(false);
    }
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
    "sticker-text",
    "st-stripe",
    "st-heart",
    "st-text",
  ].forEach((id) => {
    const el = $(id);
    el.addEventListener("input", drawPreview);
    el.addEventListener("change", drawPreview);
  });

  $("soacra").addEventListener("change", (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    state.soacraName = file.name;
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
    $("soacra").value = "";
    $("soacra-label").textContent = "Încarcă o poză → decal pe fuselaj";
    $("btn-clear-photo").hidden = true;
    drawPreview();
  });

  $("btn-preset").addEventListener("click", applyEugen);
  $("btn-preset-2").addEventListener("click", applyEugen);
  $("btn-generate").addEventListener("click", onGenerate);
  $("btn-generate-2").addEventListener("click", onGenerate);
  $("btn-config").addEventListener("click", downloadConfig);

  syncInputsFromState();
  drawPreview();
})();
