# -*- coding: utf-8 -*-
"""Agent 测试：抽取闸门、三类冲突、基线缺项与独立核验。"""

import pytest                                                # 断言与异常
from app.agents import a1_evidence, a2_conflict, a3_baseline, a4_design, a5_verify   # 被测 agent
from app.domain.models import Confidence, Dimension, Fact     # 模型
from app.harness.guards import GuardError                     # 闸门异常
from app.harness.runner import Runner                         # 执行器
from app.harness.trace import TraceWriter                      # 追踪
from app.model.fake import FakeClient                          # 假模型
from pathlib import Path                                       # 临时目录


def _fact(fid: str, text: str) -> Fact:                        # 构造事实
    """生成一条测试事实。

    入参：fid 编号；text 正文。
    出参：Fact。
    失败行为：无。
    """
    return Fact(fact_id=fid, role="测试", statement=text,
                dimension=Dimension.FACT, confidence=Confidence.FACT,
                roles_visible=["engineer"])                     # 最小事实


def test_a1_accepts_valid_claim(tmp_path: Path):                # 合法抽取
    """验证合法 JSON 可通过并带编号。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    runner = Runner(FakeClient(['{"claims":[{"text":"取消单仍被装车","fact_id":"f11"}]}']),
                    TraceWriter(str(tmp_path)), max_retry=0)    # 假模型
    result = a1_evidence.extract(runner, "取消单被装车", ["f11", "f31"])   # 抽取
    assert result["data"]["claims"][0]["fact_id"] == "f11"      # 编号保留


def test_a1_blocks_missing_evidence(tmp_path: Path):            # 无证据拦截
    """验证编号不存在时被闸门拒绝。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    runner = Runner(FakeClient(['{"claims":[{"text":"拣选是主因","fact_id":"f99"}]}']),
                    TraceWriter(str(tmp_path)), max_retry=0)    # 编造编号
    with pytest.raises(GuardError):                             # 期望拦截
        a1_evidence.extract(runner, "拣选是主因", ["f11"])        # 抽取


def test_a2_value_conflict():                                   # 数值冲突
    """验证同一指标两个数值被判为冲突。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    facts = [_fact("f01", "错发率 1.8%，目标 0.5%"), _fact("f02", "错发率 2.2% 需要整改")]   # 两个数值
    out = a2_conflict.detect(facts)                             # 检测
    assert any(item.kind == "value" and item.metric == "错发率" for item in out.conflicts)   # 命中


def test_a2_definition_and_scope():                             # 口径与范围冲突
    """验证完成口径与提示/阻断范围被识别。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    facts = [_fact("f50", "仓库按出库算完成，配送站按正确收货算完成"),
             _fact("f05", "只做提示，不自动操作叉车"),
             _fact("f34", "待刷新状态是只做提示还是要阻断操作")]   # 三类素材
    kinds = {item.kind for item in a2_conflict.detect(facts).conflicts}   # 类型集合
    assert "definition" in kinds and "scope" in kinds           # 两类都命中


def test_a3_baseline_marks_tbd():                               # 基线缺项
    """验证缺字段写 TBD 且保留证据。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    facts = [_fact("f00", "错发率 1.8%，目标 0.5%")]              # 只有错发率
    out = a3_baseline.build(facts)                               # 构建
    assert len(out.rows) == 5                                    # 五个指标
    assert out.rows[0].current == "1.8"                           # 现状值
    assert out.rows[0].owner == "TBD"                            # 责任人待定
    assert out.tbd_count > 0                                     # 存在待定字段


def test_a5_verifies_claims():                                  # 核验
    """验证假编号不通过、真编号通过。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    known = {"f11", "f31"}                                      # 已知编号
    good = a5_verify.verify_claims([{"text": "x", "fact_id": "f11"}], known)   # 合法
    bad = a5_verify.verify_claims([{"text": "x", "fact_id": "f99"}], known)     # 非法
    assert good.passed and not bad.passed                       # 结果相反


def test_a5_verifies_baseline():                                # 基线核验
    """验证估计值行可追溯但提示需人工确认。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    baseline = a3_baseline.build([_fact("f00", "错发率 1.8%")])   # 含估计值
    verdict = a5_verify.verify_baseline(baseline, {"f00"})       # 核验
    assert verdict.items[0].passed                               # 有证据的行结构通过
    assert verdict.passed is False                               # 其余四行无证据，总体不通过
    assert any("估计值" in item.reason for item in verdict.items)  # 提示等级


def test_verify_relevance():                                    # 相关性核验
    """验证结论与被引用事实不匹配时判定失败。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    facts = {"f11": "取消订单已进入波次，拣完后仍被装车", "f31": "订单取消事件同步延迟 12 分钟"}   # 两条事实
    good = a5_verify.verify_relevance([{"text": "取消单仍被装车", "fact_id": "f11"}], facts)   # 匹配
    bad = a5_verify.verify_relevance([{"text": "拣选是错发主因", "fact_id": "f31"}], facts)     # 不匹配
    assert good.passed and not bad.passed                        # 结果相反


def test_a4_design():                                           # 方案生成
    """验证方案含四条规则、边界与证据引用。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    baseline = a3_baseline.build([_fact("f00", "错发率 1.8%")])   # 基线
    conflicts = a2_conflict.detect([_fact("f50", "仓库按出库算完成，配送站按正确收货算完成")])   # 冲突
    design = a4_design.build(baseline, conflicts)                 # 生成
    assert len(design.rules) == 4                                 # 四条规则
    assert any("不自动操作叉车" in item for item in design.boundary)   # 边界
    assert design.fact_refs                                       # 证据引用
    assert design.open_questions                                  # 待答问题
