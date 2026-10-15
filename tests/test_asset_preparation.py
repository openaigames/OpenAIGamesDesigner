"""Offline behavioral cases for asset requirements and frozen generation inputs."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
from adapters.assets import input_preparation as prep, model_defaults, api_common, tripo
from adapters.assets import generation_approval, credential_store, model_prompt_policy
import asset_workflow
import asset_prepare
import validate_records


def png(color):
    """A real, decodable RGB PNG fixture, without an optional imaging dependency."""
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    raw = (b'\0' + bytes(color) * 256) * 256
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 256, 256, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        policy_path = patch.object(model_prompt_policy, 'user_path', return_value=self.root / 'isolated-policy.json')
        policy_path.start()
        self.addCleanup(policy_path.stop)
        self.spec = {'schema_version': 1, 'asset_id': 'warehouse_crate', 'kind': 'model',
                     'brief': 'A worn red wooden supply crate for an FPS warehouse.',
                     'requirements': [
                         {'id': 'shape', 'text': 'Keep the rectangular crate silhouette.',
                          'category': 'identity', 'priority': 'must'},
                         {'id': 'color', 'text': 'Keep the red painted wood.',
                          'category': 'appearance', 'priority': 'must'}], 'references': []}
        self.plan = {'schema_version': 1, 'provider': 'tripo', 'parameters': {'type': 'text_to_model'},
                     'references': [], 'routes': [{'requirement': r['id'], 'via': 'prompt'} for r in self.spec['requirements']],
                     'review': {'reviewer': 'synthetic-case-fixture',
                                'notes': 'Input routing fixture only; no visual assessment claimed.',
                                **dict.fromkeys(prep.REVIEW_CHECKS, True)}}
        self.settings = {'mode': 'api'}

    def reference(self, name='front', color=(220, 30, 40), view='front', send=True):
        path = 'references/' + name + '.png'
        (self.root / path).parent.mkdir(exist_ok=True)
        (self.root / path).write_bytes(png(color))
        entry = {'id': name, 'path': path, 'role': 'shape'}
        if view is not None:
            entry['view'] = view
        self.spec['references'].append(entry)
        self.plan['references'].append({'id': name, 'send': send, 'reason': 'Fixture routing decision'})
        return entry

    def image_route(self, provider='tripo', mode='image_to_model'):
        self.plan['provider'] = provider
        self.plan['parameters'] = {'type': mode} if provider == 'tripo' else {}
        self.reference()
        self.plan['routes'] = [
            {'requirement': r['id'], 'via': 'reference', 'references': ['front'],
             'evidence': 'Synthetic fixture declaration; no object recognition asserted.'}
            for r in self.spec['requirements']]

    def compile(self):
        return prep.compile_inputs(self.root, self.spec, self.plan, self.settings)

    def save(self, output='prepared'):
        for name, value in (('spec.json', self.spec), ('plan.json', self.plan)):
            (self.root / name).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        record = prep.prepare(self.root, 'spec.json', 'plan.json', output)
        request = json.loads((self.root / output / 'request.json').read_text(encoding='utf-8'))
        return record, request

    def assert_blocked(self, code):
        record = self.compile()
        self.assertEqual(record['status'], 'blocked', record)
        self.assertIn(code, [e['code'] for e in record['errors']], record['errors'])
        return record

    def test_crate_text_preserves_brief_constraints_and_pins_models(self):
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        body = record['preview']['body']
        self.assertEqual(body['model'], model_defaults.TRIPO)
        self.assertEqual(body['texture_version'], model_defaults.TRIPO_TEXTURE)
        for text in [self.spec['brief']] + [r['text'] for r in self.spec['requirements']]:
            self.assertIn(text, body['prompt'])
        self.assertFalse(record['review']['quality_verified'])
        self.assertNotIn('model_version', body)
        self.assertNotIn('type', body)

    def test_door_technical_requirements_remain_pending(self):
        self.spec['asset_id'] = 'warehouse_door'
        self.spec['brief'] = 'A warehouse door with a separate frame.'
        self.spec['requirements'].append({'id': 'opening', 'category': 'technical', 'priority': 'must',
                                          'text': 'Clear opening is 1.2 m wide.', 'attribute': 'opening_width_m', 'value': 1.2})
        self.plan['routes'].append({'requirement': 'opening', 'via': 'postprocess',
                                    'reason': 'Calibrate the model and collision after import.',
                                    'check': 'Measure the clear opening in Godot and Unreal; test passage.'})
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        row = record['coverage'][-1]
        self.assertEqual(row['status'], 'pending')
        self.assertFalse(row['output_verified'])
        self.assertNotIn('1.2 m', record['preview']['body']['prompt'])

    def test_rewrite_retains_required_clauses_and_exposes_diff(self):
        self.plan['rewrite'] = {'text': 'A red wooden warehouse supply crate with surface wear.',
                                'reason': 'Group object, material and surface description.'}
        record = self.compile()
        self.assertIn('-' + self.spec['brief'], record['prompt_diff'])
        self.assertIn(self.spec['requirements'][0]['text'], record['request']['parameters']['prompt'])
        self.plan['review']['no_unrequested_features'] = False
        self.assert_blocked('semantic_review')

    def test_image_only_has_no_phantom_prompt(self):
        self.image_route()
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        self.assertNotIn('prompt', record['preview']['body'])
        self.assertNotIn('brief', record['preview']['body'])
        self.assertIn('file_token sha256=', record['preview']['body']['input'])
        self.assertFalse(record['preview']['submitted'])

    def test_asymmetric_weapon_multiview_order_and_no_shape_claim(self):
        self.image_route(mode='multiview_to_model')
        self.reference('back', (30, 220, 40), 'back')
        self.reference('left', (30, 40, 220), 'left')
        self.plan['references'].reverse()
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        self.assertEqual([next(iter(r)) for r in record['preview']['body']['inputs']], ['front', 'left', 'back'])
        self.assertTrue(all(not r['output_verified'] for r in record['coverage']))
        self.assertIn('not measured', record['coverage'][0]['evidence_kind'])

    def test_generated_views_are_image_deliverable(self):
        self.image_route(mode='generate_multiview_image')
        self.assert_blocked('output_kind')
        self.spec['kind'] = 'image'
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        self.assertEqual(set(record['preview']['body']), {'input'})
        self.assertNotIn('model_version', record['request']['parameters'])

    def test_hunyuan_text_and_explicit_sketch_version(self):
        self.plan.update(provider='hunyuan3d', parameters={})
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        self.assertEqual(record['preview']['body']['Model'], model_defaults.HUNYUAN)
        self.reference()
        self.plan['parameters'] = {'Model': '3.0', 'GenerateType': 'Sketch'}
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        self.assertEqual(record['preview']['body']['Model'], '3.0')
        self.assertIn('Prompt', record['preview']['body'])
        self.assertTrue(record['preview']['body']['ImageBase64'].startswith('<reference'))
        del self.plan['parameters']['Model']
        self.assert_blocked('capability')

    def test_hunyuan_multiview_uses_declared_directions(self):
        self.image_route('hunyuan3d')
        self.reference('top', (5, 50, 240), 'top')
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        self.assertNotIn('Prompt', record['preview']['body'])
        self.assertEqual(record['preview']['body']['MultiViewImages'][0]['ViewType'], 'top')

    def test_seedream_palette_reference(self):
        self.spec['kind'] = 'image'
        self.plan.update(provider='seedream', parameters={})
        self.reference('palette', view=None)
        self.spec['references'][0]['role'] = 'style'
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        self.assertTrue(record['preview']['body']['image'].startswith('<reference'))
        self.assertEqual(record['request']['parameters']['size'], '2K')

    def test_seedance_first_frame_and_ratio_validation(self):
        self.spec['kind'] = 'video'
        self.plan.update(provider='seedance', parameters={'ratio': 'adaptive'})
        self.reference('first_frame', view=None)
        record = self.compile()
        self.assertEqual(record['status'], 'ready', record['errors'])
        self.assertEqual(record['preview']['body']['content'][1]['role'], 'first_frame')
        self.plan['parameters']['ratio'] = '16:9'
        self.assert_blocked('adapter_validation')

    def test_audio_descriptions_and_literal_speech(self):
        for kind, params in [('sound_effect', {'duration_seconds': 1.5}),
                             ('music', {'music_length_ms': 10000})]:
            with self.subTest(kind=kind):
                self.spec['kind'] = kind
                self.plan.update(provider='elevenlabs', parameters={'kind': kind, **params})
                self.assertEqual(self.compile()['status'], 'ready')
        self.spec.update(kind='speech', brief='门已经打开。', requirements=[])
        self.plan.update(parameters={'kind': 'speech', 'voice_id': 'fixture_voice'}, routes=[])
        self.assertEqual(self.compile()['preview']['body']['text'], '门已经打开。')
        self.plan['rewrite'] = {'text': 'The door is open.', 'reason': 'Translation'}
        self.assert_blocked('speech_rewrite')

    def test_host_image(self):
        self.spec['kind'] = 'image'
        self.plan.update(provider='image', parameters={})
        self.settings = {'mode': 'host'}
        self.reference('shape', view=None)
        record, request = self.save()
        self.assertEqual(record['status'], 'ready', record['errors'])
        job = asset_workflow.new_job(self.root, 'image', request, self.settings)
        self.assertEqual(job['status'], 'queued')

    def test_missing_unknown_duplicate_routes(self):
        self.plan['routes'].pop()
        self.assert_blocked('coverage')
        self.plan['routes'].append({'requirement': 'invented', 'via': 'prompt'})
        self.assert_blocked('coverage')
        self.plan['routes'].append(self.plan['routes'][0])
        self.assert_blocked('duplicate_route')

    def test_conflicting_required_values(self):
        for requirement, value in zip(self.spec['requirements'], ('red', 'blue')):
            requirement.update(attribute='base_color', value=value)
        self.assert_blocked('conflicting_constraint')

    def test_unsupported_prompt_not_silently_dropped(self):
        self.image_route()
        self.plan['routes'][0] = {'requirement': 'shape', 'via': 'prompt'}
        self.assert_blocked('unsupported_prompt')
        record, request = self.save()
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            asset_workflow.new_job(self.root, 'tripo', request, self.settings)
        self.assertFalse((self.root / '.openaigame/asset-jobs').exists())

    def test_excluded_reference_and_unseen_evidence(self):
        self.image_route()
        self.plan['references'][0]['send'] = False
        self.assert_blocked('unsent_reference')
        self.plan['references'][0]['send'] = True
        self.plan['routes'][0].pop('evidence')
        self.assert_blocked('reference_evidence')

    def test_reference_decisions_cannot_disappear(self):
        self.image_route()
        self.plan['references'] = []
        self.assert_blocked('reference_decisions')

    def test_duplicate_views_images_and_invalid_content(self):
        self.image_route(mode='multiview_to_model')
        self.reference('back', (220, 30, 40), 'back')
        self.assert_blocked('duplicate_image')
        (self.root / 'references/back.png').write_bytes(png((1, 2, 3)))
        self.spec['references'][1]['view'] = 'front'
        self.assert_blocked('adapter_validation')
        self.spec['references'][1]['view'] = 'back'
        (self.root / 'references/back.png').write_bytes(b'not an image')
        self.assert_blocked('adapter_validation')

    def test_unresolved_deferred_and_review_requirements(self):
        self.plan['routes'][0] = {'requirement': 'shape', 'via': 'unresolved'}
        self.assert_blocked('unresolved_requirement')
        self.plan['routes'][0]['via'] = 'postprocess'
        self.assert_blocked('deferred_check')
        self.plan.pop('review')
        self.assert_blocked('semantic_review')

    def test_parameter_prompt_override_and_unsent_rewrite(self):
        self.plan['parameters']['prompt'] = 'silently replace the original'
        self.assert_blocked('prompt_override')
        self.image_route()
        self.plan['rewrite'] = {'text': 'New description', 'reason': 'Test'}
        self.assert_blocked('unsent_rewrite')

    def test_existing_project_prompt_requirement_is_not_waived(self):
        self.image_route()
        (self.root / '.openaigame').mkdir()
        (self.root / '.openaigame/generation-policy.json').write_text(
            json.dumps({'version': 1, 'require_3d_prompt': True}), encoding='utf-8')
        self.assert_blocked('adapter_validation')

    def test_queue_preserves_preparation_and_contract(self):
        record, request = self.save()
        job = asset_workflow.new_job(self.root, 'tripo', request, self.settings)
        self.assertEqual(job['request']['preparation'], request['preparation'])
        path = asset_workflow.location(self.root, job['job_id']) / 'job.json'
        self.assertEqual(validate_records.check_record('asset-job', job, self.root, path), [])
        self.assertEqual(job['attempts'], [])
        self.assertIsNone(job['provider_job_id'])

    def test_changed_prompt_model_settings_and_provider_block_before_queue(self):
        _, request = self.save()
        for field, value in [('prompt', 'changed'), ('model_version', 'changed')]:
            with self.subTest(field=field):
                changed = deepcopy(request)
                changed['parameters'][field] = value
                with self.assertRaises(ValueError):
                    asset_workflow.new_job(self.root, 'tripo', changed, self.settings)
        with self.assertRaisesRegex(ValueError, 'settings'):
            prep.verify_request(self.root, 'tripo', request, {'mode': 'api', 'api_key_env': 'OTHER_KEY'})
        with self.assertRaisesRegex(ValueError, 'Provider'):
            prep.verify_request(self.root, 'hunyuan3d', request, self.settings)
        self.assertFalse((self.root / '.openaigame/asset-jobs').exists())

    def test_sources_change_requires_reprepare_but_queued_job_keeps_snapshots(self):
        self.image_route()
        _, request = self.save()
        job = asset_workflow.new_job(self.root, 'tripo', request, self.settings)
        (self.root / 'references/front.png').write_bytes(png((3, 2, 1)))
        (self.root / 'spec.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            asset_workflow.new_job(self.root, 'tripo', request, self.settings)
        prep.verify_request(self.root, 'tripo', job['request'], self.settings)
        retry = asset_workflow.new_job(self.root, 'tripo', job['request'], self.settings, retry_of=job['job_id'])
        self.assertEqual(retry['request']['parameters'], job['request']['parameters'])
        self.assertEqual(retry['request']['preparation'], job['request']['preparation'])
        self.assertEqual(retry['request']['inputs'][0]['sha256'], job['request']['inputs'][0]['sha256'])

    def test_record_and_queued_snapshot_changes_block(self):
        self.image_route()
        _, request = self.save()
        job = asset_workflow.new_job(self.root, 'tripo', request, self.settings)
        (self.root / job['request']['inputs'][0]['snapshot']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Queued'):
            prep.verify_request(self.root, 'tripo', job['request'], self.settings)
        (self.root / request['preparation']['path']).write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'record'):
            prep.verify_request(self.root, 'tripo', request, self.settings)

    def test_reference_preparation_snapshot_change_blocks(self):
        self.image_route()
        _, request = self.save()
        (self.root / request['inputs'][0]['snapshot']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            prep.verify_request(self.root, 'tripo', request, self.settings)

    def test_no_overwrite_or_path_escape(self):
        self.save()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.save()
        with self.assertRaises(ValueError):
            prep.prepare(self.root, 'spec.json', 'plan.json', '../escape')
        self.spec['references'].append({'id': 'escape', 'path': '../escape.png', 'role': 'shape'})
        with self.assertRaises(ValueError):
            self.compile()

    def test_cli_prepare_check_and_submit_without_credentials(self):
        self.save()
        from contextlib import redirect_stdout
        for function, args in [
            (asset_prepare.main, ['check', '--request', 'prepared/request.json']),
            (asset_workflow.main, ['submit', '--provider', 'tripo', '--request', 'prepared/request.json'])]:
            with self.subTest(function=function.__module__), redirect_stdout(io.StringIO()) as out:
                with patch.object(credential_store, 'get', side_effect=AssertionError('Credential access')), \
                     patch.object(api_common, 'credential', side_effect=AssertionError('Credential access')), \
                     patch('socket.socket.connect', side_effect=AssertionError('Network access')):
                    code = function(['--project', str(self.root), *args])
                self.assertEqual(code, 0, out.getvalue())

    def test_preview_equals_tripo_wire_body_with_token_substitution(self):
        self.image_route(mode='multiview_to_model')
        self.reference('back', (1, 2, 3), 'back')
        record = self.compile()
        expected = deepcopy(record['preview']['body'])
        for item in expected['inputs']:
            for view in item:
                item[view] = view + '-token'
        with patch.object(api_common, 'credential', return_value='fixture'):
            client = tripo.Client({})
        request = prep.absolute_request(self.root, record['request'])
        with patch.object(client, 'upload_image', side_effect=['front-token', 'back-token']), \
             patch.object(client, 'call', return_value={'task_id': 'fixture-task'}) as call:
            client.submit(request)
        self.assertEqual(call.call_args.args[1], expected)

    def test_approval_binds_preparation_without_issuing_receipt(self):
        _, request = self.save()
        with patch.object(api_common, 'credential', return_value='synthetic-fixture'):
            with_preparation = generation_approval.identity(self.root, 'fixture-job', 'tripo', self.settings, request)
            changed = deepcopy(request)
            changed.pop('preparation')
            without_preparation = generation_approval.identity(self.root, 'fixture-job', 'tripo', self.settings, changed)
        self.assertNotEqual(with_preparation, without_preparation)

    def test_preparation_is_retained_in_version_provenance(self):
        from workbench import asset_versions
        _, request = self.save()
        job = asset_workflow.new_job(self.root, 'tripo', request, self.settings)
        target = self.root / 'crate.obj'
        target.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n', encoding='utf-8')
        job.update(status='registered', artifacts=[{'path': 'crate.obj', 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                                                   'bytes': target.stat().st_size}])
        result = asset_versions.complete_job(self.root, job)
        _, version = asset_versions.version(asset_versions.load(self.root), result['group'], result['version'])
        self.assertEqual(version['provenance']['preparation'], request['preparation'])


if __name__ == '__main__':
    unittest.main()
