#+
# Copyright 2014 iXsystems, Inc.
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
    RpcBasedLoadMixin, EntityNamespace
)
from freenas.cli.output import Object, Sequence, ValueType, format_value
from freenas.cli.descriptions import events
from freenas.cli.utils import post_save, parse_timedelta
import gettext

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Shuts the system down")
class ShutdownCommand(Command):
    """
    Usage: shutdown

    Shuts the system down.
    """

    def run(self, context, args, kwargs, opargs):
        context.submit_task('system.shutdown')
        return _("The system will now shutdown...")


@description("Reboots the system")
class RebootCommand(Command):
    """
    Usage: reboot delay=<delay>

    Examples: reboot
              reboot delay=1:10.10 (1hour 10 minutes 10 seconds)
              reboot delay=0:10 (10 minutes)
              reboot delay=0:0.10 (10 seconds)

    Reboots the system.
    """

    def run(self, context, args, kwargs, opargs):
        delay = kwargs.get('delay', None)
        if delay:
            delay = parse_timedelta(delay).seconds
        context.submit_task('system.reboot', delay)
        return _("The system will now reboot...")


@description("System power management options")
class SystemNamespace(EntityNamespace):
    """
    The system namespace provides power management commands.
    """
    def __init__(self, name, context):
        super(SystemNamespace, self).__init__(name, context)
        self.context = context
        self.allow_create = False

        self.extra_commands = {
            'reboot': RebootCommand(),
            'shutdown': ShutdownCommand()
        }

    def commands(self):
        cmds = super(SystemNamespace, self).commands()
        del cmds['show']
        return cmds


def _init(context):
    context.attach_namespace('/', SystemNamespace('system', context))
    context.map_tasks('system.*', SystemNamespace)
