/**
 * SkinMyBird 3D hangar preview — procedural meshes + OrbitControls.
 * ES module; Three.js via importmap CDN.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const TEX_W = 1024;
const TEX_H = 512;

function hexToThree(hex) {
  return new THREE.Color(hex || "#888888");
}

function shadeHex(hex, amt) {
  const n = (hex || "#888888").replace("#", "");
  const full =
    n.length === 3
      ? n
          .split("")
          .map((c) => c + c)
          .join("")
      : n;
  const num = parseInt(full, 16);
  let r = (num >> 16) + amt;
  let g = ((num >> 8) & 0xff) + amt;
  let b = (num & 0xff) + amt;
  r = Math.max(0, Math.min(255, r));
  g = Math.max(0, Math.min(255, g));
  b = Math.max(0, Math.min(255, b));
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`;
}

function disposeObject(obj) {
  if (!obj) return;
  obj.traverse((child) => {
    if (child.geometry) child.geometry.dispose();
    if (child.material) {
      const mats = Array.isArray(child.material)
        ? child.material
        : [child.material];
      mats.forEach((m) => {
        if (m.map) m.map.dispose();
        m.dispose();
      });
    }
  });
}

function matSolid(color, opts = {}) {
  return new THREE.MeshStandardMaterial({
    color: hexToThree(color),
    metalness: opts.metalness ?? 0.35,
    roughness: opts.roughness ?? 0.55,
    flatShading: false,
  });
}

function matTextured(map, fallbackColor) {
  return new THREE.MeshStandardMaterial({
    map,
    color: 0xffffff,
    metalness: 0.25,
    roughness: 0.6,
    // keep a tint if map fails
    ...(map ? {} : { color: hexToThree(fallbackColor) }),
  });
}

/** Resolve procedural shape family from profile.id / silhouette / category. */
export function resolveShapeFamily(profile) {
  if (!profile) return "narrow";
  const id = String(profile.id || "").toLowerCase();
  const sil = String(profile.silhouette || "").toLowerCase();
  const cat = String(profile.category || "").toLowerCase();
  const name = String(profile.displayName || "").toLowerCase();
  const blob = `${id} ${sil} ${cat} ${name}`;

  if (sil === "balloon" || cat === "balon" || blob.includes("balloon"))
    return "balloon";
  if (
    sil === "helicopter" ||
    cat === "elicopter" ||
    blob.includes("h135") ||
    blob.includes("helo") ||
    blob.includes("helicopter")
  )
    return "helicopter";
  if (blob.includes("747")) return "747";
  if (
    blob.includes("787") ||
    blob.includes("a330") ||
    blob.includes("dreamliner") ||
    blob.includes("wide")
  )
    return "widebody";
  if (blob.includes("a321")) return "narrow-long";
  if (
    blob.includes("a319") ||
    blob.includes("736") ||
    blob.includes("737") ||
    blob.includes("pmdg")
  )
    return "narrow-short";
  return "narrow";
}

function drawHeart2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(cx, cy + s * 0.3);
  ctx.bezierCurveTo(cx, cy, cx - s, cy, cx - s, cy + s * 0.35);
  ctx.bezierCurveTo(cx - s, cy + s * 0.8, cx, cy + s * 1.1, cx, cy + s * 1.4);
  ctx.bezierCurveTo(cx, cy + s * 1.1, cx + s, cy + s * 0.8, cx + s, cy + s * 0.35);
  ctx.bezierCurveTo(cx + s, cy, cx, cy, cx, cy + s * 0.3);
  ctx.fill();
}

/**
 * Paint livery onto an offscreen canvas → CanvasTexture.
 * Covers both sides of a cylinder UV unwrap (left + right halves).
 */
