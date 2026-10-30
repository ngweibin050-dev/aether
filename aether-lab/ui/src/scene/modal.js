// Blender modal transforms: G / R / S follow the mouse, X Y Z lock an axis, type a number for an exact value,
// hold Ctrl to snap (1 mm, 5°, 0.1), Shift for precision. LMB / Enter confirms, RMB / Esc cancels.
// The same functions are used by hand mode (pinch-drag) through begin/update/finish.
import * as THREE from "three";
import { objects, view } from "./registry";
import { useStore } from "../store";

const AX = { x: new THREE.Vector3(1, 0, 0), y: new THREE.Vector3(0, 1, 0), z: new THREE.Vector3(0, 0, 1) };
const RAD = Math.PI / 180;
let M = null;

const toScreen = (v) => {
  const p = v.clone().project(view.camera), r = view.dom.getBoundingClientRect();
  return new THREE.Vector2((p.x + 1) / 2 * r.width + r.left, (1 - p.y) / 2 * r.height + r.top);
};

function roots(ids) {
  const parts = useStore.getState().state.parts, by = Object.fromEntries(parts.map((p) => [p.id, p]));
  const sel = new Set(ids);
  return ids.filter((id) => { let q = by[id]?.parent; while (q) { if (sel.has(q)) return false; q = by[q]?.parent; } return true; });
}

export function explodeOffset(id) {
  const s = useStore.getState();
  const o = s.offsets[id], f = s.view.explode || 0;
  return o ? new THREE.Vector3(...o).multiplyScalar(f) : new THREE.Vector3();
}

export function begin(kind, mouse, ids = useStore.getState().selection) {
  const list = roots(ids).map((id) => [id, objects.get(id)]).filter(([, o]) => o);
  if (!list.length || !view.camera) return false;
  const items = list.map(([id, o]) => ({
    id, o, pos: o.position.clone(), quat: o.quaternion.clone(), scale: o.scale.clone(),
    wpos: o.getWorldPosition(new THREE.Vector3()), wquat: o.getWorldQuaternion(new THREE.Quaternion()),
  }));
  const pivot = items.reduce((a, it) => a.add(it.wpos), new THREE.Vector3()).divideScalar(items.length);
  M = { kind, items, pivot, m0: mouse.clone(), m: mouse.clone(), axis: null, typed: "", ctrl: false, shift: false };
  useStore.setState({ modal: { kind, text: "" } });
  update();
  return true;
}

export const active = () => !!M;
export const setDepth = (mm) => { if (M) M.depth = mm; };      // hand mode: push / pull along the view direction
export const moved = () => !!M && (M.m.distanceTo(M.m0) > 6 || Math.abs(M.depth || 0) > 3);

export function update(mouse) {
  if (!M) return;
  if (mouse) M.m.copy(mouse);
  const { kind, items, pivot, m0, m, axis } = M;
  const typed = M.typed && M.typed !== "-" ? parseFloat(M.typed) : null;
  const c = toScreen(pivot);
  let text = "";
  if (kind === "G") {
    let delta;
    if (axis) {
      const a = AX[axis], s = toScreen(pivot.clone().add(a)).sub(c);
      let t = typed ?? m.clone().sub(m0).dot(s) / Math.max(s.lengthSq(), 1e-9);
      if (typed === null) t = snap(t, 1);
      delta = a.clone().multiplyScalar(t);
      text = `D: ${t.toFixed(2)} mm along global ${axis.toUpperCase()}`;
    } else if (typed !== null) {
      delta = new THREE.Vector3(typed, 0, 0);
      text = `D: ${typed} mm along X`;
    } else {
      const ndc = pivot.clone().project(view.camera), r = view.dom.getBoundingClientRect();
      ndc.x += (m.x - m0.x) / r.width * 2; ndc.y -= (m.y - m0.y) / r.height * 2;
      delta = ndc.unproject(view.camera).sub(pivot);
      delta.set(snap(delta.x, 1), snap(delta.y, 1), snap(delta.z, 1));
      text = `D: ${delta.x.toFixed(1)}  ${delta.y.toFixed(1)}  ${delta.z.toFixed(1)} mm`;
    }
    if (M.depth) delta.add(view.camera.getWorldDirection(new THREE.Vector3()).multiplyScalar(M.depth));
    for (const it of items) {
      const w = it.wpos.clone().add(delta);
      it.o.position.copy(it.o.parent.worldToLocal(w));
    }
  } else if (kind === "R") {
    const a0 = Math.atan2(m0.y - c.y, m0.x - c.x), a1 = Math.atan2(m.y - c.y, m.x - c.x);
    const fwd = view.camera.getWorldDirection(new THREE.Vector3());
    const ax = axis ? AX[axis].clone() : fwd;
    let ang = typed !== null ? typed * RAD : (a1 - a0) * (axis ? Math.sign(AX[axis].dot(fwd)) || 1 : 1);
    if (typed === null) ang = snap(ang / RAD, 5) * RAD;
    const q = new THREE.Quaternion().setFromAxisAngle(ax, ang);
    for (const it of items) {
      const wq = q.clone().multiply(it.wquat);
      const pq = it.o.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
      it.o.quaternion.copy(pq.multiply(wq));
      const w = it.wpos.clone().sub(pivot).applyQuaternion(q).add(pivot);
      it.o.position.copy(it.o.parent.worldToLocal(w));
    }
    text = `Rot: ${(ang / RAD).toFixed(1)}°${axis ? " about " + axis.toUpperCase() : " (view)"}`;
  } else if (kind === "S") {
    let f = typed ?? m.distanceTo(c) / Math.max(m0.distanceTo(c), 1);
    if (typed === null) f = snap(f, 0.1);
    f = Math.max(f, 0.01);
    const k = axis ? { x: 0, y: 1, z: 2 }[axis] : -1;
    for (const it of items) {
      const sc = it.scale.clone();
      if (k < 0) sc.multiplyScalar(f); else sc.setComponent(k, sc.getComponent(k) * f);
      it.o.scale.copy(sc);
      if (k < 0) it.o.position.copy(it.o.parent.worldToLocal(it.wpos.clone().sub(pivot).multiplyScalar(f).add(pivot)));
    }
    text = `Scale: ${f.toFixed(3)}${axis ? " along " + axis.toUpperCase() : ""}`;
  }
  if (M.typed) text += `   [${M.typed}]`;
  useStore.setState({ modal: { kind, axis, text } });
}

