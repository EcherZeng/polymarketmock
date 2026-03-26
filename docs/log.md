INFO:     127.0.0.1:63205 - "GET /api/backtest/replay/btc-updown-5m-1774505700/snapshot?t=2026-03-26T14:15:21%2B08:00 HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 328, in jsonable_encoder
    data = dict(obj)
TypeError: cannot convert dictionary update sequence element #0 to a sequence

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 333, in jsonable_encoder
    data = vars(obj)
TypeError: vars() argument must have __dict__ attribute

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\uvicorn\protocols\http\httptools_impl.py", line 416, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        self.scope, self.receive, self.send
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\uvicorn\middleware\proxy_headers.py", line 60, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\applications.py", line 1159, in __call__
    await super().__call__(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\applications.py", line 90, in __call__
    await self.middleware_stack(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\errors.py", line 186, in __call__
    raise exc
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\cors.py", line 88, in __call__
    await self.app(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\middleware\asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\routing.py", line 660, in __call__
    await self.middleware_stack(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\routing.py", line 680, in app
    await route.handle(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\routing.py", line 276, in handle
    await self.app(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 134, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 120, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 695, in app
    content = await serialize_response(
              ^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<11 lines>...
    )
    ^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 317, in serialize_response
    return jsonable_encoder(response_content)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 289, in jsonable_encoder
    encoded_value = jsonable_encoder(
        value,
    ...<4 lines>...
        sqlalchemy_safe=sqlalchemy_safe,
    )
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 336, in jsonable_encoder
    raise ValueError(errors) from e
ValueError: [TypeError('cannot convert dictionary update sequence element #0 to a sequence'), TypeError('vars() argument must have __dict__ attribute')]
INFO:     127.0.0.1:56887 - "GET /api/backtest/replay/btc-updown-5m-1774505700/snapshot?t=2026-03-26T14:15:21%2B08:00 HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 328, in jsonable_encoder
    data = dict(obj)
TypeError: cannot convert dictionary update sequence element #0 to a sequence

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 333, in jsonable_encoder
    data = vars(obj)
TypeError: vars() argument must have __dict__ attribute

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\uvicorn\protocols\http\httptools_impl.py", line 416, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        self.scope, self.receive, self.send
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\uvicorn\middleware\proxy_headers.py", line 60, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\applications.py", line 1159, in __call__
    await super().__call__(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\applications.py", line 90, in __call__
    await self.middleware_stack(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\errors.py", line 186, in __call__
    raise exc
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\cors.py", line 88, in __call__
    await self.app(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\middleware\asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\routing.py", line 660, in __call__
    await self.middleware_stack(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\routing.py", line 680, in app
    await route.handle(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\routing.py", line 276, in handle
    await self.app(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 134, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 120, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 695, in app
    content = await serialize_response(
              ^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<11 lines>...
    )
    ^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 317, in serialize_response
    return jsonable_encoder(response_content)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 289, in jsonable_encoder
    encoded_value = jsonable_encoder(
        value,
    ...<4 lines>...
        sqlalchemy_safe=sqlalchemy_safe,
    )
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 336, in jsonable_encoder
    raise ValueError(errors) from e
ValueError: [TypeError('cannot convert dictionary update sequence element #0 to a sequence'), TypeError('vars() argument must have __dict__ attribute')]
INFO:     127.0.0.1:54222 - "GET /api/backtest/replay/btc-updown-5m-1774505700/snapshot?t=2026-03-26T14:15:21%2B08:00 HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 328, in jsonable_encoder
    data = dict(obj)
TypeError: cannot convert dictionary update sequence element #0 to a sequence

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 333, in jsonable_encoder
    data = vars(obj)
TypeError: vars() argument must have __dict__ attribute

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\uvicorn\protocols\http\httptools_impl.py", line 416, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        self.scope, self.receive, self.send
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\uvicorn\middleware\proxy_headers.py", line 60, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\applications.py", line 1159, in __call__
    await super().__call__(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\applications.py", line 90, in __call__
    await self.middleware_stack(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\errors.py", line 186, in __call__
    raise exc
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\cors.py", line 88, in __call__
    await self.app(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\middleware\exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\middleware\asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\routing.py", line 660, in __call__
    await self.middleware_stack(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\routing.py", line 680, in app
    await route.handle(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\routing.py", line 276, in handle
    await self.app(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 134, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 120, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 695, in app
    content = await serialize_response(
              ^^^^^^^^^^^^^^^^^^^^^^^^^
    ...<11 lines>...
    )
    ^
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\routing.py", line 317, in serialize_response
    return jsonable_encoder(response_content)
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 289, in jsonable_encoder
    encoded_value = jsonable_encoder(
        value,
    ...<4 lines>...
        sqlalchemy_safe=sqlalchemy_safe,
    )
  File "c:\Users\v-yujieceng\Documents\Ls\poly\polymarketmock\.venv\Lib\site-packages\fastapi\encoders.py", line 336, in jsonable_encoder
    raise ValueError(errors) from e
ValueError: [TypeError('cannot convert dictionary update sequence element #0 to a sequence'), TypeError('vars() argument must have __dict__ attribute')]
