# -*- coding: utf-8 -*-
"""数据接入契约：把现场导出文件变成可回放的记录，缺失字段直接报错。"""

import csv                                                   # 读取 CSV
from pathlib import Path                                     # 路径
from typing import List, Optional                             # 类型标注
from pydantic import BaseModel, ConfigDict, Field              # 契约
from app import errors as E                                   # 错误码
from app.execution.models import ScanContext                   # 复用扫码上下文


class ImportError_(Exception):                               # 导入异常
    def __init__(self, code: str, msg: str):                   # 初始化
        """构造导入异常。

        入参：code 错误码；msg 说明。
        出参：无。
        失败行为：无。
        """
        super().__init__(msg)                                  # 基类
        self.code = code                                       # 错误码


class PickingRecord(BaseModel):                              # 一行记录
    model_config = ConfigDict(extra="forbid")                 # 禁止多余字段
    line_id: str = Field(min_length=1, max_length=40)         # 行号，去重与追溯用
    ctx: ScanContext                                         # 判定上下文
    scanned_at: str = Field(default="", max_length=40)        # 扫描时间
    is_error: Optional[bool] = None                          # 人工标注：是否真的错发
    provenance: str = Field(default="real", max_length=20)     # real / synthetic
    note: str = Field(default="", max_length=200)              # 来源说明


REQUIRED = ("biz_id", "line_id", "sku", "base_sku", "spec")   # 必需列
TRUTHY = ("1", "true", "yes", "y", "是")                      # 真值写法


def _bool(value: str, default: bool = False) -> bool:         # 解析布尔
    """把导出文件里的布尔写法统一成 bool。

    入参：value 原始文本；default 缺省值。
    出参：布尔值。
    失败行为：空值时返回 default。
    """
    if value is None or value == "":                           # 空值
        return default                                        # 用缺省
    return value.strip().lower() in TRUTHY                     # 统一判断


def _neighbors(value: str) -> List[str]:                      # 解析邻位规格
    """把分隔字符串拆成规格列表。

    入参：value 形如 500ml|750ml。
    出参：列表。
    失败行为：空值返回空列表。
    """
    if not value:                                             # 空
        return []                                             # 空列表
    return [item.strip() for item in value.replace("|", ",").split(",") if item.strip()]   # 拆分


def load_csv(path: str, provenance: str = "real") -> List[PickingRecord]:   # 读取
    """读取导出文件并校验必需列。

    入参：path 文件路径；provenance 数据来源标记。
    出参：记录列表。
    失败行为：缺列或行缺字段时抛 ImportError_（E_SCHEMA），不静默跳过。
    """
    file_path = Path(path)                                    # 路径对象
    if not file_path.exists():                                # 文件不存在
        raise ImportError_(E.E_SCHEMA, "文件不存在：%s" % path)   # 抛出
    with file_path.open("r", encoding="utf-8-sig", newline="") as fh:   # 兼容 BOM
        reader = csv.DictReader(fh)                           # 按表头读
        headers = reader.fieldnames or []                     # 表头
        missing = [col for col in REQUIRED if col not in headers]   # 缺列
        if missing:                                           # 缺必需列
            raise ImportError_(E.E_SCHEMA, "缺少必需列：%s" % ",".join(missing))   # 抛出
        records: List[PickingRecord] = []                     # 结果
        for index, row in enumerate(reader, start=2):          # 从第 2 行开始
            if not row.get("biz_id"):                          # 空行
                continue                                      # 跳过
            for col in REQUIRED:                               # 逐列校验
                if not (row.get(col) or "").strip():           # 缺值
                    raise ImportError_(E.E_SCHEMA, "第 %d 行缺少 %s" % (index, col))   # 抛出
            label_raw = (row.get("is_error") or "").strip()    # 标注
            record = PickingRecord(                            # 组装
                line_id=row["line_id"].strip(),                # 行号
                ctx=ScanContext(                               # 上下文
                    biz_id=row["biz_id"].strip(), sku=row["sku"].strip(),
                    base_sku=row["base_sku"].strip(), spec=row["spec"].strip(),
                    neighbor_specs=_neighbors(row.get("neighbor_specs", "")),
                    cancelled=_bool(row.get("cancelled")),
                    cancel_seen_ago_min=int(row["cancel_seen_ago_min"])
                    if (row.get("cancel_seen_ago_min") or "").strip().isdigit() else None,
                    note_text=(row.get("note_text") or "").strip(),
                    note_attached=_bool(row.get("note_attached"), default=True),
                    system_available=_bool(row.get("system_available"), default=True),
                    data_asof=(row.get("data_asof") or "").strip()),
                scanned_at=(row.get("scanned_at") or "").strip(),
                is_error=(label_raw.lower() in TRUTHY) if label_raw else None,   # 无标注则空
                provenance=provenance, note=(row.get("note") or "").strip())   # 来源
            records.append(record)                             # 收集
    return records                                             # 返回
