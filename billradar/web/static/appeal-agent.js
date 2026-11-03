// Muse Spark fills the insurer's portal from the case and stops. Only the family's press of Send lets it submit.
(() => {
  const box = document.getElementById("agent");
  if (!box) return;
  const url = box.dataset.url, $ = (s) => box.querySelector(s);
  const go = $("#agent-go"), send = $("#agent-send"), state = $(".agent-state"), stop = $(".agent-stop"), note = $(".agent-note");
  const WORDS = { filling: "The agent is filling the form…", ready: "Stopped before Send. You decide.", sending: "Sending…" };
  const paint = (j) => {
    const shots = j.shots || 0, blocked = (j.mismatches || []).length > 0 || j.state === "failed";
    state.textContent = j.replayed && j.state === "sent" ? "" : (WORDS[j.state] || (j.state === "sent" ? "Sent." : ""));
    if (shots) {
      const last = `${url}/shot/${shots - 1}.png`, a = $(".agent-shot");
      a.hidden = false; a.href = last; a.querySelector("img").src = last;
      $(".agent-strip").replaceChildren(...[...Array(shots).keys()].map((n) => {
        const li = document.createElement("li"), im = document.createElement("img");
        im.src = `${url}/shot/${n}.png`; im.alt = ""; im.loading = "lazy"; li.append(im); return li;
      }));
    }
    $(".agent-filled").replaceChildren(...Object.entries(j.filled || {}).flatMap(([k, v]) => {
      const dt = document.createElement("dt"), dd = document.createElement("dd");
      dt.textContent = k.replace(/_/g, " "); dd.textContent = v; return [dt, dd];
    }));
    stop.textContent = blocked ? [j.stopped, ...(j.mismatches || [])].filter(Boolean).join(" · ") : "";
    send.hidden = !(j.state === "ready" && !blocked);
    if (j.state === "sent" && !j.replayed && j.confirmation) note.textContent = "Confirmation: " + j.confirmation;
    if (j.note) note.textContent = j.note;
    go.hidden = ["filling", "ready", "sending", "sent"].includes(j.state);
  };
  const poll = async (opening) => {
    try {
      const r = await fetch(url), j = await r.json().catch(() => ({}));
      if (!r.ok) { state.textContent = j.error || "That did not work."; return; }
      if (opening === true && j.replayed) return;  // a recorded run belongs to the press that played it: the next visitor starts at the button
      paint(j);
      if (j.state === "filling" || j.state === "sending") setTimeout(poll, 2000);
    } catch (e) { if (opening !== true) state.textContent = "The connection dropped. Reload the page to see where the agent stopped."; }
  };
  go.addEventListener("click", async () => {
    go.disabled = true; state.textContent = WORDS.filling;
    const r = await fetch(url, { method: "POST" }), j = await r.json().catch(() => ({}));
    go.disabled = false;
    if (!r.ok) { state.textContent = j.error || "That did not work."; return; }
    paint(j); if (j.state === "filling") setTimeout(poll, 2000);
  });
  send.addEventListener("click", async () => {
    send.disabled = true;
    const r = await fetch(url + "/send", { method: "POST" }), j = await r.json().catch(() => ({}));
    send.disabled = false;
    if (!r.ok) { note.textContent = j.error || "That did not work."; return; }
    paint(j); if (j.state === "sending") setTimeout(poll, 2000);
  });
  poll(true);
})();
