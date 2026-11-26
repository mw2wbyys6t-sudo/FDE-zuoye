# FDE-zuoye

开源课程 FDE 作业仓库｜案例：远川物流「拣完了，却装错了车」——仓内拣选与装车核验。

本仓库完整记录一次 FDE 需求发现的交付链：客户简报 → 六角色访谈 → 证据台账 → 业务机会与基线 → 决策链 → 结论流程图 → 技术方案。所有材料基于**合成训练场景**，不代表真实客户验收。

## 目录结构

```
├─ README.md
└─ docs/
   ├─ 远川物流-拣完了，却装错了车-四份可核对资料.html   # 客户简报 / 现状信息请求表 / 访谈材料
   ├─ discovery-report.md                              # 业务需求发现报告（36 条事实、四来源核对、REQ-1~6）
   ├─ discovery-report.json                            # 同上，结构化数据
   ├─ discovery-report.csv                             # 6 条需求假设（优先级 / 负责人 / 验收与约束 / 证据编号）
   ├─ 仓内拣选与装车核验-业务挖掘报告.md                 # 三任务作答与模型评分（三项均 88/100）
   ├─ 远川物流-三任务作答-业务机会·基线·决策链.html      # 三任务作答的可读版本
   ├─ 远川物流-FDE结论总流程图.html                      # 现状 → 判断 → 路径 三段合一流程图
   └─ agent-system/                                    # 提示词归档 + 智能体系统技术方案
      ├─ README.md
      ├─ PROMPT.md
      ├─ 远川物流-智能体系统-技术方案.md
      ├─ 远川物流-智能体系统-技术方案.docx
      └─ 远川物流-仓内拣选与装车核验-技术方案.md
```

## 材料说明

| 文件 | 内容 | 格式 |
|---|---|---|
| [四份可核对资料](docs/%E8%BF%9C%E5%B7%9D%E7%89%A9%E6%B5%81-%E6%8B%A3%E5%AE%8C%E4%BA%86%EF%BC%8C%E5%8D%B4%E8%A3%85%E9%94%99%E4%BA%86%E8%BD%A6-%E5%9B%9B%E4%BB%BD%E5%8F%AF%E6%A0%B8%E5%AF%B9%E8%B5%84%E6%96%99.html) | 客户简报、现状信息请求表、待索取记录清单、调查边界 | HTML |
| [discovery-report.md](docs/discovery-report.md) | 六角色事实台账（f00–f55）、按角色整理的证据、四来源核对、候选需求 | Markdown |
| [discovery-report.json](docs/discovery-report.json) / [discovery-report.csv](docs/discovery-report.csv) | 结构化导出，便于二次处理 | JSON / CSV |
| [业务挖掘报告](docs/%E4%BB%93%E5%86%85%E6%8B%A3%E9%80%89%E4%B8%8E%E8%A3%85%E8%BD%A6%E6%A0%B8%E9%AA%8C-%E4%B8%9A%E5%8A%A1%E6%8C%96%E6%8E%98%E6%8A%A5%E5%91%8A.md) | 任务1 识别业务机会、任务2 建立现状基线、任务3 确认立项与决策链，含评分与改进建议 | Markdown |
| [三任务作答（HTML）](docs/%E8%BF%9C%E5%B7%9D%E7%89%A9%E6%B5%81-%E4%B8%89%E4%BB%BB%E5%8A%A1%E4%BD%9C%E7%AD%94-%E4%B8%9A%E5%8A%A1%E6%9C%BA%E4%BC%9A%C2%B7%E5%9F%BA%E7%BA%BF%C2%B7%E5%86%B3%E7%AD%96%E9%93%BE.html) | 同上内容的可读排版版本 | HTML |
| [FDE 结论总流程图](docs/%E8%BF%9C%E5%B7%9D%E7%89%A9%E6%B5%81-FDE%E7%BB%93%E8%AE%BA%E6%80%BB%E6%B5%81%E7%A8%8B%E5%9B%BE.html) | 现状故障链 → 证据门槛判断 → G0–G6 落地路径与验收硬线 | HTML |
| [agent-system/](docs/agent-system/README.md) | 会话提示词归档，以及两套技术方案（业务侧 + 智能体系统侧） | Markdown / DOCX |

