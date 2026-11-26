# -*- coding: utf-8 -*-
"""契约测试：校验 schema 的严格性（禁止多余字段、事实编号格式）。"""

import pytest                                                  # 断言与异常
from pydantic import ValidationError                           # 校验异常
from app.harness.schema import Claim, EvidenceOutput           # 被测对象


def test_claim_accepts_valid_fact_id():                        # 合法编号应通过
    """验证合法事实编号可正常构造。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    claim = Claim(text="取消单仍被装车", fact_id="f11")          # 构造合法条目
    assert claim.fact_id == "f11"                              # 编号原样保留


def test_claim_allows_empty_fact_id_for_guard():                # 空编号交给闸门判定
    """验证 schema 不强判编号合法性，保持错误码统一为 E_NO_EVIDENCE。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    claim = Claim(text="拣选是主因", fact_id="")                  # 空编号可构造
    assert claim.fact_id == ""                                  # 由证据闸门负责拦截


def test_schema_forbids_extra_fields():                        # 多余字段应拒绝
    """验证契约禁止模型夹带额外字段。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    with pytest.raises(ValidationError):                        # 期望校验异常
        EvidenceOutput(claims=[], confidence=0.9)               # confidence 不在契约内


def test_empty_claims_allowed():                               # 空结论合法
    """验证无证据时可以返回空列表。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    out = EvidenceOutput(claims=[])                             # 空列表构造
    assert out.claims == []                                     # 保持为空
