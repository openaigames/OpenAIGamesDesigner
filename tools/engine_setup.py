#!/usr/bin/env python3
"""Explicitly install the Unity execution helper; never replace edited project code."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.engines import unity


def install_unity(root):
    root = root.resolve()
    config = json.loads((root / '.openaigame/project.json').read_text(encoding='utf-8-sig'))
    if config.get('engine') != 'unity':
        raise ValueError('This helper is only for an explicitly selected Unity project')
    project = (root / config['engine_root']).resolve()
    if not project.is_relative_to(root):
        raise ValueError('engine_root must be inside the game project')
    unity.inspect(config, project)
    pairs = []
    for name in ('OAGDEngineBridge.cs', 'OAGDBuild.cs'):
        source = Path(__file__).resolve().parents[1] / 'adapters/engines/unity' / name
        destination = (project / 'Assets/Editor/OpenAIGamesDesigner' / name).resolve()
        if not destination.is_relative_to(project):
            raise ValueError('Refusing a helper destination outside the project')
        data = source.read_bytes()
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError('Existing helper differs; review and back it up before explicitly replacing it: ' + str(destination))
        pairs.append((destination, data))
    # Check every dependency before writing any file.
    for destination, data in pairs:
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(data)
    return pairs[0][0]



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(install_unity(args.project))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')
