"""Run the rest server"""
from time import sleep
import asyncio
import os

from neomodel import db as neodb
import neo4j
from roamrs import HTTPServer, Method
from ws import WebSocketExtension

from utils import SnowflakeService, BoardDeleteService
from user import UserCog
from board import BoardCog
from channel import ChannelCog

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
    cogs = [UserCog(), BoardCog(), ChannelCog()]

    for cog in cogs:
        server.load_cog(cog)

    loop.run_until_complete(server())
    loop.close()

if __name__ == '__main__':
    main()
