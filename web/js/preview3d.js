/**
 * SkinMyBird 3D hangar preview — real airliner GLBs + procedural helo/balloon.
 * ES module; Three.js via local vendor importmap (no CDN).
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DecalGeometry } from "three/addons/geometries/DecalGeometry.js";

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

const GLB_TARGET_SPAN = 12;
const glbCache = new Map(); // url -> Promise<GLTF>
let _gltfLoader = null;

function getGltfLoader() {
  if (!_gltfLoader) _gltfLoader = new GLTFLoader();
  return _gltfLoader;
}

/** Map profile → vendored GLB path, or null for procedural (helo/balloon). */
export function resolveGlbUrl(profile) {
  if (!profile) return null;
  const id = String(profile.id || "").toLowerCase();
  const sil = String(profile.silhouette || "").toLowerCase();
  const cat = String(profile.category || "").toLowerCase();
  const name = String(profile.displayName || "").toLowerCase();
  const blob = `${id} ${sil} ${cat} ${name}`;

  if (sil === "balloon" || cat === "balon" || blob.includes("balloon"))
    return null;
  if (
    sil === "helicopter" ||
    cat === "elicopter" ||
    blob.includes("h135") ||
    blob.includes("helo") ||
    blob.includes("helicopter")
  )
    return null;

  if (blob.includes("787") || blob.includes("dreamliner"))
    return "models/b787.glb";
  if (
    blob.includes("737") ||
    blob.includes("736") ||
    blob.includes("pmdg")
  )
    return "models/b737.glb";
  // Widebody stand-in (A350 GLB): A330 / 747 / generic wide — 747 is not exact
  if (
    blob.includes("747") ||
    blob.includes("a330") ||
    blob.includes("a350") ||
    blob.includes("widebody") ||
    blob.includes("wide-body")
  )
    return "models/a350.glb";
  // A320 / A319 / A321 / FBW / LatinVFR Airbus + default airliner
  return "models/a320.glb";
}

function loadGlbCached(url) {
  if (!glbCache.has(url)) {
    glbCache.set(
      url,
      new Promise((resolve, reject) => {
        getGltfLoader().load(
          url,
          (gltf) => resolve(gltf),
          undefined,
          (err) => {
            glbCache.delete(url);
            reject(err);
          }
        );
      })
    );
  }
  return glbCache.get(url);
}

/**
 * Orient so smallest extent → +Y (up), longest → +X (forward), then
 * scale to ~span 12 and sit on y=0.
 */
function fitAircraftToHangar(model, targetSpan = GLB_TARGET_SPAN) {
  model.updateMatrixWorld(true);
  const box0 = new THREE.Box3().setFromObject(model);
  const size0 = box0.getSize(new THREE.Vector3());

  const axes = [
    { len: size0.x, dir: new THREE.Vector3(1, 0, 0) },
    { len: size0.y, dir: new THREE.Vector3(0, 1, 0) },
    { len: size0.z, dir: new THREE.Vector3(0, 0, 1) },
  ].sort((a, b) => a.len - b.len);

  const up = axes[0].dir.clone();
  const forward = axes[2].dir.clone();
  let right = new THREE.Vector3().crossVectors(forward, up);
  if (right.lengthSq() < 1e-8) {
    right = axes[1].dir.clone();
  }
  right.normalize();
  const upOrtho = new THREE.Vector3().crossVectors(right, forward).normalize();
  forward.normalize();

  // Matrix whose columns map unit axes → (forward, up, right); invert to remap model
  const basis = new THREE.Matrix4().makeBasis(forward, upOrtho, right);
  const inv = basis.clone().invert();
  model.applyMatrix4(inv);

  model.updateMatrixWorld(true);
  let box = new THREE.Box3().setFromObject(model);
  let size = box.getSize(new THREE.Vector3());
  // Prefer wing span (Z after remap) but fall back to max horizontal
  const span = Math.max(size.z, size.x * 0.85, 0.001);
  const scale = targetSpan / span;
  model.scale.multiplyScalar(scale);

  model.updateMatrixWorld(true);
  box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  model.position.x -= center.x;
  model.position.z -= center.z;
  model.position.y -= box.min.y;

  model.updateMatrixWorld(true);
  return model;
}

function cloneMaterialsDeep(root) {
  root.traverse((child) => {
    if (!child.isMesh) return;
    child.castShadow = true;
    child.receiveShadow = true;
    if (!child.material) return;
    if (Array.isArray(child.material)) {
      child.material = child.material.map((m) => m.clone());
    } else {
      child.material = child.material.clone();
    }
  });
}

function classifyMeshRole(name, box, craftBox) {
  const n = String(name || "").toLowerCase();
  if (/engine|nacelle|motor|fan|pylon/.test(n)) return "engines";
  if (/wing|aileron|flap|slat|winglet/.test(n)) return "wings";
  if (/tail|fin|rudder|stabil|elevator|htail|vtail/.test(n)) return "tail";
  if (/fusel|body|hull|cabin|cockpit|nose/.test(n)) return "fuselage";
  // Bounding-box heuristic when names are generic (single-mesh models)
  if (!craftBox || !box) return "fuselage";
  const cSize = craftBox.getSize(new THREE.Vector3());
  const mSize = box.getSize(new THREE.Vector3());
  const cCenter = craftBox.getCenter(new THREE.Vector3());
  const mCenter = box.getCenter(new THREE.Vector3());
  // Engines: small, below center
  if (mSize.x < cSize.x * 0.35 && mCenter.y < cCenter.y - cSize.y * 0.05)
    return "engines";
  // Wings: wide in Z, thin in Y, near mid height
  if (mSize.z > cSize.z * 0.55 && mSize.y < cSize.y * 0.35) return "wings";
  // Tail: aft (low X if nose=+X)
  if (mCenter.x < cCenter.x - cSize.x * 0.25) return "tail";
  return "fuselage";
}

const FONT_STACKS = {
  segoe: '"Segoe UI", system-ui, sans-serif',
  arial: 'Arial, Helvetica, sans-serif',
  georgia: 'Georgia, "Times New Roman", serif',
  impact: 'Impact, Haettenschweiler, "Arial Narrow Bold", sans-serif',
  courier: '"Courier New", Courier, monospace',
  trebuchet: '"Trebuchet MS", "Segoe UI", sans-serif',
  verdana: 'Verdana, Geneva, sans-serif',
  comic: '"Comic Sans MS", "Comic Sans", cursive',
};

