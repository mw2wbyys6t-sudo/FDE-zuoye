# 许可证状态核对（CANN GELU 算子工程）

核对对象：本目录 72 个文件（源自 `mw2wbyys6t-sudo/CANN-`）。
核对方式：文件清单扫描 + 版权头检索 + 许可证文件定位。核对日期 2026-11-26。

## 一、结论速览

| 项目 | 状态 | 说明 |
|---|---|---|
| 项目级 LICENSE | **缺失** | 仓库根目录与各子目录均无 LICENSE / LICENCE / COPYING（`makeself` 除外） |
| 源码版权头 | 华为技术有限公司 | 2020、2020-2021、2024 三种年份，均含 "All rights reserved." |
| 本仓库再许可 | **不可** | 无许可证即默认保留所有权利，本仓库不授予任何使用权 |
| 第三方组件 | 1 项 | `cmake/util/makeself/` 为 **GPL-2.0**，随附 COPYING 全文 |
| 二进制/大文件 | 2 项 | `week3/*.docx`（85 KB）、`week3/media/report.png`（73 KB），均为课程作业产物 |

## 二、版权与许可证分布

| 路径 | 版权年份 | 许可证状态 |
|---|---|---|
| `op_host/gelu.cpp`、`op_host/gelu_tiling.h` | 2024 | 华为版权，无许可证文本 |
| `op_kernel/gelu.cpp` | 2024 | 华为版权，无许可证文本 |
| `framework/tf_plugin/tensorflow_gelu_plugin.cc` | 2020-2021 | 华为版权，无许可证文本 |
| `framework/tf_plugin/CMakeLists.txt`、`cmake/**/CMakeLists.txt` | 2020 起 | 华为版权，无许可证文本 |
| `scripts/install.sh`、`scripts/upgrade.sh`、`cmake/util/*.sh` | 2020-2021 | 华为版权，无许可证文本 |
| `test/AclNNInvocation/**`（`common.h`、`op_runner.h` 等） | 2020 | 华为版权，无许可证文本 |
| `cmake/util/makeself/**` | 第三方 | **GPL-2.0**，COPYING 全文随附 |

## 三、风险分级

| 级别 | 风险 | 影响 | 建议动作 |
|---|---|---|---|
| 高 | 项目无 LICENSE，代码标注 All rights reserved | 对外分发缺少授权依据；他人无法合法复用 | 向上游确认原始许可（CANN 样例通常随 CANN 协议或 Apache-2.0 发布），补齐 LICENSE 后再对外提供 |
| 中 | 内置 GPL-2.0 的 makeself | 若整体分发，须保留 COPYING 并提供对应源码；GPL 义务仅及该组件 | 保留 `cmake/util/makeself/COPYING` 原样；发布说明中列为第三方组件 |
| 已处理 | 课程作业物料原含姓名、学号、班级、指导教师 | 公开仓库暴露个人身份信息 | 2026-11-26 已脱敏并替换为脱敏版 DOCX |
| 低 | 无 SBOM、无 NOTICE | 下游无法快速核对组件 | 生成 `THIRD-PARTY-NOTICES`，接入扫描工具 |

## 四、本目录已采取的处理

1. 完整保留 `cmake/util/makeself/COPYING`（GPL-2.0 全文），未删除、未改写。
2. 保留全部源码版权头，未做任何去除或替换。
3. 不添加任何许可证文件，避免造成"本仓库已获授权"的误解。
4. 在 `integrated/README.md` 与完整报告中说明来源与边界。

## 五、待办（需人工确认）

- [ ] 向上游确认该算子工程的原始许可证（CANN 样例来源、是否 Apache-2.0）
- [ ] 决定课程 docx 是否保留在公开仓库（含姓名、学号、班级）
- [ ] 若对外分发，补充 `LICENSE` 与 `THIRD-PARTY-NOTICES`
- [ ] 在 CI 中加入许可证扫描（如 ScanCode），防止后续引入不兼容组件

> 本核对为工程侧事实记录，不构成法律意见。
