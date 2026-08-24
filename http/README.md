# HTTP request files

Runnable requests for every endpoint this API serves, one file per router
module in [`app/routers/`](../app/routers). They are the hand-testing
counterpart to `tests/` — the suite proves the logic offline, these exercise a
real server over the wire.

They are written for the **VS Code [REST Client][rest-client] extension**
(`humao.rest-client`), which is in
[`.vscode/extensions.json`](../.vscode/extensions.json), so VS Code will offer
to install it on first open. Open any `.http` file and a **Send Request** link
appears above each request.

[rest-client]: https://marketplace.visualstudio.com/items?itemName=humao.rest-client

## Pick an environment first

Bottom-right of the VS Code status bar, or `Ctrl`+`Alt`+`E`:

| Environment | `baseUrl` | For |
| --- | --- | --- |
| `development` | `http://localhost:8000` | The usual one. `uv run fastapi dev` |
| `production` | `https://api.dileepa.dev` | Read-only checks against the live API |

The environments are defined in
[`.vscode/settings.json`](../.vscode/settings.json) under
`rest-client.environmentVariables`, and mirror the per-environment split described in
[`.env.development.example`](../.env.development.example).

> **`production` is the live site.** Its data is what dileepa.dev serves. Run
> the `GET` requests there if you need to; do not run the writes.

## Credentials

Nothing secret is committed. The environments read credentials from your shell
with `{{$processEnv …}}`, so export them before launching VS Code:

```bash
export API_ADMIN_EMAIL="you@example.com"
export API_ADMIN_PASSWORD="…"
export API_BLOG_SYNC_KEY="…"   # only needed for blogs.http and uploads.http
```

VS Code reads the environment it was launched from, so if you export these in a
terminal that is already open, restart VS Code — or launch it from that shell
with `code .`.

If you would rather not export anything, replace `{{adminEmail}}` and
`{{adminPassword}}` in `auth.http` with literal values while you work, and
don't commit that.

## How the token works

REST Client scopes a named request's response to **the file it lives in**, so a
token fetched in `auth.http` is not visible from `projects.http`. Every file
that writes therefore opens with its own sign-in:

```http
# @name login
POST {{baseUrl}}/auth/login
Content-Type: application/json

{ "email": "{{adminEmail}}", "password": "{{adminPassword}}" }

###

@accessToken = {{login.response.body.$.access_token}}
```

Send that request once per file, then every request below it picks up the
token. If you get a `401 missing_token`, the sign-in above hasn't been run in
that file yet — or the access token has expired
(`ACCESS_TOKEN_EXPIRE_MINUTES`, 60 by default), and you should send it again.

## The files

| File | Covers |
| --- | --- |
| [`meta.http`](meta.http) | `/`, `/health`, `/version`, `/docs`, `/api-json` |
| [`auth.http`](auth.http) | Sign in, refresh, profile, and the failure cases |
| [`about.http`](about.http) | The single about record |
| [`profile.http`](profile.http) | experiences, educations, tools, communities, videos |
| [`projects.http`](projects.http) | Projects. New in v2.0.0 |
| [`sessions.http`](sessions.http) | Talks, workshops, webinars. New in v2.0.0 |
| [`blogs.http`](blogs.http) | Blog CRUD and `POST /blogs/sync` |
| [`contact.http`](contact.http) | The contact form, and its tighter rate limit |
| [`uploads.http`](uploads.http) | Cloudinary uploads, including the multipart bodies |

Each file ends with a `failure cases` section. Those are the requests worth
re-running after touching auth, validation or the error envelope: they pin the
status codes and the `{ error: { code, message, details } }` shape, not just
the happy path.

## Two of these reach the outside world

- **`contact.http`** sends a real email through Resend when `RESEND_API_KEY` is
  set. With no key it returns `503`, which is the correct answer rather than a
  broken request.
- **`uploads.http`** uploads to Cloudinary for real, using
  [`fixtures/example.png`](fixtures/example.png) — a 1×1 PNG, deliberately the
  smallest thing that still exercises the path. Same story: no credentials
  means `503`.

## Keeping them honest

[`tests/test_http_files.py`](../tests/test_http_files.py) fails if a route
exists in the OpenAPI spec with no request in this directory. Add the endpoint
and the request in the same commit, the same way the README's endpoint table
and the code move together.
