from aiohttp import ClientSession
from functools import wraps
import asyncio
from datetime import datetime
from db import User, Board, Channel, Role, Message
from roamrs import Service, Extension
from enum import Enum

EPOCH = 1558915200

class EventType(Enum):
    BOARD_CREATE = 'BOARD_CREATE'
    BOARD_UPDATE = 'BOARD_UPDATE'
    BOARD_DELETE = 'BOARD_DELETE'
    CHANNEL_CREATE = 'CHANNEL_CREATE'
    CHANNEL_UPDATE = 'CHANNEL_UPDATE'
    CHANNEL_DELETE = 'CHANNEL_DELETE'
    MESSAGE_CREATE = 'MESSAGE_CREATE'

class SnowflakeService(Service):
    __slots__ = ('url', '__session')
    def __init__(self, url, *args, **kwargs):
        self.url = url
        self.__session = ClientSession()

    async def __call__(self):
        async with self.__session.get(self.url) as resp:
            return int((await resp.json())['snowflake'])


class CheckForTime:
    def __init__(self, timeout, callback):
        self._timeout = timeout
        self._counter = 0
        self._callback = callback
        self.task = asyncio.create_task(self._job())

    async def _job(self):
        result = False
        while self._counter < self._timeout and not result:
            await asyncio.sleep(1)
            self._counter += 1
            result = await self._callback()

    def cancel(self):
        self.task.cancel()


class BoardDeleteTimer(CheckForTime):
    def __init__(self, board, required_votes, websocket):
        super().__init__(5*60, self.delete_board)
        self.board = board
        self.votes = []
        self.votes_required = required_votes
        self.ws = websocket

    async def delete_board(self):
        if len(self.votes) >= self.votes_required:
            roles = self.board.roles
            task = await self.ws.event(EventType.BOARD_DELETE, self.board.subscribers, board=self.board)
            await task
            for role in roles:
                role.delete()
            for channel in self.board.channel_children:
                channel.delete()
            self.board.delete()
            return True
        return False


class BoardDeleteService(Service):
    #__slots__ = ('timers', '_task', 'loop', 'ws')
    def __init__(self, extensions):
        self.ws = extensions.get('ws')
        self.timers = {}

    def create(self, board, user, required_votes):
        self.clear()
        if self.timers.get(board.uid):
            if user not in self.timers.get(board.uid).votes:
                self.timers[board.uid].votes.append(user)
        else:
            self.timers[board.uid] = BoardDeleteTimer(board, required_votes, self.ws)
            self.timers[board.uid].votes.append(user)

    def clear(self):
        self.timers = {b: t for b, t in self.timers.items() if not t.task.done()}

def snowflake_to_time(snowflake):
    snowflake = snowflake >> 22
    snowflake += EPOCH
    snowflake /= 1000
    return datetime.utcfromtimestamp(snowflake).isoformat()


def user_wrapper(func):
    @wraps(func)
    async def wrapper(request, services, extensions, **kwargs):
        auth = services.get('roamgg_token')
        token_str = request.headers.get('Authorization')
        user_uid = (await auth.get_user(token_str))['uid']
        user_object = User.nodes.first(uid=user_uid)
        kwargs['user'] = user_object
        return await func(request, services, extensions, **kwargs)
    return wrapper


def jsonify(o, **kwargs):
    if isinstance(o, Board):
        requester = kwargs['requester']
        owner_role = o.roles.filter(name__exact='Owner').first()
        owners = o.subscribers.match(role__exact=owner_role.uid)
        return {
            'uid': o.uid,
            'name': o.name,
            'channels': list(map(jsonify, o.channel_children)),
            'roles': list(map(jsonify, o.roles)),
            'owner_uids': [owner.uid for owner in owners],
            'owner': requester in owners}
    elif isinstance(o, Channel):
        if o.messages:
            last_message = o.messages.order_by('-uid').first()
        else:
            last_message = None
        j = {
            'uid': o.uid,
            'type': o.type,
            'name': o.name,
            'topic': o.topic,
            'position': o.position,
            'board_uid': o.board_parent.single().uid
        }
        if last_message:
            j['last_message_uid'] = last_message.uid
        return j
    elif isinstance(o, Role):
        return {
            'uid': o.uid,
            'name': o.name,
            'permissions': o.permissions,
        }
    elif isinstance(o, User):
        return {
            'uid': o.uid,
            'username': o.username,
            'discriminator': o.discriminator
        }
    elif isinstance(o, Message):
        channel = o.channel.single()
        board = channel.board_parent.single()
        author = o.author.single()
        return {
            'uid': o.uid,
            'channel_uid': channel.uid,
            'board_uid': board.uid,
            'author': jsonify(author),
            'timestamp': snowflake_to_time(o.uid),
            'content': o.content
        }
