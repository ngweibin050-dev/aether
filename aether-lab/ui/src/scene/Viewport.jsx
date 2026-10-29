import { useEffect, useMemo, useRef } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { Edges, Line, OrbitControls, TransformControls } from "@react-three/drei";
import * as THREE from "three";
import { useStore } from "../store";
import { objects } from "./registry";

const RAD = Math.PI / 180;

function useGeometry(mesh) {
  return useMemo(() => {
    if (!mesh) return null;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(mesh.v, 3));
    g.setIndex(mesh.f);
    g.computeVertexNormals();
    return g;
  }, [mesh]);
}

function PartNode({ part, childrenOf }) {
  const ref = useRef();
  const mesh = useStore((s) => s.meshes[part.id]);
  const selected = useStore((s) => s.state?.selected === part.id);
  const select = useStore((s) => s.select);
  const geom = useGeometry(mesh);

  useEffect(() => {
    objects.set(part.id, ref.current);
    return () => objects.delete(part.id);
  }, [part.id]);

  const kids = childrenOf[part.id] || [];
  const tint = part.type === "mesh" ? "#b7c6ff" : "#f5c46b";
  return (
    <group ref={ref} name={part.id} position={part.position}
      rotation={new THREE.Euler(part.rotation[0] * RAD, part.rotation[1] * RAD, part.rotation[2] * RAD, "ZYX")}
      scale={part.scale} visible={part.visible !== false}>
      {geom && (
        <mesh geometry={geom} castShadow receiveShadow
          onClick={(e) => { e.stopPropagation(); select(part.id); }}>
          <meshStandardMaterial color={tint} metalness={0.72} roughness={0.3}
            emissive={selected ? "#2fb8ff" : "#1a0e00"} emissiveIntensity={selected ? 0.35 : 0.4}
            transparent opacity={part.brightness ?? 1} />
          <Edges threshold={28} color={selected ? "#7fe8ff" : "#ffe3a6"} transparent opacity={selected ? 0.9 : 0.18} />
        </mesh>
      )}
      {kids.map((k) => <PartNode key={k.id} part={k} childrenOf={childrenOf} />)}
    </group>
  );
}

function Parts() {
  const parts = useStore((s) => s.state?.parts || []);
  const childrenOf = useMemo(() => {
    const m = {};
    for (const p of parts) (m[p.parent || "root"] ||= []).push(p);
    return m;
  }, [parts]);
  return (childrenOf.root || []).map((p) => <PartNode key={p.id} part={p} childrenOf={childrenOf} />);
}

function Panel() {
  const desk = useStore((s) => s.state?.desk);
  const holo = useStore((s) => s.results.hologram?.img);
  const tex = useMemo(() => {
    if (!holo) return null;
    const t = new THREE.TextureLoader().load(holo);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [holo]);
  if (!desk) return null;
  const w = desk.panel_w_mm, h = desk.panel_h_mm;
  const corners = [[-w / 2, -h / 2, 0], [w / 2, -h / 2, 0], [w / 2, h / 2, 0], [-w / 2, h / 2, 0], [-w / 2, -h / 2, 0]];
  const zone = (z) => corners.map(([x, y]) => [x * 0.98, y * 0.98, z]);
  return (
    <group>
      <mesh position={[0, 0, -0.5]} receiveShadow>
        <planeGeometry args={[w, h]} />
        <meshStandardMaterial color={tex ? "#1f5f7d" : "#0d2233"} map={tex} emissive="#0b3550"
          emissiveIntensity={0.35} metalness={0.3} roughness={0.75} transparent opacity={0.85} />
      </mesh>
      <Line points={corners} color="#5fe1ff" lineWidth={1.5} />
      <Line points={zone(100)} color="#5eead4" lineWidth={0.8} dashed dashSize={8} gapSize={6} transparent opacity={0.45} />
      <mesh position={[0, 0, -1]}>
        <planeGeometry args={[w * 1.25, h * 1.35]} />
        <meshBasicMaterial color="#5fe1ff" transparent opacity={0.035} />
      </mesh>
    </group>
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
      <mesh position={eye}><sphereGeometry args={[7, 24, 24]} /><meshBasicMaterial color="#a78bfa" /></mesh>
      <Line points={segs} segments color="#a78bfa" lineWidth={0.7} transparent opacity={0.25} />
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
        <mesh key={j} position={p}><sphereGeometry args={[j % 4 === 0 ? 4.2 : 3, 12, 12]} />
          <meshBasicMaterial color={frame.pinch[i] ? "#5eead4" : "#5fe1ff"} transparent opacity={0.85} /></mesh>
      ))}
    </group>
  ));
}

function Gizmo() {
  const selected = useStore((s) => s.state?.selected);
  const mode = useStore((s) => s.mode);
  const gizmo = useStore((s) => s.gizmo);
  const axis = useStore((s) => s.axis);
  const commit = useStore((s) => s.commitTransform);
  const obj = selected ? objects.get(selected) : null;
  if (!obj || mode !== "laptop") return null;
  return (
    <TransformControls object={obj} mode={gizmo} size={0.8}
      showX={!axis || axis === "x"} showY={!axis || axis === "y"} showZ={!axis || axis === "z"}
      onMouseUp={() => {
        const r = obj.rotation;
        commit(selected, {
          position: obj.position.toArray().map((v) => +v.toFixed(2)),
          rotation: [r.x, r.y, r.z].map((v) => +(v / RAD).toFixed(2)),
          scale: obj.scale.toArray().map((v) => +v.toFixed(3)),
        });
      }} />
  );
}

function CameraSetup() {
  const { camera } = useThree();
  useEffect(() => {
    camera.up.set(0, 0, 1);
    camera.position.set(250, -390, 300);
    camera.lookAt(0, 0, 60);
  }, [camera]);
  return null;
}

export default function Viewport() {
  const select = useStore((s) => s.select);
  return (
    <Canvas shadows dpr={[1, 2]} camera={{ fov: 35, near: 1, far: 6000 }}
      gl={{ antialias: true, alpha: true }} onPointerMissed={(e) => e.button === 0 && select(null)}>
      <CameraSetup />
      <fog attach="fog" args={["#04060b", 900, 2600]} />
      <hemisphereLight args={["#9fdcff", "#160c26", 0.75]} />
      <directionalLight position={[300, -200, 700]} intensity={1.8} castShadow shadow-mapSize={[2048, 2048]} />
      <pointLight position={[-250, 200, 220]} intensity={60000} color="#5fe1ff" />
      <pointLight position={[260, 220, 180]} intensity={40000} color="#a78bfa" />
      <gridHelper args={[1400, 56, "#173049", "#0e1a2b"]} rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -2]} />
      <Panel />
      <EyeAndWindow />
      <Parts />
      <HandJoints />
      <Gizmo />
      <OrbitControls makeDefault target={[0, 0, 60]} enableDamping dampingFactor={0.08} maxDistance={3000} />
    </Canvas>
  );
}
