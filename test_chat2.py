#!/usr/bin/env python

import websockets
import asyncio
import aiohttp
import json
import os
import curses
import pprint
from time import sleep


class HeartbeatHandler:
    def __init__(self, ws, time):
        self.stop = asyncio.Event()
        self.t = None
        self.ws = ws
        self.time = time-2000

    async def stop(self):
        self.stop.set()
        await self.t

    async def start(self):
        self.t = asyncio.create_task(self.heartbeat())

    async def heartbeat(self):
        while not self.stop.is_set():
            await asyncio.sleep(self.time)
            await self.ws.send('{"op": 1}')

class EventListener:
    def __init__(self, ws):
        self.stop = asyncio.Event()
        self.t = None
        self.event_queue = asyncio.Queue()
        self.websocket = ws

    async def stop(self):
        self.stop.set()
        await self.t

    async def start(self):
        websocket = self.websocket
        while not self.stop.is_set():
            raw_event = await websocket.recv()
            event = json.loads(raw_event)
            await self.event_queue.put(event)

class User:
    def __init__(self, json):
        self.uid = json['uid']
        self.username = json['username']
        self.discriminator = json['discriminator']
class Message:
    def __init__(self, json):
        self.uid = json['uid']
        self.author = User(json['author'])
        self.timestamp = json['timestamp']
        self.content = json['content']
class Channel:
    def __init__(self, json):
        self.uid = json['uid']
        self.name = json['name']
        self.topic = json['topic']
        self.position = json['position']
        self.last_message = json['last_message_uid']
        self.messages = []
class Board:
    def __init__(self, json):
        self.uid = json['uid']
        self.name = json['name']
        #self.channels = [Channel(i) for i in json['channels']]
        self.channels = []
        with open('log.txt', 'a') as f:
            for i in json['channels']:
                f.write(json.dumps(i)+'\n')
                self.channels.append(Channel(i))

class Drawer:
    def __init__(self, host, token, websocket, inc_win, out_win, chn_win, brd_win):
        self.ws = websocket
        self.boards = []
        self.stop = asyncio.Event()
        self.tasks = []
        self.sel = [0, 0, 0]
        self.incoming_window = inc_win
        self.outgoing_window = out_win
        self.channel_window = chn_win
        self.board_window = brd_win
        self.host = host
        self.token = token

    async def stop(self):
        self.stop.set()
        await asyncio.wait_for(self.tasks, None)

    async def handle_events(self):
        with open('log.txt', 'a') as f:
            f.write('startarooni\n')
            while not self.stop.is_set():
                f.write('loop\n')
                event = json.loads(await self.ws.recv())
                f.write('eventi\n')
                if event['op'] == 0:
                    if event['t'] == 'BOARD_CREATE':
                        new_board = event['d']
                        f.write(json.dumps(new_board)+'\n')
                        self.boards.append(Board(new_board))
                        f.write(str(self.boards)+'\n')
                    elif event['t'] == 'MESSAGE_CREATE':
                        new_message = event['d']
                        f.write(json.dumps(new_message)+'\n')
                        for board in self.boards:
                            if board.uid == new_message['board_uid']:
                                target_board = board
                                break
                        for channel in target_board.channels:
                            if channel.uid == new_message['channel_uid']:
                                channel.messages.append(new_message)
                                channel.messages = channel.messages[:50]
                                break
            f.write('stoparooni\n')

    async def draw_screen(self):
        while not self.stop.is_set():
            self.incoming_window.erase()
            if len(self.boards) != 0:
                channel = self.boards[self.sel[0]].channels[self.sel[1]]
                for y, message in enumerate(channel.messages, 1):
                    self.incoming_window.addstr(
                        y,1,
                        f'{message.author.username}#{message.author}: {message.content}')
                    self.incoming_window.refresh()
                    self.channel_window.erase()
                    self.channel_window.border()
                for y, channel in enumerate(self.boards[self.sel[1]], 1):
                    if y == self.sel[0]+1:
                        self.channel_window.addstr(
                            y,1,
                            f'{channel.name}', curses.A_UNDERLINE if self.sel[2] == 0 else curses.A_STANDOUT)
                    else:
                        self.channel_window.addstr(
                            y,1,
                            f'{channel.name}')
                    self.channel_window.refresh()
                    self.board_window.erase()
                    self.board_window.boarder()
                for y, board in enumerate(self.boards, 1):
                    if y == self.sel[1]+1:
                        self.board_window.addstr(
                            y,1,
                            f'{board.name}', curses.A_UNDERLINE if self.sel[2] == 1 else curses.A_STANDOUT)
                    else:
                        self.board_window.addstr(
                            y,1,
                            f'{board.name}')

    async def handle_outgoing(self):
        self.outgoing_window.nodelay(True)
        self.outgoing_window.keypad(True)
        headers = {'Authorization': self.token}
        async with aiohttp.ClientSession(headers=headers) as session:
            while not self.stop.is_set():
                message = ''
                char = -1
                while char != 10:
                    await asyncio.sleep(0.001)
                    self.render_outgoing_window(message)
                    char = self.outgoing_window.getch(1, len(message)+1)
                    if char != -1:
                        if char not in range(32, 127):
                            if char == 127:
                                message = message[:-1]
                            elif char == curses.KEY_LEFT and self.sel[2] == 1:
                                self.sel[2] = 0
                            elif char == curses.KEY_RIGHT and self.sel[2] == 0:
                                self.sel[2] = 1
                            elif char == curses.KEY_UP and self.sel[self.sel[2]] == 0:
                                self.sel[self.sel[2]] = len(self.boards if self.sel[2] == 1 else self.boards[self.sel[0]])
                            elif char == curses.KEY_DOWN and self.sel[self.sel[2]] == len(self.boards if self.sel[2] == 1 else self.boards[self.sel[0]]):
                                self.sel[self.sel[2]] = 0
                        else:
                            message += chr(char)
                channel_uid = self.boards[self.sel[1]].channels[self.sel[0]].uid
                await session.post(
                    f'http://{self.host}:8081/channels/{channel_uid}/messages',
                    json={'content': message})

    def render_outgoing_window(self, message):
        w = self.outgoing_window
        w.erase()
        w.border()
        w.addstr(1,1, message)
        w.refresh()

    async def start(self):
        self.tasks.append(asyncio.create_task(self.handle_events()))
        self.tasks.append(asyncio.create_task(self.draw_screen()))
        #self.tasks.append(asyncio.create_task(self.handle_outgoing()))
        await asyncio.wait(self.tasks)