function paintFuselageCanvas(canvas, state, family) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  const fus = state.colors.fuselage || "#FF6A00";
  const tail = state.colors.tail || fus;
  const textColor = state.textColor || "#FFFFFF";

  ctx.clearRect(0, 0, W, H);

  // Base fuselage fill
  ctx.fillStyle = fus;
  ctx.fillRect(0, 0, W, H);

  // Subtle belly shade
  const belly = ctx.createLinearGradient(0, H * 0.55, 0, H);
  belly.addColorStop(0, "rgba(0,0,0,0)");
  belly.addColorStop(1, "rgba(0,0,0,0.22)");
  ctx.fillStyle = belly;
  ctx.fillRect(0, 0, W, H);

  // Upper highlight
  const top = ctx.createLinearGradient(0, 0, 0, H * 0.35);
  top.addColorStop(0, "rgba(255,255,255,0.14)");
  top.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = top;
  ctx.fillRect(0, 0, W, H);

  // Window row (skip balloon)
  if (family !== "balloon" && family !== "helicopter") {
    ctx.fillStyle = "#152030";
    const winY = H * 0.42;
    const winH = H * 0.055;
    const cols = family === "widebody" || family === "747" ? 28 : 18;
    for (let half = 0; half < 2; half++) {
      const x0 = half * (W / 2) + W * 0.08;
      for (let i = 0; i < cols; i++) {
        const wx = x0 + i * ((W * 0.38) / cols);
        ctx.fillRect(wx, winY, 10, winH);
      }
    }
  }

  // Team stripe
  if (state.stickers && state.stickers.stripe) {
    const sy = H * 0.58;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, sy, W, 10);
    ctx.fillStyle = tail;
    ctx.fillRect(0, sy + 10, W, 8);
  }

  // Heart
  if (state.stickers && state.stickers.heart) {
    drawHeart2d(ctx, W * 0.22, H * 0.28, 28, "#dc2840");
    drawHeart2d(ctx, W * 0.72, H * 0.28, 28, "#dc2840");
  }

  // Text / airline / registration
  if (state.stickers && state.stickers.text) {
    const sizeKey = state.textSize || "M";
    const px = sizeKey === "S" ? 28 : sizeKey === "L" ? 52 : 40;
    const weight = state.textStyle === "bold" ? "700" : "500";
    const place = state.textPlacement || "fuselage";

    ctx.fillStyle = textColor;
    ctx.textBaseline = "middle";
    ctx.shadowColor = "rgba(0,0,0,0.45)";
    ctx.shadowBlur = 6;

    const drawSideText = (xCenter) => {
      ctx.textAlign = "center";
      let y = H * 0.32;
      if (place === "belly") y = H * 0.72;
      if (place === "tail") y = H * 0.28;

      ctx.font = `${weight} ${px}px "Segoe UI", system-ui, sans-serif`;
      ctx.fillText(state.airline || "SkinMyBird", xCenter, y);

      if (state.slogan) {
        ctx.font = `500 ${Math.round(px * 0.5)}px "Segoe UI", system-ui, sans-serif`;
        ctx.globalAlpha = 0.92;
        ctx.fillText(state.slogan, xCenter, y + px * 0.55);
        ctx.globalAlpha = 1;
      }

      ctx.font = `600 ${Math.round(px * 0.42)}px "Segoe UI", system-ui, sans-serif`;
      const regY = place === "tail" ? y + px * 0.7 : H * 0.52;
      const regX = place === "tail" ? xCenter : xCenter + W * 0.12;
      ctx.fillText(state.registration || "", regX, regY);
    };

    // Left and right sides of cylinder UV
    drawSideText(W * 0.25);
    drawSideText(W * 0.75);
    ctx.shadowBlur = 0;
  }

  // Logo / photo (approximate)
  if (state.soacra) {
    try {
      const s = 96;
      ctx.drawImage(state.soacra, W * 0.18, H * 0.62, s, s);
      ctx.drawImage(state.soacra, W * 0.68, H * 0.62, s, s);
    } catch (_) {
      /* cross-origin / incomplete image */
    }
  }

  // Balloon-specific gore lines
  if (family === "balloon") {
    ctx.strokeStyle = shadeHex(tail, 0);
    ctx.globalAlpha = 0.45;
    ctx.lineWidth = 3;
    for (let i = 0; i < 8; i++) {
      const x = (i / 8) * W;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, H);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
}

