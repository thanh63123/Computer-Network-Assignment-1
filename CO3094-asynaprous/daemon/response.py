#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a :class: `Response <Response>` object to manage and persist
response settings (cookies, auth, proxies), and to construct HTTP responses
based on incoming requests.

The current version supports MIME type detection, content loading and header formatting
"""
import datetime
import os
import json
import mimetypes
from .dictionary import CaseInsensitiveDict

BASE_DIR = ""


class Response():
    """
    The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.
    
    Instances are generated from a :class:`Request <Request>` object, and
    should not be instantiated manually; doing so may produce undesirable
    effects.
    
    :class:`Response <Response>` object encapsulates headers, content,
    status code, cookies, and metadata related to the request-response cycle.
    It is used to construct and serve HTTP responses in a custom web server.
    
    :attrs status_code (int): HTTP status code (e.g., 200, 404).
    :attrs headers (dict): dictionary of response headers.
    :attrs url (str): url of the response.
    :attrsencoding (str): encoding used for decoding response content.
    :attrs history (list): list of previous Response objects (for redirects).
    :attrs reason (str): textual reason for the status code (e.g., "OK", "Not Found").
    :attrs cookies (CaseInsensitiveDict): response cookies.
    :attrs elapsed (datetime.timedelta): time taken to complete the request.
    :attrs request (PreparedRequest): the original request object.
    
    Usage::
    
      >>> import Response
      >>> resp = Response()
      >>> resp.build_response(req)
      >>> resp
      <Response>
    """

    __attrs__ = [
        "_content", "_header", "status_code", "method", "headers",
        "url", "history", "encoding", "reason", "cookies",
        "elapsed", "request", "body",
    ]

    def __init__(self, request=None):
        self._content = b""
        self._header = b""
        self._content_consumed = False
        self._next = None
        self.status_code = 200
        self.reason = "OK"
        self.headers = {}
        self.url = None
        self.encoding = "utf-8"
        self.history = []
        self.cookies = CaseInsensitiveDict()
        self.elapsed = datetime.timedelta(0)
        self.request = request
        self.body = None

    def get_mime_type(self, path):
        """
        Determines the MIME type of a file based on its path.
        
        "params path (str): Path to the file.
        
        :rtype str: MIME type string (e.g., 'text/html', 'image/png').
        """
        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return 'application/octet-stream'
        return mime_type or 'application/octet-stream'

    def prepare_content_type(self, mime_type='text/html'):
        """
        Prepares the Content-Type header and determines the base directory
        for serving the file based on its MIME type.
        
        :params mime_type (str): MIME type of the requested resource.
        
        :rtype str: Base directory path for locating the resource.
        
        :raises ValueError: If the MIME type is unsupported.
        """
        main_type, sub_type = mime_type.split('/', 1)
        base_dir = ""

        if main_type == 'text':
            self.headers['Content-Type'] = 'text/{}; charset={}'.format(sub_type, self.encoding)
            if sub_type in ['plain', 'css', 'javascript']:
                base_dir = os.path.join(BASE_DIR, "static/")
            elif sub_type == 'html':
                base_dir = os.path.join(BASE_DIR, "www/")
            else:
                base_dir = os.path.join(BASE_DIR, "static/")
        elif main_type == 'image':
            self.headers['Content-Type'] = 'image/{}'.format(sub_type)
            base_dir = os.path.join(BASE_DIR, "static/")
        elif main_type == 'application':
            if sub_type == 'javascript':
                self.headers['Content-Type'] = 'application/javascript; charset={}'.format(self.encoding)
                base_dir = os.path.join(BASE_DIR, "static/")
            else:
                self.headers['Content-Type'] = mime_type
                base_dir = os.path.join(BASE_DIR, "static/")
        else:
            self.headers['Content-Type'] = mime_type
            base_dir = os.path.join(BASE_DIR, "static/")

        return base_dir

    def build_content(self, path, base_dir):
        """
        Loads the objects file from storage space.
        
        :params path (str): relative path to the file.
        :params base_dir (str): base directory where the file is located.
        
        :rtype tuple: (int, bytes) representing content length and content data.
        """
        filename = path.lstrip('/')
        if not filename or filename == 'index.html':
            filename = 'index.html'

        filepath = os.path.join(base_dir, filename)
        print("[Response] Serving the object at location {}".format(filepath))

        try:
            with open(filepath, "rb") as f:
                content = f.read()
            return len(content), content
        except Exception as e:
            print("[Response] build_content exception: {}".format(e))
            return -1, b""

    def build_response_header(self, request):
        """
        Constructs the HTTP response headers based on the class:`Request <Request>
        and internal attributes.
        
        :params request (class:`Request <Request>`): incoming request object.
        
        :rtypes bytes: encoded HTTP response header.
        """
        status_line = "HTTP/1.1 {} {}".format(self.status_code, self.reason)

        full_headers = {
            "Date": datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Server": "AsynapRous/1.0",
            "Content-Length": str(len(self._content)),
            "Connection": "close",
        }

        full_headers.update(self.headers)

        if self.status_code == 401 and 'WWW-Authenticate' not in full_headers:
            full_headers["WWW-Authenticate"] = 'Basic realm="HCMUT Secure Area"'

        header_lines = [status_line]
        for key, value in full_headers.items():
            if key.lower() != 'set-cookie':
                header_lines.append("{}: {}".format(key, value))

        if self.cookies:
            for key, value in self.cookies.items():
                header_lines.append("Set-Cookie: {}={}; Path=/".format(key, value))

        if 'Set-Cookie' in self.headers:
            header_lines.append("Set-Cookie: {}".format(self.headers['Set-Cookie']))

        fmt_header = "\r\n".join(header_lines) + "\r\n\r\n"
        return fmt_header.encode('utf-8')

    def build_notfound(self):
        """
        Constructs a standard 404 Not Found HTTP response.
        
        :rtype bytes: Encoded 404 response.
        """
        body = b"404 Not Found"
        header = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n\r\n"
        ).format(len(body)).encode('utf-8')
        return header + body

    def build_response(self, request, envelop_content=None):
        """
        Builds a full HTTP response including headers and content based on the request.
        
        :params request (class:`Request <Request>`): incoming request object.
        
        :rtype bytes: complete HTTP response using prepared headers and content.
        """
        self.request = request
        path = request.path if request else "/"

        if envelop_content is not None:
            if isinstance(envelop_content, dict):
                json_str = json.dumps(envelop_content, ensure_ascii=False)
                self._content = json_str.encode(self.encoding)
                if 'Content-Type' not in self.headers:
                    self.headers['Content-Type'] = 'application/json; charset=utf-8'

            elif isinstance(envelop_content, str):
                self._content = envelop_content.encode(self.encoding)
                if 'Content-Type' not in self.headers:
                    self.headers['Content-Type'] = 'text/html; charset=utf-8'

            elif isinstance(envelop_content, bytes):
                self._content = envelop_content
                if 'Content-Type' not in self.headers:
                    self.headers['Content-Type'] = 'application/octet-stream'

            else:
                self._content = str(envelop_content).encode(self.encoding)
        else:
            mime_type = self.get_mime_type(path)
            base_dir = self.prepare_content_type(mime_type)
            length, content = self.build_content(path, base_dir)

            if length >= 0:
                self._content = content
            else:
                return self.build_notfound()

        self._header = self.build_response_header(request)
        return self._header + self._content
