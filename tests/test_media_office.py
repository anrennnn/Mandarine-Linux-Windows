"""ffmpeg, LibreOffice and Tesseract, for real. Skipped where a tool is missing."""
import subprocess

import pytest
from PIL import Image, ImageDraw, ImageFont

from mandarine import ops
from mandarine.ops import external

needs_ffmpeg = pytest.mark.skipif(not external.available("ffmpeg"), reason="ffmpeg not installed")
needs_soffice = pytest.mark.skipif(not external.available("soffice"), reason="LibreOffice not installed")
needs_tesseract = pytest.mark.skipif(not external.available("tesseract"), reason="Tesseract not installed")


@pytest.fixture
def clip(tmp_path):
    if not external.available("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    path = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest", "-c:v", "libx264",
                    "-c:a", "aac", str(path)], check=True)
    return path


@pytest.fixture
def song(tmp_path):
    if not external.available("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    path = tmp_path / "song.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(path)], check=True)
    return path


def test_kinds_and_targets(tmp_path):
    assert ops.kind(tmp_path / "a.MOV") == "video" and ops.kind(tmp_path / "a.flac") == "audio"
    assert ops.kind(tmp_path / "a.xlsx") == "sheet" and ops.kind(tmp_path / "a.pptx") == "slides"
    assert ops.kind(tmp_path / "a.md") == "document"
    assert ops.ext_of(tmp_path / "a.JPEG") == "jpg"
    assert "docx" not in ops.targets_for(tmp_path / "a.docx")
    assert "txt" not in ops.targets_for(tmp_path / "a.md")
    assert ops.targets_for(tmp_path / "a.xlsx") == ["pdf", "ods", "csv"]
    assert ops.targets_for(tmp_path / "a.pptx") == ["pdf", "odp", "png"]
    assert ops.targets_for(tmp_path / "a.mp3")[0] == "m4a"
    assert ops.default_target(tmp_path / "a.mov") == "mp4"
    assert ops.default_target(tmp_path / "a.mp4") == "webm"  # its own format: the first other one
    assert ops.common_targets([]) == []
    with pytest.raises(ValueError):
        ops.convert(tmp_path / "a.mp4", "docx")
    with pytest.raises(ValueError):
        ops.compress(tmp_path / "a.docx")


def test_missing_tool_names_the_package(monkeypatch, tmp_path):
    monkeypatch.setattr(external.sys, "platform", "linux")
    monkeypatch.setattr(external.shutil, "which", lambda name: None)
    assert not external.available("ffmpeg")
    with pytest.raises(ops.MissingTool, match="sudo apt install ffmpeg"):
        ops.convert(tmp_path / "a.mp4", "mp3")
    with pytest.raises(ops.MissingTool, match="libreoffice"):
        external.require("soffice")


def test_run_reports_the_error_tail(monkeypatch):
    import sys
    monkeypatch.setattr(external, "require", lambda program: sys.executable)
    with pytest.raises(RuntimeError, match="python failed: .*boom"):
        external.run(["python", "-c", "import sys; sys.exit('boom')"])
    with pytest.raises(RuntimeError, match="exit code 3"):
        external.run(["python", "-c", "import sys; sys.exit(3)"])


@needs_ffmpeg
def test_video(clip):
    assert ops.media.duration(clip) > 1.5
    seen = []
    [mp3] = ops.convert(clip, "mp3", progress=lambda a, b: seen.append((a, b)))
    assert mp3.name == "clip.mp3" and mp3.stat().st_size > 0 and seen[-1] == (1000, 1000)
    [gif] = ops.convert(clip, "gif")
    assert Image.open(gif).format == "GIF"
    [webm] = ops.convert(clip, "webm")
    assert webm.stat().st_size > 0
    assert ops.compress(clip, "high").name == "clip Compressed.mp4"
    assert ops.media.mute(clip).name == "clip Muted.mp4"
    assert ops.rotate(clip, 90).name == "clip Rotated.mp4"
    assert ops.media.rotate(clip, 180).exists()
    assert ops.media.resize(clip, 120).name == "clip 120p.mp4"
    assert ops.media.normalize(clip).name == "clip Normalized.mp4"
    assert ops.strip_metadata(clip).name == "clip Clean.mp4"


@needs_ffmpeg
def test_audio(song, tmp_path):
    for target in ("mp3", "m4a", "ogg", "flac", "opus"):
        [out] = ops.convert(song, target)
        assert out.suffix == f".{target}"
    assert ops.compress(song).name == "song Compressed.mp3"
    for name in ("song.mp3", "song.m4a", "song.opus", "song.ogg"):
        assert ops.compress(tmp_path / name).exists()
    assert ops.media.normalize(song).name == "song Normalized.wav"
    assert ops.media.normalize(tmp_path / "song.m4a").suffix == ".m4a"
    assert ops.media.duration(tmp_path / "missing.wav") == 0.0


