"""Optional Blender evidence capture; never edits or saves the source model."""
import json
from pathlib import Path
import shutil
import struct
import subprocess

from .quality import path, read, write, bind, verify_dependencies, digest


def self_contained_glb(source):
    if source.suffix.lower() != '.glb' or source.stat().st_size > 1024**3:
        raise ValueError('Capture accepts a self-contained GLB up to 1 GiB')
    with source.open('rb') as stream:
        header = stream.read(20)
        if len(header) != 20:
            raise ValueError('Truncated GLB')
        magic, version, length, size, kind = struct.unpack('<4sIIII', header)
        if magic != b'glTF' or version != 2 or length != source.stat().st_size or kind != 0x4e4f534a or size > 32*1024**2 or size + 20 > length:
            raise ValueError('Invalid GLB header')
        document = json.loads(stream.read(size).decode('utf-8'))
    for item in document.get('buffers', []) + document.get('images', []):
        if item.get('uri') and not item['uri'].startswith('data:'):
            raise ValueError('Embed external GLB buffers/textures before capture')
    # Unknown extensions can read external resources or change rendered geometry.
    allowed = {'KHR_materials_unlit', 'KHR_materials_specular', 'KHR_materials_ior',
               'KHR_materials_transmission', 'KHR_materials_volume', 'KHR_materials_clearcoat',
               'KHR_materials_sheen', 'KHR_materials_emissive_strength', 'KHR_texture_transform',
               'KHR_mesh_quantization', 'KHR_draco_mesh_compression'}
    if set(document.get('extensionsUsed', [])) - allowed:
        raise ValueError('GLB uses extensions not covered by this capture worker')
    return document


def capture(root, model, output, blender, front='-Y', units='unknown', resolution=512):
    root = Path(root).resolve()
    target, source, executable = path(root, output), path(root, model), Path(blender)
    if target.exists():
        raise ValueError('Use a new capture directory')
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError('Supply an absolute path to an installed Blender executable')
    if front not in ('-X','+X','-Y','+Y') or units not in ('meters','centimeters','unknown') or type(resolution) is not int or not 128 <= resolution <= 2048:
        raise ValueError('Invalid front axis, units or resolution')
    self_contained_glb(source)
    deps = {}
    sha = bind(root, deps, model)
    target.mkdir(parents=True)
    snapshot = target / 'source.glb'
    shutil.copyfile(source, snapshot)
    bind(root, deps, snapshot.relative_to(root).as_posix(), sha)
    config = {'source':str(snapshot), 'output':str(target), 'front':front, 'units':units, 'resolution':resolution}
    write(target/'capture-request.json', config)
    worker = Path(__file__).resolve().parents[1] / 'processing/asset_evidence_blender.py'
    command = [str(executable), '--background', '--factory-startup', '--disable-autoexec',
               '--python-exit-code', '1', '--python', str(worker), '--', str(target/'capture-request.json')]
    with (target/'blender.log').open('wb') as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=240)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('Blender capture timed out; inspect blender.log') from exc
    if result.returncode or not (target/'model-metrics.json').is_file():
        raise ValueError('Blender capture failed; inspect blender.log')
    metrics = read(root, output + '/model-metrics.json')
    views = []
    for camera in metrics['views']:
        direction = camera['direction']
        relative = output + '/' + direction + '.png'
        bind(root, deps, relative)
        views.append({'id':'model_' + direction, 'set':'model', 'path':relative,
            'direction':direction, 'projection':'orthographic', 'segmentation':{'alpha':True},
            'calibration':{'group':'model_capture', 'pixels_per_unit':metrics['pixels_per_unit'],
                           'baseline_y':metrics['baseline_y']}})
    for name in ('model-metrics.json','blender.log','capture-request.json'):
        bind(root, deps, output + '/' + name)
    verify_dependencies(root, deps)
    record = {'schema_version':1,'format':'asset-model-capture','source':{'path':model,'sha256':sha},
              'views':views,'dependencies':deps,'metrics':output+'/model-metrics.json',
              'worker_sha256':digest(worker)}
    write(target/'capture.json', record)
    return record
