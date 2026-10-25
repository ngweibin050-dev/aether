# Meta Global AI Developer Hackathon：报名表草稿

报名截止：美东时间 10 月 25 日 23:59（马来西亚时间 10 月 26 日中午 11:59），名额满 20,000 会提前关闭。

建议：Indie developer 赛道，主题选 "Push the Frontier"。

## Project idea（可直接粘贴，按表单字数删减）

**AETHER Window: a floating 3D display you control with your hands and voice, running on any laptop.**

Sci-fi "holograms in thin air" are physically impossible: clean air scatters almost no light, so a point in empty space can only be seen if light reaching the eye comes from behind it. We derived from first principles that the only mass-producible way to make objects appear to float is to send the correct rays into each eye separately. AETHER Window is the software version of that idea. A standard webcam tracks the viewer's irises, estimates each eye's 3D position, and renders an off-axis view so the screen becomes a window: a 3D object floats up to 4 cm in front of the glass and stays fixed in space as you move your head.

You interact without touching anything. Pinch to grab and rotate, pull two hands apart to explode an engine into its parts, point at a part to highlight it. You can also speak naturally ("take the engine apart", "what does the piston do?"). Meta's models turn speech into structured scene actions and spoken explanations, and SAM 3.1 can segment real objects from the camera so they can be turned into explorable 3D scenes.

A working prototype already runs in the browser (Three.js + MediaPipe). During the 10 days we will move the AI layer onto the Meta Model API, add glasses-free viewing with an off-the-shelf lenticular film, and support two viewers at once. Long term this becomes AETHER, a credit-card-sized floating display (microlens light-field optics, ~2 W) with AI running in the cloud.

## Technical skill（如果表单有单独一栏）

Working prototype: per-eye off-axis projection (generalized perspective projection), iris-based depth estimation with One-Euro filtering, two-hand gesture recognition with ray-cast picking, an LLM-driven structured action layer with an offline fallback, and anaglyph stereo rendering. Plus a first-principles physics study of free-space displays (scattering limits, aperture-cone law, accommodation tolerance) that sets the design constraints.
