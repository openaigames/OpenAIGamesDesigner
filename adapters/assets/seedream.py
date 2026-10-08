"""Seedream images through the shared Ark adapter."""
from . import ark

def command(settings, request, output, result):
    return ark.command('seedream', settings, request, output, result)

def validate(paths):
    ark.validate(paths, 'seedream')
