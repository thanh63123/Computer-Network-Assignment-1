#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist
request settings (cookies, auth, proxies).
"""

import json
import base64
from .dictionary import CaseInsensitiveDict


class Request():
    """
    The fully mutable "class" `Request <Request>` object,
    containing the exact bytes that will be sent to the server.
    
    Instances are generated from a "class" `Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.
    
    Usage::
    
      >>> import deamon.request
      >>> req = request.Request()
      ## Incoming message obtain aka. incoming_msg
      >>> r = req.prepare(incoming_msg)
      >>> r
      <Request>
    """

    __attrs__ = [
        "method", "url", "headers", "body", "_raw_headers",
        "_raw_body", "reason", "cookies", "routes", "hook",
    ]

    def __init__(self):
        self.method = None
        self.url = None
        self.path = None
        self.version = None
        self.headers = CaseInsensitiveDict()
        self.cookies = {}
        self.auth = None
        self.body = None
        self._raw_headers = ""
        self._raw_body = ""
        self.routes = {}
        self.hook = None
        self.reason = None

    def fetch_headers_body(self, incoming_msg):
        """Prepares the given HTTP headers."""
        if "\r\n\r\n" in incoming_msg:
            parts = incoming_msg.split("\r\n\r\n", 1)
            return parts[0], parts[1]
        return incoming_msg, ""

    def extract_request_line(self, header_section):
        try:
            lines = header_section.splitlines()
            if not lines:
                return None, None, None

            first_line = lines[0]
            parts = first_line.split()

            method = parts[0].upper()
            path = parts[1]
            version = parts[2] if len(parts) > 2 else "HTTP/1.1"

            if path == '/':
                path = '/index.html'

            return method, path, version
        except Exception:
            return "GET", "/", "HTTP/1.1"

    def prepare_headers(self, header_section):
        """Prepares the given HTTP headers."""
        lines = header_section.split('\r\n')
        headers = CaseInsensitiveDict()
        for line in lines[1:]:
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key] = val
        return headers

    def prepare_cookies(self, cookie_header):
        cookies = {}
        if cookie_header:
            pairs = cookie_header.split(';')
            for pair in pairs:
                if '=' in pair:
                    key, val = pair.strip().split('=', 1)
                    cookies[key] = val
        self.cookies = cookies

    def prepare_auth(self, auth_header):
        if auth_header and auth_header.startswith('Basic '):
            try:
                encoded_str = auth_header.split(' ', 1)[1]
                decoded_str = base64.b64decode(encoded_str).decode('utf-8')
                if ':' in decoded_str:
                    user, password = decoded_str.split(':', 1)
                    self.auth = (user, password)
            except Exception:
                self.auth = None

    def prepare_body(self, raw_body):
        self._raw_body = raw_body
        content_type = self.headers.get('content-type', '')

        if 'application/json' in content_type:
            try:
                self.body = json.loads(raw_body)
            except Exception:
                self.body = raw_body
        else:
            self.body = raw_body

        self.headers["Content-Length"] = str(len(raw_body))

    def prepare_content_length(self, body):
        self.headers["Content-Length"] = str(len(body)) if body else "0"

    def prepare(self, incoming_msg, routes=None):
        """Prepares the entire request with the given parameters."""
        if not incoming_msg:
            return self

        print("[Request] Processing incoming message...")

        self._raw_headers, self._raw_body = self.fetch_headers_body(incoming_msg)
        self.method, self.path, self.version = self.extract_request_line(self._raw_headers)
        self.url = self.path

        self.headers = self.prepare_headers(self._raw_headers)

        self.prepare_cookies(self.headers.get('cookie', ''))
        self.prepare_auth(self.headers.get('authorization', ''))

        self.prepare_body(self._raw_body)

        if routes:
            self.routes = routes
            self.hook = routes.get((self.method, self.path))
            if not self.hook:
                self.hook = routes.get(self.path)

        print("[Request] Completed: {} {}".format(self.method, self.path))
        return self

    def __repr__(self):
        return "<Request [{}]>".format(self.method or "INVALID")
