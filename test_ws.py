import websockets
import asyncio
import json

async def heartbeat(websocket):
    while True:
        await asyncio.sleep(45)
        await websocket.send('{"op": 1}')
        print('ba')

async def run():
    async with websockets.connect("ws://127.0.0.1:8082/") as websocket:
        hello = await websocket.recv()
        print('hello')
        await websocket.send('{"op": 2, "d": {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2NTUzNTc0OTU2NjYyMjU5NzEyIn0.hMjeQJqmK0OnORO04blCMKRJuVruzIQkRvI1XoijcjA"}}')
        print('identify')
        ready = json.loads(await websocket.recv())
        if ready['op'] == 0 and ready['t'] == 'READY':
            print('ready')
            asyncio.create_task(heartbeat(websocket))
            while True:
                event = json.loads(await websocket.recv())
                if event['op'] == 11: print('bump')
                else: print(event)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        pass
    loop.close()
