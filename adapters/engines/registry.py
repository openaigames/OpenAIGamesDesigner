"""Explicit engine selection; never infer an engine from installed software."""
from .unity import production as unity
from .unreal import production as unreal

DRIVERS = {'unity': unity, 'unreal': unreal}


def production_driver(name):
    try:
        return DRIVERS[name]
    except KeyError:
        raise ValueError('No production driver for explicitly selected engine: ' + str(name)) from None
