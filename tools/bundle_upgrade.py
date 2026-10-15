#!/usr/bin/env python3
"""Prepare an additive bundle delta, preserve local edits, install with guarded backup."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
from check_installation import MANIFEST, bundle_id, check


def sha(data):return hashlib.sha256(data).hexdigest()


def safe(root,relative):
    path=(root/relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root) or path==root:raise ValueError('Unsafe bundle path: '+relative)
    return path


def read_manifest(root):
    value=json.loads((root/MANIFEST).read_text(encoding='utf-8-sig'))
    if value.get('bundle_id')!=bundle_id(value['files']):raise ValueError('Invalid manifest')
    for name in value['files']:safe(root,name)
    return value


def merge_text(before,after,current):
    """Apply each changed hunk only where both context lines match uniquely."""
    old=before.decode('utf-8-sig').replace('\r\n','\n').splitlines(keepends=True)
    new=after.decode('utf-8-sig').replace('\r\n','\n').splitlines(keepends=True)
    actual=current.decode('utf-8-sig').replace('\r\n','\n')
    for tag,i,j,k,l in reversed(difflib.SequenceMatcher(a=old,b=new,autojunk=False).get_opcodes()):
        if tag=='equal':continue
        start=max(0,i-1);end=min(len(old),j+1)
        needle=''.join(old[start:end]);replacement=''.join(old[start:i]+new[k:l]+old[j:end])
        if not needle or actual.count(needle)!=1:raise ValueError('Delta context is missing or ambiguous; explicit merge required')
        actual=actual.replace(needle,replacement,1)
    return actual.encode('utf-8')


def prepare(baseline,new,installed,output,extras=()):
    baseline,new,installed,output=map(lambda p:Path(p).resolve(),(baseline,new,installed,output))
    if output.exists():raise ValueError('Candidate output must not exist')
    old_manifest=read_manifest(baseline);new_manifest=read_manifest(new);local_manifest=read_manifest(installed)
    for folder in (baseline,new):
        result=check(folder)
        if result['missing'] or result['changed']:raise ValueError('Source bundle integrity failed')
    files={};before_hashes={};preserved=[];changed=[];added=[]
    # Only manifest-owned files and explicitly reviewed extras enter the candidate.
    for name in sorted(set(local_manifest['files'])|set(extras)):
        path=safe(installed,name)
        if not path.is_file():raise ValueError('Installed baseline file missing: '+name)
        files[name]=path.read_bytes();before_hashes[name]=sha(files[name])
        if name not in old_manifest['files'] or files[name]!=(baseline/name).read_bytes():preserved.append(name)
    for name in sorted(set(old_manifest['files'])|set(new_manifest['files'])):
        old=(baseline/name).read_bytes() if name in old_manifest['files'] else None
        after=(new/name).read_bytes() if name in new_manifest['files'] else None
        if old==after:continue
        if after is None:raise ValueError('Removal requires explicit migration: '+name)
        actual=files.get(name)
        if actual is None:
            unmanaged=safe(installed,name)
            if unmanaged.exists():raise ValueError('Unreviewed local file collision: '+name)
            files[name]=after;before_hashes[name]=None;added.append(name)
        elif actual==old or actual==after:files[name]=after;changed.append(name)
        else:
            try:files[name]=merge_text(old or b'',after,actual)
            except (UnicodeError,ValueError) as error:raise ValueError(name+': '+str(error)) from error
            changed.append(name)
    hashes={name:sha(data) for name,data in files.items()}
    manifest={'version':1,'bundle_id':bundle_id(hashes),'files':hashes}
    for name,data in files.items():
        path=safe(output,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (output/MANIFEST).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    receipt={'schema_version':1,'source_baseline':old_manifest['bundle_id'],'source_new':new_manifest['bundle_id'],
             'installed_manifest_before':local_manifest['bundle_id'],'candidate':manifest['bundle_id'],
             'target':str(installed),'before':before_hashes,'manifest_before_sha256':sha((installed/MANIFEST).read_bytes()),
             'preserved_local_files':preserved,'updated_files':changed,'added_files':added}
    (output/'upgrade-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    return receipt


def apply(candidate,target,backup):
    candidate,target,backup=map(lambda p:Path(p).resolve(),(candidate,target,backup))
    if backup.exists():raise ValueError('Backup destination must be new')
    if backup.is_relative_to(target) or target.is_relative_to(backup):raise ValueError('Backup and target must be separate')
    receipt=json.loads((candidate/'upgrade-receipt.json').read_text(encoding='utf-8'))
    if str(target)!=receipt['target']:raise ValueError('Candidate is bound to a different installation')
    manifest=read_manifest(candidate)
    if manifest['bundle_id']!=receipt['candidate']:raise ValueError('Candidate identity mismatch')
    integrity=check(candidate)
    if integrity['missing'] or integrity['changed']:raise ValueError('Candidate modified after preparation')
    for name,expected in receipt['before'].items():
        path=safe(target,name)
        actual=sha(path.read_bytes()) if path.is_file() else None
        if actual!=expected:raise ValueError('Installation changed since preparation: '+name)
    if sha((target/MANIFEST).read_bytes())!=receipt['manifest_before_sha256']:raise ValueError('Installed manifest changed')
    names=[name for name in manifest['files'] if receipt['before'].get(name)!=manifest['files'][name]]+[MANIFEST]
    backup.mkdir(parents=True)
    for name in names:
        source=safe(target,name)
        if source.is_file():
            saved=safe(backup/'files',name);saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,saved)
    transaction={'target':str(target),'candidate':manifest['bundle_id'],'files':names,
                 'after':{name:sha((candidate/name).read_bytes()) for name in names},'state':'prepared'}
    (backup/'transaction.json').write_text(json.dumps(transaction,indent=2),encoding='utf-8')
    # Every changed original is backed up before the first live write. A partial
    # transaction remains recoverable using the saved originals and after hashes.
    for name in names:
        destination=safe(target,name);destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name(destination.name+'.oagd-upgrade-tmp')
        if temporary.exists():raise ValueError('Stale upgrade staging file: '+str(temporary))
        owned=False
        try:
            with temporary.open('xb') as out:
                owned=True
                out.write((candidate/name).read_bytes())
            temporary.replace(destination)
        finally:
            # A catchable write/replace failure must not leave our staging file
            # blocking a retry after the saved transaction has been rolled back.
            if owned and temporary.exists():temporary.unlink()
    transaction['state']='applied'
    (backup/'transaction.json').write_text(json.dumps(transaction,indent=2),encoding='utf-8')
    return {'backup':str(backup),'written':len(names),'bundle_id':manifest['bundle_id'],'integrity':check(target)}


def rollback(backup):
    backup=Path(backup).resolve();tx=json.loads((backup/'transaction.json').read_text())
    target=Path(tx['target']).resolve()
    restore=[]
    for name in tx['files']:
        path=safe(target,name);original=safe(backup/'files',name)
        current=sha(path.read_bytes()) if path.is_file() else None
        old=sha(original.read_bytes()) if original.is_file() else None
        if current not in (tx['after'][name],old):raise ValueError('Post-upgrade edits prevent rollback: '+name)
        restore.append((path,original))
    for path,original in restore:
        if original.is_file():shutil.copy2(original,path)
        elif path.exists():path.unlink() # Exact manifest-owned newly added file, never a directory.
    tx['state']='rolled_back';(backup/'transaction.json').write_text(json.dumps(tx,indent=2))
    return {'target':str(target),'state':'rolled_back'}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare')
    for name in ('baseline','new','installed','output'):prep.add_argument('--'+name,required=True,type=Path)
    prep.add_argument('--extras',type=Path,help='JSON array of explicitly reviewed extra relative files to preserve')
    do=sub.add_parser('apply')
    for name in ('candidate','target','backup'):do.add_argument('--'+name,required=True,type=Path)
    undo=sub.add_parser('rollback');undo.add_argument('--backup',required=True,type=Path)
    a=p.parse_args()
    try:
        if a.action=='prepare':r=prepare(a.baseline,a.new,a.installed,a.output,json.loads(a.extras.read_text()) if a.extras else [])
        elif a.action=='apply':r=apply(a.candidate,a.target,a.backup)
        else:r=rollback(a.backup)
        print(json.dumps(r,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as error:print(json.dumps({'error':str(error)},ensure_ascii=False));return 1

if __name__=='__main__':raise SystemExit(main())
