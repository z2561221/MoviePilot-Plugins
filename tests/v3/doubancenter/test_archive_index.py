"""对17ff14fd冻结参考做输出差分，覆盖弱匹配、替换及候选顺序。"""

import random
from copy import deepcopy
from itertools import product

import pytest
from app.plugins.doubancenter.model import archive_match
from app.plugins.doubancenter.service import archive

from tests.v3.doubancenter import archive_reference as reference


def item(record, label, source="subscribe_history"):
    return {"id": label, "source": source, "record": record, "archived_at": "2026-11-16 00:00:00"}


def strong(number, **fields):
    return {"title": "same", "media_source": "douban", "media_id": str(number), **fields}


def weak(**fields):
    return {"title": "same", "media_source": "douban", "media_id": None, **fields}


def assert_equivalent(rows):
    before = deepcopy(rows)
    expected = reference.dedupe_archive_records(rows)
    actual = archive.dedupe_archive_records(rows)
    assert actual == expected
    assert rows == before
    return actual


def test_pair_matching_preserves_exact_key_priority_and_partial_id_semantics():
    records = [None, [], "invalid", {}, {"title": ""}, strong(1), strong(2),
               strong(1, tmdbid="10"), strong(1, tmdbid="11"),
               weak(), weak(tmdbid="10"), weak(tmdb_id="10"), weak(unique="a"),
               weak(unique="b"), weak(detail="a"), weak(detail="b"),
               weak(detail=["a"]), weak(detail={"a": 1}), strong(1, time="new"),
               {"title": "same", "tmdbid": "123"}, {"title": "same", "tmdbid": "0"},
               {"title": "other"}, {"title": " same "}]
    for source, left, right in product(("subscribe_history", "observation", ""), records, records):
        assert archive.same_archive_record(source, left, right) == reference.same_archive_record(source, left, right)
        assert archive.archive_record_key(source, left) == reference.archive_record_key(source, left)
    # tmdbid不是精确键的一部分，原实现精确键优先于其弱字段冲突。
    assert archive.same_archive_record("history", strong(1, tmdbid="10"), strong(1, tmdbid="11")) is True
    assert archive.same_archive_record("history", strong(1), strong(2)) is False


@pytest.mark.parametrize("rows", [
    [], [None, "bad", item(None, "none"), item([], "list"), item({}, "empty")],
    [item(strong(1), "one"), item(strong(2), "two")],
    [item(strong(1), "one"), item(strong(1, poster="rich"), "rich")],
    [item(weak(), "weak"), item(strong(1), "one"), item(strong(2), "two")],
    [item(strong(1), "one"), item(strong(2), "two"), item(weak(), "weak")],
    [item(weak(detail="x"), "x"), item(weak(detail="y"), "y"), item(weak(unique="u"), "u")],
    [item(strong(1, unique="a"), "a"), item(strong(1, unique="b"), "b")],
    [item(strong(1, time="old"), "old"), item(strong(1, time="new"), "new")],
    [item(strong(1), "a", "first"), item(strong(1), "b", "second")],
])
def test_ordered_deduplication_matches_reference(rows):
    assert_equivalent(rows)


def test_weak_completeness_replacement_can_bridge_strong_ids_and_create_duplicate_keys():
    rows = [item(strong(1, unique="a", detail="d"), "one"),
            item(strong(2, unique="b", detail="d"), "two")]
    rich_weak = weak(detail="d", **{f"extra{i}": "yes" for i in range(20)})
    rows.append(item(rich_weak, "bridge"))
    rows.append(item(strong(3, unique="c", detail="d"), "three"))
    rows.append(item(strong(2, unique="b", detail="d", **{f"extra{i}": "yes" for i in range(40)}), "two-rich"))
    rows.append(item(strong(2, unique="b", detail="d", **{f"extra{i}": "yes" for i in range(50)}), "two-richest"))
    result, changed = assert_equivalent(rows)
    assert changed
    # 弱记录先匹配0号位；替换后不主动把已有1号位合并，精确键也不能抢先跳过0号位。
    assert [row["id"] for row in result] == ["two-richest", "two"]


