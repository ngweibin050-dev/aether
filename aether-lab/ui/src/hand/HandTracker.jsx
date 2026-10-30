// Hand mode: everything laptop mode can do, with a webcam and two hands.
//   Air cursor  = point between thumb and index tip (works on every button, menu, slider and panel)
//   Pinch       = click; pinch-hold = press and drag (sliders, panels, hold-to-talk mic)
//   Pinch on a part = grab it (move in the view plane, push/pull by moving the hand toward/away from the camera)
//   Pinch on empty space = orbit the view
//   Two-hand pinch = rotate + scale the selected part, or (nothing selected) pull apart = explode the assembly
//   Peace sign (index + middle up) held = hand menu (8 big actions, incl. search-all); fist held = deselect / close
//   Both palms open = calculate the hologram
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";
import { useStore } from "../store";
import { objects, view } from "../scene/registry";
import { pick } from "../scene/Interaction";
import * as modal from "../scene/modal";
import { explodeOffset } from "../scene/modal";
import { cmd, run } from "../commands";

const VOL = { x: 520, zMin: 0, zMax: 170, yNear: -160, yFar: 160 };
const BONES = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];
const RAD = Math.PI / 180;
const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

function toDesk(lm) {
  const palm = d2(lm[0], lm[9]) || 0.1;
  const depth = THREE.MathUtils.clamp((palm - 0.12) / 0.16, 0, 1);
  return lm.map((p) => [(0.5 - p.x) * VOL.x, VOL.yFar + (VOL.yNear - VOL.yFar) * depth, VOL.zMin + (1 - p.y) * (VOL.zMax - VOL.zMin)]);
}

function gestureOf(lm, wasPinch) {
  const palm = d2(lm[0], lm[9]) || 0.1;
  const r = d2(lm[4], lm[8]) / palm;
  const pinch = wasPinch ? r < 0.42 : r < 0.27;                  // hysteresis: no flicker at the threshold
  const ext = (tip, pip) => d2(lm[tip], lm[0]) > d2(lm[pip], lm[0]) * 1.15;
  const fingers = [ext(8, 6), ext(12, 10), ext(16, 14), ext(20, 18)];
  return { pinch, open: fingers.every(Boolean) && r > 0.5, fist: fingers.every((f) => !f) && !pinch, palm,
           peace: fingers[0] && fingers[1] && !fingers[2] && !fingers[3] && !pinch };
}

const HAND_MENU = () => [
  { id: "h.add", label: "Add part", icon: "plus", run: () => { const c = useStore.getState().handCursor; useStore.getState().setMenu({ kind: "add", x: c?.x, y: c?.y }); } },
  { ...cmd("in.explode"), icon: "explode" },
  { ...cmd("obj.delete"), icon: "trash" },
  { ...cmd("in.secx"), label: "Section cut", icon: "section" },
  { ...cmd("obj.dup"), label: "Duplicate", icon: "layers", run: () => useStore.getState().duplicate() },
  { ...cmd("in.xray"), icon: "xray" },
  { ...cmd("edit.search"), label: "All actions…", icon: "search", run: () => useStore.getState().setMenu({ kind: "search" }) },
  { ...cmd("holo.calc"), label: "Hologram", icon: "holo" },
];

// ---- synthetic pointer events, so the air cursor can press anything in the UI ----
function fire(type, el, x, y, buttons) {
  if (!el) return;
  const init = { bubbles: true, cancelable: true, composed: true, clientX: x, clientY: y, button: 0, buttons, pointerId: 77, pointerType: "pen", isPrimary: true };
  el.dispatchEvent(new PointerEvent(type, init));
  const m = { pointerdown: "mousedown", pointermove: "mousemove", pointerup: "mouseup" }[type];
  if (m) el.dispatchEvent(new MouseEvent(m, init));
}
const under = (x, y) => document.elementFromPoint(x, y);

