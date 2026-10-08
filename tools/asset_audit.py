#!/usr/bin/env python3
"""Deterministic asset audit; AI supplies only evidence-backed object assignments."""
import argparse, json
from pathlib import Path
from workbench import art_registry, asset_browser, asset_taxonomy

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True,type=Path)
    parser.add_argument('--init-art',action='store_true',help='Explicitly append empty record tables, preserving existing Art Direction')
    parser.add_argument('--register-missing',action='store_true',help='Register file facts; leave unknown purposes pending')
    classification=parser.add_mutually_exclusive_group()
    classification.add_argument('--classify',choices=sorted(asset_taxonomy.CATEGORY_IDS),help='Save the primary category for the listed files')
    classification.add_argument('--reset-classification',action='store_true',help='Restore automatic categories for the listed files')
    parser.add_argument('--paths',nargs='+',help='Project-relative paths for classification')
    parser.add_argument('--audio-kind',choices=sorted(asset_taxonomy.AUDIO_KINDS),default='')
    args=parser.parse_args();root=args.project.resolve()
    if not root.is_dir():parser.error('项目目录不存在')
    changing=bool(args.classify or args.reset_classification)
    if changing and (not args.paths or args.init_art or args.register_missing):parser.error('分类操作需提供 --paths，并与美术登记操作分别执行')
    if not changing and (args.paths or args.audio_kind):parser.error('--paths 和 --audio-kind 需配合分类操作')
    try:
        if args.init_art:art_registry.initialize(root)
        snapshot=asset_browser.scan(root);added=[]
        if changing:
            by_path={a['path']:a for a in snapshot['assets']}
            previous=by_path.get(args.paths[0],{}).get('classification',{}).get('previousPath') if len(args.paths)==1 else None
            payload={'paths':args.paths,'revision':snapshot['taxonomy']['revision'],
                     'action':'reset' if args.reset_classification else 'set',
                     'classification':{'category':args.classify,'audioKind':args.audio_kind},
                     'previousPath':previous}
            result=asset_taxonomy.save(root,payload,snapshot['assets'])
            print(json.dumps({'project':str(root),**result},ensure_ascii=False,indent=2));return 0
        if args.register_missing and not snapshot['artAudit']['error']:
            registry=art_registry.load(root)
            paths=[a['path'] for a in snapshot['artAudit']['unregistered']]
            if paths:
                added=art_registry.register(root,registry,snapshot['assets'],paths)
                art_registry.write(root,registry,snapshot['artRevision'])
            snapshot=asset_browser.scan(root)
        report={'project':str(root),'registeredNow':added,**snapshot['artAudit']}
        report['document']=art_registry.document_path(root).relative_to(root).as_posix()
        report['classification']={key:snapshot['taxonomy'][key] for key in ('error','needsReview','missingRecords')}
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 1 if report['error'] else 0
    except (OSError,ValueError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
