"""Local camera and inference control service."""
import base64
import json
import logging
import sqlite3
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import psutil
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
API = 'http://127.0.0.1:8084'
LOG = logging.getLogger(__name__)


def image_part(frame: bytes) -> dict[str, Any]:
    """Encode a JPEG for the local multimodal API."""
    image = base64.b64encode(frame).decode('ascii')
    return {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image}'}}


def split_reasoning(text: str, reasoning: str) -> tuple[str, str]:
    """Separate explicit reasoning tags, including an unfinished tag block."""
    import re
    thoughts = re.findall(r'<think>(.*?)(?:</think>|$)', text, re.S)
    answer = re.sub(r'<think>.*?(?:</think>|$)', '', text, flags=re.S)
    for tag in ('<think>', '</think>'):
        for length in range(len(tag)-1, 0, -1):
            if answer.endswith(tag[:length]):
                answer = answer[:-length]
                break
    return answer, reasoning + ''.join(thoughts)


def frame_difference(previous: bytes, current: bytes) -> float:
    """Measure mean absolute grayscale difference on a small image grid."""
    import numpy as np
    def decode(data: bytes) -> Any:
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError('Invalid JPEG')
        return cv2.resize(image, (80, 60), interpolation=cv2.INTER_AREA)
    return float(cv2.absdiff(decode(previous), decode(current)).mean()) * 100 / 255


class Settings(BaseModel):
    """Validated camera and observation settings."""

    camera: str = Field(pattern=r'^/dev/video[0-9]+$')
    width: int = Field(ge=320, le=640)
    height: int = Field(ge=240, le=480)
    fps: int = Field(ge=15, le=60)
    interval: float = Field(ge=1, le=60)
    prompt: str = Field(min_length=1, max_length=4000)
    save_observations: bool = True
    save_frames: bool = False
    max_tokens: int = Field(default=2048, ge=128, le=4096)
    temperature: float = Field(default=0.4, ge=0, le=2)
    changes_only: bool = False
    change_threshold: float = Field(default=8.0, ge=1, le=100)


class Question(BaseModel):
    """Question about the latest camera frame."""

    text: str = Field(min_length=1, max_length=4000)


