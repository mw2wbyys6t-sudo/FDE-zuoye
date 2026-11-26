# -*- coding: utf-8 -*-
"""统一响应封装：所有对外接口只允许返回 {"ok","data","error"} 三键结构。"""

from typing import Any, Dict, Optional                    # 类型标注
from fastapi import FastAPI, Request                        # 注册全局异常处理器
from fastapi.exceptions import RequestValidationError       # 请求参数校验异常
from fastapi.responses import JSONResponse                  # 直接返回 JSON 响应
from starlette.exceptions import HTTPException as StarletteHTTPException   # 覆盖默认 HTTP 异常响应
from app import errors as E                                  # 错误码常量（统一定义在 app/errors.py）


def ok(data: Any = None) -> Dict[str, Any]:                 # 成功响应构造器
    """构造成功响应。

    入参：data 为任意可序列化对象，缺省为 None。
    出参：{"ok": True, "data": data, "error": None}。
    失败行为：不抛异常；序列化失败由 FastAPI 层抛出，属于编程错误。
    """
    return {"ok": True, "data": data, "error": None}         # 三键结构，缺一不可


def fail(code: str, msg: str, data: Any = None) -> Dict[str, Any]:   # 失败响应构造器
    """构造失败响应。

    入参：code 为错误码；msg 为中文说明；data 为可选的调试载荷。
    出参：{"ok": False, "data": data, "error": {"code","msg"}}。
    失败行为：不抛异常，调用方负责给出合适 HTTP 状态码。
    """
    return {"ok": False, "data": data, "error": {"code": code, "msg": msg}}   # 统一错误体


def register_handlers(app: FastAPI) -> None:                 # 注册全局异常处理
    """把各类异常统一转换为三键结构，避免出现裸 422/500 响应。

    入参：app 为 FastAPI 实例。
    出参：无。
    失败行为：注册过程本身不抛异常；处理器内部异常会退化为 E_INTERNAL。
    """
    @app.exception_handler(RequestValidationError)           # 处理参数校验失败
    async def _validation_handler(request: Request, exc: RequestValidationError):   # 参数错误统一成 schema 错误
        return JSONResponse(status_code=400, content=fail(E.E_SCHEMA, "请求参数不符合约定结构"))   # 400 + 错误码

    @app.exception_handler(StarletteHTTPException)            # 覆盖框架默认的 {"detail": ...}
    async def _http_handler(request: Request, exc: StarletteHTTPException):   # 把 403 等转成统一结构
        code = E.E_PERM if exc.status_code in (401, 403) else E.E_INTERNAL   # 权限类单独给 E_PERM
        return JSONResponse(status_code=exc.status_code, content=fail(code, str(exc.detail)))   # 保持原状态码

    @app.exception_handler(Exception)                          # 处理未捕获异常
    async def _unhandled_handler(request: Request, exc: Exception):   # 兜底，避免泄漏堆栈
        return JSONResponse(status_code=500, content=fail(E.E_INTERNAL, "服务内部错误"))   # 500 + 错误码
