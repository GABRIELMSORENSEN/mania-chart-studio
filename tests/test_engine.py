import io
import zipfile

import pytest

import engine


def sample():
    return {"name": "Hard", "style": "stream", "level": 2, "bpm": 120., "anchor": 0.,
            "offset": 0., "notes": [{"t": 1000., "end": 1000., "lane": 0},
                                     {"t": 1500., "end": 1800., "lane": 2}]}


@pytest.mark.parametrize("url", ["https://youtu.be/s4fuzKjr4cA", "https://www.youtube.com/watch?v=s4fuzKjr4cA&list=abc", "https://youtube.com/shorts/s4fuzKjr4cA"])
def test_video_urls(url):
    assert engine.youtube_id(url) == "s4fuzKjr4cA"


@pytest.mark.parametrize("url", ["http://youtu.be/s4fuzKjr4cA", "https://youtube.com.evil.test/watch?v=s4fuzKjr4cA", "https://127.0.0.1/", "https://youtube.com/playlist?list=x", "https://evil@youtube.com/watch?v=s4fuzKjr4cA"])
def test_url_boundaries(url):
    with pytest.raises(ValueError):
        engine.youtube_id(url)


def test_offset_and_ln_export():
    c = sample()
    c["offset"] = 25
    text = engine.osu_text({"title": "A\nMode:0", "artist": "B"}, c)
    assert "64,192,1025,1,0" in text
    assert "320,192,1525,128,0,1825:" in text
    assert "Mode: 3" in text
    assert "\nMode:0" not in text
    assert engine.statistics({"title": "A", "artist": "B"}, c)["stars"] >= 0


def test_overlap_and_duration():
    c = sample()
    c["notes"].append({"t": 1600, "end": 1600, "lane": 2})
    with pytest.raises(ValueError, match="sobrepostas"):
        engine.validate_chart(c, 5)
    with pytest.raises(ValueError, match="fora"):
        engine.validate_chart(sample(), 1)


def test_export_package(tmp_path):
    (tmp_path / "audio.wav").write_bytes(b"test-pcm")
    project = {"meta": {"title": "A", "artist": "B"}, "analysis": {"duration": 5}, "charts": [sample()]}
    with zipfile.ZipFile(io.BytesIO(engine.export(tmp_path, project))) as package:
        assert set(package.namelist()) == {"audio.wav", "cover.jpg", "Mania Chart Studio [1].osu", "AI-DRAFT.txt"}
        assert package.read("cover.jpg").startswith(b"\xff\xd8")


def test_draft_does_not_shift_attacks():
    analysis = {"bpm": 120, "anchor": 0, "events": [{"t": 1051, "strength": 1.5, "band": 0}, {"t": 1337, "strength": 1.2, "band": 1}, {"t": 1678, "strength": .8, "band": 2}]}
    for style in engine.STYLES:
        c = engine.draft(analysis, style, 3)
        assert set(n["t"] for n in c["notes"]) <= {1051, 1337, 1678}
        engine.validate_chart(c, 5)
