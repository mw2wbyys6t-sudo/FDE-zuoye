# -*- coding: utf-8 -*-
"""P4 验证脚本：方案生成、相关性核验、编排状态机、断点续跑与人工闸门。"""

import shutil                                                # 清理目录
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 直接运行时补路径
    sys.path.insert(0, str(ROOT))                             # 保证 app 可导入

from fastapi.testclient import TestClient                     # 接口
from app.agents import a4_design, a5_verify                    # A4/A5
from app.agents.contracts import BaselineOutput, ConflictOutput   # 空输入构造
from app.knowledge.ingest import parse_ledger_file              # 台账
from app.knowledge.store import KnowledgeStore                  # 知识库
from app.main import app                                       # 应用
from app.orchestrator.engine import (Orchestrator, OrchestratorError, TaskState)   # 编排

SOURCE_CANDIDATES = [ROOT.parent / "discovery-report.md",
                     ROOT.parent / "docs" / "discovery-report.md"]   # 两种布局
SOURCE = next((p for p in SOURCE_CANDIDATES if p.exists()), SOURCE_CANDIDATES[0])   # 取存在
WORK = ROOT / "var" / "p4-verify"                             # 验证目录
RESULTS = []                                                  # 结果


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录
    """记录并打印检查结果。

    入参：name 名称；condition 是否通过；detail 说明。
    出参：无。
    失败行为：不抛异常。
    """
    RESULTS.append((name, bool(condition)))                     # 收集
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 打印


def main() -> int:                                             # 入口
    """执行 P4 全部验证。

    入参：无。
    出参：0 全通过，1 有失败，2 缺台账。
    失败行为：异常向上抛出。
    """
    if not SOURCE.exists():                                    # 台账缺失
        print("台账不存在：%s" % SOURCE)                        # 提示
        return 2                                               # 退出
    shutil.rmtree(WORK, ignore_errors=True)                    # 清理
    facts = parse_ledger_file(str(SOURCE))                     # 36 条
    known = {fact.fact_id for fact in facts}                   # 编号集合
    kb = KnowledgeStore(str(WORK / "kb"))                      # 临时知识库
    kb.ingest(facts)                                           # 入库

    orch = Orchestrator(str(WORK / "tasks"), kb)               # 编排器
    task = orch.create("engineer")                             # 创建
    record = orch.run(task["task_id"])                         # 全流程
    check("状态进入待签核", record["state"] == TaskState.AWAITING_GATE.value, record["state"])   # 状态
    design = record["payload"]["design"]                       # 方案
    check("方案含四条规则", len(design["rules"]) == 4, str(len(design["rules"])))   # 规则数
    check("方案写明不自动操作叉车", any("不自动操作叉车" in x for x in design["boundary"]), "boundary")   # 边界
    check("方案证据均真实", set(design["fact_refs"]).issubset(known), "refs")   # 引用
    check("方案有验收与停止条件", bool(design["acceptance"]) and bool(design["stop_conditions"]), "accept/stop")   # 两清单
    gate = record["gate"]                                      # 闸门
    check("闸门三要素齐全", bool(gate["reason"]) and gate["status"] == "pending"
          and bool(gate["required_roles"]), "reason/status/roles")   # 三要素前置
    before = len(record["history"])                            # 记录历史长度
    again = orch.run(task["task_id"])                          # 幂等重跑
    check("重复执行幂等", len(again["history"]) == before, str(len(again["history"])))   # 历史未增长

    try:                                                       # 工程角色签核
        orch.decide(task["task_id"], "engineer", "approve")    # 越权
        check("工程角色不能签核", False, "未拦截")             # 失败
    except OrchestratorError as exc:                           # 预期
        check("工程角色不能签核", exc.code == "E_PERM", exc.code)   # 拦截
    approved = orch.decide(task["task_id"], "safety", "approve", "同意单仓区试点")   # 安全签核
    check("安全角色可签核", approved["state"] == TaskState.APPROVED.value, approved["state"])   # 状态
    check("签核记录接手人与时间", bool(approved["gate"]["decided_by"])
          and bool(approved["gate"]["decided_at"]), "decided")   # 三要素

    partial = orch.create("engineer")                          # 续跑用例
    orch.run(partial["task_id"], ["conflicts"])                # 只跑第一步
    resumed = Orchestrator(str(WORK / "tasks"), kb).run(
        partial["task_id"], ["baseline", "design", "verify"])   # 新实例续跑
    check("断点续跑可完成", resumed["state"] == TaskState.AWAITING_GATE.value, resumed["state"])   # 续跑

    fact_map = {fact.fact_id: fact.statement for fact in facts}   # 编号到陈述
    good = a5_verify.verify_relevance([{"text": "取消订单已进入波次，拣完仍被装车", "fact_id": "f11"}], fact_map)   # 匹配
    bad = a5_verify.verify_relevance([{"text": "拣选是错发主因", "fact_id": "f31"}], fact_map)   # 不匹配
    check("相关性核验能识别错配", good.passed and not bad.passed, "relevance")   # 对比
    empty_design = a4_design.build(BaselineOutput(rows=[]), ConflictOutput())   # 空上游
    check("A4 空输入仍返回骨架方案", len(empty_design.rules) == 4, "rules")   # 鲁棒性

    client = TestClient(app)                                   # 接口
    ingest = client.post("/v1/kb/ingest", json={"path": str(SOURCE)}, headers={"X-Role": "engineer"})   # 入库
    check("接口入库成功", ingest.status_code == 200 and ingest.json()["ok"], str(ingest.status_code))   # 入库
    created = client.post("/v1/tasks", headers={"X-Role": "engineer"})   # 创建任务
    task_id = created.json()["data"]["task_id"]                # 任务号
    ran = client.post("/v1/tasks/%s/run" % task_id, json={}, headers={"X-Role": "engineer"})   # 执行
    check("接口执行到待签核", ran.status_code == 200
          and ran.json()["data"]["state"] == "awaiting_gate", str(ran.status_code))   # 状态
    denied = client.post("/v1/tasks/%s/gate/decide" % task_id, json={"decision": "approve"},
                         headers={"X-Role": "viewer"})          # 越权签核
    check("接口：一线角色不能签核", denied.status_code == 403, str(denied.status_code))   # 403
    ok_decide = client.post("/v1/tasks/%s/gate/decide" % task_id,
                            json={"decision": "approve", "note": "接口签核"},
                            headers={"X-Role": "admin"})        # 管理员签核
    check("接口：管理员可签核", ok_decide.status_code == 200
          and ok_decide.json()["data"]["state"] == "approved", str(ok_decide.status_code))   # 批准

    failed = [name for name, ok in RESULTS if not ok]           # 汇总
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 输出
    return 0 if not failed else 1                              # 退出码


if __name__ == "__main__":                                     # 直接运行
    sys.exit(main())                                           # 返回退出码
