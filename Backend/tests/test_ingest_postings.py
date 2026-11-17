from app.ingest_postings import normalize


def test_normalize_preserves_short_external_id():
    posting = normalize({"job_id": "job-123"})

    assert posting["id"] == "job-123"


def test_normalize_hashes_external_id_over_database_limit():
    raw_id = "x" * 256
    posting = normalize({"job_id": raw_id})

    assert len(posting["id"]) <= 255
    assert posting["id"].startswith("sha256:")
    assert posting["raw"]["job_id"] == raw_id
