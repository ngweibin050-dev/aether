# AETHER Window（中文说明）

英文完整说明见 README.md。这里是自己用的简要版。

## 运行

1. 电脑要有 Node.js（没有就到 https://nodejs.org 装 LTS 版）。
2. 双击 `start.bat`，浏览器会打开 http://localhost:8787 ，允许摄像头。
3. 第一次用：按 C 用银行卡校准屏幕大小；坐在 50 cm 处按 D 校准距离；按 F 全屏。

## 拿到 Meta 的 key 之后

1. 打开 `ai.config.json`，把 key 填进 `chat` 里的 `"apiKey": ""` 引号中间。
2. 如果比赛方文档给的模型名或网址不一样，改 `model` 和 `baseUrl`。
3. 保存，关掉黑色窗口，重新双击 `start.bat`。左上角会显示正在用哪个模型。

SAM 3.1：拿到接口后，把 `segment` 里的 `provider` 改成 `"http"`，`url` 填接口地址。如果它的请求格式不一样，改 `server.mjs` 里的 `callSegmenter()` 一个函数就行。

`ai.config.json` 不会被 git 上传，key 只留在你的电脑上。

## 新功能

| 键 | 功能 |
| --- | --- |
| P 或 📷 | 360° 扫描成 3D 模型：倒数 3 秒后，把物体放在虚线框里慢慢原地转一圈，转完再按 P。系统会自动认出物体、去掉你的手，用各个角度的轮廓雕出立体网格并上色 |
| E | 把扫描出的模型导出成 .obj（Blender、Windows 3D 查看器能打开） |
| 4 | 回到上一次扫描的物体 |
| T | 双人观看：屏幕分成左右两扇窗，左边的人看左半屏，右边的人看右半屏 |
| L | 中文 / English 切换（界面、语音识别、朗读都会换） |
| W | 窗口定律演示 |

其他键和以前一样：M 鼠标模式、S 红蓝立体、V 摄像头画面、1 2 3 换场景、R 重置、空格按住说话、H 帮助。

## 没有 key 时

语音和文字指令用本地关键词兜底，中英文都可以，例如“拆开”“太阳系”“拍照”，或 "take it apart"、"solar system"、"take a photo"。
