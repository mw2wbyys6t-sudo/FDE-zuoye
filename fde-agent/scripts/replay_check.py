# -*- coding: utf-8 -*-
"""回放校验：按追踪原文重跑，断言结构完全一致（FF6）。"""

import argparse                                              # 参数
import json                                                  # 解析追踪
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 补路径
    sys.path.insert(0, str(ROOT))                             # 保证可导入

from app.agents.a1_evidence import SYSTEM_PROMPT, build_spec   # 复用同一规格
from app.harness.replay import ReplayClient, ReplayError        # 回放客户端
from app.harness.runner import Runner                          # 执行器
from app.harness.trace import TraceWriter                       # 追踪


def main() -> int:                                            # 入口
    """执行回放并比对结构。

    入参：--trace 追踪文件。
    出参：0 一致，1 不一致，2 参数或文件问题。
    失败行为：不抛异常，统一转退出码。
    """
    parser = argparse.ArgumentParser(description="回放校验")     # 参数
    parser.add_argument("--trace", required=True)               # 追踪文件
    args = parser.parse_args()                                  # 解析
    path = Path(args.trace)                                     # 路径
    if not path.exists():                                       # 缺失
        print("追踪文件不存在：%s" % path)                        # 提示
        return 2                                                # 退出
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]   # 读事件
    recorded = [e for e in events if e.get("status") == "ok"]    # 原运行成功记录
    if not recorded:                                            # 无成功记录
        print("追踪中没有成功记录，无法比对")                     # 提示
        return 2                                                # 退出
    expected = recorded[-1]["data"]                             # 期望结构
    step = recorded[-1]["step"]                                 # 步骤名
    prompt_version = recorded[-1]["prompt_version"]             # 提示词版本
    try:                                                        # 回放
        client = ReplayClient(str(path))                        # 回放客户端
        runner = Runner(client, TraceWriter(str(ROOT / "var" / "trace-replay")), max_retry=2)   # 执行器
        spec = build_spec("回放输入", [])                        # 构造同构规格
        spec.step, spec.prompt_version = step, prompt_version   # 对齐原值
        spec.guards = []                                        # 回放只比结构，闸门在首次已执行
        result = runner.run(spec)                               # 重跑
    except ReplayError as exc:                                  # 回放失败
        print("FAIL 回放失败：%s" % exc)                         # 提示
        return 1                                                # 退出
    same = result["data"] == expected                           # 结构比对
    print("%s 回放结构一致 step=%s prompt=%s" % ("PASS" if same else "FAIL", step, prompt_version))   # 输出
    if not same:                                                # 不一致时打印差异摘要
        print("期望：%s" % json.dumps(expected, ensure_ascii=False)[:300])   # 期望
        print("实际：%s" % json.dumps(result["data"], ensure_ascii=False)[:300])   # 实际
    return 0 if same else 1                                     # 退出码


if __name__ == "__main__":                                     # 直接运行
    sys.exit(main())                                           # 返回退出码
