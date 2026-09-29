/**
 * SkinMyBird 3D hangar preview v0.7.4 — single-mesh nacelle pods + constant-height windowband, reliable custom textures.
 * ES module; Three.js via local vendor importmap (no CDN).
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DecalGeometry } from "three/addons/geometries/DecalGeometry.js";

const TEX_W = 2048;
const TEX_H = 1024;
const REG_W = 2048;
const REG_H = 640;
const DECAL_W = 4096;
const DECAL_H = 768;

/** Max anisotropy from the live renderer (set in Preview3D.init). */
let _maxAnisotropy = 8;

/** HQ sampling for canvas / paint textures (mipmaps + aniso). */
function configurePaintTexture(tex) {
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.generateMipmaps = true;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.anisotropy = Math.min(16, _maxAnisotropy || 8);
  tex.needsUpdate = true;
  return tex;
}

function prepareCanvas2d(ctx, w, h) {
  if (!ctx) return;
  ctx.imageSmoothingEnabled = true;
  try { ctx.imageSmoothingQuality = "high"; } catch (_) {}
  // Crisp glyph edges at high zoom (when supported)
  try { ctx.textRendering = "geometricPrecision"; } catch (_) {}
  ctx.clearRect(0, 0, w, h);
}

/** True for vivid airline-brand blues/reds (e.g. Korean Air on FetchCFD 747). */
function isBrandLiveryMaterial(mat) {
  if (!mat) return false;
  const n = String(mat.name || "").toLowerCase();
  if (/dodgerblue|0098|korean|airline|logo|__80_|__82_|material_7|material_9/.test(n))
    return true;
  if (!mat.color) return false;
  const { r, g, b } = mat.color;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const sat = max > 1e-6 ? (max - min) / max : 0;
  if (sat < 0.35) return false;
  // vivid blue / cyan brand panels
  if (b > 0.4 && b >= r && b >= g && r < 0.55) return true;
  // vivid red brand accents
  if (r > 0.65 && g < 0.35 && b < 0.4) return true;
  return false;
}

function stripAndNeutralizeMaterial(m) {
  if (!m) return;
  if (m.map) {
    try { m.map.dispose(); } catch (_) {}
    m.map = null;
  }
  if (m.emissiveMap) {
    try { m.emissiveMap.dispose(); } catch (_) {}
    m.emissiveMap = null;
  }
  if (m.envMap) m.envMap = null;
  if (m.color) m.color.set(0xffffff);
  if (m.emissive) m.emissive.set(0x000000);
  // Solid paint, not chrome — face-zone materials own color (no vertexColors)
  if ("metalness" in m) m.metalness = Math.min(m.metalness ?? 0.12, 0.12);
  if ("roughness" in m) m.roughness = Math.max(m.roughness ?? 0.7, 0.7);
  m.vertexColors = false;
  m.needsUpdate = true;
}

/**
 * Neutralize any residual baked livery on GLBs (amvlab are nologo; keep as safety net).
 * Hide embossed titles/logos, clear baked albedo maps, reset materials to zone colors.
 * Keeps Two-Tone paint able to override plain gray materials (e.g. God's Eye View 747).
 */
