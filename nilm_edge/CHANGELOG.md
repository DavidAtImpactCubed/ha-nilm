# Changelog

## 1.1.3.3

- Made the autodetected internal training server the default selection when it is available.
- Updated the Training page so the external URL input only appears when `Custom External Server` is selected explicitly.
- Improved switching between internal and external training server modes.

## 1.1.3.2

- Added support for using an external training server URL from the Training page.
- Added a `Custom External Server` option so users can connect to a remote `nilm_trainer` running on another machine.
- Kept compatibility with the autodetected internal Home Assistant training app.
- Improved training server selection and status messaging to make the active server source clearer.
- Added validation and normalization for manually entered training server URLs before saving.
