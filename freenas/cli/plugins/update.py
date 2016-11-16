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
import inspect
from datetime import datetime
from freenas.cli.complete import EnumComplete
from freenas.cli.namespace import ConfigNamespace, Command, description, CommandException
from freenas.cli.output import output_msg, ValueType, Table, read_value
from freenas.cli.utils import TaskPromise


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

    Examples:
        current_train

    Displays the current update train that this system is on.
    """

    def run(self, context, args, kwargs, opargs):
        return context.call_sync('update.get_current_train')


@description("Lists the Available Update Trains")
class ShowTrainsCommand(Command):
    """
    Usage: show_trains

    Examples:
        show_trains

    Displays the set of available trains from the update server.
    """

    def run(self, context, args, kwargs, opargs):
        trains = context.call_sync('update.trains')
        if trains is None:
            return _(
                "Could not fetch Available Trains from the Update Server. "
                "Please Check internet connectivity and try again."
            )
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
    Usage: check_now

    Examples:
        check_now

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
            return _("No new updates available.")


@description("Downloads New Updates and saves them for apllying later")
class DownloadNowCommand(Command):
    """
    Usage: download

    Examples:
        download

    Downloads and Saves the latest update available.
    """

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task('update.download')
        return TaskPromise(context, tid)


@description("Updates the system and reboots it (can be specified)")
class UpdateNowCommand(Command):
    """
    Usage: update_now reboot=<reboot>

    Examples:
        update_now (This will not reboot the system post update)
        update_now reboot=yes (This will reboot the system post update)

    Installs updates if they are available and reboots the system if
    told to do so via the `reboot` flag.
    """

    def __init__(self):
        super(UpdateNowCommand, self).__init__()
        self.task_id = None
        self.reboot = False
        self.context = None

    def task_callback(self, task_state, task_data):
        if task_state == 'FINISHED' and task_data["result"]:
            if self.reboot:
                output_msg(_(
                    "Updates Downloaded and Installed Successfully."
                    " System going for a reboot now."
                ))
            else:
                output_msg(_(
                    "System successfully updated."
                    " Please reboot now using the '/ system reboot' command"
                ))

    def run(self, context, args, kwargs, opargs):
        if args or len(kwargs) > 1 or ('reboot' not in kwargs and len(kwargs) == 1):
            raise CommandException(_(
                "Incorrect syntax {0} {1}\n{2}".format(args, kwargs, inspect.getdoc(self))
            ))
        self.context = context
        self.reboot = read_value(kwargs.get('reboot', self.reboot), tv=ValueType.BOOLEAN)
        self.task_id = context.submit_task(
            'update.updatenow',
            self.reboot,
            callback=self.task_callback
        )

        return TaskPromise(context, self.task_id)

    def complete(self, context, **kwargs):
        return [
            EnumComplete('reboot=', ['yes', 'no'])
        ]


@description("Configure system updates")
class UpdateNamespace(ConfigNamespace):
    """
    The update namespace provides commands for updating and configuring system updates.
    """

    def __init__(self, name, context):
        super(UpdateNamespace, self).__init__(name, context)
        self.context = context
        self.update_info = None
        self.update_task = 'update.update'

        self.add_property(
            descr='Set Update Train',
            name='train',
            type=ValueType.STRING,
            get='train',
            set='train',
            usage=_("The Update Train to be used for checking/downloading updates")
        )

        self.add_property(
            descr='Enable/Disable Auto check for Updates',
            name='check_auto',
            type=ValueType.BOOLEAN,
            get='check_auto',
            set='check_auto',
            usage=_("Flag that controls automatic periodic check for downloading new updates")
        )

        self.add_property(
            descr='Update Server',
            name='update_server',
            get='update_server',
            set=None,
            usage=_("The Update Server configured to be used by the system")
        )

        self.add_property(
            descr='Update Available',
            name='available',
            type=ValueType.BOOLEAN,
            get=lambda x: self.update_info['available'],
            set=None,
            usage=_("Flag stating whether an update is available for download/install")
        )

        self.add_property(
            descr='Update Changelog',
            name='changelog',
            type=ValueType.STRING,
            get=lambda x: self.update_info['changelog'],
            list=True,
            set=None,
            usage=_("Contains the changelog describing the the fixes/features added in this update w.r.t to your current system version")
        )

        self.add_property(
            descr='Updates already Downloaded',
            name='downloaded',
            type=ValueType.BOOLEAN,
            get=lambda x: self.update_info['downloaded'],
            set=None,
            usage=_("Flag stating whether the update available was already downloaded")
        )

        self.add_property(
            descr='Version of the Update',
            name='version',
            type=ValueType.STRING,
            get=lambda x: self.update_info['version'],
            set=None,
            usage=_("The version of the update that is either available, downloaded, or already installed")
        )

        self.add_property(
            descr='An Update is installed and activated for next boot',
            name='installed',
            type=ValueType.BOOLEAN,
            get=lambda x: self.update_info['installed'],
            set=None,
            usage=_("Flag stating whether the update available was already installed")
        )

        self.add_property(
            descr='Version of the Installed Update (if any)',
            name='installed_version',
            type=ValueType.STRING,
            get=lambda x: self.update_info['installed_version'],
            set=None,
            usage=_("Version of the Installed Update (if any)")
        )

        self.subcommands = {
            'check_now': CheckNowCommand(self)
        }
        self.extra_commands = {
            'current_train': CurrentTrainCommand(),
            'download': DownloadNowCommand(),
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


def _init(context):
    context.attach_namespace('/', UpdateNamespace('update', context))
