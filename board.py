from aiohttp import web
from db import User, Board, Role, Channel
from utils import user_wrapper, jsonify, EventType
from math import ceil
import asyncio

@user_wrapper
async def create_board(request, services, extensions, **kwargs):
    sent_data = await request.json()
    ws = extensions.get('ws')
    jwt = services.get('jwt')
    user = kwargs.get('user')

    snowflake = services.get('snowflake')
    new_board_uid = await snowflake()
    new_board = Board(
        uid=new_board_uid,
        name=sent_data['name'],
        owner_id=user.uid
    )
    new_board.save()
    owner_role = Role(
        uid=await snowflake(),
        name='Owner',
        permissions=8
    )
    everyone_role = Role(
        uid=await snowflake(),
        name='everyone',
        permissions=104324161
    )
    general_channel = Channel(
        uid=await snowflake(),
        name='general',
        type=0,
        topic='general discussion',
        position=0
    )
    owner_role.save()
    everyone_role.save()
    general_channel.save()
    everyone_role.parents.connect(owner_role)
    new_board.roles.connect(owner_role)
    new_board.roles.connect(everyone_role)
    new_board.subscribers.connect(user, {'role': owner_role.uid})
    new_board.channel_children.connect(general_channel)
    await ws.event(EventType.BOARD_CREATE, new_board.subscribers, board=new_board)
    return web.json_response(jsonify(new_board, requester=user))

@user_wrapper
async def get_board(*args, **kwargs):
    user = kwargs.get('user')

    url_data = kwargs.get('url_data')
    if not url_data:
        raise web.HTTPBadRequest()
    uid = url_data['board.id']
    board_object = Board.nodes.first_or_none(uid=uid)
    if board_object is None:
        raise web.HTTPBadRequest()
    return web.json_response(jsonify(board_object, requester=user))


@user_wrapper
async def mod_board(request, services, extensions, **kwargs):
    user = kwargs.get('user')
    ws = extensions.get('ws')
    url_data = kwargs.get('url_data')
    board_uid = url_data['board.id']
    board = Board.nodes.first_or_none(uid=board_uid)
    user_role_uid = board.subscribers.relationship(user).role
    user_role = Role.nodes.first(uid=user_role_uid)
    if (user_role.permissions & 8 == 8) or (user_role.permissions & 32 == 32):
        sent_data = await request.json()
        if not board:
            raise web.HTTPBadRequest()
        if sent_data.get('name'):
            board.name = sent_data.get('name')
        board.save()
        await ws.event(EventType.BOARD_UPDATE, board.subscribers, board=board)
        return web.json_response(jsonify(board, requester=user))
    raise web.HTTPForbidden(reason='Permission MANAGE_GUILD not set')

@user_wrapper
async def delete_board(request, services, *args, **kwargs):
    user = kwargs.get('user')
    board_uid = kwargs.get('url_data')['board.id']
    board = Board.nodes.first_or_none(uid=board_uid)
    if not board:
        raise web.HTTPBadRequest()
    owner_role = board.roles.filter(name__exact='Owner').first()
    owners = board.subscribers.match(role__exact=owner_role.uid)
    if user not in owners:
        raise web.HTTPForbidden(reason='You must be an owner of a board to delete it')
    bds = services.get('board_delete')
    votes_needed = ceil(len(owners)*0.75)
    bds.create(board, user, votes_needed)
    raise web.HTTPAccepted(text=f"{len(bds.timers[board.uid].votes)}/{votes_needed} Votes counted")

@user_wrapper
async def get_channels(*args, **kwargs):
    user = kwargs.get('user')
    board_uid = kwargs.get('url_data')['board.id']
    board = Board.nodes.first_or_none(uid=board_uid)
    if not board:
        return web.HTTPBadRequest()
    channels = board.channel_children
    return web.json_response([jsonify(channel) for channel in channels])

@user_wrapper
async def create_channel(request, services, extensions, *args, **kwargs):
    snowflake = services.get('snowflake')
    ws = extensions.get('ws')
    user = kwargs.get('user')
    board_uid = kwargs.get('url_data')['board.id']
    board = Board.nodes.first_or_none(uid=board_uid)
    if not board:
        raise web.HTTPBadRequest()
    user_role_uid = board.subscribers.relationship(user).role
    user_role = Role.nodes.first(uid=user_role_uid)
    if (user_role.permissions & 8 == 8) or (user_role.permissions & 16 == 16):
        sent_data = await request.json()
        name = sent_data['name']
        new_channel = Channel(
            uid=await snowflake(),
            name=name,
            type=sent_data.get('type') or 0,
            topic=sent_data.get('topic') or '',
            position=sent_data.get('position') or 0
        )
        new_channel.save()
        board.channel_children.connect(new_channel)
        await ws.event(EventType.CHANNEL_CREATE, board.subscribers, channel=new_channel)
        return web.json_response(jsonify(new_channel))
    raise web.HTTPForbidden(reason='Permission MANAGE_CHANNELS not set')

@user_wrapper
async def move_channel_positions(request, services, extensions, *args, **kwargs):
    ws = extensions.get('ws')
    user = kwargs.get('user')
    board_uid = kwargs.get('url_data')['board.id']
    board = Board.nodes.first_or_none(uid=board_uid)
    if not board:
        raise web.HTTPBadRequest()
    user_role_uid = board.subscribers.relationship(user).role
    user_role = Role.nodes.first(uid=user_role_uid)
    if (user_role.permissions & 8 == 8) or (user_role.permissions & 16 == 16):
        sent_data = await request.json()
        if len(sent_data) < 2:
            raise web.HTTPBadRequest()
        for data in sent_data:
            channel = board.channel_children.filter(uid__exact=data['uid']).first()
            channel.position = data['position']
            channel.save()
            await ws.event(EventType.CHANNEL_UPDATE, board.subscribers, channel=channel)
        raise web.HTTPNoContent()
