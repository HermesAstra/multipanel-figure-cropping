# multipanel-figure-cropping

多面板期刊图（Nature / Cell / Science 式复合图版）的拆分工具：从整张图版里测量出每个子图的矩形，
裁成独立图片，并产出可核验的报告（每个子图的像素矩形、归一化坐标、是否切到标签的检查）。

## 状态

2026-10-13 初始化，作为工作区 `git_management\<仓库名>\` 约定的第一个子仓库
（父目录原名 `projects\`，2026-10-14 改名为 `git_management\`）。内容待迁入。

## 目录约定

| 路径 | 用途 |
|---|---|
| `scripts/` | 可复用脚本与库 |
| `examples/` | 示例输入、参数 JSON、运行说明 |
| `output/` | 产出（图片与报告）；**不进 git** |

## 提交约定

- 初始分支 `main`。
- 提交信息说明「做了什么、为什么」，中文或英文均可。
- 图片类产出不进仓库，只落 `output/`。

## 相关

- 同名 skill 位于 `~/.dsh/skills/multipanel-figure-cropping/`：`SKILL.md` +
  `scripts/panelkit.py`、`crop_panels.py`、`layout_probe.py`、`audit_crops.py`、`auto_edge_cleanup.py` + `examples/`。

## 待办

- [ ] 决定是否把上述 skill 内容迁入本仓库
- [ ] 补依赖与入口命令
- [ ] 配置远程仓库（尚未配置，`git push` 目前无处可推）
