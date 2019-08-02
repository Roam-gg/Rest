from neomodel import db as neodb
neodb.set_connection('bolt://neo4j:test@localhost:7687')
import user, board, channel
import asyncio
import signal
from roamrs import HTTPServer, JWTService, Method
from utils import SnowflakeService, BoardDeleteService
from ws import WebSocketExtension

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    s = SnowflakeService.service_factory('http://127.0.0.1:8080/')
    b = BoardDeleteService.service_factory()
    w = WebSocketExtension('0.0.0.0', 8082)
    server = HTTPServer({'snowflake': s, 'board_delete': b}, {'ws': w}, port=8081, security_url='http://127.0.0.1:8083/')
    server.router.add_handler('/users/me/', Method.GET, user.get_me)
    server.router.add_handler('/users/me/', Method.PATCH, user.mod_me)
    server.router.add_handler('/users/{user.id}', Method.GET, user.get_user)

    server.router.add_handler('/boards/', Method.POST, board.create_board)
    server.router.add_handler('/boards/{board.id}', Method.GET, board.get_board)
    server.router.add_handler('/boards/{board.id}', Method.PATCH, board.mod_board)
    server.router.add_handler('/boards/{board.id}', Method.DELETE, board.delete_board)
    server.router.add_handler('/boards/{board.id}/channels', Method.GET, board.get_channels)
    server.router.add_handler('/boards/{board.id}/channels', Method.POST, board.create_channel)
    server.router.add_handler('/boards/{board.id}/channels', Method.PATCH, board.move_channel_positions)

    server.router.add_handler('/channels/{channel.id}', Method.GET, channel.get_channel)
    server.router.add_handler('/channels/{channel.id}', Method.PATCH, channel.mod_channel)
    server.router.add_handler('/channels/{channel.id}', Method.DELETE, channel.delete_channel)
    server.router.add_handler('/channels/{channel.id}/messages', Method.GET, channel.get_messages)
    server.router.add_handler('/channels/{channel.id}/messages', Method.POST, channel.create_message)
    server.router.add_handler('/channels/{channel.id}/messages/{message.id}', Method.GET, channel.get_message)

    async def exit():
        print('stopping')
        loop.stop()

    def ask_exit():
        for task in asyncio.Task.all_tasks():
            task.cancel()
        asyncio.create_task(exit())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, ask_exit)
    loop.run_until_complete(server())
    print('close')
    loop.close()
