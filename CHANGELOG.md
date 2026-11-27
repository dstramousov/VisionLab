# CHANGELOG

## 0.0.1
- Local web control and observation panel.
- Independent camera, model and interval analysis controls.
- Latest submitted frame, frame questions, SQLite observation storage.

## 0.0.2
- Compact desktop layout, streaming text and collapsed reasoning.
- Generation settings, elapsed timer and persisted local configuration.
- Automatic two-frame comparison and optional grayscale change threshold.
- Adapted a and appr; added run helper with quiet access logging.

## 0.0.3
- Persisted horizontal and vertical camera transforms.
- Experimental text-guided object localization on a captured frame.
- Validated bounding boxes and snapshot/live view switch.

## v0.0.4

- Experimental CSRT live tracking with bounded frame replay and automatic reacquisition.
- Separate raw inference frames and annotated live stream; tracking transitions in SQLite.
- Replace opencv-python-headless with opencv-contrib-python-headless (uninstall the former first).
- Tracking and automatic scene analysis are mutually exclusive. Tracker drift and capture slowdown are possible.
- Add ./stop, ./restart and ./status for project-owned backend processes; restart runs in foreground.
