import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Grid, Html, Line, TransformControls } from "@react-three/drei";
import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { toCreasedNormals } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import * as THREE from "three";
import { beamMaterial, holoMaterial, holoSweep, holoTime } from "./holo";
import { useStore } from "../store";
import { objects, view } from "./registry";
import { Nav } from "./nav";
import { explodeOffset } from "./modal";

const RAD = Math.PI / 180;
const AXI = { x: 0, y: 1, z: 2 };
const clipPlane = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);

function useGeometry(mesh) {
  const g = useMemo(() => {
    if (!mesh) return null;
    const src = new THREE.BufferGeometry();
    src.setAttribute("position", new THREE.Float32BufferAttribute(mesh.v, 3));
    src.setIndex(mesh.f);
    if (mesh.n) {
      // a CAD part: normals come from the B-rep surfaces (smooth NURBS stays smooth, real edges stay sharp)
      src.setAttribute("normal", new THREE.Float32BufferAttribute(mesh.n, 3));
      src.computeBoundingBox();
      return src;
    }
    // smooth across gentle edges, sharp across creases > 35 deg: an extruded plate keeps crisp rims, a hull its curves
    const g = toCreasedNormals(src, 35 * RAD);
    src.dispose();
    g.computeBoundingBox();
    return g;
  }, [mesh]);
  // free the GPU buffers of the old geometry: without this every rebuild of a 100-part model leaked them until
  // the browser dropped the WebGL context (the black viewport)
  useEffect(() => () => g?.dispose(), [g]);
  return g;
}

// Outline edges; a model rebuilt from a drawing carries the drawing's own lines (doors, windows, intakes) instead.
function EdgeLines({ geom, lines, color, opacity, clip }) {
  const edges = useMemo(() => {
    if (!lines) return new THREE.EdgesGeometry(geom, 28);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(lines, 3));
    return g;
  }, [geom, lines]);
  useEffect(() => () => edges.dispose(), [edges]);
  return (
    <lineSegments geometry={edges} raycast={() => null} userData={{ edge: true }}>
      <lineBasicMaterial color={color} transparent opacity={opacity} depthWrite={false} clippingPlanes={clip} />
    </lineSegments>
  );
}

// Hatched cut face (CAD section convention): the cap is the B-rep face the Boolean section left on the plane.
const hatchMaterial = (fill) => new THREE.ShaderMaterial({
  uniforms: { uFill: { value: new THREE.Color(fill) }, uLine: { value: new THREE.Color("#0b1220") } },
  vertexShader: "void main(){ gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
  fragmentShader: "uniform vec3 uFill; uniform vec3 uLine; void main(){ float d = mod(gl_FragCoord.x + gl_FragCoord.y, 10.0); gl_FragColor = vec4(d < 1.8 ? uLine : uFill, 1.0); }",
  side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
});

function Cap({ cap, color }) {
  const geom = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(cap.cap, 3));
    return g;
  }, [cap]);
  const mat = useMemo(() => hatchMaterial(new THREE.Color(color || "#cfd8e4").lerp(new THREE.Color("#ff4fd8"), 0.35)), [color]);
  useEffect(() => () => { geom.dispose(); mat.dispose(); }, [geom, mat]);
  return <mesh geometry={geom} material={mat} raycast={() => null} renderOrder={2} />;
}

const REGION_DEFAULT = { glass: "#1d2b3a", light: "#dfe7ef" };      // as the CAD document's materials

