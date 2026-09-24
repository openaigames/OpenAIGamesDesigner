#!/usr/bin/env python3
"""Deterministic asset audit; AI supplies only evidence-backed object assignments."""
import argparse, json
from pathlib import Path
from workbench import art_registry, asset_browser

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--init-art',action='store_true',help='Explicitly append empty record tables, preserving existing Art Direction')
    parser.add_argument('--register-missing',action='store_true',help='Register file facts; leave unknown purposes pending')
    args=parser.parse_args();root=args.project.resolve()
    if not root.is_dir():parser.error('项目目录不存在')
    try:
        if args.init_art:art_registry.initialize(root)
        snapshot=asset_browser.scan(root);added=[]
        if args.register_missing and not snapshot['artAudit']['error']:
            registry=art_registry.load(root)
            paths=[a['path'] for a in snapshot['artAudit']['unregistered']]
            if paths:
                added=art_registry.register(root,registry,snapshot['assets'],paths)
                art_registry.write(root,registry,snapshot['artRevision'])
            snapshot=asset_browser.scan(root)
        report={'project':str(root),'registeredNow':added,**snapshot['artAudit']}
        report['document']=art_registry.document_path(root).relative_to(root).as_posix()
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 1 if report['error'] else 0
    except (OSError,ValueError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
