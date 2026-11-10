import csv
import gzip
from pathlib import Path
import tempfile
import unittest

from sharc.support.tcc2_detailed_records import (
    DeltaWriter, convert_csv_to_delta, read_delta_rows, read_detailed_rows,
)


class DetailedRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def frames(self):
        frames = []
        for snapshot in (1, 2):
            for step in (0, 1, 2):
                frames.append([
                    dict(snapshot_id=snapshot, secondary_seed=123, step=step,
                         id=i, power=42.8 - (10 if i == 1 and step else 0),
                         sinr=float('nan'), optional=None, label='cell, "A"')
                    for i in range(3)
                ])
        return frames

    def expected(self):
        return [{k: '' if v is None else str(v) for k, v in row.items()}
                for frame in self.frames() for row in frame]

    def test_roundtrip_and_snapshot_writer_recreation(self):
        path = self.folder / 'tcc2_links.delta.jsonl.gz'
        writer = DeltaWriter(path)
        for frame in self.frames():
            if frame[0]['snapshot_id'] == 2 and frame[0]['step'] == 0:
                writer = DeltaWriter(path)
            writer.write(frame)
        self.assertEqual(list(read_delta_rows(path)), self.expected())
        self.assertEqual(list(read_detailed_rows(self.folder, 'links')), self.expected())

    def test_conversion_preserves_source_and_rejects_overwrite(self):
        source = self.folder / 'tcc2_links.csv.gz'
        with gzip.open(source, 'wt', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.frames()[0][0]))
            writer.writeheader()
            for frame in self.frames():
                writer.writerows(frame)
        original = source.read_bytes()
        self.assertEqual(list(read_detailed_rows(self.folder, 'links')), self.expected())
        target = self.folder / 'tcc2_links.delta.jsonl.gz'
        result = convert_csv_to_delta(source, target)
        self.assertEqual(result['rows'], 18)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(list(read_delta_rows(target)), self.expected())
        with self.assertRaises(FileExistsError):
            convert_csv_to_delta(source, target)
        with self.assertRaises(ValueError):
            list(read_detailed_rows(self.folder, 'links'))

    def test_invalid_frame_rejected(self):
        writer = DeltaWriter(self.folder / 'records.gz')
        writer.write(self.frames()[0])
        with self.assertRaises(ValueError):
            writer.write(self.frames()[0])
        frame = self.frames()[1]
        frame[1]['step'] = 4
        with self.assertRaises(ValueError):
            writer.write(frame)

    def test_changed_row_count_resets(self):
        path = self.folder / 'records.gz'
        writer = DeltaWriter(path)
        writer.write(self.frames()[0])
        writer.write(self.frames()[1][:1])
        expected = self.expected()[:3] + self.expected()[3:4]
        self.assertEqual(list(read_delta_rows(path)), expected)


if __name__ == '__main__':
    unittest.main()
