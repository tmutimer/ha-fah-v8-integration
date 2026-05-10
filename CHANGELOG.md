# Changelog

## [1.2.0]

### Added
- **Donor / User Stats** — a new config entry type that tracks your global Folding@home donor stats via the public FAH stats API, independent of any local FAH client
  - **Work Units Completed** sensor — lifetime total WUs, tracked as a cumulative counter so HA graphs it correctly over time
  - **Total Score** sensor — lifetime points earned
  - **Global Rank** sensor — your rank among all donors, with `active_donors_7_days` and `teams` as attributes for context
- Config flow now opens with a menu to choose between "Local FAH Machine" and "Donor / User Stats"
- Donor username is validated against the FAH stats API during setup, with a clear error if the username isn't found
- Stats poll hourly (matching FAH's update cadence); entities show as unavailable if the API is unreachable

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
