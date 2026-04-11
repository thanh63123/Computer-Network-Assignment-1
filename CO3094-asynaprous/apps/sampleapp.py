#
# Copyright (C) 2026 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# AsynapRous release
#

"""
app.sampleapp
~~~~~~~~~~~~~~~~~
"""

import json
import base64
import asyncio

from daemon import AsynapRous

app = AsynapRous()

USER_DB = {
    "admin": "admin123",
    "alice": "alice123",
    "bob": "bob123",
}


def get_basic_auth_creds(auth_header):
    if not auth_header or not auth_header.startswith('Basic '):
        return None, None
    try:
        encoded = auth_header.split(' ')[1]
        decoded = base64.b64decode(encoded).decode('utf-8')
        return decoded.split(':', 1)
    except Exception:
        return None, None


def parse_form_body(body):
    params = {}
    if isinstance(body, bytes):
        body = body.decode('utf-8')
    if isinstance(body, str):
        for pair in body.split('&'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                params[k] = v
    return params


@app.route('/admin', methods=['GET'])
def admin_route(headers, body):
    auth_header = headers.get('authorization', '')
    user, pw = get_basic_auth_creds(auth_header)

    if user and USER_DB.get(user) == pw:
        return "", 302, {"Location": "/form.html"}

    return "Unauthorized", 401, {
        "WWW-Authenticate": 'Basic realm="Admin Area"',
    }


@app.route('/login', methods=['POST'])
def login(headers="guest", body="anonymous"):
    """
    Handle user login via POST request.
    
    This route simulates a login process and prints the provided headers and body
    to the console.
    
    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """
    params = parse_form_body(body) if isinstance(body, str) else body

    username = params.get('username', '')
    password = params.get('password', '')

    if USER_DB.get(username) == password:
        return "Login successful", 302, {
            "Location": "/index.html",
            "Set-Cookie": "auth_token=session_{}; Path=/; HttpOnly".format(username),
        }

    return {"error": "Invalid credentials"}, 401, {}


@app.route("/echo", methods=["POST"])
def echo(headers="guest", body="anonymous"):
    try:
        message = json.loads(body) if isinstance(body, str) else body
        return {"received": message}, 200, {}
    except (json.JSONDecodeError, TypeError):
        return {"error": "Invalid JSON"}, 400, {}


@app.route('/hello', methods=['PUT'])
async def hello(headers, body):
    """
    Handle greeting via PUT request.
    
    This route prints a greeting message to the console using the provided headers
    and body.
    
    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or message payload.
    """
    data = {"id": 1, "name": "Alice", "email": "alice@example.com"}
    return data, 200, {}


@app.route('/slow', methods=['GET'])
async def slow_request(headers, body):
    print("[SampleApp] Processing slow request (10 seconds)...")
    await asyncio.sleep(10)
    print("[SampleApp] Slow request completed!")
    return {
        "status": "completed",
        "message": "10-second task completed without blocking the server!",
    }, 200, {}


def create_sampleapp(ip, port):
    app.prepare_address(ip, port)
    app.run()
