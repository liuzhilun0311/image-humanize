# 图片自然化 (image-humanize)

对已有图片进行自然质感后处理，包括颗粒、色彩调整、缩放重采样、重压缩和元数据清理。
不生成新图片、不判断图片是否由 AI 生成，也不保证移除隐藏水印或通过任何来源检测。

英文调用标识是 `$image-humanize`，界面显示为“图片自然化 (image-humanize)”。

## 安装与依赖

将完整技能目录放入宿主的用户技能目录并刷新。
需要 Python 3.10+、Pillow 和 NumPy；安装依赖可能需要网络，依赖齐全后可离线处理。
不需要图片服务 API Key、ImageMagick、ExifTool 或 Bash。

从技能目录运行以下命令；在其他目录运行时，使用脚本和依赖文件的实际绝对路径。

```text
python scripts/check_deps.py
python -m pip install -r requirements.txt
python scripts/check_deps.py
```

上述命令使用当前 `python` 对应的环境；不要在未确认的全局环境中安装依赖。
隔离环境和更多选项见 [使用说明](references/usage.md)。

## 输入与调用

提供已有图片路径，或需要批处理的目录。
默认使用 `medium`；保留细节可选 `light`，明显颗粒可选 `heavy`。

```text
使用 $image-humanize 处理我上传的图片，采用 light 档，
保留原图，将结果另存到我指定的目录。
```

```text
使用 $image-humanize 批量处理这个图片目录，
只清理元数据，不改变质感，并汇总成功和失败的文件。
```

## 手工运行

以下输入路径需要替换为真实文件，命令从技能目录执行。

```text
python scripts/humanize.py "input.png" --strength light -o "output.png"
python scripts/humanize.py "input.jpg" --strength medium --seed 42
python scripts/humanize.py "images" --batch --recursive -o "results"
python scripts/humanize.py "input.png" --metadata-only -o "clean.png"
```

需要报告时：

```text
python scripts/humanize.py "images" --batch -o "results" --report "results/report.json"
```

## 输出

单图默认另存为 `<原名>_humanized.png` 或 `.jpg`，批量默认使用输入目录中的 `humanized_output`。
透明图片自动采用 PNG；明确输出 JPEG 时，透明区域会合成到背景色。
报告包含输入输出摘要、尺寸、格式、处理参数和逐文件成功或失败结果，不包含 AI 检测结论。

## 注意事项

- 原图不会被原地修改，已有输出默认拒绝覆盖。
- 仅清理元数据仍会解码并重新编码，JPEG 不属于无损复制。
- EXIF、XMP、ICC 等输入元数据不会直接复制，不适合必须保留原始 ICC 的任务。
- 动图、多页图片和无法解码的文件会报错，不会静默丢弃其他帧。
- 批量处理中会继续处理其他文件，但任何失败都会反映到汇总和退出码。

详细规则见 [SKILL.md](SKILL.md)，依赖见 [requirements.txt](requirements.txt)，许可证及上游出处见 [LICENSE](LICENSE)。
