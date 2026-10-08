"""Purpose classification, file preservation and authenticated board persistence."""
import json
import sys
import subprocess
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from workbench import asset_taxonomy as taxonomy, asset_browser as browser, art_registry
import test_project_workbench as workbench_tests


class TaxonomyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def file(self,path,data=b'fixture'):
        target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)

    def test_scan_classifies_formats_directories_and_keeps_ambiguous_resources(self):
        for name in ('Characters/Hero.fbx','Weapons/Sword.fbx','Props/Crate.obj','Maps/Arena.umap',
                     'Animations/Swing.anim','VFX/Hit.vfx','Characters/Textures/Hero.dds',
                     'Music/Combat.ogg','SFX/Impact.wav','Voices/Boss.wav','UI/Icon.svg',
                     'Plugins/Weapon/Weapon.uplugin','Templates/Dodge.prefab','Misc/Unknown.uasset',
                     'Archviz/Materials/Wall.png'):
            self.file(name)
        result=browser.scan(self.root);rows={a['path']:a for a in result['assets']}
        expected={'Characters/Hero.fbx':'character','Weapons/Sword.fbx':'weapon','Props/Crate.obj':'prop',
                  'Maps/Arena.umap':'environment','Animations/Swing.anim':'animation','VFX/Hit.vfx':'vfx',
                  'Characters/Textures/Hero.dds':'material','UI/Icon.svg':'ui',
                  'Plugins/Weapon/Weapon.uplugin':'code','Templates/Dodge.prefab':'template','Misc/Unknown.uasset':'unclassified'}
        for name,category in expected.items():self.assertEqual(rows[name]['classification']['category'],category,name)
        for name,kind in [('Music/Combat.ogg','music'),('SFX/Impact.wav','sfx'),('Voices/Boss.wav','speech')]:
            self.assertEqual(rows[name]['classification']['audioKind'],kind)
        self.assertEqual(rows['Archviz/Materials/Wall.png']['classification']['topics'],['archviz'])
        self.assertFalse((self.root/'.openaigame/asset-taxonomy.json').exists(),'Scanning must not write')

    def test_manual_overrides_persist_on_refresh_without_moving_files_or_tags(self):
        self.file('game/Unknown.fbx');rows=browser.scan(self.root)['assets']
        payload={'paths':['game/Unknown.fbx'],'revision':taxonomy.load(self.root)[1],
                 'classification':{'category':'weapon','topics':['archviz']}}
        taxonomy.save(self.root,payload,rows)
        row=browser.scan(self.root)['assets'][0]
        self.assertEqual(row['classification']['category'],'weapon');self.assertTrue(row['classification']['manual'])
        self.assertEqual(row['kind'],'model');self.assertEqual(row['location'],'game')
        self.assertEqual(row['tags'],[]);self.assertEqual((self.root/'game/Unknown.fbx').read_bytes(),b'fixture')
        self.assertFalse((self.root/'Art Direction.md').exists())
        with self.assertRaises(art_registry.RevisionConflict):taxonomy.save(self.root,payload,rows)
        payload.update(revision=taxonomy.load(self.root)[1],action='reset')
        taxonomy.save(self.root,payload,rows)
        self.assertEqual(browser.scan(self.root)['assets'][0]['classification']['category'],'unclassified')

    def test_invalid_batch_and_corrupt_store_do_not_overwrite(self):
        self.file('A.obj');rows=browser.scan(self.root)['assets'];revision=taxonomy.load(self.root)[1]
        for paths,value in [(['../escape'],{'category':'prop'}),(['A.obj','missing.obj'],{'category':'prop'}),
                            (['A.obj'],{'category':'prop','audioKind':'music'}),(['A.obj'],{'category':[]})]:
            with self.assertRaises(ValueError):taxonomy.save(self.root,{'paths':paths,'classification':value,'revision':revision},rows)
        self.assertFalse((self.root/'.openaigame/asset-taxonomy.json').exists())
        self.file('.openaigame/asset-taxonomy.json',b'{broken')
        self.assertTrue(browser.scan(self.root)['taxonomy']['error'])
        with self.assertRaises(ValueError):taxonomy.save(self.root,{'paths':['A.obj'],'classification':{'category':'prop'},'revision':revision},rows)
        self.assertEqual((self.root/'.openaigame/asset-taxonomy.json').read_bytes(),b'{broken')

    def test_engine_metadata_and_actual_binding_do_not_assume_every_fbx_is_a_character(self):
        plain={'path':'mystery.fbx','kind':'model','ext':'FBX'}
        self.assertEqual(taxonomy.classify(plain,{},[])['category'],'unclassified')
        bindings=[{'model':'mystery.fbx','actions':[{'path':'swing.fbx'}]}]
        self.assertEqual(taxonomy.classify(plain,{},bindings)['category'],'character')
        self.assertEqual(taxonomy.classify({**plain,'path':'swing.fbx'},{},bindings)['category'],'animation')
        self.assertEqual(taxonomy.classify({'path':'asset.uasset','kind':'engine','ext':'UASSET','assetClass':'NiagaraSystem'},{},[])['category'],'vfx')
        self.assertEqual(taxonomy.classify({'path':'asset.uasset','kind':'engine','ext':'UASSET','assetClass':'Blueprint'},{},[])['category'],'unclassified')

    def assign(self, path, category='weapon'):
        snapshot=browser.scan(self.root)
        taxonomy.save(self.root,{'paths':[path],'revision':snapshot['taxonomy']['revision'],
                                'classification':{'category':category}},snapshot['assets'])

    def test_replaced_file_does_not_inherit_saved_category_and_stale_save_is_atomic(self):
        self.file('A.fbx');self.file('B.fbx',b'other');self.assign('A.fbx')
        before=browser.scan(self.root);stored=(self.root/'.openaigame/asset-taxonomy.json').read_bytes()
        self.file('A.fbx',b'a replacement asset')
        after=browser.scan(self.root);row=next(a for a in after['assets'] if a['path']=='A.fbx')
        self.assertEqual(row['classification']['category'],'unclassified')
        self.assertEqual(row['classification']['previousCategory'],'weapon')
        self.assertTrue(row['classification']['needsReview'])
        with self.assertRaises(art_registry.RevisionConflict):
            taxonomy.save(self.root,{'paths':['B.fbx','A.fbx'],'revision':before['taxonomy']['revision'],
                'classification':{'category':'character'},
                'versions':{a['path']:a['classification']['version'] for a in before['assets']}},after['assets'])
        self.assertEqual((self.root/'.openaigame/asset-taxonomy.json').read_bytes(),stored)
        self.assign('A.fbx','prop')
        self.assertFalse(next(a for a in browser.scan(self.root)['assets'] if a['path']=='A.fbx')['classification']['needsReview'])

    def test_unique_move_can_be_confirmed_without_changing_range_or_source_file(self):
        self.file('Sword.fbx');self.assign('Sword.fbx')
        (self.root/'game').mkdir();(self.root/'Sword.fbx').rename(self.root/'game/Sword.fbx')
        snapshot=browser.scan(self.root);row=snapshot['assets'][0]
        self.assertEqual(row['classification']['previousPath'],'Sword.fbx')
        self.assertEqual(row['location'],'game');self.assertFalse(row['classification']['manual'])
        taxonomy.save(self.root,{'paths':['game/Sword.fbx'],'previousPath':'Sword.fbx','revision':snapshot['taxonomy']['revision'],
            'classification':{'category':'weapon'}},snapshot['assets'])
        assignments,_=taxonomy.load(self.root)
        self.assertNotIn('Sword.fbx',assignments);self.assertIn('game/Sword.fbx',assignments)
        self.assertEqual((self.root/'game/Sword.fbx').read_bytes(),b'fixture')

    def test_duplicate_hashes_are_not_automatically_treated_as_a_move(self):
        self.file('Sword.fbx');self.assign('Sword.fbx');(self.root/'Sword.fbx').rename(self.root/'A.fbx')
        self.file('B.fbx')
        snapshot=browser.scan(self.root)
        self.assertTrue(all('previousPath' not in a['classification'] for a in snapshot['assets']))
        self.assertEqual(snapshot['taxonomy']['missingRecords'],['Sword.fbx'])

    def test_legacy_categories_are_read_only_until_checked_and_keep_topic_data(self):
        self.file('A.fbx')
        legacy={'schemaVersion':1,'assignments':{'A.fbx':{'category':'weapon','audioKind':'','topics':['archviz']}}}
        self.file('.openaigame/asset-taxonomy.json',json.dumps(legacy).encode())
        snapshot=browser.scan(self.root)
        self.assertTrue(snapshot['assets'][0]['classification']['needsReview'])
        self.assertEqual(json.loads((self.root/'.openaigame/asset-taxonomy.json').read_text()),legacy)
        self.assign('A.fbx')
        record=taxonomy.load(self.root)[0]['A.fbx']
        self.assertEqual(record['topics'],['archviz']);self.assertEqual(len(record['sha256']),64)

    def test_pack_directory_does_not_assign_character_category_to_dependency_images(self):
        self.file('Characters/Albedo.png');self.file('Characters/Textures/Normal.png')
        rows={a['path']:a for a in browser.scan(self.root)['assets']}
        self.assertEqual(rows['Characters/Albedo.png']['classification']['category'],'unclassified')
        self.assertEqual(rows['Characters/Textures/Normal.png']['classification']['category'],'material')

    def test_category_changes_preserve_shared_object_tags_and_art_document(self):
        self.file('Hero.fbx');self.file('Hit.wav')
        art_registry.initialize(self.root);snapshot=browser.scan(self.root);registry=art_registry.load(self.root)
        art_registry.register(self.root,registry,snapshot['assets'],['Hero.fbx','Hit.wav'])
        registry['objects']['hero']={'id':'hero','label':'玩家','tags':['主角','冰属性']}
        for record in registry['assets'].values():record['objectId']='hero'
        art_registry.write(self.root,registry,snapshot['artRevision']);before=(self.root/'Art Direction.md').read_bytes()
        self.assign('Hero.fbx','character')
        rows={a['path']:a for a in browser.scan(self.root)['assets']}
        self.assertEqual(rows['Hero.fbx']['tags'],['主角','冰属性'])
        self.assertEqual(rows['Hit.wav']['tags'],['主角','冰属性'])
        self.assertEqual(rows['Hit.wav']['classification']['category'],'audio')
        self.assertEqual((self.root/'Art Direction.md').read_bytes(),before)

    def test_cli_classification_works_without_creating_art_direction(self):
        self.file('Hit.wav')
        command=[sys.executable,'-X','utf8','-B',str(ROOT/'tools/asset_audit.py'),'--project',str(self.root)]
        result=subprocess.run(command+['--classify','audio','--audio-kind','sfx','--paths','Hit.wav'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertEqual(browser.scan(self.root)['assets'][0]['classification']['audioKind'],'sfx')
        self.assertFalse((self.root/'Art Direction.md').exists())
        result=subprocess.run(command+['--reset-classification','--paths','Hit.wav'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertFalse(browser.scan(self.root)['assets'][0]['classification']['manual'])


class TaxonomyHTTPTests(unittest.TestCase):
    # Reuse fixture helpers without collecting the existing suite twice.
    setUp=workbench_tests.WorkbenchTests.setUp
    request=workbench_tests.WorkbenchTests.request
    login=workbench_tests.WorkbenchTests.login
    def test_saved_classification_shared_between_browsers_and_requires_session(self):
        body={'project':'current','paths':['Audio/click.ogg'],'classification':{'category':'audio','audioKind':'sfx','topics':[]},
              'revision':self.request('/api/assets')[2]['taxonomy']['revision']}
        self.assertEqual(self.request('/api/asset-classification',body,auth=False)[0],401)
        self.assertEqual(self.request('/api/asset-classification',body)[0],200)
        self.assertEqual(self.request('/api/asset-classification',body)[0],409)
        self.login();row=next(a for a in self.request('/api/assets')[2]['assets'] if a['path']=='Audio/click.ogg')
        self.assertEqual(row['classification']['audioKind'],'sfx')
        self.assertTrue(row['classification']['manual'])
        wrong={**body,'project':'another'}
        self.assertEqual(self.request('/api/asset-classification',wrong)[0],400)


if __name__=='__main__':unittest.main()
