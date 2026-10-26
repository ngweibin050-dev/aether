# AETHER Window：3 分钟 demo 录像稿

英文是你要说的台词，【】里是中文操作提示。总长约 3 分钟，每段后面是建议时长。

## 录之前准备

- 【用 Chrome，按 L 切到英文界面，按 C 和 D 校准，按 F 全屏】
- 【光线：脸和手都要亮，窗户不要在你身后】
- 【准备一个颜色鲜艳的小物体（杯子、玩具、水果），后面放一面素色的墙或一张白纸】
- 【录屏用 OBS 或 Xbox Game Bar（Win + G）。另外最好用手机从你肩膀后面拍屏幕，因为“物体固定在空间里”的效果只有从旁边拍才看得出来，录屏看不出】
- 【如果手势现场不稳，按 M 用鼠标代替头部移动，照样能讲】
- 【拿到 Meta key 之前，语音指令走本地关键词，台词里的指令都能用】

## 1. 开场（0:00–0:20）

"This is AETHER Window: a normal laptop and webcam turned into a head-tracked 3D window you control with your hands and voice. To be clear, it is a rendering illusion, not a hologram. It is the software first step of a longer project that asks what it would physically take to put a true hologram into a room."

【对着镜头，画面里是发动机】

## 2. 屏幕变成一扇窗（0:20–0:50）

"A normal webcam tracks my eyes. The screen is rendered as a window into a 3D room, so when I move my head, the engine stays fixed in space, like a real object behind glass."

【慢慢左右移动头，再前后移动。手机从旁边拍效果最好】

## 3. 手和语音（0:50–1:30）

"I can grab it." 【单手捏合，拖动旋转】

"Pull it apart." 【两只手同时捏合，往两边拉开】

"Or just ask." 【按住空格说】 "What does the piston do?"

【活塞高亮，AETHER 读出解释】

"The language model never touches the 3D scene directly. It can only return a fixed set of actions, like explode, rotate or select, so it cannot break anything. Here Llama, through the Meta Model API, is the brain of the scene."

【只有 Llama 真的接上后才说最后一句；没接上就改说："Today this runs on on-device keywords; Llama plugs into the same action layer."】

## 4. 真实物体变 3D（1:30–2:05）

"Now a real object." 【按 P，把物体放进虚线框，等倒数】

"The camera cuts it out and turns it into a 3D card inside the window. Segmentation is pluggable: here it uses Meta's SAM."

【只有 SAM 真的接上后才说最后一句；没接上就改说："Today it uses a local segmenter; SAM plugs into the same step."】 【捏合转一下，说 "take it apart" 看分层】

## 5. 两个人一起看（2:05–2:25）

"Head tracking only works for one pair of eyes. So we split the screen into two windows, each rendered for one person." 【按 T，让朋友坐到旁边，两人各看自己那半边】

## 6. 物理：为什么全息是一扇窗（2:25–2:55）

【按 W】

"This visualises the main constraint in our physics analysis. Applying the known Kirchhoff–Helmholtz integral, we derived that a true hologram from a small device behaves like a window: you only see a point if the line from your eye through it passes through the device. Move your head, and the object is clipped at the edge of the card. It is a candidate result we are still testing, and the scripts are in our repository."

【慢慢移动头，让物体被裁掉，右上角的俯视图会变色】

"So our long-term product goal is a window-scale true hologram in a bank card. Our open research question is whether air itself could be made to emit light at intensities far below today's plasma. That is a hypothesis, not a result."

## 7. 结尾（2:55–3:00）

"AETHER. A 3D window today, a path toward true holography."

## 备用短句（出状况时用）

- 手势没反应："Lighting is tricky for a single webcam, so I'll use the mouse viewpoint." 【按 M】
- AI 没反应："It falls back to on-device commands when the network is slow."
- 抠图不干净："The local cut-out needs a plain background; SAM 3.1 removes that limit."