function makeFuselageTexture(state, family) {
  const canvas = document.createElement("canvas");
  canvas.width = TEX_W;
  canvas.height = TEX_H;
  paintFuselageCanvas(canvas, state, family);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.ClampToEdgeWrapping;
  tex.needsUpdate = true;
  tex.userData.canvas = canvas;
  return tex;
}

function addBox(parent, w, h, d, x, y, z, material, rx = 0, ry = 0, rz = 0) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
  mesh.position.set(x, y, z);
  mesh.rotation.set(rx, ry, rz);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

function addCyl(parent, rTop, rBot, h, x, y, z, material, rx = 0, ry = 0, rz = 0, segs = 24) {
  const mesh = new THREE.Mesh(
    new THREE.CylinderGeometry(rTop, rBot, h, segs),
    material
  );
  mesh.position.set(x, y, z);
  mesh.rotation.set(rx, ry, rz);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

function buildAirliner(group, family, mats) {
  const specs = {
    narrow: { len: 10.5, rad: 0.55, wingSpan: 9.5, wingY: -0.15, engCount: 2, engScale: 1 },
    "narrow-short": { len: 9.2, rad: 0.52, wingSpan: 8.8, wingY: -0.12, engCount: 2, engScale: 0.95 },
    "narrow-long": { len: 12.2, rad: 0.55, wingSpan: 10.2, wingY: -0.15, engCount: 2, engScale: 1.05 },
    widebody: { len: 14.5, rad: 0.78, wingSpan: 13.5, wingY: -0.2, engCount: 2, engScale: 1.35 },
    "747": { len: 16.5, rad: 0.85, wingSpan: 15.5, wingY: -0.22, engCount: 4, engScale: 1.15 },
  };
  const s = specs[family] || specs.narrow;
  const half = s.len / 2;

  // Fuselage body (cylinder along Z → rotate to X)
  const fuselage = addCyl(
    group,
    s.rad,
    s.rad,
    s.len * 0.78,
    0,
    0,
    0,
    mats.fuselage,
    0,
    0,
    Math.PI / 2,
    32
  );
  fuselage.name = "fuselage";

  // Nose cone (pointing +X / forward)
  const nose = addCyl(
    group,
    0.02,
    s.rad,
    s.len * 0.14,
    half * 0.78 + (s.len * 0.07),
    0,
    0,
    mats.fuselage,
    0,
    0,
    Math.PI / 2,
    24
  );
  nose.name = "nose";

  // Cockpit glass tint
  addCyl(
    group,
    s.rad * 0.92,
    s.rad * 0.98,
    s.len * 0.06,
    half * 0.72,
    s.rad * 0.15,
    0,
    mats.glass,
    0,
    0,
    Math.PI / 2,
    16
  );

  // Tail cone
  addCyl(
    group,
    s.rad,
    s.rad * 0.15,
    s.len * 0.12,
    -half * 0.78 - s.len * 0.05,
    0,
    0,
    mats.fuselage,
    0,
    0,
    Math.PI / 2,
    20
  );

  // 747 upper-deck hump
  if (family === "747") {
    const hump = addCyl(
      group,
      s.rad * 0.55,
      s.rad * 0.72,
      s.len * 0.28,
      half * 0.25,
      s.rad * 0.55,
      0,
      mats.fuselage,
      0,
      0,
      Math.PI / 2,
      20
    );
    hump.name = "hump";
    // hump fairing toward nose
    addCyl(
      group,
      s.rad * 0.35,
      s.rad * 0.55,
      s.len * 0.1,
      half * 0.48,
      s.rad * 0.45,
      0,
      mats.fuselage,
      0,
      0,
      Math.PI / 2,
      16
    );
  }

  // Wings
  const wingChord = family === "widebody" || family === "747" ? 2.4 : 1.8;
  const wingThick = 0.12;
  const wingZ = s.wingSpan / 2;
  [-1, 1].forEach((side) => {
    const wing = addBox(
      group,
      wingChord,
      wingThick,
      wingZ,
      -0.3,
      s.wingY,
      (side * wingZ) / 2,
      mats.wings,
      0,
      0,
      side * 0.08
    );
    wing.name = "wing";
    // winglet
    addBox(
      group,
      0.35,
      0.9,
      0.08,
      -0.3 + wingChord * 0.15,
      s.wingY + 0.35,
      side * (wingZ - 0.1),
      mats.wings,
      0,
      0,
      side * -0.15
    );
  });

  // Engines under wing
  const engR = 0.28 * s.engScale;
  const engLen = 1.35 * s.engScale;
  const engY = s.wingY - 0.55;
  const positions =
    s.engCount === 4
      ? [
          [-0.2, engY, 2.2],
          [-0.2, engY, 4.6],
          [-0.2, engY, -2.2],
          [-0.2, engY, -4.6],
        ]
      : [
          [-0.15, engY, s.wingSpan * 0.28],
          [-0.15, engY, -s.wingSpan * 0.28],
        ];
  positions.forEach(([x, y, z]) => {
    const eng = addCyl(group, engR, engR * 0.85, engLen, x, y, z, mats.engines, 0, 0, Math.PI / 2, 20);
    eng.name = "engine";
    // intake lip
    addCyl(group, engR * 1.05, engR, 0.12, x + engLen * 0.48, y, z, mats.enginesDark, 0, 0, Math.PI / 2, 16);
    // pylon
    addBox(group, 0.5, 0.45, 0.1, x + 0.1, y + 0.35, z, mats.wings);
  });

  // Vertical stabilizer
  const finH = family === "747" || family === "widebody" ? 2.8 : 2.2;
  const fin = addBox(
    group,
    1.4,
    finH,
    0.12,
    -half * 0.72,
    finH * 0.45,
    0,
    mats.tail,
    0,
    0,
    -0.15
  );
  fin.name = "fin";

  // Horizontal stabilizer
  const stabSpan = family === "widebody" || family === "747" ? 5.2 : 3.8;
  addBox(
    group,
    1.1,
    0.08,
    stabSpan,
    -half * 0.78,
    0.35,
    0,
    mats.tail
  );

  // Landing gear (simple)
  addBox(group, 0.15, 0.7, 0.15, half * 0.35, -s.rad - 0.25, 0, mats.enginesDark);
  addBox(group, 0.15, 0.85, 0.15, -0.5, -s.rad - 0.3, 0.9, mats.enginesDark);
  addBox(group, 0.15, 0.85, 0.15, -0.5, -s.rad - 0.3, -0.9, mats.enginesDark);

  return { fuselageMeshes: [fuselage, nose] };
}

function buildHelicopter(group, mats) {
  // Cabin
  const cabin = addBox(group, 3.2, 1.5, 1.6, 0.2, 0.2, 0, mats.fuselage);
  cabin.name = "fuselage";
  // Rounded nose
  addCyl(group, 0.7, 0.75, 1.1, 1.7, 0.15, 0, mats.fuselage, 0, 0, Math.PI / 2, 16);
  // Cockpit glass
  addBox(group, 0.9, 0.7, 1.35, 1.55, 0.35, 0, mats.glass);

  // Boom
  const boom = addCyl(group, 0.18, 0.12, 4.2, -3.2, 0.35, 0, mats.tail, 0, 0, Math.PI / 2, 12);
  boom.name = "boom";

  // Tail fin
  addBox(group, 0.6, 1.1, 0.08, -5.1, 0.7, 0, mats.tail);

  // Skids
  addBox(group, 2.8, 0.08, 0.1, 0.1, -0.85, 0.7, mats.engines);
  addBox(group, 2.8, 0.08, 0.1, 0.1, -0.85, -0.7, mats.engines);
  addBox(group, 0.08, 0.55, 0.08, 0.8, -0.55, 0.7, mats.engines);
  addBox(group, 0.08, 0.55, 0.08, -0.6, -0.55, 0.7, mats.engines);
  addBox(group, 0.08, 0.55, 0.08, 0.8, -0.55, -0.7, mats.engines);
  addBox(group, 0.08, 0.55, 0.08, -0.6, -0.55, -0.7, mats.engines);

  // Main rotor hub + blades (animated group)
  const rotor = new THREE.Group();
  rotor.name = "mainRotor";
  rotor.position.set(0.1, 1.15, 0);
  group.add(rotor);
  addCyl(rotor, 0.12, 0.12, 0.35, 0, 0, 0, mats.wings);
  const bladeMat = mats.wings;
  for (let i = 0; i < 4; i++) {
    const blade = addBox(rotor, 5.5, 0.04, 0.22, 0, 0.12, 0, bladeMat);
    blade.rotation.y = (i * Math.PI) / 2;
  }

  // Tail rotor
  const tailRotor = new THREE.Group();
  tailRotor.name = "tailRotor";
  tailRotor.position.set(-5.2, 0.55, 0.25);
  group.add(tailRotor);
  for (let i = 0; i < 2; i++) {
    const blade = addBox(tailRotor, 0.08, 0.9, 0.12, 0, 0, 0, mats.wings);
    blade.rotation.z = (i * Math.PI) / 2;
  }

  return { fuselageMeshes: [cabin], anim: { mainRotor: rotor, tailRotor } };
}

function buildBalloon(group, mats) {
  // Envelope
  const envelope = new THREE.Mesh(
    new THREE.SphereGeometry(2.4, 32, 24),
    mats.fuselage
  );
  envelope.position.set(0, 3.2, 0);
  envelope.scale.set(1, 1.15, 1);
  envelope.name = "fuselage";
  envelope.castShadow = true;
  group.add(envelope);

  // Skirt / throat
  addCyl(group, 0.55, 0.85, 1.1, 0, 0.9, 0, mats.wings);

  // Cables
  const cableMat = new THREE.LineBasicMaterial({ color: 0xcccccc });
  const basketY = -0.6;
  const pts = [
    [0.5, 0.4, 0.5],
    [-0.5, 0.4, 0.5],
    [0.5, 0.4, -0.5],
    [-0.5, 0.4, -0.5],
  ];
  pts.forEach(([x, y, z]) => {
    const geo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(x * 1.4, 1.5, z * 1.4),
      new THREE.Vector3(x * 0.7, basketY + 0.5, z * 0.7),
    ]);
    group.add(new THREE.Line(geo, cableMat));
  });

  // Basket
  const basket = addBox(group, 1.1, 0.7, 1.1, 0, basketY, 0, mats.engines);
  basket.name = "basket";
  // rim
  addBox(group, 1.2, 0.1, 1.2, 0, basketY + 0.35, 0, mats.tail);

  return { fuselageMeshes: [envelope] };
}

