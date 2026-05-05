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
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

import asyncio
import inspect


# Maximum allowed header size (8KB) to prevent memory exhaustion
# from continuous data flows (Assignment Requirement: non-blocking protocol design)
MAX_HEADER_SIZE = 8192

# Read timeout in seconds to prevent hanging connections
# in the non-blocking async event loop
READ_TIMEOUT = 30


def get_encoding_from_headers(headers):
    return 'utf-8'


class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.
    
    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>`
    and :class:`Response <Response>` objects for full request lifecycle management.
    
    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip", "port", "conn", "connaddr", "routes", "request", "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        self.ip = ip
        self.port = port
        self.conn = conn
        self.connaddr = connaddr
        self.routes = routes
        self.request = Request()
        self.response = Response()

    def _recv_full_request(self, conn):
        """Read a complete HTTP request from a blocking socket.

        Accumulates bytes until the header terminator (\r\n\r\n) is found,
        then reads exactly Content-Length bytes for the body.
        Enforces MAX_HEADER_SIZE to prevent memory exhaustion from
        continuous data flows (Assignment: non-blocking protocol design).
        """
        raw = conn.recv(65536)
        if not raw:
            return None

        while b'\r\n\r\n' not in raw:
            # Guard: reject headers larger than MAX_HEADER_SIZE
            if len(raw) > MAX_HEADER_SIZE:
                print("[HttpAdapter] Header too large ({}B), dropping".format(len(raw)))
                return None
            chunk = conn.recv(65536)
            if not chunk:
                break
            raw += chunk

        if b'\r\n\r\n' not in raw:
            return raw.decode('utf-8', errors='ignore')

        sep = raw.index(b'\r\n\r\n') + 4
        header_bytes = raw[:sep]
        body_so_far = raw[sep:]

        content_length = 0
        for line in header_bytes.decode('utf-8', errors='ignore').split('\r\n'):
            if line.lower().startswith('content-length:'):
                try:
                    content_length = int(line.split(':', 1)[1].strip())
                except ValueError:
                    pass
                break

        while len(body_so_far) < content_length:
            chunk = conn.recv(min(content_length - len(body_so_far), 65536))
            if not chunk:
                break
            body_so_far += chunk

        return (header_bytes + body_so_far).decode('utf-8', errors='ignore')

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.
        
        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.
        
        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """
        self.conn = conn
        self.connaddr = addr
        req = self.request
        resp = self.response

        raw_msg = self._recv_full_request(conn)
        if not raw_msg:
            conn.close()
            return

        req.prepare(raw_msg, routes)
        print("[HttpAdapter] Invoke handle_client connection {}".format(addr))

        response_data = None

        if req.hook:
            result = req.hook(headers=req.headers, body=req.body)

            if isinstance(result, tuple) and len(result) == 3:
                app_body, app_status, app_headers = result
                resp._content = app_body if isinstance(app_body, bytes) else b""
                resp.status_code = app_status

                reasons = {
                    200: "OK", 301: "Moved Permanently", 302: "Found",
                    400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
                    404: "Not Found", 500: "Internal Server Error",
                }
                resp.reason = reasons.get(app_status, "OK")

                if isinstance(app_headers, dict):
                    for k, v in app_headers.items():
                        if k.lower() == 'set-cookie':
                            resp.headers['Set-Cookie'] = v
                        elif k.lower() == 'location':
                            resp.headers['Location'] = v
                        else:
                            resp.headers[k] = v

                response_data = app_body

            elif isinstance(result, (dict, str, bytes)):
                response_data = result
                resp.status_code = 200
                resp.reason = "OK"
            else:
                response_data = result

        response_bytes = resp.build_response(req, envelop_content=response_data)
        conn.sendall(response_bytes)
        conn.close()

    async def _read_full_request_async(self, reader):
        """Read a complete HTTP request from an asyncio StreamReader.

        Uses asyncio.wait_for with READ_TIMEOUT to prevent the coroutine
        from hanging indefinitely on slow or malicious clients.
        Enforces MAX_HEADER_SIZE to prevent memory exhaustion from
        continuous data flows (Assignment: non-blocking protocol design).
        """
        try:
            raw = await asyncio.wait_for(reader.read(65536), timeout=READ_TIMEOUT)
        except asyncio.TimeoutError:
            print("[HttpAdapter] Read timeout on initial data")
            return None
        if not raw:
            return None

        while b'\r\n\r\n' not in raw:
            # Guard: reject headers larger than MAX_HEADER_SIZE
            if len(raw) > MAX_HEADER_SIZE:
                print("[HttpAdapter] Header too large ({}B), dropping".format(len(raw)))
                return None
            try:
                chunk = await asyncio.wait_for(reader.read(65536), timeout=READ_TIMEOUT)
            except asyncio.TimeoutError:
                print("[HttpAdapter] Read timeout waiting for header end")
                return None
            if not chunk:
                break
            raw += chunk

        if b'\r\n\r\n' not in raw:
            return raw.decode('utf-8', errors='ignore')

        sep = raw.index(b'\r\n\r\n') + 4
        header_bytes = raw[:sep]
        body_so_far = raw[sep:]

        content_length = 0
        for line in header_bytes.decode('utf-8', errors='ignore').split('\r\n'):
            if line.lower().startswith('content-length:'):
                try:
                    content_length = int(line.split(':', 1)[1].strip())
                except ValueError:
                    pass
                break

        while len(body_so_far) < content_length:
            remaining = content_length - len(body_so_far)
            try:
                chunk = await asyncio.wait_for(
                    reader.read(min(remaining, 65536)), timeout=READ_TIMEOUT
                )
            except asyncio.TimeoutError:
                print("[HttpAdapter] Read timeout waiting for body")
                break
            if not chunk:
                break
            body_so_far += chunk

        return (header_bytes + body_so_far).decode('utf-8', errors='ignore')

    async def handle_client_coroutine(self, reader, writer):
        """
        Handle an incoming client connection using stream reader writer asynchronously.
        
        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.
        
        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """
        addr = writer.get_extra_info("peername")
        print("[HttpAdapter] New async connection from {}".format(addr))

        try:
            incoming_msg = await self._read_full_request_async(reader)
            if not incoming_msg:
                return

            req = Request()
            req.prepare(incoming_msg, routes=self.routes)

            resp = Response()
            response_data = None

            if req.hook:
                if inspect.iscoroutinefunction(req.hook):
                    result = await req.hook(headers=req.headers, body=req.body)
                else:
                    result = req.hook(headers=req.headers, body=req.body)

                if isinstance(result, tuple) and len(result) == 3:
                    response_data, status_code, extra = result
                    resp.status_code = status_code

                    reasons = {
                        200: "OK", 301: "Moved Permanently", 302: "Found",
                        400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
                        404: "Not Found", 500: "Internal Server Error",
                    }
                    resp.reason = reasons.get(status_code, "OK")

                    if isinstance(extra, dict):
                        for k, v in extra.items():
                            if k.lower() == 'set-cookie':
                                resp.headers['Set-Cookie'] = v
                            elif k.lower() == 'location':
                                resp.headers['Location'] = v
                            else:
                                resp.cookies[k] = v
                else:
                    response_data = result
                    resp.status_code = 200
            else:
                mime_type = resp.get_mime_type(req.path)
                if 'text/html' in mime_type or 'text/css' in mime_type or \
                   'image/' in mime_type or 'javascript' in mime_type:
                    response_data = None
                else:
                    response_data = {"error": "Not Found", "path": req.path}
                    resp.status_code = 404

            msg_to_send = resp.build_response(req, envelop_content=response_data)

            writer.write(msg_to_send)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        except Exception as e:
            print("[HttpAdapter] Coroutine Error: {}".format(e))
            try:
                writer.close()
            except Exception:
                pass

    def extract_cookies(self, req):
        """
        Build cookies from the :class:`Request <Request>` headers.
        
        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}
        cookie_header = req.headers.get("cookie", "")
        if cookie_header:
            for pair in cookie_header.split(";"):
                if "=" in pair:
                    key, value = pair.strip().split("=", 1)
                    cookies[key] = value
        return cookies

    def build_response(self, req, resp_obj):
        """
        Builds a :class:`Response <Response>` object
        
        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        resp_obj.encoding = get_encoding_from_headers(resp_obj.headers)
        resp_obj.reason = "OK"

        if isinstance(req.url, bytes):
            resp_obj.url = req.url.decode("utf-8")
        else:
            resp_obj.url = req.url

        resp_obj.cookies = self.extract_cookies(req)
        resp_obj.request = req
        resp_obj.connection = self
        return resp_obj

    def build_json_response(self, req, resp_obj):
        """
        Builds a :class:`Response <Response>` object from JSON data
        
        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        resp_obj.request = req
        resp_obj.connection = self

        if isinstance(req.url, bytes):
            resp_obj.url = req.url.decode("utf-8")
        else:
            resp_obj.url = req.url

        return resp_obj

    def add_headers(self, request):
        """
        Add headers to the request.
        
        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.
        
        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """
        Returns a dictionary of the headers to add to any request sent
        through a proxy.
        
        :class:`HttpAdapter <HttpAdapter>`.
        
        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        username, password = ("user1", "password")
        if username:
            headers["Proxy-Authorization"] = (username, password)
        return headers
