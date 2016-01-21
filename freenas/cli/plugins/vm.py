#
# Copyright 2015 iXsystems, Inc.
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
import curses
import pyte
from signal import signal, SIGWINCH
from shutil import get_terminal_size
from threading import RLock
from freenas.dispatcher.shell import VMConsoleClient
from freenas.cli.namespace import (
    EntityNamespace, Command, NestedObjectLoadMixin, NestedObjectSaveMixin, EntitySubscriberBasedLoadMixin,
    RpcBasedLoadMixin, TaskBasedSaveMixin, description
)
from freenas.cli.output import ValueType


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class VMConsole(object):
    class CursesScreen(pyte.DiffScreen):
        def __init__(self, parent, cols, lines):
            super(VMConsole.CursesScreen, self).__init__(cols, lines)
            self.parent = parent

    def __init__(self, context, id, name):
        self.context = context
        self.id = id
        self.name = name
        self.conn = None
        self.stream = pyte.Stream()
        self.screen = None
        self.window = None
        self.output_lock = RLock()
        self.stdscr = None
        self.header = None

    def on_data(self, data):
        with self.output_lock:
            self.stream.feed(data.decode('utf-8'))
            for i in self.screen.dirty:
                self.window.addstr(i, 0, self.screen.display[i])

            self.screen.dirty.clear()
            #print('\033[{0};{1}H'.format(self.screen.cursor.y + 1, self.screen.cursor.x + 1))

    def connect(self):
        token = self.context.call_sync('containerd.management.request_console', self.id)
        self.conn = VMConsoleClient(self.context.hostname, token)
        self.conn.on_data(self.on_data)
        self.conn.open()

    def disconnect(self):
        self.conn.close()

    def start(self):
        self.stdscr = curses.initscr()
        self.stdscr.immedok(True)
        curses.noecho()
        curses.raw()
        self.stdscr.clear()
        rows, cols = self.stdscr.getmaxyx()
        self.header = curses.newwin(1, cols, 0, 0)
        self.screen = VMConsole.CursesScreen(self, cols, rows - 2)
        self.stream.attach(self.screen)
        self.window = curses.newwin(rows - 1, cols, 1, 0)
        self.window.immedok(True)
        self.header.immedok(True)
        self.header.bkgdset(' ', curses.A_REVERSE)
        self.header.addstr(0, 0, "Connected to {0} console - hit ^] to detach".format(self.name))
        signal(SIGWINCH, self.resize)
        self.connect()
        while True:
            ch = self.stdscr.getch()
            if ch == 29:
                curses.endwin()
                self.disconnect()
                break

            self.conn.write(chr(ch))

    def resize(self, signum, frame):
        size = get_terminal_size()
        self.screen.resize(size.lines - 2, size.columns)
        self.header.resize(1, size.columns)
        self.window.resize(size.lines - 1, size.columns)
        self.screen.dirty.clear()
        self.header.clear()
        self.header.bkgdset(' ', curses.A_REVERSE)
        self.header.addstr(0, 0, "Connected to {0} console - hit ^] to detach".format(self.name))


class StartVMCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.call_task_sync('container.start', self.parent.entity['id'])


class StopVMCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.call_task_sync('container.stop', self.parent.entity['id'])


class RebootVMCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        pass


class ConsoleCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        console = VMConsole(context, self.parent.entity['id'], self.parent.entity['name'])
        console.start()


