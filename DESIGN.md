---
version: alpha
name: Mania Chart Studio
description: Local four-key music chart drafting and timing editor for G4T0XX.
colors:
  bg: '#101116'
  surface: '#181a22'
  raised: '#222530'
  ink: '#ecebf1'
  muted: '#b5b6c2'
  line: '#373a45'
  accent: '#ff3e57'
  focus: '#80cfff'
  warn: '#ffd18c'
typography:
  sans:
    fontFamily: 'Segoe UI, Arial, sans-serif'
  display:
    fontFamily: 'Arial Black, Segoe UI, sans-serif'
  mono:
    fontFamily: 'Consolas, monospace'
rounded:
  DEFAULT: '8px'
spacing:
  section-gap: '48px'
  page-max: '1500px'
components:
  button: {}
  input: {}
  timeline: {}
---

# Mania Chart Studio Design System

## Overview

### Creative North Star

A rhythm-game editor as a small audio workstation: four real note lanes, waveform and a precise playback cursor carry the identity. The timeline is the signature, not decorative dashboard statistics.

### Product context and register

Portuguese-speaking G4T0XX, Windows desktop, local music chart creation. Product/tool register, Brazilian Portuguese, with English rhythm-game terms retained. No Japan-market scope. Black and red follow the user's existing identity. Familiar controls surround the four-lane visual. Avoid marketing claims about perfect timing and ranked eligibility.

### Token ownership/runtime mapping

`web/style.css :root` is the canonical runtime token source. This frontmatter mirrors it; canvas reads CSS variables directly. Single-screen app, no sibling design system. Cover uses the same identity but is a standalone exported bitmap.

## Colors

Dark bg, surface and raised provide hierarchy. Ink and muted provide readable text. Accent identifies safe primary actions and outer lanes. Focus is blue, warn is amber; all feedback also uses text. Forced colors preserves system outlines.

## Typography

Segoe UI is the local body font, Arial Black is reserved for the opening title and logo, Consolas for timing and measurements. No font downloads. Portuguese labels, locale-formatted counts. Titles wrap instead of truncating source names.

## Layout

Maximum width 1500px with 48px gutters, reducing to 24px. Sidebar 295px, flexible editor. At 720px the sections stack in natural document scroll. The timeline remains four lanes at every width. No fixed-height page wrapper. Controls reserve minimum height 42px. No layout-changing font load.

## Elevation & Depth

Borders and tonal surfaces separate panels. No blur or ornamental shadows. The app does not contain modal overlays.

## Shapes

8px control radius and 12px workstation perimeter. Note bars retain square ends to communicate exact timestamps.

## Components

### Foundational visual states

Buttons support hover, visible focus, pressed, disabled and busy. Feedback occupies inline live regions. Empty state explains link entry; progress names the active stage; errors preserve the entered link and project.

### Buttons and actions

Primary red buttons use dark text. Neutral buttons share the same dimensions. Removing a note is reversible through Undo; there is no irreversible project delete action.

### Navigation and data display

Single workspace with a local library and difficulty buttons using aria-pressed. Stars are engine-calculated. Column counts expose distribution without claiming quality.

### Forms and overlays

Native labeled inputs/selects; OS-owned select popup geometry is deliberately accepted. Form validation is app-owned with novalidate and inline errors. Canvas has equivalent time/lane controls. No dialogs, secrets, search or date picker.

### Iconography

Text glyphs accompany visible action labels. No third-party icon font or icon-only main actions.

### Motion

The playback cursor represents actual playback time. Decorative animation is absent. Reduced-motion disables nonessential motion; cursor movement is needed for the audio editing task.

### Content and data visualization

Plain Portuguese, explicit draft status and uncertain tempo. Waveform and beat lines provide context while the note lanes show actual generated objects. Accessible metrics and numeric editing complement the canvas.

## Do's and Don'ts

- Do keep music and hit preview on the same Web Audio clock.
- Do retain undo and server validation for edits.
- Don't describe generated notes as musically verified.
- Don't label difficulty with invented star ratings.