function resolveFontStack(key) {
  return FONT_STACKS[key] || FONT_STACKS.segoe;
}

/** Map textStyle → CSS font style + weight for canvas. */
function resolveFontFace(state, px) {
  const style = String(state.textStyle || "bold").toLowerCase();
  const italic = style.includes("italic") ? "italic " : "";
  let weight = "400";
  if (style === "bold" || style === "bold-italic" || style === "bolditalic") weight = "700";
  else if (style === "normal" || style === "regular") weight = "400";
  else if (style === "italic") weight = "400";
  else if (style.includes("bold")) weight = "700";
  const stack = resolveFontStack(state.textFont);
  return `${italic}${weight} ${Math.round(px)}px ${stack}`;
}

/** Shrink font until text fits maxWidth; returns used px. */
function fitFontPx(ctx, text, maxWidth, basePx, state, minPx = 10) {
  let px = basePx;
  while (px > minPx) {
    ctx.font = resolveFontFace(state, px);
    if (ctx.measureText(text || "").width <= maxWidth) return px;
    px -= 2;
  }
  ctx.font = resolveFontFace(state, minPx);
  return minPx;
}

function drawStar2d(ctx, cx, cy, r, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  for (let i = 0; i < 5; i++) {
    const a = -Math.PI / 2 + (i * 2 * Math.PI) / 5;
    const b = a + Math.PI / 5;
    const x1 = cx + Math.cos(a) * r;
    const y1 = cy + Math.sin(a) * r;
    const x2 = cx + Math.cos(b) * (r * 0.4);
    const y2 = cy + Math.sin(b) * (r * 0.4);
    if (i === 0) ctx.moveTo(x1, y1);
    else ctx.lineTo(x1, y1);
    ctx.lineTo(x2, y2);
  }
  ctx.closePath();
  ctx.fill();
}

function drawLightning2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(cx - s * 0.15, cy - s);
  ctx.lineTo(cx + s * 0.35, cy - s * 0.15);
  ctx.lineTo(cx + s * 0.05, cy - s * 0.15);
  ctx.lineTo(cx + s * 0.4, cy + s);
  ctx.lineTo(cx - s * 0.2, cy + s * 0.05);
  ctx.lineTo(cx + s * 0.05, cy + s * 0.05);
  ctx.closePath();
  ctx.fill();
}

function drawBird2d(ctx, cx, cy, s, color) {
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(2, s * 0.18);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(cx - s, cy + s * 0.15);
  ctx.quadraticCurveTo(cx - s * 0.35, cy - s * 0.7, cx, cy);
  ctx.quadraticCurveTo(cx + s * 0.35, cy - s * 0.7, cx + s, cy + s * 0.15);
  ctx.stroke();
}

function drawRoundel2d(ctx, cx, cy, r, colors) {
  const rings = colors || ["#dc2840", "#ffffff", "#1a3a8a"];
  rings.forEach((c, i) => {
    ctx.fillStyle = c;
    ctx.beginPath();
    ctx.arc(cx, cy, r * (1 - i * 0.28), 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawChevron2d(ctx, cx, cy, s, color) {
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(3, s * 0.2);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (let i = 0; i < 3; i++) {
    const x = cx - s * 0.5 + i * s * 0.45;
    ctx.beginPath();
    ctx.moveTo(x, cy - s * 0.55);
    ctx.lineTo(x + s * 0.4, cy);
    ctx.lineTo(x, cy + s * 0.55);
    ctx.stroke();
  }
}

function drawCheckered2d(ctx, x, y, w, h, cols, colorA, colorB) {
  const cw = w / cols;
  const rows = Math.max(2, Math.round(h / cw));
  const ch = h / rows;
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      ctx.fillStyle = (row + col) % 2 === 0 ? colorA : colorB;
      ctx.fillRect(x + col * cw, y + row * ch, cw + 0.5, ch + 0.5);
    }
  }
}

function drawStickersOnCanvas(ctx, W, H, state, layout) {
  const st = state.stickers || {};
  const accent = state.colors && state.colors.tail ? state.colors.tail : "#FF6A00";
  // layout: "decal" (single panel) or "half" with x0 offset for procedural sides
  const xMid = layout.xMid != null ? layout.xMid : W / 2;
  const scale = layout.scale || 1;

  if (st.stripe) {
    const sy = layout.stripeY != null ? layout.stripeY : H * 0.82;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(layout.x0 || 0, sy, layout.bandW || W, 8 * scale);
    ctx.fillStyle = accent;
    ctx.fillRect(layout.x0 || 0, sy + 8 * scale, layout.bandW || W, 6 * scale);
  }
  if (st.heart) {
    drawHeart2d(ctx, xMid - 70 * scale, H * 0.22, 16 * scale, "#dc2840");
  }
  if (st.star) {
    drawStar2d(ctx, xMid + 80 * scale, H * 0.2, 18 * scale, "#ffd24a");
  }
  if (st.lightning) {
    drawLightning2d(ctx, (layout.x0 || 0) + 40 * scale, H * 0.55, 22 * scale, "#ffe566");
  }
  if (st.bird) {
    drawBird2d(ctx, xMid, H * 0.88, 28 * scale, state.textColor || "#FFFFFF");
  }
  if (st.roundel) {
    drawRoundel2d(ctx, (layout.x0 || 0) + W * 0.08 * (layout.bandW ? 1 : 1) + 36 * scale, H * 0.55, 22 * scale);
  }
  if (st.chevron) {
    drawChevron2d(ctx, xMid + 100 * scale, H * 0.55, 20 * scale, "#ffffff");
  }
  if (st.checkered) {
    const bw = layout.bandW || W;
    const x0 = layout.x0 || 0;
    drawCheckered2d(ctx, x0, H * 0.05, bw, 18 * scale, 16, "#111111", "#f5f5f5");
  }
}

function paintDecalCanvas(canvas, state) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const st = state.stickers || {};
  const anySticker =
    st.stripe || st.heart || st.star || st.lightning || st.bird ||
    st.roundel || st.chevron || st.checkered;
  const showText = !!st.text;

  if (anySticker) {
    drawStickersOnCanvas(ctx, W, H, state, { xMid: W / 2, scale: 1.2 });
  }

  if (!showText) return;

  const textColor = state.textColor || "#FFFFFF";
  const sizeKey = state.textSize || "M";
  const basePx = sizeKey === "S" ? 42 : sizeKey === "L" ? 86 : 62;
  const maxW = W * 0.92;

  ctx.fillStyle = textColor;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.shadowColor = "rgba(0,0,0,0.55)";
  ctx.shadowBlur = 8;

  const airline = state.airline || "SkinMyBird";
  const airPx = fitFontPx(ctx, airline, maxW, basePx, state, 14);
  ctx.font = resolveFontFace(state, airPx);
  ctx.fillText(airline, W / 2, H * 0.36);

  if (state.slogan) {
    const sloganState = { ...state, textStyle: state.textStyle === "bold-italic" || state.textStyle === "italic" ? "italic" : "regular" };
    // keep weight lighter for slogan but honor italic
    const style = String(state.textStyle || "").toLowerCase();
    const sloganStyle = style.includes("italic")
      ? (style.includes("bold") ? "bold-italic" : "italic")
      : "regular";
    const sState = { ...state, textStyle: sloganStyle };
    const sPx = fitFontPx(ctx, state.slogan, maxW, Math.round(basePx * 0.48), sState, 12);
    ctx.font = resolveFontFace(sState, sPx);
    ctx.fillText(state.slogan, W / 2, H * 0.36 + airPx * 0.58);
  }

  // Registration drawn on primary wrap only when placement is fuselage/belly;
  // secondary rear decal handles it for GLB — still paint lightly here as fallback.
  if (state.registration && (state.textPlacement === "fuselage" || state.textPlacement === "belly")) {
    const rState = { ...state, textStyle: "bold" };
    const rPx = fitFontPx(ctx, state.registration, maxW * 0.4, Math.round(basePx * 0.38), rState, 10);
    ctx.font = resolveFontFace(rState, rPx);
    ctx.globalAlpha = 0.9;
    ctx.fillText(state.registration, W * 0.82, H * 0.72);
    ctx.globalAlpha = 1;
  }
  ctx.shadowBlur = 0;
}

function makeDecalTexture(state, w = 1536, h = 256) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  paintDecalCanvas(canvas, state);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.needsUpdate = true;
  tex.userData.canvas = canvas;
  return tex;
}

