# -*- coding: utf-8 -*-
"""检查行注释覆盖率：业务代码每一行都应有中文注释说明意图。"""

import io                                                     # 构造 tokenize 输入
import sys                                                    # 退出码
import tokenize                                               # 精确区分代码、字符串与注释
from pathlib import Path                                      # 遍历目录

ROOT = Path(__file__).resolve().parents[1]                    # 项目根目录
if str(ROOT) not in sys.path:                                 # 直接运行时脚本目录在首位
    sys.path.insert(0, str(ROOT))                             # 插入项目根，保证 app 包可导入

from app.config import load_config, get                      # 读取阈值

TARGET_DIRS = ["app", "scripts", "tests"]                    # 需要检查的目录


SKIP_TOKENS = {tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
               tokenize.DEDENT, tokenize.ENDMARKER}           # 无实义的词法单元
BRACKET_OPS = {")", "]", "}", ",", ":", "(", "[", "{"}       # 纯括号与分隔符


def count_lines(path: Path) -> tuple:                         # 统计代码行与注释行
    """用 tokenize 精确统计有效代码行与带行注释的行数。

    入参：path 为 Python 文件路径。
    出参：(code_lines, commented_lines)。
    失败行为：语法错误时抛 tokenize.TokenError，由调用方暴露问题而非静默跳过。
    """
    source = path.read_text(encoding="utf-8")                 # 读取源码
    comment_lines = set()                                     # 含注释的行号
    code_lines = set()                                        # 含有效代码的行号
    bracket_only = set()                                      # 仅含括号的行号
    for token in tokenize.generate_tokens(io.StringIO(source).readline):   # 逐词法单元
        if token.type == tokenize.COMMENT:                     # 注释
            comment_lines.add(token.start[0])                  # 记录行号
            continue                                           # 下一个
        if token.type in SKIP_TOKENS or token.type == tokenize.STRING:   # 跳过无实义与字符串（含文档字符串）
            continue                                           # 不参与统计
        row = token.start[0]                                   # 行号
        code_lines.add(row)                                    # 记为代码行
        if token.type == tokenize.OP and token.string in BRACKET_OPS:   # 括号或分隔符
            bracket_only.add(row)                              # 暂记，稍后剔除
    code_lines -= {row for row in bracket_only if row not in comment_lines}   # 纯括号行不计
    commented = len(code_lines & comment_lines)               # 代码行中带注释的数量
    return len(code_lines), commented                         # 返回统计


def main() -> int:                                           # 脚本入口
    """扫描目录并计算总体注释覆盖率。

    入参：无。
    出参：0 表示达标，1 表示低于阈值。
    失败行为：目录不存在时跳过并提示。
    """
    threshold = float(get(load_config(), "guard.min_comment_ratio", 0.95))   # 读取阈值
    total_code = 0                                           # 总代码行
    total_commented = 0                                      # 总已注释行
    for dirname in TARGET_DIRS:                              # 逐个目录
        base = Path(dirname)                                 # 目录对象
        if not base.exists():                                # 目录不存在
            continue                                         # 跳过
        for path in base.rglob("*.py"):                      # 递归所有 py 文件
            code, commented = count_lines(path)              # 统计
            total_code += code                               # 累加
            total_commented += commented                     # 累加
    ratio = (total_commented / total_code) if total_code else 1.0   # 计算比例
    print("代码行 %d，已注释 %d，覆盖率 %.3f（阈值 %.2f）" % (total_code, total_commented, ratio, threshold))   # 输出
    return 0 if ratio >= threshold else 1                    # 达标与否


if __name__ == "__main__":                                   # 直接运行
    sys.exit(main())                                         # 返回退出码
