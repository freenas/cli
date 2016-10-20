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

import gettext
from freenas.cli.namespace import (
    Namespace, Command, CommandException, description,
)
from freenas.utils import query as q
from freenas.cli.complete import NullComplete, EnumComplete
from freenas.cli.output import Sequence

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Create a support ticket from the CLI")
class CreateSupportTicketCommand(Command):
    """
    Creates support ticket.
    Username and password needs to be provided first.
    """
    ticket_categories = {}

    def run(self, context, args, kwargs, opargs):
        if not kwargs.get('username') or not kwargs.get('password'):
            raise CommandException(
                'You have to provide a bug tracking system password and username in order to submit a ticket'
            )

        if not kwargs.get('subject'):
            raise CommandException(_('You have to provide a subject for a ticket'))

        if not kwargs.get('description'):
            raise CommandException(_('You have to provide a description for a ticket'))

        if not kwargs.get('type'):
            raise CommandException(_('You have to provide a type of the ticket: bug/feature'))

        if not kwargs.get('category'):
            raise CommandException(_('You have to provide a category for the ticket'))

        if not kwargs.get('attach_debug_data'):
            kwargs['debug'] = True
        else:
            kwargs['debug'] = True if kwargs.pop('attach_debug_data') == 'yes' else False

        if kwargs.get('attachments') and isinstance(kwargs['attachments'], str):
            kwargs['attachments'] = [kwargs['attachments']]

        if not self.ticket_categories:
            self.ticket_categories.update(
                context.call_sync('support.categories', kwargs['username'], kwargs['password'])
            )

        kwargs['category'] = self.ticket_categories[kwargs['category']]

        ticket_result = context.call_task_sync('support.submit', kwargs)
        if ticket_result.get('result') and ticket_result['result'][0] is not None:
            return Sequence(
                'Submitted ticket number:{0}. {1}'.format(ticket_result['result'][0], ticket_result['result'][1])
            )

    def complete(self, context, **kwargs):
        props = []
        username = q.get(kwargs, 'kwargs.username')
        password = q.get(kwargs, 'kwargs.password')
        if username and password:
            if not self.ticket_categories:
                self.ticket_categories.update(context.call_sync('support.categories', str(username), str(password)))

        if self.ticket_categories:
            props += [EnumComplete('category=', list(self.ticket_categories.keys()))]
            props += [NullComplete('subject=')]
            props += [NullComplete('description=')]
            props += [EnumComplete('type=', ['bug', 'feature'])]
            props += [EnumComplete('attach_debug_data=', ['yes', 'no'])]
            props += [NullComplete('attachments=')]

        return props + [
            NullComplete('username='),
            NullComplete('password='),
        ]


@description("Allows to fill support ticket report.")
class SupportNamespace(Namespace):
    """
    This namespace allows to create support ticket with optional debug information.
    Before filing a bug report or feature request, search http://bugs.freenas.org to ensure the issue has not already been reported.
    If it has, add a comment to the existing issue instead of creating a new one.
    For enterprise-grade storage solutions and support, please visit http://www.ixsystems.com/storage/.

    Please type the bug tracking system login and password first.
    """

    def __init__(self, name, context):
        super(SupportNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {'create_ticket': CreateSupportTicketCommand()}


def _init(context):
    context.attach_namespace('/', SupportNamespace('support', context))
