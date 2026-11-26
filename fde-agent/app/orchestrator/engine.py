# -*- coding: utf-8 -*-
"""编排引擎：四步状态机 + 断点续跑 + 幂等 + 人工闸门。"""

import hashlib                                              # 计算输入指纹
import json                                                 # 持久化
import uuid                                                 # 任务编号
from datetime import datetime, timezone                      # 时间
from enum import Enum                                        # 状态枚举
from pathlib import Path                                     # 路径
from typing import Any, Dict, List, Optional                 # 类型标注
from app.agents import a2_conflict, a3_baseline, a4_design, a5_verify   # 四个 agent
from app import errors as E                                  # 错误码
from app.knowledge.store import KnowledgeStore               # 知识库


class TaskState(str, Enum):                                  # 任务状态
    CREATED = "created"                                      # 已创建
    CONFLICTS_READY = "conflicts_ready"                       # 冲突已检测
    BASELINE_READY = "baseline_ready"                        # 基线已生成
    DESIGN_READY = "design_ready"                            # 方案已生成
    VERIFIED = "verified"                                    # 已核验
    AWAITING_GATE = "awaiting_gate"                          # 等待人工签核
    APPROVED = "approved"                                    # 已批准
    REJECTED = "rejected"                                    # 已驳回
    FAILED = "failed"                                        # 失败


class OrchestratorError(Exception):                          # 编排异常
    def __init__(self, code: str, msg: str):                  # 初始化
        """构造编排异常。

        入参：code 错误码；msg 说明。
        出参：无。
        失败行为：无。
        """
        super().__init__(msg)                                # 基类
        self.code = code                                     # 错误码
        self.msg = msg                                       # 说明


STEPS = ["conflicts", "baseline", "design", "verify"]         # 固定步骤顺序
GATE_ROLES = ("safety", "admin")                             # 可签核角色


