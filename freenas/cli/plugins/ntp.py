# coding=utf-8
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
    Command, Namespace, EntityNamespace, TaskBasedSaveMixin,
    RpcBasedLoadMixin, description, CommandException
)
from freenas.cli.output import ValueType


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description(_("Manage NTP servers"))
class NTPServersNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """ The NTP server namespace provides commands for managing NTP servers """
    def __init__(self, name, context):
        super(NTPServersNamespace, self).__init__(name, context)

        self.context = context
        self.query_call = 'ntp_server.query'
        self.create_task = 'ntp_server.create'
        self.update_task = 'ntp_server.update'
        self.delete_task = 'ntp_server.delete'
        self.required_props = ['name', 'address']
        self.primary_key_name = 'id'
        self.localdoc['CreateEntityCommand'] = _("""\
            Usage: create <name> address=<address> <property>=<value> ...

            Examples: create myntp address=utcnist.colorado.edu

            Adds an NTP server for syncing with. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = _("""\
            Usage: set <property>=<value> ...

            Examples: set address=utcnist2.colorado.edu
                      set burst=True
                      set preferred=yes
                      set minpoll=6
                      set maxpoll=15

            Sets a user property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['DeleteEntityCommand'] = _("""\
            Usage: delete 

            Deletes the specified NTP server.""")

        self.add_property(
            descr='Name',
            name='name',
            get='id',
            set='id',
            list=True,
            type=ValueType.STRING
        )

        self.add_property(
            descr='Address',
            name='address',
            get='address',
            set='address',
            list=True,
            usage=_("Must be a valid hostname for an NTP server"),
            type=ValueType.STRING
        )

        self.add_property(
            descr='Burst',
            name='burst',
            get='burst',
            set='burst',
            list=True,
            usage=_("""\
                    Can be set to true or false, if true this option will send 8 packets
                    instead of 1 on each poll interval to the server while the server is
                    reachable for improved timekeeping."""),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Initial Burst',
            name='iburst',
            get='iburst',
            set='iburst',
            list=True,
            usage=_("""\
                    Can be set to true or false, if true this option will send 8 packets
                    instead of 1 on each poll interval to the server while the server is
                    not reachable for improved synchronization."""),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Preferred',
            name='prefer',
            get='prefer',
            set='prefer',
            list=True,
            usage=_("""\
                    Can be set to yes or no, if true then this will be the preferred server."""),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Min Poll',
            name='minpoll',
            get='minpoll',
            set='minpoll',
            list=True,
            usage=_("""\
                    An integer value that ranges between 4 and 1 minus the max poll value."""),
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Max Poll',
            name='maxpoll',
            get='maxpoll',
            set='maxpoll',
            usage=_("""\
                    An integer value that ranges between 17 and 1 plus the min poll value."""),
            list=True,
            type=ValueType.NUMBER
        )

        self.primary_key = self.get_mapping('name')

    def delete(self, this, kwargs):
        self.context.submit_task('ntp_server.delete', this.entity['id'])

def _init(context):
    context.attach_namespace('/', NTPServersNamespace('ntp', context))
