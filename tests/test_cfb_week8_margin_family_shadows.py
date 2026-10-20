import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from cfb_week8_margin_family_shadows import choose_alpha


def row(i,margin):
    x=[margin+(0.5 if i%2==0 else -0.5),50.0,(i%5)/5,(i%7)/7,(i%4)/4,(i%6)/6,(i%3)/30,(i%8)/8,(i%5)/20,125+(i%8),(i%4)/10,float((i%7)-3),float((i%3)-1)]
    return {'x':x,'margin':float(margin)}


class TestMarginFamilyShadows(unittest.TestCase):
    def test_choose_alpha_returns_valid_candidate(self):
        train=[row(i,((i*3)%19)-9) for i in range(80)]
        valid=[row(i+100,((i*2)%17)-8) for i in range(20)]
        best,cands=choose_alpha(train,valid,(0,2,3,4))
        self.assertIn(best['alpha'],{0.1,1.0,10.0,100.0})
        self.assertEqual(len(cands),4)
        self.assertIsNotNone(best['mae'])


if __name__=='__main__':
    unittest.main()
