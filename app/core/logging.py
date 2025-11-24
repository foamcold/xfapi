import logging
from urllib.parse import unquote
import uvicorn.logging

class DecodedAccessFormatter(uvicorn.logging.AccessFormatter):
    def format(self, record):
        # The args are usually: (client_addr, method, full_path, http_version, status_code)
        # We want to unquote the full_path (index 2)
        if record.args and len(record.args) >= 3:
            args = list(record.args)
            # Check if args[2] looks like a path/url
            if isinstance(args[2], str):
                args[2] = unquote(args[2])
            record.args = tuple(args)
        return super().format(record)
