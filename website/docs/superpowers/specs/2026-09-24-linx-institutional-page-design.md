# LINX Institutional Page - Design Specification

**Date:** 2026-09-24  
**Project:** LINX Website (Astro)  
**Status:** Approved for Implementation

---

## 1. Project Overview

### 1.1 Purpose
Create a modern, bold institutional page for LINX - a tech/software company. The page serves as the primary marketing presence, communicating value proposition, showcasing product features, and converting visitors to signups.

### 1.2 Scope
Single-page hybrid architecture with shareable section anchors. All content loads on one page with smooth-scroll navigation, but each section is accessible via direct URL (e.g., `/#features`, `/#contact`).

### 1.3 Success Criteria
- Clear value proposition within 3 seconds (hero)
- Feature understanding via interactive tabs
- Conversion via email capture (CTA section)
- Professional brand presence matching "Bold & Modern" aesthetic
- Accessible, performant, responsive across all devices

---

## 2. Brand System

### 2.1 Color Palette

| Role | Hex | Usage |
|------|-----|-------|
| Primary Dark | `#0a2540` | Header bar, hero background, footer, feature tab panel |
| Accent Teal | `#00d4AA` | Primary CTAs, active states, gradient accents, focus rings |
| Secondary Cyan | `#00b4d8` | Secondary CTAs, borders, hover states, gradient accents |
| Page Background | `#ffffff` | Main page background (light for readability) |
| Section Alternate | `#f8fafc` | Alternating section backgrounds for visual separation |
| Text Primary | `#0a2540` | Headlines, body text on light backgrounds |
| Text Secondary | `#6b7280` | Supporting text, descriptions |
| Text Muted | `#9ca3af` | Meta info, legal links |
| Border Light | `#e5e7eb` | Card borders, input borders, dividers |

### 2.2 Typography

- **Font Stack:** System UI (`Inter, Roboto, 'Helvetica Neue', 'Arial Nova', 'Nimbus Sans', Arial, sans-serif`)
- **Monospace:** `ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace`
- **Scale:**
  - Hero H1: `clamp(2.5rem, 5vw, 4rem)` / weight 800 / line-height 1.05
  - Section H2: `clamp(2rem, 3vw, 2.5rem)` / weight 800 / line-height 1.15
  - Feature H3: `1.25rem` / weight 700
  - Body: `1rem` / weight 400 / line-height 1.6
  - Small: `0.875rem` / weight 400

### 2.3 Spacing & Layout

- **Base unit:** 4px (0.25rem)
- **Section padding:** `clamp(3rem, 8vw, 6rem)` vertical, `clamp(1.5rem, 5vw, 3rem)` horizontal
- **Container max-width:** 1200px
- **Grid gaps:** 1.5rem (cards), 3rem (feature sections)
- **Border radius:** 8px (buttons/inputs), 12px (cards), 16px (major sections)

### 2.4 Effects

- **Shadows:** `0 4px 20px rgba(10,37,64,0.1)` (cards), `0 4px 24px rgba(0,212,170,0.4)` (primary CTA)
- **Transitions:** 200ms ease (colors, transforms, shadows)
- **Gradients:** Linear 135deg for primary elements (`#00d4AA` → `#00b4d8`)

---

## 3. Page Architecture

### 3.1 Hybrid Single-Page Structure

```
/ (root)
├── Header/Navigation (sticky, #header)
├── Hero Section (#hero)
├── Features Section (#features)
├── Contact/CTA Section (#contact)
└── Footer (#footer)
```

- Each section has an `id` matching its anchor
- Sticky header with smooth-scroll navigation
- URL updates on scroll (IntersectionObserver)
- Direct link access works (e.g., `linx.dev/#features`)

### 3.2 Component Hierarchy

```
Layout.astro
├── Header.astro (new - replaces Navigation.astro)
│   ├── Logo
│   ├── NavLinks (desktop)
│   ├── MobileMenuButton
│   ├── AuthButtons (Login / Sign Up)
│   └── MobileDrawer (mobile nav)
├── Hero.astro
├── Features.astro
├── Contact.astro
└── Footer.astro (replaces Footer.astro)
```

---

## 4. Section Specifications

### 4.1 Header / Navigation

**Visual:** Dark brand bar (`#0a2540`) with 3px teal (`#00d4AA`) bottom accent line.

**Structure:**
```
[LINX Logo]                    [About] [Features] [Contact]    [Login] [Sign Up]
```

**Responsive:**
- Desktop (≥768px): Horizontal layout as above
- Mobile (<768px): Logo left, hamburger right; drawer slides from right with nav links + auth buttons

