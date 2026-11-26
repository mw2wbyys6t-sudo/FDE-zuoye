# FDE Agent Harness

远川物流 FDE 智能体系统的最小可运行骨架：契约、执行器、闸门、追踪、评估入口，附一个零构建 MVP 控制台。

## 启动

```bash
pip install -r requirements.txt      # 安装依赖（本地已具备可跳过）
uvicorn app.main:app --reload        # 启动服务，默认 127.0.0.1:8000
```

打开 http://127.0.0.1:8000/ui/ 进入控制台（`/` 会自动跳转）；API 文档在 http://127.0.0.1:8000/docs 。

控制台四个视图：概览（健康 / 知识库 / 记忆 / 页面）、任务编排（新建 → 执行四步 → 签核）、知识 Wiki（用户 / 管理员模式）、记忆与审计。右上角切换 `X-Role` 演示权限差异，生产环境角色须由网关注入。

## 自测

```bash
pytest -q                            # 73 项单元测试
python scripts/verify_p0.py          # 10 项 Harness 端到端验证
python scripts/verify_p1.py          # 12 项知识库验证（解析/四维/持久化/检索/权限）
python scripts/verify_p2.py          # 18 项记忆与 Wiki 验证（分层/冲突/双模式/回滚/审计）
python scripts/verify_p3.py          # 14 项 Agent 验证（冲突/基线/核验/评估门禁/接口）
python scripts/verify_p4.py          # 17 项编排验证（方案/幂等/续跑/闸门/相关性）
python scripts/verify_p5.py          # 11 项交付验证（回放/P95/故障演练/手册）
python scripts/verify_p6.py          # 12 项前端验证（静态审查/挂载/角色权限对齐）
python scripts/verify_p7.py          # 18 项执行层验证（四规则/三要素/指标/接口权限）
python scripts/verify_p8.py          # 10 项接入验证（格式/回放门禁/来源隔离）
python scripts/replay_csv.py --csv data/sample/picking_sample.csv   # 历史回放评估
python scripts/eval_run.py --suite all   # 黄金集：FF1/FF2/FF3 门禁
python scripts/replay_check.py --trace var/trace/<id>.jsonl   # 单次回放
python scripts/bench_p95.py          # P95 压测
python scripts/drill.py --fault all  # 三类故障演练
python scripts/ingest.py --source ../discovery-report.md   # 手动入库
python scripts/check_comment_rules.py   # 关键函数「为什么这么卡」注释
python scripts/check_config.py          # 禁止硬编码密钥与地址
python scripts/check_imports.py         # 依赖方向：harness/model 不得依赖 api
python scripts/check_line_comments.py   # 行注释覆盖率 ≥ 0.95
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/v1/health` | 依赖与配置状态 |
| POST | `/v1/harness/selftest` | 三个用例：正常、重试、证据拦截（需 `X-Role` 头） |
| GET | `/v1/kb/stats` | 知识库片段数与维度分布 |
| POST | `/v1/kb/ingest` | 台账入库，仅 engineer / admin |
| POST | `/v1/kb/search` | 按角色与维度检索，返回带 `fact_id` 的片段 |
| POST | `/v1/memory/write` | 写记忆，仅 engineer / admin；语义层强制核验+事实编号 |
| POST | `/v1/memory/search` | 按角色与层检索记忆（自动跳过过期项） |
| GET | `/v1/memory/stats` | 分层数量与冲突数 |
| GET | `/v1/wiki/pages?mode=user\|admin` | 双模式列表：用户只看已发布且可见；管理员看全部 |
| POST | `/v1/wiki/pages` | 创建草稿（需引用真实事实编号） |
| PATCH | `/v1/wiki/pages/{slug}` | 更新并升版本 |
| POST | `/v1/wiki/pages/{slug}/publish` | 发布，仅管理员签核 |
| POST | `/v1/wiki/pages/{slug}/rollback/{version}` | 回滚到历史版本（回滚本身升版本） |
| POST | `/v1/wiki/draft-from-facts` | 按维度聚合事实生成草稿 |
| GET | `/v1/wiki/audit` | 审计记录，仅管理员 |
| POST | `/v1/agents/conflicts` | 冲突检测（数值 / 口径 / 范围），限 engineer / safety / admin |
| POST | `/v1/agents/baseline` | 五个指标的基线表 + 独立核验 |
| POST | `/v1/agents/verify` | 核验一组结论是否带真实事实编号 |
| POST | `/v1/agents/pipeline` | 冲突 → 基线 → 核验 一次跑完 |
| POST | `/v1/tasks` | 创建编排任务（engineer / admin） |
| POST | `/v1/tasks/{id}/run` | 按步执行，已完成步骤自动复用（幂等） |
| GET | `/v1/tasks/{id}` | 查看状态、产物与历史 |
| POST | `/v1/tasks/{id}/gate/decide` | 人工签核，仅 safety / admin |
| POST | `/v1/exec/scan` | 现场判定：R1 规格差异 / R2 取消 / R3 说明随单 / R4 系统不可用 |
| POST | `/v1/exec/dispositions` | 处置闭环；挂起单必须带原因、接手人、确认时间 |
| GET | `/v1/exec/metrics` | 判定数、提示/挂起、未闭环、闭环率、分规则命中 |
| GET | `/v1/exec/events` | 执行事件流（扫码与处置），供排查与回放 |
| POST | `/v1/exec/import` | 导入现场导出 CSV，返回条数与回放指标（engineer / admin） |

