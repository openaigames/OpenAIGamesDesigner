"""Install an engine recorder or import an actual recording into the project workbench."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from workbench import action_review

ADAPTERS = Path(__file__).resolve().parents[1]/'adapters/engines/action_timing'


def install(engine, target):
    source = ADAPTERS/('web' if engine in ('threejs', 'phaser', 'web') else engine)
    target = target.resolve()
    rows = [(p, target/p.relative_to(source)) for p in source.rglob('*') if p.is_file()]
    for src, dst in rows:
        if not dst.resolve().is_relative_to(target): raise ValueError('目标包含目录链接')
        if dst.exists() and dst.read_bytes() != src.read_bytes(): raise ValueError('目标已修改，保留现有文件：'+str(dst))
    for src, dst in rows:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            with dst.open('xb') as stream: stream.write(src.read_bytes())
    return {'engine': engine, 'files': [{'path': str(dst), 'sha256': hashlib.sha256(dst.read_bytes()).hexdigest()} for _, dst in rows]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    i = sub.add_parser('install'); i.add_argument('--engine', choices=action_review.ENGINES, required=True); i.add_argument('--out', type=Path, required=True)
    r = sub.add_parser('import'); r.add_argument('--project', type=Path, required=True); r.add_argument('--capture', required=True)
    for name in ('spec', 'title', 'video'): r.add_argument('--'+name)
    r.add_argument('--video-zero-s', type=float, default=0)
    l = sub.add_parser('list'); l.add_argument('--project', type=Path, required=True)
    c = sub.add_parser('compare'); c.add_argument('--project', type=Path, required=True); c.add_argument('--a', required=True); c.add_argument('--b', required=True)
    args = p.parse_args()
    try:
        if args.command == 'install': result = install(args.engine, args.out)
        elif args.command == 'import': result = action_review.register(args.project, {k:v for k,v in vars(args).items() if v is not None})
        elif args.command == 'list': result = action_review.snapshot(args.project)
        else: result = action_review.compare(args.project, args.a, args.b)
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False)); return 1


if __name__ == '__main__': raise SystemExit(main())
