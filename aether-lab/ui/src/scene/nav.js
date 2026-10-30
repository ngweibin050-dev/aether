// Blender-style viewport navigation (z-up turntable).
//   MMB drag orbit · Shift+MMB pan · Ctrl+MMB zoom · wheel zoom
//   Laptop: Alt+LMB orbit (emulate 3-button mouse), Alt+Shift+LMB pan, trackpad two-finger scroll orbits,
//   Shift+scroll pans, pinch (Ctrl+wheel) zooms.
//   Numpad 1/3/7 (Ctrl = opposite side) switch to orthographic axis views, 5 toggles ortho, 0 = viewer's eye,
//   2/4/6/8 orbit in 15° steps, . frames the selection, Home frames everything.
import * as THREE from "three";

const TAU = Math.PI * 2;
const ease = (t) => 1 - Math.pow(1 - t, 3);

export class Nav {
  constructor(persp, ortho, dom, setCamera) {
    this.persp = persp; this.ortho = ortho; this.dom = dom; this.setCamera = setCamera;
    this.target = new THREE.Vector3(0, 0, 60);
    this.theta = -1.0; this.phi = 1.05; this.dist = 560;
    this.isOrtho = false; this.autoOrtho = false;
    this.anim = null; this.listeners = new Set();
    this.drag = null;
    this._bind();
    this.apply();
  }
  get camera() { return this.isOrtho ? this.ortho : this.persp; }

  apply() {
    const s = Math.sin(this.phi);
    const off = new THREE.Vector3(s * Math.cos(this.theta), s * Math.sin(this.theta), Math.cos(this.phi)).multiplyScalar(this.dist);
    for (const cam of [this.persp, this.ortho]) {
      cam.up.set(0, 0, 1);
      cam.position.copy(this.target).add(off);
      cam.lookAt(this.target);
    }
    const h = this.dom.clientHeight || 800;
    this.ortho.zoom = h / (2 * this.dist * Math.tan(THREE.MathUtils.degToRad(this.persp.fov / 2)));
    this.ortho.near = -5000; this.ortho.far = 5000;
    this.ortho.updateProjectionMatrix();
    this.listeners.forEach((f) => f(this));
  }
  onChange(f) { this.listeners.add(f); return () => this.listeners.delete(f); }

  setOrtho(on) {
    if (on === this.isOrtho) return;
    this.isOrtho = on;
    this.setCamera(this.camera);
    this.apply();
  }

  animateTo({ theta = this.theta, phi = this.phi, dist = this.dist, target = this.target }, ms = 320) {
    let dt = ((theta - this.theta) % TAU + TAU * 1.5) % TAU - Math.PI;   // shortest way round
    const from = { theta: this.theta, phi: this.phi, dist: this.dist, target: this.target.clone() };
    const to = { theta: this.theta + dt, phi, dist, target: target.clone() };
    const t0 = performance.now();
    cancelAnimationFrame(this.anim);
    const step = () => {
      const t = Math.min(1, (performance.now() - t0) / ms), k = ease(t);
      this.theta = from.theta + (to.theta - from.theta) * k;
      this.phi = from.phi + (to.phi - from.phi) * k;
      this.dist = from.dist + (to.dist - from.dist) * k;
      this.target.lerpVectors(from.target, to.target, k);
      this.apply();
      if (t < 1) this.anim = requestAnimationFrame(step);
    };
    step();
  }

