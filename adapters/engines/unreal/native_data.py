"""Native data/curve inspection and guarded writes, inside UE Python.

Transient JSON is exchange evidence. The native asset remains the author source.
"""
import json
import math
import unreal
from observation_worker import serial


def export_method(asset,method):
    raw=asset.call_method(method,())
    if not isinstance(raw,str) or len(raw)>1024*1024:raise ValueError('Native exporter must return <=1 MiB JSON string')
    data=json.loads(raw,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite export')))
    if not isinstance(data,dict):raise ValueError('Native exporter must return a JSON object')
    return data


def read(spec,load):
    asset=load(spec['path'])
    result={'id':spec['id'],'path':asset.get_path_name(),'class':asset.get_class().get_path_name(),
            'provenance':'native_author_source','properties':{},'curve_samples':[],
            'runtime_effect':'not_established_by_author_read'}
    for prop in spec.get('properties',[]):result['properties'][prop]=serial(asset.get_editor_property(prop))
    if spec.get('read_method'):result['project_export']=export_method(asset,spec['read_method'])
    if spec.get('curve_times') is not None:
        if not isinstance(asset,unreal.CurveFloat):raise ValueError('curve_times currently supports native CurveFloat only')
        result['curve_samples']=[[t,asset.get_float_value(t)] for t in spec['curve_times']]
    return result


def same_readback(expected,actual):
    if type(expected) in (int,float) and type(actual) in (int,float):
        return math.isclose(expected,actual,rel_tol=1e-6,abs_tol=1e-6)
    if isinstance(expected,dict) and isinstance(actual,dict):
        return expected.keys()==actual.keys() and all(same_readback(expected[k],actual[k]) for k in expected)
    if isinstance(expected,list) and isinstance(actual,list):
        return len(expected)==len(actual) and all(same_readback(a,b) for a,b in zip(expected,actual))
    return type(expected) is type(actual) and expected==actual


def patch(spec,load,package):
    package(spec['path'])
    asset=load(spec['path'])
    expected,changes=spec['expected'],spec['values']
    if spec.get('read_method'):
        before=export_method(asset,spec['read_method'])
    else:
        before={key:serial(asset.get_editor_property(key)) for key in expected}
    # Baseline comparison is exact; rounding tolerance applies only to write readback.
    if before!=expected:raise ValueError('Native author data changed; re-read before applying this patch')
    if not set(changes)<=set(before):raise ValueError('Patch cannot introduce unexported native fields')
    if spec.get('write_method'):
        accepted=asset.call_method(spec['write_method'],(json.dumps(changes,allow_nan=False),))
        if accepted is not True:raise ValueError('Project native importer rejected the patch; inspect side effects before retry')
        after=export_method(asset,spec['read_method'])
    else:
        for key,value in changes.items():
            if type(value) not in (int,float,bool,str) or isinstance(before[key],(dict,list)):
                raise ValueError('Complex native values require explicit project read/write methods')
        for key,value in changes.items():
            asset.set_editor_property(key,value)
        after={key:serial(asset.get_editor_property(key)) for key in expected}
    if any(key not in after or not same_readback(value,after[key]) for key,value in changes.items()):
        raise ValueError('Native readback differs from requested values; asset was not saved, inspect the failed session')
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset,only_if_is_dirty=False):raise ValueError('Native asset save failed')
    return {'op':'native_patch','path':spec['path'],'before':before,'after':after,'status':'native_asset_saved',
            'reload_verification':'requires_separate_inspect_session','runtime_validation':'not_run'}
