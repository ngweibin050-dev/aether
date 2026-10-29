import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";
import { useStore } from "../store";
import { objects } from "../scene/registry";

// Interaction volume above the desk (mm). Camera image x -> desk x, image y -> height z,
// apparent hand size -> desk y (closer to the camera = toward the user).
const VOL = { x: 520, zMin: 0, zMax: 170, yNear: -160, yFar: 160 };
const PINCH = 0.33;          // thumb-index distance / palm size
const BONES = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];

const d2 = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

function toDesk(lm) {
  const palm = d2(lm[0], lm[9]) || 0.1;
  const depth = THREE.MathUtils.clamp((palm - 0.12) / 0.16, 0, 1);       // 0 far .. 1 near
  return lm.map((p) => [
    (0.5 - p.x) * VOL.x,                                               // mirrored like a selfie
    VOL.yFar + (VOL.yNear - VOL.yFar) * depth,
    VOL.zMin + (1 - p.y) * (VOL.zMax - VOL.zMin),
  ]);
}

function gestureOf(lm) {
  const palm = d2(lm[0], lm[9]) || 0.1;
  const pinch = d2(lm[4], lm[8]) / palm < PINCH;
  const ext = (tip, pip) => d2(lm[tip], lm[0]) > d2(lm[pip], lm[0]) * 1.15;
  const fingers = [ext(8, 6), ext(12, 10), ext(16, 14), ext(20, 18)];
  const open = fingers.every(Boolean) && !pinch;
  const fist = fingers.every((f) => !f);
  return { pinch, open, fist };
}