export function createHandController() {
  const st = useStore.getState;
  const S = { cur: null, pinch: [false, false], press: null, two: null, holdOpen: 0, holdFist: 0, holdBoth: 0, lastSend: 0, palm0: 0 };

  function step(hands, now = performance.now()) {
    const g = hands.map((lm, i) => gestureOf(lm, S.pinch[i]));
    S.pinch = [g[0]?.pinch || false, g[1]?.pinch || false];
    const world = hands.map(toDesk);
    st().setHandFrame(hands.length ? { world, pinch: g.map((x) => x.pinch) } : null);
    if (!hands.length) { release(); st().handCursor && useStore.setState({ handCursor: null }); return ""; }

    // air cursor from the first hand (thumb-index midpoint is stable while pinching)
    const lm = hands[0];
    const mx = 1 - (lm[4].x + lm[8].x) / 2, my = (lm[4].y + lm[8].y) / 2;
    const tx = THREE.MathUtils.clamp((mx - 0.15) / 0.7, 0, 1) * innerWidth, ty = THREE.MathUtils.clamp((my - 0.12) / 0.62, 0, 1) * innerHeight;
    S.cur = S.cur ? { x: S.cur.x + (tx - S.cur.x) * 0.4, y: S.cur.y + (ty - S.cur.y) * 0.4 } : { x: tx, y: ty };
    const { x, y } = S.cur;
    let label = "point";

    // two hands pinching: rotate + scale the selection, or explode
    if (hands.length === 2 && g[0].pinch && g[1].pinch) {
      if (S.press) release();
      const a = world[0][8], b = world[1][8];
      const ang = Math.atan2(b[1] - a[1], b[0] - a[0]), dist = Math.hypot(b[0] - a[0], b[2] - a[2], b[1] - a[1]);
      const sel = st().state?.selected, obj = sel && objects.get(sel);
      if (!S.two) S.two = { ang, dist, obj, rot: obj?.quaternion.clone(), scale: obj?.scale.clone(), explode: st().view.explode };
      if (S.two.obj) {
        const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), ang - S.two.ang);
        S.two.obj.quaternion.copy(q.multiply(S.two.rot));
        S.two.obj.scale.copy(S.two.scale).multiplyScalar(THREE.MathUtils.clamp(dist / S.two.dist, 0.3, 3));
        S.two.obj.userData.dragging = true;
        label = "rotate + scale";
      } else {
        st().setView({ explode: +THREE.MathUtils.clamp(S.two.explode + (dist - S.two.dist) / 220, 0, 1).toFixed(2) });
        label = `pull apart · explode ${Math.round(st().view.explode * 100)}%`;
      }
      useStore.setState({ handCursor: { x, y, down: true, label } });
      return label;
    }
    if (S.two) {
      const o = S.two.obj;
      if (o) {
        o.userData.dragging = false;
        const id = st().state.selected, r = o.rotation;
        st().commitParts(st().state.parts.map((p) => p.id !== id ? p : { ...p,
          rotation: [r.x, r.y, r.z].map((v) => +(v / RAD).toFixed(2)), scale: o.scale.toArray().map((v) => +v.toFixed(3)),
          position: o.position.clone().sub(explodeOffset(id)).toArray().map((v) => +v.toFixed(2)) }));
      }
      S.two = null;
    }

    // one-hand pinch = press
    const p = g[0].pinch;
    if (p && !S.press) {
      const el = under(x, y);
      if (el === view.dom) {
        const h = pick(x, y);
        if (h?.id) {
          if (!st().selection.includes(h.id)) st().select(h.id);
          modal.begin("G", new THREE.Vector2(x, y));
          S.press = { kind: "grab", palm0: g[0].palm, t: now };
        } else S.press = { kind: "orbit", x, y, x0: x, y0: y, t: now };
      } else {
        fire("pointerdown", el, x, y, 1);
        S.press = { kind: "ui", el, x0: x, y0: y, t: now };
      }
    } else if (p && S.press) {
      if (S.press.kind === "grab") {
        modal.setDepth((g[0].palm - S.press.palm0) * -900);       // hand toward the camera = toward the viewer
        modal.update(new THREE.Vector2(x, y));
        label = "grab · move";
      } else if (S.press.kind === "orbit") {
        view.nav?.orbit(-(x - S.press.x) * 0.006, -(y - S.press.y) * 0.006);
        S.press.x = x; S.press.y = y;
        label = "orbit view";
      } else {
        fire("pointermove", under(x, y) || document.body, x, y, 1);
        label = "press";
      }
    } else if (!p && S.press) release();
    else fire("pointermove", under(x, y) || document.body, x, y, 0);

    // held poses
    const both = hands.length === 2 && g.every((q) => q.open);
    if (both) {
      S.holdBoth ||= now;
      label = "hold both palms → hologram";
      if (now - S.holdBoth > 1000 && S.holdBoth !== -1) { S.holdBoth = -1; run("holo.calc"); }
    } else S.holdBoth = 0;
    if (!both && g[0].peace && !S.press) {
      S.holdOpen ||= now;
      const t = Math.min(1, (now - S.holdOpen) / 600);
      label = "V-sign hold → hand menu";
      if (t >= 1 && S.holdOpen !== -1 && !st().menu) { S.holdOpen = -1; st().setMenu({ kind: "hand", x, y, items: HAND_MENU() }); }
      useStore.setState({ handCursor: { x, y, down: false, hold: S.holdOpen === -1 ? 0 : t, label } });
      return label;
    } else if (!g[0].peace) S.holdOpen = 0;
    if (g[0].fist && !S.press) {
      S.holdFist ||= now;
      label = "fist → deselect";
      if (now - S.holdFist > 800 && S.holdFist !== -1) { S.holdFist = -1; st().menu ? st().setMenu(null) : st().select(null); }
    } else S.holdFist = 0;

    // fingertips to the physics server for the v13 hand-shadow check, twice a second
    if (now - S.lastSend > 500) {
      S.lastSend = now;
      st().tool("set_hands", { points: world.flatMap((w) => [w[0], w[4], w[8], w[12], w[16], w[20], w[9]]) }, { record: false, quiet: true }).catch(() => {});
    }
    useStore.setState({ handCursor: { x, y, down: !!S.press, label } });
    return label;
  }

  function release() {
    const pr = S.press;
    if (!pr) return;
    S.press = null;
    const { x, y } = S.cur || { x: 0, y: 0 };
    if (pr.kind === "grab") { modal.moved() ? modal.finish() : modal.cancel(); }
    else if (pr.kind === "orbit") { if (Math.hypot(x - pr.x0, y - pr.y0) < 8) st().select(null); }
    else {
      const el = under(x, y);
      fire("pointerup", el || pr.el, x, y, 0);
      if (el && (el === pr.el || pr.el.contains(el) || el.contains(pr.el)) && Math.hypot(x - pr.x0, y - pr.y0) < 18) {
        const target = el.closest("button, a, input, select, textarea, [data-hand-target]") || el;
        if (/^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) target.focus();
        target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, clientX: x, clientY: y }));
      }
    }
  }
  return { step, release };
}

