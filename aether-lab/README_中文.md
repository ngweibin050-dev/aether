# AETHER Lab 使用说明（中文）

1. 确认电脑有 Python 3.11 以上。
2. `.env` 里要有 `META_API=你的key`（放在 aether-lab 文件夹或上一层 C:\Aether 都可以）。
3. 双击 `start.bat`，浏览器会打开 http://localhost:8765
4. 先拖滑杆，按 “Calculate hologram”，再按 “Focus sweep”，拖动下方滑杆看对焦变化。
5. 在 “Ask AETHER” 输入英文或中文问题，或者点下方示例按钮。

物理测试：在此文件夹打开命令行，运行 `python -m tests.test_physics`（16 项）。

2.2 新增：
- 清晰度 = 同一焦距下 1D 桌面 ÷ 全 2D 全息（全 2D = 100%）；斜视清晰区 −108…+87 mm。
- 图纸 → 按零件类型重建 3D（标准渐开线齿轮、销、框架分层）；每个尺寸标明来源（图上读到 / 测量 / 假设）。
- 选中齿轮可按 ↺ ↻ 或 Run 让相啮合的齿轮一起转。
- 场景面板：上传按钮可导入 STL / OBJ / GLB（保持真实毫米）；“3V” 按钮导入三视图（主视、俯视、右视）生成实体。
- 物理面板 “Desk wave check”：真实尺寸 1D 桌面波动仿真，验证眼模型。
- 改了 engine 后请重新 `modal deploy modal_app.py`（Windows 下先 `set PYTHONUTF8=1`）。
