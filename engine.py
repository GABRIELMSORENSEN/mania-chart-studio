"""Neural beat proposals + deterministic audio-driven 4K draft mapping.

This is not a trained chart generation model. No claims of ranked eligibility
or guaranteed musical timing are made. All generated objects are editable.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import parse_qs, urlparse
import zipfile

import numpy as np
from scipy.signal import find_peaks

MODEL_URL = "https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/small0.ckpt"
MODEL_SHA = "6074be2c4d490c5f6101fcc374a1ec72ae93456e23bb6019783b849f5dc7d47b"
MAX_DURATION = 1200
STYLES = ("auto", "stream", "jumpstream", "handstream", "chordjack", "jack", "hybrid", "ln")
LEVELS = ("Easy", "Normal", "Hard", "Insane", "Extra")


def youtube_id(url):
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        raise ValueError("Use um link HTTPS de um vídeo do YouTube.")
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        value = parsed.path.strip("/")
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        value = parse_qs(parsed.query).get("v", [""])[0]
        if parsed.path.startswith(("/shorts/", "/embed/")):
            value = parsed.path.split("/")[2]
    else:
        raise ValueError("O endereço precisa ser do YouTube.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        raise ValueError("O link não contém um vídeo válido. Playlists não são aceitas.")
    return value


def run(args, timeout=240):
    result = subprocess.run(args, capture_output=True, timeout=timeout)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"Falha ao processar áudio: {detail}")
    return result.stdout


def download(url, folder, status):
    import yt_dlp
    ident = youtube_id(url)
    canonical = f"https://www.youtube.com/watch?v={ident}"
    options = dict(quiet=True, no_warnings=True, noplaylist=True, socket_timeout=25,
                   retries=2, format="bestaudio/best", outtmpl=str(folder / "source.%(ext)s"),
                   max_filesize=100_000_000, restrictfilenames=True)
    status("Consultando vídeo")
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(canonical, download=False)
        duration = info.get("duration")
        if info.get("is_live") or not duration or duration > MAX_DURATION:
            raise ValueError("Use um vídeo gravado com até 20 minutos.")
        status("Baixando áudio")
        result = ydl.extract_info(canonical, download=True)
        source = Path(ydl.prepare_filename(result))
    # PCM is shared by the browser and osu!, avoiding MP3 priming ambiguities.
    status("Preparando áudio")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-t", str(MAX_DURATION),
         "-vn", "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(folder / "audio.wav")])
    source.unlink(missing_ok=True)
    return {"title": info.get("track") or info.get("title") or ident,
            "artist": info.get("artist") or info.get("uploader") or "Unknown",
            "source": canonical, "video_id": ident}


def checkpoint():
    import requests
    dest = Path(os.getenv("MANIA_MODEL_PATH", str(Path(__file__).parent / "models/small0.ckpt")))
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        # TLS verification remains enabled. Do not bypass certificate errors.
        response = requests.get(MODEL_URL, timeout=90)
        response.raise_for_status()
        raw = response.content
        if hashlib.sha256(raw).hexdigest() != MODEL_SHA:
            raise RuntimeError("Checksum do modelo diferente do esperado.")
        temp = dest.with_suffix(".part")
        temp.write_bytes(raw)
        temp.replace(dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest() != MODEL_SHA:
        raise RuntimeError("Modelo local inválido. Reinstale small0.ckpt.")
    return dest


def analyze(audio, status):
    import librosa
    import torch
    from beat_this.inference import Audio2Beats
    status("Carregando modelo de batidas")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    signal = np.frombuffer(run(["ffmpeg", "-v", "error", "-i", str(audio), "-f", "f32le",
                               "-ar", "22050", "-ac", "1", "-"]), dtype="<f4").copy()
    if len(signal) / 22050 > MAX_DURATION or len(signal) < 22050:
        raise ValueError("Áudio precisa durar de 1 segundo a 20 minutos.")
    status("IA: estimando batidas e compassos")
    tracker = Audio2Beats(checkpoint_path=str(checkpoint()), device="cpu")
    beats, downbeats = tracker(signal, 22050)
    beats = np.asarray(beats)
    if len(beats) < 4:
        raise ValueError("Não foi possível estimar o pulso. Tente outra gravação.")
    status("Extraindo ataques e energia")
    hop = 220
    spec = abs(librosa.stft(signal, n_fft=1024, hop_length=hop))
    freq = librosa.fft_frequencies(sr=22050, n_fft=1024)
    flux = np.maximum(np.diff(np.log1p(spec * 20), axis=1, prepend=0), 0)
    bands = np.stack([flux[(freq >= lo) & (freq < hi)].mean(axis=0)
                      for lo, hi in [(40, 220), (220, 2200), (2200, 10000)]])
    envelope = bands.mean(axis=0)
    peaks, _ = find_peaks(envelope, distance=5, prominence=max(.008, float(np.std(envelope) * .3)))
    baseline = max(float(np.percentile(envelope[peaks], 80)), .001) if len(peaks) else .001
    events = [{"t": round(float(p * hop / 22050 * 1000), 2),
               "strength": round(min(3., float(envelope[p]) / baseline), 3),
               "band": int(np.argmax(bands[:, p]))} for p in peaks if p * hop < len(signal)]
    if not events:
        raise ValueError("Nenhum ataque de áudio detectado. Tente outra gravação.")
    chunks = np.array_split(signal, min(2400, len(signal)))
    waveform = [round(float(np.max(np.abs(c))), 4) for c in chunks]
    # Robust constant-tempo proposal. Variable-tempo audio must be reviewed.
    intervals = np.diff(beats)
    period = float(np.median(intervals[(intervals > .18) & (intervals < 2)]))
    bpm = 60 / period
    phases = np.angle(np.mean(np.exp(2j * np.pi * beats / period))) / (2 * np.pi) * period
    anchor = float(phases % period) * 1000
    stability = float(np.mean(abs(intervals - period) < .025))
    return {"duration": round(len(signal) / 22050, 3), "bpm": round(bpm, 3),
            "anchor": round(anchor, 2), "beats": (beats * 1000).round(2).tolist(),
            "downbeats": (np.asarray(downbeats) * 1000).round(2).tolist(),
            "events": events, "waveform": waveform, "tempo_stability": round(stability, 3),
            "model": "Beat This small0", "reviewed": False}


def draft(analysis, style="auto", level=2):
    if style not in STYLES or not 0 <= level < len(LEVELS):
        raise ValueError("Estilo ou dificuldade inválida.")
    events = analysis["events"]
    thresholds = [.95, .72, .48, .32, .20]
    min_gap = [210, 150, 105, 80, 65][level]
    notes, last_lane, last_time = [], -1, -1000
    weights = [0, 0, 0, 0]
    chosen = [e for e in events if e["strength"] >= thresholds[level]]
    for index, event in enumerate(chosen):
        t = round(event["t"])
        if t - last_time < min_gap:
            continue
        # Auto adapts chord size to observed attack strength; it is a heuristic.
        effective = style
        if style == "auto":
            effective = "jumpstream" if event["strength"] > 1.2 else "stream"
        chord = 1
        if level > 0 and effective in ("jumpstream", "chordjack", "hybrid") and event["strength"] > .95:
            chord = 2
        if level >= 3 and effective == "handstream" and event["strength"] > .8:
            chord = 3
        if effective == "chordjack" and level >= 2:
            chord = 2
        preferred = (0, 2, 3, 1)[index % 4]
        if effective == "jack" and last_lane >= 0 and t - last_time < 330:
            preferred = last_lane
        elif preferred == last_lane:
            preferred = (preferred + 1) % 4
        lanes = [preferred]
        if chord >= 2:
            lanes.append((preferred + 2) % 4)
        if chord == 3:
            lanes.append((preferred + 1) % 4)
        for lane in lanes:
            notes.append({"t": t, "lane": lane, "end": t,
                          "origin": "audio-attack", "strength": event["strength"]})
            weights[lane] += 1
        if effective in ("ln", "hybrid") and level >= 1:
            next_t = next((e["t"] for e in chosen[index + 1:] if e["t"] > t + 160), t + 160)
            length = min(next_t - t - 60, 400)
            if length >= 180 and event["strength"] > .8:
                # Draft LN requires manual review; do not infer sustained vocals.
                notes[-1]["end"] = round(t + length)
        last_lane, last_time = preferred, t
    # Prevent a future note from starting inside a previous LN on the same lane.
    for lane in range(4):
        lane_notes = [n for n in notes if n["lane"] == lane]
        for a, b in zip(lane_notes, lane_notes[1:]):
            a["end"] = min(a["end"], b["t"] - 30) if a["end"] > a["t"] else a["end"]
    return {"name": LEVELS[level], "level": level, "style": style, "notes": notes,
            "offset": 0, "bpm": analysis["bpm"], "anchor": analysis["anchor"],
            "reviewed": False}


def validate_chart(chart, duration):
    if not math.isfinite(chart["bpm"]) or not 20 <= chart["bpm"] <= 500:
        raise ValueError("BPM deve estar entre 20 e 500.")
    if not math.isfinite(chart["offset"]) or abs(chart["offset"]) > 5000:
        raise ValueError("Offset deve estar entre -5000 e 5000 ms.")
    if not math.isfinite(chart["anchor"]) or not -5000 <= chart["anchor"] <= duration * 1000:
        raise ValueError("Início da grade inválido.")
    if len(chart["notes"]) > 100000:
        raise ValueError("Limite de 100 mil notas.")
    previous = [-1000.] * 4
    for n in sorted(chart["notes"], key=lambda n: n["t"]):
        t, end, lane = n["t"] + chart["offset"], n["end"] + chart["offset"], n["lane"]
        if lane not in range(4) or not all(math.isfinite(v) for v in (t, end)):
            raise ValueError("Nota inválida.")
        if t < 0 or end < t or end > duration * 1000:
            raise ValueError("Há notas fora do áudio. Ajuste o offset ou remova essas notas.")
        if round(t) <= round(previous[lane]):
            raise ValueError("Há notas sobrepostas na mesma coluna.")
        previous[lane] = end


def clean(value):
    return re.sub(r"[\r\n\x00-\x1f]", " ", str(value)).strip()[:180]


def osu_text(meta, chart):
    notes = []
    for n in sorted(chart["notes"], key=lambda n: (n["t"], n["lane"])):
        t, end, x = round(n["t"] + chart["offset"]), round(n["end"] + chart["offset"]), 64 + 128 * n["lane"]
        notes.append(f"{x},192,{t},128,0,{end}:0:0:0:0:" if end > t else f"{x},192,{t},1,0,0:0:0:0:")
    return f"""osu file format v14

