import * as THREE from "three";

// Shared clock for every hologram material (updated once per frame by <HoloClock/>).
export const holoTime = { value: 0 };
export const holoSweep = { value: 0 }; // world z of the rising scan line

const vert = /* glsl */ `
#include <common>
#include <clipping_planes_pars_vertex>
varying vec3 vN; varying vec3 vV; varying vec3 vW;
void main() {
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  vN = normalMatrix * normal;                 // normalised in the fragment shader (zero normals stay safe)
  vV = -mvPosition.xyz;
  vW = (modelMatrix * vec4(position, 1.0)).xyz;
  gl_Position = projectionMatrix * mvPosition;
  #include <clipping_planes_vertex>
}`;

const frag = /* glsl */ `
#include <common>
#include <clipping_planes_pars_fragment>
uniform vec3 uColor; uniform float uTime; uniform float uSweep; uniform float uOpacity; uniform float uRim;
varying vec3 vN; varying vec3 vV; varying vec3 vW;
void main() {
  #include <clipping_planes_fragment>
  // guard against NaN (zero normal, |dot| > 1 by rounding, pow of a negative base): the bloom pass
  // spreads one NaN pixel over the whole frame and the screen goes black
  vec3 n = vN / max(length(vN), 1e-6), v = vV / max(length(vV), 1e-6);
  float facing = clamp(abs(dot(n, v)), 0.0, 1.0);
  float rim = pow(max(1.0 - facing, 0.0), 2.4) * uRim;                // fresnel edge light
  float lines = smoothstep(0.92, 1.0, abs(sin(vW.z * 0.9)));          // fine horizontal raster
  float ds = (vW.z - uSweep) * 0.35;
  float sweep = exp(-ds * ds);                                        // the scan band (pow() of a negative base is NaN in GLSL)
  float flick = 0.94 + 0.06 * sin(uTime * 37.0 + vW.z * 0.2);
  // low base fill: many overlapping parts add up (additive), so keep the body faint and let the rim carry the shape
  vec3 c = uColor * (0.045 + rim * 1.1 + lines * 0.06 + sweep * 0.6) * flick;
  float a = uOpacity * clamp(0.05 + rim * 0.8 + lines * 0.04 + sweep * 0.4, 0.0, 1.0);
  gl_FragColor = vec4(clamp(c, 0.0, 4.0), clamp(a, 0.0, 1.0));
}`;

export function holoMaterial({ color = "#38d9ff", opacity = 1, rim = 1, clip = null } = {}) {
  const m = new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(color) }, uTime: holoTime, uSweep: holoSweep, uOpacity: { value: opacity }, uRim: { value: rim } },
    vertexShader: vert, fragmentShader: frag,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
  m.clipping = true;
  m.clippingPlanes = clip;
  return m;
}

// Soft vertical light: a column that fades upward, used for the projection volume above the desk panel.
export function beamMaterial(color = "#4fd6ff", strength = 0.16) {
  return new THREE.ShaderMaterial({
    uniforms: { uColor: { value: new THREE.Color(color) }, uS: { value: strength }, uTime: holoTime },
    vertexShader: /* glsl */ `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
    fragmentShader: /* glsl */ `uniform vec3 uColor; uniform float uS; uniform float uTime; varying vec2 vUv;
      void main(){ float h = vUv.y; float edge = smoothstep(0.0, 0.18, vUv.x) * smoothstep(1.0, 0.82, vUv.x);
        float a = uS * pow(clamp(1.0 - h, 0.0, 1.0), 1.6) * (0.55 + 0.45 * edge) * (0.9 + 0.1 * sin(uTime * 2.0 + h * 9.0));
        gl_FragColor = vec4(uColor * a * 2.0, a); }`,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
}
