# -*- coding: utf-8 -*-
"""执行层测试：四条规则、挂起三要素与指标闭环。"""

from pathlib import Path                                      # 临时目录
import pytest                                                 # 断言
from app.execution.models import DispositionIn, ScanContext     # 契约
from app.execution.service import ExecutionError, ExecutionService   # 服务

BASE = dict(biz_id="wv-1001", sku="SKU-A500", base_sku="SKU-A", spec="500ml",
            neighbor_specs=["750ml"], data_asof="2026-11-19T08:00")   # 基础上下文


def _svc(tmp_path: Path) -> ExecutionService:                 # 构造服务
    """创建使用临时目录的执行服务。

    入参：tmp_path 临时目录。
    出参：ExecutionService。
    失败行为：无。
    """
    return ExecutionService(str(tmp_path / "exec"))            # 独立事件流


def test_pass_without_signal(tmp_path: Path):                  # 全通过
    """验证无任何信号时放行。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    decision = _svc(tmp_path).scan(ScanContext(**dict(BASE, neighbor_specs=[])))   # 无邻位差异
    assert decision.level == "pass" and not decision.requires_human   # 放行


def test_r1_hint(tmp_path: Path):                              # 规格差异
    """验证相邻货位不同规格时给提示而非挂起。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    decision = _svc(tmp_path).scan(ScanContext(**BASE))         # 判定
    assert decision.level == "hint"                             # 提示
    assert decision.reasons[0].rule_id == "R1"                  # 命中 R1
    assert decision.requires_human is False                     # 不需人审


def test_r2_hold_with_asof(tmp_path: Path):                     # 取消挂起
    """验证取消单挂起并要求波次计划员处置，同时回显数据截止时间。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    decision = _svc(tmp_path).scan(ScanContext(**BASE, cancelled=True))   # 判定
    assert decision.level == "hold" and decision.requires_human   # 挂起
    assert decision.human_role == "planner"                       # 处置岗位
    assert "2026-11-19T08:00" in decision.reasons[0].message      # 截止时间回显


def test_r3_note_not_attached(tmp_path: Path):                   # 说明未随单
    """验证便签说明未随单时给提示。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    decision = _svc(tmp_path).scan(ScanContext(**BASE, note_text="易碎", note_attached=False))   # 判定
    assert any(r.rule_id == "R3" for r in decision.reasons)       # 命中 R3


def test_r4_system_down(tmp_path: Path):                         # 系统不可用
    """验证系统不可用时挂起并转安全岗。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    decision = _svc(tmp_path).scan(ScanContext(**BASE, system_available=False))   # 判定
    assert decision.level == "hold" and decision.human_role == "safety"   # 挂起


def test_dispose_requires_three_elements(tmp_path: Path):         # 三要素
    """验证挂起单缺三要素被拒，补齐后可闭环。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    svc = _svc(tmp_path)                                        # 服务
    decision = svc.scan(ScanContext(**BASE, cancelled=True))     # 挂起
    with pytest.raises(ExecutionError) as info:                  # 缺要素
        svc.dispose(DispositionIn(decision_id=decision.decision_id, action="override"))   # 处置
    assert info.value.code == "E_HUMAN_REQUIRED"                 # 错误码
    done = svc.dispose(DispositionIn(decision_id=decision.decision_id, action="override",
                                     operator="唐映秋", reason="客户确认保留", confirmed_at="2026-11-19T08:05"))   # 补齐
    assert done.closed is True                                   # 已闭环
    stats = svc.metrics()                                        # 指标
    assert stats["holds"] == 1 and stats["closure_rate"] == 1.0   # 闭环率


def test_dedupe_same_scan(tmp_path: Path):                       # 重复扫码
    """验证窗口内同业务同 SKU 重复扫码不再产生新判定。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    svc = ExecutionService(str(tmp_path / "exec"), dedupe_minutes=10)   # 开启去重
    first = svc.scan(ScanContext(**BASE))                        # 首次
    second = svc.scan(ScanContext(**BASE))                       # 重复
    assert first.dedupe is False and second.dedupe is True        # 第二次标记复用
    assert second.decision_id == first.decision_id                # 复用同一判定
    stats = svc.metrics()                                        # 指标
    assert stats["scans"] == 1 and stats["dedupe_hits"] == 1      # 判定不重复计数


def test_overdue_holds(tmp_path: Path):                          # 超时挂起
    """验证超时阈值为 0 时未闭环挂起立即计入超时。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    svc = ExecutionService(str(tmp_path / "exec"), overdue_minutes=0)   # 立即超时
    svc.scan(ScanContext(**dict(BASE, cancelled=True)))           # 产生挂起
    stats = svc.metrics()                                        # 指标
    assert stats["unresolved_holds"] == 1 and stats["overdue_holds"] == 1   # 超时计数
