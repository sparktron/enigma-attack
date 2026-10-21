import importlib.util
import pathlib
import unittest
p=pathlib.Path(__file__).resolve().parents[1]/'scripts/low_ic_joint_v1.py'
spec=importlib.util.spec_from_file_location('low_ic_joint',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SummaryTests(unittest.TestCase):
    def test_actual_arm_names_and_paired_gain(self):
        e='complete_w117_estecker';r='complete_w117_rngonly'
        rows=[]
        for i,(eh,rh) in enumerate([(True,True),(False,True),(False,False)]):
            def flags(hit):return dict.fromkeys(('detected','retained','confirmed','sweep_success'),hit)
            rows.append({'cell':0,'draw':i,'plaintext':{'index':i},'arms':{e:flags(eh),r:flags(rh)}})
        s=m.summarise(rows,['clean'],{e:-7.5,r:-7.4})['clean']
        self.assertEqual(s['arms'][e]['sweep_success']['count'],1)
        self.assertEqual(s['arms'][r]['sweep_success']['count'],2)
        self.assertEqual(s['arms'][r]['retained_given_detected']['rate'],1)
        self.assertEqual(s['draws'],3)
