// 三个演示场景。单位全部是厘米，原点在屏幕中心，z 轴朝向观看者。
// 每个场景返回 { id, title, group, parts: [{ name, info, object, base, dir }], update(t, state) }
// explode 时零件沿 dir 移动 explode × dir；dir 的 z 分量要小，保证拆开后仍在漂浮舒适区内。
import * as THREE from 'three';

function mat(color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, metalness: 0.55, roughness: 0.38, ...opts });
}

// en = [英文名, 英文说明]，切到英文界面时显示；name 仍是零件的唯一标识
function part(group, parts, name, info, mesh, dir, en = []) {
  group.add(mesh);
  parts.push({ name, info, nameEn: en[0] || name, infoEn: en[1] || info, object: mesh, base: mesh.position.clone(), dir: new THREE.Vector3(...dir) });
}

export function buildEngine() {
  const group = new THREE.Group();
  const parts = [];
  const steel = 0x9aa4b1, dark = 0x4a5059, copper = 0xc07a3a;

  const block = new THREE.Mesh(new THREE.BoxGeometry(7, 3.2, 3), mat(dark));
  block.position.set(0, -0.6, 0);
  part(group, parts, '缸体', '发动机的骨架，里面是四个气缸，活塞在缸里上下运动。', block, [0, -0.6, 0], ['Engine block', 'The skeleton of the engine. It holds four cylinders where the pistons move up and down.']);

  const head = new THREE.Mesh(new THREE.BoxGeometry(7, 0.7, 2.7), mat(steel));
  head.position.set(0, 2.1, 0);
  part(group, parts, '气缸盖', '盖住气缸顶部，装着气门和火花塞，燃烧就发生在它下面。', head, [0, 3.2, 0], ['Cylinder head', 'Caps the cylinders and holds the valves and spark plugs. Combustion happens right below it.']);

  const pistons = [];
  [-2.4, -0.8, 0.8, 2.4].forEach((x, i) => {
    const p = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 1.1, 32), mat(0xd8dde3));
    p.position.set(x, 1.0, 0);
    part(group, parts, `活塞${i + 1}`, '燃烧把活塞往下推，再通过连杆把直线运动变成曲轴的旋转。', p, [0, 1.9, 0], [`Piston ${i + 1}`, 'Burning fuel pushes the piston down; the connecting rod turns that into crankshaft rotation.']);
    pistons.push(p);
    const plug = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.9, 16), mat(0xe9e3d0, { metalness: 0.1 }));
    plug.position.set(x, 2.9, 0);
    part(group, parts, `火花塞${i + 1}`, '在压缩到顶点时放电点火，点燃油气混合物。', plug, [0, 4.4, 0], [`Spark plug ${i + 1}`, 'Fires a spark at the top of compression to ignite the fuel-air mix.']);
  });

  const crank = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 8, 24), mat(steel));
  crank.rotation.z = Math.PI / 2;
  crank.position.set(0, -2.6, 0);
  part(group, parts, '曲轴', '把四个活塞的上下运动合成连续旋转，输出动力。', crank, [0, -1.8, 0], ['Crankshaft', 'Combines the up-and-down motion of four pistons into continuous rotation.']);

  const fly = new THREE.Mesh(new THREE.CylinderGeometry(1.6, 1.6, 0.4, 48), mat(steel));
  fly.rotation.z = Math.PI / 2;
  fly.position.set(4.3, -1.6, 0);
  part(group, parts, '飞轮', '很重的圆盘，靠惯性让转速平稳，也连着离合器。', fly, [2.2, 0, 0], ['Flywheel', 'A heavy disc whose inertia smooths the engine speed; it also connects to the clutch.']);

  const intake = new THREE.Mesh(new THREE.BoxGeometry(6, 0.8, 0.8), mat(copper));
  intake.position.set(0, 1.4, -1.9);
  part(group, parts, '进气歧管', '把空气均匀分配到四个气缸。', intake, [0, 0.4, -2.0], ['Intake manifold', 'Spreads incoming air evenly across the four cylinders.']);

  const exhaust = new THREE.Mesh(new THREE.BoxGeometry(6, 0.7, 0.7), mat(0x7a4b3a));
  exhaust.position.set(0, 0.6, 1.8);
  part(group, parts, '排气歧管', '把燃烧后的废气从四个气缸收集起来排出去。', exhaust, [0, -0.3, 0.6], ['Exhaust manifold', 'Collects burnt gas from the four cylinders and sends it out.']);

  return {
    id: 'engine', title: '四缸发动机', titleEn: 'Four-cylinder engine', group, parts,
    update(t, s) {
      if (!s.running) return;
      // 点火顺序 1-3-4-2：相邻相位差 180°
      const phase = [0, Math.PI, Math.PI, 0];
      pistons.forEach((p, i) => { p.position.y += 0.45 * Math.sin(t * 8 + phase[i]); });
      crank.rotation.x = t * 8;
      fly.rotation.x = t * 8;
    },
  };
}

