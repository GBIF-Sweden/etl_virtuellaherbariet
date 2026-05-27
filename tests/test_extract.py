import os
import sys
import tempfile
import types
import io
import csv
import unittest
from unittest.mock import patch

import requests
import urllib3

class _FakeProgress:
    def update(self, *_args, **_kwargs):
        return None

    def close(self):
        return None


sys.modules.setdefault("tqdm", types.SimpleNamespace(tqdm=lambda *args, **kwargs: _FakeProgress()))

from extraction import download_csv  # noqa: E402


class FakeRaw(io.BytesIO):
    def __init__(self, content: bytes, exc=None, raise_after=None):
        super().__init__(content)
        self.exc = exc
        self.raise_after = raise_after

    def read(self, size=-1):
        if self.exc is not None and self.raise_after is not None and self.tell() >= self.raise_after:
            exc = self.exc
            self.exc = None
            raise exc
        if self.raise_after is not None and self.tell() < self.raise_after:
            remaining_before_error = self.raise_after - self.tell()
            if size < 0 or size > remaining_before_error:
                size = remaining_before_error
        data = super().read(size)
        if self.exc is not None and self.tell() == len(self.getvalue()):
            exc = self.exc
            self.exc = None
            raise exc
        return data

    def read1(self, size=-1):
        return self.read(size)


class FakeResponse:
    def __init__(self, content, status_code=200, exc=None, raise_after=None):
        self.content = content
        self.status_code = status_code
        self.exc = exc
        self.headers = {"Content-Type": "text/csv"}
        self.encoding = None
        self.raw = FakeRaw(content.encode("utf-8"), exc=exc, raise_after=raise_after)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"Unexpected HTTP status in test: {self.status_code}")

class TestExtract(unittest.TestCase):
    @patch("requests.Session.post")
    def test_download_csv_utf8(self, mock_post):
        mock_post.return_value = FakeResponse("col1,col2\nval1,värdeå\n")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "test.csv")
            download_csv("http://example.com", {}, output_file)

            with open(output_file, "r", encoding="utf-8") as f:
                saved_content = f.read()

        self.assertEqual(saved_content, "col1,col2\nval1,värdeå\n")

    @patch("requests.Session.post")
    def test_retry_does_not_duplicate_partial_page(self, mock_post):
        mock_post.side_effect = [
            requests.exceptions.Timeout("stream interrupted"),
            FakeResponse("id,name\n1,alpha\n2,beta\n"),
            FakeResponse("id,name\n"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "test.csv")
            download_csv("http://example.com", {}, output_file, page_size=2, max_retries=2)

            with open(output_file, "r", encoding="utf-8") as f:
                saved_content = f.read()

        self.assertEqual(saved_content, "id,name\n1,alpha\n2,beta\n")

    @patch("requests.Session.post")
    def test_multiline_field_is_preserved(self, mock_post):
        mock_post.side_effect = [
            FakeResponse('id,notes\n1,"line one\nline two"\n2,single line\n'),
            FakeResponse("id,notes\n"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "test.csv")
            download_csv("http://example.com", {}, output_file, page_size=2)

            with open(output_file, "r", encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))

        self.assertEqual(rows, [["id", "notes"], ["1", "line one\nline two"], ["2", "single line"]])

    @patch("requests.Session.post")
    def test_retry_on_protocol_error(self, mock_post):
        mock_post.side_effect = [
            FakeResponse(
                "id,name\n1,alpha\n2,beta\n",
                exc=urllib3.exceptions.ProtocolError("Connection broken", Exception("IncompleteRead")),
                raise_after=0,
            ),
            FakeResponse("id,name\n1,alpha\n2,beta\n"),
            FakeResponse("id,name\n"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "test.csv")
            download_csv("http://example.com", {}, output_file, page_size=2, max_retries=3)

            with open(output_file, "r", encoding="utf-8") as f:
                saved_content = f.read()

        self.assertEqual(saved_content, "id,name\n1,alpha\n2,beta\n")


if __name__ == "__main__":
    unittest.main()
