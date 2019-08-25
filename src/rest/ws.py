import asyncio
import websockets
import json
from db import User
from time import time
from roamrs import Extension
from enum import Enum
from aiostream import stream, pipe
from utils import jsonify, EventType

class RoamWebSocketHandler:
    def __init__(self, websocket, user):
        self.user = user
        self.events = asyncio.Queue()
        self.last_heartbeat = time()
        self._stop = asyncio.Event()
        self.websocket = websocket

    async def stop(self):
        self._stop.set()

    async def __call__(self):
        t1 = asyncio.create_task(self._keep_alive())
        t2 = asyncio.create_task(self._handle_msg())
        t3 = asyncio.create_task(self._handle_event())
        async for board in stream.iterate(self.user.boards):
            await self.events.put((EventType.BOARD_CREATE, board))
        await asyncio.wait([t1, t2, t3])

    async def _handle_event(self):
        while True:
            event, kwargs = await self.events.get()
            print(f'Event is: {event}')
            print(f'Kwargs are: {kwargs}')
            data = {'op': 0, 't': event.value}
            if event in [EventType.BOARD_CREATE, EventType.BOARD_UPDATE]:
                data['d'] = jsonify(kwargs.get('board'), requester=self.user)
            elif event is EventType.BOARD_DELETE:
                data['d'] = {'uid': kwargs.get('board').uid, 'unavailable': False}
            elif event in [EventType.CHANNEL_CREATE, EventType.CHANNEL_UPDATE, EventType.CHANNEL_DELETE]:
                data['d'] = jsonify(kwargs.get('channel'))
            elif event in [EventType.MESSAGE_CREATE]:
                data['d'] = jsonify(kwargs.get('message'))
            await self.websocket.send(json.dumps(data))

    async def _handle_msg(self):
        incorrect_blips = 0
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(self.websocket.recv(), timeout=1))
            except asyncio.TimeoutError:
                pass
            else:
                if msg['op'] == 1:
                    if time() - self.last_heartbeat < 15:
                        if incorrect_blips == 5:
                            await self.websocket.close(4008, 'Too fast, slow down')
                            self._stop.set()
                            return
                        await self.websocket.send(json.dumps({'op': 12}))
                        incorrect_blips += 1
                    else:
                        await self.websocket.send(json.dumps({'op': 11}))
                        self.last_heartbeat = time()
                        incorrect_blips = 0
                elif msg['op'] == 2:
                    await self.websocket.close(4005, 'Already authenticated')
                    self._stop.set()
                    return

    async def _keep_alive(self):
        while True:
            await asyncio.sleep(1)
            if time() - self.last_heartbeat > 25:
                await self.websocket.close(4009, 'Too slow')
                self._stop.set()
                return

class WebSocketExtension(Extension):
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self._stop = asyncio.Event()
        self.handlers = {}
        self.services = None
        self.extensions = None

    async def _event(self, event, users, **kwargs):
        print('assigning event!')
        handlers = (stream.iterate(users)
                         | pipe.filter(lambda u: u.uid in self.handlers)
                         | pipe.map(lambda u: self.handlers.get(u.uid)))
        async with handlers.stream() as handlers:
            async for handler in handlers:
                print(f'assigning event to: {handler.user.username}#{handler.user.discriminator}')
                await handler.events.put((event, kwargs))

    async def event(self, event, users, **kwargs):
        print('event started!')
        return asyncio.create_task(self._event(event, users, **kwargs))

    async def handler(self, websocket, path):
        auth = self.services.get('roamgg_token')
        await websocket.send(json.dumps({
            'op': 10,
            'd': {'heartbeat_interval': 20000}}))
        try:
            identify = json.loads(await websocket.recv())
        except json.decoder.JSONDecodeError:
            await websocket.close(4002, 'What was that?')
            return
        try:
            if identify['op'] != 2:
                await websocket.close(4003, 'Not authenticated')
                return
            token_data = identify['d']['token']
        except KeyError:
            await websocket.close(4001, 'The identify payload was not valid')
            return
        user_details = await auth.get_user(token_data)
        if user_details == {}:
            await websocket.close(4004, 'The token you sent is invalid')
            return
        user_object = User.nodes.first(uid=user_details['uid'])
        handler = RoamWebSocketHandler(websocket, user_object)
        boards = user_object.boards
        self.handlers[user_details['uid']] = handler
        await websocket.send(json.dumps({
            'op': 0,
            'd': {
                'user': jsonify(user_object),
                'boards': [{'uid': b.uid, 'unavailable': True} for b in boards]},
            't': 'READY'
        }))
        await handler()

    async def __call__(self, services, extensions):
        self.services = services
        self.extensions = extensions
        asyncio.create_task(self._start())

    async def _start(self):
        async with websockets.serve(self.handler, self.host, self.port):
            await self._stop.wait()

    async def stop(self):
        for handler in self.handlers.values():
            await handler.stop()
        self._stop.set()