export function AirCursor() {
  const c = useStore((s) => s.handCursor);
  const mode = useStore((s) => s.mode);
  if (mode !== "hand" || !c) return null;
  const R = 15, circ = 2 * Math.PI * R;
  return (
    <div className="pointer-events-none fixed z-[70]" style={{ left: c.x, top: c.y }}>
      <svg width="44" height="44" className="-translate-x-1/2 -translate-y-1/2" style={{ filter: "drop-shadow(0 0 8px rgba(95,225,255,.8))" }}>
        <circle cx="22" cy="22" r={c.down ? 6 : 9} fill={c.down ? "#ff4fd8" : "rgba(95,225,255,.18)"} stroke="#5fe1ff" strokeWidth="1.6" />
        {c.hold > 0 && <circle cx="22" cy="22" r={R} fill="none" stroke="#5fe1ff" strokeWidth="2.2" strokeDasharray={`${c.hold * circ} ${circ}`} transform="rotate(-90 22 22)" />}
      </svg>
      {c.label && <div className="absolute left-4 top-4 whitespace-nowrap rounded-md bg-black/60 px-1.5 py-0.5 font-mono text-[10px] text-cyan-50">{c.label}</div>}
    </div>
  );
}

export default function HandTracker() {
  const mode = useStore((s) => s.mode);
  const video = useRef();
  const canvas = useRef();
  const [status, setStatus] = useState("starting camera…");

  useEffect(() => {
    if (mode !== "hand") return;
    let stop = false, raf = 0, stream, landmarker;
    const ctl = createHandController();
    window.__aetherHand = ctl;          // lets tests drive hand mode with recorded landmarks
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        video.current.srcObject = stream;
        await video.current.play();
        setStatus("loading hand model…");
        const fileset = await FilesetResolver.forVisionTasks("./mediapipe/wasm");
        landmarker = await HandLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: "./mediapipe/hand_landmarker.task", delegate: "GPU" },
          runningMode: "VIDEO", numHands: 2,
        });
        setStatus("tracking");
        loop();
      } catch (e) { setStatus("camera error: " + e.message); }
    })();

    function draw(hands) {
      const c = canvas.current, ctx = c.getContext("2d");
      ctx.clearRect(0, 0, c.width, c.height);
      for (const lm of hands) {
        ctx.strokeStyle = "rgba(95,225,255,.9)"; ctx.lineWidth = 2;
        for (const [a, b] of BONES) { ctx.beginPath(); ctx.moveTo((1 - lm[a].x) * c.width, lm[a].y * c.height); ctx.lineTo((1 - lm[b].x) * c.width, lm[b].y * c.height); ctx.stroke(); }
        ctx.fillStyle = "#ff4fd8";
        for (const p of lm) { ctx.beginPath(); ctx.arc((1 - p.x) * c.width, p.y * c.height, 2.4, 0, 7); ctx.fill(); }
      }
    }
    function loop() {
      if (stop) return;
      raf = requestAnimationFrame(loop);
      const v = video.current;
      if (!landmarker || v.readyState < 2) return;
      const hands = landmarker.detectForVideo(v, performance.now()).landmarks || [];
      draw(hands);
      ctl.step(hands);
    }
    return () => {
      stop = true; cancelAnimationFrame(raf);
      ctl.release();
      stream?.getTracks().forEach((t) => t.stop());
      landmarker?.close();
      useStore.setState({ handFrame: null, handCursor: null });
    };
  }, [mode]);

  if (mode !== "hand") return null;
  return (
    <div className="glass pointer-events-auto absolute bottom-[78px] z-20 w-[232px] overflow-hidden p-1.5" style={{ left: 332 }}>
      <div className="relative overflow-hidden rounded-xl bg-black">
        <video ref={video} className="aspect-[4/3] w-full -scale-x-100 object-cover opacity-50" muted playsInline />
        <canvas ref={canvas} width={640} height={480} className="absolute inset-0 h-full w-full" />
        <div className="absolute left-1.5 top-1.5 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[9.5px] text-cyan-glow">{status}</div>
      </div>
      <p className="px-1 pt-1.5 text-[10px] leading-snug text-silver">Grab from the front or the sides: on a real hologram a hand behind the object erases the parts in front of it.</p>
    </div>
  );
}
