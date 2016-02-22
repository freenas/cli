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


import gettext
import copy
from datetime import datetime
from freenas.cli.namespace import ConfigNamespace, Command, description
from freenas.cli.output import output_msg, ValueType, Table, read_value
from freenas.cli.utils import post_save


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


def get_short_version(check_str):
    version = []
    for x in check_str.split('-'):
        try:
            datetime.strptime(x, '%Y%m%d%H%M')
            version.append(x)
            break
        except:
            version.append(x)
    return '-'.join(version)


def update_check_utility(context):
    """
    A small helper function that checks for updates
    and returns the update operations to be performed
    if any else None
    """
    context.call_task_sync('update.check')
    updates = context.call_sync('update.get_update_ops')
    if updates:
        for update in updates:
            update['previous_version'] = (
                get_short_version(update['previous_version'])
                if update['previous_version'] else '-'
            )
            update['new_version'] = (
                get_short_version(update['new_version'])
                if update['new_version'] else '-'
            )
        return Table(updates, [
            Table.Column('Name', 'new_name'),
            Table.Column('Operation', 'operation'),
            Table.Column('Current Version', 'previous_version'),
            Table.Column('New Version', 'new_version')
            ])
    else:
        return None


@description("Prints current Update Train")
class CurrentTrainCommand(Command):
    """
    Usage: current_train

    Displays the current update train.
    """
    def run(self, context, args, kwargs, opargs):
        return context.call_sync('update.get_current_train')


@description("Lists the Available Update Trains")
class ShowTrainsCommand(Command):
    """
    Usage: show_trains

    Displays the available update trains from the update server.
    """
    def run(self, context, args, kwargs, opargs):
        trains = context.call_sync('update.trains')
        if trains is None:
            output_msg(_(
                "Could not fetch Available Trains from the Update Server. "
                "Please Check internet connectivity and try again."
                ))
        else:
            return Table(trains, [
                Table.Column('Name', 'name'),
                Table.Column('Description', 'description'),
                Table.Column('Sequence', 'sequence'),
                Table.Column('Current', 'current', vt=ValueType.BOOLEAN)
                ])


@description("Checks for New Updates")
class CheckNowCommand(Command):
    """
    Usge: check_now

    Checks for updates.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        update_ops = update_check_utility(context)
        self.parent.load()
        if update_ops:
            return update_ops
        else:
            output_msg(_("No new updates available."))


def download_message_formatter(msg):
    """
    A small function to be passed to submit_task
    to format progress message for when `tasks_blocking
    is set to True for Downloading Updates.
    """
    msg = msg.split('Rate', 1)[0].split('Size', 1)[0]
    msg = msg.split('Progress:')
    progress = None
    if len(msg) != 1:
        try:
            progress = int(msg[1])
        except:
            progress = None
        msg = msg[0]
    else:
        msg = msg[0]
    if progress:
        filled_width = int(float(progress/100.0) * 10)
        msg += ' [{0}{1}] :{2}%'.format('#'*filled_width, '_'*(10 - filled_width), progress)
    return msg


@description("Updates the system and reboots it (can be specified)")
class UpdateNowCommand(Command):
    """
    Usage: update_now [reboot=False]

    Installs updates if they are available and restarts the system if told to do so.

    Example: update_now (This will not reboot the system post update)
             update_now reboot=True (This will reboot the system post update)
    """

    def __init__(self):
        super(UpdateNowCommand, self).__init__()
        self.task_id = None
        self.reboot = False
        self.context = None

    def task_callback(self, task_state):
        if task_state in ('FINISHED'):
            task_data = self.context.entity_subscribers['task'].get(self.task_id)
            if task_data["result"]:
                if self.reboot:
                    output_msg(_(
                        "Updates Downloaded and Installed SUccessfully."
                        " System going for a reboot now."
                    ))
                else:
                    output_msg(_(
                        "System successfully updated."
                        " Please reboot now using the '/ system reboot' command"
                    ))

    def run(self, context, args, kwargs, opargs):
        self.context = context
        self.reboot = read_value(kwargs.get('reboot', self.reboot), tv=ValueType.BOOLEAN)
        self.task_id = context.submit_task(
            'update.updatenow',
            self.reboot,
            callback=self.task_callback
        )


@description("System Updates and their Configuration")
class UpdateNamespace(ConfigNamespace):
    """
    The update namespace provides commands for updating and for
    configuring system updates.
    """
    def __init__(self, name, context):
        super(UpdateNamespace, self).__init__(name, context)
        self.context = context
        self.update_info = None

        self.add_property(
            descr='Set Update Train',
            name='train',
            type=ValueType.STRING,
            get='train',
            set='train'
        )

        self.add_property(
            descr='Enable/Disable Auto check for Updates',
            name='check_auto',
            type=ValueType.BOOLEAN,
            get='check_auto',
            set='check_auto'
        )

        self.add_property(
            descr='Update Server',
            name='update_server',
            get='update_server',
            set=None,
        )

        self.add_property(
            descr='Update Available',
            name='available',
            type=ValueType.BOOLEAN,
            get=lambda x: True if self.update_info else False,
            set=None
        )

        self.add_property(
            descr='Update Changelog',
            name='changelog',
            type=ValueType.STRING,
            get=lambda x: self.update_info['changelog'] if self.update_info else [''],
            list=True,
            set=None
        )

        self.add_property(
            descr='Updates already Downloaded',
            name='downloaded',
            type=ValueType.BOOLEAN,
            get=lambda x: self.update_info['downloaded'] if self.update_info else False,
            set=None
        )

        self.subcommands = {
            'check_now': CheckNowCommand(self)
        }
        self.extra_commands = {
            'current_train': CurrentTrainCommand(),
            'update_now': UpdateNowCommand(),
            'show_trains': ShowTrainsCommand()
        }

    def load(self):
        if self.saved:
            self.entity = self.context.call_sync('update.get_config')
            self.orig_entity = copy.deepcopy(self.entity)
            self.update_info = self.context.call_sync('update.update_info')
            self.orig_update_info = copy.deepcopy(self.update_info)
        else:
            # This is in case the task failed!
            self.entity = copy.deepcopy(self.orig_entity)
            self.update_info = copy.deepcopy(self.orig_update_info)
        self.modified = False

    def save(self):
        return self.context.submit_task(
            'update.configure',
            self.get_diff(),
            callback=lambda s: post_save(self, s))


def _init(context):
    context.attach_namespace('/', UpdateNamespace('update', context))
