// Help during a live call: consent first, then the phone's audio goes to the server as 16 kHz mono PCM in 80 ms frames.
// The server answers with what was said, what to say next, and what it wrote down (billradar/call_assist.py).
(() => {
  const box = document.getElementById("livecall"), open = document.getElementById("live-start");
  if (!box || !open) return;
  const $ = (s) => box.querySelector(s), el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; };
  const base = location.pathname.replace(/\/$/, "");
  const lang = () => box.querySelector("input[name=call-lang]:checked")?.value || "en";
  const sample = box.dataset.live !== "1";  // no live voice on this copy: the recorded call plays, no microphone is asked for
  let ws = null, mic = null, paused = false, tick = 0, seconds = 0;
  const step = (name) => box.querySelectorAll("[data-step]").forEach((s) => { s.hidden = s.dataset.step !== name; });
  const clock = () => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  const say = (cls, node) => { const c = $(".lc-tips"); c.prepend(node); node.classList.add(cls); while (c.children.length > 4) c.lastChild.remove(); };

  const turn = (d) => {
    const who = d.who === "you" ? "you" : "them", row = el("div", "lc-turn " + who);
    row.append(el("span", "lc-av", who === "you" ? "Y" : "H"));
    const body = el("div", "lc-bubble");
    body.append(el("small", "", (who === "you" ? "You" : "Them") + " · " + clock()), el("p", "", d.text));
    row.append(body);
    const log = $(".lc-log"); log.append(row); log.scrollTop = log.scrollHeight;
    // help for this turn came before the turn itself: the card now says which words it answers
    document.querySelectorAll(`.lc-tips [data-turn="${d.turn_id}"]`).forEach((card) => {
      if (who === "you" || card.querySelector(".lc-they")) return;
      const said = (d.text || "").trim(), words = said.length > 140 ? said.slice(0, 137) + "…" : said;
      if (words) card.prepend(el("p", "lc-they", "They said: “" + words + "”"));
    });
  };
  const handle = (m) => {
    const d = m.data || {};
    if (m.kind === "started") {
      if (d.sample) { box.classList.add("on"); $(".lc-status").textContent = "A recorded sample call."; tick = setInterval(() => { seconds++; $(".lc-clock").textContent = clock(); }, 1000); }
      else streamMic().catch((e) => fail("Microphone not available: " + e.message));
    }
    else if (m.kind === "partial") $(".lc-partial").textContent = d.text || "";
    else if (m.kind === "turn") { $(".lc-partial").textContent = ""; turn(d); }
    else if (m.kind === "suggestion") {
      const card = el("article", "lc-say");
      card.append(el("p", "lc-they", "They said: “" + d.they_say + "”"));
      const p = el("p", "lc-line"); p.append(el("b", "", "Say: "), d.say); card.append(p);
      (d.refs || []).forEach((r) => { const c = el("span", "law", r.label || r); if (r.quote) c.title = r.quote; card.append(c); if (r.quote) card.append(el("q", "lc-q", r.quote)); });
      say("in", card);
    } else if (m.kind === "web") {  // quoted word for word from the web, marked as such; no amounts beside it
      const card = el("article", "lc-web"); card.dataset.turn = d.turn_id; card.append(el("span", "vox-web", d.label));
      const a = el("a", "vox-quote web", "“" + d.quote + "”"); a.href = d.url; a.target = "_blank"; a.rel = "noopener"; card.append(a);
      say("in", card);
    } else if (m.kind === "no_answer") {
      const card = el("article", "lc-none"); card.dataset.turn = d.turn_id; card.append(el("p", "", d.text)); if (d.say) card.append(el("p", "lc-line", d.say));
      say("in", card);
    } else if (m.kind === "captured") {
      const row = box.querySelector(`[data-field="${d.field}"]`);
      if (row && d.field !== "promise") row.textContent = d.value;
      else if (d.field === "promise") $(".lc-promises").append(el("li", "", "“" + (d.words || d.value) + "”"));
    } else if (m.kind === "error") fail(d.message || "The call help stopped.");
    else if (m.kind === "closed") finish();
  };
  const fail = (text) => { $(".lc-status").textContent = text; stopMic(); };
  const stopMic = () => {
    if (mic) { mic.node.disconnect(); mic.stream.getTracks().forEach((t) => t.stop()); mic.ctx.close(); mic = null; }
    clearInterval(tick); box.classList.remove("on");
  };
  const finish = () => { stopMic(); $(".lc-status").textContent = sample ? "The recorded call ended." : "Call ended. BillRadar kept no audio; only these notes stay on this page."; };

  const streamMic = async () => {  // resample to 16 kHz, cut into 2 560-byte frames, no WAV header
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const ctx = new AudioContext(), src = ctx.createMediaStreamSource(stream), node = ctx.createScriptProcessor(4096, 1, 1);
    const ratio = ctx.sampleRate / 16000; let held = [], pos = 0;
    node.onaudioprocess = (e) => {
      const d = e.inputBuffer.getChannelData(0); let sum = 0;
      for (; pos < d.length; pos += ratio) held.push(Math.max(-1, Math.min(1, d[Math.floor(pos)])) * 0x7fff);
      pos -= d.length;
      for (let i = 0; i < d.length; i += 32) sum += d[i] * d[i];
      $(".lc-wave").style.setProperty("--lvl", Math.min(1, Math.sqrt(sum / (d.length / 32)) * 6).toFixed(2));
      while (held.length >= 1280) {
        const frame = Int16Array.from(held.splice(0, 1280));
        if (ws?.readyState === 1 && !paused) ws.send(frame.buffer);
      }
    };
    src.connect(node); node.connect(ctx.destination);
    mic = { stream, ctx, node };
    box.classList.add("on"); $(".lc-status").textContent = "We're taking notes as you speak.";
    tick = setInterval(() => { seconds++; $(".lc-clock").textContent = clock(); }, 1000);
  };

  open.addEventListener("click", async () => {
    box.hidden = false; step("consent"); $(".lc-phrase").textContent = "…";
    const r = await fetch(`${base}/consent?lang=${lang()}`);
    const j = await r.json().catch(() => ({}));
    $(".lc-phrase").textContent = r.ok ? j.phrase : (j.error || "The call help is not available here.");
    $("#lc-agreed").disabled = !r.ok;
  });
  $("#lc-agreed").addEventListener("click", () => {
    step("call"); seconds = 0; $(".lc-clock").textContent = "00:00"; $(".lc-status").textContent = "Connecting…";
    ws = new WebSocket(location.origin.replace(/^http/, "ws") + base + "/live");
    ws.onopen = () => ws.send(JSON.stringify({ type: "start", lang: sample ? "en" : lang(), consent: true, sample }));
    ws.onmessage = (e) => handle(JSON.parse(e.data));
    ws.onclose = (e) => { if (e.code === 4404) fail("This case is not here any more."); stopMic(); };
  });
  $("#lc-pause")?.addEventListener("click", (e) => { paused = !paused; e.currentTarget.textContent = paused ? "Resume listening" : "Pause listening"; });
  $("#lc-end").addEventListener("click", () => { if (ws?.readyState === 1) ws.send(JSON.stringify({ type: "stop" })); finish(); });
  box.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => { if (ws?.readyState === 1) ws.send(JSON.stringify({ type: "stop" })); stopMic(); box.hidden = true; }));
})();
