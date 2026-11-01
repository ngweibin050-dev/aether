# AETHER Lab（中文摘要）

一张纸上的机械图纸 → 一台能动的三维机器。英文完整说明见 [README.md](README.md)，所有数字见 [docs/RESULTS.md](docs/RESULTS.md)。

- **Muse Spark** 读图（整张图 + 4 个放大区域，各读两次，两次一致或图纸确认才保留零件），并逐步讲解这台机器（每个零件编号和数字都由代码核对）。
- **Muse Wonder**（medium）补全图纸没画出的部分：深度、隐藏的轴和轴承、哪些齿轮啮合，每个补加零件都有理由。
- **Muse Image** 画一张概念插图，始终标注"AI 插图，不是测量模型"。
- **Muse Voice Transcribe** 接收语音指令；**SAM 3.1** 从照片里抠出零件。
- 引擎把每个零件重建成实体（渐开线齿轮真正啮合），可导出 GLB / STL 和一页报告。
- 最后用波动光学人眼模型检查每个零件在 AETHER 全息桌上的清晰度。**这是仿真，没有造出任何全息显示器。**

专利图纸没有比例尺，所以尺寸都是"模型比例，真实尺寸未知"。长期全息路线见 [docs/HOLOGRAPHY_ROADMAP.md](docs/HOLOGRAPHY_ROADMAP.md)。

运行：`python server.py`，打开 http://localhost:8765（Meta key 放在 `.env`，绝不提交）。测试：`python tests/test_physics.py`（35 项）。