/**
 * Collect mesh targets for decal projection. Prefer fuselage-role / larger meshes.
 */
function collectDecalTargetMeshes(craft) {
  craft.updateMatrixWorld(true);
  const craftBox = new THREE.Box3().setFromObject(craft);
  const scored = [];
  craft.traverse((child) => {
    if (!child.isMesh || !child.geometry) return;
    if (child.name === "textDecals" || (child.parent && child.parent.name === "textDecals"))
      return;
    // Skip existing decal meshes
    if (child.userData && child.userData.isTextDecal) return;
    const box = new THREE.Box3().setFromObject(child);
    const size = box.getSize(new THREE.Vector3());
    const vol = Math.max(size.x, 0.001) * Math.max(size.y, 0.001) * Math.max(size.z, 0.001);
    if (vol < 0.02) return;
    const role = classifyMeshRole(child.name, box, craftBox);
    scored.push({ mesh: child, role, vol, box, size });
  });
  scored.sort((a, b) => b.vol - a.vol);
  const fuselage = scored.filter((s) => s.role === "fuselage");
  const wings = scored.filter((s) => s.role === "wings");
  const tail = scored.filter((s) => s.role === "tail");
  return { all: scored.map((s) => s.mesh), fuselage, wings, tail, craftBox, scored };
}

/**
 * World-space Euler so projector −Z looks along worldNormal
 * (Three Object3D.lookAt / official webgl_decals convention).
 */
function orientationFromWorldNormal(worldNormal, worldUpHint) {
  const n = worldNormal.clone().normalize();
  let up = (worldUpHint || new THREE.Vector3(0, 1, 0)).clone().normalize();
  if (Math.abs(n.dot(up)) > 0.92) {
    // Belly / spine: use aircraft forward (+X) as lookAt up-hint
    up.set(1, 0, 0);
  }
  const dummy = new THREE.Object3D();
  dummy.up.copy(up);
  dummy.position.set(0, 0, 0);
  dummy.lookAt(n);
  return dummy.rotation.clone();
}

/**
 * Raycast from outside toward the craft; return best hit or null.
 * origins: array of THREE.Vector3 in world space
 * dir: THREE.Vector3 (will be normalized)
 */
function raycastBestHit(meshes, origin, dir, raycaster) {
  if (!meshes.length) return null;
  raycaster.set(origin, dir.clone().normalize());
  const hits = raycaster.intersectObjects(meshes, true);
  for (const h of hits) {
    if (!h.face || !h.object || !h.object.isMesh) continue;
    if (h.object.userData && h.object.userData.isTextDecal) continue;
    return h;
  }
  return null;
}

function sideMaterialFromTex(baseTex, flipU, sharedMatOpts) {
  const matMap = baseTex.clone();
  matMap.userData = baseTex.userData;
  if (flipU) {
    matMap.repeat.x = -1;
    matMap.offset.x = 1;
  }
  matMap.needsUpdate = true;
  return new THREE.MeshBasicMaterial({
    ...sharedMatOpts,
    map: matMap,
  });
}

/**
 * Project a canvas texture onto mesh surface via DecalGeometry (no free-floating planes).
 *
 * Local-space note: DecalGeometry transforms mesh verts by mesh.matrixWorld, so
 * `position` + `orientation` MUST be in **world** space (same as the official
 * webgl_decals example). We then `group.attach(mesh)` so world-space geometry
 * stays correct under the craft hierarchy (attach = keep world matrix).
 */
