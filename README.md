# multipanel-figure-cropping

多面板期刊图（Nature / Cell / Science 式复合图版）的拆分工具：从整张图版里测量出每个子图的矩形，
裁成独立图片，并产出可核验的报告（每个子图的像素矩形、归一化坐标、是否切到标签的检查）。

## 状态

仓库于 2026-10-13 初始化，作为 DSH 工作区 A 路线（工作区根 + `projects\<项目>` 子仓库）的第一个试用仓库。
内容待迁入。

## 目录

| 路径 | 用途 |
|---|---|
| `scripts/` | 可复用脚本 |
| `examples/` | 示例输入、参数 JSON 与运行说明 |
| `output/` | 产出（图片、报告）；**不进 git** |

## 用法

（待补：依赖、入口命令、示例数据获取方式）

## 相关

- 同名 skill 目前位于 `~/.dsh/skills/multipanel-figure-cropping/`（`SKILL.md` +
  `scripts/panelkit.py`、`crop_panels.py`、`layout_probe.py`、`audit_crops.py`、`auto_edge_cleanup.py` + `examples/`）。
  是否迁入本仓库尚待决定。
