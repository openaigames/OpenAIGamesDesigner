"""phaser entry point backed by shared web command handling."""
from .. import web_common


def _check(config):
    if config.get("engine") != "phaser":
        raise ValueError("phaser adapter requires engine=phaser")


def inspect(config, project):
    _check(config)
    return web_common.inspect(config, project)


def command(config, project, action, run, output):
    _check(config)
    return web_common.command(config, project, action, run, output)


def starter():
    return web_common.starter("phaser")


def finalize(config, project, action, run, output):
    _check(config)
    return web_common.finalize(config, project, action, run, output)
