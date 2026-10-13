"""Local-only image transport. This ROS process never reads credentials."""

import json
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from .core import ModelUnavailable, SchemaError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalInference:
    def __init__(self, url, timeout):
        parsed = urlparse(url)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ('', '/')):
            raise ValueError('Inference URL must be local loopback HTTP')
        if timeout <= 0 or timeout > 120:
            raise ValueError('Request timeout must be in (0, 120] seconds')
        self.url, self.timeout = url.rstrip('/'), timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def infer(self, png):
        request = Request(self.url+'/infer', data=png,
                          headers={'Content-Type': 'image/png'}, method='POST')
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise SchemaError('Response exceeds limit')
            return json.loads(data)
        except SchemaError:
            raise
        except HTTPError as error:
            if error.code == 422:
                raise SchemaError('Inference schema rejected') from None
            raise ModelUnavailable('Local inference unavailable') from None
        except (ValueError, UnicodeError):
            raise SchemaError('Malformed JSON response') from None
        except Exception:
            # Never log a response body, request or exception supplied by a server.
            raise ModelUnavailable('Local inference unavailable') from None
