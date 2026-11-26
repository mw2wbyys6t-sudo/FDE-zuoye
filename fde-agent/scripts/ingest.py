# -*- coding: utf-8 -*-
"""P1 入库命令行：把台账文件灌入本地知识库并落盘。"""

import argparse                                              # 解析参数
import sys                                                   # 退出码
from pathlib import Path                                     # 路径处理

ROOT = Path(__file__).resolve().parents[1]                    # 项目根
if str(ROOT) not in sys.path:                                 # 直接运行时补路径
    sys.path.insert(0, str(ROOT))                             # 保证 app 可导入

from app.config import load_config, get                       # 配置
from app.knowledge.ingest import parse_ledger_file            # 台账解析
from app.knowledge.store import KnowledgeStore                # 存储


def main() -> int:                                            # 入口
    """执行入库并打印统计。

    入参：命令行 --source 指定台账，--store 指定知识库目录。
    出参：0 表示成功。
    失败行为：文件缺失时打印错误并返回 2。
    """
    parser = argparse.ArgumentParser(description="台账入库")   # 参数解析器
    parser.add_argument("--source", required=True, help="台账 markdown 路径")   # 源文件
    parser.add_argument("--store", default=get(load_config(), "app.kb_dir", "./var/kb"),
                        help="知识库目录")                     # 目标目录
    args = parser.parse_args()                                # 解析
    if not Path(args.source).exists():                        # 源文件校验
        print("源文件不存在：%s" % args.source)                 # 提示
        return 2                                              # 非零退出
    facts = parse_ledger_file(args.source)                    # 解析台账
    store = KnowledgeStore(args.store)                        # 打开存储
    result = store.ingest(facts)                              # 入库
    store.save()                                              # 落盘
    print("入库完成：facts=%d chunks=%d 目录=%s" % (result["facts"], result["chunks"], args.store))   # 输出
    print("维度分布：%s" % store.stats()["dimensions"])        # 输出维度分布
    return 0                                                  # 成功


if __name__ == "__main__":                                    # 直接运行
    sys.exit(main())                                          # 返回退出码