export function buildSolar() {
  const group = new THREE.Group();
  const parts = [];
  const sun = new THREE.Mesh(new THREE.SphereGeometry(1.3, 48, 32),
    new THREE.MeshStandardMaterial({ color: 0xffc35a, emissive: 0xff9a1f, emissiveIntensity: 1.2 }));
  part(group, parts, '太阳', '太阳系质量的 99.86% 都在它身上。', sun, [0, 0, 0], ['Sun', 'Holds 99.86% of all the mass in the solar system.']);
  const planets = [
    ['水星', '离太阳最近，一年只有 88 天。', 0.22, 2.0, 0xa59c94, 4.1, ['Mercury', 'Closest to the Sun; a year lasts only 88 days.']],
    ['金星', '浓厚的二氧化碳大气让它成为最热的行星。', 0.34, 2.7, 0xe8c27a, 1.6, ['Venus', 'Its thick carbon-dioxide air makes it the hottest planet.']],
    ['地球', '目前已知唯一有生命的星球。', 0.36, 3.4, 0x3f7fd9, 1.0, ['Earth', 'The only planet known to have life.']],
    ['火星', '红色来自表面的氧化铁。', 0.26, 4.1, 0xc1502e, 0.53, ['Mars', 'Its red colour comes from iron oxide on the surface.']],
    ['木星', '最大的行星，体积是地球的 1300 多倍。', 0.75, 5.2, 0xd2a77a, 0.084, ['Jupiter', 'The largest planet, more than 1,300 Earths by volume.']],
  ];
  const orbiters = [];
  for (const [name, info, r, a, color, speed, en] of planets) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(r, 32, 24), mat(color, { metalness: 0.1, roughness: 0.8 }));
    m.position.set(a, 0, 0);
    part(group, parts, name, info, m, [0, 0, 0], en);
    orbiters.push({ m, a, speed });
    const ring = new THREE.Mesh(new THREE.TorusGeometry(a, 0.015, 6, 128),
      new THREE.MeshBasicMaterial({ color: 0x5a6a80 }));
    ring.rotation.x = Math.PI / 2;
    group.add(ring);
  }
  group.rotation.x = 0.35;
  return {
    id: 'solar', title: '太阳系', titleEn: 'Solar system', group, parts,
    update(t, s) {
      // explode 在这里表示把轨道拉开看清楚
      const k = 1 + 0.6 * s.explode;
      const speed = s.running ? 1 : 0.15;
      for (const o of orbiters) {
        const ang = t * o.speed * speed;
        o.m.position.set(Math.cos(ang) * o.a * k, 0, Math.sin(ang) * o.a * k * 0.75);
      }
    },
    skipExplode: true,
  };
}

export function buildDNA() {
  const group = new THREE.Group();
  const parts = [];
  const strandA = new THREE.Group(), strandB = new THREE.Group(), rungs = new THREE.Group();
  const colors = [0xe0574f, 0x4fb3e0, 0xf2c94c, 0x6fcf97];
  const n = 22, rise = 0.42, radius = 1.4;
  for (let i = 0; i < n; i++) {
    const a = i * 0.6, y = (i - n / 2) * rise;
    const pa = new THREE.Vector3(Math.cos(a) * radius, y, Math.sin(a) * radius * 0.6);
    const pb = new THREE.Vector3(Math.cos(a + Math.PI) * radius, y, Math.sin(a + Math.PI) * radius * 0.6);
    const sa = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 12), mat(0xdfe6ee, { metalness: 0.2 }));
    sa.position.copy(pa); strandA.add(sa);
    const sb = new THREE.Mesh(new THREE.SphereGeometry(0.22, 16, 12), mat(0xdfe6ee, { metalness: 0.2 }));
    sb.position.copy(pb); strandB.add(sb);
    const len = pa.distanceTo(pb);
    const rung = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, len, 8), mat(colors[i % 4], { metalness: 0.1 }));
    rung.position.copy(pa).add(pb).multiplyScalar(0.5);
    rung.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), pb.clone().sub(pa).normalize());
    rungs.add(rung);
  }
  part(group, parts, '主链A', '由脱氧核糖和磷酸交替连接成的骨架。', strandA, [-2.2, 0, 0], ['Backbone A', 'A chain of alternating sugar and phosphate.']);
  part(group, parts, '主链B', '与主链A方向相反，两条链靠碱基配对结合。', strandB, [2.2, 0, 0], ['Backbone B', 'Runs opposite to backbone A; the two are held together by base pairs.']);
  part(group, parts, '碱基对', 'A 配 T，G 配 C，排列顺序就是遗传信息。', rungs, [0, 0, 0.4], ['Base pairs', 'A pairs with T, G pairs with C. Their order is the genetic code.']);
  group.rotation.z = 0.25;
  return {
    id: 'dna', title: 'DNA 双螺旋', titleEn: 'DNA double helix', group, parts,
    update(t, s) { if (s.running) group.rotation.y = t * 0.6; },
  };
}

export const SCENES = { engine: buildEngine, solar: buildSolar, dna: buildDNA };
