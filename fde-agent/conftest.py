# -*- coding: utf-8 -*-
"""pytest 引导：把项目根目录加入 sys.path，保证 app 包可导入。"""

import sys                                                   # 修改模块搜索路径
from pathlib import Path                                     # 计算项目根

ROOT = Path(__file__).resolve().parent                        # 当前文件所在目录即项目根
if str(ROOT) not in sys.path:                                  # 避免重复插入
    sys.path.insert(0, str(ROOT))                              # 插入到最前，优先使用本地代码
