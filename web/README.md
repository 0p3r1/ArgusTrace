# ArgusTrace web frontend

React + Vite interface for the ArgusTrace API. It renders the tool catalog
from `/api/plugins`, runs investigations, and displays the tri-state
findings.

```bash
npm install
npm run dev     # http://localhost:5173, expects the API on 127.0.0.1:8000
npm run lint
npm run build
```

Both endpoints are overridable at build time:

- `VITE_ARGUSTRACE_API_BASE` — where the API lives.
- `VITE_ARGUSTRACE_TOKEN` — sent as `X-ArgusTrace-Token` when the API is
  configured to require one. Not needed for the default loopback setup.

See the repository [README](../README.md) for running the backend, and
[CLAUDE.md](../CLAUDE.md) for the conventions this UI relies on — in
particular the `evidence` keys (`headline`, `profile`, `coordinates`) that
get their own rendering.