function createMaterials(state, fuselageMap) {
  const eng = state.colors.engines || "#222222";
  return {
    fuselage: matTextured(fuselageMap, state.colors.fuselage),
    wings: matSolid(state.colors.wings || "#111111", { metalness: 0.4, roughness: 0.5 }),
    engines: matSolid(eng, { metalness: 0.55, roughness: 0.4 }),
    enginesDark: matSolid(shadeHex(eng, -30), { metalness: 0.6, roughness: 0.35 }),
    tail: matSolid(state.colors.tail || "#FF6A00", { metalness: 0.3, roughness: 0.55 }),
    glass: new THREE.MeshStandardMaterial({
      color: 0x152030,
      metalness: 0.8,
      roughness: 0.15,
      transparent: true,
      opacity: 0.85,
    }),
  };
}

export class Preview3D {
  constructor(canvas, stageEl) {
    this.canvas = canvas;
    this.stageEl = stageEl;
    this.renderer = null;
    this.scene = null;
    this.camera = null;
    this.controls = null;
    this.root = null;
    this.anim = null;
    this.fuselageTex = null;
    this.family = null;
    this.profileId = null;
    this.raf = 0;
    this.idleTimer = 0;
    this.userInteracting = false;
    this._ro = null;
    this.ok = false;
    this._lastStateKey = "";
  }