function PartNode({ part, childrenOf }) {
  const ref = useRef();
  const mesh = useStore((s) => s.meshes[part.id]);
  const isSel = useStore((s) => s.selection.includes(part.id));
  const isActive = useStore((s) => s.state?.selected === part.id);
  const shading = useStore((s) => s.shading);
  const xray = useStore((s) => s.view.xray);
  const section = useStore((s) => !!s.view.section);
  const isolate = useStore((s) => s.view.isolate);
  const explode = useStore((s) => s.view.explode);
  const off = useStore((s) => s.offsets[part.id]);
  const cap = useStore((s) => (s.view.section ? s.caps[part.id] : null));
  const geom = useGeometry(mesh);
  // named regions of a CAD body (glass = windows, light = lamps): their own colour per triangle, the rest the part's
  const regionKey = mesh?.r ? JSON.stringify([part.color, part.region_colors, part.params?.region_names]) : null;
  useEffect(() => {
    if (!geom || !mesh?.r) return;
    const names = part.params?.region_names || [];
    const base = new THREE.Color(part.color || "#cfd8e4");
    const cols = names.map((n) => new THREE.Color(part.region_colors?.[n] || REGION_DEFAULT[n] || part.color || "#cfd8e4"));
    const F = mesh.f, n = geom.attributes.position.count, c = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) base.toArray(c, i * 3);
    for (let t = 0; t < mesh.r.length; t++) {
      const k = mesh.r[t];
      if (!k || !cols[k - 1]) continue;
      for (let j = 0; j < 3; j++) cols[k - 1].toArray(c, F[t * 3 + j] * 3);
    }
    geom.setAttribute("color", new THREE.Float32BufferAttribute(c, 3));
  }, [geom, regionKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    objects.set(part.id, ref.current);
    return () => objects.delete(part.id);
  }, [part.id]);

  // explode: animate toward the exploded position
  const target = useMemo(() => {
    const o = off || [0, 0, 0];
    return new THREE.Vector3(...part.position.map((v, i) => v + explode * o[i]));
  }, [part.position, explode, off]);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { ref.current.position.copy(target); first.current = false; }
  }, [target]);
  useFrame((st) => {
    const o = ref.current;
    if (!o || useStore.getState().modal || o.userData.dragging) return;
    if (o.position.distanceToSquared(target) > 1e-4) { o.position.lerp(target, 0.18); st.invalidate(); }   // keep animating
    else o.position.copy(target);
  });

  const kids = childrenOf[part.id] || [];
  const hiddenByIsolate = isolate.length && !part._inIsolate;
  const clip = section ? [clipPlane] : null;
  const ghost = xray && !isSel;
  // in the hologram look the selection turns amber (Iron Man style) so it stands out from the cyan light
  const sel = shading === "holo" ? (isActive ? "#ffd58a" : isSel ? "#ffb347" : null) : isActive ? "#8ff3ff" : isSel ? "#3fc6ff" : null;

  const holo = useMemo(() => shading === "holo" ? holoMaterial() : null, [shading]);
  useEffect(() => () => holo?.dispose(), [holo]);
  if (holo) {
    holo.uniforms.uColor.value.set(sel || (part.type === "mesh" ? "#4fe3ff" : "#38d9ff"));
    holo.uniforms.uOpacity.value = ghost ? 0.25 : sel ? 1.25 : 1;
    holo.clippingPlanes = clip;
  }

  let material;
  if (shading === "wire")
    material = <meshBasicMaterial color={sel || "#7fb6d6"} wireframe transparent opacity={sel ? 0.9 : 0.45} clippingPlanes={clip} />;
  else if (holo)
    material = <primitive object={holo} attach="material" />;
  else
    material = <meshStandardMaterial vertexColors={!!mesh?.r} color={mesh?.r ? "#ffffff" : part.color || (part.type === "mesh" ? "#b9c4d6" : "#cfd8e4")}
      metalness={part.material === "glass" ? 0.9 : 0.62} roughness={part.material === "glass" ? 0.06 : 0.34} envMapIntensity={part.material === "glass" ? 1.1 : 0.55}
      emissive={sel || "#000000"} emissiveIntensity={sel ? 0.22 : 0} transparent={ghost} opacity={ghost ? 0.06 : 1}
      depthWrite={!ghost} clippingPlanes={clip} polygonOffset={!!mesh?.l} polygonOffsetFactor={1.5} polygonOffsetUnits={2} />;

  return (
    <group ref={ref} name={part.id}
      rotation={new THREE.Euler(part.rotation[0] * RAD, part.rotation[1] * RAD, part.rotation[2] * RAD, "ZYX")}
      scale={part.scale} visible={part.visible !== false && !hiddenByIsolate}>
      {geom && (
        <>
          {mesh.l && shading === "holo" && !ghost && (
            // depth only: the see-through hologram still hides drawing lines on the far side of the body
            <mesh geometry={geom} renderOrder={-1} raycast={() => null}>
              <meshBasicMaterial colorWrite={false} polygonOffset polygonOffsetFactor={3} polygonOffsetUnits={4} clippingPlanes={clip} />
            </mesh>
          )}
          <mesh geometry={geom} userData={{ part: part.id }}>
            {material}
          </mesh>
          {cap && shading !== "wire" && <Cap cap={cap} color={part.color} />}
          {section && !mesh.brep && shading !== "wire" && (
            <mesh geometry={geom} raycast={() => null}>
              <meshBasicMaterial color="#ff4fd8" side={THREE.BackSide} clippingPlanes={clip} transparent opacity={shading === "holo" ? 0.12 : ghost ? 0.2 : 0.6} depthWrite={shading !== "holo"} />
            </mesh>
          )}
          {shading !== "wire" && (
            <EdgeLines geom={geom} lines={mesh.l} clip={clip}
              color={sel || (shading === "holo" ? "#8ff0ff" : mesh.l ? "#1a2533" : "#e6f6ff")}
              opacity={mesh.l ? (ghost ? 0.3 : 0.85) : sel ? 0.95 : shading === "holo" ? (ghost ? 0.25 : 0.6) : ghost ? 0.4 : 0.12} />
          )}
        </>
      )}
      {kids.map((k) => <PartNode key={k.id} part={k} childrenOf={childrenOf} />)}
    </group>
  );
}

