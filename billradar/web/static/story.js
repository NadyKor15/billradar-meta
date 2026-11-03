// Scroll story: episodes 1-3 pin while they play and get --p from 0 to 1 by scroll. Episode 4 plays by itself once
// its letter is half in view: the letter types (≈3 s), the pen signs, then the envelope and the buttons. It plays again
// when the reader scrolls back up past it and returns. Reduced motion or no JS: every episode shows its end state.
(() => {
  const root = document.getElementById("story");
  if (!root || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  root.classList.add("live");
  const eps = [...root.querySelectorAll(".ep:not(.ep4)")];
  const big = root.querySelector(".big"), to = +(big?.dataset.to || 0);
  const calls = root.querySelector(".receipt-line .calls"), usd = root.querySelector(".receipt-line .usd");  // count up to the receipt
  const clamp = (x) => Math.max(0, Math.min(1, x));
  let ticking = false;
  // the gold thread of the Muse Spark episode goes from one marked line to the other, wherever the sheets stand
  const arc = root.querySelector(".arc"), thread = arc?.querySelector(".thread"), card = arc?.querySelector(".link-card");
  const drawThread = () => {
    const [a, b] = [arc.querySelector('[data-link="a"] .hl'), arc.querySelector('[data-link="b"] .hl')];
    if (!a || !b) return;
    const box = arc.getBoundingClientRect(), ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const ax = ra.right - box.left, ay = ra.top + ra.height / 2 - box.top, bx = rb.left - box.left, by = rb.top + rb.height / 2 - box.top;
    const small = box.width < 760, cx = box.width * (small ? 0.5 : 0.63), cy = box.height * (small ? 0.8 : 0.58), half = small ? 0 : box.width * 0.09;
    thread.setAttribute("viewBox", `0 0 ${box.width} ${box.height}`);
    thread.querySelector("path").setAttribute("d", `M ${ax} ${ay} C ${ax + 150} ${ay + 8}, ${cx - half - 200} ${cy - 34}, ${cx - half} ${cy} L ${cx + half} ${cy + 6} C ${cx + half + 170} ${cy + 26}, ${bx - 110} ${by + 44}, ${bx} ${by}`);
    card?.style.setProperty("left", cx + "px"); card?.style.setProperty("top", cy + "px");
  };
  const frame = () => {
    ticking = false;
    for (const ep of eps) {
      const r = ep.getBoundingClientRect(), run = r.height - innerHeight;
      const p = clamp(run > 0 ? -r.top / run : 1);
      ep.style.setProperty("--p", p.toFixed(4));
      if (ep.classList.contains("ep3") && big && to) big.textContent = "$" + Math.round(to * clamp(p / 0.45)).toLocaleString("en-US");
    }
    if (thread) drawThread();
  };
  if (calls && usd) {  // the receipt counts up once on load, on the first screen, not by scroll (a phone saw "0 calls")
    const t0 = performance.now(), dur = 1200;
    const tick = (t) => {
      const c = clamp((t - t0) / dur);
      calls.textContent = Math.round(+calls.dataset.to * c);
      usd.textContent = "$" + (+usd.dataset.to * c).toFixed(3);
      if (c < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }
  addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }, { passive: true });
  addEventListener("resize", frame);
  frame();

  if (matchMedia("(hover: hover) and (pointer: fine)").matches) {  // a slight tilt after the pointer, desktop only
    root.classList.add("tilt");
    root.addEventListener("pointermove", (e) => {
      const tx = (e.clientX / innerWidth - 0.5) * 2, ty = (e.clientY / innerHeight - 0.5) * 2;
      root.style.setProperty("--tx", tx.toFixed(3)); root.style.setProperty("--ty", ty.toFixed(3));
      root.style.setProperty("--m", Math.min(1, Math.hypot(tx, ty)).toFixed(3));
    }, { passive: true });
  }

  // the first screen: until someone speaks, the sentence writes itself and the wave moves by itself
  const demo = root.querySelector(".vox-demo"), big0 = root.querySelector(".vox-big");
  if (demo && big0) {
    const line = demo.dataset.text; let k = 0, t0 = 0;
    big0.classList.add("idle");
    const type = (now) => {
      if (!big0.classList.contains("idle")) return;
      if (now - t0 > 46) { t0 = now; k = k >= line.length + 70 ? 0 : k + 1; demo.textContent = line.slice(0, k) || "\u00a0"; }
      requestAnimationFrame(type);
    };
    requestAnimationFrame(type);
    big0.addEventListener("click", () => { big0.classList.remove("idle"); demo.textContent = "\u00a0"; }, { once: true });
  }

  const ep4 = root.querySelector(".ep4"), paper = ep4?.querySelector(".letter-paper"), typed = ep4?.querySelector(".typed");
  if (!ep4 || !paper) return;
  const text = typed?.textContent || "", MS = 6500;  // --p .05-.50 types, .55-.77 signs, .82-.96 envelope and buttons
  let start = 0, raf = 0;
  const show = (p) => {
    ep4.style.setProperty("--p", p.toFixed(4));
    if (typed) typed.textContent = text.slice(0, Math.round(text.length * clamp((p - 0.05) / 0.45)));
  };
  const play = (now) => {
    const p = clamp((now - start) / MS);
    show(p);
    raf = p < 1 ? requestAnimationFrame(play) : 0;
  };
  show(0);
  new IntersectionObserver(([e]) => {
    if (e.intersectionRatio >= 0.45 && !start) { start = performance.now(); raf = requestAnimationFrame(play); }
    else if (!e.isIntersecting && e.boundingClientRect.top > 0) { cancelAnimationFrame(raf); start = 0; show(0); }  // scrolled back up past it: ready to play again
  }, { threshold: [0, 0.45] }).observe(paper);
})();
