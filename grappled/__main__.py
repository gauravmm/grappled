#!/usr/bin/env python3

import argparse
import hmac
import io
import ipaddress
import logging
import os
import re
from hashlib import sha1
from uuid import UUID
import pathlib

import flask
from expiringdict import ExpiringDict
from flask import abort, request, json

import grappled
import grappled.helpers

h = logging.StreamHandler()
h.setLevel(logging.INFO)
h.setFormatter(logging.Formatter('[%(asctime)s %(levelname)-3s @%(name)s] %(message)s', datefmt='%H:%M:%S'))
logging.basicConfig(level=logging.DEBUG, handlers=[h])
logger = logging.getLogger("grappled")

# Automatically convert JSON
class JSONResponse(flask.Response):
    def __init__(self, content=None, *args, **kargs):
        if isinstance(content, dict):
            kargs['mimetype'] = 'application/json'
            content = json.dumps(content)

        super(JSONResponse, self).__init__(content, *args, **kargs)

    @classmethod
    def force_type(cls, response, environ=None):
        """Override with support for list/dict."""
        if isinstance(response, (list, dict)):
            return cls(response)
        else:
            return super(flask.Response, cls).force_type(response, environ)

# Amend the response header
class GrappledFlask(flask.Flask):
    response_class = JSONResponse
    def process_response(self, response):
        response.headers['server'] = "{}".format(grappled.SERVER_STRING)
        return response

# API Exceptions:
class GrappledAPIException(Exception):
    def __init__(self, message, status_code=400):
        Exception.__init__(self)
        self.message = message
        self.status = status_code


def run(args):
    logger = logging.getLogger("grappled.main.run")
    logger.debug("Launched with arguments: {}".format(args))

    try:
        config = grappled.helpers.parseConfig(args.config_dir)
    except Exception as e:
        logger.error("Fatal error parsing configuration files.")
        logger.error(e)
        return

    app = GrappledFlask(__name__)
    if not args.no_proxyfix:
        from werkzeug.contrib.fixers import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)

    guid_history = None
    if args.guid:
        guid_history = ExpiringDict(max_len=1000, max_age_seconds=3600)

    # Error Handlers:
    @app.errorhandler(GrappledAPIException)
    def error_handler(error):
        logger.warn(error)
        if args.debug:
            return {'status': error.status, 'message': error.message}, error.status
        else:
            return {'status': 500, 'message': 'Internal Server Error'}, 500

    # Main Endpoint
    @app.route("/<endpoint>", methods=['GET', 'POST'])
    def index(endpoint=None):
        # Get the relevant endpoint object.
        # Normalize the endpoint name:
        endpoint = grappled.helpers.normalizeEndpointName(endpoint)
        try:
            end_cfg = config[endpoint]
        except KeyError:
            raise GrappledAPIException("Endpoint not found: {}".format(endpoint), 404)

        if end_cfg['ip-whitelist']:
            request_ip = ipaddress.ip_address(str(request.remote_addr))
            # Check the whitelist
            if not any((request_ip in white) for white in end_cfg['ip-whitelist']):
                raise GrappledAPIException("IP not in whitelist: {}".format(request_ip), 401)

        # Track GUID
        if not request.headers.get('X-Github-Delivery'):
            raise GrappledAPIException("Rejected event with missing UUID.", 403)
        in_guid = UUID(request.headers.get('X-Github-Delivery'))

        if guid_history is not None:
            if in_guid in guid_history:
                raise GrappledAPIException("Rejected event with duplicate UUID {}".format(in_guid), 401)
            guid_history[in_guid] = True

        # Check signature
        if "key" in end_cfg:
            try:
                hashtype, signature = request.headers.get('X-Hub-Signature').split('=', 2)
            except:
                raise GrappledAPIException("Signature in unexpected format.", 403)

            if hashtype != "sha1":
                raise GrappledAPIException("Signature uses unexpected hash type. Only SHA-1 is supported.", 403)

            assert type(end_cfg["key"]) is bytes
            mac = hmac.new(end_cfg["key"], msg=request.data, digestmod=sha1)
            if not hmac.compare_digest(mac.hexdigest(), signature):
                raise GrappledAPIException("Invalid signature.", 403)

        if request.method == 'POST':
            # Respond to ping events.
            if request.headers.get('X-GitHub-Event') == "ping":
                return {'msg': 'pong'}

            if request.headers.get('X-GitHub-Event') != "push":
                raise GrappledAPIException("Only push events are supported.", 400)

            try:
                payload = request.get_json(force=True)
            except Exception as e:
                raise GrappledAPIException("Malformed JSON input.", 400)

            rv = {"status": 200, "error": None, "guid": in_guid, "do": []}

            for act_name, action in end_cfg["do"]:
                try:
                    dostr = action(payload)
                    rv["do"].append({"plugin_name": act_name, "output": dostr})

                except Exception as e:
                    rv["error"] = {"plugin_name": act_name, "message": str(e)}
                    if hasattr(e, "output"):
                        rv["error"]["output"] = e.output
                    break

            return rv

        else:
            raise GrappledAPIException("Method Not Allowed. Only POST requests are allowed.", 405)

    app.run(host=str(args.ip), port=args.port)

if __name__ == "__main__":
    logger.info("Started")

    parser = argparse.ArgumentParser(prog="python3 -m grappled", description='Handle GitHub webhooks.')
    parser.add_argument('config_dir', nargs="?", default="config-active/", type=pathlib.Path, help="directory containing (symlinks to) configuration files")

    parser.add_argument('--ip', default="0.0.0.0", type=ipaddress.ip_address, help="ip address of local interface to bind to")
    parser.add_argument('--port', default=19891, type=int, help="port to listen on")

    parser.add_argument('--debug', action="store_true", help="show rich error data")

    parser.add_argument('--no-proxyfix', action="store_true", help="Don't use werkzeug ProxyFix")
    parser.add_argument('--guid', action="store_true", help="Prevent replay attacks by tracking GUIDs")

    try:
        run(parser.parse_args())
    except Exception as e:
        logger.error(e)
    finally:
        logger.info("Halted")
