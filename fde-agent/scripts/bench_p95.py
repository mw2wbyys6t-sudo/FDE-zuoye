# -*- coding: utf-8 -*-
"""P95 压测：用本地 Fake 模型压执行器，验证链路开销不超预算。"""

import statistics                                            # 中位数
import sys                                                   # 退出码
import time                                                  # 计时
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 补路径
    sys.path.insert(0, str(ROOT))                             # 保证可导入

from app.agents.a1_evidence import build_spec                  # 复用 A1 规格
from app.config import load_config, get                        # 配置
from app.harness.runner import Runner                          # 执行器
from app.harness.trace import TraceWriter                       # 追踪
from app.model.fake import FakeClient                           # 假模型

GOOD = '{"claims":[{"text":"取消单仍被装车","fact_id":"f11"}]}'   # 固定输出
WARMUP = 5                                                    # 预热次数
ROUNDS = 50                                                   # 正式轮数


def main() -> int:                                            # 入口
    """执行压测并输出 P50 / P95。

    入参：无。
    出参：0 达标，1 超预算。
    失败行为：不抛异常，统一转退出码。
    """
    config = load_config()                                    # 配置
    budget = int(get(config, "slo.p95_ms", 8000))             # P95 预算
    trace = TraceWriter(str(ROOT / "var" / "trace-bench"), store_raw=False)   # 压测不落原文，避免 IO 干扰
    runner = Runner(FakeClient([GOOD]), trace, max_retry=0)    # 执行器
    spec = build_spec("压测", ["f11"])                         # 规格
    spec.guards = []                                          # 压测只测链路开销
    for _ in range(WARMUP):                                   # 预热
        runner.run(spec)                                      # 执行
    samples = []                                              # 采样
    for _ in range(ROUNDS):                                   # 正式轮
        start = time.perf_counter()                           # 开始
        runner.run(spec)                                      # 执行
        samples.append((time.perf_counter() - start) * 1000)   # 毫秒
    samples.sort()                                            # 排序
    p50 = statistics.median(samples)                          # 中位数
    p95 = samples[max(0, int(len(samples) * 0.95) - 1)]        # P95
    print("轮数 %d  P50 %.1f ms  P95 %.1f ms  预算 %d ms" % (ROUNDS, p50, p95, budget))   # 输出
    passed = p95 <= budget                                    # 判定
    print("%s P95 压测" % ("PASS" if passed else "FAIL"))      # 结论
    return 0 if passed else 1                                 # 退出码


if __name__ == "__main__":                                    # 直接运行
    sys.exit(main())                                          # 返回退出码
