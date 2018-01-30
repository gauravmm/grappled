#!/usr/bin/env python3

from subprocess import Popen, PIPE

ALL_PLUGINS = {}

def PluginException(BaseException):
    def __init__(self, message, output=None):
        super(PluginException, self).__init__(message)
        self.output = output

def plugin(name):
    assert name not in ALL_PLUGINS
    def _wrapfunc(f):
        ALL_PLUGINS[name] = lambda conf: lambda args: f(conf, args)
        return f

    return _wrapfunc

@plugin("run")
def handle_run(conf, args):
    if "command" not in conf:
        raise PluginException("Missing command in run instruction.")

    cmd = ["sh", "-c", conf["command"]]

    # Add sudo command to switch user
    if "as" in conf:
        cmd = ["sudo", "-H", "-u", conf["as"]] + cmd
    
    runcwd = conf["cwd"] if "cwd" in conf else None

    proc = Popen(cmd, stdout=PIPE, stderr=PIPE, cwd=runcwd)
    sout, serr = proc.communicate()
    exitcode = proc.returncode

    rv = {"code": int(exitcode)}
    if sout:
        rv["stdout"] = sout.decode("utf8")
    if serr:
        rv["stderr"] = serr.decode("utf8")
    
    if exitcode:
        raise PluginException("Non-zero exit code ({})".format(exitcode), rv)

    return rv

@plugin("filter")
def handle_filter(conf, args):
    if "branch" in conf or "branches" in conf:
        branch_prefix = "refs/heads/"
        if args["ref"].startswith(branch_prefix):
            branch = args["ref"][len(branch_prefix):].strip()
            if "branch" in conf and conf["branch"] == branch:
                return
            if "branches" in conf and branch in conf["branches"]:
                return

    raise PluginException("Incoming ref ({}) does not match filter ({})".format(branch, conf))