function Parts() {
  const parts = useStore((s) => s.state?.parts || []);
  const isolate = useStore((s) => s.view.isolate);
  const childrenOf = useMemo(() => {
    // mark parts inside the isolated set (the parts, their descendants and ancestors)
    const by = Object.fromEntries(parts.map((p) => [p.id, p]));
    const keep = new Set(isolate.filter((i) => by[i]));
    let grew = true;
    while (grew) { grew = false; for (const p of parts) if (keep.has(p.parent) && !keep.has(p.id)) { keep.add(p.id); grew = true; } }
    for (const i of [...keep]) { let q = by[i]?.parent; while (q && by[q]) { keep.add(q); q = by[q].parent; } }
    const m = {};
    for (const p of parts) (m[p.parent && by[p.parent] ? p.parent : "root"] ||= []).push({ ...p, _inIsolate: keep.has(p.id) });
    return m;
  }, [parts, isolate]);
  return (childrenOf.root || []).map((p) => <PartNode key={p.id} part={p} childrenOf={childrenOf} />);
}

// scene bounds of everything that is shown (world mm)
export function sceneBox(ids) {
  const box = new THREE.Box3();
  for (const [id, o] of objects) {
    if (!o || (ids && !ids.includes(id))) continue;
    o.updateWorldMatrix(true, true);
    o.traverse((c) => { if (c.isMesh && c.visible && c.geometry?.boundingBox && c.userData.part) box.union(c.geometry.boundingBox.clone().applyMatrix4(c.matrixWorld)); });
  }
  return box;
}

function SectionPlane() {
  const v = useStore((s) => s.view);
  const version = useStore((s) => s.meshVersion);
  const [box, setBox] = useState(null);
  useEffect(() => { const t = setTimeout(() => setBox(sceneBox()), 60); return () => clearTimeout(t); }, [version, v.explode, v.section]);
  const gl = useThree((s) => s.gl);
  useEffect(() => { gl.localClippingEnabled = true; }, [gl]);
  useEffect(() => {
    if (!v.section) return;
    const n = new THREE.Vector3(); n.setComponent(AXI[v.section], v.section_flip ? 1 : -1);
    clipPlane.set(n, v.section_flip ? -v.section_mm : v.section_mm);
  }, [v.section, v.section_mm, v.section_flip]);
  if (!v.section || !box || box.isEmpty()) return null;
  const c = box.getCenter(new THREE.Vector3()), sz = box.getSize(new THREE.Vector3()).multiplyScalar(1.25).addScalar(30);
  const k = AXI[v.section];
  const pos = c.toArray(); pos[k] = v.section_mm;
  const dims = [0, 1, 2].filter((i) => i !== k).map((i) => sz.getComponent(i));
  const rot = v.section === "x" ? [0, Math.PI / 2, 0] : v.section === "y" ? [Math.PI / 2, 0, 0] : [0, 0, 0];
  const [w, h] = v.section === "x" ? [dims[1], dims[0]] : dims;
  const edge = [[-w / 2, -h / 2, 0], [w / 2, -h / 2, 0], [w / 2, h / 2, 0], [-w / 2, h / 2, 0], [-w / 2, -h / 2, 0]];
  return (
    <group position={pos} rotation={rot}>
      <mesh raycast={() => null}>
        <planeGeometry args={[w, h]} />
        <meshBasicMaterial color="#ff4fd8" transparent opacity={0.05} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <Line points={edge} color="#ff4fd8" lineWidth={1.2} transparent opacity={0.8} />
      <Html wrapperClass="r3f-label" position={[w / 2, h / 2, 0]} zIndexRange={[15, 0]} style={{ pointerEvents: "none" }}>
        <div className="whitespace-nowrap rounded-md border border-fuchsia-400/40 bg-black/60 px-2 py-0.5 font-mono text-[10.5px] text-fuchsia-200">
          SECTION {v.section.toUpperCase()} = {v.section_mm.toFixed(1)} mm
        </div>
      </Html>
    </group>
  );
}

