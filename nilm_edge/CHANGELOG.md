# Changelog

## 1.1.6

- Publish per-appliance energy sensors (`sensor.nilm_*_energy`) with `device_class: energy` and `state_class: total_increasing` for use in the HA Energy Dashboard.
- Energy is accumulated internally at the model's 8-second inference cadence, giving more accurate totals than an external Riemann-sum integral helper.
- Accumulated energy is persisted to `/data/energy_accumulators.json` and restored on restart, so totals are not lost when the add-on is restarted or updated.

## 1.1.5

- Added support for mains and appliance power sensors reported in `kW` by normalizing them to `W` across training and live disaggregation.
- Improved compatibility for existing configurations by resolving the mains sensor unit automatically when needed.

## 1.1.4

- Added support for external training servers, so training can run on another machine using a saved URL such as `http://<host>:<port>/train`.
- Added a `Custom External Server` option in the Training page alongside the autodetected internal Home Assistant training app.
- Improved training server selection so the internal app is selected by default when available, while custom mode only appears when chosen explicitly.
- Tightened training server validation and readiness checks to reject incomplete selections and invalid endpoints.
- Improved status messaging in the Training page so the active training server is shown clearly as internal or custom.
