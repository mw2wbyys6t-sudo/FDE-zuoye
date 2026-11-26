# -*- coding: utf-8 -*-
"""检查硬编码：代码里不得出现密钥字面量与写死的模型地址。"""

import re                                                    # 正则匹配
import sys                                                   # 退出码
from pathlib import Path                                     # 遍历

PATTERNS = (r"\bsk-[A-Za-z0-9]{10,}", r"https?://")          # 密钥字面量（带长度约束，避免命中 task-）与地址
SKIP_DIRS = {"var", ".venv", "__pycache__"}                  # 不检查的目录
SKIP_FILES = {"check_config.py"}                             # 规则自身保存了模式字符串，跳过避免自证


def main() -> int:                                           # 脚本入口
    """扫描 app/scripts/tests 中的 Python 文件。

    入参：无。
    出参：0 表示无硬编码，1 表示命中。
    失败行为：读取失败时抛异常，不静默跳过。
    """
    hits = []                                                # 命中记录
    for base_name in ("app", "scripts", "tests"):            # 三个源码目录
        base = Path(base_name)                               # 目录对象
        if not base.exists():                                # 目录不存在
            continue                                         # 跳过
        for path in base.rglob("*.py"):                      # 所有 py 文件
            if path.name in SKIP_FILES:                      # 跳过检查脚本自身
                continue                                     # 继续
            if any(part in SKIP_DIRS for part in path.parts):   # 跳过缓存目录
                continue                                     # 继续
            for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):   # 逐行
                line = raw.strip()                           # 去空白
                if line.startswith("#"):                     # 纯注释行允许出现示例
                    continue                                 # 跳过
                for token in PATTERNS:                       # 逐个模式
                    if re.search(token, line):               # 命中
                        hits.append("%s:%d 含 %s" % (path, number, token))   # 记录
    for item in hits:                                        # 输出
        print("FAIL", item)                                  # 打印
    print("硬编码检查：命中 %d 处" % len(hits))               # 汇总
    return 0 if not hits else 1                              # 返回退出码


if __name__ == "__main__":                                   # 直接运行
    sys.exit(main())                                         # 返回退出码
