#!/usr/bin/env python3
"""
WebSocket 推日志行
"""
import asyncio, websockets, os, time

LOG = "/app/logs/app.log"

async def logs(websocket, path):
    with open(LOG, "rb") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if line:
                await websocket.send(line.decode("utf-8"))
            else:
                await asyncio.sleep(0.2)

asyncio.run(websockets.serve(logs, "0.0.0.0", 8081))