class Lab:
    """Own camera, child process and serialized inference jobs."""

    def __init__(self) -> None:
        raw = json.loads((ROOT / 'config/default.json').read_text())
        self.root = Path(raw.pop('llmlab_root'))
        self.settings = Settings(**raw)
        self.pending: dict[str, Any] | None = None
        self.started = 0.0
        self.previous_frame: bytes | None = None
        self.change_score = 0.0
        self.lock = threading.RLock()
        self.camera_thread: threading.Thread | None = None
        self.camera_stop = threading.Event()
        self.shutdown = threading.Event()
        self.frame: bytes | None = None
        self.frame_time = ''
        self.last: bytes | None = None
        self.last_time = ''
        self.fps = 0.0
        self.process: subprocess.Popen | None = None
        self.auto = False
        self.busy = False
        self.error = ''
        self.duration = 0.0
        self.events: list[dict[str, Any]] = []
        self.worker: threading.Thread | None = None

    def setup(self) -> None:
        DATA.mkdir(mode=0o700, exist_ok=True)
        local = DATA / 'settings.json'
        if local.exists():
            try:
                self.settings = Settings.model_validate_json(local.read_text())
            except (OSError, ValueError):
                LOG.exception('Cannot load saved settings')
        with sqlite3.connect(DATA / 'observations.sqlite3') as db:
            db.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, captured TEXT, kind TEXT, question TEXT, answer TEXT, seconds REAL, settings TEXT, frame BLOB)')
        self.shutdown.clear()
        self.worker = threading.Thread(target=self.loop, daemon=True)
        self.worker.start()

    def camera_on(self) -> None:
        with self.lock:
            if self.camera_thread and self.camera_thread.is_alive():
                return
            self.previous_frame = None
            self.camera_stop.clear()
            self.error = ''
            settings = self.settings.model_copy()
            self.camera_thread = threading.Thread(target=self.capture, args=(settings,), daemon=True)
            self.camera_thread.start()

    def capture(self, settings: Settings) -> None:
        cap = cv2.VideoCapture(settings.camera, cv2.CAP_V4L2)
        try:
            if not cap.isOpened():
                raise RuntimeError('Не удалось открыть камеру')
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.height)
            cap.set(cv2.CAP_PROP_FPS, settings.fps)
            count, start = 0, time.monotonic()
            while not self.camera_stop.is_set():
                ok, image = cap.read()
                if not ok:
                    raise RuntimeError('Ошибка захвата кадра')
                ok, encoded = cv2.imencode('.jpg', image)
                if not ok:
                    continue
                count += 1
                now = time.monotonic()
                with self.lock:
                    if self.camera_stop.is_set():
                        break
                    self.frame = encoded.tobytes()
                    self.frame_time = datetime.now().astimezone().isoformat(timespec='milliseconds')
                    if now - start >= 1:
                        self.fps = count / (now - start)
                        count, start = 0, now
        except Exception as exc:
            LOG.exception('Capture failed')
            with self.lock:
                self.error = str(exc)
        finally:
            cap.release()
            with self.lock:
                self.frame = None
                self.fps = 0
                self.auto = False

    def camera_off(self) -> None:
        with self.lock:
            self.auto = False
            self.camera_stop.set()
            self.frame = None
        if self.camera_thread:
            self.camera_thread.join(timeout=2)

    def ready(self) -> bool:
        if not self.process or self.process.poll() is not None:
            return False
        try:
            return requests.get(f'{API}/health', timeout=0.5).status_code == 200
        except requests.RequestException:
            return False

    def model_on(self) -> None:
        with self.lock:
            if self.process and self.process.poll() is None:
                return
            import socket
            with socket.socket() as sock:
                if sock.connect_ex(('127.0.0.1', 8084)) == 0:
                    raise RuntimeError('Порт 8084 занят; чужой сервер не используется')
            binary = self.root / 'src/llama.cpp/build-cuda/bin/llama-server'
            model = self.root / 'models/vision/Qwen3.5-4B-Q4_K_M.gguf'
            projector = self.root / 'models/vision/mmproj-Qwen3.5-4B-BF16.gguf'
            for path in (binary, model, projector):
                if not path.is_file():
                    raise RuntimeError(f'Файл отсутствует: {path}')
            with (DATA / 'llama.log').open('ab') as log:
                self.process = subprocess.Popen([str(binary), '-m', str(model), '--mmproj', str(projector), '-ngl', '99', '-c', '8192', '-np', '1', '--host', '127.0.0.1', '--port', '8084'], stdout=log, stderr=log)
            self.error = ''

    def model_off(self) -> None:
        with self.lock:
            self.auto = False
            process = self.process
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            self.process = None

    def submit(self, text: str, kind: str) -> None:
        with self.lock:
            if self.busy:
                raise RuntimeError('Анализ уже выполняется')
            if not self.frame or not self.ready():
                raise RuntimeError('Необходимы кадр и готовая модель')
            self.busy = True
            self.started = time.monotonic()
            self.pending = {'captured': self.frame_time, 'kind': kind, 'question': text, 'answer': '', 'reasoning': '', 'seconds': 0, 'pending': True}
            self.error = ''
            frame, stamp = self.frame, self.frame_time
            self.last, self.last_time = frame, stamp
            settings = self.settings.model_copy()
        threading.Thread(target=self.infer, args=(text, kind, frame, stamp, settings), daemon=True).start()

    def infer(self, text: str, kind: str, frame: bytes, stamp: str, settings: Settings) -> None:
        start = time.monotonic()
        try:
            content = []
            if kind == 'auto' and self.previous_frame is not None:
                content.extend([{'type': 'text', 'text': 'Предыдущий кадр:'}, image_part(self.previous_frame)])
                text_for_model = 'Сравни предыдущий и текущий кадры. Кратко опиши только видимые изменения; если их нет, так и скажи.'
            else:
                text_for_model = text
            content.extend([{'type': 'text', 'text': 'Текущий кадр:'}, image_part(frame), {'type': 'text', 'text': text_for_model}])
            payload = {'messages': [{'role': 'system', 'content': settings.prompt}, {'role': 'user', 'content': content}], 'max_tokens': settings.max_tokens, 'temperature': settings.temperature, 'stream': True}
            raw_answer = reasoning = ''
            finish = None
            with requests.post(f'{API}/v1/chat/completions', json=payload, timeout=(10, 180), stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines(chunk_size=128):
                    if not line.startswith(b'data:'):
                        continue
                    data = line[5:].strip()
                    if data == b'[DONE]':
                        break
                    packet = json.loads(data)
                    if packet.get('error'):
                        raise RuntimeError(str(packet['error']))
                    for choice in packet.get('choices', []):
                        delta = choice.get('delta', {})
                        raw_answer += delta.get('content') or ''
                        reasoning += delta.get('reasoning_content') or ''
                        finish = choice.get('finish_reason') or finish
                    answer, thought = split_reasoning(raw_answer, reasoning)
                    with self.lock:
                        if self.pending is not None:
                            self.pending.update(answer=answer, reasoning=thought, seconds=round(time.monotonic()-start, 2))
            answer, thought = split_reasoning(raw_answer, reasoning)
            if finish is None:
                raise RuntimeError('Поток ответа завершился без причины остановки')
            if finish == 'length':
                answer += '\n[Достигнут лимит генерации]'
            if not answer.strip():
                raise RuntimeError('Модель не вернула текст ответа')
            elapsed = time.monotonic() - start
            event = {'captured': stamp, 'kind': kind, 'question': text, 'answer': answer, 'reasoning': thought, 'finish': finish, 'seconds': round(elapsed, 2)}
            if kind == 'auto':
                with self.lock:
                    if not self.camera_stop.is_set():
                        self.previous_frame = frame
            if settings.save_observations:
                with sqlite3.connect(DATA / 'observations.sqlite3') as db:
                    db.execute('INSERT INTO events (captured,kind,question,answer,seconds,settings,frame) VALUES (?,?,?,?,?,?,?)', (stamp, kind, text, answer, elapsed, settings.model_dump_json(), frame if settings.save_frames else None))
            with self.lock:
                self.duration = elapsed
                self.events = (self.events + [event])[-100:]
                self.pending = None
        except Exception as exc:
            LOG.exception('Inference failed')
            with self.lock:
                self.error = str(exc)
                self.auto = False
        finally:
            with self.lock:
                self.busy = False
                self.pending = None

    def loop(self) -> None:
        next_at = 0.0
        while not self.shutdown.wait(0.2):
            with self.lock:
                if not self.auto or self.busy:
                    next_at = time.monotonic() + self.settings.interval
                    continue
                if time.monotonic() < next_at:
                    continue
                try:
                    if self.frame and self.previous_frame:
                        self.change_score = frame_difference(self.previous_frame, self.frame)
                        if self.settings.changes_only and self.change_score < self.settings.change_threshold:
                            next_at = time.monotonic() + self.settings.interval
                            continue
                    self.submit('Опиши текущую сцену кратко.', 'auto')
                    next_at = time.monotonic() + self.settings.interval
                except RuntimeError as exc:
                    self.error = str(exc)
                    self.auto = False


lab = Lab()


@asynccontextmanager
async def lifespan(app: FastAPI):
    lab.setup()
    try:
        yield
    finally:
        lab.shutdown.set()
        lab.camera_off()
        lab.model_off()


app = FastAPI(title='VisionLab', version='0.0.2', lifespan=lifespan)


@app.middleware('http')
async def local_only(request: Request, call_next):
    """Reject nonlocal hosts and cross-origin browser requests."""
    if request.headers.get('host') not in {'127.0.0.1:8090', 'localhost:8090', 'testserver'}:
        return Response(status_code=403)
    origin = request.headers.get('origin')
    if origin and origin not in {'http://127.0.0.1:8090', 'http://localhost:8090'}:
        return Response(status_code=403)
    return await call_next(request)


@app.get('/api/status')
def status() -> dict[str, Any]:
    """Return live state and measured resources."""
    try:
        gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'], text=True, timeout=2).splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        gpu = '—'
    with lab.lock:
        return {'camera': lab.frame is not None, 'camera_active': bool(lab.camera_thread and lab.camera_thread.is_alive()), 'model': lab.ready(), 'model_active': bool(lab.process and lab.process.poll() is None), 'auto': lab.auto, 'busy': lab.busy, 'fps': round(lab.fps, 1), 'error': lab.error, 'duration': round(lab.duration, 2), 'ram': round(psutil.virtual_memory().available / 1024**3, 1), 'gpu': gpu, 'last_time': lab.last_time, 'elapsed': round(time.monotonic()-lab.started, 1) if lab.busy else 0, 'change_score': round(lab.change_score, 2), 'settings': lab.settings.model_dump(), 'devices': sorted(str(p) for p in Path('/dev').glob('video[0-9]*'))}


@app.post('/api/settings')
def settings(value: Settings) -> dict[str, bool]:
    """Apply validated settings; camera mode changes require stop."""
    with lab.lock:
        old = lab.settings
        if lab.camera_thread and lab.camera_thread.is_alive() and any(getattr(old, k) != getattr(value, k) for k in ('camera', 'width', 'height', 'fps')):
            raise HTTPException(409, 'Остановите камеру перед сменой видеорежима')
        temp = DATA / 'settings.tmp'
        temp.write_text(value.model_dump_json(indent=2))
        temp.replace(DATA / 'settings.json')
        lab.settings = value
    return {'ok': True}


@app.post('/api/control/{action}')
def control(action: str) -> dict[str, bool]:
    """Execute one explicit lifecycle action."""
    try:
        if action == 'camera-on':
            lab.camera_on()
        elif action == 'camera-off':
            lab.camera_off()
        elif action == 'model-on':
            lab.model_on()
        elif action == 'model-off':
            lab.model_off()
        elif action == 'auto-on':
            with lab.lock:
                if not lab.frame or not lab.ready():
                    raise RuntimeError('Включите камеру и модель')
                lab.previous_frame = None
                lab.auto = True
        elif action == 'auto-off':
            with lab.lock:
                lab.auto = False
        elif action == 'snapshot':
            lab.submit('Опиши изображение.', 'manual')
        else:
            raise HTTPException(404)
    except (RuntimeError, OSError) as exc:
        raise HTTPException(409, str(exc)) from exc
    return {'ok': True}


@app.post('/api/question')
def question(value: Question) -> dict[str, bool]:
    """Analyze a fresh frame with a user question."""
    try:
        lab.submit(value.text, 'question')
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {'ok': True}


@app.get('/api/events')
def events() -> list[dict[str, Any]]:
    with lab.lock:
        return list(lab.events) + ([dict(lab.pending)] if lab.pending else [])


@app.get('/api/last')
def last() -> Response:
    with lab.lock:
        return Response(lab.last or b'', media_type='image/jpeg', status_code=200 if lab.last else 404, headers={'Cache-Control': 'no-store'})


@app.get('/api/stream')
def stream() -> StreamingResponse:
    def frames():
        while not lab.shutdown.is_set():
            with lab.lock:
                frame = lab.frame
            if frame:
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
            time.sleep(1 / 30)
    return StreamingResponse(frames(), media_type='multipart/x-mixed-replace; boundary=frame')


app.mount('/', StaticFiles(directory=ROOT / 'frontend', html=True), name='frontend')
