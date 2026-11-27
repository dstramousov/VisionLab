# Versions

## v0.0.0 -> v0.0.1

Initial control and observation panel.

## v0.0.1 -> v0.0.2

- Compact workspace and live generation with collapsed reasoning.
- Persisted generation settings and frame comparison mode.
- Adapt archive and approval utilities; add local run helper.

## v0.0.2 -> v0.0.3

- Camera mirror and vertical flip controls.
- Experimental text-guided localization and snapshot bounding boxes.

## v0.0.3 -> v0.0.4

- Experimental CSRT live tracking with bounded frame replay and automatic reacquisition.
- Separate raw inference frames and annotated live stream; tracking transitions in SQLite.
- Replace opencv-python-headless with opencv-contrib-python-headless (uninstall the former first).
- Tracking and automatic scene analysis are mutually exclusive. Tracker drift and capture slowdown are possible.
- Add ./stop, ./restart and ./status for project-owned backend processes; restart runs in foreground.
