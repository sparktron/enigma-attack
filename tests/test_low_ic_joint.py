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
    def test_output_defaults_to_the_artifact_and_honours_regeneration_path(self):
        self.assertEqual(m.parse_arguments([]).output,m.OUTPUT)
        self.assertEqual(m.parse_arguments(['--output','/tmp/x.json']).output,pathlib.Path('/tmp/x.json'))


cf_path = pathlib.Path(__file__).resolve().parents[1] / 'scripts/low_ic_joint_companion_free.py'
cf_spec = importlib.util.spec_from_file_location('low_ic_joint_companion_free', cf_path)
cf = importlib.util.module_from_spec(cf_spec); cf_spec.loader.exec_module(cf)


class CompanionFreeTests(unittest.TestCase):
    def arm(self, detected, retained, confirmed, exact, score):
        return {'detected': detected, 'retained': retained, 'sweep_success': retained and confirmed,
                'plugboard_exact': exact, 'score_per_letter': score}

    def test_companion_free_success_ignores_confirmation_and_stands_out_needs_exact_key(self):
        e, r = cf.E, cf.R
        rows = [
            {'cell': 0, 'arms': {e: self.arm(True, True, False, True, -6.0), r: self.arm(True, True, True, True, -6.0)}},
            {'cell': 0, 'arms': {e: self.arm(False, True, False, False, -7.0), r: self.arm(True, True, True, True, -7.5)}},
        ]
        clean = cf.summarise(rows, ceiling=-7.4)['clean']
        self.assertEqual(clean['arms'][e]['companion_free_success']['count'], 1)
        self.assertEqual(clean['arms'][e]['sweep_success_preregistered']['count'], 0)
        self.assertEqual(clean['arms'][e]['stands_out']['count'], 1)
        self.assertEqual(clean['arms'][r]['stands_out']['count'], 1)
        self.assertEqual(clean['discordant'], {'rngonly_only': 1, 'estecker_only': 0})

    def test_output_defaults_to_the_artifact(self):
        self.assertEqual(cf.parse_arguments([]).output, cf.OUTPUT)