function projectDecal(group, hit, size, material, renderOrder = 2) {
  if (!hit || !hit.face || !hit.object) return null;

  hit.object.updateMatrixWorld(true);

  const worldPoint = hit.point.clone();
  const normalMatrix = new THREE.Matrix3().getNormalMatrix(hit.object.matrixWorld);
  const worldNormal = hit.face.normal
    .clone()
    .applyNormalMatrix(normalMatrix)
    .normalize();

  const orientation = orientationFromWorldNormal(worldNormal);

  let geo;
  try {
    geo = new DecalGeometry(hit.object, worldPoint, orientation, size);
  } catch (err) {
    console.warn("DecalGeometry failed", err);
    return null;
  }

  // Empty projector (missed surface) — skip
  const posAttr = geo.getAttribute("position");
  if (!posAttr || posAttr.count < 3) {
    geo.dispose();
    return null;
  }

  const mesh = new THREE.Mesh(geo, material);
  mesh.userData.isTextDecal = true;
  mesh.renderOrder = renderOrder;
  mesh.receiveShadow = false;
  mesh.castShadow = false;
  // Geometry is in world space; attach preserves world transform under group/craft
  group.attach(mesh);
  return mesh;
}

/**
 * Mesh-projected text/sticker decals on BOTH sides of the fuselage (or belly/tail/wing).
 * Never places free-floating PlaneGeometry in empty space.
 */
function addTextDecals(craft, state) {
  craft.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(craft);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());

  const group = new THREE.Group();
  group.name = "textDecals";
  // Identity under craft so attach() math stays simple
  craft.add(group);
  craft.updateMatrixWorld(true);

  const st = state.stickers || {};
  const anyVisual =
    st.text || st.stripe || st.heart || st.star || st.lightning ||
    st.bird || st.roundel || st.chevron || st.checkered;
  if (!anyVisual) {
    return { tex: null, mat: null, group, regTex: null };
  }

  const place = state.textPlacement || "fuselage";
  const tex = makeDecalTexture(state, 1536, 256);
  const sharedMatOpts = {
    map: tex,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    side: THREE.FrontSide,
    polygonOffset: true,
    polygonOffsetFactor: -4,
    polygonOffsetUnits: -4,
  };

  const targets = collectDecalTargetMeshes(craft);
  const raycaster = new THREE.Raycaster();
  // Avoid tiny self-hits; start a bit out
  raycaster.near = 0;
  raycaster.far = 100;

  const fusLen = size.x;
  const panelLen =
    place === "tail" ? fusLen * 0.32 :
    place === "wing" ? Math.min(size.z * 0.28, fusLen * 0.35) :
    fusLen * 0.62;
  const panelH =
    place === "wing" ? Math.max(0.35, panelLen * 0.35) :
    Math.max(0.55, Math.min(size.y * 0.55, 1.15));
  const panelDepth = Math.max(0.35, Math.min(size.y * 0.35, 0.55));
  const decalSize = new THREE.Vector3(panelLen, panelH, panelDepth);

  // Sample X along fuselage
  let xMain = center.x + size.x * 0.02;
  if (place === "tail") xMain = center.x - size.x * 0.28;
  else if (place === "wing") xMain = center.x - size.x * 0.02;

  const yWindow = center.y + size.y * 0.02;
  const yAlts = [
    yWindow,
    center.y + size.y * 0.08,
    center.y - size.y * 0.06,
    center.y + size.y * 0.14,
  ];

  const reach = Math.max(size.z, size.y, size.x) * 1.25 + 2;

  function meshesForPlace() {
    if (place === "wing" && targets.wings.length)
      return targets.wings.map((t) => t.mesh);
    if (place === "tail") {
      const list = targets.tail.map((t) => t.mesh);
      const fus = targets.fuselage.map((t) => t.mesh);
      if (list.length || fus.length) return list.concat(fus);
    }
    if (targets.fuselage.length) return targets.fuselage.map((t) => t.mesh);
    // Fallback: prefer meshes near centerline (fuselage), not wing tips
    const cz = center.z;
    const nearCenter = targets.scored
      .filter((s) => {
        const c = s.box.getCenter(new THREE.Vector3());
        return Math.abs(c.z - cz) < size.z * 0.22;
      })
      .map((s) => s.mesh);
    if (nearCenter.length) return nearCenter.slice(0, 8);
    return targets.all.slice(0, 6);
  }

  const meshList = meshesForPlace();

  function trySideHit(sideSign, x, yCandidates) {
    // sideSign: +1 = +Z (right), −1 = −Z (left)
    for (const y of yCandidates) {
      let origin, dir;
      if (place === "belly") {
        origin = new THREE.Vector3(x, center.y - reach, center.z + sideSign * 0.05);
        dir = new THREE.Vector3(0, 1, -sideSign * 0.02).normalize();
      } else if (place === "wing") {
        origin = new THREE.Vector3(
          x,
          center.y + reach * 0.55,
          center.z + sideSign * size.z * 0.28
        );
        dir = new THREE.Vector3(0, -1, 0);
      } else {
        // Fuselage / tail: from outside toward centerline
        origin = new THREE.Vector3(x, y, center.z + sideSign * reach);
        dir = new THREE.Vector3(0, 0, -sideSign);
      }
      const hit = raycastBestHit(meshList, origin, dir, raycaster);
      if (hit) return hit;
    }
    return null;
  }

  // LEFT (−Z) and RIGHT (+Z)
  [-1, 1].forEach((side) => {
    const hit = trySideHit(side, xMain, place === "belly" || place === "wing" ? [yWindow] : yAlts);
    if (!hit) {
      console.warn("addTextDecals: no hit on side", side, place);
      return;
    }
    // Flip U on −Z so text still reads L→R from outside
    const flipU = side < 0;
    const mat = sideMaterialFromTex(tex, flipU, sharedMatOpts);
    const sizeVec =
      place === "belly"
        ? new THREE.Vector3(panelLen, panelH * 0.85, panelDepth)
        : decalSize.clone();
    projectDecal(group, hit, sizeVec, mat, 2);
  });

  // Belly-only: also try a centered under-fuselage ray if sides missed (extra)
  if (place === "belly" && group.children.length === 0) {
    const origin = new THREE.Vector3(xMain, center.y - reach, center.z);
    const hit = raycastBestHit(meshList, origin, new THREE.Vector3(0, 1, 0), raycaster);
    if (hit) {
      const mat = sideMaterialFromTex(tex, false, sharedMatOpts);
      projectDecal(
        group,
        hit,
        new THREE.Vector3(panelLen, panelH * 0.85, panelDepth),
        mat,
        2
      );
    }
  }

  // Secondary registration aft on both sides
  let regTex = null;
  if (st.text && state.registration && place !== "tail" && place !== "wing") {
    regTex = makeRegTexture(state);
    const regW = Math.min(size.x * 0.16, 1.5);
    const regH = Math.max(0.28, regW * 0.38);
    const regDepth = panelDepth * 0.9;
    const regSize = new THREE.Vector3(regW, regH, regDepth);
    const regX = center.x - size.x * 0.22;
    const regYAlts = yAlts.map((y) => y - size.y * 0.02);

    [-1, 1].forEach((side) => {
      const hit = trySideHit(side, regX, regYAlts);
      if (!hit) return;
      const flipU = side < 0;
      const mat = sideMaterialFromTex(regTex, flipU, sharedMatOpts);
      projectDecal(group, hit, regSize, mat, 3);
    });
  }

  return { tex, mat: null, group, regTex };
}

