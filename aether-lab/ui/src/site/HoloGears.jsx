import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import * as THREE from "three";
import { beamMaterial, holoMaterial, holoSweep, holoTime } from "../scene/holo";

// A pair of meshing gears floating above an AETHER desk panel, drawn with the lab's hologram shader.
// Teeth are a simple trapezoid profile (the lab itself uses true involutes); speed ratio is the real -z1/z2.
const M = 0.12;

function gearShape(z) {
  const r = (M * z) / 2, ra = r + M, rf = r - 1.25 * M, s = new THREE.Shape();
  const step = (2 * Math.PI) / z;
  for (let i = 0; i < z; i++) {
    const a = i * step;
    const pts = [[rf, a - 0.5 * step], [rf, a - 0.27 * step], [ra, a - 0.13 * step], [ra, a + 0.13 * step], [rf, a + 0.27 * step]];
    pts.forEach(([rr, t], k) => (i === 0 && k === 0 ? s.moveTo : s.lineTo).call(s, rr * Math.cos(t), rr * Math.sin(t)));
  }
  s.closePath();
  const bore = new THREE.Path(); bore.absarc(0, 0, 0.22 * r, 0, Math.PI * 2, true); s.holes.push(bore);
  for (let k = 0; k < 5 && z > 16; k++) {
    const t = (k / 5) * Math.PI * 2, c = 0.58 * r, h = new THREE.Path();
    h.absarc(c * Math.cos(t), c * Math.sin(t), 0.17 * r, 0, Math.PI * 2, true); s.holes.push(h);
  }
  return s;
}

function Gear({ z, color, x, phase, speed }) {
  const ref = useRef();
  const [geo, edges] = useMemo(() => {
    const g = new THREE.ExtrudeGeometry(gearShape(z), { depth: 0.22, bevelEnabled: true, bevelSize: 0.015, bevelThickness: 0.015, bevelSegments: 2, curveSegments: 24 });
    g.translate(0, 0, -0.11);
    return [g, new THREE.EdgesGeometry(g, 25)];
  }, [z]);
  const mat = useMemo(() => holoMaterial({ color, rim: 1.2 }), [color]);
  useFrame((_, dt) => { if (ref.current) ref.current.rotation.z += speed * Math.min(dt, 0.05); });
  return (
    <group position={[x, 0, 1.25]} rotation={[Math.PI / 2, 0, 0]}>
      <group ref={ref} rotation={[0, 0, phase]}>
        <mesh geometry={geo} material={mat} />
        <lineSegments geometry={edges}><lineBasicMaterial color={color} transparent opacity={0.55} /></lineSegments>
      </group>
    </group>
  );
}

function Rig() {
  const g = useRef();
  useFrame((st, dt) => {
    holoTime.value += dt;
    holoSweep.value = -0.2 + ((holoTime.value * 0.45) % 2.9);
    if (!g.current) return;
    const tx = st.pointer.x * 0.35, ty = st.pointer.y * 0.18;
    g.current.rotation.z += (tx - g.current.rotation.z) * 0.05;
    g.current.rotation.x += (-ty - g.current.rotation.x) * 0.05;
  });
  const z1 = 24, z2 = 14, r1 = (M * z1) / 2, r2 = (M * z2) / 2;
  const beam = useMemo(() => beamMaterial("#4fd6ff", 0.2), []);
  return (
    <group ref={g}>
      <Gear z={z1} color="#5fe1ff" x={-r2} phase={0} speed={0.5} />
      <Gear z={z2} color="#b06bff" x={r1} phase={Math.PI / z2 + Math.PI} speed={-0.5 * (z1 / z2)} />
      {/* desk panel */}
      <mesh position={[0, 0, 0]}><boxGeometry args={[3.4, 1.6, 0.05]} /><meshBasicMaterial color="#0b1730" transparent opacity={0.9} /></mesh>
      <lineSegments position={[0, 0, 0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(3.4, 1.6, 0.05)]} /><lineBasicMaterial color="#5fe1ff" transparent opacity={0.7} />
      </lineSegments>
      <mesh position={[0, 0, 1.3]} rotation={[Math.PI / 2, 0, 0]}><planeGeometry args={[3.2, 2.6]} /><primitive object={beam} attach="material" /></mesh>
      <gridHelper args={[3.4, 17, "#1d4f73", "#12304a"]} rotation={[Math.PI / 2, 0, 0]} position={[0, 0, 0.03]} scale={[1, 1, 1.6 / 3.4]} />
    </group>
  );
}

export default function HoloGears() {
  return (
    <Canvas dpr={[1, 1.75]} camera={{ position: [0, -6.9, 4.3], fov: 34, up: [0, 0, 1] }}
      onCreated={({ camera }) => camera.lookAt(0, 0, 0.95)} gl={{ antialias: true, alpha: true }}>
      <Rig />
      <EffectComposer><Bloom intensity={0.6} luminanceThreshold={0.2} mipmapBlur /></EffectComposer>
    </Canvas>
  );
}
