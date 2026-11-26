# -*- coding: utf-8 -*-
"""回放门禁：导入历史导出文件，跑规则并与标注比对，不达标即失败退出。"""

import argparse                                              # 参数
import json                                                  # 输出
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 补路径
    sys.path.insert(0, str(ROOT))                             # 保证可导入

from app.execution.importer import ImportError_, load_csv     # 导入
from app.execution.replay import replay                        # 回放


def main() -> int:                                             # 入口
    """执行回放并给出通过/不通过。

    入参：--csv 文件；--min-precision/--min-recall 门限；--provenance 来源标记；--json 输出 JSON。
    出参：0 达标，1 不达标，2 文件或无标注。
    失败行为：不抛异常，统一转退出码。
    """
    parser = argparse.ArgumentParser(description="历史回放评估")   # 参数
    parser.add_argument("--csv", required=True)                   # 导出文件
    parser.add_argument("--min-precision", type=float, default=0.6)   # 精确率门限
    parser.add_argument("--min-recall", type=float, default=0.7)      # 召回率门限
    parser.add_argument("--provenance", default="synthetic")        # 来源标记
    parser.add_argument("--json", action="store_true")              # 打印 JSON
    args = parser.parse_args()                                    # 解析
    try:                                                          # 读取
        records = load_csv(args.csv, provenance=args.provenance)    # 导入
    except ImportError_ as exc:                                   # 格式问题
        print("FAIL 导入失败：%s" % exc)                           # 提示
        return 2                                                  # 退出
    report = replay(records)                                      # 回放
    if args.json:                                                 # JSON 模式
        print(json.dumps(report, ensure_ascii=False, indent=2))    # 输出
    else:                                                         # 人类可读
        print("样本 %d 条，有标注 %d 条" % (report["total"], report.get("labeled_count", 0)))
        print("判定分布 %s" % report["levels"])
        print("分规则命中 %s" % report["by_rule"])
        if report["labeled"]:                                     # 有标注才有指标
            print("精确率 %.3f  召回率 %.3f  F1 %.3f  标记率 %.3f"
                  % (report["precision"], report["recall"], report["f1"], report["flag_rate"]))
            print("混淆矩阵 %s" % report["confusion"])
    if not report["labeled"]:                                     # 无标注
        print("FAIL 没有 is_error 标注，无法评估")                 # 提示
        return 2                                                  # 退出
    passed = report["precision"] >= args.min_precision and report["recall"] >= args.min_recall   # 门禁
    print("%s 回放门禁（精确率≥%.2f，召回率≥%.2f）"
          % ("PASS" if passed else "FAIL", args.min_precision, args.min_recall))   # 结论
    return 0 if passed else 1                                     # 退出码


if __name__ == "__main__":                                       # 直接运行
    sys.exit(main())                                             # 返回退出码
