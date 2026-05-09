# Changelog

## [1.1.0]

### Added
- **WU Progress sensor** — shows the current work unit's completion percentage, based on the highest-PPD active unit
- Work unit attributes now include `eta`, `tpf`, `credit`, `deadline`, and `timeout` where provided by the client

## [1.0.0]

### Added
- Initial release
- Status sensor (`folding`, `paused`, `finishing`)
- Points Per Day (PPD) sensor — sum across all active work units
- Active CPUs sensor with `total_cpus` attribute
- Active GPUs sensor with per-GPU details
- Work Units sensor with per-unit `project`, `progress`, `state`, and `ppd` attributes
- Folding switch (pause/resume)
- Finish & Pause button
- Real-time updates via persistent WebSocket connection to the FAH v8 client
- Automatic reconnection with exponential backoff
- Integration loads successfully even when the FAH client is offline at startup
