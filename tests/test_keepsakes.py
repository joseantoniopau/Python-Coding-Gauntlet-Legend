import unittest
from gauntlet import keepsakes


class KeepsakeTests(unittest.TestCase):
    def test_assistance_and_legacy_do_not_unlock_independent_colors(self):
        for kind in (None, 'unknown', 'scaffolded', 'reading', 'puzzle'):
            r={'solved':True,'mode':'adventure','evidence_kind':kind}
            self.assertFalse(keepsakes.view({},[r])['options'][1]['unlocked'])
        r.update(evidence_kind='whole_function',hints_used=1)
        self.assertFalse(keepsakes.view({},[r])['options'][1]['unlocked'])

    def test_reviews_need_distinct_problems_and_persist_only_a_color_choice(self):
        base={'solved':True,'hints_used':0,'mode':'adventure','evidence_kind':'whole_function','is_retest':True}
        rows=[dict(base,problem_id='one') for _ in range(4)]
        self.assertFalse(keepsakes.view({},rows)['options'][2]['unlocked'])
        rows=[dict(base,problem_id=str(i)) for i in range(3)]
        state={'player':{'xp':25}}
        result=keepsakes.select(state,rows,'indigo')
        self.assertEqual(result['selected'],'indigo')
        self.assertEqual(state,{'player':{'xp':25},'appearance':{'selected':'indigo'}})
        self.assertEqual(set(keepsakes.palette(state,rows)),{'cloak','tunic','trim'})
        self.assertIn('error',keepsakes.select(state,rows,'ember'))

    def test_measured_attempts_do_not_farm_cosmetics(self):
        r={'solved':True,'mode':'interview','evidence_kind':'whole_function'}
        self.assertFalse(keepsakes.view({},[r])['options'][1]['unlocked'])


if __name__=='__main__': unittest.main()
