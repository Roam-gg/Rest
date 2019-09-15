"""Run the rest server"""
from time import sleep
import asyncio
import os

from neomodel import db as neodb
import neo4j
from roamrs import HTTPServer
from roamrs.auth import TokenValidator
from ws import WebSocketExtension

from utils import SnowflakeService, BoardDeleteService
from user import UserCog
from board import BoardCog
from channel import ChannelCog

def main():
    """Run the server"""
    env = os.environ
    while True:
        try:
            neodb.set_connection(f'bolt://{env["DB_USER"]}:{env["DB_PASS"]}@{env["DB_HOST"]}:7687')
        except neo4j.exceptions.ServiceUnavailable:
            sleep(1)
        else:
            break
    loop = asyncio.get_event_loop()
    snow = SnowflakeService(f'http://{env["SNOW_HOST"]}:8080/')
    boardds = BoardDeleteService()
    auth = TokenValidator(f'http://{env["AUTH_HOST"]}')
    websocket = WebSocketExtension('0.0.0.0', 8000)
    server = HTTPServer(
        {'snowflake': snow, 'board_delete': boardds, 'auth': auth},
        {'ws': websocket},
        port=80)
    cogs = [UserCog(), BoardCog(), ChannelCog()]

    for cog in cogs:
        server.load_cog(cog)

    loop.run_until_complete(server())
    loop.close()

if __name__ == '__main__':
    main()