function removeNamedGroup(craft, name) {
  if (!craft) return;
  const old = craft.getObjectByName(name);
  if (!old) return;
  craft.remove(old);
  disposeObject(old);
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

  // Stickers (both UV halves)
  const st = state.stickers || {};
  if (st.stripe) {
    const sy = H * 0.58;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, sy, W, 10);
    ctx.fillStyle = tail;
    ctx.fillRect(0, sy + 10, W, 8);
  }
  if (st.checkered) {
    drawCheckered2d(ctx, 0, H * 0.04, W, 16, 24, "#111111", "#f5f5f5");
  }
  if (st.heart) {
    drawHeart2d(ctx, W * 0.18, H * 0.26, 26, "#dc2840");
    drawHeart2d(ctx, W * 0.68, H * 0.26, 26, "#dc2840");
  }
  if (st.star) {
    drawStar2d(ctx, W * 0.32, H * 0.26, 22, "#ffd24a");
    drawStar2d(ctx, W * 0.82, H * 0.26, 22, "#ffd24a");
  }
  if (st.lightning) {
    drawLightning2d(ctx, W * 0.12, H * 0.7, 26, "#ffe566");
    drawLightning2d(ctx, W * 0.62, H * 0.7, 26, "#ffe566");
  }
  if (st.bird) {
    drawBird2d(ctx, W * 0.25, H * 0.78, 32, textColor);
    drawBird2d(ctx, W * 0.75, H * 0.78, 32, textColor);
  }
  if (st.roundel) {
    drawRoundel2d(ctx, W * 0.1, H * 0.7, 24);
    drawRoundel2d(ctx, W * 0.6, H * 0.7, 24);
  }
  if (st.chevron) {
    drawChevron2d(ctx, W * 0.38, H * 0.7, 22, "#ffffff");
    drawChevron2d(ctx, W * 0.88, H * 0.7, 22, "#ffffff");
  }

  // Text / airline / registration — wide halves + auto-shrink + font/style
  if (st.text) {
    const sizeKey = state.textSize || "M";
    const basePx = sizeKey === "S" ? 30 : sizeKey === "L" ? 56 : 42;
    const place = state.textPlacement || "fuselage";
    // Each side gets ~42% of full width (was tighter); leave margin
    const maxW = W * 0.42;

    ctx.fillStyle = textColor;
    ctx.textBaseline = "middle";
    ctx.shadowColor = "rgba(0,0,0,0.45)";
    ctx.shadowBlur = 6;

    const drawSideText = (xCenter) => {
      ctx.textAlign = "center";
      let y = H * 0.3;
      if (place === "belly") y = H * 0.72;
      if (place === "tail") y = H * 0.26;
      if (place === "wing") y = H * 0.48;

      const airline = state.airline || "SkinMyBird";
      const airPx = fitFontPx(ctx, airline, maxW, basePx, state, 12);
      ctx.font = resolveFontFace(state, airPx);
      ctx.fillText(airline, xCenter, y);

      if (state.slogan) {
        const style = String(state.textStyle || "").toLowerCase();
        const sloganStyle = style.includes("italic")
          ? (style.includes("bold") ? "bold-italic" : "italic")
          : "regular";
        const sState = { ...state, textStyle: sloganStyle };
        const sPx = fitFontPx(ctx, state.slogan, maxW, Math.round(basePx * 0.5), sState, 10);
        ctx.font = resolveFontFace(sState, sPx);
        ctx.globalAlpha = 0.92;
        ctx.fillText(state.slogan, xCenter, y + airPx * 0.58);
        ctx.globalAlpha = 1;
      }

      const rState = { ...state, textStyle: "bold" };
      const regPx = fitFontPx(
        ctx,
        state.registration || "",
        maxW * 0.55,
        Math.round(basePx * 0.42),
        rState,
        10
      );
      ctx.font = resolveFontFace(rState, regPx);
      const regY = place === "tail" ? y + airPx * 0.75 : H * 0.52;
      const regX = place === "tail" ? xCenter : xCenter + W * 0.1;
      ctx.fillText(state.registration || "", regX, regY);
    };

    // Wider centers on each cylinder UV half
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
    narrow: { len: 11.2, rad: 0.52, wingSpan: 10.4, wingY: -0.18, engCount: 2, engScale: 1, rootChord: 2.05, tipChord: 0.85 },
    "narrow-short": { len: 9.6, rad: 0.5, wingSpan: 9.4, wingY: -0.16, engCount: 2, engScale: 0.92, rootChord: 1.9, tipChord: 0.8 },
    "narrow-long": { len: 13.0, rad: 0.52, wingSpan: 11.0, wingY: -0.18, engCount: 2, engScale: 1.05, rootChord: 2.15, tipChord: 0.88 },
    widebody: { len: 15.2, rad: 0.78, wingSpan: 14.2, wingY: -0.22, engCount: 2, engScale: 1.35, rootChord: 2.7, tipChord: 1.05 },
    "747": { len: 17.0, rad: 0.82, wingSpan: 16.0, wingY: -0.24, engCount: 4, engScale: 1.12, rootChord: 2.9, tipChord: 1.1 },
  };
  const s = specs[family] || specs.narrow;
  const half = s.len / 2;
  const R = s.rad;

  // Smooth civil-airliner fuselage (Lathe → rotate so axis is +X forward)
  const profile = [
    new THREE.Vector2(0.001, half),
    new THREE.Vector2(R * 0.22, half - s.len * 0.028),
    new THREE.Vector2(R * 0.55, half - s.len * 0.06),
    new THREE.Vector2(R * 0.88, half - s.len * 0.1),
    new THREE.Vector2(R * 0.98, half - s.len * 0.14),
    new THREE.Vector2(R, half - s.len * 0.18),
    new THREE.Vector2(R, -half + s.len * 0.2),
    new THREE.Vector2(R * 0.92, -half + s.len * 0.14),
    new THREE.Vector2(R * 0.62, -half + s.len * 0.08),
    new THREE.Vector2(R * 0.28, -half + s.len * 0.035),
    new THREE.Vector2(R * 0.08, -half + s.len * 0.01),
    new THREE.Vector2(0.001, -half),
  ];
  const fuselage = new THREE.Mesh(
    new THREE.LatheGeometry(profile, 48),
    mats.fuselage
  );
  fuselage.rotation.z = -Math.PI / 2; // Y-axis lathe → X-axis fuselage
  fuselage.name = "fuselage";
  fuselage.castShadow = true;
  fuselage.receiveShadow = true;
  group.add(fuselage);

  // Cockpit windscreen (slightly raised near nose)
  const glass = addCyl(
    group,
    R * 0.78,
    R * 0.92,
    s.len * 0.055,
    half - s.len * 0.12,
    R * 0.22,
    0,
    mats.glass,
    0,
    0,
    Math.PI / 2,
    20
  );
  glass.name = "cockpit";

  // 747 upper-deck hump (recognizable "hump" ahead of wing)
  if (family === "747") {
    const humpPts = [
      new THREE.Vector2(0.001, s.len * 0.16),
      new THREE.Vector2(R * 0.42, s.len * 0.14),
      new THREE.Vector2(R * 0.58, s.len * 0.08),
      new THREE.Vector2(R * 0.62, 0),
      new THREE.Vector2(R * 0.55, -s.len * 0.06),
      new THREE.Vector2(R * 0.28, -s.len * 0.12),
      new THREE.Vector2(0.001, -s.len * 0.14),
    ];
    const hump = new THREE.Mesh(new THREE.LatheGeometry(humpPts, 28), mats.fuselage);
    hump.rotation.z = -Math.PI / 2;
    hump.position.set(half * 0.22, R * 0.55, 0);
    hump.scale.set(1, 0.85, 1);
    hump.name = "hump";
    hump.castShadow = true;
    group.add(hump);
  }

  // Wings: thin airfoil-ish boxes, sweep-back ~25°, dihedral, root>tip chord, upward winglets
  const sweep = (25 * Math.PI) / 180;
  const dihedral = (6 * Math.PI) / 180;
  const semi = s.wingSpan / 2;
  const wingRootX = -s.len * 0.02; // slightly aft of mid
  const wingThick = Math.max(0.08, R * 0.18);

  [-1, 1].forEach((side) => {
    const wingG = new THREE.Group();
    wingG.name = "wing";
    // Root sits just outside fuselage
    wingG.position.set(wingRootX, s.wingY, side * R * 0.92);
    // Sweep: tip goes aft (-X); dihedral: tip goes up
    wingG.rotation.y = side > 0 ? -sweep : sweep;
    wingG.rotation.x = side > 0 ? -dihedral : dihedral;

    const segs = [
      { len: semi * 0.52, chord: s.rootChord * 0.92, z0: R * 0.05 },
      { len: semi * 0.48, chord: (s.rootChord + s.tipChord) / 2, z0: R * 0.05 + semi * 0.52 },
    ];
    // Panels built along +localZ for side=+1; multiply Z by `side` so the left
    // wing extends outward (-Z) instead of folding inward through the fuselage.
    const rootPanel = addBox(
      wingG,
      s.rootChord,
      wingThick,
      segs[0].len,
      -s.rootChord * 0.15,
      0,
      side * (segs[0].z0 + segs[0].len / 2),
      mats.wings
    );
    rootPanel.name = "wingRoot";
    const tipPanel = addBox(
      wingG,
      s.tipChord,
      wingThick * 0.85,
      segs[1].len,
      -s.rootChord * 0.15 - (s.rootChord - s.tipChord) * 0.35,
      0,
      side * (segs[1].z0 + segs[1].len / 2),
      mats.wings
    );
    tipPanel.name = "wingTip";

    // Winglet upward at tip
    const tipZ = side * (segs[1].z0 + segs[1].len);
    const winglet = addBox(
      wingG,
      s.tipChord * 0.45,
      0.85,
      0.07,
      -s.rootChord * 0.15 - (s.rootChord - s.tipChord) * 0.35,
      0.4,
      tipZ,
      mats.wings,
      0,
      0,
      side > 0 ? -0.2 : 0.2
    );
    winglet.name = "winglet";

    group.add(wingG);
  });

  // Under-wing engine pods with pylons
  const engR = 0.26 * s.engScale;
  const engLen = 1.45 * s.engScale;
  const engY = s.wingY - 0.62 * s.engScale;
  const engXs = -0.05;
  const positions =
    s.engCount === 4
      ? [
          [engXs, engY, semi * 0.32],
          [engXs - 0.15, engY, semi * 0.62],
          [engXs, engY, -semi * 0.32],
          [engXs - 0.15, engY, -semi * 0.62],
        ]
      : [
          [engXs, engY, semi * 0.38],
          [engXs, engY, -semi * 0.38],
        ];
  positions.forEach(([x, y, z]) => {
    const eng = addCyl(group, engR, engR * 0.88, engLen, x, y, z, mats.engines, 0, 0, Math.PI / 2, 24);
    eng.name = "engine";
    // Cylindrical nacelle intake lip
    addCyl(group, engR * 1.06, engR * 0.98, 0.14, x + engLen * 0.48, y, z, mats.enginesDark, 0, 0, Math.PI / 2, 20);
    // Exhaust taper
    addCyl(group, engR * 0.88, engR * 0.55, 0.28, x - engLen * 0.48, y, z, mats.enginesDark, 0, 0, Math.PI / 2, 16);
    // Pylon (wing → nacelle)
    addBox(group, 0.55, Math.abs(s.wingY - y) * 0.75, 0.1, x + 0.05, (s.wingY + y) / 2, z, mats.wings);
  });

  // Vertical fin (slight sweep) + horizontal stabilizers at tail
  const finH = family === "747" || family === "widebody" ? 2.9 : 2.25;
  const finRootX = -half + s.len * 0.12;
  const fin = addBox(
    group,
    1.55,
    finH,
    0.11,
    finRootX,
    finH * 0.42,
    0,
    mats.tail,
    0,
    0,
    -0.22
  );
  fin.name = "fin";
  // Cap / fairing hint
  addBox(group, 0.45, 0.18, 0.12, finRootX - 0.35, finH * 0.85, 0, mats.tail, 0, 0, -0.22);

  const stabSpan = family === "widebody" || family === "747" ? 5.4 : 3.9;
  addBox(
    group,
    1.15,
    0.07,
    stabSpan,
    -half + s.len * 0.08,
    R * 0.55,
    0,
    mats.tail,
    0,
    0,
    -0.12
  );

  // Simple grounded landing gear
  const gearY = -R - 0.15;
  // Nose gear
  addBox(group, 0.12, 0.75, 0.12, half * 0.42, gearY - 0.15, 0, mats.enginesDark);
  addCyl(group, 0.14, 0.14, 0.08, half * 0.42, gearY - 0.52, 0, mats.enginesDark, Math.PI / 2, 0, 0, 12);
  // Main gear left/right
  [-1, 1].forEach((side) => {
    addBox(group, 0.12, 0.9, 0.12, -0.35, gearY - 0.2, side * R * 1.15, mats.enginesDark);
    addCyl(group, 0.16, 0.16, 0.1, -0.35, gearY - 0.62, side * R * 1.15, mats.enginesDark, Math.PI / 2, 0, 0, 12);
  });

  return { fuselageMeshes: [fuselage] };
}

