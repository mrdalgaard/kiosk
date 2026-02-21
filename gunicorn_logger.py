from gunicorn.glogging import Logger

class IgnoreHealthCheckLogger(Logger):
    def access(self, resp, req, environ, request_time):
        # If the request path is /health, do nothing (skip logging)
        if req.path == '/health':
            return
        
        # Otherwise, run the standard Gunicorn logging logic
        super().access(resp, req, environ, request_time)
