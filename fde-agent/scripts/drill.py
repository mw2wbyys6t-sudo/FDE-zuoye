# -*- coding: utf-8 -*-
"""故障演练：模型不可用、知识库为空、追踪不可写，验证降级路径。"""

import argparse                                              # 参数
import json                                                  # 报告
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 补路径
    sys.path.insert(0, str(ROOT))                             # 保证可导入

from app.agents import a2_conflict, a3_baseline, a4_design      # 降级链路
from app.agents.a1_evidence import build_spec                   # A1 规格
from app.harness.fault_inject import FaultMode, FaultyClient     # 故障注入
from app.harness.runner import Runner, RunnerError               # 执行器
from app.harness.trace import TraceWriter                        # 追踪
from app.knowledge.store import KnowledgeStore                   # 知识库
from app.model.fake import FakeClient                            # 假模型

GOOD = '{"claims":[{"text":"取消单仍被装车","fact_id":"f11"}]}'   # 合法输出
RESULTS = []                                                  # 结果


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录
    """记录并打印检查结果。

    入参：name 名称；condition 是否通过；detail 说明。
    出参：无。
    失败行为：不抛异常。
    """
    RESULTS.append({"check": name, "passed": bool(condition), "detail": detail})   # 收集
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 打印


def drill_model_down(trace_dir: Path) -> None:                # 模型不可用
    """验证模型全挂时有降级则降级，无降级则报依赖不可用。

    入参：trace_dir 追踪目录。
    出参：无。
    失败行为：不抛异常。
    """
    trace = TraceWriter(str(trace_dir))                       # 追踪
    faulty = FaultyClient(FakeClient([GOOD]), fail_times=5, mode=FaultMode.RAISE)   # 五次故障
    runner = Runner(faulty, trace, max_retry=2)               # 重试两次
    spec = build_spec("故障演练", ["f11"])                     # 规格
    spec.guards = []                                          # 只看降级
    spec.fallback = lambda: {"claims": []}                    # 降级结果
    result = runner.run(spec)                                 # 执行
    check("模型不可用时有降级", result["degraded"] is True, str(result["degraded"]))   # 降级
    no_fallback = Runner(FaultyClient(FakeClient([GOOD]), fail_times=5), trace, max_retry=1)   # 无降级
    bare_spec = build_spec("故障演练-无降级", ["f11"])          # 新规格，避免继承 fallback
    bare_spec.guards = []                                     # 只看依赖错误
    try:                                                      # 期望报错
        no_fallback.run(bare_spec)                            # 执行
        check("无降级时报错", False, "未抛异常")               # 失败
    except RunnerError as exc:                                # 预期
        check("无降级时报依赖不可用", exc.code == "E_MODEL_UNAVAILABLE", exc.code)   # 错误码


def drill_vector_down(work: Path) -> None:                    # 知识库为空
    """验证知识库为空时链路不崩，基线全 TBD。

    入参：work 工作目录。
    出参：无。
    失败行为：不抛异常。
    """
    empty = KnowledgeStore(str(work / "empty-kb"))            # 空知识库
    conflicts = a2_conflict.detect(empty.facts)               # 冲突
    baseline = a3_baseline.build(empty.facts)                 # 基线
    design = a4_design.build(baseline, conflicts)             # 方案
    check("空知识库仍产出基线", len(baseline.rows) == 5, str(len(baseline.rows)))   # 五指标
    check("空知识库基线全 TBD", all(row.current == "TBD" for row in baseline.rows), "TBD")   # 待定
    check("空知识库仍产出方案", len(design.rules) == 4, str(len(design.rules)))   # 规则


def drill_trace_down(work: Path) -> None:                     # 追踪不可写
    """验证追踪写入失败时业务不中断且显式标记降级。

    入参：work 工作目录。
    出参：无。
    失败行为：不抛异常。
    """
    blocker = work / "trace-blocker"                          # 用文件占住目录位置
    blocker.write_text("x", encoding="utf-8")                 # 写入文件
    trace = TraceWriter(str(blocker))                         # 目录创建会失败
    check("追踪不可写标记降级", trace.degraded is True, str(trace.degraded))   # 降级
    runner = Runner(FakeClient([GOOD]), trace, max_retry=0)    # 执行器
    spec = build_spec("追踪演练", ["f11"])                     # 规格
    spec.guards = []                                          # 忽略闸门
    result = runner.run(spec)                                 # 执行
    check("追踪失败不阻断业务", result["data"]["claims"][0]["fact_id"] == "f11", "ok")   # 业务成功
    check("结果带追踪降级标记", result["trace_degraded"] is True, str(result["trace_degraded"]))   # 标记


def main() -> int:                                            # 入口
    """按参数执行对应演练。

    入参：--fault model_down|vector_down|trace_down|all。
    出参：0 全通过。
    失败行为：不抛异常。
    """
    parser = argparse.ArgumentParser(description="故障演练")   # 参数
    parser.add_argument("--fault", default="all")              # 演练项
    args = parser.parse_args()                                 # 解析
    work = ROOT / "var" / "drill"                              # 工作目录
    work.mkdir(parents=True, exist_ok=True)                    # 创建
    trace_dir = work / "trace"                                 # 追踪目录
    trace_dir.mkdir(exist_ok=True)                             # 创建
    if args.fault in ("model_down", "all"):                    # 模型故障
        drill_model_down(trace_dir)                            # 执行
    if args.fault in ("vector_down", "all"):                   # 知识库为空
        drill_vector_down(work)                                # 执行
    if args.fault in ("trace_down", "all"):                    # 追踪故障
        drill_trace_down(work)                                 # 执行
    report = {"fault": args.fault, "results": RESULTS,
              "passed": all(item["passed"] for item in RESULTS)}   # 报告
    (work / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                      encoding="utf-8")        # 落盘
    failed = [item["check"] for item in RESULTS if not item["passed"]]   # 失败项
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 汇总
    return 0 if not failed else 1                              # 退出码


if __name__ == "__main__":                                     # 直接运行
    sys.exit(main())                                           # 返回退出码
