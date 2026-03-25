# Site Design Configuration — Impeccable-Guided

## Brand Identity
- **Site Name**: TrendPulse (placeholder — change to your domain name)
- **Tagline**: "What's trending. What matters. What's next."
- **Voice**: Confident, concise, knowledgeable — not robotic, not clickbait

## Typography System
- **Primary Font**: "General Sans" (Variable, from Fontshare — free, distinctive, NOT Inter)
- **Mono/Code**: "JetBrains Mono" (for any data/stats callouts)
- **Fallback**: system-ui, -apple-system, sans-serif
- **Scale** (modular, ratio 1.25 — Major Third):
  - `--text-xs`: 0.64rem
  - `--text-sm`: 0.8rem
  - `--text-base`: 1rem (16px)
  - `--text-md`: 1.25rem
  - `--text-lg`: 1.563rem
  - `--text-xl`: 1.953rem
  - `--text-2xl`: 2.441rem
  - `--text-3xl`: 3.052rem
- **Line heights**: 1.2 for headings, 1.6 for body

## Color System (OKLCH)
All colors defined in OKLCH for perceptual uniformity.

### Light Mode
- `--color-bg`: oklch(0.985 0.002 90)         — warm off-white (NOT pure white)
- `--color-surface`: oklch(0.97 0.003 90)      — slightly warm card bg
- `--color-text`: oklch(0.2 0.02 260)          — dark blue-tinted (NOT pure black)
- `--color-text-muted`: oklch(0.45 0.02 260)   — secondary text (NOT gray)
- `--color-accent`: oklch(0.65 0.2 25)         — warm coral/terracotta
- `--color-accent-hover`: oklch(0.58 0.22 25)  — darker on hover
- `--color-border`: oklch(0.88 0.01 90)        — subtle warm border
- `--color-success`: oklch(0.7 0.18 150)       — teal green
- `--color-warning`: oklch(0.75 0.15 70)       — amber
- `--color-error`: oklch(0.6 0.2 25)           — red-coral

### Dark Mode
- `--color-bg`: oklch(0.15 0.015 260)          — deep blue-black
- `--color-surface`: oklch(0.2 0.02 260)       — card surface
- `--color-text`: oklch(0.92 0.01 90)          — warm light
- `--color-text-muted`: oklch(0.65 0.015 90)   — soft muted
- `--color-accent`: oklch(0.72 0.18 25)        — brighter coral
- `--color-border`: oklch(0.3 0.02 260)        — subtle border

## Spacing System (8px base)
- `--space-1`: 0.25rem (4px)
- `--space-2`: 0.5rem (8px)
- `--space-3`: 0.75rem (12px)
- `--space-4`: 1rem (16px)
- `--space-6`: 1.5rem (24px)
- `--space-8`: 2rem (32px)
- `--space-12`: 3rem (48px)
- `--space-16`: 4rem (64px)
- `--space-24`: 6rem (96px)

## Layout
- **Max content width**: 72ch (for readability)
- **Page max**: 1200px
- **Grid**: CSS Grid with auto-fill, minmax(300px, 1fr)
- **Cards**: Single level only — NEVER nest cards inside cards
- **Responsive**: Mobile-first, breakpoints at 640px, 768px, 1024px, 1280px

## Motion
- **Easing**: cubic-bezier(0.25, 0.1, 0.25, 1.0) — smooth, NOT bounce/elastic
- **Duration**: 150ms for micro, 300ms for transitions, 500ms for page-level
- **Reduced motion**: Honor `prefers-reduced-motion: reduce`

## Anti-Patterns (NEVER DO)
1. ❌ Inter, Arial, or system-default as primary font
2. ❌ Purple/blue gradients (screams "AI template")
3. ❌ Cards nested inside cards
4. ❌ Gray text on colored backgrounds (use tinted neutrals)
5. ❌ Pure black (#000) or pure white (#fff) anywhere
6. ❌ Bounce/elastic easing (feels dated)
7. ❌ Generic hero sections with centered text and stock photo
8. ❌ Rounded corners > 12px (too bubbly)
9. ❌ Drop shadows with no blur (flat shadow)
10. ❌ All-caps body text
