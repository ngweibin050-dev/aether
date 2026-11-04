import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import * as THREE from "three";
import { useStore } from "../store";

// A file attached to (or produced in) the chat, opened by double-click: 3D files (GLB / glTF / STL / OBJ) in a small
// viewer you can turn (drag) and zoom (wheel), PDF and SVG inline, STEP / others as a card. Always: Download, × / Esc.
const EXT = (n) => (n.split(".").pop() || "").toLowerCase();

function Model3D({ url, ext }) {
  const box = useRef();
  const [err, setErr] = useState(null);
  useEffect(() => {
    const el = box.current;
    const W = el.clientWidth, H = el.clientHeight;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, devicePixelRatio));
    renderer.setSize(W, H);
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xdfe9ff, 0x1a2030, 1.4));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(2, -3, 4);
    scene.add(sun);
    const cam = new THREE.PerspectiveCamera(35, W / H, 0.01, 1e7);
    cam.up.set(0, 0, 1);
    let obj = null, theta = -0.9, phi = 1.1, dist = 1, centre = new THREE.Vector3(), raf = 0, alive = true;
    const draw = () => {
      raf = 0;
      cam.position.set(Math.sin(phi) * Math.cos(theta), Math.sin(phi) * Math.sin(theta), Math.cos(phi)).multiplyScalar(dist).add(centre);
      cam.lookAt(centre);
      renderer.render(scene, cam);
    };
    const ask = () => { if (!raf) raf = requestAnimationFrame(draw); };
    const load = ext === "stl" ? import("three/examples/jsm/loaders/STLLoader.js").then((m) => new m.STLLoader())
      : ext === "obj" ? import("three/examples/jsm/loaders/OBJLoader.js").then((m) => new m.OBJLoader())
        : import("three/examples/jsm/loaders/GLTFLoader.js").then((m) => new m.GLTFLoader());
    load.then((loader) => loader.loadAsync(url)).then((res) => {
      if (!alive) return;
      obj = res.scene || (res.isBufferGeometry ? new THREE.Mesh(res, new THREE.MeshStandardMaterial({ color: 0xc9d2de, metalness: 0.2, roughness: 0.5 })) : res);
      if (res.scene) obj.rotation.x = Math.PI / 2;                 // glTF is y-up; the lab is z-up
      scene.add(obj);
      const b = new THREE.Box3().setFromObject(obj);
      b.getCenter(centre);
      dist = b.getSize(new THREE.Vector3()).length() * 1.3 || 1;
      ask();
    }).catch((e) => setErr(e.message || String(e)));
    const down = (e) => {
      let x = e.clientX, y = e.clientY;
      const mv = (ev) => { theta -= (ev.clientX - x) * 0.01; phi = Math.min(3.1, Math.max(0.05, phi - (ev.clientY - y) * 0.01)); x = ev.clientX; y = ev.clientY; ask(); };
      const up = () => { removeEventListener("pointermove", mv); removeEventListener("pointerup", up); };
      addEventListener("pointermove", mv); addEventListener("pointerup", up);
    };
    const wheel = (e) => { e.preventDefault(); dist *= Math.exp(e.deltaY * 0.001); ask(); };
    renderer.domElement.addEventListener("pointerdown", down);
    renderer.domElement.addEventListener("wheel", wheel, { passive: false });
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      renderer.dispose();
      el.innerHTML = "";
    };
  }, [url, ext]);
  return (
    <div className="relative h-full w-full">
      <div ref={box} className="h-full w-full cursor-grab active:cursor-grabbing" />
      {err && <div className="absolute inset-0 grid place-items-center text-[12px] text-warn">Could not show this file: {err}</div>}
      <div className="pointer-events-none absolute bottom-2 left-3 font-mono text-[10px] text-slate-500">drag to turn · wheel to zoom</div>
    </div>
  );
}

export default function FilePreview() {
  const f = useStore((s) => s.preview);
  const close = () => useStore.setState({ preview: null });
  useEffect(() => {
    if (!f) return;
    const k = (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
    addEventListener("keydown", k, true);
    return () => removeEventListener("keydown", k, true);
  }, [f]);
  if (!f) return null;
  const ext = EXT(f.name), url = f.url;
  const body = !url ? <div className="grid h-full place-items-center text-slate-400">This file has no preview (it is still uploading or was not saved).</div>
    : ["glb", "gltf", "stl", "obj"].includes(ext) ? <Model3D url={url} ext={ext} />
      : ext === "pdf" ? <iframe title={f.name} src={url.replace(/(\?|$)/, "?inline=1$1")} className="h-full w-full rounded-lg bg-white" />
        : ["svg", "png", "jpg", "jpeg", "gif", "webp"].includes(ext) ? <img src={url} alt={f.name} data-nolightbox className="mx-auto h-full max-w-full object-contain" />
          : (
            <div className="grid h-full place-items-center text-center text-[12.5px] text-slate-300">
              <div>
                <div className="font-mono text-[28px] text-cyan-glow">.{ext}</div>
                <div className="mt-1">{ext === "step" || ext === "stp" ? "STEP: an exact B-rep CAD file. Open it in any CAD tool (FreeCAD, Fusion, SolidWorks, Onshape)." : "No preview for this kind of file."}</div>
                {f.bytes ? <div className="mt-1 font-mono text-[11px] text-slate-500">{(f.bytes / 1024).toFixed(0)} KB</div> : null}
              </div>
            </div>);
  return createPortal(
    <div className="fixed inset-0 z-[100] grid place-items-center bg-black/80 p-6" onClick={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div className="glass flex h-[min(80vh,720px)] w-[min(92vw,1000px)] flex-col overflow-hidden rounded-2xl">
        <div className="flex shrink-0 items-center gap-2 border-b border-white/10 px-4 py-2 text-[12.5px] text-white">
          <span className="min-w-0 flex-1 truncate font-semibold">{f.label || f.name}</span>
          {url && <a className="btn !py-1" href={url} download={f.name}>Download</a>}
          <button className="grid h-8 w-8 place-items-center rounded-lg bg-white/10 text-[18px] hover:bg-white/20" onClick={close} title="Close (Esc)">×</button>
        </div>
        <div className="min-h-0 flex-1 p-2">{body}</div>
      </div>
    </div>, document.body);
}
