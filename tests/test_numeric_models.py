from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import numeric_models as model
from record_io import write_json

class Models(unittest.TestCase):
    def test_threshold_boundary_and_piecewise_interpolation(self):
        points=[[0,12],[1,30]]
        self.assertEqual(model.calculate({'kind':'piecewise_linear','points':points},.5,{}),21)
        self.assertEqual(model.calculate({'kind':'step','points':points},.99,{}),12)
        self.assertEqual(model.calculate({'kind':'step','points':points},1,{}),30)
        with self.assertRaises(ValueError):model.calculate({'kind':'step','points':points},2,{})
    def test_explicit_formula_with_discrete_hit_threshold(self):
        formula={'op':'divide','args':[{'op':'subtract','args':[{'op':'ceil','args':[{'op':'divide','args':['hp','damage']}]},1]},'rate']}
        self.assertEqual(model.expression(formula,0,{'hp':100,'damage':34,'rate':2}),1)
        self.assertEqual(model.expression(formula,0,{'hp':100,'damage':33,'rate':2}),1.5)
        with self.assertRaises(ValueError):model.expression({'op':'eval','args':['__import__']},0,{})
    def test_source_pointer_measured_delta_and_stale_detection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_json(root/'native.json',{'keys':[[0,12],[1,30]],'value':22})
            write_json(root/'run.json',{'status':'completed'})
            spec={'schema_version':1,'id':'curve','title':'Measured curve','object':'player','input_unit':'normalized charge','output_unit':'HP','basis':'Synthetic regression fixture, not runtime proof','conditions':['test'],
                'inputs':[0,.5,1],'model':{'kind':'piecewise_linear','points_source':{'file':'native.json','pointer':'/keys'}},
                'measurements':[{'x':.5,'y':{'file':'native.json','pointer':'/value'},'basis':'runtime','execution_ref':'run.json','conditions':'synthetic unit test'}]}
            write_json(root/'request.json',spec)
            result=model.evaluate(root,'request.json','report.json')
            self.assertEqual(result['measurements'][0]['difference'],1)
            self.assertTrue((root/'report.html').is_file())
            write_json(root/'native.json',{'keys':[[0,12],[1,40]],'value':22})
            self.assertEqual(model.assess(root,'report.json')['status'],'stale')
    def test_nonfinite_division_and_reversed_inputs_rejected(self):
        for fn in [lambda:model.number(True),lambda:model.number(float('nan')),
            lambda:model.expression({'op':'divide','args':[1,0]},0,{}),
            lambda:model.calculate({'kind':'step','points':[[1,1],[0,2]]},.5,{})]:
            with self.assertRaises(ValueError):fn()

if __name__=='__main__':unittest.main()
