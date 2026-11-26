# -*- coding: utf-8 -*-
"""接入与回放测试：格式校验、标注比对、来源隔离。"""

import shutil                                                # 复制样例
from pathlib import Path                                     # 路径
import pytest                                                # 断言
from app.execution.importer import ImportError_, load_csv      # 导入
from app.execution.replay import replay                        # 回放
from app.execution.service import ExecutionService             # 服务

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample" / "picking_sample.csv"   # 样例


def test_load_sample():                                       # 读取
    """验证样例可解析且标注数量正确。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    records = load_csv(str(SAMPLE), provenance="synthetic")    # 读取
    assert len(records) == 12                                  # 条数
    assert sum(1 for r in records if r.is_error) == 5           # 5 条真错发
    assert records[0].ctx.neighbor_specs == []                  # 空邻位
    assert records[1].ctx.neighbor_specs == ["750ml"]            # 邻位解析


def test_missing_column(tmp_path: Path):                       # 缺列
    """验证缺必需列时明确报错。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    bad = tmp_path / "bad.csv"                                  # 临时文件
    bad.write_text("biz_id,line_id\nwv-1,L1\n", encoding="utf-8")   # 缺列
    with pytest.raises(ImportError_) as info:                    # 期望异常
        load_csv(str(bad))                                      # 读取
    assert "缺少必需列" in str(info.value)                       # 报错信息


def test_replay_metrics():                                     # 回放指标
    """验证样例上的精确率与召回率符合预期。

    入参：无。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    report = replay(load_csv(str(SAMPLE), provenance="synthetic"))   # 回放
    assert report["labeled"] is True                             # 有标注
    assert report["confusion"] == {"tp": 4, "fp": 4, "fn": 1, "tn": 3}   # 混淆矩阵
    assert report["precision"] == 0.5 and report["recall"] == 0.8      # 指标
    assert report["by_rule"]["R1"] >= 1 and report["by_rule"]["R2"] >= 1   # 分规则


def test_ingest_marks_provenance(tmp_path: Path):               # 来源隔离
    """验证导入后可按来源过滤，合成数据不进入真实验收统计。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    svc = ExecutionService(str(tmp_path / "exec"), dedupe_minutes=0)   # 关闭去重，避免导入被合并
    records = load_csv(str(SAMPLE), provenance="synthetic")        # 读取
    result = svc.ingest(records, provenance="synthetic")            # 导入
    assert result == {"imported": 12, "skipped": 0}                # 全部写入
    assert svc.metrics("synthetic")["scans"] == 12                 # 合成来源
    assert svc.metrics("real")["scans"] == 0                       # 真实来源为空
    assert svc.metrics()["sources"] == {"synthetic": 12}           # 来源分布


def test_ingest_dedupes_same_file(tmp_path: Path):                # 重复导入
    """验证同一文件二次导入全部跳过，不放大判定数。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    svc = ExecutionService(str(tmp_path / "exec"), dedupe_minutes=0)   # 服务
    records = load_csv(str(SAMPLE), provenance="synthetic")         # 读取
    svc.ingest(records, provenance="synthetic", batch_id="b1")        # 首次
    again = svc.ingest(records, provenance="synthetic", batch_id="b2")   # 二次
    assert again == {"imported": 0, "skipped": 12}                  # 全部跳过
    assert svc.metrics("synthetic")["scans"] == 12                  # 判定数未变


def test_overdue_uses_scanned_at(tmp_path: Path):                  # 超时按扫描时间
    """验证历史导入按 scanned_at 计超时，而不是导入时刻。

    入参：tmp_path 临时目录。
    出参：无。
    失败行为：断言失败即测试失败。
    """
    csv_path = tmp_path / "history.csv"                            # 临时文件
    header = ("biz_id,line_id,sku,base_sku,spec,cancelled,scanned_at,is_error\n"   # 表头
              "wv-901,L1,SKU-X,SKU-X,1L,1,2026-11-01T09:00,1\n"                     # 一周前
              "wv-902,L1,SKU-Y,SKU-Y,1L,1,2099-01-01T09:00,1\n")                    # 未来
    csv_path.write_text(header, encoding="utf-8")                  # 写入
    svc = ExecutionService(str(tmp_path / "exec"), dedupe_minutes=0, overdue_minutes=15)   # 服务
    svc.ingest(load_csv(str(csv_path)), provenance="real")          # 导入
    stats = svc.metrics("real")                                    # 指标
    assert stats["unresolved_holds"] == 2                          # 两条挂起
    assert stats["overdue_holds"] == 1                             # 只有一周前那条超时