  static isWebGLAvailable() {
    try {
      const c = document.createElement("canvas");
      return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch {
      return false;
    }
  }

  init() {
    if (!Preview3D.isWebGLAvailable()) {
      this.ok = false;
      return false;
    }
    const canvas = this.canvas;
    const rect = this.stageEl.getBoundingClientRect();
    const w = Math.max(320, Math.floor(rect.width) || 800);
    const h = Math.max(280, Math.floor(rect.height) || 480);

    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h, false);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.setClearColor(0x000000, 0);

    this.scene = new THREE.Scene();

    this.camera = new THREE.PerspectiveCamera(42, w / h, 0.1, 200);
    this.camera.position.set(8, 3.5, 10);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 4;
    this.controls.maxDistance = 40;
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.controls.target.set(0, 0.5, 0);
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = 0.6;
    this.controls.update();

    const onStart = () => {
      this.userInteracting = true;
      this.controls.autoRotate = false;
    };
    const onEnd = () => {
      this.userInteracting = false;
      this.idleTimer = performance.now();
    };
    this.controls.addEventListener("start", onStart);
    this.controls.addEventListener("end", onEnd);

    // Lights
    const hemi = new THREE.HemisphereLight(0xc8d0e0, 0x1a1a1e, 0.7);
    this.scene.add(hemi);
    const key = new THREE.DirectionalLight(0xfff0e0, 1.15);
    key.position.set(6, 12, 8);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 40;
    key.shadow.camera.left = -15;
    key.shadow.camera.right = 15;
    key.shadow.camera.top = 15;
    key.shadow.camera.bottom = -15;
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0x88a0c0, 0.35);
    fill.position.set(-8, 4, -6);
    this.scene.add(fill);
    const rim = new THREE.DirectionalLight(0xff6a00, 0.25);
    rim.position.set(-4, 6, 10);
    this.scene.add(rim);

