from aiohttp import web
from db import User, Board, Role, Channel, Message
from utils import user_wrapper, jsonify, EventType
import asyncio

async def get_channel(request, services, *args, **kwargs):
    channel_uid = kwargs['url_data'].get('channel.id')
    channel = Channel.nodes.first_or_none(uid=channel_uid)
    if not channel:
        raise web.HTTPBadRequest()
    return web.json_response(jsonify(channel))

@user_wrapper
async def mod_channel(request, services, extensions, **kwargs):
    user = kwargs.get('user')
    ws = extensions.get('ws')
    channel_uid = kwargs['url_data'].get('channel.id')
    channel = Channel.nodes.first_or_none(uid=channel_uid)
    if not channel:
        raise web.HTTPBadRequest()
    board = channel.board_parent.single()
    role_uid = board.subscribers.relationship(user).role
    role = Role.nodes.first(uid=role_uid)
    if (role.permissions & 8 == 8) or (role.permissions & 16 == 16):
        sent_data = await request.json()
        if sent_data.get('name'):
            channel.name = sent_data.get('name')
        if sent_data.get('topic'):
            channel.topic = sent_data.get('topic')
        if sent_data.get('position'):
            channel.position = sent_data.get('position')
        channel.save()
        await ws.event(EventType.CHANNEL_UPDATE, board.subscribers, channel=channel)
        return web.json_response(jsonify(channel))
    raise web.HTTPForbidden(reason='Permission MANAGE_CHANNELS not set')

@user_wrapper
async def delete_channel(request, services, extensions, **kwargs):
    user = kwargs.get('user')
    ws = extensions.get('ws')
    channel = Channel.nodes.first_or_none(uid=kwargs['url_data'].get('channel.id'))
    if not channel:
        raise web.HTTPBadRequest()
    board = channel.board_parent.single()
    role_uid = board.subscribers.relationship(user).role
    role = Role.nodes.first_or_none(uid=role_uid)
    if not role:
        raise web.HTTPBadRequest()
    if (role.permissions & 8 == 8) or (role.permissions & 16 == 16):
        j = jsonify(channel)
        channel.delete()
        await ws.event(EventType.CHANNEL_DELETE, board.subscribers, channel=channel)
        return web.json_response(j)
    raise web.HTTPForbidden(reason='Permission MANAGE_CHANNELS not set')

@user_wrapper
async def get_messages(request, *args, **kwargs):
    user = kwargs.get('user')
    channel = Channel.nodes.first_or_none(uid=kwargs['url_data'].get('channel.id'))
    if not channel:
        raise web.HTTPBadRequest()
    board = channel.board_parent.single()
    role_uid = board.subscribers.relationship(user).role
    role = Role.nodes.first_or_none(uid=role_uid)
    if not role:
        raise web.HTTPBadRequest()
    if (role.permissions & 8 == 8) or (role.permissions & 1024 == 1024):
        if not ((role.permissions & 65536 == 65536) or (role.permissions & 8 == 8)):
            return web.json_response([])
        sent_data = request.query
        around = sent_data.get('around')
        before = sent_data.get('before')
        after = sent_data.get('after')
        limit = int(sent_data.get('limit') or 50)
        if not 0 <= limit <= 100:
            raise web.HTTPBadRequest()
        if around:
            if before or after:
                raise web.HTTPBadRequest()
            before_messages = channel.messages.filter(uid__lt=around).order_by('-uid')[:int(limit/2)]
            after_messages = channel.messages.filter(uid__gt=around).order_by('uid')[:int(limit/2)]
            messages = before_messages + after_messages
        if before:
            if around or after:
                raise web.HTTPBadRequest()
            messages = channel.messages.filter(uid__lt=before).order_by('-uid')[:limit][::-1]
        if after:
            if around or before:
                raise web.HTTPBadRequest()
            messages = channel.messages.filter(uid__gt=after).order_by('uid')[:limit]
        return web.json_response([jsonify(msg) for msg in messages], content_type='application/json')

@user_wrapper
async def get_message(request, *args, **kwargs):
    user = kwargs.get('user')
    channel = Channel.nodes.first_or_none(uid=kwargs['url_data'].get('channel.id'))
    if not channel:
        raise web.HTTPBadRequest()
    board = channel.board_parent.single()
    role_uid = board.subscribers.relationship(user).role
    role = Role.nodes.first_or_none(uid=role_uid)
    if not role:
        raise web.HTTPBadRequest()
    if (role.permissions & 8 == 8) or (role.permissions & 65536 == 65536):
        message_uid = kwargs['url_data'].get('message.id')
        message = channel.messages.filter(uid__exact=message_uid).first_or_none()
        if not message:
            raise web.HTTPBadRequest()
        return web.json_response(jsonify(message))
    raise web.HTTPForbidden(reason='Permission READ_MESSAGE_HISTORY is not set')

@user_wrapper
async def create_message(request, services, extensions, **kwargs):
    user = kwargs.get('user')
    ws = extensions.get('ws')
    snowflake = services.get('snowflake')
    websocket = services.get('websocket')
    try:
        channel = Channel.nodes.first_or_none(uid=kwargs['url_data']['channel.id'])
    except KeyError:
        raise web.HTTPBadRequest()
    if not channel:
        raise web.HTTPBadRequest()
    board = channel.board_parent.single()
    role_uid = board.subscribers.relationship(user).role
    role = Role.nodes.first_or_none(uid=role_uid)
    if not role:
        raise web.HTTPBadRequest()
    if (role.permissions & 8 == 8) or (role.permissions & 2048 == 2048):
        message_data = await request.json()
        content = message_data['content']
        if content == '':
            raise web.HTTPBadRequest()
        new_message = Message(uid=await snowflake(), content=content)
        new_message.save()
        new_message.author.connect(user)
        new_message.channel.connect(channel)
        await ws.event(EventType.MESSAGE_CREATE, board.subscribers, message=new_message)
        return web.json_response(jsonify(new_message))
