# -*- coding: utf-8 -*-
"""配置加载模块：唯一配置入口，禁止在业务代码中硬编码地址与密钥。"""

import os                                            # 读取环境变量做占位符替换
import re                                            # 匹配 ${VAR} 形式的占位符
from pathlib import Path                             # 跨平台路径处理
from typing import Any, Dict                         # 类型标注
import yaml                                          # 解析 YAML 配置

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")      # 只允许大写环境变量名，避免误替换


def _expand(value: Any) -> Any:                       # 递归展开配置中的环境变量占位符
    """把配置值里的 ${VAR} 替换为环境变量值。

    入参：value 为任意配置节点（str / dict / list）。
    出参：替换后的同结构对象；环境变量不存在时替换为空字符串。
    失败行为：不抛异常，缺失变量以空字符串呈现，由调用方决定是否降级。
    """
    if isinstance(value, str):                        # 字符串才需要替换
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)  # 缺失时给空串
    if isinstance(value, dict):                       # 字典逐值递归
        return {k: _expand(v) for k, v in value.items()}  # 保持键不变
    if isinstance(value, list):                       # 列表逐项递归
        return [_expand(v) for v in value]            # 保持顺序
    return value                                      # 其它类型原样返回


def load_config(path: str = "config.yaml") -> Dict[str, Any]:   # 读取配置文件
    """加载并展开配置文件。

    入参：path 为配置文件路径，默认项目根目录下的 config.yaml。
    出参：展开后的配置字典。
    失败行为：文件不存在或 YAML 语法错误时抛异常，让启动阶段直接失败而不是带病运行。
    """
    raw_text = Path(path).read_text(encoding="utf-8")            # 以 UTF-8 读取，避免中文注释乱码
    data = yaml.safe_load(raw_text) or {}                        # 解析为字典，空文件给空字典
    return _expand(data)                                         # 返回展开后的配置


def get(config: Dict[str, Any], dotted: str, default: Any = None) -> Any:   # 点号取值工具
    """按 a.b.c 形式读取嵌套配置。

    入参：config 配置字典；dotted 形如 "model.timeout_s"；default 为缺省值。
    出参：命中的值，未命中返回 default。
    失败行为：中间节点不存在时返回 default，不抛异常。
    """
    node: Any = config                                # 从根节点开始
    for key in dotted.split("."):                     # 逐级下钻
        if not isinstance(node, dict) or key not in node:   # 任一环节缺失即返回缺省
            return default                            # 返回缺省值
        node = node[key]                              # 下钻一层
    return node                                       # 返回最终值