// Leader-line labels for the parts the B-rep section cuts (largest cut faces first), above and below the model.
function SectionLabels() {
  const caps = useStore((s) => s.caps);
  const v = useStore((s) => s.view);
  const names = useStore((s) => s.state?.parts);
  const version = useStore((s) => s.meshVersion);
  const [items, setItems] = useState([]);
  useEffect(() => {
    if (!v.section || !Object.keys(caps).length) return setItems([]);
    const t = setTimeout(() => {
      const box = sceneBox();
      if (box.isEmpty()) return setItems([]);
      const by = Object.fromEntries((names || []).map((p) => [p.id, p.name]));
      const list = Object.entries(caps).sort((a, b) => b[1].area_mm2 - a[1].area_mm2).slice(0, 12).map(([id, c]) => {
        const o = objects.get(id);
        if (!o) return null;
        o.updateWorldMatrix(true, false);
        const P = c.cap, n = P.length / 3, cen = new THREE.Vector3();
        for (let i = 0; i < P.length; i += 3) cen.x += P[i] / n, cen.y += P[i + 1] / n, cen.z += P[i + 2] / n;
        return { id, name: by[id] || id, area: c.area_mm2, at: cen.applyMatrix4(o.matrixWorld) };
      }).filter(Boolean);
      // callouts as in an illustrated cutaway: upper half of the cut above the model, lower half below, each row
      // spread evenly across the model's width in the order of the parts, so leader lines fan out and never cross
      const k = AXI[v.section] === 0 ? 1 : 0;
      const span = box.max.z - box.min.z, midZ = (box.min.z + box.max.z) / 2;
      const lo = box.min.getComponent(k), hi = box.max.getComponent(k), w = hi - lo;
      const rows = [list.filter((it) => it.at.z >= midZ), list.filter((it) => it.at.z < midZ)];
      if (!rows[0].length || !rows[1].length) { const all = [...rows[0], ...rows[1]]; rows[0] = all.filter((_, i) => i % 2 === 0); rows[1] = all.filter((_, i) => i % 2); }
      setItems(rows.flatMap((row, r) => row.sort((a, b) => a.at.getComponent(k) - b.at.getComponent(k)).map((it, i) => {
        const tip = it.at.clone();
        tip.setComponent(k, lo - 0.1 * w + ((i + 0.5) / row.length) * 1.2 * w);
        tip.z = r === 0 ? box.max.z + 0.35 * span + (i % 2) * 0.16 * span : box.min.z - 0.35 * span - (i % 2) * 0.16 * span;
        return { ...it, tip, up: r === 0 };
      })));
    }, 200);
    return () => clearTimeout(t);
  }, [caps, v.section, v.section_mm, v.explode, version, names]);
  return items.map((it) => (
    <group key={it.id}>
      <Line points={[it.at.toArray(), it.tip.toArray()]} color="#e8eef6" lineWidth={1} transparent opacity={0.85} depthTest={false} />
      <mesh position={it.at} raycast={() => null}><sphereGeometry args={[0.9, 10, 10]} /><meshBasicMaterial color="#ffffff" depthTest={false} /></mesh>
      <Html wrapperClass="r3f-label" position={it.tip} center zIndexRange={[14, 0]} style={{ pointerEvents: "none" }}>
        <div className={`whitespace-nowrap rounded border border-white/25 bg-black/70 px-1.5 py-0.5 font-display text-[11px] font-semibold uppercase tracking-wide text-white ${it.up ? "-translate-y-2" : "translate-y-2"}`}>
          {it.name}<span className="ml-1 font-mono text-[9.5px] font-normal normal-case text-fuchsia-200">{it.area.toFixed(0)} mm²</span></div>
      </Html>
    </group>
  ));
}