function snap(v, step) {
  if (!M) return v;
  if (M.ctrl) return Math.round(v / (M.shift ? step / 10 : step)) * (M.shift ? step / 10 : step);
  return v;
}

export function cancel() {
  if (!M) return;
  for (const it of M.items) { it.o.position.copy(it.pos); it.o.quaternion.copy(it.quat); it.o.scale.copy(it.scale); }
  M = null;
  useStore.setState({ modal: null });
}

export function finish() {
  if (!M) return;
  const st = useStore.getState();
  const byId = Object.fromEntries(M.items.map((it) => [it.id, it.o]));
  M = null;
  useStore.setState({ modal: null });
  const parts = st.state.parts.map((p) => {
    const o = byId[p.id];
    if (!o) return p;
    const pos = o.position.clone().sub(explodeOffset(p.id));
    return { ...p, position: pos.toArray().map((v) => +v.toFixed(2)),
      rotation: [o.rotation.x, o.rotation.y, o.rotation.z].map((v) => +(v / RAD).toFixed(2)),
      scale: o.scale.toArray().map((v) => +v.toFixed(4)) };
  });
  st.commitParts(parts);
}

// keyboard + mouse while a modal transform runs (laptop mode)
export function startModal(kind) {
  const mouse = lastMouse.clone();
  if (!begin(kind, mouse)) return;
  const move = (e) => { M && (M.ctrl = e.ctrlKey, M.shift = e.shiftKey); update(new THREE.Vector2(e.clientX, e.clientY)); };
  const down = (e) => { e.preventDefault(); e.stopPropagation(); e.button === 2 ? cancel() : finish(); done(); };
  const key = (e) => {
    if (!M) return done();
    e.preventDefault(); e.stopPropagation();
    const k = e.key.toLowerCase();
    M.ctrl = e.ctrlKey; M.shift = e.shiftKey;
    if (k === "escape") { cancel(); return done(); }
    if (k === "enter" || k === " ") { finish(); return done(); }
    if (["x", "y", "z"].includes(k)) M.axis = M.axis === k ? null : k;
    else if (/^[0-9.]$/.test(k)) M.typed += k;
    else if (k === "-") M.typed = M.typed.startsWith("-") ? M.typed.slice(1) : "-" + M.typed;
    else if (k === "backspace") M.typed = M.typed.slice(0, -1);
    else if (["g", "r", "s"].includes(k) && k.toUpperCase() !== M.kind) { const ids = M.items.map((i) => i.id); cancel(); done(); begin(k.toUpperCase(), lastMouse.clone(), ids); bind(); return; }
    update();
  };
  const ctx = (e) => e.preventDefault();
  function bind() {
    addEventListener("pointermove", move, true);
    addEventListener("pointerdown", down, true);
    addEventListener("keydown", key, true);
    addEventListener("keyup", move2, true);
    addEventListener("contextmenu", ctx, true);
  }
  const move2 = (e) => { if (M) { M.ctrl = e.ctrlKey; M.shift = e.shiftKey; update(); } };
  function done() {
    removeEventListener("pointermove", move, true);
    removeEventListener("pointerdown", down, true);
    removeEventListener("keydown", key, true);
    removeEventListener("keyup", move2, true);
    setTimeout(() => removeEventListener("contextmenu", ctx, true), 50);
  }
  bind();
}

export const lastMouse = new THREE.Vector2(innerWidth / 2, innerHeight / 2);
addEventListener("pointermove", (e) => lastMouse.set(e.clientX, e.clientY), true);
