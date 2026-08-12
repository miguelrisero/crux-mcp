# Security

## Reporting a vulnerability

Open a [private security advisory](https://github.com/miguelrisero/crux-mcp/security/advisories/new). Please do not open a public issue for anything exploitable.

## What this server can and cannot do

It makes read-only `POST` requests to `chromeuxreport.googleapis.com` and returns the response. It has no write path, no filesystem access, and no shell access. Every tool is annotated `readOnlyHint: true`, `destructiveHint: false`.

The data it reads is **public aggregate data** about website performance. It contains no personal data and nothing specific to your users — CrUX aggregates across many real Chrome users and suppresses anything below a traffic threshold.

## Handling the API key

`CRUX_API_KEY` is a **bearer credential**. Anyone holding it can spend your quota against your Google Cloud project.

**Restrict it.** In the Cloud Console: *Credentials → your key → Edit → API restrictions → Restrict key → Chrome UX Report API*. Scoped that way, a leaked key can only read public performance data — a nuisance rather than an incident.

**Keep it out of your repo and out of client configs where you can.** Reading it from a shared secrets file at launch keeps it out of the MCP config entirely:

```json
{
  "command": "sh",
  "args": ["-c", "set -a; . \"$HOME/.secrets/mcp-keys.env\"; set +a; exec uvx crux-mcp"],
  "env": {}
}
```

**Rotate it** by deleting the key in the Cloud Console and creating a new one. There is no revocation list; deletion is the revocation.

## What the server logs

Nothing. It does not write logs, does not phone home, and does not persist anything between calls. The API key is read from the environment at startup and used only in the query string of requests to Google.

## Dependencies

One runtime dependency: `mcp`. HTTP uses the standard library (`urllib`), deliberately, so the dependency surface stays small. Dependabot watches both the Python packages and the GitHub Actions used in CI.
