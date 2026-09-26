import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import check_camera_connections as bridge
import check_static_floor_bridge as floor


def pose(c):
    c=np.asarray(c,float)
    return dict(center=c.tolist(),R=np.eye(3).tolist(),t=(-c).tolist(),
                K=[[800.,0,540],[0,800.,960],[0,0,1]],dist=[0.,0.,0.,0.],component='one')


def case(post_component='one',shift=0):
    frames=[dict(name=str(i),timestamp=i*.1) for i in range(60)]
    ref={f['name']:pose([i*.03,0,0]) for i,f in enumerate(frames) if i<20 or i>=40}
    for i in range(40,60):ref[str(i)]['component']=post_component
    nn={f['name']:pose([i*.03+(shift if i>=40 else 0),0,0]) for i,f in enumerate(frames)}
    return dict(id='synthetic',loss_time=2,gap_end=4,end=6,frames=frames,methods=dict(colmap=ref,da3=nn,vggt=nn))


class ConnectionTests(unittest.TestCase):
    def test_missing_return_blocks(self):
        c=case();c['frames']=c['frames'][:40]
        self.assertEqual(bridge.analyze_case(c)['status'],'blocked')

    def test_perfect_camera_fit_does_not_certify_connection(self):
        r=bridge.analyze_case(case())
        self.assertEqual(r['status'],'unverified');self.assertFalse(r['accepted_connection'])
        for row in r['methods'].values():
            self.assertFalse(set(row['before']['fit_names'])&set(row['before']['withheld_names']))
            self.assertFalse(row['accepted_connection'])

    def test_post_gap_drift_rejected_without_refitting_it_away(self):
        r=bridge.analyze_case(case(shift=2))
        self.assertEqual(r['status'],'rejected')
        self.assertGreater(r['methods']['da3']['pre_fit_predicts_post']['position_percent_span'],100)

    def test_component_gauges_are_not_compared_as_same_world(self):
        r=bridge.analyze_case(case(post_component='other',shift=2))
        self.assertEqual(r['status'],'unverified')
        self.assertNotIn('pre_fit_predicts_post',r['methods']['da3'])

    def test_similarity_composition(self):
        theta=.3;q=np.array([[np.cos(theta),0,np.sin(theta)],[0,1,0],[-np.sin(theta),0,np.cos(theta)]])
        a=dict(scale=2.,rotation=q,offset=np.array([1,2,3.]));b=dict(scale=3.,rotation=q.T,offset=np.array([-2,1,5.]))
        h=bridge.compose_bridge(a,b);x=np.array([.3,.5,.7]);post=b['scale']*b['rotation']@x+b['offset']
        actual=h['scale']*np.asarray(h['rotation'])@post+h['offset']
        np.testing.assert_allclose(actual,a['scale']*q@x+a['offset'],atol=1e-10)

    def test_static_triangulation_and_skew_projection(self):
        a,b=pose([0,0,0]),pose([.4,0,0]);xyz=np.array([[.1,.2,3],[.5,-.3,4],[-.2,.1,2]],float)
        x,_=floor.project(xyz,a);y,_=floor.project(xyz,b)
        found,keep,_=floor.triangulate(x,y,a,b)
        self.assertTrue(keep.all());np.testing.assert_allclose(found,xyz,atol=1e-9)
        a['K'][0][1]=200;uv,_=floor.project(xyz,a)
        expected=xyz@np.asarray(a['K']).T
        np.testing.assert_allclose(uv,expected[:,:2]/expected[:,2,None])

    def test_withheld_landmarks_reject_wrong_pose_and_sparse_support(self):
        rng=np.random.default_rng(7);xyz=rng.uniform(-1,1,(100,3));xyz[:,2]+=5
        p=pose([.2,.1,.05]);xy,_=floor.project(xyz,p);ids=np.arange(len(xyz))
        self.assertTrue(floor.localize(xyz,xy,ids,p)['passed'])
        bad=xy.copy();bad[ids%5==0]+=[100,0]
        self.assertFalse(floor.localize(xyz,bad,ids,p)['passed'])
        self.assertFalse(floor.localize(xyz[:8],xy[:8],ids[:8],p)['passed'])


if __name__=='__main__':unittest.main()
