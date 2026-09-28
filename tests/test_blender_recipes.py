"""Validate recipe boundaries and optionally run real Blender round trips."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.processing import blender, blender_recipe


class RecipeTests(unittest.TestCase):
    """Input validation requires no Blender installation."""

    def setUp(self):
        """Create a temporary input identity; no bpy parser is invoked here."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'source.glb'
        self.source.write_bytes(b'validator-only fixture')
        self.request = {'inputs': [{'snapshot': str(self.source)}], 'parameters': {}}

    def test_legacy_request_defaults_and_explicit_optimization(self):
        """Old format-only requests stay conversion operations."""
        self.assertEqual(blender_recipe.plan(self.request)['operation'], 'convert')
        self.request['parameters'] = {'operation': 'optimize', 'format': 'both', 'decimate_ratio': .4}
        self.assertEqual(blender_recipe.plan(self.request)['decimate_ratio'], .4)

    def test_reject_ambiguous_or_invalid_parameters(self):
        """Reject silent typos, non-finite values and implicit destructive work."""
        for params in ({'operation': 'optimize'}, {'operation': 'unknown'}, {'format': '../x'},
                       {'typo': 1}, {'decimate_ratio': .5}, {'instances': []},
                       {'operation': 'optimize', 'decimate_ratio': float('nan')},
                       {'operation': 'optimize', 'decimate_ratio': True},
                       {'operation': 'optimize', 'decimate_ratio': 0}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                blender_recipe.plan({**self.request, 'parameters': params})

    def test_instance_identity_paths_and_transforms(self):
        """Stable instance IDs and finite positive transforms form the manifest."""
        params = {'operation': 'assemble', 'instances': [{'id': 'column_1', 'input': 0}]}
        self.request['parameters'] = params
        self.assertEqual(blender_recipe.plan(self.request)['instances'][0]['scale'], [1, 1, 1])
        bad = [{'id': '../outside', 'input': 0}, {'id': 'a', 'input': -1}, {'id': 'a', 'input': True},
               {'id': 'a', 'input': 2}, {'id': 'a', 'input': 0, 'scale': [1, -1, 1]},
               {'id': 'a', 'input': 0, 'position': [0, float('inf'), 0]},
               {'id': 'a', 'input': 0, 'path': '/unexpected/model.glb'}]
        for instance in bad:
            with self.subTest(instance=instance), self.assertRaises(ValueError):
                blender_recipe.plan({**self.request, 'parameters': {**params, 'instances': [instance]}})
        params['instances'] *= 2
        with self.assertRaises(ValueError):
            blender_recipe.plan(self.request)
        self.source.unlink()
        with self.assertRaises(ValueError):
            blender_recipe.plan({**self.request, 'parameters': {}})


BLENDER = os.environ.get('OAGD_BLENDER')


@unittest.skipUnless(BLENDER, 'Set OAGD_BLENDER to opt into real Blender verification')
class BlenderRoundTripTests(unittest.TestCase):
    """Generate original fixtures and exercise the production worker and exports."""

    def setUp(self):
        """Use isolated generated assets, never user game files."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture = self.root / 'fixture.py'
        fixture.write_text('''import bpy, sys
from pathlib import Path
folder=Path(sys.argv[sys.argv.index('--')+1])
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16)
mesh=bpy.context.object; mesh.name='Stone'
parent=bpy.data.objects.new('SourceRoot',None); bpy.context.scene.collection.objects.link(parent)
mesh.parent=parent; mesh.location=(1,0,0); parent.location=(1,0,0)
material=bpy.data.materials.new('Sand'); material.use_nodes=True
image=bpy.data.images.new('OriginalFixture',width=8,height=8)
image.generated_color=(.6,.4,.2,1); image.pack()
node=material.node_tree.nodes.new('ShaderNodeTexImage'); node.image=image
material.node_tree.links.new(node.outputs['Color'], material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
mesh.data.materials.append(material)
bpy.ops.export_scene.gltf(filepath=str(folder/'stone.glb'),export_format='GLB')
mesh.shape_key_add(name='Basis'); key=mesh.shape_key_add(name='Dent'); key.data[0].co.z+=.1
bpy.ops.export_scene.gltf(filepath=str(folder/'morph.glb'),export_format='GLB')
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add(); bpy.context.object.name='Block'
bpy.ops.export_scene.gltf(filepath=str(folder/'block.glb'),export_format='GLB')
''')
        self.run_blender(['--python', str(fixture), '--', str(self.root)])

    def run_blender(self, args, success=True):
        """Make Blender script failures observable as nonzero process exits."""
        result = subprocess.run([BLENDER, '--background', '--factory-startup', '--disable-autoexec',
                                 '--python-exit-code', '1', *args], capture_output=True, text=True, timeout=120)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-1000:])
        return result

    def execute(self, request, name):
        """Invoke the same worker command as asset_workflow."""
        request_path = self.root / (name + '.json')
        request_path.write_text(json.dumps(request))
        output, result = self.root / name, self.root / (name + '-result.json')
        argv = blender.command({'executable': BLENDER}, request_path, output, result)
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
        return proc, output, result

    def test_assembly_decimation_source_preservation_and_roundtrip(self):
        """Reopen both deliverables and check hierarchy, transforms and geometry."""
        sources = [self.root / 'stone.glb', self.root / 'block.glb']
        hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        request = {'inputs': [{'snapshot': str(p)} for p in sources], 'parameters': {
            'operation': 'assemble', 'format': 'both', 'decimate_ratio': .5,
            'instances': [{'id': 'near', 'input': 0}, {'id': 'wall', 'input': 1, 'position': [-3, 0, 0]},
                          {'id': 'far', 'input': 0, 'position': [4, 0, 0],
                           'rotation_degrees': [0, 0, 90], 'scale': [.5, .5, .5]}]}}
        proc, output, result_path = self.execute(request, 'assembled')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(result_path.read_text())
        self.assertEqual(len(result['artifacts']), 3)
        report = json.loads((output / 'processing-report.json').read_text())
        self.assertEqual(report['observations']['mesh_objects'], 3)
        self.assertEqual(report['quality_validation'], 'not_checked')
        self.assertLess(report['instances'][0]['after']['triangles'], report['instances'][0]['before']['triangles'])
        self.assertEqual(hashes, [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources])
        check = self.root / 'check.py'
        check.write_text('''import bpy, sys
from mathutils import Vector
from pathlib import Path
path=Path(sys.argv[sys.argv.index('--')+1])
if path.suffix=='.blend': bpy.ops.wm.open_mainfile(filepath=str(path))
else:
 bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
 bpy.ops.import_scene.gltf(filepath=str(path))
bpy.context.view_layer.update()
meshes=[o for o in bpy.data.objects if o.type=='MESH']; assert len(meshes)==3
for prefix,expected in [('near__Stone',(2,0,0)),('far__Stone',(4,1,0)),('wall__Block',(-3,0,0))]:
 obj=next(o for o in meshes if o.name.startswith(prefix))
 assert (obj.matrix_world.translation-Vector(expected)).length<.001, (obj.name,tuple(obj.matrix_world.translation))
assert any(i.packed_file for i in bpy.data.images), 'Texture not packed'
''')
        for extension in ('blend', 'glb'):
            self.run_blender(['--python', str(check), '--', str(output / ('processed.' + extension))])
        repeated, _, _ = self.execute(request, 'assembled')
        self.assertNotEqual(repeated.returncode, 0)
        self.assertEqual(json.loads((output / 'processing-report.json').read_text()), report)
        # A new attempt reconstructs exactly three instances, not accumulated duplicates.
        rerun, rerun_output, _ = self.execute(request, 'assembled-again')
        self.assertEqual(rerun.returncode, 0, rerun.stdout)
        self.assertEqual(json.loads((rerun_output / 'processing-report.json').read_text()), report)

    def test_conversion_compatibility_and_morph_optimization_refusal(self):
        """Ordinary conversion preserves morphing models; decimation refuses them."""
        request = {'inputs': [{'snapshot': str(self.root / 'morph.glb')}], 'parameters': {'format': 'glb'}}
        proc, _, result = self.execute(request, 'converted')
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(json.loads(result.read_text())['quality_validation'], 'not_checked')
        request['parameters'] = {'operation': 'optimize', 'decimate_ratio': .5}
        proc, output, result = self.execute(request, 'refused')
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(result.exists())
        self.assertFalse((output / 'processed.glb').exists())

    def test_animation_only_fbx_and_gltf_conversion_preserves_tracks(self):
        """A mesh is unnecessary for convert; static recipes must still reject rigs."""
        fixture = self.root / 'animation.py'
        fixture.write_text('''import bpy, sys
from pathlib import Path
folder=Path(sys.argv[sys.argv.index('--')+1])
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='MotionRig'
rig.data.bones[0].name='Root'
bone=rig.pose.bones['Root'];bone.rotation_mode='XYZ'
bone.rotation_euler=(0,0,0);bone.keyframe_insert('rotation_euler',frame=1)
bone.rotation_euler=(0,.7,0);bone.keyframe_insert('rotation_euler',frame=24)
bpy.context.scene.frame_end=24
bpy.ops.export_scene.fbx(filepath=str(folder/'motion.fbx'),object_types={'ARMATURE'},add_leaf_bones=False,bake_anim=True)
bpy.ops.export_scene.gltf(filepath=str(folder/'motion.glb'),export_format='GLB',export_animations=True)
''')
        self.run_blender(['--python', str(fixture), '--', str(self.root)])
        def document(path):
            import struct
            raw=path.read_bytes();size,kind=struct.unpack('<II',raw[12:20])
            self.assertEqual(kind,0x4E4F534A)
            return json.loads(raw[20:20+size])
        # Inspect exported input as well as output, so an empty generated fixture cannot pass.
        input_doc=document(self.root/'motion.glb')
        self.assertTrue(input_doc.get('animations'))
        for extension in ('fbx','glb'):
            source=self.root/('motion.'+extension);before=hashlib.sha256(source.read_bytes()).hexdigest()
            request={'inputs':[{'snapshot':str(source)}],'parameters':{'format':'both'}}
            proc,output,result=self.execute(request,'motion-'+extension)
            self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
            output_doc=document(output/'processed.glb')
            self.assertTrue(output_doc.get('animations'))
            self.assertTrue(any('Root' in n.get('name','') for n in output_doc.get('nodes',[])))
            self.assertTrue(all(a.get('channels') and a.get('samplers') for a in output_doc['animations']))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
            check=self.root/('check-motion-'+extension+'.py')
            check.write_text('''import bpy,sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index('--')+1])
assert len(bpy.data.actions)>0
assert not any(o.type=='MESH' for o in bpy.data.objects)
''')
            self.run_blender(['--python',str(check),'--',str(output/'processed.blend')])
            request['parameters']={'operation':'optimize','decimate_ratio':.5}
            refused,_,result=self.execute(request,'refuse-motion-'+extension)
            self.assertNotEqual(refused.returncode,0)
            self.assertFalse(result.exists())


if __name__ == '__main__':
    unittest.main()
