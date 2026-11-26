# 运行手册（P5）

对象：值守人员与开发自测。默认端口 8000，所有接口返回 `{"ok","data","error"}`，角色通过 `X-Role` 传入。

## 1. 启动与健康

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl -s http://127.0.0.1:8000/v1/health
```

健康返回 `model_provider`、`trace_dir`、`env`。非 200 或 `ok=false` 时先看进程与磁盘，不要直接重启掩盖问题。

## 2. 首次初始化（空库）

```bash
python scripts/ingest.py --source ../discovery-report.md   # 灌入 36 条事实
curl -s "http://127.0.0.1:8000/v1/kb/stats" -H "X-Role: engineer"
```

`facts` 应为 36，`dimensions` 四维均有值。入库是全量重建，台账变化后重跑一次即可。

## 3. 正常业务链路

```bash
# 建任务
TASK=$(curl -s -X POST http://127.0.0.1:8000/v1/tasks -H "X-Role: engineer" | python -c "import sys,json;print(json.load(sys.stdin)['data']['task_id'])")
# 执行四步
curl -s -X POST "http://127.0.0.1:8000/v1/tasks/$TASK/run" -H "Content-Type: application/json" -H "X-Role: engineer" -d '{}'
# 人工签核（仅 safety / admin）
curl -s -X POST "http://127.0.0.1:8000/v1/tasks/$TASK/gate/decide" \
  -H "Content-Type: application/json" -H "X-Role: admin" -d '{"decision":"approve","note":"同意试点"}'
```

状态机：`created → conflicts_ready → baseline_ready → design_ready → verified → awaiting_gate → approved / rejected`。停在 `awaiting_gate` 是预期行为，必须人工签核。

## 4. 降级处理

| 现象 | 判断 | 处置 |
|---|---|---|
| 模型报错 / 超时 | 结果含 `degraded=true`，错误码 `E_MODEL_UNAVAILABLE` | 检查推理服务；有 fallback 时结果可用但需标注降级 |
| 知识库为空 | 基线五行全 `TBD`，冲突为 0 | 重跑 `scripts/ingest.py` |
| 追踪目录不可写 | 结果含 `trace_degraded=true`，业务不中断 | 修复磁盘或权限；确认 `var/trace` 可写 |
| 签核被拒 | 403 + `E_PERM` / `E_HUMAN_REQUIRED` | 换 safety / admin 账号，不要借用他人账号 |

## 5. 回放与验收

```bash
python scripts/replay_check.py --trace var/trace/<id>.jsonl   # FF6 结构一致
python scripts/bench_p95.py                                    # P95 ≤ slo.p95_ms
python scripts/drill.py --fault all                            # 三类故障演练
python scripts/eval_run.py --suite all                         # FF1/FF2/FF3 门禁
```

回放要求 `trace.store_raw=true`；若生产按合规关闭原文，则只能做结构审计，不能回放。

## 6. 数据留存与清理

- 记忆：默认 90 天 TTL，过期由检索前自动清理；`memory.ttl_days` 可调。
- 追踪：`var/trace/*.jsonl`，含模型原文时按敏感数据管理，建议与审计留存同周期（90 天）。
- 任务：`var/tasks/*.json`，含签核记录，不可随意删除；删除需走归档流程并留痕。

## 7. 停止与回滚

- 触发任一停止条件（错发率未降、漏扫未归零、现场规程被放宽、出现自动审批或写库），立即暂停试点并保留现场与追踪。
- 代码回滚：按提交粒度回退；数据回滚：恢复 `var/` 快照，不要手工改任务 JSON。
- 规则版本冲突：附两版交安全主管裁定，系统不自行合并（f24）。

## 8. 常见误判

- `viewer` 看不到规则维页面与审计，是权限设计，不是故障。
- 重复执行任务不产生新版本，是幂等设计；要重算需先改变台账输入。
- 评估 FF2 为 1.000 只代表 6 条固定用例，不代表线上表现。