def test_replacement_updates_missing_fields_and_lazily_built_columns():
    rows = [item(weak(unique="a", detail="d1"), "a"),
            item(weak(unique="b", detail="d2"), "b"),
            item(weak(detail="d3"), "missing"),
            item(weak(unique="a", detail="d3", poster="image"), "filled"),
            item(weak(unique="c", detail="d3"), "c"),
            item(weak(unique="a", detail="d3", link="new", poster="image", rank_key="rank"), "richer")]
    assert_equivalent(rows)


@pytest.mark.parametrize("seed", range(30))
def test_randomized_mixed_records_match_reference(seed):
    rng = random.Random(seed)
    rows = []
    for number in range(120):
        record = {"title": rng.choice(("same", "same", "other", "", " same "))}
        identity = rng.randrange(5)
        if identity < 3:
            record.update(media_source=rng.choice(("douban", "themoviedb")), media_id=str(rng.randint(1, 5)))
        elif identity == 3:
            record.update(media_source="douban", media_id=None)
        for field in ("unique", "tmdbid", "tmdb_id", "reason", "detail", "link", "time", "poster", "year"):
            if rng.random() < 0.55:
                record[field] = rng.choice((None, "", "1", "2", 0, False, [], ["x"]))
        if rng.random() < 0.25:
            record[f"extra{number}"] = "information"
        rows.append(item(record, str(number), rng.choice(("history", "observation"))))
    assert_equivalent(rows)


@pytest.mark.parametrize("count", [1000, 2000])
def test_large_same_name_different_ids_preserve_trim_and_changed_flag(count, monkeypatch):
    rows = [item(strong(number + 1), str(number)) for number in range(count)]
    created = []
    original = archive_match.ArchiveMatchIndex

    def create():
        index = original()
        created.append(index)
        return index

    monkeypatch.setattr(archive_match, "ArchiveMatchIndex", create)
    result, changed = assert_equivalent(rows)
    assert len(result) == 500 and changed is False
    assert created[0].comparisons == 0


def test_index_is_per_operation_and_does_not_store_plugin_state():
    rows = [item(strong(1), "one"), item(strong(2), "two")]
    assert archive.dedupe_archive_records(rows) == archive.dedupe_archive_records(rows)
    assert not hasattr(archive, "_archive_match_index")


@pytest.mark.parametrize("count", [100, 300])
def test_other_identity_missing_fields_do_not_dilute_conflicting_group_filter(count, monkeypatch):
    rows = [item(strong(number + 1), str(number)) for number in range(count)]
    rows += [item(strong(99999, detail=str(number)), f"conflict-{number}") for number in range(count)]
    created = []
    original = archive_match.ArchiveMatchIndex

    def create():
        index = original()
        created.append(index)
        return index

    monkeypatch.setattr(archive_match, "ArchiveMatchIndex", create)
    assert_equivalent(rows)
    assert created[0].comparisons == 0


def test_replacement_updates_identity_group_columns_and_keeps_weak_bridge():
    rows = [item(strong(1, reason="a", detail="x"), "ax"),
            item(strong(1, reason="b", detail="x"), "bx"),
            item(strong(1, reason="a", detail="y"), "ay"),
            item(strong(2, detail="x"), "other")]
    rows += [item(weak(detail="x", **{f"extra{i}": "yes" for i in range(20)}), "bridge"),
             item(strong(3, reason="a", detail="x", poster="image"), "three"),
             item(strong(1, reason="b", detail="x", poster="image", rank_key="rank"), "bx-rich"),
             item(strong(1, reason="a", detail="y", poster="image"), "ay-rich")]
    assert_equivalent(rows)


def test_index_accepts_add_before_find_and_can_replace_demoted_identity_group():
    index = archive_match.ArchiveMatchIndex()
    source = "history"
    first, second = strong(1, detail="x"), strong(1, detail="y")
    index.add(source, first)
    index.add(source, second)
    richer = strong(1, detail="x", poster="image")
    position, feature = index.find(source, richer)
    assert position == 0
    index.replace(position, richer, feature)
    assert index.find(source, second)[0] == 1
    assert index.records == [richer, second]