    // Hangar floor
    const floorGeo = new THREE.CircleGeometry(18, 48);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x1a1a1e,
      metalness: 0.2,
      roughness: 0.85,
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -1.35;
    floor.receiveShadow = true;
    this.scene.add(floor);

    // Soft grid helper
    const grid = new THREE.GridHelper(24, 24, 0x2a2a32, 0x1e1e24);
    grid.position.y = -1.34;
    grid.material.transparent = true;
    grid.material.opacity = 0.45;
    this.scene.add(grid);

    this.root = new THREE.Group();
    this.scene.add(this.root);

    this._ro = new ResizeObserver(() => this.resize());
    this._ro.observe(this.stageEl);

    this.ok = true;
    this.idleTimer = performance.now();
    this._loop();
    return true;
  }

  resize() {
    if (!this.renderer || !this.camera) return;
    const rect = this.stageEl.getBoundingClientRect();
    const w = Math.max(320, Math.floor(rect.width));
    const h = Math.max(280, Math.floor(rect.height));
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h, false);
  }

  resetCamera() {
    if (!this.camera || !this.controls) return;
    const family = this.family || "narrow";
    const dist =
      family === "balloon"
        ? 12
        : family === "747" || family === "widebody"
          ? 18
          : family === "helicopter"
            ? 11
            : 14;
    this.camera.position.set(dist * 0.55, dist * 0.28, dist * 0.7);
    this.controls.target.set(0, family === "balloon" ? 1.5 : 0.4, 0);
    this.controls.autoRotate = true;
    this.controls.update();
  }

  clearModel() {
    if (!this.root) return;
    while (this.root.children.length) {
      const child = this.root.children[0];
      this.root.remove(child);
      disposeObject(child);
    }
    if (this.fuselageTex) {
      this.fuselageTex.dispose();
      this.fuselageTex = null;
    }
    this.anim = null;
    this.mats = null;
  }

  buildModel(profile, state) {
    const family = resolveShapeFamily(profile);
    this.clearModel();
    this.family = family;
    this.profileId = profile ? profile.id : null;

    this.fuselageTex = makeFuselageTexture(state, family);
    const mats = createMaterials(state, this.fuselageTex);

    const craft = new THREE.Group();
    craft.name = "aircraft";
    let result;
    if (family === "balloon") result = buildBalloon(craft, mats);
    else if (family === "helicopter") result = buildHelicopter(craft, mats);
    else result = buildAirliner(craft, family, mats);

    // Lift craft so gear sits near floor
    if (family === "balloon") craft.position.y = 0.2;
    else if (family === "helicopter") craft.position.y = 0.5;
    else craft.position.y = 0.15;

    this.root.add(craft);
    this.anim = (result && result.anim) || null;
    this.mats = mats;

    this.resetCamera();
    this._lastStateKey = "";
    this.applyPaint(state);
  }

  applyPaint(state) {
    if (!this.ok || !this.root) return;
    const family = this.family || "narrow";
    const key = JSON.stringify({
      c: state.colors,
      a: state.airline,
      r: state.registration,
      s: state.slogan,
      tc: state.textColor,
      ts: state.textSize,
      ty: state.textStyle,
      tp: state.textPlacement,
      st: state.stickers,
      photo: state.soacraName || null,
      fam: family,
    });
    if (key === this._lastStateKey) return;
    this._lastStateKey = key;

    // Update canvas texture (colors + text + stickers)
    if (this.fuselageTex && this.fuselageTex.userData.canvas) {
      paintFuselageCanvas(this.fuselageTex.userData.canvas, state, family);
      this.fuselageTex.needsUpdate = true;
    }

    const mats = this.mats;
    if (!mats) return;
    if (mats.wings) mats.wings.color.copy(hexToThree(state.colors.wings));
    if (mats.engines) mats.engines.color.copy(hexToThree(state.colors.engines));
    if (mats.enginesDark)
      mats.enginesDark.color.copy(hexToThree(shadeHex(state.colors.engines, -30)));
    if (mats.tail) mats.tail.color.copy(hexToThree(state.colors.tail));
  }

  setProfile(profile, state) {
    if (!this.ok) return;
    // Editor may have just become visible — sync canvas size
    this.resize();
    if (!profile) {
      this.clearModel();
      this.profileId = null;
      return;
    }
    if (this.profileId !== profile.id) {
      this.buildModel(profile, state);
    } else {
      this.applyPaint(state);
    }
  }

  _loop = () => {
    this.raf = requestAnimationFrame(this._loop);
    if (!this.ok) return;

    // Resume auto-rotate after idle ~4s
    if (
      !this.userInteracting &&
      !this.controls.autoRotate &&
      performance.now() - this.idleTimer > 4000
    ) {
      this.controls.autoRotate = true;
    }

    if (this.anim) {
      if (this.anim.mainRotor) this.anim.mainRotor.rotation.y += 0.12;
      if (this.anim.tailRotor) this.anim.tailRotor.rotation.x += 0.25;
    }

    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  };

  dispose() {
    cancelAnimationFrame(this.raf);
    if (this._ro) this._ro.disconnect();
    this.clearModel();
    if (this.controls) this.controls.dispose();
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer = null;
    }
    this.ok = false;
  }
}

export default Preview3D;