@description("Configure and manage virtual machines")
class VMNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(VMNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'container'
        self.create_task = 'container.create'
        self.update_task = 'container.update'
        self.delete_task = 'container.delete'
        self.required_props = ['name', 'volume']
        self.primary_key_name = 'name'

        self.skeleton_entity = {
            'type': 'VM',
            'devices': [],
            'config': {}
        }

        self.add_property(
            descr='VM Name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='Template name',
            name='template',
            get='template.name'
        )

        self.add_property(
            descr='State',
            name='state',
            get='status.state',
            set=None
        )

        self.add_property(
            descr='Volume',
            name='volume',
            get='target',
            createsetable=True,
            usersetable=False
        )

        self.add_property(
            descr='Description',
            name='description',
            get='description',
            list=False
        )

        self.add_property(
            descr='Memory size (MB)',
            name='memsize',
            get='config.memsize',
            list=True,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='CPU cores',
            name='cores',
            get='config.ncpus',
            list=True,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Boot device',
            name='boot_device',
            get='config.boot_device',
            list=False
        )

        self.add_property(
            descr='Boot partition (for GRUB)',
            name='boot_partition',
            get='config.boot_partition',
            list=False
        )

        self.add_property(
            descr='Bootloader type',
            name='bootloader',
            get='config.bootloader',
            list=False,
            enum=['BHYVELOAD', 'GRUB']
        )

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = lambda this: [
            VMDisksNamespace('disks', self.context, this),
            VMNicsNamespace('nic', self.context, this)
        ]

        self.entity_commands = lambda this: {
            'start': StartVMCommand(this),
            'stop': StopVMCommand(this),
            'reboot': RebootVMCommand(this),
            'console': ConsoleCommand(this)
        }

    def namespaces(self):
        yield TemplateNamespace('template', self.context)
        for namespace in super(VMNamespace, self).namespaces():
            yield namespace


class VMDisksNamespace(NestedObjectLoadMixin, NestedObjectSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(VMDisksNamespace, self).__init__(name, context)
        self.parent = parent
        self.primary_key_name = 'name'
        self.extra_query_params = [('type', 'in', ['DISK', 'CDROM'])]
        self.parent_path = 'devices'
        self.skeleton_entity = {
            'type': 'DISK',
            'properties': {}
        }

        self.add_property(
            descr='Disk name',
            name='name',
            get='name'
        )

        self.add_property(
            descr='Disk type',
            name='type',
            get='type',
            enum=['DISK', 'CDROM']
        )

        self.add_property(
            descr='Disk size',
            name='size',
            get='properties.size',
            type=ValueType.STRING,
            condition=lambda e: e['type'] == 'DISK'
        )

        self.add_property(
            descr='Image path',
            name='path',
            get='properties.path',
            condition=lambda e: e['type'] == 'CDROM'
        )

        self.primary_key = self.get_mapping('name')


class VMNicsNamespace(NestedObjectLoadMixin, NestedObjectSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(VMNicsNamespace, self).__init__(name, context)
        self.parent = parent
        self.primary_key_name = 'name'
        self.extra_query_params = [('type', '=', 'NIC')]
        self.parent_path = 'devices'
        self.skeleton_entity = {
            'type': 'NIC',
            'properties': {}
        }

        self.add_property(
            descr='NIC name',
            name='name',
            get='name'
        )

        self.add_property(
            descr='NIC type',
            name='type',
            get='properties.type'
        )

        self.add_property(
            descr='Bridge with',
            name='bridge',
            get='properties.bridge'
        )

        self.add_property(
            descr='MAC address',
            name='macaddr',
            get='properties.macaddr',
            type=ValueType.SIZE
        )

        self.primary_key = self.get_mapping('name')


@description("VM templates operations")
class TemplateNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(TemplateNamespace, self).__init__(name, context)
        self.query_call = 'vm_template.query'
        self.primary_key_name = 'template.name'
        self.allow_create = False

        self.skeleton_entity = {
            'type': 'VM',
            'devices': [],
            'config': {}
        }

        self.add_property(
            descr='Name',
            name='name',
            get='template.name',
            list=True
        )

        self.add_property(
            descr='Description',
            name='description',
            get='template.description',
            list=True
        )

        self.add_property(
            descr='Author',
            name='author',
            get='template.author',
            list=False
        )

        self.add_property(
            descr='Memory size (MB)',
            name='memsize',
            get='config.memsize',
            list=False,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='CPU cores',
            name='cores',
            get='config.ncpus',
            list=False,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Boot device',
            name='boot_device',
            get='config.boot_device',
            list=False
        )

        self.add_property(
            descr='Bootloader type',
            name='bootloader',
            get='config.bootloader',
            list=False,
            enum=['BHYVELOAD', 'GRUB']
        )

        self.primary_key = self.get_mapping('name')

        self.extra_commands = {
            'fetch': FetchCommand()
        }


@description("Downloads templates from git")
class FetchCommand(Command):
    """
    Usage: fetch

    Example: fetch

    Refreshes local cache of VM templates.
    """

    def run(self, context, args, kwargs, opargs):
        context.submit_task('vm_template.fetch')


def _init(context):
    context.attach_namespace('/', VMNamespace('vm', context))
