# -*- coding: utf-8 -*-
"""检查依赖方向：harness 与 model 不得反向依赖 api 层。"""

import re                                                    # 解析 import
import sys                                                   # 退出码
from pathlib import Path                                     # 遍历

RULES = {                                                    # 目录 -> 禁止依赖的模块前缀
    "app/harness": ("app.api",),                             # 执行器不得依赖接口层
    "app/model": ("app.api", "app.harness"),                 # 模型层只依赖自身与基础模块
    "app/agents": ("app.api",),                              # agent 不得依赖接口层，保证可独立评估
}


def imported_modules(text: str) -> list:                     # 提取导入的模块名
    """解析源码中的 import 语句。

    入参：text 为文件全文。
    出参：模块名列表。
    失败行为：不抛异常，无法识别的行直接忽略。
    """
    found = []                                               # 收集结果
    for line in text.splitlines():                           # 逐行
        stripped = line.strip()                              # 去空白
        match = re.match(r"from\s+(app[\w\.]*)\s+import", stripped)   # from x import y
        if match:                                            # 命中
            found.append(match.group(1))                     # 记录模块
    return found                                             # 返回


def main() -> int:                                           # 脚本入口
    """扫描指定目录并检查依赖方向。

    入参：无。
    出参：0 表示合规，1 表示存在反向依赖。
    失败行为：目录缺失时跳过。
    """
    violations = []                                           # 违规记录
    for dirname, forbidden in RULES.items():                  # 逐个目录
        base = Path(dirname)                                  # 目录对象
        if not base.exists():                                 # 不存在
            continue                                          # 跳过
        for path in base.rglob("*.py"):                       # 所有文件
            for module in imported_modules(path.read_text(encoding="utf-8")):   # 提取依赖
                if any(module == f or module.startswith(f + ".") for f in forbidden):   # 命中禁止
                    violations.append("%s -> %s" % (path, module))   # 记录
    for item in violations:                                   # 输出
        print("FAIL", item)                                   # 打印
    print("依赖方向检查：违规 %d 处" % len(violations))        # 汇总
    return 0 if not violations else 1                         # 返回退出码


if __name__ == "__main__":                                   # 直接运行
    sys.exit(main())                                          # 返回退出码
