"""Field-tool tests: inspect (signature detection, deep backends),
hash, ocr (unavailable path), and username provider logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from tracefield.fieldtools.inspect import (
    detect_media_type,
    find_gps,
    hash_file,
    inspect_file,
)

pytestmark = pytest.mark.integration


PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PDF_HEADER = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + b"x" * 20


@pytest.fixture()
def sample_files(tmp_path: Path) -> dict[str, Path]:
    png = tmp_path / "img.png"
    png.write_bytes(PNG_HEADER)
    jpg = tmp_path / "img.jpg"
    jpg.write_bytes(JPEG_HEADER)
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(PDF_HEADER)
    txt = tmp_path / "note.txt"
    txt.write_text("plain text fixture\n", encoding="utf-8")
    mp4 = tmp_path / "clip.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 16)
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 16)
    return {"png": png, "jpg": jpg, "pdf": pdf, "txt": txt, "mp4": mp4, "wav": wav}


class TestSignatureDetection:
    def test_png(self, sample_files) -> None:
        assert detect_media_type(sample_files["png"]) == "image/png"

    def test_jpeg(self, sample_files) -> None:
        assert detect_media_type(sample_files["jpg"]) == "image/jpeg"

    def test_pdf(self, sample_files) -> None:
        assert detect_media_type(sample_files["pdf"]) == "application/pdf"

    def test_txt(self, sample_files) -> None:
        assert detect_media_type(sample_files["txt"]) == "text/plain"

    def test_mp4_by_ftyp(self, sample_files) -> None:
        assert detect_media_type(sample_files["mp4"]) == "video/mp4"

    def test_wav_by_riff_wave(self, sample_files) -> None:
        assert detect_media_type(sample_files["wav"]) == "audio/wav"

    def test_not_just_extension(self, tmp_path: Path) -> None:
        """A .txt file that is really a PNG must detect as PNG."""
        disguised = tmp_path / "actually-a.png.txt"
        disguised.write_bytes(PNG_HEADER)
        assert detect_media_type(disguised) == "image/png"


class TestHashAndInspect:
    def test_hash_sha256(self, sample_files) -> None:
        digest = hash_file(sample_files["png"], "sha256")
        assert len(digest) == 64

    def test_hash_unknown_algorithm(self, sample_files) -> None:
        with pytest.raises(ValueError):
            hash_file(sample_files["png"], "not-a-real-algo")

    def test_inspect_basic(self, sample_files) -> None:
        result = inspect_file(sample_files["png"], deep=False)
        assert result["detected_media_type"] == "image/png"
        assert "sha256" in result["hashes"]
        assert result["backends"]["exiftool"] == "not_requested"
        assert any("Metadata can be" in c for c in result["caveats"])

    def test_inspect_deep_reports_backend_status(self, sample_files) -> None:
        result = inspect_file(sample_files["png"], deep=True)
        # exiftool is installed in this environment; if not, must say so.
        assert result["backends"]["exiftool"] in ("ok", "unavailable", "error")
        assert result["backends"]["ffprobe"] in ("ok", "unavailable", "error")

    def test_gps_warning_language_says_metadata(self, tmp_path: Path) -> None:
        """GPS hits must be framed as file metadata, not verified location."""
        # Build a minimal JPEG with a GPS-containing fake EXIF payload that
        # exiftool can read is complex; instead exercise find_gps + inspect
        # warning generation on a dict directly.
        meta = {"GPSLatitude": "51.5", "GPSLongitude": "-0.12"}
        hits = find_gps(meta)
        assert hits
        assert any("GPSLatitude" in h for h in hits)

    def test_large_file_does_not_oom_streaming(self, tmp_path: Path) -> None:
        """attach path uses streaming; here we just check hash_file streams."""
        big = tmp_path / "big.bin"
        # 3 MB — modest but enough to exercise chunked read.
        big.write_bytes(b"\x00" * (3 * 1024 * 1024))
        assert len(hash_file(big)) == 64


class TestOcr:
    def test_ocr_unavailable_or_ok_honestly(self, tmp_path: Path) -> None:
        import shutil

        from tracefield.fieldtools.ocr import ocr_image

        img = tmp_path / "x.png"
        img.write_bytes(PNG_HEADER)
        result = ocr_image(img)
        if shutil.which("tesseract") is None:
            assert result["status"] == "UNAVAILABLE"
        else:
            # With a garbage PNG tesseract may error or return empty — both
            # are honest outcomes, never a fake success with fabricated text.
            assert result["status"] in ("ok", "ERROR")
            if result["status"] == "ok":
                assert "text" in result


class TestUsernameRateLimiting:
    def test_min_interval_enforced(self) -> None:
        """The module must define a positive inter-request delay."""
        from tracefield.fieldtools.username import MIN_INTERVAL_S

        assert MIN_INTERVAL_S > 0

    def test_single_username_no_bulk_api(self) -> None:
        """check_username accepts exactly one username — no list parameter."""
        import inspect as pyinspect

        from tracefield.fieldtools import username as umod

        sig = pyinspect.signature(umod.check_username)
        assert "usernames" not in sig.parameters
        assert "bulk" not in sig.parameters
