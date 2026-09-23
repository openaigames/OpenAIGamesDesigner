"""threejs entry point backed by shared web command handling."""
from .. import web_common


def _check(config):
    if config.get("engine") != "threejs":
        raise ValueError("threejs adapter requires engine=threejs")


def inspect(config, project):
    _check(config)
    return web_common.inspect(config, project)


def command(config, project, action, run, output):
    _check(config)
    return web_common.command(config, project, action, run, output)


def starter():
    return web_common.starter("threejs")


def finalize(config, project, action, run, output):
    _check(config)
    return web_common.finalize(config, project, action, run, output)