**Auth Buttons (Mandatory):**
- **Login:** Outline style - `border: 1px solid #00d4AA`, `color: #00d4AA`, `background: transparent`
- **Sign Up:** Filled style - `background: #00d4AA`, `color: #0a2540`, `font-weight: 700`
- Both: `padding: 0.5rem 1.5rem`, `border-radius: 6px`, `font-weight: 600`

**Sticky Behavior:**
- `position: sticky`, `top: 0`, `z-index: 100`
- Backdrop blur on scroll: `backdrop-filter: blur(10px)`, `background: rgba(10,37,64,0.95)`

### 4.2 Hero Section

**Background:** White (`#ffffff`) with subtle decorative gradients

**Content (Centered, max-width 800px):**
```
[Badge: "New Release v2.0" - optional]
H1: "Build faster with LINX" ("LINX" in gradient #00d4AA → #00b4d8)
Subheadline: "The modern platform for developers to ship products at lightning speed."
[CTA Group]
  Primary: "Get Started Free" - filled #00d4AA, white text, large
  Secondary: "Watch Demo" - outline #00b4d8, cyan text
[Trust Indicators - 3 items]
  "50ms cold start" | "35 regions" | "SOC2 certified"
```

**Visual Treatment:**
- Generous whitespace (6rem vertical padding)
- Subtle radial gradient orbs in background (opacity 0.05-0.08)
- Gradient text on "LINX" brand name
- CTA buttons with hover/tap states

### 4.3 Features Section

**Background:** Alternating - white / `#f8fafc`

**Structure:** Interactive tabbed interface

**Tabs (4):**
1. **Deploy** (default active) - Lightning deploy, edge network, zero config
2. **Scale** - Auto-scaling, global regions, instant rollbacks
3. **Collaborate** - Real-time preview, team workspaces, live editing
4. **Secure** - SOC2, encryption, access controls, audit logs

**Tab Panel Layout (per tab):**
```
[Left: Content - 50%]                    [Right: Visual - 50%]
H2: "Deploy in seconds, not minutes"     [Terminal/Code Mockup]
P: Description paragraph                 Background: rgba(255,255,255,0.05)
Framework badges (Next.js, Astro, etc.)  Monospace font, #00d4AA text
```

**Tab Styling:**
- Container: Dark background `#0a2540`, rounded 16px
- Tabs: Horizontal, flex-wrap, gap 0.5rem
- Active: `#00d4AA` background, `#0a2540` text, weight 700
- Inactive: `rgba(255,255,255,0.1)` background, white text, border `rgba(255,255,255,0.2)`
- All: `border-radius: 8px`, `padding: 0.75rem 1.5rem`

**Responsive:**
- Mobile: Tabs scroll horizontally, panels stack (content above visual)

### 4.4 Contact / CTA Section

**Background:** White (`#ffffff`)

**Content (Centered, max-width 600px):**
```
H2: "Ready to ship faster?"
P: "Join thousands of developers deploying on LINX. Free tier includes 100GB bandwidth."
[Email Capture Form]
  Input: type="email", placeholder="Enter your email"
  Button: "Get Started Free" (primary style)
Micro-copy: "No credit card required · 14-day free trial · Cancel anytime"
```

**Form Styling:**
- Input: `padding: 1rem 1.5rem`, `border-radius: 8px`, `border: 1px solid #e5e7eb`, `background: white`
- Focus: `border-color: #00d4AA`, `box-shadow: 0 0 0 3px rgba(0,212,170,0.15)`
- Button: Primary style, full width on mobile

### 4.5 Footer

**Background:** Dark `#0a2540` (strong contrast from page)

**Structure (4-column grid, max-width 1200px):**

| Column 1: Brand | Column 2: Product | Column 3: Company | Column 4: Resources |
|-----------------|-------------------|-------------------|---------------------|
| LINX logo | Features | About | Documentation |
| Tagline | Pricing | Blog | API Reference |
| Social links (4) | Changelog | Careers | Community |
| | Roadmap | Press | Status |

**Bottom Bar:**
- Left: `© 2025 LINX. All rights reserved.`
- Right: Privacy · Terms · Cookies links

**Styling:**
- Column headers: `#00d4AA`, weight 700
- Links: `rgba(255,255,255,0.7)`, hover → white
- Divider: `border-top: 1px solid rgba(255,255,255,0.1)`
- Padding: 4rem top, 2rem bottom

---

## 5. Responsive Breakpoints

| Breakpoint | Width | Key Changes |
|------------|-------|-------------|
| Mobile | < 640px | Single column, stacked CTAs, horizontal tab scroll, hamburger menu |
| Tablet | 640-1023px | 2-col grids, adjusted padding, drawer navigation |
| Desktop | ≥ 1024px | Full layouts, hover states, sticky header |

