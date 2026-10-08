#!/usr/bin/env python3
"""Inspect or fit a local PCM16 WAV to a gameplay window without cloud generation."""
import argparse
import json
from pathlib import Path
import sys
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.assets import audio_timing
from game_workflow import atomic_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('inspect', 'fit', 'decode'):
        child = sub.add_parser(action); child.add_argument('--input', required=True)
        if action == 'fit': child.add_argument('--request', required=True)
        if action in ('fit', 'decode'): child.add_argument('--output', required=True)
    args = parser.parse_args(argv); root = args.project.resolve()
    try:
        source = audio_timing.local_path(root, args.input)
        if args.action == 'inspect': result = audio_timing.inspect(source)
        elif args.action == 'decode':
            target = audio_timing.local_path(root, args.output)
            if target.suffix.lower() != '.wav': raise ValueError('Output must be WAV')
            target.parent.mkdir(parents=True, exist_ok=True)
            result = audio_timing.decode(source, target)
        else:
            request = json.loads(audio_timing.local_path(root, args.request).read_text(encoding='utf-8-sig'))
            request = audio_timing.prepare(root, request)
            timing = request['parameters']['timing']
            target = audio_timing.local_path(root, args.output)
            if target.suffix.lower() != '.wav': raise ValueError('Output must be WAV')
            report = target.with_suffix('.timing.json')
            if target.exists() or report.exists(): raise ValueError('Choose a new output revision')
            target.parent.mkdir(parents=True, exist_ok=True)
            result = audio_timing.fit(source, target, timing)
            result.update(source=args.input, output=args.output, timing=timing)
            if timing.get('source'):
                result['timing_source_sha256'] = audio_timing.digest(audio_timing.local_path(root, timing['source']['path']))
            atomic_json(report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (OSError, ValueError, KeyError, TypeError, wave.Error, EOFError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False)); return 2


if __name__ == '__main__': raise SystemExit(main())
