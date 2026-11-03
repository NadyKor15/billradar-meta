# Email intake Worker

Forwards mail sent to `intake+<token>@<intake subdomain>` to BillRadar, signed with HMAC-SHA256 over `"<unix time>." + raw message` (hex), in `X-BillRadar-Signature` with `X-BillRadar-Timestamp`, plus the envelope `X-BillRadar-To` and `X-BillRadar-From`. BillRadar answers 202 when it takes the message; anything else rejects the mail back to the sender.

Setup (by the deploy lane, after an owner's yes): Email Routing on the subdomain (literal rule `intake@<subdomain>` to this Worker, subaddressing on), `INTAKE_URL` and the `INTAKE_SECRET` secret. On the app: `BILLRADAR_INTAKE_DOMAIN`, `BILLRADAR_INTAKE_PATH` (default `/intake/email`), `BILLRADAR_INTAKE_LOCAL` (default `intake`), `BILLRADAR_INTAKE_SECRET`. Catch-all rules exist only on the apex domain, so per-case addresses use plus addressing.