// The AETHER Desk panel: a lit glass slab with corner brackets and the light volume it projects into (the sharp zone above the panel).
function Panel() {
  const desk = useStore((s) => s.state?.desk);
  const holo = useStore((s) => s.results.hologram?.img);
  const tex = useMemo(() => {
    if (!holo) return null;
    const t = new THREE.TextureLoader().load(holo);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [holo]);
  const beam = useMemo(() => beamMaterial(), []);
  const scan = useRef();
  useFrame(() => { if (scan.current) scan.current.position.z = 4 + ((holoTime.value * 22) % 96); });
  if (!desk) return null;
  const w = desk.panel_w_mm, h = desk.panel_h_mm, Z = 87;   // 80 % sharp zone top for the seated eye (desk_score sharp_zone_mm)
  const corners = [[-w / 2, -h / 2, 0], [w / 2, -h / 2, 0], [w / 2, h / 2, 0], [-w / 2, h / 2, 0], [-w / 2, -h / 2, 0]];
  const L = 34;
  const brackets = [[-1, -1], [1, -1], [1, 1], [-1, 1]].flatMap(([sx, sy]) => {
    const x = sx * w / 2, y = sy * h / 2;
    return [[x - sx * L, y, 0.2], [x, y, 0.2], [x, y, 0.2], [x, y - sy * L, 0.2]];
  });
  const walls = [[0, -h / 2, w, 0], [0, h / 2, w, 0], [-w / 2, 0, h, Math.PI / 2], [w / 2, 0, h, Math.PI / 2]];
  return (
    <group>
      <mesh position={[0, 0, -0.6]} raycast={() => null}>
        <planeGeometry args={[w, h]} />
        <meshBasicMaterial color={tex ? "#2c4a5c" : "#04101a"} map={tex} transparent opacity={tex ? 0.3 : 0.85} />
      </mesh>
      <Line points={corners} color="#2a6f8a" lineWidth={1} transparent opacity={0.7} />
      <Line points={brackets} segments color="#9ff3ff" lineWidth={2.2} />
      {walls.map(([x, y, len, rz], i) => (
        <mesh key={i} position={[x, y, Z / 2]} rotation={[Math.PI / 2, rz, 0]} material={beam} raycast={() => null}>
          <planeGeometry args={[len, Z]} />
        </mesh>
      ))}
      <group ref={scan}>
        <Line points={corners.map(([x, y]) => [x * 0.995, y * 0.995, 0])} color="#5fe1ff" lineWidth={1} transparent opacity={0.35} />
      </group>
      <Line points={corners.map(([x, y]) => [x, y, Z])} color="#5fe1ff" lineWidth={0.7} dashed dashSize={8} gapSize={7} transparent opacity={0.28} />
      <Html wrapperClass="r3f-label" position={[w / 2, h / 2, Z]} zIndexRange={[15, 0]} style={{ pointerEvents: "none" }}>
        <div className="hud-tag">SHARP ZONE · ≈ +87 mm (seated eye, 80 %)</div>
      </Html>
      <Html wrapperClass="r3f-label" position={[-w / 2, -h / 2, 0]} zIndexRange={[15, 0]} style={{ pointerEvents: "none" }}>
        <div className="hud-tag -translate-x-full">AETHER DESK · 27″ · 598 × 336</div>
      </Html>
    </group>
  );
}

function Floor() {
  return (
    <group>
      <Grid rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -1.5]} infiniteGrid cellSize={10} sectionSize={100}
        cellColor="#0c1a26" sectionColor="#16374c" cellThickness={0.6} sectionThickness={1} fadeDistance={9000} fadeStrength={3} />
      <Line points={[[-1000, 0, -1.2], [1000, 0, -1.2]]} color="#b8435a" lineWidth={1} transparent opacity={0.45} />
      <Line points={[[0, -1000, -1.2], [0, 1000, -1.2]]} color="#5b9a3a" lineWidth={1} transparent opacity={0.45} />
    </group>
  );
}

// Time + the scan band that rises through the design in hologram shading.
function HoloClock() {
  const box = useRef(null);
  const version = useStore((s) => s.meshVersion);
  useEffect(() => { const t = setTimeout(() => { box.current = sceneBox(); }, 300); return () => clearTimeout(t); }, [version]);
  useFrame((_, dt) => {
    holoTime.value += dt;
    const b = box.current;
    if (b && !b.isEmpty()) {
      const span = b.max.z - b.min.z + 30;
      holoSweep.value = b.min.z - 15 + ((holoTime.value * 0.28) % 1.4) * span;
    }
  });
  return null;
}

function Env() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pm = new THREE.PMREMGenerator(gl);
    const env = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = env;
    return () => { scene.environment = null; env.dispose(); pm.dispose(); };
  }, [gl, scene]);
  return null;
}

