from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

from app.auth.dependencies import require_csrf


class AuthSafetyMiddleware:
    """Bound auth bodies before parsing; protect mutations and prohibit auth caching."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        sensitive = scope['path'].startswith(('/api/v1/auth/', '/api/v1/applications', '/api/v1/admin/', '/api/v1/installment-')) or scope['path'] == '/api/v1/me'
        if not sensitive:
            return await self.app(scope, receive, send)

        async def secure_send(message):
            if message['type'] == 'http.response.start':
                headers = [(k, v) for k, v in message['headers'] if k.lower() != b'cache-control']
                headers += [(b'cache-control', b'no-store'), (b'pragma', b'no-cache'),
                            (b'x-content-type-options', b'nosniff'), (b'referrer-policy', b'no-referrer')]
                message = {**message, 'headers': headers}
            await send(message)

        if scope['method'] not in ('GET', 'HEAD', 'OPTIONS'):
            try:
                require_csrf(Request(scope))
            except HTTPException as error:
                return await JSONResponse({'detail': error.detail}, status_code=error.status_code)(scope, receive, secure_send)
            body = bytearray()
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                body.extend(message.get('body', b''))
                limit = 1048576 if scope['path'] == '/api/v1/installment-history/imports' else 16384
                if len(body) > limit:
                    return await JSONResponse({'detail': 'Request body too large'}, status_code=413)(scope, receive, secure_send)
                if not message.get('more_body', False):
                    break
            delivered = False

            async def buffered_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
                return await receive()
            return await self.app(scope, buffered_receive, secure_send)
        return await self.app(scope, receive, secure_send)

