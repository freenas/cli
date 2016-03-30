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
from freenas.cli.namespace import EntityNamespace, EntitySubscriberBasedLoadMixin, description
from freenas.cli.output import ValueType


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Browse and query system log entries")
class LogNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The log namespace can be used to browse and query system log
    entries, where each entry is assigned a numeric log ID.
    """
    def __init__(self, name, context):
        super(LogNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'syslog'
        self.primary_key_name = 'seqnum'
        self.allow_edit = False
        self.allow_create = False

        self.add_property(
            descr='ID',
            name='id',
            get='seqnum',
            usage=_("""\
            Log entry ID. Read-only value as
            assigned by operating system."""),
            set=None,
            list=True
        )

        self.add_property(
            descr='Timestamp',
            name='timestamp',
            get='created_at',
            usage=_("""\
            Time the log entry was created. Read-only value
            as assigned by operating system."""),
            set=None,
            list=True,
            type=ValueType.TIME
        )

        self.add_property(
            descr='Priority',
            name='priority',
            get='priority',
            usage=_("""\
            Log entry priority. Read-only value as
            assigned by operating system. Possible values
            are emerg, alert, crit, err, warning, notice,
            info, and debug."""),
            list=True,
            set=None,
        )

        self.add_property(
            descr='Program',
            name='program',
            get='program',
            usage=_("""\
            Name of application which generated the log message. Read-only
            value as reported by operating system."""),
            list=True,
            set=None,
        )

        self.add_property(
            descr='Message',
            name='message',
            get='message',
            usage=_("""\
            Actual log entry. Read-only value as
            reported by the logging system."""),
            list=True,
            set=None,
        )

        self.primary_key = self.get_mapping('id')

    def serialize(self):
        raise NotImplementedError()


def _init(context):
    context.attach_namespace('/', LogNamespace('log', context))