class Orchestrator:                                          # 编排器
    def __init__(self, root: str = "var/tasks", knowledge: Optional[KnowledgeStore] = None):   # 构造
        """初始化编排目录与知识库。

        入参：root 任务目录；knowledge 知识库。
        出参：无。
        失败行为：knowledge 为空时抛 ValueError。
        """
        if knowledge is None:                                 # 必要依赖
            raise ValueError("knowledge 不能为空")             # 直接失败
        self.root = Path(root)                                # 保存目录
        self.root.mkdir(parents=True, exist_ok=True)           # 创建目录
        self.kb = knowledge                                   # 保存知识库

    def _path(self, task_id: str) -> Path:                    # 任务文件
        """返回任务文件路径。

        入参：task_id 任务编号。
        出参：路径。
        失败行为：无。
        """
        return self.root / ("%s.json" % task_id)              # 固定命名

    def _input_hash(self) -> str:                             # 输入指纹
        """按当前事实集合计算指纹，用于判断是否需要重跑。

        入参：无。
        出参：十六进制摘要。
        失败行为：无。
        """
        ids = "|".join(sorted(fact.fact_id for fact in self.kb.facts))   # 事实编号串
        return hashlib.sha1(ids.encode("utf-8")).hexdigest()[:12]        # 摘要

    def create(self, role: str) -> Dict[str, Any]:            # 创建任务
        """创建一个待执行任务。

        入参：role 创建角色。
        出参：任务字典。
        失败行为：不抛异常。
        """
        task_id = "task-" + uuid.uuid4().hex[:8]              # 生成编号
        record = {"task_id": task_id, "state": TaskState.CREATED.value,
                  "role": role, "payload": {}, "done_steps": [],
                  "input_hash": self._input_hash(), "gate": None,
                  "history": [], "updated_at": datetime.now(timezone.utc).isoformat()}   # 初始记录
        self._save(record)                                    # 落盘
        return record                                         # 返回

    def _save(self, record: Dict[str, Any]) -> None:          # 保存
        """把任务写入磁盘。

        入参：record 记录。
        出参：无。
        失败行为：磁盘错误时抛异常。
        """
        record["updated_at"] = datetime.now(timezone.utc).isoformat()   # 更新时间
        self._path(record["task_id"]).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")   # 写文件

    def get(self, task_id: str) -> Dict[str, Any]:            # 读取
        """读取任务记录。

        入参：task_id 任务编号。
        出参：记录字典。
        失败行为：不存在时抛 OrchestratorError(E_SCHEMA)。
        """
        path = self._path(task_id)                            # 路径
        if not path.exists():                                 # 不存在
            raise OrchestratorError(E.E_SCHEMA, "任务不存在：%s" % task_id)   # 抛出
        return json.loads(path.read_text(encoding="utf-8"))    # 解析

    def run(self, task_id: str, steps: Optional[List[str]] = None) -> Dict[str, Any]:   # 执行
        """按步执行，已完成且输入未变则直接复用。

        入参：task_id 任务编号；steps 指定步骤，缺省全部。
        出参：更新后的记录。
        失败行为：步骤非法时抛 OrchestratorError(E_SCHEMA)。
        """
        record = self.get(task_id)                            # 读取
        todo = steps or STEPS                                 # 默认全部
        for step in todo:                                     # 逐步执行
            if step not in STEPS:                             # 非法步骤
                raise OrchestratorError(E.E_SCHEMA, "未知步骤：%s" % step)   # 抛出
            # 原因：幂等键是「任务+步骤+输入指纹」，台账没变就不重算，避免重复消耗与结果漂移
            if step in record["done_steps"] and record["input_hash"] == self._input_hash():
                continue                                      # 直接复用
            record = self._run_step(record, step)             # 执行单步
        self._save(record)                                    # 落盘
        return record                                         # 返回

    def _run_step(self, record: Dict[str, Any], step: str) -> Dict[str, Any]:   # 单步
        """执行一个步骤并更新状态。

        入参：record 记录；step 步骤名。
        出参：更新后的记录。
        失败行为：不抛异常，失败写入 FAILED 状态。
        """
        payload = record["payload"]                           # 取载荷
        facts = self.kb.facts                                  # 事实
        try:                                                  # 统一捕获，保证可恢复
            if step == "conflicts":                            # 冲突
                payload["conflicts"] = a2_conflict.detect(facts).model_dump()   # 检测
                record["state"] = TaskState.CONFLICTS_READY.value   # 状态
            elif step == "baseline":                           # 基线
                output = a3_baseline.build(facts)              # 构建
                payload["baseline"] = output.model_dump()      # 保存
                record["state"] = TaskState.BASELINE_READY.value   # 状态
            elif step == "design":                             # 方案
                from app.agents.contracts import BaselineOutput, ConflictOutput   # 局部导入
                baseline = BaselineOutput.model_validate(payload["baseline"])   # 还原
                conflicts = ConflictOutput.model_validate(payload["conflicts"])   # 还原
                payload["design"] = a4_design.build(baseline, conflicts).model_dump()   # 生成
                record["state"] = TaskState.DESIGN_READY.value   # 状态
            elif step == "verify":                             # 核验 + 开闸门
                from app.agents.contracts import BaselineOutput   # 局部导入
                baseline = BaselineOutput.model_validate(payload["baseline"])   # 还原
                known = {fact.fact_id for fact in facts}       # 已知编号
                verdict = a5_verify.verify_baseline(baseline, known)   # 基线核验
                payload["verify"] = verdict.model_dump()       # 保存
                record["state"] = TaskState.VERIFIED.value     # 状态
                record["gate"] = self._open_gate(record, verdict.passed)   # 开闸门
                record["state"] = TaskState.AWAITING_GATE.value   # 转为待签核
            record["done_steps"].append(step)                  # 记录已完成
            record["input_hash"] = self._input_hash()          # 更新指纹
            record["history"].append({"step": step, "at": datetime.now(timezone.utc).isoformat()})   # 轨迹
        except KeyError as exc:                               # 上游缺失
            record["state"] = TaskState.FAILED.value           # 失败态
            record["history"].append({"step": step, "error": "缺少上游产物：%s" % exc})   # 记录
        return record                                          # 返回

    def _open_gate(self, record: Dict[str, Any], verified: bool) -> Dict[str, Any]:   # 开闸门
        """创建待签核项，必须由安全或管理员确认。

        入参：record 记录；verified 是否通过核验。
        出参：闸门字典。
        失败行为：不抛异常。
        """
        # 原因：方案进入试点等于对外承诺，必须由安全或管理员签核，系统不得自动放行
        return {"gate_id": "gate-" + uuid.uuid4().hex[:6],
                "reason": "方案审核通过，进入单仓区并行试点需签核" if verified else "核验未通过，需人工裁定",
                "required_roles": list(GATE_ROLES), "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "decided_by": "", "decided_at": "", "note": ""}   # 三要素：原因/接手人/确认时间

    def decide(self, task_id: str, role: str, decision: str, note: str = "") -> Dict[str, Any]:   # 签核
        """处理人工闸门。

        入参：task_id 任务编号；role 角色；decision approve/reject；note 说明。
        出参：更新后的记录。
        失败行为：无权限或状态不符时抛 OrchestratorError。
        """
        record = self.get(task_id)                            # 读取
        gate = record.get("gate")                              # 闸门
        if not gate or gate["status"] != "pending":            # 无可签核项
            raise OrchestratorError(E.E_HUMAN_REQUIRED, "当前没有待签核项")   # 抛出
        if role not in GATE_ROLES:                             # 非签核角色
            raise OrchestratorError(E.E_PERM, "签核仅限安全或管理员")   # 抛出
        if decision not in ("approve", "reject"):              # 非法决定
            raise OrchestratorError(E.E_SCHEMA, "decision 只能是 approve 或 reject")   # 抛出
        gate.update({"status": "approved" if decision == "approve" else "rejected",
                     "decided_by": role, "decided_at": datetime.now(timezone.utc).isoformat(),
                     "note": note[:200]})                      # 写入三要素
        record["gate"] = gate                                  # 回写
        record["state"] = TaskState.APPROVED.value if decision == "approve" else TaskState.REJECTED.value   # 状态
        record["history"].append({"gate": decision, "role": role,
                                  "at": gate["decided_at"]})   # 轨迹
        self._save(record)                                     # 落盘
        return record                                          # 返回
