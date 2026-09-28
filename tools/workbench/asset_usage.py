"""Read an engine-generated, hash-verified asset usage manifest."""
import hashlib, json

def read(root):
    path=root/'.asset-browser'/'usage.json'
    if not path.exists():return {}, {'status':'missing','message':'尚未生成游戏引用清单'}
    try:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or path.stat().st_size>4*1024*1024:raise ValueError('无效的引用清单')
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        if data.get('version')!=1:raise ValueError('不支持的引用清单版本')
        for rel, expected in data['dependencies'].items():
            target=(root/rel).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():raise ValueError('引用文件缺失：'+rel)
            if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise ValueError('引用已变化，请重新核对：'+rel)
        rows={}
        for row in data['assets']:
            if not isinstance(row,dict) or not isinstance(row.get('path'),str):raise ValueError('引用记录格式错误')
            rel=row['path']
            if rel not in data['dependencies']:raise ValueError('引用缺少哈希：'+rel)
            rows[rel]={'status':'used','roles':row.get('roles',[]),'clips':row.get('clips',[]),'evidence':data.get('evidence','')}
        return rows, {'status':'verified','message':data.get('description','引擎引用已核对'),'generatedAt':data.get('generatedAt'),'count':len(rows)}
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        return {}, {'status':'stale','message':str(exc)}
