# -*- coding: utf-8 -*-
"""检查关键业务函数的"为什么这么卡"注释是否齐全。"""

import re                                                    # 提取函数块
import sys                                                   # 退出码
from pathlib import Path                                     # 路径

TARGETS = [                                                  # 必须带原因注释的函数
    ("app/api/auth.py", "_dep"),                             # 角色校验
    ("app/harness/guards.py", "check_evidence"),             # 证据闸门
    ("app/harness/guards.py", "check_boundary"),             # 边界闸门
    ("app/harness/guards.py", "check_permission"),           # 权限闸门
]


def function_block(text: str, name: str) -> str:             # 抽取函数源码块
    """从源码中截取指定函数到下一个顶层定义之间的文本。

    入参：text 全文件文本；name 函数名。
    出参：函数块字符串；找不到时返回空串。
    失败行为：不抛异常。
    """
    pattern = re.compile(r"^\s*def %s\b" % re.escape(name), re.M)   # 定位函数定义
    match = pattern.search(text)                             # 查找
    if not match:                                            # 未找到
        return ""                                            # 返回空
    rest = text[match.end():]                                # 取函数后文
    nxt = re.search(r"^\s*(def |class )", rest, re.M)        # 找下一个顶层定义
    return rest[: nxt.start()] if nxt else rest              # 截断到下一个定义


def main() -> int:                                           # 脚本入口
    """逐个检查关键函数是否含"# 原因"注释。

    入参：无。
    出参：0 表示全部达标，1 表示存在缺失。
    失败行为：文件不存在时判为失败。
    """
    failures = []                                            # 收集失败项
    for path_str, func in TARGETS:                           # 遍历目标
        path = Path(path_str)                                # 路径对象
        if not path.exists():                                # 文件缺失
            failures.append("%s 不存在" % path_str)           # 记录
            continue                                         # 继续下一个
        block = function_block(path.read_text(encoding="utf-8"), func)   # 取函数块
        if "# 原因" not in block:                            # 缺少原因注释
            failures.append("%s::%s 缺少「# 原因」注释" % (path_str, func))   # 记录
    for item in failures:                                    # 输出失败项
        print("FAIL", item)                                  # 打印
    print("检查 %d 个函数，失败 %d 个" % (len(TARGETS), len(failures)))   # 汇总
    return 0 if not failures else 1                          # 返回退出码


if __name__ == "__main__":                                   # 直接运行
    sys.exit(main())                                         # 返回退出码
