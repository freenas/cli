#
# Copyright 2016 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

from freenas.cli.namespace import (
    Namespace, ConfigNamespace, Command, CommandException, description,
    EntitySubscriberBasedLoadMixin, EntityNamespace
)
from freenas.cli.output import Object, Sequence, ValueType, format_value
from freenas.cli.descriptions import events
from freenas.cli.utils import post_save, parse_timedelta
import gettext


class SendMessageCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException("No message provided")

        context.call_sync('session.send_to_session', self.parent.entity['id'], str(args[0]))


@description("View sessions")
class SessionsNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    System sessions command, expands into commmands to show sessions.
    """

    def __init__(self, name, context):
        super(SessionsNamespace, self).__init__(name, context)
        self.allow_create = False
        self.allow_edit = False
        self.entity_subscriber_name = 'session'

        self.add_property(
            descr='Session ID',
            name='id',
            get='id',
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='IP Address',
            name='address',
            get='address',
        )

        self.add_property(
            descr='User name',
            name='username',
            get='username',
        )

        self.add_property(
            descr='Started at',
            name='started',
            get='started_at',
            type=ValueType.TIME
        )

        self.add_property(
            descr='Ended at',
            name='ended',
            get='ended_at',
            type=ValueType.TIME
        )

        self.primary_key = self.get_mapping('id')
        self.entity_commands = lambda this: {
            'send': SendMessageCommand(this)
        }

    def serialize(self):
        raise NotImplementedError()


def _init(context):
    context.attach_namespace('/', SessionsNamespace('session', context))