@needs_ffmpeg
def test_ffmpeg_failure_cleans_up(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        ops.convert(bad, "mp3")
    assert not (tmp_path / "bad.mp3").exists()


@needs_soffice
def test_documents(tmp_path, pdf):
    note = tmp_path / "note.txt"
    note.write_text("Hola mundo\n")
    [docx] = ops.convert(note, "docx")
    [back] = ops.convert(docx, "pdf")
    assert back.read_bytes().startswith(b"%PDF")
    [txt] = ops.convert(docx, "txt")
    assert "Hola mundo" in txt.read_text()
    [word] = ops.convert(pdf, "docx")
    assert word.name == "Page 001.docx" and word.stat().st_size > 0
    csv = tmp_path / "data.csv"
    csv.write_text("a,b\n1,2\n")
    [xlsx] = ops.convert(csv, "xlsx")
    assert xlsx.stat().st_size > 0


def test_soffice_without_output(monkeypatch, tmp_path):
    monkeypatch.setattr(external, "run", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="could not convert"):
        external.soffice_convert(tmp_path / "x.docx", "pdf")


def test_pdf_text_layer(pdf):
    [txt] = ops.convert(pdf, "txt")
    text = txt.read_text()
    assert "SECRET-4242 page 1" in text and "SECRET-4242 page 2" in text


@needs_tesseract
def test_ocr(tmp_path):
    img = tmp_path / "scan.png"
    im = Image.new("RGB", (700, 160), "white")
    font = ImageFont.truetype("DejaVuSans.ttf", 56) if _has_dejavu() else ImageFont.load_default(56)
    ImageDraw.Draw(im).text((20, 40), "Hola Mandarine", fill="black", font=font)
    im.save(img)
    [txt] = ops.convert(img, "txt")
    assert "Mandarine" in txt.read_text()
    im.save(tmp_path / "scan.pdf")  # a scanned PDF: no text layer, OCR fills in
    assert "Mandarine" in ops.text.pdf_text(tmp_path / "scan.pdf")
    blank = tmp_path / "blank.png"
    Image.new("RGB", (50, 50), "white").save(blank)
    with pytest.raises(ValueError, match="No text"):
        ops.convert(blank, "txt")
    assert external.tesseract_langs()


def test_text_rejects_other_kinds(tmp_path):
    with pytest.raises(ValueError):
        ops.text.to_text(tmp_path / "a.mp4")


def test_image_formats(png, jpg):
    for target in ("avif", "heic", "ico", "webp"):
        [out] = ops.convert(png, target)
        assert Image.open(out).size[0] > 0
    [back] = ops.convert(png.with_suffix(".heic"), "jpg")
    assert Image.open(back).format == "JPEG"
    [ico] = ops.convert(jpg, "ico")
    assert Image.open(ico).format == "ICO"


def _has_dejavu():
    try:
        ImageFont.truetype("DejaVuSans.ttf", 10)
        return True
    except OSError:
        return False


def test_direct_calls_check_targets(tmp_path, pdf):
    with pytest.raises(ValueError):
        ops.media.convert(tmp_path / "a.mp4", "mp4")
    with pytest.raises(ValueError):
        ops.office.convert(tmp_path / "a.docx", "docx")
    seen = []
    ops.text.pdf_text(pdf, progress=lambda a, b: seen.append(a))
    assert seen == [1, 2]


def test_palette_image_to_avif(tmp_path):
    src = tmp_path / "pal.gif"
    Image.new("P", (20, 20)).save(src)
    [out] = ops.convert(src, "avif")
    assert out.exists()


@needs_ffmpeg
def test_cli_media_commands(clip, capsys):
    from mandarine import cli
    assert cli.main(["mute", str(clip)]) == 0
    assert cli.main(["resize", str(clip), "--height", "120"]) == 0
    assert cli.main(["normalize", str(clip)]) == 0
    assert cli.main(["targets", str(clip)]) == 0
    out = capsys.readouterr().out
    assert "clip Muted.mp4" in out and "clip 120p.mp4" in out and "webm, gif, mp3" in out


@needs_ffmpeg
def test_app_media_actions(clip, qapp, tmp_path, monkeypatch, qtbot):
    from test_app import Backend, FakeHotkey
    from PySide6.QtCore import QSettings
    from mandarine.gui import app as A, autostart
    monkeypatch.setattr(autostart, "entry_path", lambda: tmp_path / "autostart.desktop")
    core = A.Mandarine(qapp, settings=QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat),
                       backend=Backend(), hotkey_backend=FakeHotkey())
    core.pool = type("Inline", (), {"start": staticmethod(lambda task: task.run())})()
    for key, name in [("mute", "Muted"), ("resize", "720p"), ("normalize", "Normalized"),
                      ("metadata", "Clean"), ("rotate", "Rotated"), ("to:mp3", None)]:
        core._run(key, [clip])
        assert core.toast.title.text().endswith("done"), key
    assert (tmp_path / "clip Muted.mp4").exists() and (tmp_path / "clip.mp3").exists()
    core.tray.hide()
    core.toast.hide()
    core.bubble.hide()
