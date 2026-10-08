"""Seedance videos through the shared Ark adapter."""
from . import ark

def command(settings, request, output, result):
    return ark.command('seedance', settings, request, output, result)

def validate(paths):
    ark.validate(paths, 'seedance')
