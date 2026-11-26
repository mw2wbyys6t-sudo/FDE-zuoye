# 样例数据说明

`picking_sample.csv` 是**合成样例**，不是任何客户的真实数据。

- 用途：演示接入格式与回放评估，不用于得出业务结论。
- 标注列 `is_error`：0/1，由人工标注是否真的发生错发。
- 字段含义见 `app/execution/importer.py`；`neighbor_specs` 用 `|` 或逗号分隔。
- 导入时必须传 `provenance=synthetic`，验收统计只允许看 `provenance=real`。
- 本样例的规则表现为：精确率 0.5、召回率 0.8 —— 说明单靠当前规则误报偏高，这正是需要真实数据才能判断的地方。
