# -*- coding: utf-8 -*-
"""执行层服务：判定签发、处置闭环与指标统计（事件溯源，单文件 JSONL）。"""

import json                                                  # 事件序列化
import uuid                                                  # 编号生成
from datetime import datetime, timezone                       # 时间
from pathlib import Path                                     # 路径
from typing import Any, Dict, List, Optional                  # 类型标注
from app import errors as E                                   # 错误码
from app.execution.models import Decision, Disposition, DispositionIn, ScanContext   # 契约
from app.execution.rules import RULE_VERSION, evaluate         # 规则


class ExecutionError(Exception):                              # 业务异常
    def __init__(self, code: str, msg: str):                   # 初始化
        """构造执行层异常。

        入参：code 错误码；msg 说明。
        出参：无。
        失败行为：无。
        """
        super().__init__(msg)                                  # 基类
        self.code = code                                       # 错误码
        self.msg = msg                                         # 说明


class ExecutionService:                                       # 执行层服务
    def __init__(self, root: str = "var/exec", dedupe_minutes: int = 10,
                 overdue_minutes: int = 15):                   # 构造
        """初始化事件文件目录与两个现场阈值。

        入参：root 数据目录；dedupe_minutes 去重窗口分钟；overdue_minutes 挂起超时分钟。
        出参：无。
        失败行为：目录不可创建时抛 OSError。
        """
        self.root = Path(root)                                 # 数据目录
        self.root.mkdir(parents=True, exist_ok=True)            # 创建
        self.path = self.root / "events.jsonl"                  # 单一事件流
        self.dedupe_minutes = max(0, int(dedupe_minutes))       # 去重窗口，0 表示不去重
        self.overdue_minutes = max(0, int(overdue_minutes))     # 超时阈值，0 表示立即可判超时

    def _append(self, event: Dict[str, Any]) -> None:          # 追加事件
        """追加一条事件到事件流。

        入参：event 事件。
        出参：无。
        失败行为：磁盘错误时抛 OSError。
        """
        event.setdefault("at", datetime.now(timezone.utc).isoformat())   # 时间戳
        with self.path.open("a", encoding="utf-8") as fh:       # 追加写
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")   # 单行 JSON

    def events(self) -> List[Dict[str, Any]]:                   # 读取事件
        """读取全部事件。

        入参：无。
        出参：事件列表。
        失败行为：文件不存在时返回空列表。
        """
        if not self.path.exists():                             # 尚未产生事件
            return []                                          # 空
        return [json.loads(line) for line in
                self.path.read_text(encoding="utf-8").splitlines() if line.strip()]   # 逐行解析

    def decisions(self) -> List[Dict[str, Any]]:                # 判定列表
        """返回全部判定记录。

        入参：无。
        出参：判定列表（按时间顺序）。
        失败行为：不抛异常。
        """
        return [e["decision"] for e in self.events() if e.get("type") == "scan"]   # 过滤

    def _closed_ids(self) -> set:                              # 已闭环判定集合
        """返回已产生处置的判定编号。

        入参：无。
        出参：编号集合。
        失败行为：不抛异常。
        """
        return {e["disposition"]["decision_id"] for e in self.events() if e.get("type") == "disposition"}   # 集合

    def _recent_open(self, ctx: ScanContext) -> Optional[Dict[str, Any]]:   # 去重查找
        """查找窗口内同一业务同一 SKU 且尚未处置的判定。

        入参：ctx 扫码上下文。
        出参：判定字典或 None。
        失败行为：时间解析失败时视为不命中。
        """
        if self.dedupe_minutes <= 0:                           # 关闭去重
            return None                                       # 不使用
        closed = self._closed_ids()                            # 已处置
        now = datetime.now(timezone.utc)                       # 当前时间
        for event in reversed(self.events()):                  # 从新到旧
            if event.get("type") != "scan":                    # 只看判定
                continue                                      # 跳过
            ctx_old = event.get("ctx", {})                     # 旧上下文
            if ctx_old.get("biz_id") != ctx.biz_id or ctx_old.get("sku") != ctx.sku:   # 不同业务或 SKU
                continue                                      # 跳过
            try:                                              # 时间比较
                age_min = (now - datetime.fromisoformat(event["at"])).total_seconds() / 60   # 相差分钟
            except (KeyError, ValueError):                     # 缺时间或格式异常
                continue                                      # 视为不命中
            if age_min > self.dedupe_minutes:                  # 超出窗口
                break                                         # 不再往前找
            if event["decision"]["decision_id"] in closed:     # 已处置过
                return None                                   # 允许重新判定
            return event["decision"]                          # 命中可复用判定
        return None                                           # 未命中

    def scan(self, ctx: ScanContext, provenance: str = "synthetic") -> Decision:   # 扫码判定
        """执行一次判定并落事件；窗口内重复扫码复用结果。

        入参：ctx 扫码上下文；provenance 数据来源（real / synthetic）。
        出参：Decision（dedupe=True 表示复用）。
        失败行为：不抛异常。
        """
        previous = self._recent_open(ctx)                      # 去重查找
        if previous is not None:                               # 命中重复扫码
            # 原因：现场会连续扫同一行，重复弹卡会让人直接忽略提示，等于把拦截能力做废
            decision = Decision.model_validate(previous)        # 复用原判定
            decision.dedupe = True                             # 标记复用
            self._append({"type": "dedupe", "biz_id": ctx.biz_id,
                          "decision_id": decision.decision_id})   # 只记轻量事件，不计入判定数
            return decision                                    # 返回
        decision = evaluate(ctx)                               # 规则判定
        decision.decision_id = "dec-" + uuid.uuid4().hex[:10]   # 补编号
        self._append({"type": "scan", "biz_id": ctx.biz_id, "ctx": ctx.model_dump(),
                      "provenance": provenance,                # 标记来源，验收只统计 real
                      "decision": decision.model_dump()})       # 落事件
        return decision                                        # 返回

    def _line_keys(self) -> set:                                # 已导入行键
        """返回已存在的事件行键集合，用于批量去重。

        入参：无。
        出参：{(biz_id, line_id)} 集合。
        失败行为：不抛异常。
        """
        return {(e.get("biz_id"), e.get("line_id")) for e in self.events()
                if e.get("type") == "scan" and e.get("line_id")}   # 只统计带行号的导入记录

    def ingest(self, records: List[Any], provenance: str = "real",
               batch_id: str = "") -> Dict[str, int]:          # 批量导入
        """把历史记录批量写入事件流，按业务编号+行号去重。

        入参：records PickingRecord 列表；provenance 来源；batch_id 批次号。
        出参：{"imported": 写入数, "skipped": 跳过数}。
        失败行为：不抛异常；重复行跳过而不是覆盖。
        """
        existing = self._line_keys()                            # 已有行键
        batch = batch_id or datetime.now(timezone.utc).strftime("batch-%Y%m%d%H%M%S")   # 默认批次
        imported = 0                                            # 写入计数
        skipped = 0                                             # 跳过计数
        for record in records:                                  # 逐条
            key = (record.ctx.biz_id, record.line_id)            # 去重键
            # 原因：同一份导出常被重复上传，若不去重会把判定数放大，直接污染验收比例
            if key in existing:                                 # 已导入过
                skipped += 1                                    # 计数
                continue                                        # 跳过
            decision = evaluate(record.ctx)                     # 跑规则
            decision.decision_id = "dec-" + uuid.uuid4().hex[:10]   # 编号
            self._append({"type": "scan", "biz_id": record.ctx.biz_id,
                          "ctx": record.ctx.model_dump(), "provenance": provenance,
                          "line_id": record.line_id, "batch_id": batch,
                          "is_error": record.is_error,
                          "scanned_at": record.scanned_at,
                          "decision": decision.model_dump()})   # 落事件
            existing.add(key)                                   # 更新集合，防止同批次内重复行
            imported += 1                                       # 累加
        return {"imported": imported, "skipped": skipped}       # 返回计数

    def dispose(self, body: DispositionIn) -> Disposition:       # 处置
        """记录处置并判断是否闭环。

        入参：body 处置请求。
        出参：Disposition。
        失败行为：判定不存在抛 E_SCHEMA；挂起单缺三要素抛 E_HUMAN_REQUIRED。
        """
        target = next((d for d in self.decisions() if d["decision_id"] == body.decision_id), None)   # 找判定
        if target is None:                                     # 判定不存在
            raise ExecutionError(E.E_SCHEMA, "判定不存在：%s" % body.decision_id)   # 抛出
        if target.get("requires_human"):                       # 挂起单必须三要素齐全
            # 原因：挂起单不闭环就放行等于绕过审核，必须留下触发原因、接手人和确认时间
            if not body.operator or not body.reason or not body.confirmed_at:   # 三要素
                raise ExecutionError(E.E_HUMAN_REQUIRED,
                                     "挂起单必须提供 operator、reason、confirmed_at")   # 拒绝
        disposition = Disposition(disposition_id="dsp-" + uuid.uuid4().hex[:10],
                                  decision_id=body.decision_id, action=body.action,
                                  operator=body.operator, reason=body.reason,
                                  confirmed_at=body.confirmed_at, closed=True)   # 组装
        self._append({"type": "disposition", "disposition": disposition.model_dump(),
                      "note": body.note})                      # 落事件
        return disposition                                     # 返回

    def _age_minutes(self, stamp: str) -> float:               # 滞留分钟
        """把时间戳换算成距今分钟数。

        入参：stamp ISO 时间（可带 Z 或无时区）。
        出参：分钟数；无时区按 UTC 处理，无法解析返回 0。
        失败行为：不抛异常。
        """
        if not stamp:                                          # 空值
            return 0.0                                         # 视为刚发生
        try:                                                   # 解析
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))   # 兼容 Z
        except ValueError:                                     # 格式异常
            return 0.0                                         # 视为刚发生
        if parsed.tzinfo is None:                              # 导出常不带时区
            # 原因：历史导出多为本地时间且不带时区，统一按 UTC 解释，避免 naive/aware 直接相减报错
            parsed = parsed.replace(tzinfo=timezone.utc)        # 补时区
        return (datetime.now(timezone.utc) - parsed).total_seconds() / 60   # 分钟

    def metrics(self, provenance: Optional[str] = None) -> Dict[str, Any]:   # 指标
        """统计判定与处置情况，可按数据来源过滤。

        入参：provenance 为 None 表示全部，否则只统计该来源（验收只应看 real）。
        出参：计数、闭环率、未闭环与超时数、分规则命中与来源分布。
        失败行为：不抛异常。
        """
        events = self.events()                                 # 全量事件
        scans_all = [e for e in events if e.get("type") == "scan"]   # 全部判定事件
        sources: Dict[str, int] = {}                           # 来源分布
        for event in scans_all:                                # 逐条
            key = event.get("provenance", "unknown")           # 来源
            sources[key] = sources.get(key, 0) + 1             # 累加
        scans_events = [e for e in scans_all
                        if provenance is None or e.get("provenance") == provenance]   # 过滤
        scans = [e["decision"] for e in scans_events]           # 判定
        dispositions = [e["disposition"] for e in events if e.get("type") == "disposition"]   # 处置
        dedupes = [e for e in events if e.get("type") == "dedupe"]   # 重复扫码
        closed_ids = {d["decision_id"] for d in dispositions}   # 已处置判定
        holds = [d for d in scans if d["level"] == "hold"]       # 挂起
        hints = [d for d in scans if d["level"] == "hint"]       # 提示
        unresolved = [d for d in holds if d["decision_id"] not in closed_ids]   # 未闭环挂起
        overdue = 0                                             # 超时计数
        for item in unresolved:                                 # 逐条未闭环
            created = None                                      # 基准时间
            for e in events:                                    # 找对应事件
                if e.get("type") == "scan" and e["decision"]["decision_id"] == item["decision_id"]:   # 命中
                    # 原因：历史导入的扫描时间与导入时间可能差几天，超时必须按真实扫描时间算
                    created = e.get("scanned_at") or e.get("at")   # 优先用扫描时间
                    break                                       # 找到即止
            if created and self._age_minutes(created) >= self.overdue_minutes:   # 超过阈值
                overdue += 1                                    # 计数
        by_rule: Dict[str, int] = {}                            # 分规则计数
        for d in scans:                                        # 遍历判定
            for r in d["reasons"]:                             # 遍历理由
                by_rule[r["rule_id"]] = by_rule.get(r["rule_id"], 0) + 1   # 累加
        return {"scans": len(scans), "pass": sum(1 for d in scans if d["level"] == "pass"),
                "hints": len(hints), "holds": len(holds),
                "dispositions": len(dispositions), "unresolved_holds": len(unresolved),
                "overdue_holds": overdue, "dedupe_hits": len(dedupes),
                "closure_rate": round((len(holds) - len(unresolved)) / len(holds), 3) if holds else 1.0,
                "by_rule": by_rule, "rule_version": RULE_VERSION,
                "sources": sources}                            # 返回（含来源分布，便于隔离验收）
