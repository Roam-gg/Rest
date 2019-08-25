"""Run the rest server"""
from time import sleep
import asyncio
import os

from neomodel import db as neodb
import neo4j
from roamrs import HTTPServer, Method
from ws import WebSocketExtension

from utils import SnowflakeService, BoardDeleteService
import user
import board
import channel

def main():
    """Run the servur"""
    env = os.environ
    while True:
        try:
            neodb.set_connection(f'bolt://{env["DB_USER"]}:{env["DB_PASS"]}@{env["DB_HOST"]}:7687')
        except neo4j.exceptions.ServiceUnavailable:
            sleep(1)
        else:
            break
    loop = asyncio.get_event_loop()
    snow = SnowflakeService.service_factory(f'http://{env["SNOW_HOST"]}:8080/')
    boardds = BoardDeleteService.service_factory()
    websocket = WebSocketExtension('0.0.0.0', 8000)
    server = HTTPServer(
        {'snowflake': snow, 'board_delete': boardds},
        {'ws': websocket},
        port=80,
        security_url=f'http://{env["AUTH_HOST"]}')
    server.router.add_handler('/users/me/', Method.GET, user.get_me)
    server.router.add_handler('/users/me/', Method.PATCH, user.mod_me)
    server.router.add_handler('/users/{user.id}', Method.GET, user.get_user)

    server.router.add_handler('/boards/', Method.POST, board.create_board)
    server.router.add_handler('/boards/{board.id}', Method.GET, board.get_board)
    server.router.add_handler('/boards/{board.id}', Method.PATCH, board.mod_board)
    server.router.add_handler('/boards/{board.id}', Method.DELETE, board.delete_board)
    server.router.add_handler('/boards/{board.id}/channels', Method.GET, board.get_channels)
    server.router.add_handler('/boards/{board.id}/channels', Method.POST, board.create_channel)
    server.router.add_handler(
        '/boards/{board.id}/channels',
        Method.PATCH,
        board.move_channel_positions)

    server.router.add_handler('/channels/{channel.id}', Method.GET, channel.get_channel)
    server.router.add_handler('/channels/{channel.id}', Method.PATCH, channel.mod_channel)
    server.router.add_handler('/channels/{channel.id}', Method.DELETE, channel.delete_channel)
    server.router.add_handler('/channels/{channel.id}/messages', Method.GET, channel.get_messages)
    server.router.add_handler(
        '/channels/{channel.id}/messages',
        Method.POST,
        channel.create_message)
    server.router.add_handler(
        '/channels/{channel.id}/messages/{message.id}',
        Method.GET,
        channel.get_message)

    loop.run_until_complete(server())
    loop.close()

if __name__ == '__main__':
    main()
