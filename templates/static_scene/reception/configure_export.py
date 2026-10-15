from pathlib import Path
import os,json
W=Path(__file__).parent;settings=json.loads(Path(os.environ['OAGD_ENGINE_CONFIG']).read_text())
(W/'packages/Godot').mkdir(parents=True,exist_ok=True)
(W/'Godot/export_presets.cfg').write_text('[preset.0]\nname="Windows"\nplatform="Windows Desktop"\nrunnable=true\nexport_filter="all_resources"\ninclude_filter="case.json"\nexclude_filter="baseline.gd,prepare.gd,rollback.gd,*report.json,revisions/*"\nscript_export_mode=2\n[preset.0.options]\ncustom_template/debug="'+settings['godot_template']+'"\ndebug/export_console_wrapper=0\nbinary_format/embed_pck=false\ntexture_format/s3tc_bptc=true\nbinary_format/architecture="x86_64"\ncodesign/enable=false\napplication/modify_resources=false\n')
