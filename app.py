"""STS prototype. One microphone stream, one translation session, many listeners."""
import asyncio
import base64
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import sounddevice as sd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from websockets.asyncio.client import connect

listeners = set()
status = "Starting"


async def broadcast(event):
    for queue in list(listeners):
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(event)


async def translate():
    global status
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        status = "Missing OPENAI_API_KEY. Restart after configuring it."
        return
    loop = asyncio.get_running_loop()
    audio = asyncio.Queue(maxsize=100)

    def enqueue(data):
        if audio.full():
            audio.get_nowait()
        audio.put_nowait(data)

    def capture(data, frames, time, flags):
        loop.call_soon_threadsafe(enqueue, bytes(data))

    try:
        async with connect(
            "wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate",
            additional_headers={"Authorization": f"Bearer {key}"},
            max_size=4 * 1024 * 1024,
        ) as upstream:
            await upstream.send(json.dumps({
                "type": "session.update",
                "session": {"audio": {"output": {"language": "en"}}},
            }))

            async def receive():
                global status
                async for message in upstream:
                    event = json.loads(message)
                    if event["type"] == "error":
                        raise RuntimeError(event.get("error", {}).get("message", "API error"))
                    if event["type"] in {
                        "session.output_audio.delta", "session.output_transcript.delta"
                    }:
                        await broadcast(event)

            device = os.environ.get("STS_AUDIO_DEVICE") or None
            with sd.RawInputStream(
                samplerate=24000, channels=1, dtype="int16",
                blocksize=2400, device=device, callback=capture,
            ):
                status = "Live"
                receiver = asyncio.create_task(receive())
                try:
                    while not receiver.done():
                        try:
                            chunk = await asyncio.wait_for(audio.get(), timeout=1)
                        except TimeoutError:
                            continue
                        await upstream.send(json.dumps({
                            "type": "session.input_audio_buffer.append",
                            "audio": base64.b64encode(chunk).decode(),
                        }))
                    await receiver
                finally:
                    receiver.cancel()
                    await asyncio.gather(receiver, return_exceptions=True)
    except Exception as exc:
        status = f"Stopped: {type(exc).__name__}: {exc}"
        await broadcast({"type": "status", "message": status})


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(translate())
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def home():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/health")
async def health():
    return {"status": status, "listeners": len(listeners)}


@app.websocket("/listen")
async def listen(socket: WebSocket):
    await socket.accept()
    queue = asyncio.Queue(maxsize=100)
    listeners.add(queue)
    await socket.send_json({"type": "status", "message": status})

    async def sender():
        while True:
            await socket.send_json(await queue.get())

    task = asyncio.create_task(sender())
    try:
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        listeners.discard(queue)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
