TypeError: unhashable type: 'list'
INFO:     172.18.0.6:49142 - "PUT /presets/Test01 HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "/opt/venv/lib/python3.11/site-packages/uvicorn/protocols/http/h11_impl.py", line 415, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/venv/lib/python3.11/site-packages/uvicorn/middleware/proxy_headers.py", line 60, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/venv/lib/python3.11/site-packages/fastapi/applications.py", line 1163, in __call__
    await super().__call__(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/applications.py", line 90, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/middleware/errors.py", line 186, in __call__
    raise exc
  File "/opt/venv/lib/python3.11/site-packages/starlette/middleware/errors.py", line 164, in __call__
    await self.app(scope, receive, _send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/middleware/gzip.py", line 29, in __call__
    await responder(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/middleware/gzip.py", line 130, in __call__
    await super().__call__(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/middleware/gzip.py", line 46, in __call__
    await self.app(scope, receive, self.send_with_compression)
  File "/opt/venv/lib/python3.11/site-packages/starlette/middleware/cors.py", line 96, in __call__
    await self.simple_response(scope, receive, send, request_headers=headers)
  File "/opt/venv/lib/python3.11/site-packages/starlette/middleware/cors.py", line 154, in simple_response
    await self.app(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/middleware/exceptions.py", line 63, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/opt/venv/lib/python3.11/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/opt/venv/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py", line 18, in __call__
    await self.app(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/routing.py", line 660, in __call__
    await self.middleware_stack(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/routing.py", line 680, in app
    await route.handle(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/routing.py", line 276, in handle
    await self.app(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/fastapi/routing.py", line 134, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "/opt/venv/lib/python3.11/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "/opt/venv/lib/python3.11/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "/opt/venv/lib/python3.11/site-packages/fastapi/routing.py", line 120, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "/opt/venv/lib/python3.11/site-packages/fastapi/routing.py", line 674, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/venv/lib/python3.11/site-packages/fastapi/routing.py", line 328, in run_endpoint_function
    return await dependant.call(**values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/api/presets.py", line 40, in save_preset
    registry.save_preset(name, preset_data)
  File "/app/core/registry.py", line 201, in save_preset
    params = self.normalize_config(params)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/core/registry.py", line 147, in normalize_config
    if not result.get(toggle_key):
           ^^^^^^^^^^^^^^^^^^^^^^
TypeError: unhashable type: 'list