// Iron Man-style callout: a leader line from the active part to a label with its name and size.
function Callout() {
  const id = useStore((s) => s.state?.selected);
  const part = useStore((s) => s.state?.parts.find((p) => p.id === id));
  const version = useStore((s) => s.meshVersion);
  const modal = useStore((s) => s.modal);
  const [box, setBox] = useState(null);
  useEffect(() => {
    if (!id) return setBox(null);
    const t = setTimeout(() => setBox(sceneBox([id])), 120);
    return () => clearTimeout(t);
  }, [id, version, part?.position, part?.scale, part?.rotation]);
  if (!part || !box || box.isEmpty() || modal) return null;
  const s = box.getSize(new THREE.Vector3());
  return (
    <Html wrapperClass="r3f-label" position={[(box.min.x + box.max.x) / 2, (box.min.y + box.max.y) / 2, box.max.z]} zIndexRange={[16, 0]} style={{ pointerEvents: "none" }}>
      <div className="callout">
        <svg width="64" height="44" className="absolute bottom-0 left-0 overflow-visible"><path d="M0 44 L26 4 L64 4" fill="none" stroke="#8ff3ff" strokeWidth="1.2" /><circle cx="0" cy="44" r="3" fill="#8ff3ff" /></svg>
        <div className="callout-card">
          <div className="font-display text-[13px] font-semibold text-white">{part.name}</div>
          <div className="font-mono text-[10px] text-cyan-glow/90">{part.type.toUpperCase()} · {s.x.toFixed(1)} × {s.y.toFixed(1)} × {s.z.toFixed(1)} mm</div>
        </div>
      </div>
    </Html>
  );
}

function EyeAndWindow() {
  const eye = useStore((s) => s.state?.eye);
  const desk = useStore((s) => s.state?.desk);
  if (!eye || !desk) return null;
  const w = desk.panel_w_mm / 2, h = desk.panel_h_mm / 2;
  const segs = [[-w, -h], [w, -h], [w, h], [-w, h]].flatMap(([x, y]) => [eye, [x, y, 0]]);
  return (
    <group>
      <mesh position={eye} raycast={() => null}><sphereGeometry args={[6, 24, 24]} /><meshBasicMaterial color="#c4b5fd" /></mesh>
      <Line points={segs} segments color="#a78bfa" lineWidth={0.6} transparent opacity={0.18} />
    </group>
  );
}

function Cursor3D() {
  const c = useStore((s) => s.cursor3d);
  const ring = useMemo(() => Array.from({ length: 33 }, (_, i) => [Math.cos(i / 32 * 2 * Math.PI) * 6, Math.sin(i / 32 * 2 * Math.PI) * 6, 0]), []);
  return (
    <group position={c}>
      <Line points={ring} color="#ff5d73" lineWidth={1.4} dashed dashSize={2.4} gapSize={2.4} />
      <Line points={[[-11, 0, 0], [-4, 0, 0], [4, 0, 0], [11, 0, 0], [0, -11, 0], [0, -4, 0], [0, 4, 0], [0, 11, 0]]} segments color="#e5e7eb" lineWidth={1} />
    </group>
  );
}

function Measure() {
  const m = useStore((s) => s.measure);
  if (!m?.a) return null;
  const b = m.b || m.a;
  const d = new THREE.Vector3(...m.a).distanceTo(new THREE.Vector3(...b));
  const mid = m.a.map((v, i) => (v + b[i]) / 2);
  return (
    <group>
      <mesh position={m.a}><sphereGeometry args={[1.6, 12, 12]} /><meshBasicMaterial color="#fde68a" depthTest={false} /></mesh>
      {m.b && <>
        <mesh position={m.b}><sphereGeometry args={[1.6, 12, 12]} /><meshBasicMaterial color="#fde68a" depthTest={false} /></mesh>
        <Line points={[m.a, m.b]} color="#fde68a" lineWidth={1.6} depthTest={false} />
        <Html wrapperClass="r3f-label" position={mid} center zIndexRange={[15, 0]} style={{ pointerEvents: "none" }}>
          <div className="whitespace-nowrap rounded-md border border-amber-200/40 bg-black/70 px-2 py-0.5 font-mono text-[11px] text-amber-100">{d.toFixed(2)} mm</div>
        </Html>
      </>}
    </group>
  );
}

function HandJoints() {
  const frame = useStore((s) => s.handFrame);
  const mode = useStore((s) => s.mode);
  if (mode !== "hand" || !frame) return null;
  return frame.world.map((hand, i) => (
    <group key={i}>
      {hand.map((p, j) => (
        <mesh key={j} position={p} raycast={() => null}><sphereGeometry args={[j % 4 === 0 ? 3.6 : 2.6, 12, 12]} />
          <meshBasicMaterial color={frame.pinch[i] ? "#ff4fd8" : "#5fe1ff"} transparent opacity={0.8} /></mesh>
      ))}
    </group>
  ));
}

