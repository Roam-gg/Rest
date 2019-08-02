from aiohttp import web
from db import User
from utils import user_wrapper, jsonify
import asyncio

@user_wrapper
async def get_me(request, services, extensions, **kwargs):
    user = kwargs.get('user')
    if user is None:
        raise web.HTTPBadRequest()
    return web.json_response(jsonify(user))

async def get_user(request, services, extensions, **kwargs):
    url_data = kwargs.get('url_data', {})
    if not url_data:
        raise web.HTTPBadRequest()
    uid = url_data['user.id']
    user = User.nodes.first_or_none(uid=uid)
    if user is None:
        raise web.HTTPBadRequest()
    return web.json_response(jsonify(user))

@user_wrapper
async def mod_me(request, services, extensions, **kwargs):
    sent_data = await request.json()
    user = kwargs.get('user')
    new_username = sent_data['username']
    user.username = new_username
    user.save()
    return web.json_response(jsonify(user))
