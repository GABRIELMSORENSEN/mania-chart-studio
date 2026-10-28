"use strict";
const $ = (id) => document.getElementById(id);
let project = null,
  index = 0,
  dirty = false,
  history = [],
  ctx = null,
  buffer = null,
  source = null;
let playing = false,
  position = 0,
  startClock = 0,
  nextNote = 0,
  nextBeat = 0,
  scheduled = new Set(),
  loading = false,
  saving = false;
const storage = {
  get: (key) => {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set: (key, value) => {
    try {
      localStorage.setItem(key, value);
    } catch {}
  },
  remove: (key) => {
    try {
      localStorage.removeItem(key);
    } catch {}
  },
};
const canvas = $("timeline"),
  g = canvas.getContext("2d");
const chart = () => project.charts[index];
const fmt = (t) =>
  `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const time = () =>
  playing
    ? Math.max(0, Math.min(buffer.duration, ctx.currentTime - startClock))
    : position;
async function api(path, options = {}) {
  const response = await fetch(path, {
    signal: AbortSignal.timeout(20000),
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    let data;
    try {
      data = await response.json();
    } catch {
      data = { detail: response.statusText };
    }
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "Dados inválidos. Confira os campos.",
    );
  }
  return response.json();
}
function status(message, error = false) {
  $("editor-status").textContent = message;
  $("editor-status").classList.toggle("error", error);
}
function remember() {
  history.push(JSON.stringify(project.charts));
  if (history.length > 50) history.shift();
  dirty = true;
  $("undo").disabled = false;
}
function pause() {
  if (playing) {
    position = time();
    playing = false;
    try {
      source.stop();
    } catch {}
    for (const node of scheduled) {
      try {
        node.stop();
      } catch {}
    }
    scheduled.clear();
  }
  $("play").textContent = "▶ Ouvir";
}
function seek(value) {
  const was = playing;
  pause();
  position = Math.max(0, Math.min(buffer?.duration || 0, value));
  if (was) play();
}
async function play() {
  if (!buffer) return;
  if (playing) {
    pause();
    return;
  }
  await ctx.resume();
  if (position >= buffer.duration) position = 0;
  source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(ctx.destination);
  const begin = ctx.currentTime + 0.06;
  startClock = begin - position;
  nextNote = chart().notes.findIndex(
    (n) => (n.t + chart().offset) / 1000 >= position,
  );
  if (nextNote < 0) nextNote = chart().notes.length;
  nextBeat = Math.max(
    0,
    Math.ceil(
      (position * 1000 - chart().anchor - chart().offset) /
        (60000 / chart().bpm),
    ),
  );
  playing = true;
  source.start(begin, position);
  $("play").textContent = "Ⅱ Pausar";
}
function tick(when, beat = false) {
  const oscillator = ctx.createOscillator(),
    gain = ctx.createGain();
  oscillator.type = "sine";
  oscillator.frequency.value = beat ? 1450 : 880;
  gain.gain.setValueAtTime(beat ? 0.07 : 0.11, when);
  gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.025);
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  oscillator.start(when);
  oscillator.stop(when + 0.03);
  scheduled.add(oscillator);
  oscillator.onended = () => {
    scheduled.delete(oscillator);
    oscillator.disconnect();
    gain.disconnect();
  };
}
setInterval(() => {
  if (!playing || !project) return;
  const c = chart(),
    horizon = ctx.currentTime + 0.1;
  while (nextNote < c.notes.length) {
    const n = c.notes[nextNote],
      at = startClock + (n.t + c.offset) / 1000;
    if (at > horizon) break;
    if (at >= ctx.currentTime && $("hits").checked) tick(at);
    nextNote++;
  }
  const period = 60 / c.bpm;
  while (
    startClock + (c.anchor + c.offset) / 1000 + nextBeat * period <
    horizon
  ) {
    const at = startClock + (c.anchor + c.offset) / 1000 + nextBeat * period;
    if (at >= ctx.currentTime && $("metro").checked) tick(at, true);
    nextBeat++;
  }
  if (time() >= buffer.duration) pause();
}, 25);
async function library() {
  try {
    const list = await api("/api/projects");
    $("library-list").replaceChildren();
    if (!list.length) {
      const p = document.createElement("p");
      p.className = "hint";
      p.textContent = "Seus projetos salvos aparecerão aqui.";
      $("library-list").append(p);
    }
    for (const item of list) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = item.title;
      const small = document.createElement("small");
      small.textContent = item.artist;
      button.append(small);
      button.onclick = () => openProject(item.id);
      $("library-list").append(button);
    }
  } catch (e) {
    $("library-list").textContent = `Biblioteca indisponível: ${e.message}`;
  }
}
async function openProject(id) {
  if (loading) return;
  loading = true;
  try {
    if (dirty) await save();
    pause();
    status("Carregando áudio…");
    const next = await api(`/api/projects/${id}`);
    ctx = ctx || new AudioContext({ latencyHint: "interactive" });
    const response = await fetch(`/api/projects/${id}/audio`);
    if (!response.ok) throw Error("Áudio indisponível.");
    const nextBuffer = await ctx.decodeAudioData(await response.arrayBuffer());
    project = next;
    buffer = nextBuffer;
    position = 0;
    index = 0;
    history = [];
    dirty = false;
    $("undo").disabled = true;
    $("empty").hidden = true;
    $("project").hidden = false;
    $("track-title").textContent = project.meta.title;
    $("track-artist").textContent = project.meta.artist;
    document.title = `${project.meta.title} — Mania Chart Studio`;
    $("seek").max = buffer.duration;
    renderChart();
    status("Confira o início, o meio e o final com Hits e metrônomo.");
  } catch (e) {
    status(e.message, true);
    $("form-error").textContent = e.message;
  } finally {
    loading = false;
  }
}
function renderChart() {
  const c = chart();
  $("difficulty-tabs").replaceChildren();
  project.charts.forEach((item, i) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${item.name} · ${item.stats?.stars ?? "?"}★`;
    button.setAttribute("aria-pressed", String(i === index));
    button.onclick = () => {
      pause();
      index = i;
      renderChart();
    };
    $("difficulty-tabs").append(button);
  });
  $("bpm").value = c.bpm;
  $("offset").value = c.offset;
  $("anchor").value = c.anchor;
  const counts = [0, 0, 0, 0];
  c.notes.forEach((n) => counts[n.lane]++);
  $("metrics").textContent =
    `${c.notes.length.toLocaleString("pt-BR")} notas · Colunas ${counts.join(" / ")} · ${c.stats?.stars ?? "?"}★ calculadas${dirty ? " · Alterações pendentes" : ""}`;
  $("tempo-warning").textContent =
    project.analysis.tempo_stability < 0.85
      ? "Pulso variável ou incerto. A grade de BPM único pode se desalinhar; revise os trechos antes de exportar."
      : "BPM estimado pela IA. Ouça os acertos ao longo da faixa e revise as notas antes de exportar.";
}
function windowStart() {
  return Math.max(0, time() - Number($("zoom").value) * 0.18);
}
function draw() {
  requestAnimationFrame(draw);
  const w = canvas.clientWidth,
    h = canvas.clientHeight,
    dpr = devicePixelRatio || 1;
  if (
    canvas.width !== Math.round(w * dpr) ||
    canvas.height !== Math.round(h * dpr)
  ) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const css = getComputedStyle(document.documentElement),
    color = (name) => css.getPropertyValue(name).trim();
  g.fillStyle = color("--bg");
  g.fillRect(0, 0, w, h);
  if (!project) return;
  const c = chart(),
    span = Number($("zoom").value),
    start = windowStart(),
    x = (t) => 54 + ((t - start) / span) * (w - 64),
    laneH = 47,
    top = 100;
  g.font = "11px Consolas, monospace";
  g.fillStyle = color("--muted");
  for (let lane = 0; lane < 4; lane++) {
    g.fillText(
      ["1  Z", "2  X", "3  ,", "4  ."][lane],
      5,
      top + lane * laneH + 27,
    );
    g.strokeStyle = color("--line");
    g.beginPath();
    g.moveTo(54, top + (lane + 1) * laneH);
    g.lineTo(w, top + (lane + 1) * laneH);
    g.stroke();
  }
  const period = 60 / c.bpm,
    anchor = (c.anchor + c.offset) / 1000;
  for (
    let beat = Math.max(0, Math.floor((start - anchor) / period));
    beat < (start + span - anchor) / period;
    beat++
  ) {
    const at = anchor + beat * period,
      px = x(at);
    if (px < 54) continue;
    g.strokeStyle = color("--line");
    g.beginPath();
    g.moveTo(px, 90);
    g.lineTo(px, h);
    g.stroke();
    if (beat % 4 === 0) g.fillText(fmt(at), px + 3, 88);
  }
  const wave = project.analysis.waveform,
    duration = project.analysis.duration;
  g.strokeStyle = color("--muted");
  g.beginPath();
  for (let px = 54; px < w; px++) {
    const sec = start + ((px - 54) / (w - 64)) * span,
      amp = wave[Math.floor((sec / duration) * wave.length)] || 0;
    g.moveTo(px, 40 - amp * 28);
    g.lineTo(px, 40 + amp * 28);
  }
  g.stroke();
  for (const n of c.notes) {
    const t = (n.t + c.offset) / 1000,
      end = (n.end + c.offset) / 1000;
    if (end < start || t > start + span) continue;
    const px = x(t),
      endX = x(end),
      y = top + n.lane * laneH + 10;
    g.fillStyle = color(n.lane === 0 || n.lane === 3 ? "--accent" : "--ink");
    g.globalAlpha = 0.35;
    if (end > t)
      g.fillRect(
        Math.max(54, px),
        y + 6,
        Math.max(4, endX - Math.max(54, px)),
        12,
      );
    g.globalAlpha = 1;
    if (px >= 54) g.fillRect(px, y, 5, 25);
  }
  g.fillStyle = color("--focus");
  g.fillRect(x(time()), 0, 2, h);
  $("clock").value = `${fmt(time())} / ${fmt(buffer.duration)}`;
  $("seek").value = time();
}
canvas.addEventListener("click", (event) => {
  if (!project) return;
  pause();
  const rect = canvas.getBoundingClientRect(),
    px = event.clientX - rect.left,
    py = event.clientY - rect.top,
    lane = Math.floor((py - 100) / 47);
  if (lane < 0 || lane > 3 || px < 54) return;
  const t =
    (windowStart() +
      ((px - 54) / (rect.width - 64)) * Number($("zoom").value)) *
      1000 -
    chart().offset;
  const near = chart().notes.findIndex(
    (n) =>
      n.lane === lane &&
      Math.abs(n.t - t) <
        ((Number($("zoom").value) * 1000) / (rect.width - 64)) * 8,
  );
  remember();
  if (near >= 0) chart().notes.splice(near, 1);
  else
    chart().notes.push({
      t: Math.round(t),
      end: Math.round(t + (event.shiftKey ? 300 : 0)),
      lane,
      origin: "manual",
      strength: 1,
    });
  chart().notes.sort((a, b) => a.t - b.t);
  renderChart();
  status("Edição pendente. Salve para recalcular as estrelas.");
});
$("generate").onsubmit = async (event) => {
  event.preventDefault();
  const url = $("url").value.trim();
  $("form-error").textContent = "";
  if (
    !/^https:\/\/(?:youtu\.be|(?:(?:www|m|music)\.)?youtube\.com)\//i.test(url)
  ) {
    $("form-error").textContent = "Cole o link HTTPS de um vídeo do YouTube.";
    $("url").setAttribute("aria-invalid", "true");
    $("url").focus();
    return;
  }
  $("url").removeAttribute("aria-invalid");
  $("generate-button").disabled = true;
  $("generate").setAttribute("aria-busy", "true");
  try {
    if (dirty) await save();
    const job = await api("/api/generate", {
      method: "POST",
      body: JSON.stringify({ url, style: $("style").value }),
    });
    storage.set("mania-active-job", job.id);
    await poll(job.id);
  } catch (e) {
    $("form-error").textContent = e.message;
  } finally {
    $("generate-button").disabled = false;
    $("generate").removeAttribute("aria-busy");
  }
};
async function poll(id) {
  while (true) {
    const job = await api(`/api/jobs/${id}`);
    $("job-status").textContent = job.message;
    if (job.state === "done") {
      storage.remove("mania-active-job");
      await library();
      await openProject(id);
      return;
    }
    if (job.state === "error") {
      storage.remove("mania-active-job");
      throw Error(job.message);
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}
async function save() {
  if (!project) return;
  if (saving) throw Error("Aguarde o salvamento atual.");
  saving = true;
  $("save").disabled = true;
  pause();
  status("Salvando…");
  try {
    const saved = await api(`/api/projects/${project.id}`, {
      method: "PUT",
      body: JSON.stringify({ charts: project.charts }),
    });
    project = saved;
    dirty = false;
    renderChart();
    status("Projeto salvo no seu PC. Estrelas recalculadas.");
    return saved;
  } finally {
    saving = false;
    $("save").disabled = false;
  }
}
$("save").onclick = async () => {
  try {
    await save();
  } catch (e) {
    status(e.message, true);
  }
};
$("export").onclick = async () => {
  if (!project) return;
  $("export").disabled = true;
  try {
    await save();
    status("Preparando pacote…");
    const response = await fetch(`/api/projects/${project.id}/export`);
    if (!response.ok) {
      const err = await response.json();
      throw Error(err.detail);
    }
    const url = URL.createObjectURL(await response.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = "Mania-Chart-Studio.osz";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    status("Pacote exportado. Abra o .osz para importar no osu!.");
  } catch (e) {
    status(e.message, true);
  } finally {
    $("export").disabled = false;
  }
};
$("play").onclick = () => play().catch((e) => status(e.message, true));
$("back").onclick = () => seek(time() - 3);
$("forward").onclick = () => seek(time() + 3);
$("seek").oninput = () => seek(Number($("seek").value));
$("apply-timing").onclick = () => {
  if (!project) return;
  const bpm = Number($("bpm").value),
    offset = Number($("offset").value),
    anchor = Number($("anchor").value);
  if (
    !Number.isFinite(bpm) ||
    bpm < 20 ||
    bpm > 500 ||
    !Number.isFinite(offset) ||
    Math.abs(offset) > 5000 ||
    !Number.isFinite(anchor)
  ) {
    status("Confira BPM, início da grade e offset.", true);
    return;
  }
  pause();
  remember();
  Object.assign(chart(), { bpm, offset, anchor });
  renderChart();
  status("Ajuste aplicado. Ouça antes de salvar.");
};
$("undo").onclick = () => {
  if (!history.length) return;
  pause();
  project.charts = JSON.parse(history.pop());
  dirty = true;
  $("undo").disabled = !history.length;
  renderChart();
  status("Última edição desfeita.");
};
function editNote(remove) {
  if (!project) return;
  const t = Number($("note-time").value),
    lane = Number($("note-lane").value),
    length = Number($("note-length").value);
  if (!Number.isFinite(t) || t < 0 || !Number.isFinite(length) || length < 0) {
    status("Informe tempo e duração válidos.", true);
    return;
  }
  pause();
  const at = chart().notes.findIndex(
    (n) => n.lane === lane && Math.abs(n.t - t) <= 40,
  );
  if (remove && at < 0) {
    status("Nenhuma nota encontrada a até 40 ms desse tempo.", true);
    return;
  }
  remember();
  if (remove) chart().notes.splice(at, 1);
  else
    chart().notes.push({
      t,
      end: t + length,
      lane,
      origin: "manual",
      strength: 1,
    });
  chart().notes.sort((a, b) => a.t - b.t);
  renderChart();
  status(
    remove ? "Nota removida. Desfazer está disponível." : "Nota inserida.",
  );
}
$("add-note").onclick = () => editNote(false);
$("remove-note").onclick = () => editNote(true);
document.addEventListener("keydown", (event) => {
  if (
    event.isComposing ||
    ["INPUT", "SELECT", "TEXTAREA", "BUTTON", "SUMMARY"].includes(
      document.activeElement.tagName,
    )
  )
    return;
  if (event.code === "Space" && project) {
    event.preventDefault();
    play().catch((e) => status(e.message, true));
  }
});
window.addEventListener("beforeunload", (event) => {
  if (dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) pause();
});
// Controls stay disabled until their handlers have been attached successfully.
for (const id of [
  "play",
  "back",
  "forward",
  "apply-timing",
  "add-note",
  "remove-note",
  "save",
  "export",
])
  $(id).disabled = false;
library();
draw();
const pending = storage.get("mania-active-job");
if (pending) {
  $("generate-button").disabled = true;
  poll(pending)
    .catch((e) => {
      $("form-error").textContent = e.message;
      storage.remove("mania-active-job");
    })
    .finally(() => {
      $("generate-button").disabled = false;
    });
}
