from neomodel import (StructuredNode, StructuredRel, StringProperty,
                      IntegerProperty, JSONProperty, RelationshipTo,
                      RelationshipFrom, ArrayProperty, DateTimeProperty,
                      BooleanProperty, EmailProperty, One, OneOrMore, ZeroOrMore)

######################################################################
#                                 Edges                              #
######################################################################


class Subscribed_To(StructuredRel):
    nickname = IntegerProperty(required=False)
    role = IntegerProperty(required=True)

######################################################################
#                                 Nodes                              #
######################################################################


class Application(StructuredNode):
    uid = IntegerProperty(unique_index=True, required=True)
    name = StringProperty(required=True)
    description = StringProperty(required=True)
    redirect_uri = StringProperty(required=True)

    owner = RelationshipFrom('User', 'OWNS', cardinality=One)

class Client(StructuredNode):
    uid = IntegerProperty(unique_index=True, required=True)
    username = StringProperty(required=True)
    discriminator = StringProperty(required=True)

    messages = RelationshipFrom('Message', 'SAID_BY', cardinality=ZeroOrMore)
    boards = RelationshipTo('Board', 'SUBSCRIBED_TO', cardinality=ZeroOrMore)

class User(Client):
    hashp = StringProperty(required=True)

    applications = RelationshipTo('Application', 'OWNS', cardinality=ZeroOrMore)
    bots = RelationshipTo('Bot', 'OWNS', cardinality=ZeroOrMore)


class Bot(Client):
    token = StringProperty(required=True)

    owner = RelationshipFrom('User', 'OWNS', cardinality=One)


class Message(StructuredNode):
    uid = IntegerProperty(unique_index=True, required=True)
    content = StringProperty(required=True)

    channel = RelationshipTo('Channel', 'POSTED_TO', cardinality=One)
    author = RelationshipTo('User', 'SAID_BY', cardinality=One)


class Board(StructuredNode):
    uid = IntegerProperty(unique_index=True, required=True)
    name = StringProperty(required=True)
#    owner_id = IntegerProperty(required=True)

    subscribers = RelationshipFrom(
        'User', 'SUBSCRIBED_TO', model=Subscribed_To, cardinality=OneOrMore)

    roles = RelationshipFrom('Role', 'ROLE_OF', cardinality=OneOrMore)
    board_parents = RelationshipTo('Board', 'B_CHILD_OF')
    board_children = RelationshipFrom('Board', 'B_CHILD_OF')
    channel_children = RelationshipFrom('Channel', 'CHANNEL_OF', cardinality=OneOrMore)


class Channel(StructuredNode):
    uid = IntegerProperty(unique_index=True, required=True)
    position = IntegerProperty(required=True)
    type = IntegerProperty(required=True)
    name = StringProperty(required=True)
    topic = StringProperty(required=False)

    board_parent = RelationshipTo('Board', 'CHANNEL_OF', cardinality=One)
    messages = RelationshipFrom('Message', 'POSTED_TO', cardinality=ZeroOrMore)

class Role(StructuredNode):
    uid = IntegerProperty(unique_index=True, required=True)
    name = StringProperty(required=True)
    permissions = IntegerProperty(required=True)

    parents = RelationshipTo('Role', 'R_CHILD_OF')
    board = RelationshipFrom('Board', 'ROLE_OF', cardinality=One)
