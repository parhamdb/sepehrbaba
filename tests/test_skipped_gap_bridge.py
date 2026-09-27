import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from evaluate_skipped_gap_bridge import similarity, apply, screen_similarity, unique_groups, verify_cache, view_coverage


class BridgeTests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(11);x=rng.uniform(-1,1,(60,3));x[:,2]=0
        angle=.35;R=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
        return x,apply(x,(2.3,R,np.array([3.,-2.,.7])))

    def groups(self,x,y):
        return [dict(held=i%5==0,observations=[dict(xyz_a=a.tolist(),xyz_b=b.tolist())]) for i,(a,b) in enumerate(zip(x,y))]

    def test_recovers_positive_similarity_from_planar_landmarks(self):
        x,y=self.fixture();r=screen_similarity(self.groups(x,y))
        self.assertTrue(r['screen_passed']);self.assertAlmostEqual(r['scale'],2.3)
        np.testing.assert_allclose(apply(x,(r['scale'],np.array(r['rotation']),np.array(r['translation']))),y,atol=1e-10)

    def test_withheld_mismatch_rejects_correct_training_fit(self):
        x,y=self.fixture();y[::5]=y[::5][::-1]
        self.assertFalse(screen_similarity(self.groups(x,y))['screen_passed'])

    def test_collinear_configuration_rejected(self):
        x=np.c_[np.arange(20),np.zeros((20,2))]
        with self.assertRaises(ValueError):similarity(x,x*2+1)

    def test_conflicting_group_removed_and_repeated_views_share_fold(self):
        rows=[dict(id_a='a',id_b='b'),dict(id_a='a',id_b='b'),dict(id_a='c',id_b='d'),dict(id_a='c',id_b='e')]
        groups,conflicts=unique_groups(rows)
        self.assertEqual(conflicts,1);self.assertEqual(len(groups),1);self.assertEqual(len(groups[0]['observations']),2)

    def test_duplicate_observations_cannot_inflate_landmark_count(self):
        x,y=self.fixture();rows=[]
        for i in range(5):
            rows.extend([dict(id_a=str(i),id_b=str(i),xyz_a=x[i].tolist(),xyz_b=y[i].tolist())]*20)
        groups,_=unique_groups(rows);r=screen_similarity(groups)
        self.assertFalse(r['screen_passed']);self.assertEqual(r['fit_landmarks']+r['withheld_landmarks'],5)

    def test_rejects_running_missing_and_duplicate_pair_inventory(self):
        import copy
        selection=dict(samples=[dict(name=n) for n in 'abc'])
        raw=dict(status='complete-raw-matches-not-verified',frames={n:{} for n in 'abc'},pairs=[dict(a='a',b='b'),dict(a='a',b='c'),dict(a='b',b='c')])
        verify_cache(raw,selection)
        for change in ('running','missing','duplicate'):
            bad=copy.deepcopy(raw)
            if change=='running':bad['status']='running'
            if change=='missing':bad['pairs'].pop()
            if change=='duplicate':bad['pairs'][2]=bad['pairs'][0]
            with self.assertRaises(ValueError):verify_cache(bad,selection)

    def test_coverage_does_not_pool_separate_views(self):
        tiny=np.array([[0,0],[1,0],[0,1]])
        result=view_coverage(dict(first=tiny,second=tiny+[900,1600]))
        self.assertTrue(all(v<.005 for v in result.values()))


if __name__=='__main__':unittest.main()