## 阅读顺序（建议）

1. [docs/远川物流-拣完了，却装错了车-四份可核对资料.html](docs/%E8%BF%9C%E5%B7%9D%E7%89%A9%E6%B5%81-%E6%8B%A3%E5%AE%8C%E4%BA%86%EF%BC%8C%E5%8D%B4%E8%A3%85%E9%94%99%E4%BA%86%E8%BD%A6-%E5%9B%9B%E4%BB%BD%E5%8F%AF%E6%A0%B8%E5%AF%B9%E8%B5%84%E6%96%99.html)——先看客户说了什么、要什么记录。
2. [docs/discovery-report.md](docs/discovery-report.md)——再看六个角色分别讲了什么，事实编号怎么来的。
3. [docs/仓内拣选与装车核验-业务挖掘报告.md](docs/%E4%BB%93%E5%86%85%E6%8B%A3%E9%80%89%E4%B8%8E%E8%A3%85%E8%BD%A6%E6%A0%B8%E9%AA%8C-%E4%B8%9A%E5%8A%A1%E6%8C%96%E6%8E%98%E6%8A%A5%E5%91%8A.md)——三任务作答与评分，能看出哪些地方被扣分、为什么。
4. [docs/远川物流-FDE结论总流程图.html](docs/%E8%BF%9C%E5%B7%9D%E7%89%A9%E6%B5%81-FDE%E7%BB%93%E8%AE%BA%E6%80%BB%E6%B5%81%E7%A8%8B%E5%9B%BE.html)——一张图看完结论与路径。
5. [docs/agent-system/README.md](docs/agent-system/README.md)——若关注系统实现，从这里进入技术方案。

## 核心结论（四条）

1. **需求是手段，结果才是交付物**：客户点名「AI 防错提示」，可验收的是错发率 1.8%→0.5%、复核漏扫为零、装车复核 35→20 分钟、取消单不再外溢到客户端。
2. **证据必须分级**：只有 12 分钟同步延迟、每日两次状态更新、22 万预算、90 天留存、编码不一致属事实级；1.8%/0.5%、35→20 分钟、7000 行/日、14 人时/日均为估计级；以估计值推算的「91 行/日」不得写入验收。
3. **不能先上功能**：口径未冻结、因果未分解（拣选与装车各占多少错发无数据）、基线未测量，三项门槛未过即不立项。
4. **治理是上线阻断项**：拣选差异放行与装车异常关闭的审批矩阵未定，出资者缺位（22 万由仓储经理确认，无财务角色）。

## 技术方案（agent-system）

- **业务方案**：判定用确定性规则（R1 规格差异 / R2 取消状态 / R3 说明随单 / R4 转人工），只提示不阻断、不回写业务库；先离线回放，再影子模式，最后单仓区并行。
- **系统方案**：Harness 优先的模块化单体 + 多智能体流水线；本地推理（OpenAI 兼容网关）、Mem0 四层记忆、四维知识库（事实/规则/指标/案例）；7 条可测适配函数作为架构不变量。
- Markdown 为唯一源文件，DOCX 由 Markdown 转换生成（A4 / 微软雅黑 / 正文 10.5pt）。

## 方法来源

需求归纳基于 `workflow-decomposition`、`outcome-risk-matrix`、`4-source-convergence` 三个框架：https://github.com/kalyvask/fde-simulation

## 边界与声明

- 本仓库为课程作业与合成训练材料，**不代表真实授权、业务执行或客户验收**。
- 不含账号口令、密钥、真实客户个人信息；所有指标均标注证据等级，不得直接用于对外承诺。
- 正式立项前需重新取得访谈引用授权、脱敏范围与历史资料回放调取授权。

## 维护约定

- 新增材料放入 `docs/`；与技术方案相关的放入 `docs/agent-system/`。
- 修改技术方案时先改 `.md`，再重新导出 `.docx`，避免两版不一致。
- 提交信息使用 `docs: 说明` / `docs(agent-system): 说明` 前缀。

## 内容整合（2026-11-26）

本仓库在原有 FDE 交付链之外，迁入了另一条独立的课程内容线，两者没有代码依赖，阅读与引用时请分别标注来源。

