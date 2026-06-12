"""Tests for the data collector's pure parts (distance tiers + CSV append).

The OpenCV capture loop needs a camera/models and isn't unit-tested here; the
detection/feature path it uses is the agent's, already covered by the edge tests.
"""

from __future__ import annotations

import csv

from visionmetrics.training.collect import CSV_HEADER, SampleWriter, tier_for


def test_tier_buckets():
    assert tier_for(0.30) == "near <0.5m"
    assert tier_for(0.15) == "mid 0.5-1.5m"
    assert tier_for(0.06) == "far 1.5-3.5m"
    assert tier_for(0.01) == "v-far >3.5m"


def test_writer_creates_file_with_header(tmp_path):
    path = tmp_path / "samples.csv"
    w = SampleWriter(str(path))
    w.add(0.1, -0.2, 0.18, 1, "near <0.5m")
    w.add(0.0, 0.0, 0.05, 0, "far 1.5-3.5m")
    assert w.save() == 2

    rows = list(csv.reader(path.open()))
    assert rows[0] == CSV_HEADER
    assert rows[1] == ["0.1", "-0.2", "0.18", "1"]
    assert len(rows) == 3                      # header + 2


def test_writer_appends_without_duplicating_header(tmp_path):
    path = tmp_path / "samples.csv"
    w1 = SampleWriter(str(path)); w1.add(0.1, 0.1, 0.2, 1, "near <0.5m"); w1.save()
    w2 = SampleWriter(str(path)); w2.add(0.2, 0.2, 0.1, 0, "mid 0.5-1.5m"); w2.save()

    rows = list(csv.reader(path.open()))
    assert rows.count(CSV_HEADER) == 1         # header written once
    assert len(rows) == 3                       # header + 2 data rows


def test_writer_counts_by_label_and_tier():
    w = SampleWriter("unused.csv")
    w.add(0, 0, 0.30, 1, "near <0.5m")
    w.add(0, 0, 0.06, 1, "far 1.5-3.5m")
    w.add(0, 0, 0.06, 0, "far 1.5-3.5m")
    assert w.counts == {1: 2, 0: 1}
    assert w.tier_counts["far 1.5-3.5m"] == {1: 1, 0: 1}
