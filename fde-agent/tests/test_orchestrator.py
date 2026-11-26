# -*- coding: utf-8 -*-
"""编排测试：四步状态机、幂等、断点续跑、闸门权限与驳回。"""

from pathlib import Path                                     # 临时目录
import pytest                                                # 断言与异常
from app.knowledge.ingest import parse_ledger                 # 构造知识库
from app.knowledge.store import KnowledgeStore                # 知识库
from app.orchestrator.engine import (GATE_ROLES, Orchestrator,
                                     OrchestratorError, TaskState)   # 被测对象

SAMPLE = """# 台账
- [logistics-warehouse-f11] 林亦舟：取消订单已进入波次，拣完后仍被装车，配送站到货才发现（物流-005 · 业务事件样本）
- [logistics-warehouse-f31] 秦芮：短拣原因编码不一致，订单取消事件同步延迟 12 分钟（物流-011 · 业务事件样本）
- [logistics-warehouse-f00] 顾明岚：错发率 1.8%，目标 0.5%；装车复核平均 35 分钟降到 20 分钟（物流-001 · 访谈事实记录）
- [logistics-warehouse-f42] 傅景：一个仓区试点，错发率下降且复核漏扫为零；同时检查高位叉车、危险品及冷链操作必须遵循现场规程（物流-015 · 流程与约束说明）
- [logistics-warehouse-f50] 叶书：仓库按出库算完成，配送站按正确收货算完成，取消订单责任分歧（物流-016 · 访谈事实记录）
"""


def _orch(tmp_path: Path) -> Orchestrator:                    # 构造编排器
    """创建带样例知识库的编排器。

    入参：tmp_path 临时目录。
    出参：Orchestrator。
    失败行为：无。
    """
    kb = KnowledgeStore(str(tmp_path / "kb"))                  # 知识库
    kb.ingest(parse_ledger(SAMPLE))                            # 入库
    return Orchestrator(str(tmp_path / "tasks"), kb)            # 编排器


def test_full_run_and_gate(tmp_path: Path):                    # 全流程
    """验证四步跑完进入待签核，且闸门具备三要素。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    orch = _orch(tmp_path)                                     # 编排器
    task = orch.create("engineer")                             # 创建
    record = orch.run(task["task_id"])                         # 全部步骤
    assert record["state"] == TaskState.AWAITING_GATE.value    # 待签核
    assert set(record["done_steps"]) == {"conflicts", "baseline", "design", "verify"}   # 四步完成
    gate = record["gate"]                                      # 闸门
    assert gate["status"] == "pending"                         # 待处理
    assert gate["reason"] and gate["required_roles"]           # 触发原因与所需角色
    assert record["payload"]["design"]["rules"]                # 方案含规则


def test_idempotent_rerun(tmp_path: Path):                     # 幂等
    """验证重复执行不会重复追加历史。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    orch = _orch(tmp_path)                                     # 编排器
    task = orch.create("engineer")                             # 创建
    first = orch.run(task["task_id"])                          # 首次
    second = orch.run(task["task_id"])                         # 再次
    assert len(second["history"]) == len(first["history"])     # 历史未增长
    assert second["done_steps"] == first["done_steps"]         # 步骤未变


def test_resume_after_reload(tmp_path: Path):                  # 断点续跑
    """验证部分执行后重新加载实例可继续。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    orch = _orch(tmp_path)                                     # 编排器
    task = orch.create("engineer")                             # 创建
    orch.run(task["task_id"], ["conflicts"])                   # 只跑第一步
    fresh = Orchestrator(str(tmp_path / "tasks"), orch.kb)      # 模拟进程重启
    record = fresh.run(task["task_id"], ["baseline", "design", "verify"])   # 续跑
    assert record["state"] == TaskState.AWAITING_GATE.value    # 正常收尾


def test_missing_upstream_fails(tmp_path: Path):               # 缺上游
    """验证跳过基线直接生成方案会进入失败态。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    orch = _orch(tmp_path)                                     # 编排器
    task = orch.create("engineer")                             # 创建
    record = orch.run(task["task_id"], ["design"])              # 越序
    assert record["state"] == TaskState.FAILED.value           # 失败态


def test_gate_permission_and_approve(tmp_path: Path):          # 签核权限
    """验证工程角色不能签核、安全角色可批准并记录三要素。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    orch = _orch(tmp_path)                                     # 编排器
    task = orch.create("engineer")                             # 创建
    orch.run(task["task_id"])                                  # 跑到待签核
    with pytest.raises(OrchestratorError):                     # 越权签核
        orch.decide(task["task_id"], "engineer", "approve")    # 工程角色
    record = orch.decide(task["task_id"], "safety", "approve", "同意试点")   # 安全角色
    assert record["state"] == TaskState.APPROVED.value         # 已批准
    assert record["gate"]["decided_by"] == "safety"            # 接手人
    assert record["gate"]["decided_at"]                        # 确认时间
    assert record["gate"]["note"] == "同意试点"                 # 备注


def test_gate_reject(tmp_path: Path):                          # 驳回
    """验证驳回后进入拒绝态且不可重复签核。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    orch = _orch(tmp_path)                                     # 编排器
    task = orch.create("engineer")                             # 创建
    orch.run(task["task_id"])                                  # 跑到待签核
    record = orch.decide(task["task_id"], "admin", "reject", "口径未定")   # 驳回
    assert record["state"] == TaskState.REJECTED.value         # 拒绝态
    with pytest.raises(OrchestratorError):                     # 重复签核
        orch.decide(task["task_id"], "admin", "approve")       # 已无待办
    assert "safety" in GATE_ROLES                              # 角色表可读
