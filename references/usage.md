# 安装与参数

## 可分发的内容

把整个 `image-humanize` 目录交给别人，包括 SKILL.md、agents、scripts、requirements.txt、references 和 LICENSE。接收者把目录放入所用客户端的技能目录；仅下载到任意仓库目录不等于该客户端已加载技能。脚本也可以独立通过 Python 运行。

此目录不包含 Python 或依赖包。所需依赖仅为 Python 3.10+、Pillow 和 NumPy；无需安装 ImageMagick、ExifTool。检查脚本使用标准库，缺少图片库时仍能输出安装建议。

## 推荐隔离安装

以下命令从技能目录运行，不需要管理员权限：

```bash
python -m venv .venv
```

Windows：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/check_deps.py
.\.venv\Scripts\python.exe scripts/humanize.py "D:\图片\示例.png"
```

macOS/Linux：

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/check_deps.py
.venv/bin/python scripts/humanize.py "/path/to/image.png"
```

以后用同一个虚拟环境解释器执行。离线机器必须提前准备与其系统、Python 版本匹配的依赖 wheel；技能本身不会下载依赖。

## CLI

| 参数 | 行为 |
|---|---|
| `input` | 单图路径，或配合 --batch 使用的目录 |
| `-o, --output` | 单图输出文件，或批量输出目录；不存在的父目录自动创建 |
| `--strength light/medium/heavy` | 默认 medium |
| `--format auto/jpg/png` | 自动按透明度选择；输出后缀明确时尊重后缀 |
| `--background "#RRGGBB"` | 透明图转 JPEG 的背景色；默认白色 |
| `--seed N` | 固定随机噪声；相同输入、参数与运行环境可重复 |
| `--metadata-only` | 重新编码，不执行颗粒/色彩/缩放 |
| `--no-metadata` | 旧参数别名，等同 metadata-only |
| `--batch` | 批量处理 PNG/JPEG/WebP/BMP/TIFF；不重复处理大小写扩展 |
| `--recursive` | 递归目录，保持相对目录层级；需 --batch |
| `--overwrite` | 允许替换已有输出，始终禁止覆盖原图 |
| `--report FILE` | 保存 UTF-8 JSON；不得覆盖图片输入或输出 |
| `-q, --quiet` | 隐藏成功进度；错误仍写入 stderr |

PNG 保留透明通道，跳过 JPEG 重压缩；因此与 JPEG 路径的质感不同。输入按 EXIF 转正，输出可能交换宽高。JPEG/PNG 输出从像素新建，不复制源元数据；PNG 无质感处理时可保留转正后的像素，但不是文件字节无损。动图和多页 TIFF 不支持。

三档参数继承上游：噪声标准差 1.5/2.5/4.0，缩放系数 .99/.97/.95，JPEG 质量 88→96 / 80→94 / 72→92。无检测效果承诺；选择档位应依据视觉需要。

## 失败与兼容

- `pip` 安装失败：检查当前解释器、网络、虚拟环境及 Python 版本，不用别的 Python 的 pip 代替。
- 输出已存在：指定新输出路径，或在明确要替换输出时加入 --overwrite。
- 输入与输出是同一路径、硬链接或符号链接：拒绝操作。
- 输入文件损坏/不受支持：单图失败返回 1；批处理记录失败并继续，最终返回 1。
- 参数错误返回 2；缺依赖返回 3；全部处理与报告写入成功返回 0。
- 使用系统 tempfile 在输出父目录创建独立临时目录，先完整写入与验证，再发布结果。支持硬链接的文件系统使用原子发布；FAT/exFAT 等使用排他创建并复制，普通复制错误会清理半成品，但进程被强制杀死或断电时可能留下不完整的新输出。原图不变。不同进程写同一输出时默认拒绝覆盖；显式 overwrite 按最后成功写入者为准。
- 本实现依赖 Pillow 的色彩转换；带 ICC 的特殊色域图、CMYK 印刷文件需先做视觉检查，输出不会保留源 ICC。

## 开发核验

在技能目录运行：

```bash
python -m unittest discover -s tests -v
```

Windows 在本次创建时实测；macOS/Linux 使用标准库跨平台路径与文件接口，但交付时若未在这些系统执行，不得称为已实测。
