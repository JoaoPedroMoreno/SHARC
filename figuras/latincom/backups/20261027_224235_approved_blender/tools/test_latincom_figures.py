"""Focused checks for the LATINCOM schematic figures, without final rendering."""
import unittest
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.transforms import Affine2D
from shapely.geometry import Polygon
from shapely.ops import unary_union
import latincom_visual_style as style
import latincom_encom_cover as cover
import latincom_perspective as perspective
import generate_latincom_figures as figures
import latincom_fs_antenna as antenna


class LatincomFiguresTest(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def test_reference_panel_geometry_is_preserved(self):
        reference,ax=plt.subplots()
        style.original.local_scene(ax,0,False)
        updated=perspective.context()
        new_ax=updated.axes[0]
        ids={'shared-ground','ground-cell','ground-frontier'}

        def relevant(artist):
            gid=artist.get_gid() or ''
            return gid in ids or gid.startswith(('service-beam:','off-axis:'))

        old=[a for a in ax.get_children() if relevant(a)]
        new=[a for a in new_ax.get_children() if relevant(a)]
        self.assertEqual(len(old),len(new))
        for first,second in zip(old,new):
            self.assertEqual(first.get_gid(),second.get_gid())
            if first.get_gid().startswith('off-axis:'):
                np.testing.assert_array_equal(first.get_array(),second.get_array())
                np.testing.assert_allclose(first.get_extent(),second.get_extent())
            else:
                np.testing.assert_allclose(first.get_path().vertices,second.get_path().vertices)
        self.assertEqual(sum(a.get_gid()=='fs-dish:reflector' for a in new_ax.patches),2)

    def test_complete_cover_symbol_is_inside_paraguay(self):
        countries,regional,_=cover.geography()
        for dx in (0,8):
            affine=style.original.fit_map(regional,(dx+.35,.95,dx+7.65,6),vertical_scale=.8)
            foot,scale,bounds=cover.fs_symbol_placement(countries['Paraguay'],affine)
            country=unary_union([Polygon(affine.transform(np.asarray(p.exterior.coords)))
                                 for p in style.original.polygons(countries['Paraguay'])])
            self.assertTrue(country.covers(bounds))
            xmin,ymin,xmax,ymax=style.FS_SYMBOL_BOUNDS
            self.assertTrue(country.contains(Polygon([
                foot+scale*np.array([xmin,ymin]),foot+scale*np.array([xmax,ymin]),
                foot+scale*np.array([xmax,ymax]),foot+scale*np.array([xmin,ymax])])))

    def test_cover_beam_counts_and_clearance(self):
        fig=cover.cover()
        counts=fig._latincom_validation['cover']
        self.assertEqual([item['service_beams'] for item in counts],[8,9])
        self.assertTrue(all(item['fs_symbol_inside_paraguay'] for item in counts))
        self.assertTrue(all(item['outside_area_m2']<1 for item in counts))
        self.assertTrue(all(a['facing']=='north' and a['boresight'][1]>0
                            for a in fig.axes[0]._fs_antenna_geometry))

    def test_mss_service_link_remains_single_bidirectional_arrow(self):
        fig=figures.architecture('mss')
        links=[a for a in fig.axes[0].texts if a.get_gid()=='mss-service-link-bidirectional']
        self.assertEqual(len(links),1)
        self.assertEqual(links[0].arrowprops['arrowstyle'],'<->')

    def test_both_snapshot_methods_use_directional_fs(self):
        fig,ax=plt.subplots()
        for index,method in enumerate(('ez','pbo')):
            perspective.snapshot(ax,index*4,2,method,0)
        self.assertEqual(sum(a.get_gid()=='fs-dish:reflector' for a in ax.patches),2)
        self.assertTrue(all(a['facing']=='north' and a['boresight'][1]>0
                            for a in ax._fs_antenna_geometry))

    def test_fs_link_follows_ground_north(self):
        fig=perspective.context()
        rx,tx=fig.axes[0]._fs_antenna_geometry
        self.assertEqual(rx['facing'],'north')
        self.assertEqual(tx['facing'],'south')
        delta=tx['phase_center']-rx['phase_center']
        north=rx['boresight']
        self.assertGreater(np.dot(delta,north),0)
        self.assertAlmostEqual(delta[0]*north[1]-delta[1]*north[0],0,places=10)
        np.testing.assert_allclose(tx['boresight'],-north)

    def test_open_parabola_and_horizontal_feed_axis(self):
        fig,ax=plt.subplots()
        style.receiver(ax,0,0,1)
        model=ax._fs_antenna_geometry[0]
        self.assertFalse(model['radome'])
        np.testing.assert_array_equal(model['boresight_3d'],[0,1,0])
        self.assertEqual(model['feed_focus'][2],model['vertex'][2])
        self.assertAlmostEqual(np.linalg.norm(model['feed_focus']-model['vertex']),
                               model['focal_length'])
        names={name for _,_,name in antenna.dish_mesh()}
        self.assertTrue({'mast','mount','feed-arm','feed-horn','horn-mouth','rim'}<=names)
        for vertices,_,name in antenna.dish_mesh():
            if name=='reflector':
                radius_sq=vertices[:,0]**2+(vertices[:,2]-antenna.AXIS_HEIGHT)**2
                np.testing.assert_allclose(vertices[:,1]-antenna.VERTEX_NORTH,
                                           radius_sq/(4*antenna.FOCAL_LENGTH))


if __name__=='__main__':
    unittest.main(verbosity=2)
