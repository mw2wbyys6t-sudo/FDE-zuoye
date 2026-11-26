# -*- coding: utf-8 -*-
"""错误码常量：所有对外错误必须使用这里的编号，禁止在业务处写裸字符串。"""

E_SCHEMA = "E_SCHEMA"                          # 模型输出不符合约定 schema
E_NO_EVIDENCE = "E_NO_EVIDENCE"                # 结论缺少事实编号，按规则必须拒答
E_BOUNDARY = "E_BOUNDARY"                      # 触碰边界：写库、自动审批、自动操作设备
E_PERM = "E_PERM"                              # 角色无权限
E_MODEL_UNAVAILABLE = "E_MODEL_UNAVAILABLE"    # 模型不可用且降级也失败
E_TIMEOUT = "E_TIMEOUT"                        # 调用超时
E_HUMAN_REQUIRED = "E_HUMAN_REQUIRED"          # 必须转人工，不得自动通过
E_CONFLICT_UNRESOLVED = "E_CONFLICT_UNRESOLVED"  # 存在未解决的口径或版本冲突
E_INTERNAL = "E_INTERNAL"                      # 未归类的内部错误
