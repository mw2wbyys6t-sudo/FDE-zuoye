# -*- coding: utf-8 -*-
"""角色鉴权：按请求头声明的角色做白名单校验，真实身份由网关注入。"""

from typing import Dict, Any, List                        # 类型标注
from fastapi import Header, HTTPException                 # 依赖注入与异常


def make_role_dependency(config: Dict[str, Any]):          # 生成带配置的角色依赖
    """根据配置构造 FastAPI 依赖，校验 X-Role 请求头。

    入参：config 为已加载的配置字典。
    出参：一个可注入的依赖函数，返回角色字符串。
    失败行为：角色缺失或不在白名单时抛 HTTPException(403)，由全局处理器转成三键结构。
    """
    allowed: List[str] = config.get("app", {}).get("allowed_roles", [])   # 读取角色白名单

    def _dep(x_role: str = Header(default="", alias="X-Role")) -> str:   # 从请求头取角色
        """校验请求头中的角色。

        入参：x_role 为请求头 X-Role，缺省空串。
        出参：合法角色字符串。
        失败行为：为空或不合法时抛 403；这一层必须卡住，否则下游权限判断全部失效。
        """
        # 原因：角色是后续所有可见性过滤的前提，请求头缺失时必须直接拒绝，不能默认放行
        if not x_role:                                     # 未声明角色
            raise HTTPException(status_code=403, detail="缺少 X-Role 请求头")   # 直接拒绝
        # 原因：白名单来自配置而非代码，避免测试角色在生产环境被误用
        if x_role not in allowed:                          # 角色不在白名单
            raise HTTPException(status_code=403, detail="角色未授权")   # 直接拒绝
        return x_role                                      # 通过校验，返回角色
    return _dep                                           # 返回可注入依赖
