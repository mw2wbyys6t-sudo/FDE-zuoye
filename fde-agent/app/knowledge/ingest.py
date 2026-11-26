# -*- coding: utf-8 -*-
"""入库解析：把事实台账按"事实条目"切分，绝不按段落切，保证编号完整。"""

import re                                                  # 解析行格式
from pathlib import Path                                   # 读取文件
from typing import List                                    # 列表类型
from app.domain.models import Confidence, Dimension, Fact   # 领域模型

LINE_PATTERN = re.compile(r"^- \[logistics-warehouse-(f\d{2})\]\s*([^：:]{1,20})[：:](.+)$")   # 台账行格式
META_PATTERN = re.compile(r"[（(]([^（）()]+?)\s*·\s*([^（）()]+?)[）)]\s*$")                  # 行尾来源元信息

RULE_WORDS = ("红线", "审批", "权限", "账号", "规程", "签核", "留存", "归档", "授权",
              "禁止", "不得", "必须", "转人工", "借用")      # 规则维关键词
CASE_WORDS = ("取消订单", "事件", "案例", "错例", "到货才发现", "拿错规格", "异常")   # 案例维关键词
INDICATOR_WORDS = ("率", "分钟", "人时", "拣选行", "基线", "统计口径", "分母", "周期", "目标")   # 指标维关键词


def classify_dimension(statement: str) -> Dimension:        # 维度判定
    """按关键词把陈述归入四维之一。

    入参：statement 为陈述正文。
    出参：Dimension 枚举。
    失败行为：都不命中时归为事实维，保证不丢数据。
    """
    # 原因：规则优先级最高，因为红线与权限类内容一旦误归为普通事实，检索时会被普通角色读到
    if any(word in statement for word in RULE_WORDS):        # 命中规则词
        return Dimension.RULE                                # 归为规则
    if any(word in statement for word in CASE_WORDS):        # 命中案例词
        return Dimension.CASE                                # 归为案例
    if any(word in statement for word in INDICATOR_WORDS):   # 命中指标词
        return Dimension.INDICATOR                           # 归为指标
    return Dimension.FACT                                    # 默认事实


def infer_confidence(statement: str) -> Confidence:          # 证据等级判定
    """按措辞推断证据等级。

    入参：statement 为陈述正文。
    出参：Confidence 枚举。
    失败行为：无法判断时给事实级，但下游闸门仍要求编号，避免把猜测当结论。
    """
    if any(word in statement for word in ("尚未核实", "待确认", "待定", "未测", "未采集")):   # 明确未核实
        return Confidence.TBD                                # 待定级
    if any(word in statement for word in ("推算", "折算", "量级")):   # 推算措辞
        return Confidence.EXTRAPOLATION                      # 推算级
    if any(word in statement for word in ("约", "估计", "左右", "预计", "大概")):   # 估计措辞
        return Confidence.ESTIMATE                           # 估计级
    return Confidence.FACT                                   # 默认事实级


def visible_roles(dimension: Dimension) -> List[str]:        # 可见角色
    """按维度给出默认可见角色。

    入参：dimension 维度。
    出参：角色列表。
    失败行为：不抛异常。
    """
    # 原因：规则维包含红线与签核信息，默认只给安全、管理员与技术角色，避免一线越权读到审批细节
    if dimension == Dimension.RULE:                          # 规则维收紧
        return ["safety", "admin", "engineer"]               # 仅三类角色
    return ["viewer", "operator", "engineer", "safety", "admin"]   # 其余维全角色可见


def parse_ledger(text: str, source: str = "discovery-report.md") -> List[Fact]:   # 解析台账
    """解析事实台账文本为 Fact 列表。

    入参：text 为 Markdown 全文；source 为来源文件名。
    出参：Fact 列表，按编号去重（后者覆盖前者）。
    失败行为：不抛异常；无法识别的行直接跳过，避免因一行格式差异中断整批入库。
    """
    table = {}                                               # 以编号为键去重
    for raw in text.splitlines():                            # 逐行扫描
        match = LINE_PATTERN.match(raw.strip())              # 匹配台账行
        if not match:                                        # 非台账行
            continue                                         # 跳过
        fact_id, role, body = match.group(1), match.group(2).strip(), match.group(3).strip()   # 拆字段
        source_type = ""                                     # 来源类型默认空
        meta = META_PATTERN.search(body)                     # 匹配行尾元信息
        if meta:                                             # 命中元信息
            source_type = meta.group(2).strip()              # 取来源类型
            body = body[: meta.start()].strip()              # 从正文去掉元信息
        dimension = classify_dimension(body)                 # 维度判定
        table[fact_id] = Fact(fact_id=fact_id, role=role, statement=body, source=source,
                              source_type=source_type, dimension=dimension,
                              confidence=infer_confidence(body), version="v1",
                              roles_visible=visible_roles(dimension))   # 组装模型
    return [table[key] for key in sorted(table)]             # 按编号排序返回，保证可复现


def parse_ledger_file(path: str) -> List[Fact]:              # 文件入口
    """读取文件并解析台账。

    入参：path 为文件路径。
    出参：Fact 列表。
    失败行为：文件不存在时抛异常，避免静默得到空库。
    """
    text = Path(path).read_text(encoding="utf-8")            # 以 UTF-8 读取
    return parse_ledger(text, source=Path(path).name)        # 复用解析逻辑
