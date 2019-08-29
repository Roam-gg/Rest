from aiohttp import web
from roamrs import Cog, Method, route
from db import User
from utils import user_wrapper, jsonify

class UserCog(Cog):
    @route('/users/me/', Method.GET)
    @user_wrapper
    async def get_me(self, ctx):
        user = ctx.user
        if user is None:
            raise web.HTTPBadRequest()
        return ctx.respond(jsonify(user))

    @route('/users/{user.id}', Method.GET)
    async def get_user(self, ctx):
        url_data = ctx.url_data
        if not url_data:
            raise web.HTTPBadRequest()
        uid = url_data['user.id']
        user = User.nodes.first_or_none(uid=uid)
        if user is None:
            raise web.HTTPBadRequest()
        return ctx.respond(jsonify(user))

    @route('/users/me/', Method.PATCH)
    @user_wrapper
    async def mod_me(self, ctx):
        sent_data = ctx.sent_data
        user = ctx.user
        new_username = sent_data['username']
        user.username = new_username
        user.save()
        return ctx.respond(jsonify(user))