function Gizmo() {
  const selected = useStore((s) => s.state?.selected);
  const count = useStore((s) => s.selection.length);
  const mode = useStore((s) => s.mode);
  const tool = useStore((s) => s.activeTool);
  const modal = useStore((s) => s.modal);
  const ref = useRef();
  useEffect(() => { view.gizmo = ref.current; return () => { view.gizmo = null; }; });
  const obj = selected ? objects.get(selected) : null;
  if (!obj || mode !== "laptop" || modal || count !== 1 || !["move", "rotate", "scale"].includes(tool)) return null;
  return (
    <TransformControls ref={ref} object={obj} mode={tool === "move" ? "translate" : tool} size={0.75}
      onMouseDown={() => { obj.userData.dragging = true; }}
      onMouseUp={() => {
        obj.userData.dragging = false;
        const r = obj.rotation, st = useStore.getState();
        st.commitParts(st.state.parts.map((p) => p.id !== selected ? p : { ...p,
          position: obj.position.clone().sub(explodeOffset(selected)).toArray().map((v) => +v.toFixed(2)),
          rotation: [r.x, r.y, r.z].map((v) => +(v / RAD).toFixed(2)),
          scale: obj.scale.toArray().map((v) => +v.toFixed(3)) }));
      }} />
  );
}

// frame the design when it first loads and whenever a new assembly replaces the scene
function AutoFrame() {
  const roots = useStore((s) => (s.state?.parts || []).filter((p) => !p.parent).map((p) => p.id).join());
  const ready = useStore((s) => s.meshVersion >= 0);
  const framed = useRef("");
  useEffect(() => {
    if (!ready || !roots || framed.current === roots) return;
    // the parts' geometry is built a moment after the meshes arrive (a big model takes longer): try every 100 ms
    // until there is something to frame (one try at 250 ms framed an empty box after a reload and gave up)
    let tries = 0;
    const t = setInterval(() => {
      const b = sceneBox();
      if (view.nav && !b.isEmpty()) { clearInterval(t); view.nav.frame(b); framed.current = roots; }
      else if (++tries > 40) clearInterval(t);
    }, 100);
    return () => clearInterval(t);
  }, [roots, ready]);
  return null;
}

