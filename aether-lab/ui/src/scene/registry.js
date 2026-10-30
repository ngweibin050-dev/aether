// id -> THREE.Object3D for every part, so the gizmo, the G/R/S modal and the hand controller can move them directly.
export const objects = new Map();
// The live camera, canvas and navigation controller, shared with code outside the <Canvas> (hand mode, nav gizmo).
export const view = { camera: null, dom: null, nav: null, hitPart: false, scene: null };
