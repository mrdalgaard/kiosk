import os
from gunicorn.glogging import Logger

class IgnoreHealthCheckLogger(Logger):
    def access(self, resp, req, environ, request_time):
        # 1. Global toggle for access logs via environment variable
        if os.environ.get('LOG_HTTP_ACCESS', 'True').lower() == 'false':
            return

        # 2. If the request path is /health, do nothing (skip logging)
        if req.path == '/health':
            return
        
        # Otherwise, run the standard Gunicorn logging logic
        super().access(resp, req, environ, request_time)
