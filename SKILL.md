---
name: image-humanize
description: 对已有图片进行自然质感后处理，支持轻中重三档颗粒、色彩调整、缩放与重压缩，以及重新编码清理附带元数据。用于改善 AI 图片过度平滑的质感、批量导出和图片隐私清理；不生成图片、不检测 AI 来源，不保证移除像素水印或通过 AI 检测。
---

# 图片自然化

基于 humanize-image / deai-image 的后处理思路，使用一个跨平台 Python 入口。无需 API Key、联网模型、ImageMagick、ExifTool 或 Bash；首次使用仍需要安装 Python 3.10+、Pillow 和 NumPy。安装依赖需要网络，完成后处理可离线运行。

## 首次运行

命令中的 `<skill-dir>` 必须替换为本技能所在的真实绝对路径，不要以当前工作目录猜测脚本位置。选择实际可用的 Python 3.10+ 解释器；以下示例使用 `python`，macOS/Linux 可能需要 `python3`，Windows 可使用 `py -3`。

```bash
python "<skill-dir>/scripts/check_deps.py"
python -m pip install -r "<skill-dir>/requirements.txt"
python "<skill-dir>/scripts/check_deps.py"
```

检查缺失时给出该解释器对应的安装命令。用户要求安装或已经授权安装环境时执行安装；否则说明缺什么。不要宣称技能文件自带 Python 或已经自动装好依赖。不要静默修改全局环境；需要隔离时按 [references/usage.md](references/usage.md) 创建虚拟环境。

## 图片处理

输入必须是已有图片或目录。图片自然化默认 `medium`；用户强调保留细节时用 `light`，明显颗粒效果时用 `heavy`。完整流程：按 EXIF 方向转正 → 颗粒 → 色彩 → 模糊/锐化 → 缩小再放大 → JPEG 重压缩（不适用于保留透明度的 PNG）→ 重建像素容器另存。

```bash
python "<skill-dir>/scripts/humanize.py" "input.png" --strength light -o "output.png"
python "<skill-dir>/scripts/humanize.py" "input.jpg" --strength medium --seed 42
python "<skill-dir>/scripts/humanize.py" "images" --batch --recursive -o "results"
python "<skill-dir>/scripts/humanize.py" "input.png" --metadata-only -o "clean.png"
```

默认输出 `<原名>_humanized.png` 或 `.jpg`，批量输出到输入目录中的 `humanized_output`；同名不同格式输入会保留原扩展名作为输出文件名的一部分。透明图片自动使用 PNG，JPEG 明确指定时用白色或 `--background "#RRGGBB"` 合成背景。详见 [references/usage.md](references/usage.md)，有需要时再读取。

## 操作约束

- 原图永远不原地修改；即使 `--overwrite` 也不能把输出指向输入。现有输出默认拒绝覆盖；仅在用户要求替换输出时使用 `--overwrite`。
- `--metadata-only`（兼容旧参数 `--no-metadata`）跳过质感变化，但仍解码与重新编码，JPEG 不是无损复制。保留方向显示效果，不复制 EXIF、XMP、ICC 等输入元数据；不承诺清除像素内隐藏水印。重新编码会改变色彩管理，不适合要求保留原始 ICC 的工作。
- 不把处理后的图称为真实相机照片；不提供虚构的检测通过率。用户需要检测评分时说明本技能没有检测器。
- 动图、多页图和无法读取的文件会报错，不静默丢弃帧。批处理继续其他文件，汇总每个失败；任意失败返回非零退出码。
- 通过退出码、输出图片和 JSON 报告确认结果；目录存在或打印了进度不代表成功。保留原图，查看颗粒、颜色、边缘和透明区域；报告实际处理档位、输出路径和失败。

## 报告

```bash
python "<skill-dir>/scripts/humanize.py" "images" --batch -o "results" --report "results/report.json"
```

报告含逐图输入/输出 SHA-256、尺寸、格式、处理参数、成功/失败列表；报告不包含 AI 检测结论。只展示用户需要的输出链接和简短结果。

许可证及上游出处见 `LICENSE`。
