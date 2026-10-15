from pathlib import Path
import json,sys,shutil
W=Path(__file__).parent;sys.path.insert(0,str(W/'toolkit/tools'))
import scene_replacement
engine=sys.argv[1];scene_replacement.prepare(W,engine+'/baseline.json','mapping.json',W/'transactions'/engine.lower())
if engine=='Godot':shutil.copy2(W/'transactions/godot/plan.json',W/'Godot/replacement-plan.json')
