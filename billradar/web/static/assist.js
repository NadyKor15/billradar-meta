// Help that is on every page: larger text, reading aloud on your computer, and the voice helper.
// Voice goes to Muse Voice Transcribe as 16 kHz mono WAV (the API takes WAV only) through /voice/intake or
// /cases/{id}/ask/voice; reading aloud is the browser's own speechSynthesis, nothing leaves the device.
(() => {
  const root = document.documentElement, KEY = "billradar.larger";
  const larger = document.getElementById("larger");
  const setLarger = (on) => {
    root.classList.toggle("larger", on);
    if (larger) larger.setAttribute("aria-pressed", on ? "true" : "false");
    try { localStorage.setItem(KEY, on ? "1" : "0"); } catch (e) {}
  };
  if (larger) {
    larger.setAttribute("aria-pressed", root.classList.contains("larger") ? "true" : "false");
    larger.addEventListener("click", () => setLarger(!root.classList.contains("larger")));
  }

  // Read to me: <button data-read="selector"> speaks the text of that part of the page.
  const speak = (text, btn) => {
    if (!("speechSynthesis" in window)) return false;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = (btn && btn.closest("[lang]")?.lang) || root.lang || "en";
    u.rate = 0.95;
    if (btn) {
      const label = btn.querySelector("span") || btn, was = label.textContent;
      btn.classList.add("speaking"); label.textContent = "Stop reading";
      u.onend = u.onerror = () => { btn.classList.remove("speaking"); label.textContent = was; };
    }
    speechSynthesis.speak(u);
    return true;
  };
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-read]");
    if (!b) return;
    if (b.classList.contains("speaking")) { speechSynthesis.cancel(); return; }
    const text = [...document.querySelectorAll(b.dataset.read)].map((el) => el.innerText).join(". ").replace(/\s+/g, " ");
    if (text) speak(text, b);
  });
  if (!("speechSynthesis" in window)) document.querySelectorAll("[data-read]").forEach((b) => { b.hidden = true; });

  // ---- recording: 16 kHz mono 16-bit WAV in the browser ----
  const wav = (samples, rate) => {
    const buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true);
    v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 0x7fff, true);
    return new Blob([buf], { type: "audio/wav" });
  };
  const record = async (onLevel) => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const ctx = new AudioContext(), src = ctx.createMediaStreamSource(stream), node = ctx.createScriptProcessor(4096, 1, 1), chunks = [];
    node.onaudioprocess = (e) => {
      const d = e.inputBuffer.getChannelData(0); chunks.push(new Float32Array(d));
      onLevel(Math.min(1, Math.sqrt(d.reduce((n, x) => n + x * x, 0) / d.length) * 6));
    };
    src.connect(node); node.connect(ctx.destination);
    return async () => {
      node.disconnect(); stream.getTracks().forEach((t) => t.stop());
      const all = new Float32Array(chunks.reduce((n, c) => n + c.length, 0)); let o = 0;
      chunks.forEach((c) => { all.set(c, o); o += c.length; });
      const off = new OfflineAudioContext(1, Math.ceil(all.length * 16000 / ctx.sampleRate), 16000);
      const b = off.createBuffer(1, all.length, ctx.sampleRate); b.copyToChannel(all, 0);
      const s = off.createBufferSource(); s.buffer = b; s.connect(off.destination); s.start();
      const pcm = (await off.startRendering()).getChannelData(0); ctx.close();
      return wav(pcm, 16000);
    };
  };

  // ---- the voice helper: one .vox block per place on the page ----
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; };
  const answer = (out, j) => {
    if (j.transcript) out.append(el("p", "vox-said", "“" + j.transcript + "”"));
    if (j.chips) {  // intake: what she said becomes the same chips as on the upload page
      const q = j.chips.map((c) => "context=" + encodeURIComponent(c)).join("&");
      document.querySelectorAll("[data-chip]").forEach((c) => c.classList.toggle("on", j.chips.includes(c.dataset.chip)));
      const go = el("a", "btn primary", "Check my bills"); go.href = "/upload" + (q ? "?" + q : ""); out.append(go);
      return;
    }
    if (j.source === "none") {  // not in the case: the ready sentence, nothing made up
      out.append(el("p", "vox-answer", j.text || ""));
      if (j.say) out.append(el("p", "vox-say", j.say));
    } else if (j.source === "web") {  // a word-for-word quote from the web, marked as such; no amounts beside it
      const q = el("a", "vox-quote web", "“" + j.text + "”"); q.href = j.web.url; q.target = "_blank"; q.rel = "noopener";
      out.append(el("span", "vox-web", j.web.label), q);
    } else out.append(el("p", "vox-answer", j.text || ""));
    (j.citations || []).forEach((c) => {
      const q = el(c.url ? "a" : "blockquote", "vox-quote", "“" + c.quote + "” · " + c.label);
      if (c.url) { q.href = c.url; q.target = "_blank"; q.rel = "noopener"; }
      out.append(q);
    });
    if (j.text && "speechSynthesis" in window) {
      const r = el("button", "vox-read"); r.type = "button"; r.append(el("span", "", "Read aloud"));
      r.addEventListener("click", () => { if (r.classList.contains("speaking")) speechSynthesis.cancel(); else speak(j.text, r); });
      out.append(r);
    }
  };
  const mount = (box) => {
    const url = box.dataset.url, sample = box.dataset.sample, live = box.dataset.live === "1";
    const mic = box.querySelector(".vox-mic"), status = box.querySelector(".vox-status"), out = box.querySelector(".vox-out");
    const sampleBtn = box.querySelector(".vox-sample"), wave = box.querySelector(".vox-wave");
    const lang = () => box.querySelector("input[type=radio]:checked")?.value || "en";
    let stop = null;
    const send = async (blob, spoken = lang()) => {
      status.textContent = "Reading what you said…"; out.textContent = "";
      try {
        const r = await fetch(`${url}?lang=${spoken}&consent=1`, { method: "POST", body: blob, headers: { "Content-Type": "audio/wav" } });
        const j = await r.json();
        status.textContent = r.ok ? (j.replayed ? "A recorded sample." : "") : (j.error || "That did not work.");
        if (r.ok) answer(out, j);
      } catch (e) { status.textContent = "That did not work: " + e.message; }
    };
    if (mic) mic.addEventListener("click", async () => {
      if (stop) {
        const end = stop; stop = null; box.classList.remove("rec"); wave?.style.setProperty("--lvl", 0);
        return send(await end());
      }
      try {
        stop = await record((l) => wave?.style.setProperty("--lvl", l.toFixed(2)));
        box.classList.add("rec"); status.textContent = "Listening… tap to stop";
      } catch (e) { status.textContent = "Microphone not available: " + e.message; }
    });
    if (sampleBtn) sampleBtn.addEventListener("click", async () => send(await (await fetch(sample)).blob(), "en"));  // the samples are spoken in English, whatever is picked
    if (!live && mic) mic.disabled = true;
  };
  document.querySelectorAll(".vox").forEach(mount);
  window.billradarAnswer = answer;  // the typed question on the case screen shows its answer the same way

  // the sum on the case counts up once; without JS it is simply there
  const gold = document.querySelector(".hero-card h1 .gold");
  const m = gold && /^\$([\d,]+)$/.exec(gold.textContent.trim());
  if (m && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const to = +m[1].replace(/,/g, ""), t0 = performance.now(), MS = 900;
    const tick = (now) => {
      const k = Math.min(1, (now - t0) / MS);
      gold.textContent = "$" + Math.round(to * (1 - (1 - k) ** 3)).toLocaleString("en-US");
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  // the model calls of the case, played back in order when the list comes into view; the numbers are the run's own
  const feed = document.getElementById("feed");
  if (feed && "IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const rows = [...feed.querySelectorAll("li")], count = feed.querySelector(".feed-count"), sum = feed.querySelector(".feed-sum"), again = feed.querySelector(".feed-play");
    const total = rows.reduce((n, r) => n + +r.dataset.usd, 0), list = feed.querySelector("ol");
    let timer = 0;
    const play = () => {
      clearTimeout(timer); feed.classList.add("playing"); again.hidden = true;
      rows.forEach((r) => r.classList.remove("seen"));
      let i = 0, usd = 0;
      const next = () => {
        if (i >= rows.length) { sum.textContent = "$" + total.toFixed(3); feed.classList.remove("playing"); again.hidden = false; return; }
        const r = rows[i]; r.classList.add("seen"); usd += +r.dataset.usd; i += 1;
        count.textContent = i + (i === 1 ? " call" : " calls"); sum.textContent = "$" + usd.toFixed(3);
        list.scrollTop = list.scrollHeight;
        timer = setTimeout(next, Math.min(900, 180 + +r.dataset.s * 22));
      };
      next();
    };
    feed.classList.add("live");
    again.addEventListener("click", play);
    new IntersectionObserver(([e], o) => { if (e.isIntersecting) { o.disconnect(); play(); } }, { threshold: 0.4 }).observe(feed);
  }

  const dock = document.getElementById("vox-dock");
  if (dock) {
    const open = dock.querySelector(".vox-open");
    open.addEventListener("click", () => {
      const on = dock.classList.toggle("open");
      open.setAttribute("aria-expanded", on ? "true" : "false");
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") dock.classList.remove("open"); });
  }
})();
