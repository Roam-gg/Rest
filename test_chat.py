#!/usr/bin/env python

import websockets
import asyncio
import aiohttp
import json
import os
import sys
import curses
from curses.textpad import Textbox
import pprint
from time import sleep

curses.initscr()
message_win = curses.newwin(27, 100, 0, 0)
input_win = curses.newwin(3, 100, 52, 0)
heartbeat_win = curses.newwin(25, 50, 27, 0)
event_win = curses.newwin(25,50,27,50)
clear = lambda: os.system('clear')
message_buffer = []
stop = asyncio.Event()
loop = asyncio.get_event_loop()
CHANNEL_ID = 6555890469811781632
token = None
#username, password = sys.argv[1], sys.argv[2]

async def heartbeat(websocket, time):
    time_left = time-2000
    while not stop.is_set():
        heartbeat_win.erase()
        heartbeat_win.border()
        heartbeat_win.addstr(1, 1, "boop")
        heartbeat_win.addstr(2, 1, "boop period:" + str(time-2000))
        heartbeat_win.addstr(3, 1, "time left:" + str(time_left))
        heartbeat_win.refresh()
        await asyncio.sleep(1/1000)
        time_left -= 1
        if time_left == 0:
            await websocket.send('{"op": 1}')
            time_left = time-2000


async def message_listener(username, password):
    global message_buffer
    global token
    #global username
    #global password
#    username = ''
#    char = -1
#    last_char = char
#    f = open('log2txt', 'w')
#    f.write('start\n')
#    while char != 10:
#        char = -1
#        await asyncio.sleep(0.001)
#        input_win.erase()
#        input_win.border()
#        input_win.addstr(1,1,username)
#        input_win.addstr(2,1,str(last_char))
#        char = input_win.getch(1,len(username)+1)
#        if char != -1:
#            f.write(f'{char}\n')
#            if char not in range(32, 127):
#                last_char = char
#                if char == 127:
#                    username = username[:-1]
#                else:
#                    username += chr(char)
#                    f.write('u: '+username+'\n')
#        input_win.refresh()
#    f.write('username: '+username+'\n')
#    password = ''
#    char = -1
#    last_char = char
#    f.write('start\n')
#    while char != 10:
#        char = -1
#        await asyncio.sleep(0.001)
#        input_win.erase()
#        input_win.border()
#        input_win.addstr(1,1,password)
#        input_win.addstr(2,1,str(last_char))
#        char = input_win.getch(1,len(password)+1)
#        if char != -1:
#            if char not in range(32, 127):
#                last_char = char
#                if char == 127:
#                   password = password[:-1]
#               else:
#                   password += chr(char)
#       input_win.refresh()
#   f.write(password+'\n')
#   f.close()
    async with aiohttp.ClientSession() as session:
        async with session.post('http://127.0.0.1:8083/token', data={
                'grant_type': 'password',
                'username': username,
                'password': password,
        }) as resp:
            with open('log.txt', 'w') as f:
                f.write(f'resp_status: {resp.status}\n')
            if resp.status != 200:
                stop.set()
            else:
                data = await resp.json()
                token = data['access_token']
                refresh_token = data['refresh_token']
                refresh_time = data['expires_in']
                with open('log.txt', 'a') as f:
                    f.write(f'{token}\n')
                    f.write(f'{refresh_token}\n')
                    f.write(f'{refresh_time}\n')
                #asyncio.create_task(refresh_token_task(refresh_token, refresh_time))
            del password
    async with websockets.connect('ws://127.0.0.1:8082') as websocket:
        hello = json.loads(await websocket.recv())
        await websocket.send('{"op": 2, "d": {"token": "' + token + '"}}')
        with open('log.txt', 'a') as f:
            f.write(f'token: {token}\n')
        ready = json.loads(await websocket.recv())
        if ready['op'] == 0 and ready['t'] == 'READY':
            headers = {'Authorization': token}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get('http://127.0.0.1:8081/users/me') as resp:
                    data = await resp.json()
                    input_win.addstr(0, 0, f'Logged in as: {data["username"]}#{data["discriminator"]}')
                    input_win.refresh()
                    await asyncio.sleep(1)
                    input_win.erase()
                async with session.get(f'http://127.0.0.1:8081/channels/{CHANNEL_ID}') as resp:
                    data = await resp.json()
                    last_message_uid = data['last_message_uid']
                async with session.get(f'http://127.0.0.1:8081/channels/{CHANNEL_ID}/messages?before={last_message_uid}&limit=25') as resp:
                    data = await resp.json()
                    for message in data:
                        message_buffer.append(message)
            asyncio.create_task(heartbeat(websocket, hello['d']['heartbeat_interval']))
            asyncio.create_task(message_sender())
            while not stop.is_set():
                event = json.loads(await websocket.recv())
                pstring = pprint.pformat(event, width=49).split('\n')
                event_win.erase()
                event_win.border()
                for y, line in enumerate(pstring, 1):
                    event_win.addstr(y, 1, line)
                event_win.refresh()
                if event['op'] == 0 and event['t'] == 'MESSAGE_CREATE':
                    payload = event['d']
                    if payload['channel_uid'] == CHANNEL_ID:
                        message_buffer.append(payload)
                        if len(message_buffer) > 25:
                            message_buffer = message_buffer[-25:]
                message_win.erase()
                message_win.border()
                for row, message in enumerate(message_buffer, 1):
                    message_win.addstr(row, 1, f'> {message["author"]["username"]}#{message["author"]["discriminator"]}: {message["content"]}')
                message_win.refresh()

async def message_sender():
    headers = {'Authorization': token}
    async with aiohttp.ClientSession(headers=headers) as session:
        while not stop.is_set():
            message = ''
            char = -1
            last_char = char
            while char != 10:
                char = -1
                await asyncio.sleep(0.001)
                input_win.erase()
                input_win.border()
                input_win.addstr(1,1,message)
                input_win.addstr(2,1,str(last_char))
                char = input_win.getch(1,len(message)+1)
                if char != -1:
                    if char not in range(32, 127):
                        last_char = char
                        if char == 127:
                            message = message[:-1]
                    else:
                        message += chr(char)
                input_win.refresh()
            if message == ':q':
                stop.set()
            else:
                async with session.post(
                        f'http://127.0.0.1:8081/channels/{CHANNEL_ID}/messages',
                        json={'content': message}) as resp:
                    input_win.clear()
                    input_win.border()
                    input_win.addstr(1, 1, 'Status:' + str(resp.status))
                input_win.refresh()
                await asyncio.sleep(0.5)
                input_win.clear()

async def run(username, password):
#    tasks = list(map(asyncio.create_task, [message_listener()]))
#    group = await asyncio.gather(*tasks)
    await message_listener(username, password)
    await stop.wait()
#    group.cancel()
    input_win.clear()
    input_win.addstr('all cleared')
    input_win.refresh()

if __name__ == '__main__':
    input_win.clear()
    input_win.border()
    input_win.refresh()
    username = input_win.getstr(1,1).decode('UTF-8')
    input_win.clear()
    input_win.border()
    input_win.refresh()
    password = input_win.getstr(1,1).decode('UTF-8')
    input_win.clear()
    input_win.border()
    input_win.addstr(1,1,f'Username: {username}, password: {password}')
    input_win.refresh()
    sleep(1)
    input_win.nodelay(True)
    curses.noecho()
    try:
        loop.run_until_complete(run(username, password))
    except KeyboardInterrupt:
        pass
    loop.stop()
    loop.close()
