# -*- coding: utf-8 -*-
"""P5 测试：回放一致、故障注入降级、追踪不可写不阻断。"""

from pathlib import Path                                     # 临时目录
import pytest                                                # 断言与异常
from app.agents.a1_evidence import build_spec                 # A1 规格
from app.harness.fault_inject import FaultMode, FaultyClient   # 故障
from app.harness.replay import ReplayClient, ReplayError        # 回放
from app.harness.runner import Runner, RunnerError              # 执行器
from app.harness.trace import TraceWriter                       # 追踪
from app.model.fake import FakeClient                           # 假模型

GOOD = '{"claims":[{"text":"取消单仍被装车","fact_id":"f11"}]}'   # 合法输出


def test_replay_matches(tmp_path: Path):                       # 回放一致
    """验证按追踪原文回放得到相同结构。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    trace = TraceWriter(str(tmp_path))                         # 追踪
    runner = Runner(FakeClient([GOOD]), trace, max_retry=0)     # 执行器
    first = runner.run(build_spec("t", ["f11"]))                # 首次
    path = tmp_path / ("%s.jsonl" % first["trace_id"])          # 追踪文件
    client = ReplayClient(str(path))                            # 回放客户端
    replay = Runner(client, TraceWriter(str(tmp_path / "r")), max_retry=0).run(build_spec("t", ["f11"]))   # 回放
    assert replay["data"] == first["data"]                      # 结构一致


def test_replay_requires_raw(tmp_path: Path):                   # 缺原文
    """验证关闭原文记录时回放给出明确错误。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    trace = TraceWriter(str(tmp_path), store_raw=False)         # 不记录原文
    result = Runner(FakeClient([GOOD]), trace, max_retry=0).run(build_spec("t", ["f11"]))   # 执行
    with pytest.raises(ReplayError):                            # 期望异常
        ReplayClient(str(tmp_path / ("%s.jsonl" % result["trace_id"])))   # 回放


def test_fault_fallback(tmp_path: Path):                        # 故障降级
    """验证模型连续故障时按配置降级。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    faulty = FaultyClient(FakeClient([GOOD]), fail_times=5, mode=FaultMode.RAISE)   # 全故障
    runner = Runner(faulty, TraceWriter(str(tmp_path)), max_retry=2)   # 执行器
    spec = build_spec("t", ["f11"])                             # 规格
    spec.fallback = lambda: {"claims": []}                      # 降级
    result = runner.run(spec)                                   # 执行
    assert result["degraded"] is True                           # 降级标记


def test_fault_without_fallback(tmp_path: Path):                 # 无降级
    """验证完全依赖不可用时抛 E_MODEL_UNAVAILABLE。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    faulty = FaultyClient(FakeClient([GOOD]), fail_times=5)     # 全故障
    runner = Runner(faulty, TraceWriter(str(tmp_path)), max_retry=1)   # 执行器
    with pytest.raises(RunnerError) as info:                    # 期望异常
        runner.run(build_spec("t", ["f11"]))                    # 执行
    assert info.value.code == "E_MODEL_UNAVAILABLE"             # 错误码


def test_garbage_retries(tmp_path: Path):                        # 垃圾输出
    """验证非法文本走重试后仍失败为 E_SCHEMA。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    faulty = FaultyClient(FakeClient([GOOD]), fail_times=5, mode=FaultMode.GARBAGE)   # 只给垃圾
    runner = Runner(faulty, TraceWriter(str(tmp_path)), max_retry=1)   # 执行器
    with pytest.raises(RunnerError) as info:                    # 期望异常
        runner.run(build_spec("t", ["f11"]))                    # 执行
    assert info.value.code == "E_SCHEMA"                        # 错误码


def test_trace_degraded_not_blocking(tmp_path: Path):            # 追踪故障
    """验证追踪目录被文件占用时业务仍完成并标记降级。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    blocker = tmp_path / "blocked"                              # 文件占位
    blocker.write_text("x", encoding="utf-8")                   # 写入
    trace = TraceWriter(str(blocker))                           # 目录创建失败
    assert trace.degraded is True                               # 降级
    result = Runner(FakeClient([GOOD]), trace, max_retry=0).run(build_spec("t", ["f11"]))   # 执行
    assert result["trace_degraded"] is True                      # 结果标记
    assert result["data"]["claims"]                              # 业务结果仍在