class Client:
    def __init__(self, login_window, outgoing_window, incoming_window, channel_window, board_window, loop=None):
        # lets login!
        username = ''
        password = ''
        host = ''
        char = -1
        selection = 0
        login_window.nodelay(True)
        curses.noecho()
        while char != 10:
#            sleep(0.001)
            self.render_login_window(username, password, host, login_window)
            if selection == 0:
                char = login_window.getch(1, len('Username: ' + username)+1)
            elif selection == 1:
                char = login_window.getch(1, len('Password: ' + password)+1)
            else:
                char = login_window.getch(1, len('Password: ' + password)+1)
            if char != -1:
                if char not in range(32, 127):
                    if char == 127:
                        if selection == 0:
                            username = username[:-1]
                        elif selection == 1:
                            password = password[:-1]
                        else:
                            host = host[:-1]
                    if char == 9:
                        selection = (selection + 1) % 3
                else:
                    if selection == 0:
                        username += chr(char)
                    elif selection == 1:
                        password += chr(char)
                    else:
                        host += chr(char)
        if not loop:
            loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.start(
                username,
                password,
                host,
                outgoing_window,
                incoming_window,
                channel_window,
                board_window))
        except KeyboardInterrupt:
            pass

    async def start(self, username, password, host, outw, inw, chnw, brdw):
        async with aiohttp.ClientSession() as session:
            async with session.post(f'http://{host}:8083/token', data={
                    'grant_type': 'password',
                    'username': username,
                    'password': password}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data['access_token']
                    refresh_token = data['refresh_token']
                    refresh_time = data['expires_in']
        async with websockets.connect(f'ws://{host}:8082') as websocket:
            hello = json.loads(await websocket.recv())
            await websocket.send(json.dumps({'op': 2, 'd': {'token': token}}))
            ready = json.loads(await websocket.recv())
            if ready['op'] == 0 and ready['t'] == 'READY':
                h = HeartbeatHandler(websocket, hello['d']['heartbeat_interval'])
                #e = EventListener(websocket)
                d = Drawer(host, token, websocket, outw, inw, chnw, brdw)
                tasks = []
                for c in (h, d):
                    tasks.append(asyncio.create_task(c.start()))
                with open('status.txt', 'a') as s:
                    while True:
                        s.write('---\n')
                        for task in tasks:
                            s.write(task.done())
                            await asyncio.sleep(1)

    def render_login_window(self, username, password, host, login_window):
        login_window.erase()
        login_window.border()
        login_window.addstr(1, 1, 'Username: ' + username)
        login_window.addstr(3, 1, 'Password: ' + '*'*len(password))
        login_window.addstr(5, 1, '    Host: ' + host)
        login_window.refresh()

def main(*args):
    rows, columns = os.popen('stty size', 'r').read().split()
    rows, columns = int(rows), int(columns)
    curses.initscr()
    y, x = int(rows/2)-5, int(columns/2)-100
    c = Client(
        #curses.newwin(7,  100, int(rows/2)-5, int(columns/2)-100), # login
        curses.newwin(7,  100, 0, 0), # login
        curses.newwin(3,  50, 0, 0), # outging
        curses.newwin(50, 100,   0, 0), # incoming
        curses.newwin(50,  50,  50, 0), # channel
        curses.newwin(50,  50,  50, 50)) # board

if __name__ == '__main__':
    curses.wrapper(main)