function buildHelicopter(group, mats) {
  // H135-ish: bubble cabin, slender boom, skids, main + tail rotors
  const cabin = new THREE.Group();
  cabin.name = "fuselage";

  // Bubble / rounded cabin (sphere scaled)
  const bubble = new THREE.Mesh(
    new THREE.SphereGeometry(1.05, 28, 20),
    mats.fuselage
  );
  bubble.scale.set(1.35, 0.95, 0.95);
  bubble.position.set(0.35, 0.35, 0);
  bubble.castShadow = true;
  cabin.add(bubble);

  // Lower cabin fairing
  addBox(cabin, 2.4, 0.7, 1.35, 0.15, -0.05, 0, mats.fuselage);

  // Nose / cockpit glass bubble
  const noseGlass = new THREE.Mesh(
    new THREE.SphereGeometry(0.72, 20, 16, 0, Math.PI * 2, 0, Math.PI * 0.55),
    mats.glass
  );
  noseGlass.rotation.z = -Math.PI / 2;
  noseGlass.position.set(1.45, 0.4, 0);
  noseGlass.scale.set(1.1, 1.05, 1.15);
  cabin.add(noseGlass);

  group.add(cabin);

  // Slender tail boom
  const boom = addCyl(group, 0.16, 0.1, 4.6, -2.85, 0.45, 0, mats.tail, 0, 0, Math.PI / 2, 14);
  boom.name = "boom";
  // Boom fairing at cabin junction
  addCyl(group, 0.28, 0.16, 0.7, -0.9, 0.4, 0, mats.fuselage, 0, 0, Math.PI / 2, 12);

  // Vertical / horizontal stabilizers at boom end
  addBox(group, 0.55, 1.15, 0.07, -5.0, 0.85, 0, mats.tail);
  addBox(group, 0.35, 0.06, 0.9, -4.85, 0.55, 0, mats.tail);

  // Skids
  const skidY = -0.95;
  [-1, 1].forEach((side) => {
    const z = side * 0.72;
    addBox(group, 3.0, 0.07, 0.09, 0.1, skidY, z, mats.engines);
    addBox(group, 0.07, 0.55, 0.07, 1.0, skidY + 0.28, z, mats.engines);
    addBox(group, 0.07, 0.55, 0.07, -0.85, skidY + 0.28, z, mats.engines);
  });

  // Main rotor mast + 4-blade disk
  const rotor = new THREE.Group();
  rotor.name = "mainRotor";
  rotor.position.set(0.05, 1.35, 0);
  group.add(rotor);
  addCyl(rotor, 0.1, 0.12, 0.45, 0, -0.1, 0, mats.wings);
  addCyl(rotor, 0.22, 0.22, 0.12, 0, 0.12, 0, mats.enginesDark);
  for (let i = 0; i < 4; i++) {
    const blade = addBox(rotor, 5.8, 0.035, 0.2, 0, 0.18, 0, mats.wings);
    blade.rotation.y = (i * Math.PI) / 2;
    blade.position.y = 0.18;
  }

  // Fenestron-ish / classic tail rotor
  const tailRotor = new THREE.Group();
  tailRotor.name = "tailRotor";
  tailRotor.position.set(-5.05, 0.7, 0.22);
  group.add(tailRotor);
  addCyl(tailRotor, 0.06, 0.06, 0.2, 0, 0, 0, mats.enginesDark, 0, 0, Math.PI / 2, 8);
  for (let i = 0; i < 4; i++) {
    const blade = addBox(tailRotor, 0.06, 0.85, 0.1, 0, 0, 0, mats.wings);
    blade.rotation.z = (i * Math.PI) / 4;
  }

  return { fuselageMeshes: [bubble], anim: { mainRotor: rotor, tailRotor } };
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
    this.glbUrl = null;
    this.modelMode = null; // "glb" | "procedural"
    this.decalTex = null;
    this.regTex = null;
    this.glbMaterials = []; // { mat, role }
    this._loadToken = 0;
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
    try {
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
    this.camera.position.set(9, 4, 7.5);

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
    } catch (err) {
      console.error("Preview3D.init failed", err);
      this.ok = false;
      try {
        if (this.renderer) {
          this.renderer.dispose();
          this.renderer = null;
        }
      } catch (_) { /* ignore */ }
      return false;
    }
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
    // Distance chosen so craft fills ~60% of the frame
    const dist =
      family === "balloon"
        ? 11
        : family === "747" || family === "widebody"
          ? 16
          : family === "helicopter"
            ? 10
            : 12.5;
    // Classic 3/4 front-side view, slightly above
    this.camera.position.set(dist * 0.72, dist * 0.32, dist * 0.58);
    this.controls.target.set(0, family === "balloon" ? 1.6 : 0.35, 0);
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
    if (this.decalTex) {
      this.decalTex.dispose();
      this.decalTex = null;
    }
    if (this.regTex) {
      this.regTex.dispose();
      this.regTex = null;
    }
    this.anim = null;
    this.mats = null;
    this.glbMaterials = [];
    this.modelMode = null;
    this.glbUrl = null;
  }

  buildProcedural(profile, state) {
    const family = resolveShapeFamily(profile);
    this.clearModel();
    this.family = family;
    this.profileId = profile ? profile.id : null;
    this.modelMode = "procedural";
    try { window.dispatchEvent(new CustomEvent("skinmybird-model-mode",{detail:{mode:"procedural"}})); } catch (e) {}

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
    else if (family === "helicopter") craft.position.y = 0.85;
    else craft.position.y = 0.55;

    this.root.add(craft);
    this.anim = (result && result.anim) || null;
    this.mats = mats;

    this.resetCamera();
    this._lastStateKey = "";
    this.applyPaint(state);
  }

  /**
   * Place a loaded GLTF scene into the hangar, tint + decals from state.
   */
  mountGlb(gltf, profile, state, url) {
    this.clearModel();
    this.family = resolveShapeFamily(profile);
    this.profileId = profile ? profile.id : null;
    this.glbUrl = url;
    this.modelMode = "glb";
    try { window.dispatchEvent(new CustomEvent("skinmybird-model-mode",{detail:{mode:"glb",url}})); } catch (e) {}
    try { window.__SMB_MODEL_MODE = "glb"; const el=document.getElementById("preview-sub"); if(el&&!el.dataset.keep){/* set by app */} } catch(e){}

    const craft = new THREE.Group();
    craft.name = "aircraft";

    const model = gltf.scene.clone(true);
    cloneMaterialsDeep(model);
    fitAircraftToHangar(model, GLB_TARGET_SPAN);
    craft.add(model);

    // Index materials by role for live recolor
    const craftBox = new THREE.Box3().setFromObject(craft);
    this.glbMaterials = [];
    model.traverse((child) => {
      if (!child.isMesh || !child.material) return;
      const mats = Array.isArray(child.material)
        ? child.material
        : [child.material];
      const meshBox = new THREE.Box3().setFromObject(child);
      const role = classifyMeshRole(child.name, meshBox, craftBox);
      mats.forEach((m) => {
        if (m.map) {
          // Keep albedo loosely; we'll tint via color
          m.color.set(0xffffff);
        }
        this.glbMaterials.push({ mat: m, role });
      });
    });

    // Single-material models: fuselage primary + text decal overlay
    const uniqueMats = new Set(this.glbMaterials.map((g) => g.mat));
    if (uniqueMats.size <= 1) {
      this.glbMaterials.forEach((g) => {
        g.role = "fuselage";
      });
    }

    // Sit slightly above hangar floor grid BEFORE decals so raycasts/world matches final pose
    craft.position.y = 0.02;
    this.root.add(craft);
    craft.updateMatrixWorld(true);

    const decal = addTextDecals(craft, state);
    this.decalTex = decal.tex;
    this.regTex = decal.regTex || null;
    this.anim = null;
    this.mats = null;

    this.resetCamera();
    this._lastStateKey = "";
    this.applyPaint(state);
  }

  async buildGlb(profile, state, url) {
    const token = ++this._loadToken;
    try {
      const gltf = await loadGlbCached(url);
      if (token !== this._loadToken) return; // stale
      if (!this.ok || !this.root) return;
      this.mountGlb(gltf, profile, state, url);
    } catch (err) {
      console.warn("GLB load failed, falling back to procedural:", url, err);
      if (token !== this._loadToken) return;
      this.buildProcedural(profile, state);
    }
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
      tf: state.textFont,
      tp: state.textPlacement,
      st: state.stickers,
      photo: state.soacraName || null,
      fam: family,
      mode: this.modelMode,
    });
    if (key === this._lastStateKey) return;
    this._lastStateKey = key;

    if (this.modelMode === "glb") {
      const colors = {
        fuselage: hexToThree(state.colors.fuselage || "#FF6A00"),
        wings: hexToThree(state.colors.wings || "#111111"),
        engines: hexToThree(state.colors.engines || "#222222"),
        tail: hexToThree(state.colors.tail || "#FF6A00"),
      };
      const unique = new Set(this.glbMaterials.map((g) => g.mat));
      if (unique.size <= 1) {
        // Single material: fuselage as primary tint
        this.glbMaterials.forEach(({ mat }) => {
          mat.color.copy(colors.fuselage);
          mat.needsUpdate = true;
        });
      } else {
        this.glbMaterials.forEach(({ mat, role }) => {
          mat.color.copy(colors[role] || colors.fuselage);
          mat.needsUpdate = true;
        });
      }
      // Rebuild mesh-projected decals (size/font/placement/text length)
      const craft = this.root.getObjectByName("aircraft");
      if (craft) {
        removeNamedGroup(craft, "textDecals");
        if (this.decalTex) {
          this.decalTex.dispose();
          this.decalTex = null;
        }
        if (this.regTex) {
          this.regTex.dispose();
          this.regTex = null;
        }
        const decal = addTextDecals(craft, state);
        this.decalTex = decal.tex;
        this.regTex = decal.regTex || null;
      }
      return;
    }

    // Procedural path
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
      this._loadToken++;
      this.clearModel();
      this.profileId = null;
      return;
    }
    const url = resolveGlbUrl(profile);
    const sameProfile = this.profileId === profile.id;
    const sameGlb = url && this.glbUrl === url && this.modelMode === "glb";

    if (sameProfile && (sameGlb || (!url && this.modelMode === "procedural"))) {
      this.applyPaint(state);
      return;
    }

    if (url) {
      this.buildGlb(profile, state, url);
    } else {
      this._loadToken++;
      this.buildProcedural(profile, state);
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
