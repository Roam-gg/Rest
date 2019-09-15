import asyncio
import websockets
import json
import logging

from sys import stdout
from db import User
from time import time
from roamrs import Extension
from enum import Enum
from aiostream import stream, pipe
from utils import jsonify, EventType

LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    LOGGER.setLevel(logging.INFO)
    HANDLER = logging.StreamHandler(stdout)
    HANDLER.setLevel(logging.INFO)
    FORMATTER = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    HANDLER.setFormatter(FORMATTER)
    LOGGER.addHandler(HANDLER)
   
class RoamWebSocketHandler:
    def __init__(self, websocket, user):
        self.user = user
        self.events = asyncio.Queue()
        self.last_heartbeat = time()
        self._stop = asyncio.Event()
        self.websocket = websocket
        self.incorrect_blips = 0

    async def stop(self):
        LOGGER.info('Stopping Websocket handler')
        self._stop.set()

    async def __call__(self):
        LOGGER.info('Starting Websocket handler')
        t1 = asyncio.create_task(self._keep_alive())
        t2 = asyncio.create_task(self._handle_msg())
        t3 = asyncio.create_task(self._handle_event())
        async for board in stream.iterate(self.user.boards):
            await self.events.put((EventType.BOARD_CREATE, board))
        await asyncio.wait([t1, t2, t3])

    async def _handle_event(self):
        while True:
            event, kwargs = await self.events.get()
            data = {'op': 0, 't': event.value}
            LOGGER.info('Sending %s event to user %s#%s (id: %s)', event, self.user.username, self.user.discriminator, self.user.uid)
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
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(self.websocket.recv(), timeout=1))
            except asyncio.TimeoutError:
                pass
            else:
                if msg['op'] == 1:
                    if time() - self.last_heartbeat < 15:
                        if self.incorrect_blips == 5:
                            LOGGER.warning('Closing gateway for user: %s#%s (id: %s). REASON: 4008 (Too fast, slow down)',
                                           self.user.username, self.user.discriminator, self.user.uid)
                            await self.websocket.close(4008, 'Too fast, slow down')
                            self._stop.set()
                            return
                        LOGGER.info('Telling user: %s#%s (id: %s) to slow down.', self.user.username,
                                    self.user.discriminator, self.user.uid)
                        await self.websocket.send(json.dumps({'op': 12}))
                        self.incorrect_blips += 1
                    else:
                        LOGGER.info('Heartbeat from user: %s#%s (id: %s)', self.user.username, self.user.discriminator,
                                    self.user.uid)
                        await self.websocket.send(json.dumps({'op': 11}))
                        self.last_heartbeat = time()
                        self.incorrect_blips = 0
                elif msg['op'] == 2:
                    LOGGER.warning('Closing gateway for user: %s#%s (id: %s). REASON: 4005 (Already authenticated)')
                    await self.websocket.close(4005, 'Already authenticated')
                    self._stop.set()
                    return

    async def _keep_alive(self):
        while True:
            await asyncio.sleep(1)
            if time() - self.last_heartbeat > 25:
                self.incorrect_blips += 1
            if self.incorrect_blips == 5:
                LOGGER.warning('Closing gateway for user: %s#%s (id: %s). REASON: 4009 (Too slow)')
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
        handlers = (stream.iterate(users)
                         | pipe.filter(lambda u: u.uid in self.handlers)
                         | pipe.map(lambda u: self.handlers.get(u.uid)))
        async with handlers.stream() as handlers:
            async for handler in handlers:
                await handler.events.put((event, kwargs))

    async def event(self, event, users, **kwargs):
        return asyncio.create_task(self._event(event, users, **kwargs))

    async def handler(self, websocket, path):
        auth = self.services.get('auth')
        await websocket.send(json.dumps({
            'op': 10,
            'd': {'heartbeat_interval': 20000}}))
        try:
            identify = json.loads(await websocket.recv())
        except json.decoder.JSONDecodeError:
            LOGGER.warning('Closing gateway for user: ?#? (id: ?). REASON: 4002 (What was that?)')
            await websocket.close(4002, 'What was that?')
            return
        try:
            if identify['op'] != 2:
                LOGGER.warning('Closing gateway for user: ?#? (id: ?). REASON: 4003 (Not authenticated)')
                await websocket.close(4003, 'Not authenticated')
                return
            token_data = identify['d']['token']
        except KeyError:
            LOGGER.warning('Closing gateway for user: ?#? (id: ?). REASON: 4001 (The identify payload was not valid)')
            await websocket.close(4001, 'The identify payload was not valid')
            return
        user_details = await auth.get_user(token_data)
        if user_details == {}:
            LOGGER.warning('Closing gateway for user: ?#? (id: ?). REASON: 4004 (The token you sent was invalid)')
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
        LOGGER.info('Gateway ready for user: %s#%s (id: %s)', user_object.username, user_object.discriminator,
                    user_object.uid)
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