`GET /v1/exec/metrics?provenance=real` 只统计真实数据；合成演示数据一律标记 `synthetic`，不得进入验收口径。

所有响应固定为 `{"ok", "data", "error"}`；错误码见 `app/errors.py`。

## 结构

```
app/
  api/        统一 envelope、角色鉴权、知识库/记忆/Wiki/Agent 路由
  agents/     A1 证据抽取、A2 冲突检测、A3 口径基线、A5 独立核验 + 契约
  domain/     Fact / Chunk / Hit 领域模型（四维 + 四档证据等级）
  deps.py     配置、追踪、知识库、记忆、Wiki 的进程内单例
  harness/    契约(schema)、执行器(runner)、闸门(guards)、追踪(trace)、回放(replay)、故障注入
  knowledge/  入库(ingest)、切分(chunk)、倒排索引(index)、检索(retrieve)、存储(store)
  memory/     分层模型、写入策略、本地存储、环境画像、Mem0 适配器
  orchestrator/ 任务状态机、幂等与断点续跑、人工闸门
  wiki/       页面/版本/审计模型、存储、双模式服务
  model/      模型接口、OpenAI 兼容网关、Fake
  config.py   配置加载（${ENV} 展开）
scripts/      验证、入库与规范检查
tests/        单元与接口测试
```

## 阶段范围

- **P0 已实现**：契约强校验、失败重试与降级、证据/边界/权限闸门、JSONL 追踪、统一响应、角色白名单。
- **P1 已实现**：36 条事实解析、四维自动归类（事实 10 / 规则 11 / 指标 5 / 案例 10）、按条目切分、中文二元组 BM25 检索、角色可见性过滤、JSONL + 索引持久化、知识库接口。
- **P2 已实现**：四层记忆（working / episodic / semantic / procedural）、写入策略（语义层必须有核验+事实编号）、冲突并存不合并、90 天 TTL 与过期清理、环境画像、Mem0 可选适配器（缺失自动降级）；项目专属 Wiki 双模式（用户只读已发布 / 管理员可写可发布可回滚），版本快照、审计留痕、按维度从事实聚合草稿。
- **P3 已实现**：A1 证据抽取（走 Runner，输出即过证据闸门）、A2 三类冲突（数值 / 完成口径 / 提示与阻断）、A3 五指标基线（缺项写 TBD 并标注证据等级）、A5 独立核验（无上游上下文）；黄金集 6 例 + FF1/FF2/FF3 门禁（实测 1.000 / 1.000 / 1.000）；`/v1/agents/*` 四个端点。
- **P4 已实现**：A4 方案生成（固定范围 + 4 条规则草案 + 验收/停止条件/边界/待答问题，全部带事实编号）；A5 增加"文本-证据相关性"判定（字符二元组重合度，默认阈值 0.25）；编排状态机（conflicts → baseline → design → verify → 待签核），幂等复用、断点续跑、失败留痕；人工闸门强制 safety/admin 签核并记录触发原因/接手人/确认时间。
- **P5 已实现**：追踪可选记录模型原文并支持按原文回放（FF6 结构一致）；模型故障（异常/超时/垃圾输出）统一走重试与降级，全挂时报 `E_MODEL_UNAVAILABLE`；追踪不可写时业务不中断并标记 `trace_degraded`；P95 压测脚本（本地链路 P95 ≈ 1.8ms，预算 8000ms）；三类故障演练脚本与运行手册 `docs/runbook.md`。
- **未实现（可选后续）**：接真实本地模型（Ollama/vLLM）后的端到端压测、编排级整体回放、Qdrant/PG 真实故障注入。

## 约定

- 判定不进模型：规则与闸门在代码里，模型只做抽取与解释。
- 配置只走 `config.yaml` 与 `${ENV}`，禁止硬编码地址与密钥。
