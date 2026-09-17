# Changelog

## 1.0.2 — Native delegation readiness

- Refuse installation when Flash is present but not advertised for native subagents.
- Explain full host-app restart, cached catalogs, and Router commands that can trigger paid verification.
- Distinguish local route selection from runtime capability evidence.

## 1.0.1 — Public repository preparation

- Support the Router's native authenticated `/v1` base path alongside capability paths; retain loopback and URL-shape validation.
- Preserve permissions on an existing installation-backup directory.
- Add regression tests for direct routing, rejected URL shapes and permission preservation.
- Exclude local backup/cache artifacts from installed skill files and release archives.
- Replace private handoff/audit notes with public installation, troubleshooting, contribution and security documentation.
- Add reproducible release inventory and ZIP packaging with integrity checks.

## 1.0.0 — Initial package

- Native Flash builder role, Astra orchestration skill, scoped personal policy, dry run and guarded undo.
- Offline installation tests, configuration doctor, task templates and optional plan validator.
