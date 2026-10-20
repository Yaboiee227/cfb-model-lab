import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from cfb_feature_family_validation import evaluate, FEATURE_FAMILIES


def make_row(week,i,margin,total):
    x=[
        margin+(0.6 if i%2==0 else -0.6),
        total+(0.7 if i%3==0 else -0.7),
        (i%5)/5,(i%7)/7,(i%4)/4,(i%6)/6,(i%3)/30,(i%8)/8,(i%5)/20,
        124+(i%10),(i%4)/10,float((i%7)-3),float((i%3)-1)
    ]
    return {'weekStart':week,'x':x,'margin':float(margin),'total':float(total)}


class TestFeatureFamilyValidation(unittest.TestCase):
    def test_all_families_are_scored_on_multiple_unseen_folds(self):
        prior=[]
        for w in range(7):
            week=f'2025-09-{1+w*4:02d}T00:00:00Z'
            for i in range(30):
                prior.append(make_row(week,i+w*100,((i*2+w)%21)-10,48+((i+w)%17)))
        current=[]
        weeks=['2026-09-07T00:00:00Z','2026-09-14T00:00:00Z','2026-09-21T00:00:00Z','2026-09-28T00:00:00Z']
        for w,week in enumerate(weeks):
            for i in range(25):
                current.append(make_row(week,i+w*1000,((i*3+w)%23)-11,50+((i+w)%15)))
        out=evaluate(prior,current)
        self.assertGreaterEqual(out['foldCount'],3)
        self.assertEqual(set(out['families']),set(FEATURE_FAMILIES))
        for family,row in out['families'].items():
            self.assertEqual(len(row['folds']),out['foldCount'])
            self.assertIn('marginChallengerEligible',row)
            self.assertIn('totalChallengerEligible',row)


if __name__=='__main__':
    unittest.main()
