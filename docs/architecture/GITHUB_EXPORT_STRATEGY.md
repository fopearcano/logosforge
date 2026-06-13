# GitHub Export Strategy

> Phase 1 — direction only. **GitHub is optional, never the default.** No
> export automation is implemented here (and none until Phase 5, manual push
> only).

## GitHub may be used for

- developers and power users
- backup / export
- markdown memory archive
- Claude Code workflows
- repository-linked projects
- versioning architecture docs
- project memory snapshots **if explicitly enabled**

## GitHub must NOT be

- required for normal users
- the default memory backend
- the default sync backend
- used for automatic commits without user approval
- used to store secrets
- used to store raw private chat logs by default
- used to store raw audio

## Export types

- memory snapshot (markdown)
- architecture decision log
- assistant meta-memory changelog
- project memory summary
- session summary
- prompt history archive
- Claude Code workflow notes

## Safety

- **explicit opt-in** per export type
- **clear preview** before any write
- **no secrets** (provider keys, tokens) ever exported
- **no automatic push** unless explicitly enabled by the user
- every artifact carries **project / user / workspace scope labels**
- **sensitive-memory warning** before exporting anything visibility-limited

## Relationship to sync

GitHub is an **archive/export layer on top of** local + cloud memory
(`SYNC_STRATEGY.md`), not a replacement for either. The canonical shared
state is the cloud account/workspace memory (future); GitHub is an optional
human-readable/versioned mirror for those who want it.
