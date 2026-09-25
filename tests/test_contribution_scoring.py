"""Run with Python + numpy + torch; these checks do not start model training."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from score_splat_contributions import composite_effect, export_candidate, sample_view
from prune_splat_candidates import read_ply


def slow_render(alpha,color):
    # Deliberately independent back-to-front reference compositor.
    out=torch.zeros((alpha.shape[1],3),dtype=alpha.dtype)
    for i in range(len(alpha)-1,-1,-1):
        out=alpha[i,:,None]*color[i]+(1-alpha[i,:,None])*out
    return out


class ContributionTests(unittest.TestCase):
    def test_masked_rgb_cannot_influence_verification(self):
        model=(torch.tensor([[0.,0.,2.]]),torch.eye(3)[None]*.08,
               torch.tensor([[.5,.5,.5]]),torch.zeros((1,15,3)),torch.tensor([.8]))
        view={'name':'test','position':[0,0,0],'target':[0,0,2],'up':[0,1,0],'fov':60}
        regions=[{'image':'test','box':[0,0,1,1]}]
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for folder in ['images','masks','a','b']:(root/folder).mkdir()
            mask=np.full((24,24),255,np.uint8);mask[8:16,8:16]=0
            Image.fromarray(mask).save(root/'masks/test.png')
            picture=np.full((24,24,3),100,np.uint8)
            # PNG encoding at this test path avoids JPEG changes outside the mask.
            Image.fromarray(picture).save(root/'images/test.jpg',format='PNG')
            before=sample_view(model,view,root,root/'a',regions)
            picture[mask==0]=255
            Image.fromarray(picture).save(root/'images/test.jpg',format='PNG')
            after=sample_view(model,view,root,root/'b',regions)
            np.testing.assert_array_equal(before,after)
            self.assertGreater(float(before[0,5]),float(before[0,0]))

    def test_counterfactual_includes_revealed_background(self):
        alpha=torch.tensor([[.8,0,.99],[.4,.9,.3],[.7,.2,.6]],dtype=torch.float64)
        color=torch.tensor([[1,0,0],[0,1,0],[.2,.3,1]],dtype=torch.float64)
        target=torch.tensor([[.2,.6,.1],[.1,.4,.2],[.9,.1,.1]],dtype=torch.float64)
        current,weights,gain=composite_effect(alpha,color,target,.5)
        expected=slow_render(alpha,color)
        torch.testing.assert_close(current,expected)
        self.assertTrue(bool((weights.sum(0)<=1).all()))
        for i in range(len(alpha)):
            changed=alpha.clone();changed[i]*=.5
            after=slow_render(changed,color)
            expected_gain=((expected-target).square()-(after-target).square()).mean(-1)
            torch.testing.assert_close(gain[i],expected_gain)

    def test_occluded_splat_has_no_effect(self):
        alpha=torch.tensor([[.999]*2]*5+[[.5,.9]],dtype=torch.float64)
        color=torch.ones((6,3),dtype=torch.float64)
        _,weights,gain=composite_effect(alpha,color,torch.zeros((2,3)),.5)
        self.assertLess(float(weights[-1].max()),1e-14)
        self.assertLess(float(gain[-1].abs().max()),1e-14)

    def test_export_preserves_all_other_fields_and_refuses_overwrite(self):
        names=['x','y','z','opacity','scale_0','scale_1','scale_2','f_dc_0']
        data=np.zeros(4,dtype=[(k,'<f4') for k in names]);data['x']=np.arange(4)
        original=data.tobytes()
        header=[b'ply\n',b'format binary_little_endian 1.0\n',b'element vertex 4\n']
        header += [f'property float {k}\n'.encode() for k in names]+[b'end_header\n']
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'candidate.ply'
            export_candidate(header,data,path,np.array([1]),.5)
            _,result=read_ply(path)
            self.assertAlmostEqual(float(1/(1+np.exp(-result['opacity'][1]))),.25,places=6)
            self.assertEqual(data.tobytes(),original)
            self.assertEqual(result[[0,2,3]].tobytes(),data[[0,2,3]].tobytes())
            with self.assertRaises(FileExistsError):export_candidate(header,data,path,np.array([1]),.5)


if __name__=='__main__':unittest.main()