function prepareGlbForSkinning(model) {
  model.updateMatrixWorld(true);
  model.traverse((child) => {
    if (!child.isMesh || !child.material) return;
    const mats = Array.isArray(child.material) ? child.material : [child.material];
    const name = String(child.name || "");

    let vertCount = 0;
    try {
      const pos = child.geometry && child.geometry.getAttribute("position");
      if (pos) vertCount = pos.count;
    } catch (_) {}

    const brandMats = mats.filter(isBrandLiveryMaterial);
    // Mesh12* = raised "KOREAN AIR" / taegeuk. Other small/medium brand
    // meshes are embossed logos (e.g. stylized K) — hide so lighting cannot
    // silhouette them after recolor. Large brand panels (blue cheatline) stay
    // and are neutralized to zone colors below.
    const allBrand = brandMats.length > 0 && brandMats.length === mats.length;
    const anyBrand = brandMats.length > 0;
    if (
      /^Mesh12/i.test(name) ||
      (allBrand && vertCount > 0 && vertCount < 4000) ||
      (anyBrand && vertCount > 0 && vertCount < 400)
    ) {
      child.visible = false;
      child.userData.skinHiddenLivery = true;
      return;
    }

    mats.forEach(stripAndNeutralizeMaterial);
  });
}


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
  const seenMats = new Set();
  obj.traverse((child) => {
    if (child.geometry) {
      try { child.geometry.dispose(); } catch (_) {}
    }
    if (child.material) {
      const mats = Array.isArray(child.material)
        ? child.material
        : [child.material];
      mats.forEach((m) => {
        if (!m || seenMats.has(m)) return;
        seenMats.add(m);
        if (m.map) {
          try { m.map.dispose(); } catch (_) {}
        }
        try { m.dispose(); } catch (_) {}
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
    blob.includes("cessna") ||
    blob.includes("c172") ||
    sil === "ga" ||
    blob.includes("general aviation")
  )
    return "ga";
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
  const meta = resolveGlbMeta(profile);
  return meta ? meta.url : null;
}

/**
 * Resolve GLB URL + whether the mesh is a licensed stand-in (not exact type).
 * 747 → b747.glb (God's Eye View CC BY 4.0); A330 borrows A350; Cessna uses c172 GLB.
 */
export function resolveGlbMeta(profile) {
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

  if (
    blob.includes("cessna") ||
    blob.includes("c172") ||
    sil === "ga" ||
    blob.includes("general aviation")
  ) {
    return {
      url: "/models/cessna.glb",
      standIn: true,
      note: "Cessna 172 preview (CC BY 4.0; not an MSFS UV map)",
    };
  }

  // v0.5.5: clean CC-BY 747 from God's Eye View (plain gray; Two-Tone overrides via prepareGlbForSkinning)
  if (blob.includes("747")) {
    return {
      url: "/models/b747.glb",
      standIn: false,
      note: "Boeing 747 preview — God's Eye View airplane.glb (CC BY 4.0, zairiq-123)",
    };
  }

  if (blob.includes("787") || blob.includes("dreamliner"))
    return { url: "/models/b787.glb", standIn: false };

  if (blob.includes("737") || blob.includes("736") || blob.includes("pmdg"))
    return { url: "/models/b737.glb", standIn: false };

  // A330 / generic wide → A350 GLB (stand-in); exact A350 is not stand-in
  if (blob.includes("a330") || blob.includes("widebody") || blob.includes("wide-body")) {
    return {
      url: "/models/a350.glb",
      standIn: true,
      note: "Widebody preview stand-in (A350 GLB)",
    };
  }
  if (blob.includes("a350"))
    return { url: "/models/a350.glb", standIn: false };

  // A320 / A319 / A321 / FBW / LatinVFR Airbus + default airliner
  return { url: "/models/a320.glb", standIn: false };
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

/** Own BufferGeometry per hangar instance so face-zone splits never mutate the GLB cache. */
function cloneGeometriesDeep(root) {
  root.traverse((child) => {
    if (!child.isMesh || !child.geometry) return;
    child.geometry = child.geometry.clone();
  });
}

function classifyMeshRole(name, box, craftBox) {
  const n = String(name || "").toLowerCase();
  if (/engine|nacelle|motor|fan|pylon/.test(n)) return "engines"; // pylons → engines
  if (/winglet|sharklet/.test(n)) return "winglet";
  if (/wing|aileron|flap|slat/.test(n)) return "wings";
  if (/stabil|elevator|htail|h-?stab|horiz/.test(n)) return "tail";
  if (/tail|fin|rudder|vtail|v-?stab/.test(n)) return "tail";
  if (/door|exit|hatch|outline/.test(n)) return "fuselage";
  if (/window|cabin.?band|cheat|windowband/.test(n)) return "windowband";
  if (/nose|cockpit|radome/.test(n)) return "nose";
  if (/belly|underside|keel/.test(n)) return "belly";
  if (/fusel|body|hull|cabin/.test(n)) return "fuselage";
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
  // Nose: forward tip region
  if (mCenter.x > cCenter.x + cSize.x * 0.28 && mSize.x < cSize.x * 0.35)
    return "nose";
  // Tail: aft (low X if nose=+X)
  if (mCenter.x < cCenter.x - cSize.x * 0.25) return "tail";
  return "fuselage";
}

/** Paint-zone ids — v0.7.4 fragment-shader body bands + solid role mats for wings/engines. */
const ZONE_ID = {
  fuselage: 0,
  nose: 1,
  belly: 2,
  wings: 3,
  winglet: 4,
  engines: 5,
  tail: 6,
  windowband: 7,
};
const ZONE_NAMES = [
  "fuselage",
  "nose",
  "belly",
  "wings",
  "winglet",
  "engines",
  "tail",
  "windowband",
];

/**
 * After hangar fit: +X longest (fuselage), +Y up, +Z span.
 * High-Y verts mark the vertical fin → aft; noseSign flips so nose is +X.
 */
function detectGlbNoseSign(samples) {
  if (!samples.length) return 1;
  const ys = samples.map((s) => s[1]).sort((a, b) => a - b);
  const yThresh = ys[Math.floor(ys.length * 0.92)] ?? 0;
  const high = samples.filter((s) => s[1] >= yThresh);
  if (!high.length) return 1;
  const avgX = high.reduce((a, s) => a + s[0], 0) / high.length;
  return avgX < 0 ? 1 : -1;
}

/**
 * Build craft-local zone context: wing plane, nacelle seeds from low-Y outboard verts.
 */
function buildGlbZoneContext(samples, craftBox, noseSign) {
  const min = craftBox.min;
  const max = craftBox.max;
  const sx = Math.max(max.x - min.x, 1e-6);
  const sy = Math.max(max.y - min.y, 1e-6);
  const sz = Math.max(max.z - min.z, 1e-6);
  const halfZ = sz * 0.5;

  const wingish = samples
    .filter((s) => Math.abs(s[2]) > halfZ * 0.35)
    .map((s) => s[1])
    .sort((a, b) => a - b);
  const wingY = wingish.length
    ? wingish[Math.floor(wingish.length * 0.5)]
    : min.y + sy * 0.35;

  // Fuselage tube half-width (airliner body ≈ 20–24% of half-span)
  const fuseHalf = halfZ * 0.22;

  // Nacelle seeds: under-wing outboard verts (raise cut so pods aren't only bottom 22%)
  const yCut = Math.min(wingY - sy * 0.015, min.y + sy * 0.40);
  const seeds = [];
  const avg3 = (arr) => [
    arr.reduce((a, s) => a + s[0], 0) / arr.length,
    arr.reduce((a, s) => a + s[1], 0) / arr.length,
    arr.reduce((a, s) => a + s[2], 0) / arr.length,
  ];
  for (const side of [-1, 1]) {
    let cand = samples.filter(
      (s) =>
        s[1] <= yCut &&
        s[1] > min.y + sy * 0.01 &&
        s[2] * side > 0 &&
        Math.abs(s[2]) >= fuseHalf * 1.15 &&
        Math.abs(s[2]) <= halfZ * 0.58
    );
    if (cand.length < 6) {
      // Fallback: slightly looser lateral band
      cand = samples.filter(
        (s) =>
          s[1] <= yCut &&
          s[2] * side > 0 &&
          Math.abs(s[2]) >= halfZ * 0.16 &&
          Math.abs(s[2]) <= halfZ * 0.55
      );
    }
    if (cand.length < 6) continue;
    cand = cand.slice().sort((a, b) => a[1] - b[1]);
    cand = cand.slice(0, Math.max(6, Math.ceil(cand.length * 0.6)));
    const zs = cand.map((s) => Math.abs(s[2])).sort((a, b) => a - b);
    const zMin = zs[0];
    const zMax = zs[zs.length - 1];
    if (zMax - zMin > halfZ * 0.14) {
      const mid = (zMin + zMax) * 0.5;
      for (const part of [
        cand.filter((s) => Math.abs(s[2]) < mid),
        cand.filter((s) => Math.abs(s[2]) >= mid),
      ]) {
        if (part.length >= 4) seeds.push(avg3(part));
      }
    } else {
      seeds.push(avg3(cand));
    }
  }

  // Large enough to cover single-mesh nacelle shells (not just seed cores)
  const engineR = Math.max(sy * 0.22, halfZ * 0.12, fuseHalf * 1.1);

  // Fuselage tube top (exclude vertical fin): high-|Z| and extreme aft-high verts skew sy
  // so crown v-thresholds never fire. Use ~95th %ile Y of near-centerline samples.
  const tubeYs = samples
    .filter((s) => Math.abs(s[2]) < halfZ * 0.28)
    .map((s) => s[1])
    .sort((a, b) => a - b);
  let fuseTop = max.y;
  if (tubeYs.length >= 8) {
    fuseTop = tubeYs[Math.min(tubeYs.length - 1, Math.floor(tubeYs.length * 0.95))];
  }
  // Keep a little headroom but never above craft max
  fuseTop = Math.min(Math.max(fuseTop, min.y + sy * 0.35), max.y);
  const fuseSy = Math.max(fuseTop - min.y, sy * 0.35, 1e-6);

  return { min, max, sx, sy, sz, halfZ, fuseHalf, wingY, noseSign, seeds, engineR, fuseTop, fuseSy };
}

function classifyPoint(x, y, z, ctx) {
  const xx = x * ctx.noseSign;
  const xmin = ctx.noseSign === 1 ? ctx.min.x : -ctx.max.x;
  const u = (xx - xmin) / ctx.sx; // 0 = aft, 1 = nose
  const v = (y - ctx.min.y) / ctx.sy;
  const w = Math.abs(z) / Math.max(ctx.halfZ, 1e-6);
  const absZ = Math.abs(z);
  const { sy, halfZ, wingY, seeds, engineR, min } = ctx;
  const fuseHalf = ctx.fuseHalf != null ? ctx.fuseHalf : halfZ * 0.22;
  const fuseSy = ctx.fuseSy || sy;
  const vTube = (y - min.y) / fuseSy;
  const fuseTop = ctx.fuseTop || ctx.max.y;
  const span = Math.max(fuseTop - wingY, 1e-6);

  // --- engines (single-mesh critical): under-wing pod → seeds → pylons ---
  if (
    absZ > fuseHalf * 1.2 &&
    y < wingY - sy * 0.02 &&
    y > min.y + sy * 0.02 &&
    u > 0.32 &&
    u < 0.78
  ) {
    return ZONE_ID.engines;
  }
  for (let i = 0; i < seeds.length; i++) {
    const s = seeds[i];
    const dx = x - s[0];
    const dy = y - s[1];
    const dz = z - s[2];
    if (dx * dx + dy * dy + dz * dz < engineR * engineR) return ZONE_ID.engines;
  }
  for (let i = 0; i < seeds.length; i++) {
    const s = seeds[i];
    const dx = x - s[0];
    const dy = y - s[1];
    const dz = z - s[2];
    const horiz = Math.sqrt(dx * dx + dz * dz);
    if (
      horiz < engineR * 0.95 &&
      dy > 0 &&
      dy < engineR * 1.7 &&
      y < wingY + sy * 0.08
    ) {
      return ZONE_ID.engines; // pylons → engines
    }
  }
  // Geometric pylon: outboard of tube, under/at wing plane, wing station
  if (
    absZ > fuseHalf * 1.15 &&
    absZ < halfZ * 0.52 &&
    y < wingY + sy * 0.05 &&
    y > wingY - sy * 0.30 &&
    u > 0.32 &&
    u < 0.78
  ) {
    return ZONE_ID.engines;
  }

  // --- wings / winglet ---
  if (w > 0.9 && v > 0.18 && v < 0.85 && u > 0.2 && u < 0.9) return ZONE_ID.winglet;
  if (w > 0.30 && absZ > halfZ * 0.20 && u > 0.28 && u < 0.82) {
    const nearWingPlane = Math.abs(y - wingY) < sy * 0.15;
    if (nearWingPlane && v > 0.08 && v < 0.58) return ZONE_ID.wings;
    if (w > 0.44 && v > 0.1 && v < 0.52) return ZONE_ID.wings;
  }

  // --- tail ---
  if (u < 0.22 && v > 0.45 && w < 0.40) return ZONE_ID.tail;
  if (u < 0.24 && v > 0.22 && v < 0.55 && w > 0.18 && w < 0.75)
    return ZONE_ID.tail;

  // --- nose tip / cockpit (do not bite mid-side windowband Y) ---
  if (u > 0.92 && w < 0.32) return ZONE_ID.nose;
  if (u > 0.82 && u < 0.95 && y > wingY + span * 0.52 && absZ <= fuseHalf * 1.15)
    return ZONE_ID.nose;

  // --- windowband: constant-height side stripe (airline cheatline) ---
  const bandLo = wingY + span * 0.30;
  const bandHi = wingY + span * 0.52;
  if (
    absZ <= fuseHalf * 1.15 &&
    absZ >= fuseHalf * 0.25 &&
    y >= bandLo &&
    y <= bandHi &&
    y > min.y + sy * 0.18 &&
    u > 0.12 &&
    u < 0.92
  ) {
    return ZONE_ID.windowband;
  }

  // --- belly ---
  if (absZ <= fuseHalf * 1.2 && (vTube < 0.20 || y < wingY - sy * 0.04)) {
    return ZONE_ID.belly;
  }

  if (u > 0.88 && absZ <= fuseHalf * 1.15) return ZONE_ID.nose;

  // Always paintable — never leave raw GLB gray
  return ZONE_ID.fuselage;
}

/** Majority-vote zone priority (tie-break when triangle verts disagree). */
const ZONE_MAJORITY_PRI = {
  [ZONE_ID.windowband]: 0,
  [ZONE_ID.fuselage]: 1,
  [ZONE_ID.belly]: 2,
  [ZONE_ID.nose]: 3,
  [ZONE_ID.wings]: 4,
  [ZONE_ID.winglet]: 5,
  [ZONE_ID.engines]: 6,
  [ZONE_ID.tail]: 7,
};

function majorityZoneId(z0, z1, z2) {
  if (z0 === z1 || z0 === z2) return z0;
  if (z1 === z2) return z1;
  // all different — prefer cleaner body bands
  let best = z0;
  let bestPri = ZONE_MAJORITY_PRI[z0] != null ? ZONE_MAJORITY_PRI[z0] : 99;
  for (const z of [z1, z2]) {
    const p = ZONE_MAJORITY_PRI[z] != null ? ZONE_MAJORITY_PRI[z] : 99;
    if (p < bestPri) {
      bestPri = p;
      best = z;
    }
  }
  return best;
}

/**
 * One-pass mid-edge subdivision for triangles with a long edge.
 * Smooths zone boundaries on coarse fuselage-like GLB meshes without new deps.
 */
function subdivideGeometryLongEdges(geometry, maxEdge) {
  const pos = geometry.getAttribute("position");
  if (!pos || !pos.count) return geometry;
  const norm = geometry.getAttribute("normal");
  const uv = geometry.getAttribute("uv");
  const index = geometry.getIndex();
  const triCount = index ? Math.floor(index.count / 3) : Math.floor(pos.count / 3);
  if (triCount <= 0) return geometry;

  const maxE2 = maxEdge * maxEdge;
  const outPos = [];
  const outNrm = [];
  const outUv = [];
  const hasN = !!(norm && norm.count === pos.count);
  const hasUv = !!(uv && uv.count === pos.count);

  const getI = (t, k) => {
    if (index) return index.getX(t * 3 + k);
    return t * 3 + k;
  };
  const pushV = (vi) => {
    outPos.push(pos.getX(vi), pos.getY(vi), pos.getZ(vi));
    if (hasN) outNrm.push(norm.getX(vi), norm.getY(vi), norm.getZ(vi));
    if (hasUv) outUv.push(uv.getX(vi), uv.getY(vi));
  };
  const midKey = (a, b) => (a < b ? a + "_" + b : b + "_" + a);
  const midCache = Object.create(null);
  const pushMid = (ia, ib) => {
    const key = midKey(ia, ib);
    if (midCache[key] != null) {
      const mi = midCache[key];
      outPos.push(outPos[mi * 3], outPos[mi * 3 + 1], outPos[mi * 3 + 2]);
      if (hasN) outNrm.push(outNrm[mi * 3], outNrm[mi * 3 + 1], outNrm[mi * 3 + 2]);
      if (hasUv) outUv.push(outUv[mi * 2], outUv[mi * 2 + 1]);
      return;
    }
    const mx = (pos.getX(ia) + pos.getX(ib)) * 0.5;
    const my = (pos.getY(ia) + pos.getY(ib)) * 0.5;
    const mz = (pos.getZ(ia) + pos.getZ(ib)) * 0.5;
    const mi = outPos.length / 3;
    outPos.push(mx, my, mz);
    if (hasN) {
      let nx = norm.getX(ia) + norm.getX(ib);
      let ny = norm.getY(ia) + norm.getY(ib);
      let nz = norm.getZ(ia) + norm.getZ(ib);
      const nl = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
      outNrm.push(nx / nl, ny / nl, nz / nl);
    }
    if (hasUv) {
      outUv.push((uv.getX(ia) + uv.getX(ib)) * 0.5, (uv.getY(ia) + uv.getY(ib)) * 0.5);
    }
    midCache[key] = mi;
  };

  let splitAny = false;
  for (let t = 0; t < triCount; t++) {
    const i0 = getI(t, 0);
    const i1 = getI(t, 1);
    const i2 = getI(t, 2);
    if (i0 >= pos.count || i1 >= pos.count || i2 >= pos.count) continue;
    const d01 =
      (pos.getX(i0) - pos.getX(i1)) ** 2 +
      (pos.getY(i0) - pos.getY(i1)) ** 2 +
      (pos.getZ(i0) - pos.getZ(i1)) ** 2;
    const d12 =
      (pos.getX(i1) - pos.getX(i2)) ** 2 +
      (pos.getY(i1) - pos.getY(i2)) ** 2 +
      (pos.getZ(i1) - pos.getZ(i2)) ** 2;
    const d20 =
      (pos.getX(i2) - pos.getX(i0)) ** 2 +
      (pos.getY(i2) - pos.getY(i0)) ** 2 +
      (pos.getZ(i2) - pos.getZ(i0)) ** 2;
    if (d01 <= maxE2 && d12 <= maxE2 && d20 <= maxE2) {
      pushV(i0);
      pushV(i1);
      pushV(i2);
      continue;
    }
    splitAny = true;
    // 4-way midpoint split
    const base = outPos.length / 3;
    pushV(i0);
    pushV(i1);
    pushV(i2);
    // mids appended after the 3 corners — recompute locally without cache for simplicity
    // Use dedicated mid verts into temp then emit 4 tris
    // Actually rebuild this triangle cleanly:
    outPos.length = base * 3;
    if (hasN) outNrm.length = base * 3;
    if (hasUv) outUv.length = base * 2;

    const emitCorner = (vi) => pushV(vi);
    const emitMidAB = (ia, ib) => {
      outPos.push(
        (pos.getX(ia) + pos.getX(ib)) * 0.5,
        (pos.getY(ia) + pos.getY(ib)) * 0.5,
        (pos.getZ(ia) + pos.getZ(ib)) * 0.5
      );
      if (hasN) {
        let nx = norm.getX(ia) + norm.getX(ib);
        let ny = norm.getY(ia) + norm.getY(ib);
        let nz = norm.getZ(ia) + norm.getZ(ib);
        const nl = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
        outNrm.push(nx / nl, ny / nl, nz / nl);
      }
      if (hasUv) {
        outUv.push(
          (uv.getX(ia) + uv.getX(ib)) * 0.5,
          (uv.getY(ia) + uv.getY(ib)) * 0.5
        );
      }
    };
    // corners 0,1,2 then mids 01,12,20 → indices base..base+5
    emitCorner(i0);
    emitCorner(i1);
    emitCorner(i2);
    emitMidAB(i0, i1);
    emitMidAB(i1, i2);
    emitMidAB(i2, i0);
    const c0 = base, c1 = base + 1, c2 = base + 2;
    const m01 = base + 3, m12 = base + 4, m20 = base + 5;
    // We already pushed verts; now we need indexed tris — easier to duplicate verts per tri
    // Rewind and emit 4 separate triangles as non-indexed verts
    outPos.length = base * 3;
    if (hasN) outNrm.length = base * 3;
    if (hasUv) outUv.length = base * 2;
    const V = [
      [pos.getX(i0), pos.getY(i0), pos.getZ(i0)],
      [pos.getX(i1), pos.getY(i1), pos.getZ(i1)],
      [pos.getX(i2), pos.getY(i2), pos.getZ(i2)],
    ];
    const N = hasN
      ? [
          [norm.getX(i0), norm.getY(i0), norm.getZ(i0)],
          [norm.getX(i1), norm.getY(i1), norm.getZ(i1)],
          [norm.getX(i2), norm.getY(i2), norm.getZ(i2)],
        ]
      : null;
    const U = hasUv
      ? [
          [uv.getX(i0), uv.getY(i0)],
          [uv.getX(i1), uv.getY(i1)],
          [uv.getX(i2), uv.getY(i2)],
        ]
      : null;
    const mid = (a, b) => [(a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5];
    const midN = (a, b) => {
      let nx = a[0] + b[0], ny = a[1] + b[1], nz = a[2] + b[2];
      const nl = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
      return [nx / nl, ny / nl, nz / nl];
    };
    const midU = (a, b) => [(a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5];
    const m01v = mid(V[0], V[1]);
    const m12v = mid(V[1], V[2]);
    const m20v = mid(V[2], V[0]);
    const m01n = N ? midN(N[0], N[1]) : null;
    const m12n = N ? midN(N[1], N[2]) : null;
    const m20n = N ? midN(N[2], N[0]) : null;
    const m01u = U ? midU(U[0], U[1]) : null;
    const m12u = U ? midU(U[1], U[2]) : null;
    const m20u = U ? midU(U[2], U[0]) : null;
    const emit = (pv, nv, uvv) => {
      outPos.push(pv[0], pv[1], pv[2]);
      if (hasN) outNrm.push(nv[0], nv[1], nv[2]);
      if (hasUv) outUv.push(uvv[0], uvv[1]);
    };
    const tris = [
      [V[0], m01v, m20v, N && N[0], m01n, m20n, U && U[0], m01u, m20u],
      [V[1], m12v, m01v, N && N[1], m12n, m01n, U && U[1], m12u, m01u],
      [V[2], m20v, m12v, N && N[2], m20n, m12n, U && U[2], m20u, m12u],
      [m01v, m12v, m20v, m01n, m12n, m20n, m01u, m12u, m20u],
    ];
    for (const tr of tris) {
      emit(tr[0], tr[3], tr[6]);
      emit(tr[1], tr[4], tr[7]);
      emit(tr[2], tr[5], tr[8]);
    }
  }

  if (!splitAny) return geometry;

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(outPos, 3));
  if (hasN && outNrm.length === outPos.length) {
    geo.setAttribute("normal", new THREE.Float32BufferAttribute(outNrm, 3));
  } else {
    geo.computeVertexNormals();
  }
  if (hasUv && outUv.length === (outPos.length / 3) * 2) {
    geo.setAttribute("uv", new THREE.Float32BufferAttribute(outUv, 2));
  }
  geo.computeBoundingBox();
  geo.computeBoundingSphere();
  return geo;
}

/** @deprecated alias — face path uses classifyPoint */
function classifyVertexZone(x, y, z, ctx) {
  return classifyPoint(x, y, z, ctx);
}

function makeGlbZoneMaterial(hexColor) {
  return new THREE.MeshStandardMaterial({
    color: hexColor ? hexToThree(hexColor) : new THREE.Color(0xffffff),
    metalness: 0.1,
    roughness: 0.72,
    vertexColors: false,
    flatShading: false,
    envMap: null,
    map: null,
    emissive: new THREE.Color(0x000000),
    emissiveIntensity: 0,
  });
}

/**
 * v0.7.4 — Hybrid zone paint:
 * Body meshes (fuselage/nose/belly/tail/windowband roles) share ONE MeshStandardMaterial
 * with onBeforeCompile fragment classification → smooth parametric stripes (no tri stairs).
 * Wings / winglets / engines get solid MeshStandardMaterial by mesh role (no mixed faces).
 * Face-split geometry is bypassed for body appearance.
 */
function craftLocalPoint(craft, worldPoint, out = new THREE.Vector3()) {
  out.copy(worldPoint);
  craft.updateMatrixWorld(true);
  const inv = craft.userData._craftInv || new THREE.Matrix4();
  inv.copy(craft.matrixWorld).invert();
  craft.userData._craftInv = inv;
  return out.applyMatrix4(inv);
}

function zoneNameFromId(zid) {
  return ZONE_NAMES[zid] || "fuselage";
}

function makeBodyZoneShaderMaterial(ctx) {
  const mat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(0xffffff),
    metalness: 0.1,
    roughness: 0.72,
    vertexColors: false,
    flatShading: false,
    envMap: null,
    map: null,
    emissive: new THREE.Color(0x000000),
    emissiveIntensity: 0,
  });

  const seedVecs = [0, 1, 2, 3].map((i) => {
    const s = ctx.seeds[i];
    return s
      ? new THREE.Vector3(s[0], s[1], s[2])
      : new THREE.Vector3(0, -9999, 0);
  });

  const uniforms = {
    uCraftWorldInverse: { value: new THREE.Matrix4() },
    uMin: { value: ctx.min.clone() },
    uMax: { value: ctx.max.clone() },
    uSx: { value: ctx.sx },
    uSy: { value: ctx.sy },
    uHalfZ: { value: ctx.halfZ },
    uWingY: { value: ctx.wingY },
    uNoseSign: { value: ctx.noseSign },
    uEngineR: { value: ctx.engineR },
    uFuseTop: { value: ctx.fuseTop },
    uFuseSy: { value: ctx.fuseSy },
    uSeedCount: { value: Math.min(4, ctx.seeds.length) },
    uSeed0: { value: seedVecs[0] },
    uSeed1: { value: seedVecs[1] },
    uSeed2: { value: seedVecs[2] },
    uSeed3: { value: seedVecs[3] },
    uColFuselage: { value: new THREE.Color(0xf2f4f7) },
    uColNose: { value: new THREE.Color(0xf2f4f7) },
    uColBelly: { value: new THREE.Color(0xb0b6be) },
    uColWindowband: { value: new THREE.Color(0x2ec4b6) },
    uColTail: { value: new THREE.Color(0xf2f4f7) },
    uColWings: { value: new THREE.Color(0x1b2430) },
    uColWinglet: { value: new THREE.Color(0x1b2430) },
    uColEngines: { value: new THREE.Color(0x1b2430) },
    uHighlightZone: { value: -1 },
  };

  mat.userData.zoneUniforms = uniforms;
  mat.userData.isBodyZoneShader = true;
  mat.userData.baseColor = new THREE.Color(0xffffff);
  mat.customProgramCacheKey = () => "smb_body_zone_shader_v074";

  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    mat.userData.shaderRef = shader;

    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
varying vec3 vCraftPos;
uniform mat4 uCraftWorldInverse;`
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
vCraftPos = (uCraftWorldInverse * modelMatrix * vec4( transformed, 1.0 )).xyz;`
      );

    const fragInject = `
varying vec3 vCraftPos;
uniform vec3 uMin;
uniform vec3 uMax;
uniform float uSx;
uniform float uSy;
uniform float uHalfZ;
uniform float uWingY;
uniform float uNoseSign;
uniform float uEngineR;
uniform float uFuseTop;
uniform float uFuseSy;
uniform int uSeedCount;
uniform vec3 uSeed0;
uniform vec3 uSeed1;
uniform vec3 uSeed2;
uniform vec3 uSeed3;
uniform vec3 uColFuselage;
uniform vec3 uColNose;
uniform vec3 uColBelly;
uniform vec3 uColWindowband;
uniform vec3 uColTail;
uniform vec3 uColWings;
uniform vec3 uColWinglet;
uniform vec3 uColEngines;
uniform int uHighlightZone;

int smbClassifyCraft(vec3 p) {
  float xx = p.x * uNoseSign;
  float xmin = uNoseSign > 0.0 ? uMin.x : -uMax.x;
  float u = (xx - xmin) / max(uSx, 1e-6);
  float v = (p.y - uMin.y) / max(uSy, 1e-6);
  float w = abs(p.z) / max(uHalfZ, 1e-6);
  float absZ = abs(p.z);
  float sy = uSy;
  float halfZ = uHalfZ;
  float wingY = uWingY;
  float engineR = uEngineR;
  float fuseHalf = halfZ * 0.22;
  float fuseSy = max(uFuseSy, 1e-6);
  float vTube = (p.y - uMin.y) / fuseSy;
  float fuseTop = uFuseTop;
  float span = max(fuseTop - wingY, 1e-6);

  // engines: under-wing pod → seeds → pylons
  if (absZ > fuseHalf * 1.2 && p.y < wingY - sy * 0.02 && p.y > uMin.y + sy * 0.02 && u > 0.32 && u < 0.78) {
    return 5;
  }
  vec3 seeds[4];
  seeds[0] = uSeed0; seeds[1] = uSeed1; seeds[2] = uSeed2; seeds[3] = uSeed3;
  for (int i = 0; i < 4; i++) {
    if (i >= uSeedCount) break;
    vec3 s = seeds[i];
    vec3 d = p - s;
    if (dot(d, d) < engineR * engineR) return 5;
  }
  for (int i = 0; i < 4; i++) {
    if (i >= uSeedCount) break;
    vec3 s = seeds[i];
    float dx = p.x - s.x;
    float dy = p.y - s.y;
    float dz = p.z - s.z;
    float horiz = sqrt(dx * dx + dz * dz);
    if (horiz < engineR * 0.95 && dy > 0.0 && dy < engineR * 1.7 && p.y < wingY + sy * 0.08) {
      return 5;
    }
  }
  if (absZ > fuseHalf * 1.15 && absZ < halfZ * 0.52 && p.y < wingY + sy * 0.05 && p.y > wingY - sy * 0.30 && u > 0.32 && u < 0.78) {
    return 5;
  }

  // wings / winglet
  if (w > 0.9 && v > 0.18 && v < 0.85 && u > 0.2 && u < 0.9) return 4;
  if (w > 0.30 && absZ > halfZ * 0.20 && u > 0.28 && u < 0.82) {
    float nearWingPlane = abs(p.y - wingY);
    if (nearWingPlane < sy * 0.15 && v > 0.08 && v < 0.58) return 3;
    if (w > 0.44 && v > 0.1 && v < 0.52) return 3;
  }

  // tail
  if (u < 0.22 && v > 0.45 && w < 0.40) return 6;
  if (u < 0.24 && v > 0.22 && v < 0.55 && w > 0.18 && w < 0.75) return 6;

  // nose tip / cockpit above band
  if (u > 0.92 && w < 0.32) return 1;
  if (u > 0.82 && u < 0.95 && p.y > wingY + span * 0.52 && absZ <= fuseHalf * 1.15) return 1;

  // windowband: constant-height side stripe
  float bandLo = wingY + span * 0.30;
  float bandHi = wingY + span * 0.52;
  if (absZ <= fuseHalf * 1.15 && absZ >= fuseHalf * 0.25 && p.y >= bandLo && p.y <= bandHi && p.y > uMin.y + sy * 0.18 && u > 0.12 && u < 0.92) {
    return 7;
  }

  // belly
  if (absZ <= fuseHalf * 1.2 && (vTube < 0.20 || p.y < wingY - sy * 0.04)) return 2;

  if (u > 0.88 && absZ <= fuseHalf * 1.15) return 1;
  return 0;
}

vec3 smbZoneColor(int z) {
  if (z == 1) return uColNose;
  if (z == 2) return uColBelly;
  if (z == 3) return uColWings;
  if (z == 4) return uColWinglet;
  if (z == 5) return uColEngines;
  if (z == 6) return uColTail;
  if (z == 7) return uColWindowband;
  return uColFuselage;
}
`;

    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", `#include <common>\n${fragInject}`)
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
{
  int zid = smbClassifyCraft(vCraftPos);
  vec3 zcol = smbZoneColor(zid);
  if (uHighlightZone >= 0) {
    if (zid == uHighlightZone) {
      zcol = mix(zcol, vec3(1.0, 0.604, 0.290), 0.35);
    } else {
      zcol *= 0.72;
    }
  }
  diffuseColor.rgb = zcol;
}`
      );
  };

  return mat;
}

function syncBodyZoneCraftMatrix(craft) {
  const mat = craft && craft.userData && craft.userData.bodyZoneMaterial;
  if (!mat || !mat.userData || !mat.userData.zoneUniforms) return;
  craft.updateMatrixWorld(true);
  mat.userData.zoneUniforms.uCraftWorldInverse.value.copy(craft.matrixWorld).invert();
}

function estimateWindowBandWorld(craft, size, center) {
  const ctx = craft && craft.userData && craft.userData.zoneCtx;
  if (!ctx) {
    const bandH = Math.max(0.12, size.y * 0.10);
    const yAim = center.y + size.y * 0.04;
    return {
      yAim,
      bandH,
      bandMidY: yAim,
      yBandFloor: yAim - bandH * 0.55,
      yPreferFloor: yAim - bandH * 0.25,
    };
  }
  const span = Math.max(ctx.fuseTop - ctx.wingY, 1e-6);
  // Match classifyPoint constant-height stripe (span*0.30 … span*0.52)
  const bandH = Math.max(0.06, (0.52 - 0.30) * span);
  const localY = ctx.wingY + ((0.30 + 0.52) * 0.5) * span;
  const world = new THREE.Vector3(0, localY, 0);
  craft.localToWorld(world);
  const yAim = world.y;
  return {
    yAim,
    bandH,
    bandMidY: yAim,
    yBandFloor: yAim - bandH * 0.45,
    yPreferFloor: yAim - bandH * 0.25,
  };
}

/**
 * Build hybrid zone materials on intact GLB meshes (no body face-split).
 */
function buildGlbShaderZonePaint(craft) {
  craft.updateMatrixWorld(true);
  const craftBox = new THREE.Box3().setFromObject(craft);
  const craftInv = craft.matrixWorld.clone().invert();
  const samples = [];
  const tmp = new THREE.Vector3();
  const meshes = [];

  craft.traverse((child) => {
    if (!child.isMesh || !child.geometry) return;
    if (child.userData && child.userData.skinHiddenLivery) return;
    if (child.userData && child.userData.zonePaintPart) return;
    if (child.userData && child.userData.isTextDecal) return;
    if (child.visible === false) return;
    if (child.name && /decal|textDecal|flag/i.test(child.name)) return;
    const pos = child.geometry.getAttribute("position");
    if (!pos || !pos.count) return;
    meshes.push(child);
    const step = Math.max(1, Math.floor(pos.count / 2500));
    for (let i = 0; i < pos.count; i += step) {
      tmp.fromBufferAttribute(pos, i).applyMatrix4(child.matrixWorld);
      tmp.applyMatrix4(craftInv);
      samples.push([tmp.x, tmp.y, tmp.z]);
    }
  });

  const noseSign = detectGlbNoseSign(samples);
  const localBox = craftBox.clone();
  localBox.min.applyMatrix4(craftInv);
  localBox.max.applyMatrix4(craftInv);
  const lb = new THREE.Box3(
    new THREE.Vector3(
      Math.min(localBox.min.x, localBox.max.x),
      Math.min(localBox.min.y, localBox.max.y),
      Math.min(localBox.min.z, localBox.max.z)
    ),
    new THREE.Vector3(
      Math.max(localBox.min.x, localBox.max.x),
      Math.max(localBox.min.y, localBox.max.y),
      Math.max(localBox.min.z, localBox.max.z)
    )
  );
  const ctx = buildGlbZoneContext(samples, lb, noseSign);

  const bodyMat = makeBodyZoneShaderMaterial(ctx);
  const solidMats = {
    wings: makeGlbZoneMaterial("#1b2430"),
    winglet: makeGlbZoneMaterial("#1b2430"),
    engines: makeGlbZoneMaterial("#1b2430"),
  };

  const BODY_ROLES = new Set(["fuselage", "nose", "belly", "windowband", "tail"]);
  const SOLID_ROLES = new Set(["wings", "winglet", "engines"]);

  meshes.forEach((mesh) => {
    // Drop any leftover face-split children from older sessions
    const toRemove = [];
    mesh.children.forEach((ch) => {
      if (ch.userData && ch.userData.zonePaintPart) toRemove.push(ch);
    });
    toRemove.forEach((ch) => {
      mesh.remove(ch);
      if (ch.geometry) {
        try { ch.geometry.dispose(); } catch (_) {}
      }
    });
    if (mesh.userData) {
      delete mesh.userData.zoneSplitParent;
      delete mesh.userData.paintZones;
    }
    // Restore raycast if a prior build emptied the parent
    if (typeof mesh.raycast !== "function" || mesh.geometry?.attributes?.position == null) {
      // keep geometry as-is; only reset raycast override
    }
    if (mesh.raycast && mesh.userData && mesh.userData._hadEmptyZoneParent) {
      mesh.raycast = THREE.Mesh.prototype.raycast;
    }

    const meshBox = new THREE.Box3().setFromObject(mesh);
    const role = classifyMeshRole(mesh.name, meshBox, craftBox);
    if (SOLID_ROLES.has(role)) {
      mesh.material = solidMats[role];
      mesh.userData.paintZone = role;
      mesh.userData.bodyZoneShaded = false;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
    } else {
      // Body-like (incl. unknown → fuselage): fragment classification
      mesh.material = bodyMat;
      mesh.userData.paintZone = BODY_ROLES.has(role) ? role : "fuselage";
      mesh.userData.bodyZoneShaded = true;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      // Prefer intact mesh picking by classifyPoint at hit
      mesh.userData.paintZones = true;
    }
  });

  // zoneMaterials map used by applyPaint / highlight
  const zoneMaterials = {
    fuselage: bodyMat,
    nose: bodyMat,
    belly: bodyMat,
    windowband: bodyMat,
    tail: bodyMat,
    wings: solidMats.wings,
    winglet: solidMats.winglet,
    engines: solidMats.engines,
  };

  craft.userData.zoneMaterials = zoneMaterials;
  craft.userData.bodyZoneMaterial = bodyMat;
  craft.userData.solidZoneMaterials = solidMats;
  craft.userData.zoneCtx = ctx;
  craft.userData.faceZones = false;
  craft.userData.shaderZones = true;
  syncBodyZoneCraftMatrix(craft);
  return { ctx, zoneMaterials, bodyMat };
}

/** @deprecated — face splits removed in v0.7.3; kept as alias for any stale callers. */
function buildGlbFaceZoneSplits(craft) {
  return buildGlbShaderZonePaint(craft);
}

/**
 * Fast path: update zone colors via shader uniforms / solid materials (no geometry rebuild).
 */
function applyGlbZonePaint(craft, colorsByZone) {
  if (!craft) return false;
  const mats = craft.userData && craft.userData.zoneMaterials;
  if (!mats || typeof mats !== "object") return false;

  syncBodyZoneCraftMatrix(craft);

  const bodyMat = craft.userData.bodyZoneMaterial;
  if (bodyMat && bodyMat.userData && bodyMat.userData.zoneUniforms) {
    const u = bodyMat.userData.zoneUniforms;
    const setCol = (uni, name) => {
      const c = colorsByZone[name] || colorsByZone.fuselage;
      uni.value.copy(c);
    };
    setCol(u.uColFuselage, "fuselage");
    setCol(u.uColNose, "nose");
    setCol(u.uColBelly, "belly");
    setCol(u.uColWindowband, "windowband");
    setCol(u.uColTail, "tail");
    setCol(u.uColWings, "wings");
    setCol(u.uColWinglet, "winglet");
    setCol(u.uColEngines, "engines");
    bodyMat.userData.baseColor = (colorsByZone.fuselage || new THREE.Color(0xffffff)).clone();
    bodyMat.needsUpdate = true;
  }

  const solid = craft.userData.solidZoneMaterials || {};
  ["wings", "winglet", "engines"].forEach((name) => {
    const m = solid[name] || mats[name];
    if (!m || m.userData && m.userData.isBodyZoneShader) return;
    const c = colorsByZone[name] || colorsByZone.fuselage;
    if (!m.userData) m.userData = {};
    m.userData.baseColor = c.clone();
    m.color.copy(c);
    m.vertexColors = false;
    if (m.map) {
      try { m.map.dispose(); } catch (_) {}
      m.map = null;
    }
    if (m.envMap) m.envMap = null;
    if ("metalness" in m) m.metalness = Math.min(m.metalness ?? 0.1, 0.12);
    if ("roughness" in m) m.roughness = Math.max(m.roughness ?? 0.72, 0.7);
    m.needsUpdate = true;
  });

  return true;
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


function drawSmile2d(ctx, cx, cy, s, color) {
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = Math.max(2, s * 0.12);
  ctx.beginPath();
  ctx.arc(cx, cy, s, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx - s * 0.35, cy - s * 0.15, s * 0.12, 0, Math.PI * 2);
  ctx.arc(cx + s * 0.35, cy - s * 0.15, s * 0.12, 0, Math.PI * 2);
  ctx.fill();
  ctx.beginPath();
  ctx.arc(cx, cy + s * 0.1, s * 0.55, 0.15 * Math.PI, 0.85 * Math.PI);
  ctx.stroke();
}

function drawCrown2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(cx - s, cy + s * 0.45);
  ctx.lineTo(cx - s, cy - s * 0.1);
  ctx.lineTo(cx - s * 0.5, cy + s * 0.2);
  ctx.lineTo(cx, cy - s * 0.55);
  ctx.lineTo(cx + s * 0.5, cy + s * 0.2);
  ctx.lineTo(cx + s, cy - s * 0.1);
  ctx.lineTo(cx + s, cy + s * 0.45);
  ctx.closePath();
  ctx.fill();
}

function drawDiamond2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(cx, cy - s);
  ctx.lineTo(cx + s * 0.7, cy);
  ctx.lineTo(cx, cy + s);
  ctx.lineTo(cx - s * 0.7, cy);
  ctx.closePath();
  ctx.fill();
}

function drawSun2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(2, s * 0.14);
  ctx.beginPath();
  ctx.arc(cx, cy, s * 0.45, 0, Math.PI * 2);
  ctx.fill();
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(a) * s * 0.6, cy + Math.sin(a) * s * 0.6);
    ctx.lineTo(cx + Math.cos(a) * s, cy + Math.sin(a) * s);
    ctx.stroke();
  }
}

function drawMoon2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(cx, cy, s, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalCompositeOperation = "destination-out";
  ctx.beginPath();
  ctx.arc(cx + s * 0.35, cy - s * 0.15, s * 0.85, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";
}

function drawFlag2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  ctx.fillRect(cx - s * 0.7, cy - s * 0.7, s * 0.12, s * 1.4);
  ctx.beginPath();
  ctx.moveTo(cx - s * 0.55, cy - s * 0.7);
  ctx.lineTo(cx + s * 0.7, cy - s * 0.35);
  ctx.lineTo(cx - s * 0.55, cy);
  ctx.closePath();
  ctx.fill();
}

function drawShield2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(cx, cy - s);
  ctx.lineTo(cx + s * 0.85, cy - s * 0.55);
  ctx.lineTo(cx + s * 0.7, cy + s * 0.25);
  ctx.quadraticCurveTo(cx, cy + s * 1.1, cx - s * 0.7, cy + s * 0.25);
  ctx.lineTo(cx - s * 0.85, cy - s * 0.55);
  ctx.closePath();
  ctx.fill();
}

function drawArrow2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(cx + s, cy);
  ctx.lineTo(cx + s * 0.1, cy - s * 0.55);
  ctx.lineTo(cx + s * 0.1, cy - s * 0.22);
  ctx.lineTo(cx - s, cy - s * 0.22);
  ctx.lineTo(cx - s, cy + s * 0.22);
  ctx.lineTo(cx + s * 0.1, cy + s * 0.22);
  ctx.lineTo(cx + s * 0.1, cy + s * 0.55);
  ctx.closePath();
  ctx.fill();
}

function drawSparkle2d(ctx, cx, cy, s, color) {
  ctx.fillStyle = color;
  for (const [sx, sy, sc] of [[0, 0, 1], [-0.7, -0.5, 0.45], [0.75, 0.4, 0.4]]) {
    const r = s * sc;
    ctx.beginPath();
    ctx.moveTo(cx + sx * s, cy + sy * s - r);
    ctx.lineTo(cx + sx * s + r * 0.25, cy + sy * s);
    ctx.lineTo(cx + sx * s, cy + sy * s + r);
    ctx.lineTo(cx + sx * s - r * 0.25, cy + sy * s);
    ctx.closePath();
    ctx.fill();
  }
}

function drawWingBadge2d(ctx, cx, cy, s, color) {
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = Math.max(2, s * 0.14);
  ctx.beginPath();
  ctx.moveTo(cx - s, cy);
  ctx.quadraticCurveTo(cx - s * 0.2, cy - s * 0.7, cx, cy - s * 0.15);
  ctx.quadraticCurveTo(cx + s * 0.2, cy - s * 0.7, cx + s, cy);
  ctx.quadraticCurveTo(cx + s * 0.15, cy + s * 0.35, cx, cy + s * 0.2);
  ctx.quadraticCurveTo(cx - s * 0.15, cy + s * 0.35, cx - s, cy);
  ctx.fill();
}


/** Simplified international flags (geometric only — no copyrighted logos). */
const FLAG_CATALOG = {
  US: { name: "United States", bars: ["#B22234", "#FFFFFF", "#B22234", "#FFFFFF", "#B22234", "#FFFFFF", "#B22234"], canton: "#3C3B6E" },
  GB: { name: "United Kingdom", type: "uk" },
  RO: { name: "Romania", stripes: "v", colors: ["#002B7F", "#FCD116", "#CE1126"] },
  DE: { name: "Germany", stripes: "h", colors: ["#000000", "#DD0000", "#FFCE00"] },
  FR: { name: "France", stripes: "v", colors: ["#002395", "#FFFFFF", "#ED2939"] },
  IT: { name: "Italy", stripes: "v", colors: ["#009246", "#FFFFFF", "#CE2B37"] },
  ES: { name: "Spain", stripes: "h", colors: ["#AA151B", "#F1BF00", "#AA151B"], ratios: [1, 2, 1] },
  PT: { name: "Portugal", stripes: "v", colors: ["#006600", "#FF0000"], ratios: [2, 3], disc: "#FFFF00" },
  NL: { name: "Netherlands", stripes: "h", colors: ["#AE1C28", "#FFFFFF", "#21468B"] },
  BE: { name: "Belgium", stripes: "v", colors: ["#000000", "#FAE042", "#ED2939"] },
  PL: { name: "Poland", stripes: "h", colors: ["#FFFFFF", "#DC143C"] },
  UA: { name: "Ukraine", stripes: "h", colors: ["#0057B7", "#FFD700"] },
  TR: { name: "Turkey", type: "tr" },
  GR: { name: "Greece", type: "gr" },
  SE: { name: "Sweden", type: "cross", bg: "#006AA7", cross: "#FECC00" },
  NO: { name: "Norway", type: "cross", bg: "#EF2B2D", cross: "#FFFFFF", cross2: "#002868" },
  FI: { name: "Finland", type: "cross", bg: "#FFFFFF", cross: "#003580" },
  DK: { name: "Denmark", type: "cross", bg: "#C8102E", cross: "#FFFFFF" },
  IE: { name: "Ireland", stripes: "v", colors: ["#169B62", "#FFFFFF", "#FF883E"] },
  CH: { name: "Switzerland", type: "ch" },
  AT: { name: "Austria", stripes: "h", colors: ["#ED2939", "#FFFFFF", "#ED2939"] },
  JP: { name: "Japan", type: "jp" },
  KR: { name: "South Korea", type: "kr" },
  CN: { name: "China", type: "cn" },
  IN: { name: "India", stripes: "h", colors: ["#FF9933", "#FFFFFF", "#138808"], disc: "#000080" },
  BR: { name: "Brazil", type: "br" },
  MX: { name: "Mexico", stripes: "v", colors: ["#006847", "#FFFFFF", "#CE1126"] },
  AU: { name: "Australia", type: "au" },
  NZ: { name: "New Zealand", type: "nz" },
  AE: { name: "United Arab Emirates", stripes: "h", colors: ["#00732F", "#FFFFFF", "#000000", "#FF0000"], hoist: "#FF0000" },
  SA: { name: "Saudi Arabia", type: "sa" },
  CA: { name: "Canada", stripes: "v", colors: ["#FF0000", "#FFFFFF", "#FF0000"], ratios: [1, 2, 1] },
  CZ: { name: "Czechia", type: "cz" },
  MD: { name: "Moldova", stripes: "v", colors: ["#003DA5", "#FFD200", "#CC092F"] },
  BG: { name: "Bulgaria", stripes: "h", colors: ["#FFFFFF", "#00966E", "#D62612"] },
  HU: { name: "Hungary", stripes: "h", colors: ["#CE2939", "#FFFFFF", "#477050"] },
  RS: { name: "Serbia", stripes: "h", colors: ["#C6363C", "#0C4076", "#FFFFFF"] },
  SK: { name: "Slovakia", stripes: "h", colors: ["#FFFFFF", "#0B4EA2", "#EE1C25"] },
  AR: { name: "Argentina", stripes: "h", colors: ["#74ACDF", "#FFFFFF", "#74ACDF"], disc: "#F6B40E" },
  IL: { name: "Israel", type: "il" },
  EG: { name: "Egypt", stripes: "h", colors: ["#CE1126", "#FFFFFF", "#000000"], disc: "#C09300" },
  ZA: { name: "South Africa", type: "za" },
  NG: { name: "Nigeria", stripes: "v", colors: ["#008751", "#FFFFFF", "#008751"] },
  KE: { name: "Kenya", type: "ke" },
  HR: { name: "Croatia", stripes: "h", colors: ["#FF0000", "#FFFFFF", "#171796"] },
  SI: { name: "Slovenia", stripes: "h", colors: ["#FFFFFF", "#0055A4", "#FF0000"] },
  LT: { name: "Lithuania", stripes: "h", colors: ["#FDB913", "#006A44", "#C1272D"] },
  LV: { name: "Latvia", stripes: "h", colors: ["#9E3039", "#FFFFFF", "#9E3039"], ratios: [2, 1, 2] },
  EE: { name: "Estonia", stripes: "h", colors: ["#0072CE", "#000000", "#FFFFFF"] },
};

function drawSimpleFlag(ctx, x, y, w, h, code) {
  const def = FLAG_CATALOG[code];
  if (!def) return;
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  // default white base
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(x, y, w, h);

    if (def.bars && def.canton) {
    const n = def.bars.length;
    const hh = h / n;
    def.bars.forEach((c, bi) => {
      ctx.fillStyle = c;
      ctx.fillRect(x, y + bi * hh, w, hh + 0.5);
    });
    ctx.fillStyle = def.canton;
    ctx.fillRect(x, y, w * 0.4, h * 0.54);
  } else if (def.stripes === "h") {
    const cols = def.colors;
    const ratios = def.ratios || cols.map(() => 1);
    const sum = ratios.reduce((a, b) => a + b, 0);
    let yy = y;
    cols.forEach((c, i) => {
      const hh = (h * ratios[i]) / sum;
      ctx.fillStyle = c;
      ctx.fillRect(x, yy, w, hh + 0.5);
      yy += hh;
    });
    if (def.disc) {
      ctx.fillStyle = def.disc;
      ctx.beginPath();
      ctx.arc(x + w / 2, y + h / 2, Math.min(w, h) * 0.18, 0, Math.PI * 2);
      ctx.fill();
    }
    if (def.hoist) {
      ctx.fillStyle = def.hoist;
      ctx.fillRect(x, y, w * 0.25, h);
    }
  } else if (def.stripes === "v") {
    const cols = def.colors;
    const ratios = def.ratios || cols.map(() => 1);
    const sum = ratios.reduce((a, b) => a + b, 0);
    let xx = x;
    cols.forEach((c, i) => {
      const ww = (w * ratios[i]) / sum;
      ctx.fillStyle = c;
      ctx.fillRect(xx, y, ww + 0.5, h);
      xx += ww;
    });
    if (def.disc) {
      ctx.fillStyle = def.disc;
      ctx.beginPath();
      ctx.arc(x + w * 0.35, y + h / 2, Math.min(w, h) * 0.18, 0, Math.PI * 2);
      ctx.fill();
    }
  } else if (def.type === "uk") {
    ctx.fillStyle = "#012169";
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = h * 0.2;
    ctx.beginPath();
    ctx.moveTo(x, y); ctx.lineTo(x + w, y + h);
    ctx.moveTo(x + w, y); ctx.lineTo(x, y + h);
    ctx.stroke();
    ctx.strokeStyle = "#C8102E";
    ctx.lineWidth = h * 0.08;
    ctx.stroke();
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(x, y + h * 0.35, w, h * 0.3);
    ctx.fillRect(x + w * 0.4, y, w * 0.2, h);
    ctx.fillStyle = "#C8102E";
    ctx.fillRect(x, y + h * 0.42, w, h * 0.16);
    ctx.fillRect(x + w * 0.44, y, w * 0.12, h);
  } else if (def.type === "cross") {
    ctx.fillStyle = def.bg;
    ctx.fillRect(x, y, w, h);
    const t = h * 0.22;
    ctx.fillStyle = def.cross;
    ctx.fillRect(x, y + (h - t) / 2, w, t);
    ctx.fillRect(x + w * 0.32, y, t * 0.9, h);
    if (def.cross2) {
      const t2 = t * 0.45;
      ctx.fillStyle = def.cross2;
      ctx.fillRect(x, y + (h - t2) / 2, w, t2);
      ctx.fillRect(x + w * 0.32 + (t * 0.9 - t2) / 2, y, t2, h);
    }
  } else if (def.type === "jp") {
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#BC002D";
    ctx.beginPath();
    ctx.arc(x + w / 2, y + h / 2, h * 0.3, 0, Math.PI * 2);
    ctx.fill();
  } else if (def.type === "ch") {
    ctx.fillStyle = "#FF0000";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#FFFFFF";
    const t = h * 0.18;
    ctx.fillRect(x + w * 0.2, y + (h - t) / 2, w * 0.6, t);
    ctx.fillRect(x + (w - t) / 2, y + h * 0.2, t, h * 0.6);
  } else if (def.type === "tr") {
    ctx.fillStyle = "#E30A17";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#FFFFFF";
    ctx.beginPath();
    ctx.arc(x + w * 0.4, y + h / 2, h * 0.28, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#E30A17";
    ctx.beginPath();
    ctx.arc(x + w * 0.46, y + h / 2, h * 0.22, 0, Math.PI * 2);
    ctx.fill();
  } else if (def.type === "cn") {
    ctx.fillStyle = "#DE2910";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#FFDE00";
    // simplified stars as circles
    ctx.beginPath();
    ctx.arc(x + w * 0.18, y + h * 0.3, h * 0.12, 0, Math.PI * 2);
    ctx.fill();
  } else if (def.type === "br") {
    ctx.fillStyle = "#009C3B";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#FFDF00";
    ctx.beginPath();
    ctx.moveTo(x + w / 2, y + h * 0.12);
    ctx.lineTo(x + w * 0.88, y + h / 2);
    ctx.lineTo(x + w / 2, y + h * 0.88);
    ctx.lineTo(x + w * 0.12, y + h / 2);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#002776";
    ctx.beginPath();
    ctx.arc(x + w / 2, y + h / 2, h * 0.18, 0, Math.PI * 2);
    ctx.fill();
  } else if (def.type === "sa") {
    ctx.fillStyle = "#005430";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(x + w * 0.2, y + h * 0.55, w * 0.6, h * 0.08);
  } else if (def.type === "gr") {
    ctx.fillStyle = "#0D5EAF";
    ctx.fillRect(x, y, w, h);
    for (let i = 0; i < 9; i++) {
      if (i % 2 === 1) {
        ctx.fillStyle = "#FFFFFF";
        ctx.fillRect(x, y + (h / 9) * i, w, h / 9 + 0.5);
      }
    }
    ctx.fillStyle = "#0D5EAF";
    ctx.fillRect(x, y, w * 0.35, h * (5 / 9));
    ctx.fillStyle = "#FFFFFF";
    const t = h * 0.08;
    ctx.fillRect(x, y + h * 0.18, w * 0.35, t);
    ctx.fillRect(x + w * 0.14, y, t, h * (5 / 9));
  } else if (def.type === "kr" || def.type === "au" || def.type === "nz" || def.type === "cz") {
    // simplified stand-ins
    if (def.type === "kr") {
      ctx.fillStyle = "#FFFFFF";
      ctx.fillRect(x, y, w, h);
      ctx.fillStyle = "#CD2E3A";
      ctx.beginPath();
      ctx.arc(x + w / 2, y + h / 2, h * 0.22, Math.PI, 0);
      ctx.fill();
      ctx.fillStyle = "#0047A0";
      ctx.beginPath();
      ctx.arc(x + w / 2, y + h / 2, h * 0.22, 0, Math.PI);
      ctx.fill();
    } else if (def.type === "cz") {
      ctx.fillStyle = "#FFFFFF";
      ctx.fillRect(x, y, w, h / 2);
      ctx.fillStyle = "#D7141A";
      ctx.fillRect(x, y + h / 2, w, h / 2);
      ctx.fillStyle = "#11457E";
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + w * 0.45, y + h / 2);
      ctx.lineTo(x, y + h);
      ctx.closePath();
      ctx.fill();
    } else {
      // AU / NZ blue with canton hint
      ctx.fillStyle = "#00008B";
      ctx.fillRect(x, y, w, h);
      ctx.fillStyle = "#012169";
      ctx.fillRect(x, y, w * 0.45, h * 0.5);
      ctx.fillStyle = "#FFFFFF";
      ctx.fillRect(x + w * 0.18, y + h * 0.08, w * 0.05, h * 0.34);
      ctx.fillRect(x + w * 0.08, y + h * 0.2, w * 0.25, h * 0.08);
    }
  } else if (def.type === "il") {
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#0038B8";
    ctx.fillRect(x, y + h * 0.15, w, h * 0.12);
    ctx.fillRect(x, y + h * 0.73, w, h * 0.12);
    ctx.strokeStyle = "#0038B8";
    ctx.lineWidth = Math.max(1, h * 0.04);
    const cx = x + w / 2, cy = y + h / 2, r = h * 0.18;
    ctx.beginPath();
    ctx.moveTo(cx, cy - r); ctx.lineTo(cx + r * 0.87, cy + r * 0.5); ctx.lineTo(cx - r * 0.87, cy + r * 0.5); ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx, cy + r); ctx.lineTo(cx + r * 0.87, cy - r * 0.5); ctx.lineTo(cx - r * 0.87, cy - r * 0.5); ctx.closePath();
    ctx.stroke();
  } else if (def.type === "za") {
    ctx.fillStyle = "#002395";
    ctx.fillRect(x, y, w, h);
    ctx.fillStyle = "#DE3831";
    ctx.fillRect(x, y, w, h * 0.33);
    ctx.fillStyle = "#007A4D";
    ctx.fillRect(x, y + h * 0.67, w, h * 0.33);
    ctx.fillStyle = "#000000";
    ctx.beginPath();
    ctx.moveTo(x, y); ctx.lineTo(x + w * 0.4, y + h / 2); ctx.lineTo(x, y + h); ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#FFB612";
    ctx.beginPath();
    ctx.moveTo(x, y + h * 0.12); ctx.lineTo(x + w * 0.32, y + h / 2); ctx.lineTo(x, y + h * 0.88); ctx.closePath();
    ctx.fill();
  } else if (def.type === "ke") {
    ctx.fillStyle = "#000000";
    ctx.fillRect(x, y, w, h * 0.33);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(x, y + h * 0.3, w, h * 0.08);
    ctx.fillStyle = "#BB0000";
    ctx.fillRect(x, y + h * 0.36, w, h * 0.28);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(x, y + h * 0.62, w, h * 0.08);
    ctx.fillStyle = "#006600";
    ctx.fillRect(x, y + h * 0.68, w, h * 0.32);
  } else if (def.bars && def.canton) {
    const n = def.bars.length;
    const hh = h / n;
    def.bars.forEach((c, i) => {
      ctx.fillStyle = c;
      ctx.fillRect(x, y + i * hh, w, hh + 0.5);
    });
    ctx.fillStyle = def.canton;
    ctx.fillRect(x, y, w * 0.4, h * 0.54);
  }
  // thin border
  ctx.strokeStyle = "rgba(0,0,0,0.35)";
  ctx.lineWidth = 1;
  ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
  ctx.restore();
}

function drawCountryFlagsOnCanvas(ctx, W, H, state, layout) {
  const flags = state.flags || {};
  const codes = flags.codes || [];
  if (!codes.length) return;
  const scale = (layout && layout.scale) || stickerSizeMul(state);
  const fw = Math.max(36, 52 * scale * 0.55);
  const fh = fw * 0.62;
  const place = flags.placement || "both";
  // Free mode: user X/Y offsets (−150…150). Left/Both/Right ignore sliders.
  const free = place === "free";
  // Normalize so ±150 spans most of the fuselage panel
  const posX = free ? Number(flags.posX != null ? flags.posX : 0) / 150 : 0;
  const posY = free ? Number(flags.posY != null ? flags.posY : 10) / 150 : 0.07;
  const baseY = Math.max(fh * 0.6, Math.min(H - fh * 0.6, H * (0.50 + posY * 0.42)));
  const mid = layout && layout.xMid != null ? layout.xMid : W / 2;
  const gap = fw * 1.15;
  const totalW = codes.length * gap;
  const startX = mid - totalW / 2 + fw * 0.1 + posX * W * 0.45;

  function paintRow(x0) {
    codes.forEach((code, i) => {
      drawSimpleFlag(ctx, x0 + i * gap, baseY - fh / 2, fw, fh, code);
    });
  }
  if (place === "left" || place === "both" || place === "free") {
    paintRow(startX);
  }
  if (place === "right") {
    // Single-panel decal: still draw once; dual UV: offset to other half
    paintRow(layout && layout.dual ? startX + W * 0.5 : startX);
  } else if (place === "both" && layout && layout.dual) {
    paintRow(startX + W * 0.5);
  }
  // free: single mark (like left) — offsets already applied; do not mirror to dual half
}

function stickerSizeMul(state) {
  // Kept for flag scale; stickers removed in v0.7.1
  const k = String((state && state.flagSize) || (state && state.stickerSize) || "M").toUpperCase();
  if (k === "S") return 1.6;
  if (k === "L") return 3.0;
  return 2.2;
}

function drawStickersOnCanvas(ctx, W, H, state, layout) {
  const st = state.stickers || {};
  const accent =
    (state.colors && (state.colors.accent || state.colors.tail)) || "#FF6A00";
  // layout: "decal" (single panel) or "half" with x0 offset for procedural sides
  const xMid = layout.xMid != null ? layout.xMid : W / 2;
  const scale = (layout.scale || 1) * stickerSizeMul(state);
  const x0 = layout.x0 || 0;

  if (st.stripe) {
    const sy = layout.stripeY != null ? layout.stripeY : H * 0.82;
    ctx.fillStyle = accent;
    ctx.fillRect(x0, sy, layout.bandW || W, 8 * scale);
    ctx.fillStyle = state.colors && state.colors.tail ? state.colors.tail : "#FF6A00";
    ctx.fillRect(x0, sy + 8 * scale, layout.bandW || W, 6 * scale);
  }
  if (st.heart) drawHeart2d(ctx, xMid - 70 * scale, H * 0.22, 16 * scale, "#dc2840");
  if (st.star) drawStar2d(ctx, xMid + 80 * scale, H * 0.2, 18 * scale, "#ffd24a");
  if (st.lightning) drawLightning2d(ctx, x0 + 40 * scale, H * 0.55, 22 * scale, "#ffe566");
  if (st.bird) drawBird2d(ctx, xMid, H * 0.88, 28 * scale, state.textColor || "#FFFFFF");
  if (st.roundel) drawRoundel2d(ctx, x0 + 36 * scale, H * 0.55, 22 * scale);
  if (st.chevron) drawChevron2d(ctx, xMid + 100 * scale, H * 0.55, 20 * scale, "#ffffff");
  if (st.checkered) drawCheckered2d(ctx, x0, H * 0.05, layout.bandW || W, 18 * scale, 16, "#111111", "#f5f5f5");
  if (st.smile) drawSmile2d(ctx, xMid - 110 * scale, H * 0.35, 14 * scale, "#ffd24a");
  if (st.crown) drawCrown2d(ctx, xMid + 40 * scale, H * 0.18, 14 * scale, "#ffd24a");
  if (st.diamond) drawDiamond2d(ctx, xMid - 30 * scale, H * 0.65, 12 * scale, "#7ec8ff");
  if (st.sun) drawSun2d(ctx, x0 + 70 * scale, H * 0.28, 14 * scale, "#ffb020");
  if (st.moon) drawMoon2d(ctx, xMid + 120 * scale, H * 0.32, 12 * scale, "#d0d8ff");
  if (st.flag) drawFlag2d(ctx, x0 + 90 * scale, H * 0.7, 14 * scale, accent);
  if (st.shield) drawShield2d(ctx, xMid - 90 * scale, H * 0.55, 14 * scale, "#3d7cff");
  if (st.arrow) drawArrow2d(ctx, xMid + 60 * scale, H * 0.72, 16 * scale, "#ffffff");
  if (st.sparkle) drawSparkle2d(ctx, xMid + 20 * scale, H * 0.4, 12 * scale, "#fff6a8");
  if (st.wingbadge) drawWingBadge2d(ctx, xMid, H * 0.78, 18 * scale, state.textColor || "#FFFFFF");
}

function paintDecalCanvas(canvas, state) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  prepareCanvas2d(ctx, W, H);

  // v0.7.1: stickers removed — title / slogan / flags only
  const hasAirlineId = !!(state.airline && String(state.airline).trim());
  const hasSlogan = !!(state.slogan && String(state.slogan).trim());
  const showText = hasAirlineId || hasSlogan;
  const flagCodes = (state.flags && state.flags.codes) || [];
  const hasFlags = flagCodes.length > 0;

  if (hasFlags) {
    drawCountryFlagsOnCanvas(ctx, W, H, state, { xMid: W / 2, scale: stickerSizeMul(state) });
  }

  if (!showText && !hasFlags) return;
  if (!showText) return;

  const textColor = state.textColor || "#FFFFFF";
  const sizeKey = state.textSize || "M";
  const basePx = sizeKey === "S" ? 140 : sizeKey === "L" ? 320 : 240; // v0.7.2 larger title
  const maxW = W * 0.92;

  ctx.fillStyle = textColor;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.shadowColor = "rgba(0,0,0,0.55)";
  ctx.shadowBlur = 8;

  const airline = state.airline || "SkinMyBird";
  const airPx = fitFontPx(ctx, airline, maxW, basePx, state, 22);
  ctx.font = resolveFontFace(state, airPx);
  ctx.lineJoin = "round";
  ctx.miterLimit = 2;
  ctx.strokeStyle = "rgba(0,0,0,0.55)";
  ctx.lineWidth = Math.max(2, airPx * 0.08);
  ctx.strokeText(airline, W / 2, H * 0.48);
  ctx.fillText(airline, W / 2, H * 0.48);

  if (state.slogan) {
    const sloganState = { ...state, textStyle: state.textStyle === "bold-italic" || state.textStyle === "italic" ? "italic" : "regular" };
    // keep weight lighter for slogan but honor italic
    const style = String(state.textStyle || "").toLowerCase();
    const sloganStyle = style.includes("italic")
      ? (style.includes("bold") ? "bold-italic" : "italic")
      : "regular";
    const sState = { ...state, textStyle: sloganStyle };
    const sPx = fitFontPx(ctx, state.slogan, maxW, Math.round(basePx * 0.55), sState, 14);
    ctx.font = resolveFontFace(sState, sPx);
    ctx.fillText(state.slogan, W / 2, H * 0.48 + airPx * 0.58);
  }

  // Registration: fuselage/belly use one aft decal (addTextDecals / makeRegTexture).
  // Tail / wing bake a single mark into this panel (aft path is skipped there).
  if (
    state.registration &&
    (state.textPlacement === "tail" || state.textPlacement === "wing")
  ) {
    const rState = { ...state, textStyle: "bold" };
    const rPx = fitFontPx(ctx, state.registration, maxW * 0.55, Math.round(basePx * 0.42), rState, 10);
    ctx.font = resolveFontFace(rState, rPx);
    ctx.globalAlpha = 0.95;
    const regY = state.textPlacement === "tail" ? H * 0.72 : H * 0.62;
    ctx.fillText(state.registration, W / 2, regY);
    ctx.globalAlpha = 1;
  }
  ctx.shadowBlur = 0;
}

function makeDecalTexture(state, w = DECAL_W, h = DECAL_H) {
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  paintDecalCanvas(canvas, state);
  const tex = new THREE.CanvasTexture(canvas);
  configurePaintTexture(tex);
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
  // Side-skin priority for airline/reg decals (window belt first). Crown/cockpit/belly
  // are NEVER side-decal targets — they map to other roles and are excluded below.
  const SIDE_ZONE_PRI = {
    windowband: 0,
    fuselage: 1,
  };
  const SIDE_ZONES = new Set(["windowband", "fuselage"]);
  craft.traverse((child) => {
    if (!child.isMesh || !child.geometry) return;
    if (child.name === "textDecals" || (child.parent && child.parent.name === "textDecals"))
      return;
    // Skip existing decal meshes + empty zone-split parents
    if (child.userData && child.userData.isTextDecal) return;
    if (child.userData && child.userData.zoneSplitParent) return;
    const box = new THREE.Box3().setFromObject(child);
    const size = box.getSize(new THREE.Vector3());
    const vol = Math.max(size.x, 0.001) * Math.max(size.y, 0.001) * Math.max(size.z, 0.001);
    const isZonePart = !!(child.userData && child.userData.zonePaintPart);
    const isBodyShaded = !!(child.userData && child.userData.bodyZoneShaded);
    if (vol < 0.02 && !isZonePart && !isBodyShaded) return;
    let role = classifyMeshRole(child.name, box, craftBox);
    // v0.7.3: read paintZone from solid-role / body-shaded meshes (not only zonePaintPart)
    let paintZone = (child.userData && child.userData.paintZone) || null;
    if (paintZone) {
      const z = paintZone;
      if (SIDE_ZONES.has(z)) role = "fuselage";
      else if (z === "belly") role = "belly";
      else if (z === "nose") role = "nose";
      else if (z === "wings" || z === "winglet") role = "wings";
      else if (z === "tail") role = "tail";
      else if (z === "engines") role = "engines";
    } else if (isBodyShaded) {
      paintZone = "fuselage";
      if (role === "fuselage" || role === "nose" || role === "windowband") role = "fuselage";
    }
    const sidePri = paintZone != null && SIDE_ZONE_PRI[paintZone] != null
      ? SIDE_ZONE_PRI[paintZone]
      : (role === "fuselage" ? 5 : 9);
    scored.push({ mesh: child, role, vol, box, size, paintZone, sidePri });
  });
  scored.sort((a, b) => a.sidePri - b.sidePri || b.vol - a.vol);
  // fuselage list = true lateral skins only (no crown/cockpit/belly)
  const fuselage = scored.filter((s) => s.role === "fuselage");
  const wings = scored.filter((s) => s.role === "wings");
  const tail = scored.filter((s) => s.role === "tail");
  const belly = scored.filter((s) => s.role === "belly");
  return { all: scored.map((s) => s.mesh), fuselage, wings, tail, belly, craftBox, scored };
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

/**
 * Prefer fuselage skin hits (near centerline). Skip wing/outboard hits
 * that appear when casting from far away at low Y.
 */
function raycastFuselageHit(meshes, origin, dir, raycaster, center, maxAbsZ, preferY, opts) {
  if (!meshes.length) return null;
  const options = opts || {};
  const maxNy = options.maxNy != null ? options.maxNy : 0.45;
  const preferSideZones = !!options.preferSideZones;
  const SIDE_OK = new Set(["windowband", "fuselage"]);
  raycaster.set(origin, dir.clone().normalize());
  const hits = raycaster.intersectObjects(meshes, true);
  let best = null;
  let bestScore = Infinity;
  const nMat = new THREE.Matrix3();
  const wN = new THREE.Vector3();
  for (const h of hits) {
    if (!h.face || !h.object || !h.object.isMesh) continue;
    if (h.object.userData && h.object.userData.isTextDecal) continue;
    if (h.object.userData && h.object.userData.zoneSplitParent) continue;
    const az = Math.abs(h.point.z - center.z);
    if (az > maxAbsZ) continue; // wing / outboard rejection
    const zone = h.object.userData && h.object.userData.paintZone;
    // Hard reject roof/canopy/underside zone meshes — never treat crown as fuselage success
    if (zone === "belly") continue;
    // Soft pass: prefer named lateral skins when present
    if (preferSideZones && zone && !SIDE_OK.has(zone)) continue;
    // World normal: keep mostly sideways; reject roof/belly-facing faces
    nMat.getNormalMatrix(h.object.matrixWorld);
    wN.copy(h.face.normal).applyNormalMatrix(nMat).normalize();
    if (Math.abs(wN.y) > maxNy) continue; // |Ny| dominant → crown ridge / belly
    const sideFacing = Math.abs(wN.z); // 1 = pure side
    const vertical = Math.abs(wN.y);
    let zonePen = 0;
    if (zone === "windowband" || zone === "fuselage")
      zonePen = -2.0;
    const yErr = preferY != null ? Math.abs(h.point.y - preferY) * 2.5 : 0;
    // Lower score wins: side-facing window-band near aim Y
    const score =
      az * 6 +
      h.distance +
      yErr +
      zonePen +
      vertical * 5 -
      sideFacing * 5;
    if (score < bestScore) {
      bestScore = score;
      best = h;
    }
  }
  return best;
}

function canvasTextureFromCanvas(canvas) {
  const tex = new THREE.CanvasTexture(canvas);
  configurePaintTexture(tex);
  tex.userData.canvas = canvas;
  return tex;
}

/** Horizontally mirror a canvas so left/right fuselage both read L→R from outside. */
function mirrorCanvasHorizontal(srcCanvas) {
  const c = document.createElement("canvas");
  c.width = srcCanvas.width;
  c.height = srcCanvas.height;
  const ctx = c.getContext("2d");
  ctx.translate(c.width, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(srcCanvas, 0, 0);
  return c;
}

function sideMaterialFromTex(baseTex, flipU, sharedMatOpts) {
  let matMap;
  if (flipU && baseTex.userData && baseTex.userData.canvas) {
    matMap = canvasTextureFromCanvas(mirrorCanvasHorizontal(baseTex.userData.canvas));
  } else {
    matMap = baseTex.clone();
    matMap.userData = baseTex.userData;
    matMap.needsUpdate = true;
  }
  matMap.wrapS = THREE.ClampToEdgeWrapping;
  matMap.wrapT = THREE.ClampToEdgeWrapping;
  return new THREE.MeshBasicMaterial({
    ...sharedMatOpts,
    map: matMap,
  });
}

/**
 * Auto horizontal flip so fuselage text reads L→R from outside.
 * After face-split DecalGeometry orientation (v0.6.0+), projector U already
 * reads correctly on both fuselage sides — no auto flip. Text-tab checkboxes
 * apply a manual corrective mirror when a side still looks wrong.
 */
function autoFlipUFromHit(hit) {
  return false;
}

function resolveFlipU(hit, side, flipLeft, flipRight) {
  const autoFlip = autoFlipUFromHit(hit);
  const userFix = side < 0 ? !!flipLeft : !!flipRight;
  return autoFlip !== userFix; // XOR: unchecked = auto (none); checked = mirror that side
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


function makeRegTexture(state) {
  // Single aft registration decal (one mark per side). Not airline/slogan.
  const canvas = document.createElement("canvas");
  canvas.width = REG_W;
  canvas.height = REG_H;
  const ctx = canvas.getContext("2d");
  prepareCanvas2d(ctx, REG_W, REG_H);
  if (!state.registration) {
    const tex = new THREE.CanvasTexture(canvas);
    configurePaintTexture(tex);
    tex.userData.canvas = canvas;
    return tex;
  }
  const rState = { ...state, textStyle: "bold", textFont: state.textFont };
  ctx.fillStyle = state.textColor || "#FFFFFF";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.shadowColor = "rgba(0,0,0,0.45)";
  ctx.shadowBlur = 8;
  const px =
    typeof fitFontPx === "function"
      ? fitFontPx(ctx, state.registration, REG_W * 0.92, 200, rState, 36)
      : 72;
  ctx.font =
    typeof resolveFontFace === "function"
      ? resolveFontFace(rState, px)
      : `700 ${px}px "Segoe UI", system-ui, sans-serif`;
  ctx.lineJoin = "round";
  ctx.strokeStyle = "rgba(0,0,0,0.3)";
  ctx.lineWidth = Math.max(1.5, px * 0.045);
  ctx.strokeText(state.registration, REG_W / 2, REG_H / 2);
  ctx.fillText(state.registration, REG_W / 2, REG_H / 2);
  ctx.shadowBlur = 0;
  const tex = new THREE.CanvasTexture(canvas);
  configurePaintTexture(tex);
  tex.userData.canvas = canvas;
  return tex;
}

/**
 * v0.7.3 — Custom uploaded texture decals (Custom 1/2/3).
 * Fuselage placement aims forward of wing LE at windowband mid (same path as titles).
 * Multi-X side raycasts; PlaneGeometry hard fallback if still no hit.
 */
function ensureCustomSlotImage(slot) {
  if (!slot || !slot.dataUrl) return null;
  const existing = slot._img;
  if (existing && existing.complete && existing.naturalWidth) return existing;
  if (slot._pendingImgLoad) return null;
  slot._pendingImgLoad = true;
  const img = new Image();
  img.onload = () => {
    slot._img = img;
    slot._pendingImgLoad = false;
    try {
      const prev = typeof window !== "undefined" ? window.__SMB_PREVIEW : null;
      if (prev) {
        prev._lastStateKey = "";
        if (prev._lastPaintState) prev.applyPaint(prev._lastPaintState);
      }
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("skinmybird-custom-texture-ready"));
      }
    } catch (err) {
      console.warn("custom texture remount failed", err);
    }
  };
  img.onerror = () => {
    slot._pendingImgLoad = false;
    console.warn("custom texture image failed to load", slot.name || "(unnamed)");
  };
  img.src = slot.dataUrl;
  return null;
}

function placeFallbackPlaneDecal(group, craft, side, x, y, fusR, center, decalSize, mat, renderOrder) {
  const z = center.z + side * fusR;
  const geo = new THREE.PlaneGeometry(
    Math.max(0.4, decalSize.x),
    Math.max(0.35, decalSize.y)
  );
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(x, y, z);
  // Face outward (±Z)
  mesh.lookAt(x, y, z + side * 2);
  mesh.renderOrder = renderOrder;
  mesh.userData.isTextDecal = true;
  mesh.userData.isCustomFallback = true;
  group.add(mesh);
  return mesh;
}

function addCustomTextureDecals(craft, state, group, targets, box, size, center, raycaster) {
  const slots = state.customTextures || [];
  if (!slots.length || !group) return;
  const reach = Math.max(size.z, size.y, size.x) * 1.25 + 2;
  const fusR = Math.max(0.35, Math.min(size.y * 0.26, 0.95));
  const maxFusAbsZ = fusR * 2.35;
  const scored = targets.scored || [];
  const fusLen = size.x;

  // Wing LE + title-like forward X (fixes v0.7.2 miss at center.x / wing root)
  let wingLeX = null;
  if (targets.wings && targets.wings.length) {
    const fusNearZ = Math.max(0.45, Math.min(size.y * 0.4, size.z * 0.14));
    const nearRoot = [];
    for (const w of targets.wings) {
      if (!w.box) continue;
      const cz = (w.box.min.z + w.box.max.z) * 0.5;
      const straddles = w.box.min.z <= center.z && w.box.max.z >= center.z;
      const absCz = Math.abs(cz - center.z);
      if (straddles || absCz <= fusNearZ * 2.5) nearRoot.push(w);
    }
    const useWings = nearRoot.length ? nearRoot : targets.wings;
    let maxX = -Infinity;
    let minX = Infinity;
    for (const w of useWings) {
      if (w.box) {
        maxX = Math.max(maxX, w.box.max.x);
        minX = Math.min(minX, w.box.min.x);
      }
    }
    if (Number.isFinite(maxX)) {
      wingLeX = maxX;
      const noseX = center.x + size.x * 0.5;
      if (maxX < center.x && Number.isFinite(minX) &&
          Math.abs(noseX - minX) < Math.abs(noseX - maxX)) {
        wingLeX = minX;
      }
    }
  }
  if (wingLeX != null) {
    wingLeX += Math.max(0.04 * fusLen, 0.15);
    wingLeX = Math.max(wingLeX, center.x + size.x * 0.02);
  }

  const wbScored = scored.filter((s) => s.paintZone === "windowband");
  let yAimTitle;
  let bandH;
  if (wbScored.length) {
    const union = new THREE.Box3();
    for (const s of wbScored) union.union(s.box);
    bandH = Math.max(0.06, union.max.y - union.min.y);
    yAimTitle = union.min.y + bandH * 0.50;
  } else {
    const est = estimateWindowBandWorld(craft, size, center);
    yAimTitle = est.yAim;
    bandH = est.bandH;
  }

  const gap = Math.max(0.055 * fusLen, 0.22);
  const xAftMin = (wingLeX != null) ? wingLeX + gap : center.x + size.x * 0.12;
  const xFwdMax = center.x + size.x * 0.22;
  let xTitle = xAftMin + Math.max(0, xFwdMax - xAftMin) * 0.65;
  if (!(xFwdMax > xAftMin)) xTitle = center.x + size.x * 0.16;

  slots.forEach((slot, idx) => {
    if (!slot || !slot.dataUrl) return;
    const img = ensureCustomSlotImage(slot);
    if (!img || !img.complete || !img.naturalWidth) return;
    const placement = slot.placement || "fuselage";
    const opacity = Math.max(0.05, Math.min(1, (Number(slot.opacity) || 100) / 100));
    const scale = Math.max(0.3, Math.min(2.5, (Number(slot.scale) || 100) / 100));
    const posX = Number(slot.posX || 0) / 100;
    const posY = Number(slot.posY || 0) / 100;

    const canvas = document.createElement("canvas");
    const cw = 1024, ch = 1024;
    canvas.width = cw;
    canvas.height = ch;
    const ctx2d = canvas.getContext("2d");
    prepareCanvas2d(ctx2d, cw, ch);
    ctx2d.globalAlpha = opacity;
    const ir = img.naturalWidth / img.naturalHeight;
    let dw = cw, dh = ch;
    if (ir > 1) dh = cw / ir;
    else dw = ch * ir;
    ctx2d.drawImage(img, (cw - dw) / 2, (ch - dh) / 2, dw, dh);
    ctx2d.globalAlpha = 1;
    const tex = new THREE.CanvasTexture(canvas);
    configurePaintTexture(tex);

    const matOpts = {
      map: tex,
      transparent: true,
      depthTest: true,
      depthWrite: false,
      side: THREE.FrontSide,
      polygonOffset: true,
      polygonOffsetFactor: -4,
      polygonOffsetUnits: -4,
      opacity: 1,
    };

    let meshList;
    if (placement === "wings") {
      meshList = (targets.wings || []).map((t) => t.mesh);
      if (!meshList.length) {
        meshList = scored
          .filter((s) => s.paintZone === "wings" || s.paintZone === "winglet" || s.role === "wings")
          .map((s) => s.mesh);
      }
    } else if (placement === "tail") {
      meshList = (targets.tail || []).map((t) => t.mesh)
        .concat((targets.fuselage || []).map((t) => t.mesh));
    } else if (placement === "belly") {
      meshList = (targets.belly || []).map((t) => t.mesh)
        .concat((targets.fuselage || []).map((t) => t.mesh));
    } else {
      // fuselage: prefer windowband + fuselage (intact body meshes in v0.7.3)
      const sideParts = scored.filter(
        (s) =>
          s.paintZone === "windowband" ||
          s.paintZone === "fuselage" ||
          s.role === "fuselage" ||
          (s.mesh && s.mesh.userData && s.mesh.userData.bodyZoneShaded)
      );
      meshList = sideParts.length
        ? sideParts.map((s) => s.mesh)
        : (targets.fuselage || []).map((t) => t.mesh);
      if (!meshList.length) meshList = (targets.all || []).slice(0, 8);
    }

    // Clearly visible default size (~0.32 of fuselage length at 100%)
    const baseW = Math.max(0.75, Math.min(size.x * 0.32, 2.6)) * scale;
    const baseH = baseW * (dh / dw);
    const depth = Math.max(0.3, Math.min(size.y * 0.3, 0.55));
    const decalSize = new THREE.Vector3(baseW, Math.max(0.4, baseH), depth);

    let x0;
    let y0;
    if (placement === "fuselage") {
      // Same forward-of-LE / windowband mid aim as titles
      x0 = xTitle - size.x * posX * 0.35;
      x0 = Math.min(xFwdMax, Math.max(xAftMin - 0.02 * fusLen, x0));
      y0 = yAimTitle + bandH * (posY * 0.12);
    } else {
      x0 = center.x - size.x * posX * 0.35;
      y0 = center.y + size.y * (0.02 + posY * 0.25);
    }
    if (placement === "belly") y0 = center.y - size.y * 0.15;
    if (placement === "wings") y0 = center.y + size.y * 0.05;
    if (placement === "tail") x0 = center.x - size.x * (0.28 + posX * 0.1);

    // Multi-X samples (title-like) for fuselage / tail sides
    const xSamples = [x0];
    if (placement === "fuselage" || placement === "tail") {
      const extras = [
        x0,
        x0 + fusLen * 0.03,
        x0 - fusLen * 0.03,
        center.x + size.x * 0.18,
        center.x + size.x * 0.14,
        center.x + size.x * 0.12,
        center.x + size.x * 0.20,
        xAftMin + (xFwdMax - xAftMin) * 0.5,
      ];
      for (const x of extras) {
        if (Number.isFinite(x) && !xSamples.includes(x)) xSamples.push(x);
      }
    }

    const yCands = [
      y0,
      y0 - bandH * 0.08,
      y0 + bandH * 0.08,
      y0 - bandH * 0.18,
      yAimTitle,
    ];

    const sides = placement === "fuselage" || placement === "tail" ? [-1, 1] : [1];
    sides.forEach((side) => {
      let hit = null;
      if (placement === "belly") {
        const origin = new THREE.Vector3(x0, center.y - reach, center.z + side * 0.05);
        hit = raycastBestHit(meshList, origin, new THREE.Vector3(0, 1, 0), raycaster);
      } else if (placement === "wings") {
        const origin = new THREE.Vector3(
          x0,
          center.y + reach * 0.55,
          center.z + side * size.z * 0.28
        );
        hit = raycastBestHit(meshList, origin, new THREE.Vector3(0, -1, 0), raycaster);
      } else {
        // Title-path lateral casts with preferSideZones on windowband+fuselage
        let best = null;
        let bestErr = Infinity;
        for (const tx of xSamples) {
          for (const y of yCands) {
            const zDist = fusR * 2.4;
            const origin = new THREE.Vector3(tx, y, center.z + side * zDist);
            const dir = new THREE.Vector3(0, 0, -side);
            let h = raycastFuselageHit(meshList, origin, dir, raycaster, center, maxFusAbsZ, y, {
              maxNy: 0.55,
              preferSideZones: placement === "fuselage",
            });
            if (!h) {
              origin.z = center.z + side * (fusR * 3.6);
              h = raycastFuselageHit(meshList, origin, dir, raycaster, center, maxFusAbsZ, y, {
                maxNy: 0.55,
                preferSideZones: false,
              });
            }
            if (!h) {
              origin.z = center.z + side * (fusR * 3.2);
              h = raycastFuselageHit(meshList, origin, dir, raycaster, center, maxFusAbsZ * 1.35, y, {
                maxNy: 0.88,
                preferSideZones: false,
              });
            }
            if (!h) h = raycastBestHit(meshList, origin, dir, raycaster);
            if (!h || !h.point) continue;
            const err = Math.abs(h.point.y - yAimTitle) + Math.abs(h.point.x - x0) * 0.15;
            if (err < bestErr) {
              bestErr = err;
              best = h;
            }
          }
          if (best && bestErr < bandH * 0.35) break;
        }
        hit = best;
      }
      if (!hit) {
        console.warn(
          "addCustomTextureDecals: no hit for",
          placement,
          "side",
          side,
          slot.name || idx,
          "— using plane fallback"
        );
        const flipU = placement === "fuselage" ? side < 0 : false;
        const mat = sideMaterialFromTex(tex, flipU, matOpts);
        placeFallbackPlaneDecal(
          group,
          craft,
          side,
          x0,
          y0,
          fusR * 1.02,
          center,
          decalSize,
          mat,
          4 + idx
        );
        return;
      }
      const flipU = placement === "fuselage" ? resolveFlipU(hit, side, false, false) : false;
      const mat = sideMaterialFromTex(tex, flipU, matOpts);
      projectDecal(group, hit, decalSize, mat, 4 + idx);
    });
  });
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

  const flagCodes = (state.flags && state.flags.codes) || [];
  const hasIdentityText = !!(
    (state.airline && String(state.airline).trim()) ||
    (state.slogan && String(state.slogan).trim()) ||
    (state.registration && String(state.registration).trim())
  );
  const hasCustom = (state.customTextures || []).some((t) => t && t.dataUrl);
  const anyVisual = flagCodes.length > 0 || hasIdentityText || hasCustom;
  if (!anyVisual) {
    return { tex: null, mat: null, group, regTex: null };
  }

  const place = state.textPlacement || "fuselage";
  const tex = makeDecalTexture(state, DECAL_W, DECAL_H);
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

  // Wing LE X from wing mesh AABBs near fuselage root (not tip cloud).
  // Hangar fit: nose = +X; root LE ≈ max.x of wing meshes close to center.z.
  let wingLeX = null;
  if (targets.wings && targets.wings.length) {
    const fusNearZ = Math.max(0.45, Math.min(size.y * 0.4, size.z * 0.14));
    const nearRoot = [];
    for (const w of targets.wings) {
      if (!w.box) continue;
      const cz = (w.box.min.z + w.box.max.z) * 0.5;
      const straddles = w.box.min.z <= center.z && w.box.max.z >= center.z;
      const absCz = Math.abs(cz - center.z);
      const minAbsExtent = Math.min(
        Math.abs(w.box.min.z - center.z),
        Math.abs(w.box.max.z - center.z),
        absCz
      );
      if (straddles || absCz <= fusNearZ * 2.5 || minAbsExtent <= fusNearZ * 1.8) {
        nearRoot.push(w);
      }
    }
    const useWings = nearRoot.length ? nearRoot : targets.wings;
    let maxX = -Infinity;
    let minX = Infinity;
    for (const w of useWings) {
      if (w.box) {
        maxX = Math.max(maxX, w.box.max.x);
        minX = Math.min(minX, w.box.min.x);
      }
    }
    if (Number.isFinite(maxX)) {
      wingLeX = maxX;
      const noseX = center.x + size.x * 0.5;
      if (maxX < center.x && Number.isFinite(minX) &&
          Math.abs(noseX - minX) < Math.abs(noseX - maxX)) {
        wingLeX = minX; // invert: min.x closer to nose
      }
    }
  }
  // v0.6.15: AABB often sits aft of visual LE at fuselage; bias nose-ward + floor
  if (wingLeX != null) {
    wingLeX += Math.max(0.04 * fusLen, 0.15);
  }
  const wingLeFloor = center.x + size.x * 0.02; // LE shouldn't be aft of near-center
  if (wingLeX != null) wingLeX = Math.max(wingLeX, wingLeFloor);

  // --- v0.6.15 window-band belt (per-side title X on solid band; clear wing LE + nose taper) ---
  // sideBeltMeshes: windowband + accent + fuselage sides (title may hit fuselage at band Y).
  // Fallback fuselage ONLY if no windowband. Never belly / crown / cockpit / fairings / wings.
  // Nose is +X on hangar-fit craft (longest axis forward); wing LE = forward-most root wing AABB X.
  const scored = targets.scored || [];
  const wbScored = scored.filter((s) => s.paintZone === "windowband");
  const fuselageScored = scored.filter((s) => s.paintZone === "fuselage");
  let sideBeltScored;
  if (wbScored.length) {
    sideBeltScored = wbScored.concat(fuselageScored);
  } else {
    sideBeltScored = fuselageScored.length
      ? fuselageScored
      : scored.filter((s) => s.paintZone === "fuselage");
  }
  let sideBeltMeshes = sideBeltScored.map((s) => s.mesh);
  // v0.7.3: without zone-split children, use intact body-shaded / fuselage-role meshes
  if (!sideBeltMeshes.length) {
    sideBeltMeshes = scored
      .filter(
        (s) =>
          s.role === "fuselage" ||
          (s.mesh && s.mesh.userData && s.mesh.userData.bodyZoneShaded)
      )
      .map((s) => s.mesh);
  }
  const fuselageSideMeshes = scored
    .filter(
      (s) =>
        s.paintZone === "fuselage" ||
        s.paintZone === "windowband" ||
        s.role === "fuselage" ||
        (s.mesh && s.mesh.userData && s.mesh.userData.bodyZoneShaded)
    )
    .map((s) => s.mesh);

  // User offsets (need posX/posY before yAim / xMain)
  const posX = Number(state.textPosX || 0) / 100;
  const posY = Number(state.textPosY != null ? state.textPosY : 8) / 100;
  const scalePct = Math.max(0.5, Math.min(1.8, (Number(state.textScale) || 155) / 100));
  // Title panel length first — needed for xMain and local-band X filter
  let panelLen =
    place === "tail" ? fusLen * 0.32 :
    place === "wing" ? Math.min(size.z * 0.28, fusLen * 0.35) :
    fusLen * 0.24; // v0.7.2 larger readable title panel

  // Solid-interval clamps (nose = +X). Used for fuselage title X and per-side candidates.
  let xAftMin = center.x + size.x * 0.08;
  let xFwdMax = center.x + size.x * 0.14;

  // Title X: fit panel in solid interval [xAftMin, xFwdMax] — aft of wing LE gap, clear of nose taper
  let xMain;
  if (place === "tail") {
    xMain = center.x - size.x * (0.28 + posX * 0.1);
  } else if (place === "wing") {
    xMain = center.x - size.x * 0.02;
  } else {
    // v0.7.2: larger panel (readable); keep forward of LE with gap; bias size over notch clearance
    const gap = Math.max(0.055 * fusLen, 0.22);
    xAftMin = (wingLeX != null) ? wingLeX + gap : center.x + size.x * 0.10;
    // Room to slide nose-ward; per-side wb hit avoids taper clip
    xFwdMax = center.x + size.x * 0.26;
    panelLen = fusLen * 0.24;
    const airlineLen = String(state.airline || "").trim().length;
    if (airlineLen > 12) panelLen *= 0.94;
    const span = xFwdMax - xAftMin;
    // if span inverted / too tight: fall back to proven forward cabin (still large)
    if (span < panelLen * 0.55) {
      xMain = center.x + size.x * 0.18;
      panelLen = fusLen * 0.22;
      if (airlineLen > 12) panelLen *= 0.94;
      xAftMin = xMain - panelLen * 0.5;
      xFwdMax = xMain + panelLen * 0.5;
    } else {
      // prefer even more FORWARD in interval (closer to nose, clear of wing-root notch)
      xMain = xAftMin + span * 0.75;
      xMain = Math.min(xFwdMax - panelLen * 0.5, Math.max(xAftMin + panelLen * 0.5, xMain));
    }
    // Guarantees: aft edge >= xAftMin (forward of LE), fwd edge <= xFwdMax (clear of taper)
    // User posX nudge within clamps (posX>0 shifts aft / −X)
    xMain -= size.x * posX * 0.35;
    {
      const span2 = xFwdMax - xAftMin;
      if (span2 > 0) {
        xMain = Math.min(xFwdMax - panelLen * 0.5, Math.max(xAftMin + panelLen * 0.5, xMain));
      }
    }
  }

  // Aim Y: LOCAL windowband near title X — CENTER of band (0.50) so glyphs sit on cyan
  let yAim;
  let bandH;
  let yBandFloor;
  let yPreferFloor;
  let bandMidY;
  if (wbScored.length && place !== "belly" && place !== "wing" && place !== "tail") {
    const xPad = Math.max(panelLen * 0.6, fusLen * 0.15);
    const xLo = xMain - xPad;
    const xHi = xMain + xPad;
    const localWb = wbScored.filter((s) => {
      if (!s.box) return false;
      // AABB overlaps title X region, or within 0.15*fusLen of xMain
      return s.box.max.x >= xLo && s.box.min.x <= xHi;
    });
    const useWb = localWb.length ? localWb : wbScored;
    const union = new THREE.Box3();
    for (const s of useWb) union.union(s.box);
    bandH = Math.max(0.06, union.max.y - union.min.y);
    bandMidY = (union.min.y + union.max.y) * 0.5;
    // v0.6.12: center title in band mid (0.50) so glyphs sit on cyan
    yAim = union.min.y + bandH * 0.50;
    yAim += bandH * (posY * 0.12);
    // Reject true belly; allow mid band
    yBandFloor = union.min.y + bandH * 0.15;
    // Prefer hits near band mid (used with |y-yAim| ranking)
    yPreferFloor = union.min.y + bandH * 0.25;
  } else if (wbScored.length && place !== "belly" && place !== "wing") {
    const union = new THREE.Box3();
    for (const s of wbScored) union.union(s.box);
    bandH = Math.max(0.06, union.max.y - union.min.y);
    bandMidY = (union.min.y + union.max.y) * 0.5;
    yAim = bandMidY;
    yAim += bandH * (posY * 0.12);
    yBandFloor = union.min.y + bandH * 0.15;
    yPreferFloor = union.min.y + bandH * 0.25;
  } else {
    // v0.7.3: no face-split windowband boxes — estimate from zoneCtx parametric bands
    const est = estimateWindowBandWorld(craft, size, center);
    bandH = est.bandH;
    bandMidY = est.bandMidY;
    yAim = est.yAim + bandH * (posY * 0.12);
    yBandFloor = est.yBandFloor;
    yPreferFloor = est.yPreferFloor;
  }
  // Softer Y ladder: aim, then ±8%, −18%/+15%, then band mid
  const yAlts = [
    yAim,
    yAim - bandH * 0.08,
    yAim + bandH * 0.08,
    yAim - bandH * 0.18,
    yAim + bandH * 0.15,
    bandMidY,
  ];
  const yWindow = yAim;

  // v0.7.2: title fills most of windowband height (~0.90*bandH)
  const titlePanelH =
    place === "wing" ? Math.max(0.4, panelLen * 0.38) :
    place === "belly" || place === "tail" ? Math.max(0.38, Math.min(size.y * 0.32, 0.85)) :
    Math.max(bandH * 0.78, Math.min(bandH * 0.98, bandH * 0.90));
  const panelDepth = Math.max(0.35, Math.min(size.y * 0.35, 0.55));

  const stickerBoost = 1; // stickers removed; title size from textScale / titlePanelH
  const flipLeft = !!state.textFlipLeft;
  const flipRight = !!state.textFlipRight;
  const decalSize = new THREE.Vector3(
    panelLen * scalePct * Math.min(stickerBoost, 1.55),
    titlePanelH * scalePct * Math.min(stickerBoost, 1.55),
    panelDepth
  );

  const fusR = Math.max(0.35, Math.min(size.y * 0.26, 0.95));
  const maxFusAbsZ = fusR * 2.35;
  const reach = Math.max(size.z, size.y, size.x) * 1.25 + 2;

  function meshesForPlace(forReg) {
    if (place === "wing" && targets.wings.length)
      return targets.wings.map((t) => t.mesh);
    if (place === "belly") {
      const list = (targets.belly || []).map((t) => t.mesh);
      const fus = targets.fuselage.map((t) => t.mesh);
      if (list.length || fus.length) return list.concat(fus);
    }
    if (place === "tail") {
      const list = targets.tail.map((t) => t.mesh);
      const fus = targets.fuselage.map((t) => t.mesh);
      if (list.length || fus.length) return list.concat(fus);
    }
    if (!forReg && sideBeltMeshes.length) return sideBeltMeshes;
    if (forReg) {
      const seen = new Set();
      const out = [];
      for (const m of sideBeltMeshes.concat(fuselageSideMeshes)) {
        if (!m || seen.has(m.uuid)) continue;
        seen.add(m.uuid);
        out.push(m);
      }
      if (out.length) return out;
    }
    if (sideBeltMeshes.length) return sideBeltMeshes;
    if (targets.fuselage.length) return targets.fuselage.map((t) => t.mesh);
    return targets.all.slice(0, 4);
  }

  const meshListTitle = meshesForPlace(false);
  const meshListReg = meshesForPlace(true);

  function trySideHit(sideSign, x, yCandidates, meshList, castOpts) {
    const probeYs = Array.isArray(yCandidates) ? yCandidates.slice() : [yCandidates];
    const meshes = meshList || meshListTitle;
    const opts = Object.assign({ maxNy: 0.4, preferSideZones: true }, castOpts || {});
    function castAtY(y) {
      let origin, dir, hit;
      if (place === "belly") {
        origin = new THREE.Vector3(x, center.y - reach, center.z + sideSign * 0.05);
        dir = new THREE.Vector3(0, 1, -sideSign * 0.02).normalize();
        return raycastBestHit(meshes, origin, dir, raycaster);
      }
      if (place === "wing") {
        origin = new THREE.Vector3(
          x,
          center.y + reach * 0.55,
          center.z + sideSign * size.z * 0.28
        );
        dir = new THREE.Vector3(0, -1, 0);
        return raycastBestHit(meshes, origin, dir, raycaster);
      }
      // Lateral cast — title may relax maxNy; reg keeps 0.4
      const zDist = fusR * 2.4;
      origin = new THREE.Vector3(x, y, center.z + sideSign * zDist);
      dir = new THREE.Vector3(0, 0, -sideSign);
      hit = raycastFuselageHit(meshes, origin, dir, raycaster, center, maxFusAbsZ, y, opts);
      if (!hit) {
        origin = new THREE.Vector3(x, y, center.z + sideSign * (fusR * 3.6));
        hit = raycastFuselageHit(meshes, origin, dir, raycaster, center, maxFusAbsZ, y, opts);
      }
      if (hit && hit.point && hit.point.y < yBandFloor) hit = null;
      return hit;
    }
    // v0.6.12: prefer hit closest to band mid (yAim), NOT max point.y
    let best = null;
    let bestErr = Infinity;
    let bestPrefer = null;
    let bestPreferErr = Infinity;
    for (const y of probeYs) {
      const hit = castAtY(y);
      if (!hit || !hit.point) continue;
      const err = Math.abs(hit.point.y - yAim);
      if (err < bestErr) {
        bestErr = err;
        best = hit;
      }
      if (hit.point.y >= yPreferFloor && err < bestPreferErr) {
        bestPreferErr = err;
        bestPrefer = hit;
      }
    }
    return bestPrefer || best;
  }

  function hitPaintZone(hit) {
    if (!hit || !hit.object || !hit.object.userData) return null;
    return hit.object.userData.paintZone || hit.object.userData.zoneName || null;
  }

  // v0.6.16: build per-side title X candidates — left adds extra nose-ward first
  function buildSideTitleXs(side) {
    const preferred = [];
    const lastResort = [];
    const fwdLimit = xFwdMax + 0.01 * fusLen;
    const aftSoft = xAftMin - 0.02 * fusLen;
    // Cap last-resort aft so title centroid stays forward of wing LE
    const aftHard = (wingLeX != null)
      ? wingLeX + 0.02 * fusLen
      : aftSoft;
    function pushCand(x, into) {
      if (!Number.isFinite(x)) return;
      if (x > fwdLimit) return;
      if (!into.includes(x)) into.push(x);
    }
    // Prefer forward candidates first (nose-ward), then slightly aft.
    // Left (−Z): extra forward candidates first so TE clears wing-root fairing notch.
    const rawRight = [
      xMain,
      xMain + 0.02 * fusLen,
      center.x + size.x * 0.20,
      center.x + size.x * 0.18,
      center.x + size.x * 0.16,
      center.x + size.x * 0.14,
      xMain - 0.02 * fusLen,
      center.x + size.x * 0.12,
      xMain - 0.04 * fusLen,
    ];
    const rawLeft = [
      xMain + 0.03 * fusLen,
      center.x + size.x * 0.21,
      xMain,
      xMain + 0.02 * fusLen,
      center.x + size.x * 0.20,
      center.x + size.x * 0.18,
      center.x + size.x * 0.16,
      center.x + size.x * 0.14,
      xMain - 0.02 * fusLen,
      center.x + size.x * 0.12,
      xMain - 0.04 * fusLen,
    ];
    const raw = side === -1 ? rawLeft : rawRight;
    for (const x of raw) {
      if (x < aftSoft) pushCand(x, lastResort);
      else pushCand(x, preferred);
    }
    // Last resort: allow slightly aft of soft floor if preferred empty,
    // but never aft of wingLeX + 0.02*fusLen when wing LE known
    if (!preferred.length) {
      for (const x of raw) {
        if (x >= aftHard) pushCand(x, lastResort);
      }
    } else {
      // one step closer to LE as last resort (still above aftHard)
      const closer = Math.max(aftHard, Math.min(xMain, xAftMin) - 0.02 * fusLen);
      pushCand(closer, lastResort);
    }
    return { preferred, lastResort };
  }

  // LEFT (−Z) and RIGHT (+Z) — airline / sticker title (per-side X; prefer windowband)
  const titleCastOpts = { maxNy: 0.52, preferSideZones: true };
  [-1, 1].forEach((side) => {
    let hit = null;
    let usedX = null;
    const yCands = place === "belly" || place === "wing" ? [yWindow] : yAlts;
    const { preferred, lastResort } = buildSideTitleXs(side);
    const allXs = preferred.concat(lastResort);

    // Pass 1: windowband hits — right: first good; left: prefer larger hit.point.x (nose-ward)
    if (side === -1) {
      let bestWb = null;
      let bestTx = null;
      for (const tx of preferred) {
        const h = trySideHit(side, tx, yCands, meshListTitle, titleCastOpts);
        if (h && hitPaintZone(h) === "windowband" && h.point) {
          if (!bestWb || h.point.x > bestWb.point.x) {
            bestWb = h;
            bestTx = tx;
          }
        }
      }
      if (bestWb) {
        hit = bestWb;
        usedX = bestTx;
      }
    } else {
      for (const tx of preferred) {
        const h = trySideHit(side, tx, yCands, meshListTitle, titleCastOpts);
        if (h && hitPaintZone(h) === "windowband") {
          hit = h;
          usedX = tx;
          break;
        }
      }
    }
    // Pass 2: any side hit on accent/fuselage/windowband at band Y (preferred then last resort)
    if (!hit) {
      for (const tx of allXs) {
        const h = trySideHit(side, tx, yCands, meshListTitle, titleCastOpts);
        if (!h) continue;
        const zone = hitPaintZone(h);
        if (zone === "windowband" || zone === "fuselage" || zone == null) {
          hit = h;
          usedX = tx;
          break;
        }
      }
    }
    if (!hit) {
      console.warn("addTextDecals: no hit on side", side, place, "meshes", meshListTitle.length, "triedXs", allXs);
      return;
    }
    console.info(
      "addTextDecals: title hit side",
      side,
      "x",
      usedX,
      "y",
      hit.point && hit.point.y,
      "zone",
      hitPaintZone(hit),
      "xMain",
      xMain,
      "xAftMin",
      xAftMin,
      "xFwdMax",
      xFwdMax,
      "wingLeX",
      wingLeX
    );
    const flipU = resolveFlipU(hit, side, flipLeft, flipRight);
    const mat = sideMaterialFromTex(tex, flipU, sharedMatOpts);
    const sizeVec =
      place === "belly"
        ? new THREE.Vector3(panelLen, titlePanelH * 0.85, panelDepth)
        : decalSize.clone();
    projectDecal(group, hit, sizeVec, mat, 2);
  });

  if (place === "belly" && group.children.length === 0) {
    const origin = new THREE.Vector3(xMain, center.y - reach, center.z);
    const hit = raycastBestHit(meshListTitle, origin, new THREE.Vector3(0, 1, 0), raycaster);
    if (hit) {
      const mat = sideMaterialFromTex(tex, false, sharedMatOpts);
      projectDecal(
        group,
        hit,
        new THREE.Vector3(panelLen, titlePanelH * 0.85, panelDepth),
        mat,
        2
      );
    }
  }

  // One aft registration per side — SAME yAim ladder as title (windowband); maxNy 0.4
  let regTex = null;
  if (state.registration && place !== "tail" && place !== "wing") {
    regTex = makeRegTexture(state);
    // v0.7.2: larger aft registration
    const regW = Math.min(1.55, Math.max(1.05, size.x * 0.15));
    const regH = Math.max(bandH * 0.55, Math.min(bandH * 0.85, regW * 0.36));
    const regDepth = panelDepth * 0.9;
    const regSize = new THREE.Vector3(regW, regH, regDepth);
    const regXAft = [0.18, 0.22, 0.28, 0.32].map((f) => center.x - size.x * f);
    const regXFwd = [0.14, 0.10, 0.06]
      .map((f) => center.x - size.x * f)
      .filter((x) => x < xMain - size.x * 0.05);
    const regXCandidates = regXAft.concat(regXFwd);
    const regYAlts = yAlts.slice();
    const regCastOpts = { maxNy: 0.4, preferSideZones: true };

    [-1, 1].forEach((side) => {
      let hit = null;
      for (const rx of regXCandidates) {
        hit = trySideHit(side, rx, regYAlts, meshListReg, regCastOpts);
        if (hit) break;
      }
      if (!hit) {
        console.warn("addTextDecals: no registration hit on side", side);
        return;
      }
      const flipU = resolveFlipU(hit, side, flipLeft, flipRight);
      const mat = sideMaterialFromTex(regTex, flipU, sharedMatOpts);
      projectDecal(group, hit, regSize, mat, 3);
    });
  }

  // Custom texture uploads (after title/reg so they layer above paint, below/near text)
  try {
    addCustomTextureDecals(craft, state, group, targets, box, size, center, raycaster);
  } catch (err) {
    console.warn("custom texture decals failed", err);
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
  prepareCanvas2d(ctx, W, H);
  const fus = state.colors.fuselage || "#f2f4f7";
  const tail = state.colors.tail || fus;
  const nose = state.colors.nose || fus;
  const bellyCol = state.colors.belly || fus;
  const windowBand = state.colors.windowband || fus;
  const textColor = state.textColor || "#FFFFFF";

  ctx.clearRect(0, 0, W, H);

  // Base fuselage fill
  ctx.fillStyle = fus;
  ctx.fillRect(0, 0, W, H);

  // Belly zone (lower band)
  ctx.fillStyle = bellyCol;
  ctx.globalAlpha = 0.92;
  ctx.fillRect(0, H * 0.72, W, H * 0.28);
  ctx.globalAlpha = 1;

  // Nose / cockpit band — forward on each UV half
  ctx.fillStyle = nose;
  for (const hx of [0, W / 2]) {
    ctx.fillRect(hx + W * 0.02, H * 0.28, W * 0.1, H * 0.32);
  }

  // Subtle belly shade
  const belly = ctx.createLinearGradient(0, H * 0.55, 0, H);
  belly.addColorStop(0, "rgba(0,0,0,0)");
  belly.addColorStop(1, "rgba(0,0,0,0.18)");
  ctx.fillStyle = belly;
  ctx.fillRect(0, 0, W, H);

  // Upper highlight
  const top = ctx.createLinearGradient(0, 0, 0, H * 0.35);
  top.addColorStop(0, "rgba(255,255,255,0.14)");
  top.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = top;
  ctx.fillRect(0, 0, W, H);

  // Cabin window band + window row (skip balloon/helo)
  if (family !== "balloon" && family !== "helicopter") {
    const winY = H * 0.40;
    const winH = H * 0.09;
    // Soft band behind windows (tintable zone)
    ctx.fillStyle = windowBand;
    ctx.globalAlpha = 0.88;
    ctx.fillRect(0, winY - H * 0.01, W, winH + H * 0.02);
    ctx.globalAlpha = 1;
    // Soft door outlines (same as body — no separate doors zone in v0.7.1)
    ctx.strokeStyle = fus;
    ctx.globalAlpha = 0.35;
    ctx.lineWidth = 3;
    for (const hx of [0, W / 2]) {
      for (const dx of [W * 0.12, W * 0.38]) {
        const dx0 = hx + dx;
        ctx.strokeRect(dx0, H * 0.34, W * 0.035, H * 0.28);
      }
    }
    ctx.globalAlpha = 1;
    // Window panes
    ctx.fillStyle = "#152030";
    const cols = family === "widebody" || family === "747" ? 28 : 18;
    const paneH = H * 0.055;
    for (let half = 0; half < 2; half++) {
      const x0 = half * (W / 2) + W * 0.08;
      for (let i = 0; i < cols; i++) {
        const wx = x0 + i * ((W * 0.38) / cols);
        ctx.fillRect(wx, winY + H * 0.015, 10, paneH);
      }
    }
  }

  // v0.7.1: no decorative stickers on procedural fuselage — flags + identity text only
  const flagCodes = (state.flags && state.flags.codes) || [];
  if (flagCodes.length) {
    drawCountryFlagsOnCanvas(ctx, W, H, state, { xMid: W * 0.25, scale: stickerSizeMul(state), dual: true });
  }

  // Title (airline) + Slogan on both UV halves; Registration when placed on tail/wing
  const place = state.textPlacement || "fuselage";
  const hasAirline = !!(state.airline && String(state.airline).trim());
  const hasSlogan = !!(state.slogan && String(state.slogan).trim());
  if (hasAirline || hasSlogan || (state.registration && (place === "tail" || place === "wing"))) {
    const sizeKey = state.textSize || "M";
    const basePx = sizeKey === "S" ? 54 : sizeKey === "L" ? 110 : 84;
    const maxW = W * 0.38;
    ctx.fillStyle = textColor;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.shadowColor = "rgba(0,0,0,0.45)";
    ctx.shadowBlur = 6;

    const drawSideText = (xCenter) => {
      let y = H * 0.42;
      let airPx = 0;
      if (hasAirline) {
        airPx = fitFontPx(ctx, state.airline, maxW, basePx, state, 16);
        ctx.font = resolveFontFace(state, airPx);
        ctx.strokeStyle = "rgba(0,0,0,0.55)";
        ctx.lineWidth = Math.max(2, airPx * 0.08);
        ctx.lineJoin = "round";
        ctx.strokeText(state.airline, xCenter, y);
        ctx.fillText(state.airline, xCenter, y);
      }
      if (hasSlogan) {
        const style = String(state.textStyle || "").toLowerCase();
        const sloganStyle = style.includes("italic")
          ? (style.includes("bold") ? "bold-italic" : "italic")
          : "regular";
        const sState = { ...state, textStyle: sloganStyle };
        const sPx = fitFontPx(ctx, state.slogan, maxW, Math.round(basePx * 0.5), sState, 10);
        ctx.font = resolveFontFace(sState, sPx);
        ctx.fillText(state.slogan, xCenter, y + Math.max(airPx, basePx * 0.4) * 0.58);
      }
      if (state.registration && (place === "tail" || place === "wing")) {
        const rState = { ...state, textStyle: "bold" };
        const regPx = fitFontPx(
          ctx,
          state.registration,
          maxW * 0.55,
          Math.round(basePx * 0.42),
          rState,
          10
        );
        ctx.font = resolveFontFace(rState, regPx);
        const regY = place === "tail" ? y + airPx * 0.75 : H * 0.52;
        ctx.fillText(state.registration, xCenter, regY);
      }
    };

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
  configurePaintTexture(tex);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.ClampToEdgeWrapping;
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
    "747": { len: 18.8, rad: 0.88, wingSpan: 17.2, wingY: -0.24, engCount: 4, engScale: 1.22, rootChord: 3.2, tipChord: 1.18 },
    ga: { len: 7.2, rad: 0.38, wingSpan: 9.0, wingY: -0.05, engCount: 0, engScale: 0.7, rootChord: 1.5, tipChord: 0.7 },
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

  // 747 upper-deck hump — clear forward bubble (classic jumbo, not a tube)
  if (family === "747") {
    const humpPts = [
      new THREE.Vector2(0.001, s.len * 0.26),
      new THREE.Vector2(R * 0.55, s.len * 0.24),
      new THREE.Vector2(R * 0.88, s.len * 0.16),
      new THREE.Vector2(R * 0.98, s.len * 0.06),
      new THREE.Vector2(R * 0.95, -s.len * 0.02),
      new THREE.Vector2(R * 0.72, -s.len * 0.12),
      new THREE.Vector2(R * 0.35, -s.len * 0.2),
      new THREE.Vector2(0.001, -s.len * 0.24),
    ];
    const hump = new THREE.Mesh(new THREE.LatheGeometry(humpPts, 36), mats.fuselage);
    hump.rotation.z = -Math.PI / 2;
    // Sit on top of forward fuselage (nose = +X)
    hump.position.set(half * 0.42, R * 0.78, 0);
    hump.scale.set(1.08, 1.05, 1.02);
    hump.name = "hump";
    hump.castShadow = true;
    group.add(hump);
    // Fairing blend into main deck (aft of hump)
    const fair = addCyl(
      group, R * 1.05, R * 0.65, s.len * 0.1,
      half * 0.02, R * 0.42, 0,
      mats.fuselage, 0, 0, Math.PI / 2, 28
    );
    fair.name = "humpFairing";
    // Distinct radome tip (nose zone — solid so nose swatch is obvious)
    const radome = addCyl(
      group, R * 0.08, R * 0.55, s.len * 0.07,
      half - s.len * 0.045, 0, 0,
      mats.nose || mats.fuselage, 0, 0, Math.PI / 2, 20
    );
    radome.name = "nose";
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

  // Winglet tips (tintable accent zone)
  const tipZ = s.wingSpan * 0.48;
  for (const side of [-1, 1]) {
    const wl = addBox(
      group,
      0.35,
      0.85,
      0.08,
      -0.15,
      s.wingY + 0.35,
      side * tipZ,
      mats.winglet || mats.tail,
      0,
      0,
      side * 0.15
    );
    wl.name = "winglet";
  }

  // Vertical fin (tall on 747) + horizontal stabilizer (own paint zone)
  const finH = family === "747" ? 3.65 : family === "widebody" ? 2.9 : 2.25;
  const finRootX = -half + s.len * 0.12;
  const fin = addBox(
    group,
    1.65,
    finH,
    0.12,
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
  addBox(group, 0.5, 0.2, 0.13, finRootX - 0.4, finH * 0.88, 0, mats.tail, 0, 0, -0.22);

  const stabSpan = family === "widebody" || family === "747" ? 5.6 : 3.9;
  const stab = addBox(
    group,
    1.2,
    0.08,
    stabSpan,
    -half + s.len * 0.08,
    R * 0.55,
    0,
    mats.stabilizer || mats.tail,
    0,
    0,
    -0.12
  );
  stab.name = "stabilizer";

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
  const eng = state.colors.engines || "#1b2430";
  const fus = state.colors.fuselage || "#f2f4f7";
  return {
    fuselage: matTextured(fuselageMap, fus),
    nose: matSolid(state.colors.nose || fus, { metalness: 0.28, roughness: 0.55 }),
    wings: matSolid(state.colors.wings || "#1b2430", { metalness: 0.4, roughness: 0.5 }),
    winglet: matSolid(state.colors.winglet || state.colors.wings || "#1b2430", {
      metalness: 0.35,
      roughness: 0.5,
    }),
    engines: matSolid(eng, { metalness: 0.55, roughness: 0.4 }),
    enginesDark: matSolid(shadeHex(eng, -30), { metalness: 0.6, roughness: 0.35 }),
    tail: matSolid(state.colors.tail || fus, { metalness: 0.3, roughness: 0.55 }),
    stabilizer: matSolid(
      state.colors.stabilizer || state.colors.tail || fus,
      { metalness: 0.32, roughness: 0.52 }
    ),
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
    this._lastPaintState = null;
    this._highlightedZone = null;
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
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2.5));
    this.renderer.setSize(w, h, false);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    try {
      _maxAnisotropy = this.renderer.capabilities.getMaxAnisotropy() || 8;
    } catch (_) {
      _maxAnisotropy = 8;
    }
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.setClearColor(0x000000, 0);

    this.scene = new THREE.Scene();

    this.camera = new THREE.PerspectiveCamera(42, w / h, 0.1, 200);
    this.camera.position.set(9, 5.8, 7.5);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 4;
    this.controls.maxDistance = 40;
    this.controls.maxPolarAngle = Math.PI * 0.49;
    this.controls.target.set(0, 1.25, 0);
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

    // Soft dawn sky (friendlier than near-black hangar)
    try {
      const skyCanvas = document.createElement("canvas");
      skyCanvas.width = 4;
      skyCanvas.height = 256;
      const sctx = skyCanvas.getContext("2d");
      const grad = sctx.createLinearGradient(0, 0, 0, 256);
      grad.addColorStop(0, "#c8d6e6");
      grad.addColorStop(0.4, "#9eafc0");
      grad.addColorStop(0.72, "#5a6572");
      grad.addColorStop(1, "#2e343c");
      sctx.fillStyle = grad;
      sctx.fillRect(0, 0, 4, 256);
      const skyTex = new THREE.CanvasTexture(skyCanvas);
      skyTex.colorSpace = THREE.SRGBColorSpace;
      this.scene.background = skyTex;
    } catch (_) {
      this.scene.background = new THREE.Color(0x8a9aab);
    }

    // Lights — brighter key/fill so solid zone colors read clearly (v0.6.1)
    const hemi = new THREE.HemisphereLight(0xeef3f8, 0x3a4048, 1.15);
    this.scene.add(hemi);
    const key = new THREE.DirectionalLight(0xfff7ee, 1.55);
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
    const fill = new THREE.DirectionalLight(0xb0c8e0, 0.72);
    fill.position.set(-8, 4, -6);
    this.scene.add(fill);
    const rim = new THREE.DirectionalLight(0xd8e4ee, 0.4);
    rim.position.set(-4, 6, 10);
    this.scene.add(rim);

    // Hangar floor — lighter concrete-ish
    const floorGeo = new THREE.CircleGeometry(18, 48);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x2a3038,
      metalness: 0.12,
      roughness: 0.9,
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -1.35;
    floor.receiveShadow = true;
    this.scene.add(floor);

    // Soft grid helper
    const grid = new THREE.GridHelper(24, 24, 0x4a5560, 0x343a42);
    grid.position.y = -1.34;
    grid.material.transparent = true;
    grid.material.opacity = 0.28;
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
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2.5));
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
    // Classic 3/4 front-side view — elevated so zoom keeps model off the bottom
    const targetY = family === "balloon" ? 1.6 : 1.25;
    this.camera.position.set(dist * 0.72, dist * 0.42 + targetY * 0.15, dist * 0.58);
    this.controls.target.set(0, targetY, 0);
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
    this._highlightedZone = null;
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
    cloneGeometriesDeep(model);
    cloneMaterialsDeep(model);
    fitAircraftToHangar(model, GLB_TARGET_SPAN);
    // Neutralize baked albedo / brand mats → blank airframe for zone paint
    prepareGlbForSkinning(model);
    craft.add(model);
    try { window.__SMB_CRAFT = craft; window.__SMB_PREVIEW = this; } catch (_) {}

    // Index materials by role (multi-mesh fallback) + prepare for face-zone paint
    const craftBox = new THREE.Box3().setFromObject(craft);
    this.glbMaterials = [];
    model.traverse((child) => {
      if (!child.isMesh || !child.material) return;
      if (child.userData && child.userData.skinHiddenLivery) return;
      if (child.visible === false) return;
      const mats = Array.isArray(child.material)
        ? child.material
        : [child.material];
      const meshBox = new THREE.Box3().setFromObject(child);
      const role = classifyMeshRole(child.name, meshBox, craftBox);
      mats.forEach((m) => {
        // Ensure no residual albedo map fights zone paint
        if (m.map) {
          try { m.map.dispose(); } catch (_) {}
          m.map = null;
        }
        m.color.set(0xffffff);
        this.glbMaterials.push({ mat: m, role, mesh: child });
      });
    });

    // Lift GLB to match procedural airliner framing (~0.55) — gear not glued to bottom
    craft.position.y = 0.55;
    this.root.add(craft);
    craft.updateMatrixWorld(true);

    // Hybrid parametric zone paint (body fragment shader + solid wing/engine mats)
    try {
      buildGlbShaderZonePaint(craft);
    } catch (zoneErr) {
      console.warn("GLB shader zone paint failed:", zoneErr);
    }

    let decal = { tex: null, regTex: null };
    try {
      decal = addTextDecals(craft, state);
    } catch (decalErr) {
      console.warn("Text decals failed (keeping GLB model):", decalErr);
      try {
        const line = document.getElementById("status-line");
        if (line) line.innerHTML = "GLB model OK; skin text temporarily unavailable: " + (decalErr && decalErr.message ? decalErr.message : decalErr);
      } catch (e) {}
    }
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
      try {
        const line = document.getElementById("status-line");
        if (line) {
          line.innerHTML = "<strong style=\"color:#ff8a7a\">GLB failed</strong> (" + url + "): " + (err && err.message ? err.message : err) + " — temporary simple shape.";
        }
        window.dispatchEvent(new CustomEvent("skinmybird-model-mode",{detail:{mode:"procedural",error:String(err)}}));
      } catch (e) {}
      if (token !== this._loadToken) return;
      this.buildProcedural(profile, state);
    }
  }

  applyPaint(state) {
    if (!this.ok || !this.root) return;
    this._lastPaintState = state;
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
      tx: state.textPosX,
      ty2: state.textPosY,
      tsc: state.textScale,
      tfl: state.textFlipLeft,
      tfr: state.textFlipRight,
      fl: state.flags,
      ct: (state.customTextures || []).map((t) => ({
        dLen: t.dataUrl ? t.dataUrl.length : 0,
        ready: !!(t._img && t._img.complete && t._img.naturalWidth),
        o: t.opacity, s: t.scale, x: t.posX, y: t.posY, p: t.placement, n: t.name,
      })),
      photo: state.soacraName || null,
      fam: family,
      mode: this.modelMode,
    });
    if (key === this._lastStateKey) return;
    this._lastStateKey = key;

    if (this.modelMode === "glb") {
      const colors = {
        fuselage: hexToThree(state.colors.fuselage || "#f2f4f7"),
        nose: hexToThree(state.colors.nose || state.colors.fuselage || "#f2f4f7"),
        belly: hexToThree(state.colors.belly || state.colors.fuselage || "#f2f4f7"),
        wings: hexToThree(state.colors.wings || "#1b2430"),
        winglet: hexToThree(state.colors.winglet || state.colors.wings || "#1b2430"),
        engines: hexToThree(state.colors.engines || "#1b2430"),
        tail: hexToThree(state.colors.tail || state.colors.fuselage || "#f2f4f7"),
        windowband: hexToThree(state.colors.windowband || state.colors.fuselage || "#f2f4f7"),
      };
      const craft = this.root.getObjectByName("aircraft");
      // Shader / solid zone materials (preferred). Geometry rebuild only on mount.
      let usedFaceZones = false;
      if (craft && craft.userData && craft.userData.zoneMaterials) {
        usedFaceZones = applyGlbZonePaint(craft, colors);
        this._applyHighlightVisuals();
      }
      if (!usedFaceZones) {
        // Multi-mesh fallback: per-mesh material role from classifyMeshRole
        this.glbMaterials.forEach(({ mat, role }) => {
          mat.vertexColors = false;
          mat.color.copy(colors[role] || colors.fuselage);
          if ("metalness" in mat) mat.metalness = Math.min(mat.metalness ?? 0.1, 0.12);
          if ("roughness" in mat) mat.roughness = Math.max(mat.roughness ?? 0.72, 0.7);
          mat.needsUpdate = true;
        });
      }
      // Rebuild mesh-projected decals (size/font/placement/text length)
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

    // Procedural path — fuselage UV paint + same mesh-projected decals as GLB
    if (this.fuselageTex && this.fuselageTex.userData.canvas) {
      paintFuselageCanvas(this.fuselageTex.userData.canvas, state, family);
      this.fuselageTex.needsUpdate = true;
    }

    const mats = this.mats;
    if (mats) {
      if (mats.nose)
        mats.nose.color.copy(hexToThree(state.colors.nose || state.colors.fuselage));
      if (mats.wings) mats.wings.color.copy(hexToThree(state.colors.wings));
      if (mats.winglet)
        mats.winglet.color.copy(
          hexToThree(state.colors.winglet || state.colors.wings || state.colors.tail)
        );
      if (mats.engines) mats.engines.color.copy(hexToThree(state.colors.engines));
      if (mats.enginesDark)
        mats.enginesDark.color.copy(hexToThree(shadeHex(state.colors.engines, -30)));
      if (mats.tail) mats.tail.color.copy(hexToThree(state.colors.tail));
      if (mats.stabilizer)
        mats.stabilizer.color.copy(
          hexToThree(state.colors.tail || state.colors.fuselage)
        );
    }

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
      try {
        const decal = addTextDecals(craft, state);
        this.decalTex = decal.tex;
        this.regTex = decal.regTex || null;
      } catch (err) {
        console.warn("Procedural decals failed:", err);
      }
    }
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

  /**
   * Highlight a paint zone on the GLB preview (Colors tab hover/focus).
   * @param {string|null} zoneName
   */
  setHighlightedZone(zoneName) {
    const next = zoneName || null;
    if (next === this._highlightedZone) {
      this._applyHighlightVisuals();
      return;
    }
    this._highlightedZone = next;
    this._applyHighlightVisuals();
  }

  _applyHighlightVisuals() {
    if (!this.root) return;
    const craft = this.root.getObjectByName("aircraft");
    const mats = craft && craft.userData && craft.userData.zoneMaterials;
    if (!mats) return;
    const hl = this._highlightedZone;
    const hlId = hl != null && ZONE_ID[hl] != null ? ZONE_ID[hl] : -1;

    const bodyMat = craft.userData.bodyZoneMaterial;
    if (bodyMat && bodyMat.userData && bodyMat.userData.zoneUniforms) {
      bodyMat.userData.zoneUniforms.uHighlightZone.value = hl ? hlId : -1;
      bodyMat.needsUpdate = true;
    }

    const solid = craft.userData.solidZoneMaterials || {};
    const seen = new Set();
    Object.keys(solid).forEach((name) => {
      const m = solid[name];
      if (!m || seen.has(m)) return;
      seen.add(m);
      const base = (m.userData && m.userData.baseColor) || m.color;
      if (hl && name === hl) {
        m.color.copy(base);
        if (m.emissive) m.emissive.setHex(0xff9a4a);
        m.emissiveIntensity = 0.45;
      } else if (hl) {
        m.color.copy(base).multiplyScalar(0.72);
        if (m.emissive) m.emissive.setHex(0x000000);
        m.emissiveIntensity = 0;
      } else {
        m.color.copy(base);
        if (m.emissive) m.emissive.setHex(0x000000);
        m.emissiveIntensity = 0;
      }
      m.needsUpdate = true;
    });
  }

  /**
   * Raycast pick at canvas client coords → paint zone name or null.
   */
  pickZoneAt(clientX, clientY) {
    if (!this.ok || !this.renderer || !this.camera || !this.root) return null;
    const craft = this.root.getObjectByName("aircraft");
    if (!craft) return null;
    const rect = this.canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    const ndc = new THREE.Vector2(
      ((clientX - rect.left) / rect.width) * 2 - 1,
      -((clientY - rect.top) / rect.height) * 2 + 1
    );
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(ndc, this.camera);
    const hits = raycaster.intersectObject(craft, true);
    for (const h of hits) {
      if (!h.object || !h.object.isMesh) continue;
      if (h.object.userData && h.object.userData.isTextDecal) continue;
      if (h.object.userData && h.object.userData.zoneSplitParent) continue;
      // Body shader meshes: classify hit point in craft space (smooth bands)
      if (h.object.userData && h.object.userData.bodyZoneShaded && craft.userData.zoneCtx && h.point) {
        const local = craftLocalPoint(craft, h.point);
        return zoneNameFromId(classifyPoint(local.x, local.y, local.z, craft.userData.zoneCtx));
      }
      if (h.object.userData && h.object.userData.paintZone) {
        return h.object.userData.paintZone;
      }
    }
    return null;
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

    // Soft pulse on highlighted zone
    if (this._highlightedZone && this.modelMode === "glb") {
      const craft = this.root && this.root.getObjectByName("aircraft");
      const mats = craft && craft.userData && craft.userData.zoneMaterials;
      const m = mats && mats[this._highlightedZone];
      if (m) {
        const pulse = 0.32 + 0.22 * Math.sin(performance.now() * 0.005);
        m.emissiveIntensity = pulse;
      }
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
