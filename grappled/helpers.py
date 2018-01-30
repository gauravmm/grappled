#!/usr/bin/env python3

import pathlib

import requests
import logging
import ipaddress
from yaml import dump, load

from grappled.plugins import ALL_PLUGINS

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


logger = logging.getLogger("grappled.helpers")

# Load a single plugin
def _load_plugin(act, defaults):
    try:
        key, conf = act.popitem()
    except KeyError:
        raise ValueError("Empty item in do block.")

    if act:
        raise ValueError("Multiple items in do block.")

    if type(conf) is not dict:
        conf = {"_": conf}

    for k, v in defaults.items():
        if k not in conf:
            conf[k] = v

    try:
        return key, ALL_PLUGINS[key](conf)
    except KeyError:
        raise ValueError("Handler not recognized: {}".format(key))

_github_ips = []
_affirmative = lambda c, key: key in c and c[key] in ["yes", "true", "True"]
def _load_ip_whitelist(c):
    # Load the whitelist
    ip_whitelist = []
    if _affirmative(c, "ip-whitelist-github"):
        # If we have yet to download the list of GitHub IP addresses
        if not _github_ips:
            logger.debug("Downloading GitHub IP whitelist.")
            try:
                hook_blocks = requests.get('https://api.github.com/meta').json()['hooks']
                _github_ips = [ipaddress.ip_network(block) for block in hook_blocks]
            except Exception as e:
                logger.warn(e)
                raise ValueError("Failed to download GitHub IP addresses.")

        ip_whitelist.extend(_github_ips)

    if "ip-whitelist" in c:
        logger.debug("Adding custom addresses to IP whitelist.")
        try:
            ip_whitelist.extend(ipaddress.ip_network(block) for block in c["ip-whitelist"])
        except Exception as e:
            logger.warn(e)
            raise ValueError("Cannot parse IP network block {}".format(c["ip-whitelist"]))

    # If a whitelist exists, then it must include the loopback address.
    if ip_whitelist:
        ip_whitelist.append(ipaddress.ip_network("127.0.0.0/16"))

    return ip_whitelist

def normalizeEndpointName(n):
    return n.strip(" /")

# Parse config and return a dictionary of handlers.
def parseConfig(d):
    d = d.resolve(True)
    logger.info("Reading config files from {}".format(d))
    conf = {}
    github_ips = []
    for f in d.iterdir():
        if f.suffix != ".yml":
            logging.warn("Skipping {}. Only .yml files are parsed.".format(f))
            continue

        try:
            c = load(f.resolve().read_text(), Loader=Loader)

            # Set the path.
            c["__path"] = f

            if "endpoint" not in c:
                raise ValueError("Missing endpoint name.")

            # Normalize the endpoint
            c["endpoint"] = normalizeEndpointName(c["endpoint"])
            # Make sure the endpoint is unique
            if c["endpoint"] in conf:
                raise ValueError("Endpoint {} already defined in {}.".format(c["endpoint"], conf[c["endpoint"]]["__file"]))

            do_defaults = c["do-default"] if "do-default" in c else {}

            if "do" not in c:
                raise ValueError("Missing do block.")
            elif not c["do"]:
                raise ValueError("Empty do block.")

            c["do"] = [_load_plugin(act, do_defaults) for act in c["do"]]

            c["ip-whitelist"] = _load_ip_whitelist(c)

            # Conver key from unicode to bytes.
            if "key" in c:
                c["key"] = c["key"].encode()

            conf[c["endpoint"]] = c

        except Exception as e:
            logger.warn("Error while loading {}. Skipping. ({})".format(f, e))

    if conf:
        return conf
    else:
        raise ValueError("No handlers defined")
