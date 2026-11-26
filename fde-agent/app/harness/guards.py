# -*- coding: utf-8 -*-
"""闸门：证据、边界、权限三类硬校验。任何一条不通过都不允许继续。"""

import re                                                   # 事实编号格式校验
from typing import Any, Dict, Iterable, Optional            # 类型标注
from app import errors as E                                  # 错误码（harness 不依赖 api 层）


class GuardError(Exception):                                # 闸门专用异常
    def __init__(self, code: str, msg: str):                 # 初始化
        """构造闸门异常。

        入参：code 为错误码；msg 为中文说明。
        出参：无。
        失败行为：无。
        """
        super().__init__(msg)                               # 交给基类保存消息
        self.code = code                                    # 保存错误码供上层转换
        self.msg = msg                                      # 保存说明


def check_evidence(claims: Iterable[Dict[str, Any]], known_ids: Optional[set] = None,
                   pattern: str = r"^f[0-9]{2}$") -> None:   # 证据闸门
    """校验每条结论都带合法且存在的事实编号。

    入参：claims 结论列表；known_ids 已知事实编号集合（传 None 表示只校验格式）；pattern 编号正则。
    出参：无。
    失败行为：任一条缺失或不合法时抛 GuardError(E_NO_EVIDENCE)。
    """
    # 原因：没有事实编号的结论无法回溯，验收时无法解释，必须当场拒答而不是留到人工兜底
    for index, claim in enumerate(claims):                   # 逐条检查
        fact_id = str(claim.get("fact_id") or "").strip()    # 取编号并去空格
        if not fact_id:                                      # 完全缺失
            raise GuardError(E.E_NO_EVIDENCE, "第 %d 条结论缺少事实编号" % (index + 1))   # 立即拦截
        if not re.match(pattern, fact_id):                   # 格式不合法
            raise GuardError(E.E_NO_EVIDENCE, "第 %d 条事实编号格式不合法" % (index + 1))   # 立即拦截
        if known_ids is not None and fact_id not in known_ids:   # 编号存在性校验
            raise GuardError(E.E_NO_EVIDENCE, "事实编号 %s 不存在于台账" % fact_id)   # 编造编号同样拦截


def check_boundary(action: Optional[str], payload: Optional[Dict[str, Any]] = None) -> None:   # 边界闸门
    """拦截写业务库、自动审批、自动操作设备三类越界行为。

    入参：action 为拟执行动作名；payload 为动作载荷。
    出参：无。
    失败行为：命中禁止清单时抛 GuardError(E_BOUNDARY)。
    """
    forbidden = {"write_db", "update_inventory", "auto_approve", "operate_forklift"}   # 明确禁止的动作
    # 原因：本项目边界是"只提示不阻断、只读不写库"，这几类动作一旦执行就无法回滚
    if action and action in forbidden:                       # 动作命中禁止清单
        raise GuardError(E.E_BOUNDARY, "动作 %s 超出提示边界，必须拒绝" % action)   # 立即拒绝
    if payload:                                              # 载荷也要扫一遍
        text = str(payload)                                  # 粗粒度转字符串，覆盖嵌套字段
        # 原因：自动审批属于责任转移，必须留给人签核，文字里出现相关意图也要拦
        if any(word in text for word in ("自动审批", "自动放行", "代签")):   # 命中敏感意图
            raise GuardError(E.E_BOUNDARY, "检测到自动审批意图，必须转人工")   # 立即拒绝


def check_permission(role: str, allowed_roles: Iterable[str], require_write: bool = False,
                     write_roles: Iterable[str] = ()) -> None:   # 权限闸门
    """校验角色是否具备访问或写操作权限。

    入参：role 当前角色；allowed_roles 可读角色；require_write 是否需要写权限；write_roles 可写角色。
    出参：无。
    失败行为：无权限时抛 GuardError(E_PERM)。
    """
    # 原因：可见性必须在服务端判断，不能靠前端隐藏，否则绕过页面即可读全量
    if role not in set(allowed_roles):                       # 可读校验
        raise GuardError(E.E_PERM, "角色 %s 无读取权限" % role)   # 拒绝
    # 原因：写权限单独判定，避免只读角色通过接口参数升级为写操作
    if require_write and role not in set(write_roles):       # 写校验
        raise GuardError(E.E_PERM, "角色 %s 无写权限" % role)   # 拒绝
