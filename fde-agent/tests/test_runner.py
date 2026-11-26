# -*- coding: utf-8 -*-
"""执行器测试：验证重试、失败上抛、追踪落盘与降级标记。"""

import json                                                     # 读取追踪文件
from pathlib import Path                                        # 路径处理
import pytest                                                   # 断言与异常
from app import errors as E                                     # 错误码
from app.harness.runner import RunSpec, Runner, RunnerError      # 被测对象
from app.harness.schema import EvidenceOutput                    # 契约
from app.harness.trace import TraceWriter                        # 追踪
from app.model.fake import FakeClient                            # 假模型

GOOD = '{"claims":[{"text":"取消单仍被装车","fact_id":"f11"}]}'   # 合法输出


def _spec(script_len: int = 1) -> RunSpec:                      # 构造测试规格
    """生成一个最小 RunSpec。

    入参：script_len 仅用于保持签名一致，当前未使用。
    出参：RunSpec 实例。
    失败行为：无。
    """
    return RunSpec(step="t", prompt_version="v-test", schema=EvidenceOutput,
                   system="s", user="u")                        # 固定规格


def test_runner_retries_then_succeeds(tmp_path: Path):           # 重试成功
    """验证首次非法、第二次合法时返回 attempts=2。

    入参：tmp_path pytest 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    trace = TraceWriter(str(tmp_path))                           # 临时追踪目录
    runner = Runner(FakeClient(["不是 JSON", GOOD]), trace, max_retry=2)   # 假模型先错后对
    result = runner.run(_spec())                                 # 执行
    assert result["attempts"] == 2                               # 第二次才成功
    assert result["degraded"] is False                           # 未降级


def test_runner_fails_after_retries(tmp_path: Path):             # 重试耗尽
    """验证始终非法时抛 RunnerError(E_SCHEMA)。

    入参：tmp_path pytest 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    trace = TraceWriter(str(tmp_path))                           # 临时追踪目录
    runner = Runner(FakeClient(["坏输出"]), trace, max_retry=2)   # 始终非法
    with pytest.raises(RunnerError) as info:                     # 期望异常
        runner.run(_spec())                                      # 执行
    assert info.value.code == E.E_SCHEMA                         # 错误码正确


def test_runner_degrades(tmp_path: Path):                        # 降级路径
    """验证配置降级时返回 degraded=True。

    入参：tmp_path pytest 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    trace = TraceWriter(str(tmp_path))                           # 临时追踪目录
    runner = Runner(FakeClient(["坏输出"]), trace, max_retry=1)   # 始终非法
    spec = _spec()                                               # 基础规格
    spec.fallback = lambda: {"claims": []}                       # 挂降级结果
    result = runner.run(spec)                                    # 执行
    assert result["degraded"] is True                            # 标记降级


def test_trace_written(tmp_path: Path):                          # 追踪落盘
    """验证每次尝试都写入 JSONL 且含 prompt_version。

    入参：tmp_path pytest 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    trace = TraceWriter(str(tmp_path))                           # 临时追踪目录
    runner = Runner(FakeClient([GOOD]), trace, max_retry=0)       # 一次成功
    result = runner.run(_spec())                                 # 执行
    path = tmp_path / ("%s.jsonl" % result["trace_id"])           # 预期追踪文件
    assert path.exists()                                         # 文件必须存在
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]   # 逐行解析
    assert any(item.get("prompt_version") == "v-test" for item in lines)   # 必须记录提示词版本