function Rig() {
  const { gl, set, size, scene, get } = useThree();
  const cams = useMemo(() => {
    const p = new THREE.PerspectiveCamera(35, 1, 1, 8000);
    const o = new THREE.OrthographicCamera(-1, 1, 1, -1, -5000, 5000);
    return { p, o };
  }, []);
  useEffect(() => {
    const nav = new Nav(cams.p, cams.o, gl.domElement, (cam) => { set({ camera: cam }); view.camera = cam; });
    set({ camera: cams.p });
    Object.assign(view, { camera: cams.p, dom: gl.domElement, nav, scene });
    // While the camera moves, what costs most on an integrated GPU is not the model but what the browser redraws
    // around it: edge outlines, floating labels, CSS animations and the vignette are left out for the move and come
    // back 300 ms after it stops (orbiting the 122-part machine on Intel UHD: 49 -> 65 fps, worst frame 35 ms).
    // Not done, measured: a lower render resolution (no gain, canvas resizes), dropping the panels' blur (+7 fps but
    // a 55-76 ms stall at every start of a move).
    // edge outlines are hidden while the camera moves and drawn again 300 ms after it stops (+15 % frame rate
    // orbiting the 122-part machine on an integrated GPU), as CAD viewers do
    let moving = false, settle = 0;
    const edges = (on) => {
      scene.traverse((o) => { if (o.userData.edge) o.visible = on; });
      document.documentElement.classList.toggle("view-moving", !on);      // labels, animations, vignette (index.css)
    };
    const off = nav.onChange(() => {
      if (!moving) { moving = true; edges(false); }
      clearTimeout(settle);
      settle = setTimeout(() => { moving = false; edges(true); get().invalidate(); }, 300);
    });
    return () => { off(); nav.dispose(); };
  }, [gl, cams, set, scene, get]);
  useEffect(() => {
    cams.p.aspect = size.width / size.height; cams.p.updateProjectionMatrix();
    Object.assign(cams.o, { left: -size.width / 2, right: size.width / 2, top: size.height / 2, bottom: -size.height / 2 });
    view.nav?.apply();
  }, [size, cams]);
  // The panels cover the edges of the canvas: centre the view (and framing) in the free area between them, as
  // design apps do, so a model is never hidden behind the chat or a side panel.
  useEffect(() => {
    let last = "";
    const tick = () => {
      const W = gl.domElement.clientWidth, H = gl.domElement.clientHeight;
      if (!W || !H) return;
      let l = 0, r = 0, b = 0, t = 56;
      for (const el of document.querySelectorAll("section[data-dock]")) {
        if (el.dataset.mode === "max") continue;
        const q = el.getBoundingClientRect();
        if (el.dataset.dock === "left") l = Math.max(l, q.right);
        else if (el.dataset.dock === "right") r = Math.max(r, W - q.left);
        else if (el.dataset.dock === "bottom") b = Math.max(b, H - q.top);
        else if (el.dataset.dock === "top") t = Math.max(t, q.bottom);      // the Explain step player
      }
      l = Math.min(l, W * 0.45); r = Math.min(r, W * 0.45); b = Math.min(b, H * 0.6); t = Math.min(t, H * 0.5);
      const key = [W, H, l, r, b, t].map(Math.round).join(",");
      if (key === last) return;
      last = key;
      const ox = (l - r) / 2, oy = (t - b) / 2;
      for (const cam of [cams.p, cams.o]) { cam.setViewOffset(W, H, -ox, -oy, W, H); cam.updateProjectionMatrix(); }
      if (view.nav) view.nav.safe = { sx: (W - l - r) / W, sy: (H - t - b) / H };
    };
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [gl, cams]);
  return null;
}

// bloom tuned per shading: strong on the hologram look, only the hottest highlights on metal
function Glow() {
  const shading = useStore((s) => s.shading);
  return shading === "holo"
    ? <Bloom mipmapBlur levels={5} resolutionScale={0.5} intensity={0.7} luminanceThreshold={0.3} luminanceSmoothing={0.25} radius={0.6} />
    : <Bloom mipmapBlur intensity={0.5} luminanceThreshold={0.85} luminanceSmoothing={0.1} radius={0.6} />;
}

// Render on demand (outside the animated hologram look): a frame is drawn when something changes, not 60 times a
// second while nothing does. Anything can ask: a store change, pointer / wheel / key input (G/R/S moves and hand mode
// move objects outside React), a camera change.
function Invalidator() {
  const invalidate = useThree((s) => s.invalidate);
  const holo = useStore((s) => s.shading === "holo");
  useEffect(() => {                                  // the hologram look animates (scan band): 30 frames a second is
    if (!holo) return;                               // enough for it, and leaves the GPU to the rest of the page
    const t = setInterval(() => invalidate(), 1000 / 30);
    return () => clearInterval(t);
  }, [holo, invalidate]);
  useEffect(() => {
    const unsub = useStore.subscribe(() => invalidate());
    const ev = ["pointermove", "pointerdown", "pointerup", "wheel", "keydown", "keyup", "resize"];
    const f = () => invalidate();
    ev.forEach((e) => addEventListener(e, f, { passive: true }));
    let off = null;
    const t = setInterval(() => { if (view.nav && !off) { off = view.nav.onChange(f); clearInterval(t); } }, 200);
    return () => { unsub(); ev.forEach((e) => removeEventListener(e, f)); off?.(); clearInterval(t); };
  }, [invalidate]);
  return null;
}

export default function Viewport() {
  const shading = useStore((s) => s.shading);
  // if the GPU still drops the context (driver reset, other tabs), rebuild the 3D view instead of staying black
  const [gen, setGen] = useState(0);
  const onCreated = ({ gl }) => {
    const c = gl.domElement;
    c.addEventListener("webglcontextlost", (e) => { e.preventDefault(); setTimeout(() => setGen((g) => g + 1), 300); }, { once: true });
  };
  return (<>
    <Canvas key={gen} onCreated={onCreated} frameloop="demand" dpr={[1, 1.25]} gl={{ antialias: true, alpha: false, localClippingEnabled: true, powerPreference: "high-performance" }} raycaster={{ params: { Line: { threshold: 0 } } }}
      onContextMenu={(e) => e.preventDefault()}>
      <Rig />
      <Invalidator />
      <AutoFrame />
      <color attach="background" args={["#04060b"]} />
      <Env />
      <HoloClock />
      <hemisphereLight args={["#cfe9ff", "#0b0f18", 0.9]} />
      <directionalLight position={[300, -260, 700]} intensity={2.0} />
      <directionalLight position={[-400, 300, 200]} intensity={0.6} color="#9fdcff" />
      <pointLight position={[260, 220, 180]} intensity={30000} color="#ff4fd8" />
      <Floor />
      <Panel />
      <EyeAndWindow />
      <Parts />
      <SectionPlane />
      <SectionLabels />
      <Cursor3D />
      <Measure />
      <HandJoints />
      <Gizmo />
      <Callout />
      {shading === "holo" && (                            // the glow is the hologram look; solid / wire skip the passes
        <EffectComposer multisampling={0} disableNormalPass>
          <Glow />
          <Vignette offset={0.28} darkness={0.75} />
        </EffectComposer>)}
    </Canvas>
  </>);
}
