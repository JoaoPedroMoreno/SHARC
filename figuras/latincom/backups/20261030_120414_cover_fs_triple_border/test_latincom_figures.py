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
        for dx in cover.COVER_PANEL_OFFSETS:
            affine=style.original.fit_map(regional,(dx+.35,1.5,dx+7.65,7),vertical_scale=.8)
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
        self.assertNotIn('Wanted FS link',[a.get_text() for a in fig.axes[0].texts])
        rx,tx=fig.axes[0]._fs_antenna_geometry
        self.assertEqual(rx['facing'],'north')
        self.assertEqual(tx['facing'],'south')
        delta=tx['phase_center']-rx['phase_center']
        north=rx['boresight']
        self.assertGreater(np.dot(delta,north),0)
        # Blender exports projected anchors at single-precision accuracy.
        self.assertAlmostEqual(delta[0]*north[1]-delta[1]*north[0],0,places=6)
        np.testing.assert_allclose(tx['boresight'],-north)
        ground=Affine2D().scale(.92,.40).skew_deg(8,0).translate(59,11)
        np.testing.assert_allclose(rx['base'],ground.transform((-11.5,0)))
        np.testing.assert_allclose(tx['base'],ground.transform((-11.5,36)))
        self.assertGreater(tx['base'][1],ground.transform((-11.5,27))[1])

    def test_open_parabola_and_horizontal_feed_axis(self):
        fig,ax=plt.subplots()
        style.receiver(ax,0,0,1)
        model=ax._fs_antenna_geometry[0]
        self.assertFalse(model['radome'])
        np.testing.assert_array_equal(model['boresight_3d'],[0,1,0])
        self.assertEqual(model['feed_focus'][2],model['vertex'][2])
        self.assertAlmostEqual(np.linalg.norm(model['feed_focus']-model['vertex']),
                               model['focal_length'])
        self.assertTrue(model['approved_blender_model'])
        sprites=[a for a in ax.images if a.get_gid()=='fs-dish:approved-blender-model']
        self.assertEqual(len(sprites),1)
        self.assertEqual(sprites[0].get_array().shape[2],4)
        self.assertIn('antenna_proposal_v2',antenna.manifest()['source_model'])

    def test_fs_labels_share_the_same_antenna_relative_position(self):
        fig=perspective.context()
        ax=fig.axes[0]
        for model,text in zip(ax._fs_antenna_geometry,
                              ('Victim FS receiver','FS transmitter')):
            captions=[a for a in ax.texts if a.get_gid()=='fs-label:'+text]
            self.assertEqual(len(captions),1)
            caption=captions[0]
            np.testing.assert_allclose(np.asarray(caption.get_position())-model['base'],
                                       [0,-2.5])
            self.assertEqual(caption.get_ha(),'center')
            self.assertEqual(caption.get_va(),'center')
            self.assertEqual(caption.get_fontsize(),17)

    def test_rendered_boresights_match_ground_north(self):
        for model in antenna.manifest()['views'].values():
            start=np.asarray(model['anchors_px']['vertex'])
            end=np.asarray(model['anchors_px']['focus'])
            axis=(end-start)*[1,-1]
            self.assertAlmostEqual(axis[0]/axis[1],model['north_ratio'],places=6)
            self.assertGreater(axis[1]*model['sign'],0)
            self.assertEqual(model['boresight_3d'][2],0)

    def test_cover_bounds_contain_rendered_model(self):
        xmin,ymin,xmax,ymax=antenna.SYMBOL_BOUNDS
        for name in ('map_north','perspective_north'):
            _,extent,_,_=antenna.asset(name)
            self.assertGreater(extent[0],xmin)
            self.assertLess(extent[1],xmax)
            self.assertGreater(extent[2],ymin)
            self.assertLess(extent[3],ymax)

    def test_antenna_uses_original_satellite_style(self):
        visual=antenna.manifest()['visual_style']
        self.assertIn('satellite_from_paper.blend',visual['source'])
        self.assertTrue(visual['geometry_unchanged'])
        self.assertEqual(visual['materials'],['Satellite body','Satellite dark'])

    def test_methodology_is_visual_and_schematic(self):
        fig=figures.methodology.figure()
        ax=fig.axes[0]
        words=' '.join(a.get_text() for a in ax.texts).split()
        self.assertLess(len(words),110)
        self.assertEqual(len(ax._fs_antenna_geometry),5)
        self.assertTrue(fig._latincom_validation['ccdf_is_illustrative'])
        self.assertEqual(fig._latincom_validation['snapshots_per_method'],2)
        labels=[a.get_text() for a in ax.texts]
        self.assertEqual(labels.count('Snapshot 1'),2)
        self.assertEqual(labels.count('Snapshot 10 000'),2)
        self.assertEqual(labels.count(r'$\cdots$'),2)
        self.assertNotIn('Snapshot 2',labels)
        self.assertNotIn('Protection margin',labels)
        self.assertFalse(any('M_{20}' in value for value in labels))

    def test_compact_cover_has_explicit_cell_legend(self):
        fig=cover.cover()
        ax=fig.axes[0]
        labels=[a.get_text() for a in ax.texts]
        for expected in ('Nominal-power cell','10 dB back-off','Excluded cell',
                         'Shown beam footprint','Victim FS (Paraguay)'):
            self.assertIn(expected,labels)
        self.assertNotIn('Victim FS',labels)
        self.assertNotIn('Paraguay',labels)
        self.assertEqual(fig._latincom_validation['point_callout_leaders'],0)
        self.assertLess(fig._latincom_validation['panel_center_separation'],8)
        self.assertGreater(fig._latincom_validation['map_height'],5.05)
        legend_dish=ax._fs_antenna_geometry[-1]
        self.assertGreater(legend_dish['render_extent'][0][1],.03)


if __name__=='__main__':
    unittest.main(verbosity=2)
