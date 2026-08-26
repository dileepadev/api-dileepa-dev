"""The API reference, themed against the platform brand tokens.

Scalar is styled entirely through CSS custom properties, so this maps the
canonical token sheet (`dileepadev/docs/brand/brand-tokens.css`) onto the
`--scalar-*` names rather than restating any colour. The values here are copied
from that sheet, which is the single source of truth: when it changes, this
file is one of the places the change has to be pushed.

Two brand rules shape what follows, and neither is a preference:

1. **Emerald is the only accent**, and which emerald depends on the surface.
   Emerald Deep on Carbon and Emerald Bright on Paper are both named in the
   brand guide as failures, so the accent is declared twice — once per theme —
   rather than once globally.
2. **Manrope for UI, JetBrains Mono for code**, weights 400/500/700 only.
   Scalar's own defaults are Inter and JetBrains Mono, so `with_default_fonts`
   is turned off where this is used and the faces are loaded here instead.

HTTP method colours are left as Scalar ships them. They are functional state,
the same category as `--error` and `--warning` in the token sheet — which that
sheet permits explicitly as "UI state only, never a brand accent" — and a
reference where every verb is the same colour is harder to read, not more
on-brand.

This page is only ever served outside production (`Settings.serve_docs`), so
nothing here reaches a public surface.
"""

from __future__ import annotations

# The font stylesheet the theme needs. Named here because the docs
# Content-Security-Policy has to allow exactly these two origins and nothing
# else — see `app.core.rate_limit._docs_csp`.
FONT_STYLESHEET = (
    "https://fonts.googleapis.com/css2"
    "?family=Manrope:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap"
)
FONT_STYLE_ORIGIN = "https://fonts.googleapis.com"
FONT_FILE_ORIGIN = "https://fonts.gstatic.com"

BRAND_CSS = f"""
@import url("{FONT_STYLESHEET}");

/* Raw palette — the token sheet's values, not re-picked. Components below
   reference the semantic names, never these. */
:root {{
  --brand-emerald-deep: #087f5b;
  --brand-emerald-bright: #23b888;
  --brand-ink-900: #050505;
  --brand-ink-800: #0d0d0d;
  --brand-ink-700: #141414;
  --brand-ink-600: #1f1f1f;
  --brand-ink-500: #2e2e2e;
  --brand-ink-400: #8d8d8d;
  --brand-ink-100: #f1f1f1;
  --brand-paper-0: #ffffff;
  --brand-paper-50: #f7f7f7;
  --brand-paper-200: #e3e3e3;
  --brand-paper-300: #d2d2d2;
  --brand-paper-400: #6a6a6a;
  --brand-paper-900: #131313;

  --scalar-font: "Manrope", system-ui, -apple-system, sans-serif;
  --scalar-font-code: "JetBrains Mono", ui-monospace, "SF Mono", monospace;

  --scalar-radius: 8px;
  --scalar-radius-lg: 12px;
  --scalar-radius-xl: 16px;

  /* 400/500/700. The token sheet permits no 600, and Scalar reaches for one
     in its headings unless it is told otherwise. */
  --scalar-bold: 700;
  --scalar-semibold: 500;
  --scalar-regular: 400;
}}

/* Dark — the foundation. Emerald Bright, which is the only emerald that may
   sit on Carbon (8.0:1). */
.dark-mode {{
  --scalar-color-1: var(--brand-ink-100);
  --scalar-color-2: var(--brand-ink-400);
  --scalar-color-3: var(--brand-ink-400);
  --scalar-color-accent: var(--brand-emerald-bright);
  --scalar-background-1: var(--brand-ink-900);
  --scalar-background-2: var(--brand-ink-800);
  --scalar-background-3: var(--brand-ink-700);
  --scalar-background-accent: color-mix(
    in srgb, var(--brand-emerald-bright) 16%, transparent
  );
  --scalar-border-color: var(--brand-ink-600);

  --scalar-sidebar-background-1: var(--brand-ink-800);
  --scalar-sidebar-color-1: var(--brand-ink-100);
  --scalar-sidebar-color-2: var(--brand-ink-400);
  --scalar-sidebar-border-color: var(--brand-ink-600);
  --scalar-sidebar-item-hover-background: var(--brand-ink-700);
  --scalar-sidebar-item-hover-color: var(--brand-ink-100);
  --scalar-sidebar-item-active-background: var(--brand-ink-700);
  --scalar-sidebar-color-active: var(--brand-emerald-bright);
  --scalar-sidebar-search-background: var(--brand-ink-700);
  --scalar-sidebar-search-border-color: var(--brand-ink-500);
  --scalar-sidebar-search-color: var(--brand-ink-400);
}}

/* Light — Emerald Deep, the only emerald permitted on Paper (4.7:1). */
.light-mode {{
  --scalar-color-1: var(--brand-paper-900);
  --scalar-color-2: var(--brand-paper-400);
  --scalar-color-3: var(--brand-paper-400);
  --scalar-color-accent: var(--brand-emerald-deep);
  --scalar-background-1: var(--brand-paper-50);
  --scalar-background-2: var(--brand-paper-0);
  --scalar-background-3: var(--brand-paper-200);
  --scalar-background-accent: color-mix(
    in srgb, var(--brand-emerald-deep) 12%, transparent
  );
  --scalar-border-color: var(--brand-paper-200);

  --scalar-sidebar-background-1: var(--brand-paper-0);
  --scalar-sidebar-color-1: var(--brand-paper-900);
  --scalar-sidebar-color-2: var(--brand-paper-400);
  --scalar-sidebar-border-color: var(--brand-paper-200);
  --scalar-sidebar-item-hover-background: var(--brand-paper-50);
  --scalar-sidebar-item-hover-color: var(--brand-paper-900);
  --scalar-sidebar-item-active-background: var(--brand-paper-200);
  --scalar-sidebar-color-active: var(--brand-emerald-deep);
  --scalar-sidebar-search-background: var(--brand-paper-50);
  --scalar-sidebar-search-border-color: var(--brand-paper-300);
  --scalar-sidebar-search-color: var(--brand-paper-400);
}}

/* The lockup's rule: the wordmark stays neutral and only the "/." is emerald.
   The reference's title is the service name, so it gets the same treatment
   rather than being tinted whole. */
.scalar-api-reference h1.section-header {{
  letter-spacing: -0.02em;
  font-weight: 700;
}}
"""
