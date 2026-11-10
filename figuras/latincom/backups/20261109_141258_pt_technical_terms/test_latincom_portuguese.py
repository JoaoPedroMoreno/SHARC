"""Check the Portuguese export without regenerating its scientific geometry."""
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import generate_latincom_portuguese as translated


class PortugueseFiguresTest(unittest.TestCase):
    def test_every_final_png_has_a_caption_and_is_valid(self):
        images = sorted(translated.OUT.glob('*_pt.png'))
        self.assertEqual(len(images), 10)
        for filename in images:
            with self.subTest(image=filename.name):
                with Image.open(filename) as image:
                    image.verify()
                caption = filename.with_suffix('.txt').read_text(encoding='utf-8')
                self.assertIn('LEGENDA SUGERIDA', caption)
                self.assertIn('Fonte:', caption)

    def test_map_pixels_and_attributions_remain_unchanged(self):
        source = translated.ROOT / 'figuras/latincom/cesium_captures_20261104'
        for name in translated.MAP_CAPTIONS:
            before = np.asarray(Image.open(source / f'{name}.png').convert('RGB'))
            after = np.asarray(Image.open(translated.OUT / f'{name}_pt.png').convert('RGB'))
            self.assertEqual(before.shape, after.shape)
            changed = np.any(before != after, axis=2)
            allowed = np.zeros(changed.shape, dtype=bool)
            allowed[:112, :] = True
            allowed[1283:1722, 2339:3162] = True
            self.assertFalse(np.any(changed & ~allowed), name)
            self.assertTrue(np.any(changed), name)
            np.testing.assert_array_equal(before[1760:], after[1760:])

    def test_localization_keeps_geometry_and_technical_values(self):
        fig = translated.methodology.figure()
        ax = fig.axes[0]
        paths = [patch.get_path().vertices.copy() for patch in ax.patches]
        lines = [line.get_xydata().copy() for line in ax.lines]
        translated.localize(fig)
        for expected, patch in zip(paths, ax.patches):
            np.testing.assert_array_equal(expected, patch.get_path().vertices)
        for expected, line in zip(lines, ax.lines):
            np.testing.assert_array_equal(expected, line.get_xydata())
        values = [text.get_text() for text in ax.texts]
        self.assertIn('340 / 525 km', values)
        self.assertIn('LF 20 / 50%', values)
        self.assertIn('Snapshot 10 000', values)
        self.assertIn('20 / 40 m', values)
        plt.close(fig)

    def test_unknown_text_cannot_silently_remain_in_english(self):
        fig, ax = plt.subplots()
        ax.text(.5, .5, 'Untranslated new label')
        with self.assertRaisesRegex(ValueError, 'Unmapped labels'):
            translated.localize(fig)
        plt.close(fig)


if __name__ == '__main__':
    unittest.main()