| 内容线 | 位置 | 说明 |
|---|---|---|
| FDE 需求发现与智能体系统 | `docs/`、`docs/agent-system/` | 远川物流仓内拣选与装车核验场景的分析、流程图与技术方案 |
| CANN GELU 算子课程工程 | `integrated/cann-gelu/` | 华为昇腾 Ascend C 算子实现、构建脚本、精度比对，以及第三周开源合规作业 |

- 迁移说明与逐目录索引：[`integrated/README.md`](./integrated/README.md)
- 许可证状态核对：[`integrated/LICENSE-STATUS.md`](./integrated/LICENSE-STATUS.md)
- 完整合规报告：[`docs/license/开源许可证合规核对报告.md`](./docs/license/开源许可证合规核对报告.md) ／ [DOCX 版](./docs/license/开源许可证合规核对报告.docx)

**重要声明**：迁入内容不改变上游许可证状态。上游仓库未附项目级 LICENSE，源码多处标注华为版权与 All rights reserved，`cmake/util/makeself/` 为 GPL-2.0 第三方组件。本仓库仅作课程归档，**不构成对这些代码的再许可**；对外分发前须按报告中的待办补齐授权与声明。

## 系统代码（fde-agent）

`fde-agent/` 是实现远川物流仓内拣选与装车核验场景的完整工程：Harness 执行骨架、四维知识库、分层记忆、项目 Wiki（用户/管理员双模式）、多 agent、编排状态机、人工闸门、现场执行层与零构建控制台。

**技术栈**：Python 3.11+ / FastAPI / Pydantic v2 / pytest；前端为原生 HTML+CSS+JS，无构建步骤。

**本地运行**

```bash
cd fde-agent
pip install -r requirements.txt
uvicorn app.main:app --port 8000     # 控制台 http://127.0.0.1:8000/ui/
pytest -q                            # 75 项单元测试
python scripts/verify_p0.py          # 逐阶段验收脚本 p0…p8
```

**目录职责**

| 路径 | 内容 |
|---|---|
| `app/harness/` | 契约、执行器、闸门、追踪、回放、故障注入 |
| `app/knowledge/` | 台账解析、切分、BM25 索引与检索 |
| `app/memory/` | 四层记忆、写入策略、环境画像、Mem0 适配器 |
| `app/wiki/` | 页面/版本/审计、双模式服务 |
| `app/agents/` | A1 证据抽取、A2 冲突检测、A3 口径基线、A4 方案生成、A5 独立核验 |
| `app/orchestrator/` | 任务状态机、幂等复用、断点续跑、人工闸门 |
| `app/execution/` | 现场规则引擎、事件溯源、处置闭环、CSV 导入与回放评估 |
| `app/web/` | 零构建控制台（概览 / 任务编排 / Wiki / 记忆审计 / 现场执行） |
| `data/sample/` | 合成样例 CSV（**非真实数据**） |
| `scripts/` | 入库、验收、评估门禁、压测、故障演练、回放 |
| `tests/` | 75 项单元测试 |

**数据与边界**

- 全部数据为合成样例，不接真实 WMS/OMS/扫码终端；`var/` 运行时目录不纳入版本库。
- 角色通过请求头 `X-Role` 传递，仅用于演示，生产须由网关注入。
- 现场规则（R1–R4）尚未经真实历史数据验证，回放评估台的样例结果为精确率 0.50 / 召回率 0.80，不可作为业务结论。

## 静态演示包（deploy/static-demo）

`deploy/static-demo/` 是控制台的静态打包脚本与浏览器内 mock 层，用于在没有 Python 运行时的环境（如静态托管）演示界面。

```bash
python deploy/static-demo/build_demo.py    # 产出 deploy/static-demo/dist/public/
```

- `mock.js` 拦截 `/v1` 请求，用内存合成数据实现概览、任务编排、Wiki 双模式、记忆审计、现场执行五组接口。
- `build_demo.py` 复制前端资源、注入 mock 脚本与演示横幅；`dist/` 为构建产物，已加入忽略规则。
- 已部署实例：`https://37ko78czrou73h0ul8b.traesite.cn`（仅自己可见）。
- 边界：数据在内存中，刷新即重置；页面顶部保留"演示模式"横幅；这是演示外壳，不是系统本体，真实系统需运行 `fde-agent`。