[General]
AudioFilename: audio.wav
AudioLeadIn: 0
PreviewTime: -1
SampleSet: Normal
Mode: 3

[Editor]
DistanceSpacing: 1
BeatDivisor: 4
GridSize: 4

[Metadata]
Title:{clean(meta['title'])}
TitleUnicode:{clean(meta['title'])}
Artist:{clean(meta['artist'])}
ArtistUnicode:{clean(meta['artist'])}
Creator:Mania Chart Studio
Version:{clean(chart['name'])} - {clean(chart['style'])} (AI draft)
Source:{clean(meta.get('source', ''))}
Tags:4k ai draft unranked mania-chart-studio
BeatmapID:0
BeatmapSetID:-1

[Difficulty]
HPDrainRate:7
CircleSize:4
OverallDifficulty:7
ApproachRate:5
SliderMultiplier:1.4
SliderTickRate:1

[Events]
0,0,"cover.jpg",0,0

[TimingPoints]
{round(chart['anchor'] + chart['offset'], 3)},{60000 / chart['bpm']:.10f},4,1,0,70,1,0

[HitObjects]
""" + "\n".join(notes) + "\n"


def statistics(meta, chart):
    import rosu_pp_py as rosu
    stars = rosu.Difficulty().calculate(rosu.Beatmap(content=osu_text(meta, chart))).stars
    counts = [sum(n["lane"] == lane for n in chart["notes"]) for lane in range(4)]
    return {"stars": round(stars, 2), "notes": len(chart["notes"]), "lanes": counts,
            "ln": sum(n["end"] > n["t"] for n in chart["notes"])}


def cover(meta):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1280, 720), "#101116")
    d = ImageDraw.Draw(img)
    for i in range(4):
        x = 760 + i * 105
        d.rectangle((x, 0, x + 1, 720), fill="#373a45")
        for j in range(5):
            y = 50 + ((j * 139 + i * 91) % 600)
            d.rectangle((x + 8, y, x + 90, y + 12), fill="#ff3e57" if i in (0, 3) else "#ecebf1")
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 46)
        small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 26)
    except OSError:
        font = small = ImageFont.load_default()
    d.text((56, 70), "G4T0XX / MANIA CHART STUDIO", fill="#ff3e57", font=small)
    title = clean(meta["title"])
    lines = []
    while title:
        cut = min(25, len(title))
        lines.append(title[:cut])
        title = title[cut:]
    d.multiline_text((56, 230), "\n".join(lines[:5]), fill="#ecebf1", font=font, spacing=8)
    d.text((56, 630), "4 KEYS  /  AI DRAFT  /  UNRANKED", fill="#b5b6c2", font=small)
    result = io.BytesIO()
    img.save(result, format="JPEG", quality=90)
    return result.getvalue()


def export(folder, project):
    meta = project["meta"]
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(folder / "audio.wav", "audio.wav")
        archive.writestr("cover.jpg", cover(meta))
        for i, chart in enumerate(project["charts"]):
            validate_chart(chart, project["analysis"]["duration"])
            archive.writestr(f"Mania Chart Studio [{i + 1}].osu", osu_text(meta, chart))
        archive.writestr("AI-DRAFT.txt", "Generated draft. Not ranked eligible. Review timing and notes manually.\n")
    return result.getvalue()
