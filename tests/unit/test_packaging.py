import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_spec_is_valid_python_and_bundles_only_ffmpeg_and_ffprobe():
    text = (ROOT / "DinoTube.spec").read_text(encoding="utf-8")
    ast.parse(text)
    assert "ffmpeg.exe" in text and "ffprobe.exe" in text and "ffplay.exe" not in text
    assert 'name="DinoTube"' in text and "console=False" in text


def test_bundled_ffmpeg_keeps_its_license_files():
    folder = ROOT / "third_party" / "ffmpeg"
    assert (folder / "LICENSE").is_file() and (folder / "README.txt").is_file()
    assert sorted(p.name for p in (folder / "bin").iterdir()) == ["ffmpeg.exe", "ffprobe.exe"]


def test_legacy_files_are_gone():
    for name in ("main.spec", "spinner.gif", "amelie-poster.png", "dist/main.exe"):
        assert not (ROOT / name).exists(), name


def test_build_script_and_icon_exist():
    assert (ROOT / "packaging" / "build_windows.bat").is_file()
    assert (ROOT / "packaging" / "dinotube.ico").stat().st_size > 1000


def test_app_icon_renders_at_every_size(qapp):
    from app.styles import app_icon

    icon = app_icon.app_icon()
    assert not icon.isNull()
    for size in app_icon.SIZES:
        image = app_icon.render(size)
        assert image.width() == size and image.pixelColor(size // 2, size // 2).alpha() == 255
        assert image.pixelColor(0, 0).alpha() == 0  # cantos arredondados transparentes
