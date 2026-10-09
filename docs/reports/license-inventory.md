# Dependency license inventory — INF-001

Generated 2026-10-09 from the installed Python 3.11 environment and the complete JavaScript lockfile. Detailed package/version/license records are in [license-inventory.json](license-inventory.json).

## Scope

- Python: 34 distributions installed by `uv sync --locked`; license information read from distribution metadata (SPDX expression, declared license, or license classifier).
- Frontend: 173 package entries, including platform-optional entries, in `frontend/package-lock.json`; license field read from the lockfile metadata.
- Package metadata is an inventory aid, not a legal conclusion. Dependency terms and distribution obligations need review before external production distribution.

## Python license summary

| Declared license | Packages |
|---|---:|
| MIT | 20 |
| BSD-3-Clause | 8 |
| BSD-2-Clause | 1 |
| BSD License | 1 |
| Apache-2.0 | 1 |
| Apache-2.0 OR BSD-2-Clause | 1 |
| MPL-2.0 | 1 |
| PSF-2.0 | 1 |

`pathspec` declares MPL-2.0; `packaging` declares `Apache-2.0 OR BSD-2-Clause`. These are retained as reported metadata, not normalized to a single license.

## Frontend license summary

| Declared license | Packages |
|---|---:|
| MIT | 109 |
| Apache-2.0 | 30 |
| ISC | 9 |
| LGPL-3.0-or-later | 10 |
| BSD-2-Clause | 6 |
| BSD-3-Clause | 2 |
| Apache-2.0 AND LGPL-3.0-or-later | 3 |
| Apache-2.0 AND LGPL-3.0-or-later AND MIT | 1 |
| 0BSD | 1 |
| BlueOak-1.0.0 | 1 |
| CC-BY-4.0 | 1 |

The LGPL declarations are from optional `@img/sharp-*` platform packages pulled into the Next.js lockfile. `caniuse-lite` declares CC-BY-4.0. The per-package inventory identifies each affected entry; review applicability and attribution/distribution obligations before deployment. No license was manually reclassified.
