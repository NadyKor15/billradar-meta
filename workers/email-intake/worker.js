// BillRadar email intake: Cloudflare Email Routing hands every message for intake+<token>@<subdomain>
// to this Worker; it signs the raw message and posts it to BillRadar, which checks the signature, the
// address and the sender. If BillRadar says no, the mail is rejected back to the sender.
// Settings (wrangler secrets/vars, never in this file): INTAKE_URL, INTAKE_SECRET.
// Email Workers API: https://developers.cloudflare.com/email-service/api/route-emails/email-handler/

const MAX_BYTES = 25 * 1024 * 1024;

async function sign(secret, timestamp, raw) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const head = new TextEncoder().encode(timestamp + ".");
  const data = new Uint8Array(head.length + raw.byteLength);
  data.set(head, 0);
  data.set(new Uint8Array(raw), head.length);
  const mac = await crypto.subtle.sign("HMAC", key, data);
  return [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export default {
  async email(message, env) {
    if (!env.INTAKE_URL || !env.INTAKE_SECRET) {
      message.setReject("BillRadar email intake is not set up");
      return;
    }
    if (message.rawSize > MAX_BYTES) {
      message.setReject("Message is larger than 25 MB");
      return;
    }
    const raw = await new Response(message.raw).arrayBuffer();
    const timestamp = String(Math.floor(Date.now() / 1000));
    const res = await fetch(env.INTAKE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "message/rfc822",
        "X-BillRadar-Timestamp": timestamp,
        "X-BillRadar-Signature": await sign(env.INTAKE_SECRET, timestamp, raw),
        "X-BillRadar-To": message.to,
        "X-BillRadar-From": message.from,
      },
      body: raw,
    });
    if (res.status !== 202) {
      message.setReject(`BillRadar did not accept this message (${res.status})`);
    }
  },
};
