# Meta AI Developer Hackathon 报名表（按总纲 v3 更新）

报名截止：马来西亚时间 10 月 26 日中午 11:59（名额满会提前关闭）。
建议：Indie developer 赛道，主题 "Push the Frontier"。下面英文可以直接粘贴，字数不够就从后往前删句子。

## Project idea

**AETHER Window: the software half of a true-holography project, built from first principles.**

AETHER's goal is a bank-card-sized device that puts a true hologram (full wavefront reconstruction, so your eyes can focus on it) into the room, with no headset and nothing sprayed into the air. Starting from the wave equation, we proved that with optics alone a true hologram is always a window (Window Law H1), calculated two new workarounds and closed both, and identified the one open door: making air emit light by itself at far lower intensity than today's plasma.

At this hackathon we build AETHER Window, Phase 0 of the roadmap. A standard webcam tracks the viewer's eyes and renders an off-axis view, so the laptop screen becomes a window: a 3D engine, solar system or DNA model floats in front of the glass and stays fixed in space as you move. You pinch to rotate, pull two hands apart to explode the model, and speak naturally ("take the engine apart", "what does the piston do?"). Llama via the Meta Model API turns speech into structured scene actions and spoken explanations, and SAM 3.1 turns real objects from the camera into explorable 3D. A built-in Window Law visualiser lets judges see exactly why every hologram is a window.

A working prototype already runs on Windows with zero install. During the event we move the AI layer onto Meta's models and add SAM 3.1 capture. We are honest on stage: Phase 0 is a per-eye rendering effect, Phase 1 is a window-scale true-hologram card, and the room-scale hologram needs a scientific discovery we name precisely but do not claim to have.

## Technical skill（如果表单有单独一栏）

Working prototype: per-eye off-axis projection (generalised perspective projection), iris-based depth estimation with One-Euro filtering, hand gesture interaction with ray-cast picking, an LLM-driven structured action layer with an offline fallback, and a live Window Law visualiser. Plus a first-principles physics study of true holography: Window Law H1 via Kirchhoff–Helmholtz, a new scattering-focus efficiency law H3 (efficiency ≤ N/N_total), a superoscillation cost analysis, and an air-emission screening that sets the discovery target.

## 一句话版（表单只给一行时用）

AETHER Window turns any laptop into a head-tracked holographic-style window controlled by hands, voice and Llama, as Phase 0 of a first-principles true-holography project.