export default function HandTracker() {
  const mode = useStore((s) => s.mode);
  const video = useRef();
  const canvas = useRef();
  const [status, setStatus] = useState("starting camera…");
  const [gesture, setGesture] = useState("");

  useEffect(() => {
    if (mode !== "hand") return;
    let stop = false, raf = 0, stream, landmarker;
    let grab = null, two = null, holdOpen = 0, holdFist = 0, lastSend = 0;
    const st = useStore.getState;

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
        ctx.fillStyle = "#a78bfa";
        for (const p of lm) { ctx.beginPath(); ctx.arc((1 - p.x) * c.width, p.y * c.height, 2.5, 0, 7); ctx.fill(); }
      }
    }

    function nearestPart(pt) {
      let best = null, bd = 140;
      const v = new THREE.Vector3();
      for (const [id, o] of objects) {
        if (!o) continue;
        o.getWorldPosition(v);
        const d = v.distanceTo(new THREE.Vector3(...pt));
        if (d < bd) { bd = d; best = id; }
      }
      return best;
    }

    function commit(id, o) {
      const r = o.rotation;
      st().commitTransform(id, {
        position: o.position.toArray().map((v) => +v.toFixed(2)),
        rotation: [r.x, r.y, r.z].map((v) => +THREE.MathUtils.radToDeg(v).toFixed(2)),
        scale: o.scale.toArray().map((v) => +v.toFixed(3)),
      });
    }

    function loop() {
      if (stop) return;
      raf = requestAnimationFrame(loop);
      const v = video.current;
      if (!landmarker || v.readyState < 2) return;
      const res = landmarker.detectForVideo(v, performance.now());
      const hands = res.landmarks || [];
      draw(hands);
      const world = hands.map(toDesk);
      const g = hands.map(gestureOf);
      st().setHandFrame({ world, pinch: g.map((x) => x.pinch) });
      const pinchPt = (i) => world[i].map((_, k) => (world[i][4][k] + world[i][8][k]) / 2);
      const sel = st().state?.selected;
      const obj = sel && objects.get(sel);

      // two-hand pinch: rotate about the vertical axis + scale
      if (hands.length === 2 && g[0].pinch && g[1].pinch && obj) {
        const a = pinchPt(0), b = pinchPt(1);
        const ang = Math.atan2(b[1] - a[1], b[0] - a[0]), dist = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
        if (!two) two = { ang, dist, rot: obj.rotation.z, scale: obj.scale.clone() };
        obj.rotation.z = two.rot + (ang - two.ang);
        obj.scale.copy(two.scale).multiplyScalar(THREE.MathUtils.clamp(dist / two.dist, 0.3, 3));
        setGesture("rotate + scale");
        grab = null;
        return;
      }
      if (two && obj) { commit(sel, obj); two = null; }

      // one-hand pinch: select nearest part, then drag it
      const h = g.findIndex((x) => x.pinch);
      if (h >= 0) {
        const p = pinchPt(h);
        if (!grab) {
          const id = obj ? sel : nearestPart(p);
          if (id && id !== sel) st().select(id);
          const o = id && objects.get(id);
          if (o) grab = { id, start: p, pos: o.position.clone() };
        } else {
          const o = objects.get(grab.id);
          if (o) o.position.set(grab.pos.x + p[0] - grab.start[0], grab.pos.y + p[1] - grab.start[1], grab.pos.z + p[2] - grab.start[2]);
          setGesture("grab · move");
        }
      } else if (grab) {
        const o = objects.get(grab.id);
        if (o) commit(grab.id, o);
        grab = null;
      }

      // both palms open for 1 s -> calculate hologram; fist for 0.8 s -> deselect
      const now = performance.now();
      if (hands.length === 2 && g.every((x) => x.open)) {
        holdOpen ||= now;
        setGesture("hold open palms → hologram");
        if (now - holdOpen > 1000) { holdOpen = Infinity; st().tool("make_hologram").then(() => st().tool("focus_sweep", { steps: 9 })); }
      } else holdOpen = 0;
      if (hands.length === 1 && g[0].fist && !grab) {
        holdFist ||= now;
        if (now - holdFist > 800) { st().select(null); holdFist = Infinity; setGesture("deselect"); }
      } else holdFist = 0;
      if (!hands.length) setGesture("");
      else if (h < 0 && !g.some((x) => x.open) && !g.some((x) => x.fist)) setGesture("hover");

      // fingertips to the physics server (hand occlusion check), 2x per second
      if (now - lastSend > 500 && world.length) {
        lastSend = now;
        st().tool("set_hands", { points: world.flatMap((w) => [w[0], w[4], w[8], w[12], w[16], w[20], w[9]]) }, { record: false, quiet: true }).catch(() => {});
      }
    }

    return () => {
      stop = true; cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
      landmarker?.close();
      useStore.getState().setHandFrame(null);
    };
  }, [mode]);

  if (mode !== "hand") return null;
  return (
    <div className="glass pointer-events-auto absolute bottom-24 left-4 z-20 w-[300px] overflow-hidden p-2.5 animate-floatin">
      <div className="relative overflow-hidden rounded-xl bg-black">
        <video ref={video} className="aspect-[4/3] w-full -scale-x-100 object-cover opacity-60" muted playsInline />
        <canvas ref={canvas} width={640} height={480} className="absolute inset-0 h-full w-full" />
        <div className="absolute left-2 top-2 rounded-md bg-black/60 px-2 py-0.5 font-mono text-[10.5px] text-cyan-glow">{status}</div>
        {gesture && <div className="absolute bottom-2 left-2 rounded-md bg-cyan-glow/20 px-2 py-0.5 font-mono text-[11px] text-white">{gesture}</div>}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-slate-400">
        <span><b className="text-slate-200">Pinch</b> grab / move</span>
        <span><b className="text-slate-200">2-hand pinch</b> rotate · scale</span>
        <span><b className="text-slate-200">Fist</b> deselect</span>
        <span><b className="text-slate-200">Both palms</b> hologram</span>
      </div>
      <p className="mt-1.5 text-[10.5px] leading-snug text-slate-500">Work from the front and sides: on a real hologram a hand behind the object erases the parts in front of it.</p>
    </div>
  );
}
