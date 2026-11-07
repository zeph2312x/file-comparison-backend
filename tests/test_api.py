import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "1.0.0"}


def test_compare_csv_success():
    csv_a = b"id,name,salary\n1,Rahul,25000\n2,Priya,30000\n"
    csv_b = b"id,name,salary\n1,Rahul,27000\n2,Priya,30000\n3,Arjun,35000\n"

    files = {
        "file_a": ("report1.csv", csv_a, "text/csv"),
        "file_b": ("report2.csv", csv_b, "text/csv"),
    }
    data = {"format": "csv"}

    res = client.post("/api/v1/compare", data=data, files=files)
    assert res.status_code == 200
    body = res.json()

    assert body["summary"]["status"] == "Differences detected"
    assert body["summary"]["total_modified"] == 1
    assert body["summary"]["total_added"] == 1


def test_compare_json_success():
    json_a = b'{"name": "Rahul", "age": 25, "city": "Hyderabad"}'
    json_b = b'{"name": "Rahul", "age": 26, "city": "Hyderabad", "dept": "Eng"}'

    files = {
        "file_a": ("a.json", json_a, "application/json"),
        "file_b": ("b.json", json_b, "application/json"),
    }
    data = {"format": "json"}

    res = client.post("/api/v1/compare", data=data, files=files)
    assert res.status_code == 200
    body = res.json()

    assert body["summary"]["total_modified"] == 1  # age 25 -> 26
    assert body["summary"]["total_added"] == 1     # dept added


def test_compare_txt_success():
    txt_a = b"Line 1\nLine 2\nLine 3"
    txt_b = b"Line 1\nLine 2 updated\nLine 3\nLine 4"

    files = {
        "file_a": ("a.txt", txt_a, "text/plain"),
        "file_b": ("b.txt", txt_b, "text/plain"),
    }
    data = {"format": "txt"}

    res = client.post("/api/v1/compare", data=data, files=files)
    assert res.status_code == 200
    body = res.json()

    assert body["summary"]["total_modified"] == 1
    assert body["summary"]["total_added"] == 1


def test_invalid_extension_rejected():
    files = {
        "file_a": ("a.csv", b"a,b\n1,2", "text/csv"),
        "file_b": ("b.txt", b"a,b\n1,2", "text/plain"),
    }
    data = {"format": "csv"}
    res = client.post("/api/v1/compare", data=data, files=files)
    assert res.status_code == 400
    assert "extension" in res.json()["detail"]


def test_export_csv():
    # Run compare then export
    csv_a = b"id,name\n1,A\n"
    csv_b = b"id,name\n1,B\n"

    files = {
        "file_a": ("a.csv", csv_a, "text/csv"),
        "file_b": ("b.csv", csv_b, "text/csv"),
    }
    res = client.post("/api/v1/compare", data={"format": "csv"}, files=files)
    res_json_str = res.text

    export_res = client.post("/api/v1/export", data={"result_json": res_json_str})
    assert export_res.status_code == 200
    assert export_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