---

## 6. Accessibility Requirements

- Semantic HTML5 (`<header>`, `<main>`, `<section>`, `<footer>`, `<nav>`)
- ARIA labels on icon-only buttons (mobile menu, social links)
- Focus visible states on all interactive elements
- Color contrast: WCAG AA minimum (4.5:1 text, 3:1 UI)
- Skip-to-main-content link
- Heading hierarchy: h1 → h2 → h3
- Form labels associated with inputs
- Alt text for all decorative images (empty alt for purely decorative)

---

## 7. Performance Targets

- **LCP:** < 2.5s (hero image/text prioritized)
- **CLS:** < 0.1 (reserve space for dynamic content)
- **FID:** < 100ms (minimal JS, Astro islands for interactivity)
- **Images:** WebP/AVIF, responsive `srcset`, lazy-load below fold
- **CSS:** Critical inline, non-critical deferred
- **Fonts:** System font stack (no external font requests)

---

## 8. Technical Implementation Notes

### 8.1 Astro Components to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/components/Header.astro` | **Create** | Sticky header with nav, auth buttons, mobile drawer |
| `src/components/Hero.astro` | **Create** | Hero section with centered content |
| `src/components/Features.astro` | **Create** | Interactive tabbed feature showcase |
| `src/components/Contact.astro` | **Create** | Email capture CTA section |
| `src/components/Footer.astro` | **Modify** | Replace with comprehensive footer |
| `src/layouts/Layout.astro` | **Modify** | Update metadata, fonts, global styles |
| `src/pages/index.astro` | **Modify** | Compose all sections with anchor IDs |
| `src/styles/global.css` | **Create** | Design tokens, utilities, reset |

### 8.2 JavaScript Interactivity (Minimal)

- **Mobile menu toggle:** Vanilla JS, Astro island
- **Tab switching:** Vanilla JS, Astro island (Features component)
- **Smooth scroll:** CSS `scroll-behavior: smooth` + IntersectionObserver for active nav
- **Form submission:** Standard form POST to backend endpoint (to be implemented)

### 8.3 State Management

- No client-side state framework needed
- Astro's built-in island pattern for interactive components
- URL hash for section tracking (native browser behavior)

---

## 9. Content Requirements (Placeholder)

The following copy needs to be provided by stakeholders:

- [ ] Company tagline/one-liner
- [ ] Hero headline & subheadline
- [ ] Feature descriptions (4 tabs × content + visual concepts)
- [ ] Trust indicator metrics (real numbers)
- [ ] Footer company info (address, legal entity)
- [ ] Social media URLs
- [ ] Legal page URLs (privacy, terms, cookies)

---

## 10. Implementation Phases

### Phase 1: Foundation
- Design tokens (CSS custom properties)
- Global styles, reset, typography
- Layout.astro updates

### Phase 2: Header & Navigation
- Header.astro component
- Mobile drawer logic
- Auth button styling

### Phase 3: Hero Section
- Hero.astro component
- Background gradients/orbs
- CTA buttons

### Phase 4: Features Section
- Features.astro component
- Tab switching logic (island)
- Terminal/code mockups

### Phase 5: Contact & Footer
- Contact.astro component
- Footer.astro replacement
- Form handling setup

### Phase 6: Polish & QA
- Responsive testing
- Accessibility audit
- Performance optimization
- Cross-browser verification

---

## 11. Future Considerations

- **Internationalization:** Structure supports i18n routing (`/en/`, `/pt/`)
- **Analytics:** Event tracking on CTA clicks, tab changes, form submissions
- **A/B Testing:** Hero headline, CTA copy, form fields
- **Blog/Resources:** Extend architecture for content collections
- **Authentication:** Integrate with auth provider (Clerk, Auth.js, custom)

---

## Appendix: Design Decision Log

| Decision | Option Chosen | Rationale |
|----------|---------------|-----------|
| Architecture | Hybrid (C) | Modern tech standard, shareable URLs, progressive enhancement |
| Header Style | Split Background (C) | Bold brand presence, clear visual hierarchy |
| Hero Layout | Centered Impact (A) | Maximum readability, strong focus on value prop |
| Features | Interactive Tabs (C) | Deep-dive capability, developer-focused, space-efficient |
| Contact CTA | Centered Band (A) | Lower friction, higher conversion for email capture |
| Footer | Comprehensive (C) | SEO-friendly, trust signals, complete navigation |
| Page Background | Light/White | Readability, reduced eye strain, professional |

---

*Spec written and committed. Ready for implementation planning.*