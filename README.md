# VisionLab

Локальная лаборатория визуального восприятия. Версия 0.0.3.

## Запуск

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./run
```

Открыть http://127.0.0.1:8090. API: `/docs`. Камера и модель запускаются отдельно. Используются существующие веса и llama.cpp из `/storage/llm-lab`; порт модели 8084. Не запускайте одновременно другие тяжёлые модели.

Автоанализ сравнивает последний успешно проанализированный кадр с новым. Опция «Только изменения» измеряет среднюю абсолютную разницу яркости уменьшенных кадров; освещение и движение камеры могут вызывать ложные срабатывания. Это не детектор объектов. Интервал отсчитывается после предыдущего анализа. Настройки сохраняются в `data/settings.json`, наблюдения — в SQLite. Рассуждения отображаются отдельно и свёрнуты; в этой версии в SQLite сохраняется только основной ответ. Остановка автоанализа не отменяет текущий запрос.

`./a` создаёт архив исходников в Downloads; `./appr` предлагает подтвердить commit и push. Перед подтверждением проверьте список файлов: репозиторий публичный. `./run` запускает локальный сервер без однотипных access-логов. Данные камеры, локальные настройки и веса не предназначены для Git.

Проверки: `python -m unittest discover -s tests` и `node --check frontend/app.js`.

Зеркальный режим и вертикальный переворот применяются в OpenCV до передачи модели. Поиск объекта использует Qwen3.5 и проверяет формат координат 0..1000; рамка отображается на снимке поиска, не является непрерывным трекингом. Остановите автоанализ перед поиском. Точность необходимо проверить экспериментально.

## v0.0.4

- Experimental CSRT live tracking with bounded frame replay and automatic reacquisition.
- Separate raw inference frames and annotated live stream; tracking transitions in SQLite.
- Replace opencv-python-headless with opencv-contrib-python-headless (uninstall the former first).
- Tracking and automatic scene analysis are mutually exclusive. Tracker drift and capture slowdown are possible.
- Add ./stop, ./restart and ./status for project-owned backend processes; restart runs in foreground.