  orbit(dTheta, dPhi) {
    if (this.autoOrtho) { this.autoOrtho = false; this.setOrtho(false); }
    this.theta += dTheta;
    this.phi = THREE.MathUtils.clamp(this.phi + dPhi, 0.0005, Math.PI - 0.0005);
    this.apply();
  }
  pan(dxPx, dyPx) {
    const h = this.dom.clientHeight || 800;
    const perPx = (2 * this.dist * Math.tan(THREE.MathUtils.degToRad(this.persp.fov / 2))) / h;
    const cam = this.camera;
    const right = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0);
    const up = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1);
    this.target.addScaledVector(right, -dxPx * perPx).addScaledVector(up, dyPx * perPx);
    this.apply();
  }
  zoom(f) { this.dist = THREE.MathUtils.clamp(this.dist * f, 20, 3500); this.apply(); }

  view(name) {
    const v = {
      front: [-Math.PI / 2, Math.PI / 2], back: [Math.PI / 2, Math.PI / 2],
      right: [0, Math.PI / 2], left: [Math.PI, Math.PI / 2],
      top: [-Math.PI / 2, 0.0005], bottom: [-Math.PI / 2, Math.PI - 0.0005],
    }[name];
    if (!v) return;
    this.autoOrtho = true;
    this.setOrtho(true);
    this.animateTo({ theta: v[0], phi: v[1] });
  }
  fromPoint(eye, target) {
    const off = new THREE.Vector3(...eye).sub(target);
    this.autoOrtho = false;
    this.setOrtho(false);
    this.animateTo({ target, dist: off.length(), theta: Math.atan2(off.y, off.x), phi: Math.acos(THREE.MathUtils.clamp(off.z / off.length(), -1, 1)) });
  }
  frame(box) {
    if (!box || box.isEmpty()) return;
    const c = box.getCenter(new THREE.Vector3());
    const r = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 10);
    this.animateTo({ target: c, dist: r / Math.sin(THREE.MathUtils.degToRad(this.persp.fov / 2)) * 1.15 });
  }

  _bind() {
    const d = this.dom;
    this._down = (e) => {
      const emulate = e.button === 0 && e.altKey;
      if (e.button !== 1 && !emulate) return;
      e.preventDefault();
      const mode = e.ctrlKey ? "zoom" : e.shiftKey ? "pan" : "orbit";
      this.drag = { mode, x: e.clientX, y: e.clientY };
      d.setPointerCapture?.(e.pointerId);
      cancelAnimationFrame(this.anim);
    };
    this._move = (e) => {
      if (!this.drag) return;
      const dx = e.clientX - this.drag.x, dy = e.clientY - this.drag.y;
      this.drag.x = e.clientX; this.drag.y = e.clientY;
      if (this.drag.mode === "orbit") this.orbit(-dx * 0.0085, -dy * 0.0085);
      else if (this.drag.mode === "pan") this.pan(dx, dy);
      else this.zoom(Math.exp(dy * 0.006));
    };
    this._up = () => { this.drag = null; };
    this._wheel = (e) => {
      e.preventDefault();
      cancelAnimationFrame(this.anim);
      const trackpad = e.deltaMode === 0 && (Math.abs(e.deltaX) > 0 || (Math.abs(e.deltaY) < 40 && e.deltaY % 1 !== 0));
      if (e.ctrlKey) this.zoom(Math.exp(e.deltaY * 0.01));                  // pinch / Ctrl+wheel
      else if (trackpad && e.shiftKey) this.pan(-e.deltaX, -e.deltaY);
      else if (trackpad) this.orbit(e.deltaX * 0.006, e.deltaY * 0.006);
      else this.zoom(Math.exp(Math.sign(e.deltaY) * 0.12));
    };
    this._aux = (e) => e.button === 1 && e.preventDefault();
    d.addEventListener("pointerdown", this._down);
    addEventListener("pointermove", this._move);
    addEventListener("pointerup", this._up);
    d.addEventListener("wheel", this._wheel, { passive: false });
    d.addEventListener("auxclick", this._aux);
  }
  dispose() {
    const d = this.dom;
    d.removeEventListener("pointerdown", this._down);
    removeEventListener("pointermove", this._move);
    removeEventListener("pointerup", this._up);
    d.removeEventListener("wheel", this._wheel);
    d.removeEventListener("auxclick", this._aux);
    cancelAnimationFrame(this.anim);
  }
}
