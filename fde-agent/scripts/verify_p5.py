# -*- coding: utf-8 -*-
"""P5 验证脚本：回放一致、P95 预算、三类故障演练与运行手册。"""

import subprocess                                            # 跑子脚本
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 补路径
    sys.path.insert(0, str(ROOT))                             # 保证可导入

from app.agents.a1_evidence import build_spec                  # A1 规格
from app.config import load_config, get                        # 配置
from app.harness.replay import ReplayClient, ReplayError         # 回放
from app.harness.runner import Runner, RunnerError              # 执行器
from app.harness.trace import TraceWriter                        # 追踪
from app.model.fake import FakeClient                            # 假模型

GOOD = '{"claims":[{"text":"取消单仍被装车","fact_id":"f11"}]}'   # 合法输出
WORK = ROOT / "var" / "p5-verify"                             # 验证目录
RESULTS = []                                                  # 结果


def check(name: str, condition: bool, detail: str = "") -> None:   # 记录
    """记录并打印检查结果。

    入参：name 名称；condition 是否通过；detail 说明。
    出参：无。
    失败行为：不抛异常。
    """
    RESULTS.append((name, bool(condition)))                     # 收集
    print("%s %s %s" % ("PASS" if condition else "FAIL", name, detail))   # 打印


def _run(script: str, *args: str) -> int:                       # 跑子脚本
    """执行项目内脚本并返回退出码。

    入参：script 脚本名；args 参数。
    出参：退出码。
    失败行为：不抛异常，退出码原样返回。
    """
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args],
                          capture_output=True, text=True, cwd=str(ROOT))   # 执行
    print(proc.stdout.strip())                                  # 透传输出
    return proc.returncode                                      # 返回码


def main() -> int:                                             # 入口
    """执行 P5 全部验证。

    入参：无。
    出参：0 全通过，1 有失败。
    失败行为：异常向上抛出。
    """
    WORK.mkdir(parents=True, exist_ok=True)                    # 目录
    config = load_config()                                     # 配置
    check("配置含 trace.store_raw", get(config, "trace.store_raw") is True, "store_raw")   # 配置
    check("配置含 slo.p95_ms", int(get(config, "slo.p95_ms", 0)) > 0, str(get(config, "slo.p95_ms")))   # 配置

    trace = TraceWriter(str(WORK / "trace"), store_raw=True)    # 记录原文
    result = Runner(FakeClient([GOOD]), trace, max_retry=0).run(build_spec("p5", ["f11"]))   # 执行
    trace_file = WORK / "trace" / ("%s.jsonl" % result["trace_id"])   # 追踪文件
    content = trace_file.read_text(encoding="utf-8")           # 读内容
    check("追踪文件含模型原文", "\"raw\"" in content and "f11" in content, str(trace_file.name))   # 原文
    check("追踪文件含校验后结构", "\"data\"" in content, "data")   # 结构

    code = _run("replay_check.py", "--trace", str(trace_file))   # 回放
    check("回放结构一致（FF6）", code == 0, "exit=%d" % code)    # 回放

    no_raw = TraceWriter(str(WORK / "trace-noraw"), store_raw=False)   # 关原文
    res2 = Runner(FakeClient([GOOD]), no_raw, max_retry=0).run(build_spec("p5-noraw", ["f11"]))   # 执行
    try:                                                        # 期望无法回放
        ReplayClient(str(WORK / "trace-noraw" / ("%s.jsonl" % res2["trace_id"])))   # 尝试回放
        check("关闭原文时回放被拒", False, "未抛异常")            # 失败
    except ReplayError as exc:                                  # 预期
        check("关闭原文时回放被拒", "store_raw" in str(exc), "ReplayError")   # 拦截

    try:                                                        # 垃圾输出
        Runner(FakeClient(["这不是 JSON"]), TraceWriter(str(WORK / "trace-bad")), max_retry=1).run(
            build_spec("p5-bad", ["f11"]))                      # 执行
        check("垃圾输出失败为 E_SCHEMA", False, "未抛异常")       # 失败
    except RunnerError as exc:                                  # 预期
        check("垃圾输出失败为 E_SCHEMA", exc.code == "E_SCHEMA", exc.code)   # 错误码

    bench = _run("bench_p95.py")                                # 压测
    check("P95 压测达标", bench == 0, "exit=%d" % bench)         # 压测
    drill = _run("drill.py", "--fault", "all")                  # 演练
    check("三类故障演练通过", drill == 0, "exit=%d" % drill)      # 演练
    check("演练报告已落盘", (ROOT / "var" / "drill" / "report.json").exists(), "report.json")   # 报告

    runbook = ROOT / "docs" / "runbook.md"                      # 运行手册
    text = runbook.read_text(encoding="utf-8") if runbook.exists() else ""   # 读取
    sections = ["启动与健康", "降级处理", "回放与验收", "停止与回滚"]   # 必需章节
    check("运行手册关键章节齐全", all(name in text for name in sections), str(len(text)))   # 手册

    failed = [name for name, ok in RESULTS if not ok]           # 汇总
    print("\n共 %d 项，失败 %d 项" % (len(RESULTS), len(failed)))   # 输出
    return 0 if not failed else 1                              # 退出码


if __name__ == "__main__":                                     # 直接运行
    sys.exit(main())                                           # 返回退出码
