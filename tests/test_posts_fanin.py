"""M6 closeout (b): the per-video posts.jsonl -> history/posts.jsonl fan-in (ADR 0003 D6).

Stage 06 + the DistributionAdapter write a PER-VIDEO posts.jsonl under each run dir for
crash-safe exactly-once; merge_posts_to_history merges the CONFIRMED records into the durable
history/posts.jsonl that shorts/audit.py reads. NOTE: commit_ledgers dedupes on video_id ONLY —
a video posted to TWO platforms is two legitimate history records, so the fan-in dedupes on
(video_id, platform) via its own tolerant appender.
"""
import json

from shared.distribution.posts_ledger import write_confirmed, write_intent, write_publishing
from shorts.run_batch import merge_posts_to_history


def _run_dir(root, batch, vid):
    d = root / "runs" / batch / vid
    d.mkdir(parents=True, exist_ok=True)
    return d


def _history(root):
    p = root / "history" / "posts.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue                                            # skip pre-existing garbage
    return out


def test_confirmed_records_merge_with_ts_and_url_preserved(tmp_path):
    rd = _run_dir(tmp_path, "b1", "fin-b1-0")
    write_intent(rd / "posts.jsonl", video_id="fin-b1-0", platform="youtube")
    write_confirmed(rd / "posts.jsonl", video_id="fin-b1-0", platform="youtube",
                    remote_id="yt123", url="https://youtu.be/yt123")
    assert merge_posts_to_history(tmp_path, [rd]) == 1
    recs = _history(tmp_path)
    assert len(recs) == 1
    rec = recs[0]
    assert rec["state"] == "confirmed" and rec["video_id"] == "fin-b1-0"
    # shorts/audit.py::gather_posts needs ts (window filter) + url — both must survive the merge
    assert rec["url"] == "https://youtu.be/yt123" and rec["ts"]


def test_intent_and_publishing_records_are_not_merged(tmp_path):
    rd = _run_dir(tmp_path, "b1", "fin-b1-0")
    write_intent(rd / "posts.jsonl", video_id="fin-b1-0", platform="youtube")
    write_publishing(rd / "posts.jsonl", video_id="fin-b1-0", platform="youtube",
                     remote_id="yt123")
    assert merge_posts_to_history(tmp_path, [rd]) == 0
    # nothing confirmed -> nothing durable; the file isn't even created
    assert not (tmp_path / "history" / "posts.jsonl").exists()


def test_merge_is_idempotent_across_reruns(tmp_path):
    rd = _run_dir(tmp_path, "b1", "fin-b1-0")
    write_confirmed(rd / "posts.jsonl", video_id="fin-b1-0", platform="youtube",
                    remote_id="yt123", url="u")
    assert merge_posts_to_history(tmp_path, [rd]) == 1
    assert merge_posts_to_history(tmp_path, [rd]) == 0      # resumed batch: no double-append
    assert len(_history(tmp_path)) == 1


def test_two_platforms_yield_two_history_records(tmp_path):
    """The over-dedup regression: commit_ledgers keys on video_id alone, which would silently
    drop the tiktok record for a video that posted to youtube too."""
    rd = _run_dir(tmp_path, "b1", "fin-b1-0")
    write_confirmed(rd / "posts.jsonl", video_id="fin-b1-0", platform="youtube",
                    remote_id="yt1", url="uy")
    write_confirmed(rd / "posts.jsonl", video_id="fin-b1-0", platform="tiktok",
                    remote_id="tt1", url="ut")
    assert merge_posts_to_history(tmp_path, [rd]) == 2
    assert {r["platform"] for r in _history(tmp_path)} == {"youtube", "tiktok"}
    # and the pair stays deduped on re-merge
    assert merge_posts_to_history(tmp_path, [rd]) == 0
    assert len(_history(tmp_path)) == 2


def test_malformed_lines_in_per_video_and_history_are_tolerated(tmp_path):
    rd = _run_dir(tmp_path, "b1", "fin-b1-0")
    write_confirmed(rd / "posts.jsonl", video_id="fin-b1-0", platform="youtube",
                    remote_id="yt1", url="u")
    with (rd / "posts.jsonl").open("a") as f:
        f.write("not-json\n")                               # torn write mid-crash
        f.write('{"no_state": true}\n')                     # parseable but not a post record
    hist = tmp_path / "history"
    hist.mkdir(parents=True)
    (hist / "posts.jsonl").write_text("garbage-line\n")     # pre-existing corruption preserved
    assert merge_posts_to_history(tmp_path, [rd]) == 1
    raw = (hist / "posts.jsonl").read_text().splitlines()
    assert raw[0] == "garbage-line"                         # forensic bytes never removed
    assert len(_history(tmp_path)) == 1                     # _history skips the garbage


def test_missing_per_video_file_and_run_dir_are_tolerated(tmp_path):
    empty = _run_dir(tmp_path, "b1", "fin-b1-0")            # ran but never reached 06
    ghost = tmp_path / "runs" / "b1" / "fin-b1-1"           # quarantined early: dir absent
    assert merge_posts_to_history(tmp_path, [empty, ghost]) == 0
    assert not (tmp_path / "history" / "posts.jsonl").exists()


def test_merged_history_is_visible_to_the_audit_gatherer(tmp_path):
    """End-to-end with the real reader: audit reported zero posts forever because nothing merged
    the per-video ledgers — after the fan-in, gather_posts must see the confirmed post."""
    from shorts.audit import gather_posts
    rd = _run_dir(tmp_path, "b1", "fin-b1-0")
    write_confirmed(rd / "posts.jsonl", video_id="fin-b1-0", platform="youtube",
                    remote_id="yt1", url="https://youtu.be/yt1")
    merge_posts_to_history(tmp_path, [rd])
    posts = gather_posts(tmp_path, days=7)
    assert [p["video_id"] for p in posts] == ["fin-b1-0"]
