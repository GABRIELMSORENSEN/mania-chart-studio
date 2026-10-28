# UI behavior

## Sources

User request: YouTube-to-chart generation with AI, osu!mania 4K, public GitHub delivery. User feedback: bad timing and lane distribution in earlier packs. `README.md` records scope, supported inputs and local-only operation. `engine.py` owns export invariants; `server.py` owns API validation.

## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | Native HTML select | DESIGN.md | OS popup accepted | Browser keyboard selection |
| Form | generate form + API schemas | server.py | Inline field/status feedback | Invalid URL and generation E2E |
| Scrollbar | web/style.css root | DESIGN.md | Global, forced-colors fallback | Browser computed style |
| Feedback | status() and form/job live regions | web/app.js | Persistent inline | Success/failure E2E |
| CRUD | api()/openProject()/save() | server.py | Create/read/update/export; no delete | API + browser |
| Timeline | canvas + numeric fields | engine.validate_chart | Pointer and numeric edits | Browser insert/undo/save |

No table selection or date capability is applicable.

## Flow ledger

Generate blocks duplicate jobs, validates public YouTube video URLs, names processing stages and retains the URL on failure. Jobs run one at a time. A completed project opens only after successful audio decoding. Switching projects saves pending edits first; a failed save preserves the current project. Saving writes atomically. Export validates all charts before creating a package. Deleting a note is reversible through 50-step session undo. Project deletion is not offered. Page unload with pending edits uses the browser lifecycle warning. Other feedback is inline, not native dialogs.

All audio preview is scheduled against one AudioContext clock. Positive offset delays notes and the metronome; source audio stays unchanged. BPM and anchor update the proposed grid. No automatic human-quality approval exists. Errors cannot mark a project reviewed. The editor does not write into the user's osu! installation.

## Locale and recovery

Owned UI is pt-BR. Rhythm-game terms and source song names remain unchanged. Offline API errors keep edits in memory, and Save can be retried. Reload during a running job reconnects using only a local job ID; a server restart loses pending work but preserves completed projects. No auth, payment, personal identity or irreversible bulk operation is exposed. This is a loopback-only single-user tool; simultaneous editing from multiple tabs is unsupported in v0.1.
