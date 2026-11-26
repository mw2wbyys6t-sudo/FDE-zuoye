# 整合说明：CANN GELU 算子工程

本目录是从仓库 `mw2wbyys6t-sudo/CANN-` 整体迁入的内容，迁移时保持原有目录结构，未改动任何源码。

## 一、这是什么

华为昇腾 CANN / Ascend C 的 **GELU 自定义算子**课程工程：算子原型、Tiling 切分、Kernel 核函数、编译脚本与端到端精度验证。同时包含第三周《开源创新思维》的**开源合规与许可证**作业（ScanCode 扫描 pip 26.2.1）。

课程信息（已脱敏）：开源创新思维 · （已脱敏） F25****** · F25**** · 指导教师 （已脱敏） · 2026-2027 秋季学期 · 上海杉达学院。

## 二、迁移信息

| 项目 | 内容 |
|---|---|
| 来源仓库 | https://github.com/mw2wbyys6t-sudo/CANN- |
| 来源分支 | main（克隆时 HEAD `15c13bb`） |
| 迁移方式 | 完整复制，保留目录层级与文件名，未修改源码 |
| 文件数量 | 72 个文件，约 469 KB |
| 迁移日期 | 2026-11-26 |

## 三、目录索引

| 路径 | 作用 | 备注 |
|---|---|---|
| `op_host/` | 算子原型与 Tiling 实现（`gelu.cpp`、`gelu_tiling.h`） | 含华为 2024 版权头 |
| `op_kernel/` | Ascend C 核函数实现（`gelu.cpp`） | 含华为 2024 版权头 |
| `framework/tf_plugin/` | TensorFlow 插件适配 | 含华为 2020-2021 版权头 |
| `cmake/` | 构建脚本与算子工程框架 | 其中 `cmake/util/makeself/` 是第三方打包工具，**GPL-2.0** |
| `scripts/` | `install.sh`、`upgrade.sh` 安装与升级脚本 | 含华为 2020-2021 版权头 |
| `test/` | `AclNNInvocation` 调用样例、`reference_gelu.py`、`compare_with_official.py` | 用于精度比对 |
| `week3/` | 第三周开源合规作业（Markdown 版报告、原始 docx、报告截图） | 许可证合规内容见下方报告 |
| `build_910b.sh` / `build.sh` | 910B 与其他环境的编译脚本 | 依环境选择 |
| `CMakeLists.txt` / `CMakePresets.json` | 顶层构建入口与预设 | 依赖 CANN 工具链 |
| `gelu.json` | 算子原型描述 | 供算子工程使用 |
| `.github/workflows/build.yml` | CI 构建流水线 | 依赖自建或 GitHub runner 环境 |

## 四、如何构建与验证（原仓库说明，未改动）

```bash
bash build_910b.sh                 # 910B 环境编译
python test/compare_with_official.py   # 与官方/参考实现比对精度
```

构建依赖华为 CANN 工具包与昇腾硬件环境，本仓库不含该工具链，也无二进制产物。

## 五、许可证与合规

**本目录不改变上游的许可证状态**。核对结论、第三方组件清单与待办动作见：

- [`LICENSE-STATUS.md`](./LICENSE-STATUS.md)（目录内快速核对）
- [`../docs/license/开源许可证合规核对报告.md`](../docs/license/开源许可证合规核对报告.md)（完整报告，含第三周 pip 扫描结论）
- 同报告 DOCX 版：`../docs/license/开源许可证合规核对报告.docx`

> 一句话结论：上游仓库**未附项目级 LICENSE**，源码多处标注华为版权与 All rights reserved；`cmake/util/makeself/` 为 GPL-2.0 第三方组件。本仓库仅作课程归档，不构成对这些代码的再许可。

## 六、与 FDE-zuoye 原有内容的关系

本仓库有两条彼此独立的内容线，合并在同一仓库便于统一归档，但**不得混为同一项目**：

| 内容线 | 位置 | 性质 |
|---|---|---|
| FDE 需求发现与智能体系统 | `docs/`（报告、作答、流程图、技术方案）、`fde-agent/`（代码） | 仓内拣选与装车核验场景的分析与系统实现 |
| CANN GELU 算子课程工程 | `integrated/cann-gelu/` | 华为昇腾算子课程作业与开源合规作业 |

两条线没有代码依赖，构建方式、许可证状态、验收标准均不同，阅读与引用时请分别标注来源。
