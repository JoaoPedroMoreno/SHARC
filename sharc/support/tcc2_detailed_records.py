"""Lossless, snapshot-local deltas for TCC2 detailed CSV records.

Values use the same string representation as csv.DictWriter, including empty
None and nan. The decoder reconstructs every original row at every step.
Only serialization changes; this module never accesses simulation state/RNG.
"""
import argparse
import csv
import gzip
import hashlib
from itertools import groupby
import json
from pathlib import Path

FORMAT = "tcc2-row-delta-v1"
COMMON = ("snapshot_id", "secondary_seed", "step")


def csv_value(value):
    return "" if value is None else str(value)


class DeltaWriter:
    def __init__(self, path):
        self.path = Path(path)
        self.columns = None
        self.state = None
        self.snapshot = None
        self.step = None
        if self.path.exists():
            with gzip.open(self.path, "rt", encoding="utf-8") as stream:
                header = json.loads(next(stream))
            if header.get("format") != FORMAT:
                raise ValueError("Unexpected detailed-record format")
            self.columns = header["columns"]

    def write(self, rows):
        if not rows:
            return
        columns = list(rows[0])
        if self.columns is not None and columns != self.columns:
            raise ValueError("Detailed record schema changed")
        if any(key not in columns for key in COMMON):
            raise ValueError("Missing snapshot/seed/step keys")
        common = {key: csv_value(rows[0][key]) for key in COMMON}
        fields = [key for key in columns if key not in COMMON]
        state = []
        for row in rows:
            if list(row) != columns or any(csv_value(row[key]) != common[key] for key in COMMON):
                raise ValueError("Mixed schema or steps in one frame")
            state.append([csv_value(row[key]) for key in fields])
        snapshot = common["snapshot_id"], common["secondary_seed"]
        step = int(common["step"])
        if self.snapshot == snapshot and self.step is not None and step <= self.step:
            raise ValueError("Non-increasing detailed-record step")
        reset = self.state is None or self.snapshot != snapshot or len(self.state) != len(state)
        frame = dict(common=common, reset=reset, count=len(state))
        if reset:
            frame["rows"] = state
        else:
            updates = []
            for index, (old, new) in enumerate(zip(self.state, state)):
                changes = [[j, b] for j, (a, b) in enumerate(zip(old, new)) if a != b]
                if changes:
                    updates.append([index, changes])
            frame["updates"] = updates
        with gzip.open(self.path, "at", encoding="utf-8", newline="") as stream:
            if self.columns is None:
                stream.write(json.dumps(dict(format=FORMAT, columns=columns), separators=(",", ":")) + "\n")
            stream.write(json.dumps(frame, separators=(",", ":")) + "\n")
        self.columns, self.state, self.snapshot, self.step = columns, state, snapshot, step


def read_delta_rows(path):
    """Yield original CSV-compatible row dictionaries, including unchanged rows."""
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        header = json.loads(next(stream))
        if header.get("format") != FORMAT:
            raise ValueError("Unexpected detailed-record format")
        columns = header["columns"]
        fields = [key for key in columns if key not in COMMON]
        state = None
        previous_snapshot = None
        previous_step = None
        for line in stream:
            frame = json.loads(line)
            common = frame["common"]
            snapshot = common["snapshot_id"], common["secondary_seed"]
            step = int(common["step"])
            if snapshot == previous_snapshot and previous_step is not None and step <= previous_step:
                raise ValueError("Non-increasing detailed-record step")
            if frame["reset"]:
                state = frame["rows"]
                if len(state) != frame["count"] or any(len(row) != len(fields) for row in state):
                    raise ValueError("Invalid full frame")
            else:
                if state is None or snapshot != previous_snapshot or len(state) != frame["count"]:
                    raise ValueError("Delta without its snapshot base")
                for index, changes in frame["updates"]:
                    if not 0 <= index < len(state):
                        raise ValueError("Invalid delta row")
                    for column, value in changes:
                        if not 0 <= column < len(fields):
                            raise ValueError("Invalid delta column")
                        state[index][column] = value
            for values in state:
                row = dict(zip(fields, values))
                row.update(common)
                yield {key: row[key] for key in columns}
            previous_snapshot, previous_step = snapshot, step


def read_detailed_rows(folder, dataset):
    """Read full CSV or delta records; never silently choose between duplicates."""
    if dataset not in {"links", "users"}:
        raise ValueError("Expected links or users")
    folder = Path(folder)
    csv_path = folder / f"tcc2_{dataset}.csv.gz"
    delta_path = folder / f"tcc2_{dataset}.delta.jsonl.gz"
    if csv_path.exists() and delta_path.exists():
        raise ValueError("Both full and delta records exist; select an explicit reader")
    if delta_path.exists():
        yield from read_delta_rows(delta_path)
    else:
        with gzip.open(csv_path, "rt", encoding="utf-8", newline="") as stream:
            yield from csv.DictReader(stream)


def convert_csv_to_delta(source, destination):
    """Create and round-trip verify a separate archive; NEVER delete the source.

    Requires a stable, closed source. A changing/incomplete stream is rejected.
    On failure, a .partial archive is left for inspection, never published.
    """
    source, destination = Path(source), Path(destination)
    temporary = destination.with_name(destination.name + ".partial")
    if source.resolve() == destination.resolve() or destination.exists() or temporary.exists():
        raise FileExistsError("Destination must be new and distinct from the source")
    before = source.stat()
    original = hashlib.sha256()
    count = 0
    writer = DeltaWriter(temporary)
    with gzip.open(source, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for _, group in groupby(reader, key=lambda row: tuple(row[k] for k in COMMON)):
            rows = list(group)
            for row in rows:
                original.update(json.dumps(row, separators=(",", ":")).encode("utf-8") + b"\n")
                count += 1
            writer.write(rows)
    reconstructed = hashlib.sha256()
    decoded = 0
    for row in read_delta_rows(temporary):
        reconstructed.update(json.dumps(row, separators=(",", ":")).encode("utf-8") + b"\n")
        decoded += 1
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("Source changed during conversion; do not convert active outputs")
    if count != decoded or original.digest() != reconstructed.digest():
        raise AssertionError("Detailed-record reconstruction is not lossless")
    temporary.rename(destination)
    return dict(rows=count, sha256=original.hexdigest(), original_bytes=before.st_size,
                delta_bytes=destination.stat().st_size, source_preserved=source.exists())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a closed detailed CSV to a verified separate delta archive; source is preserved")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(convert_csv_to_delta(args.source, args.destination), indent=2))
