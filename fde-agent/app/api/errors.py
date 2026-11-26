# -*- coding: utf-8 -*-
"""错误码再导出：保持接口层历史引用可用，实际定义在 app/errors.py。"""

from app.errors import (                        # 只做再导出，避免出现两套错误码
    E_SCHEMA,                                   # schema 错误
    E_NO_EVIDENCE,                              # 无证据
    E_BOUNDARY,                                 # 越界
    E_PERM,                                     # 权限
    E_MODEL_UNAVAILABLE,                        # 模型不可用
    E_TIMEOUT,                                  # 超时
    E_HUMAN_REQUIRED,                           # 需人工
    E_CONFLICT_UNRESOLVED,                      # 口径冲突
    E_INTERNAL,                                 # 内部错误
)
