# coding=utf-8
#
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
import getpass
from pathlib import PurePath, Path
from filewrap import FileProvider
from freenas.cli.namespace import (
    Command, Namespace, EntityNamespace, TaskBasedSaveMixin,
    EntitySubscriberBasedLoadMixin, description, CommandException
)
from freenas.cli.output import ValueType, Table, Sequence, read_value, output_msg
from freenas.cli.complete import EnumComplete, NullComplete


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Sets credentials for remote machine")
class SetRemoteLogpassCommand(Command):
    """
    Sets username and password for remote Freenas machine.

    Usage:
        set_remote_logpass

    Examples:
        set_remote_logpass
            >Provide username
            >Provide password
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        self.parent.remote_logpass['username'] = input(">enter freenas username :")
        self.parent.remote_logpass['password'] = getpass.getpass(">enter freenas password :")


@description("Opens file object")
class OpenCommand(Command):
    """
    Opens object pointed to by provided URI.
    URI can be qualiffied with the following schemes to access local or remote filesystem:
    1. 'file://'
    2. 'remote://'

    Usage:
        open <uri>

    Examples:
        open file:///path/to/local/dir
        open remote://<freenas-address>/path/to/remote/dir
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args:
            raise CommandException(_("Open requires 1 argument. For help see 'help open'"))

        self.parent.curr_obj = FileProvider.open(args[0], remote_logpass=self.parent.remote_logpass)
        output_msg(_(">{0}".format(str(self.parent.curr_obj))))
        contents = [{'name': o.name, 'type': o.type.name} for o in self.parent.curr_obj.readdir()]
        return Table(contents, [
            Table.Column('Name', 'name'),
            Table.Column('Type', 'type'),
        ])


@description("Changes directory")
class ChangeDirCommand(Command):
    """
    Changes current directory.

    Usage:
        chdir <dirname>

    Examples:
        chdir otherdir
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args:
            raise CommandException(_("'chdir' requires 1 argument. For help see 'help chdir'"))

        name = args[0]
        if name == '..':
            dest = self.parent.curr_obj.parent
        elif name == '.':
            dest = self.parent.curr_obj
        else:
            dest = self.parent.curr_obj.get_child(name)
        if not dest.is_dir:
            raise CommandException('Cannot "cd" into object of type: {0}'.format(dest.type.name))
        else:
            self.parent.curr_obj = dest
            output_msg(_(">{0}".format(str(self.parent.curr_obj))))
            contents = [{'name': o.name, 'type': o.type.name} for o in self.parent.curr_obj.readdir()]
            return Table(contents, [
                Table.Column('Name', 'name'),
                Table.Column('Type', 'type'),
            ])


@description("Creates directory")
class MakeDirCommand(Command):
    """
    Creates directory.

    Usage:
        mkdir <dirname>

    Examples:
        mkdir newdir
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args:
            raise CommandException(_("'mkdir' requires 1 argument. For help see 'help mkdir'"))

        self.parent.curr_obj.mkdir(args[0])
        output_msg(_(">{0}".format(str(self.parent.curr_obj))))
        contents = [{'name': o.name, 'type': o.type.name} for o in self.parent.curr_obj.readdir()]
        return Table(contents, [
            Table.Column('Name', 'name'),
            Table.Column('Type', 'type'),
        ])


@description("Deletes directory")
class RemoveDirCommand(Command):
    """
    Deletes directory.

    Usage:
        rmdir name=<dirname>

    Examples:
        rmdir name=olddir
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args:
            raise CommandException(_("'rmdir' requires 1 argument. For help see 'help rmdir'"))

        name = args[0]
        try:
            self.parent.curr_obj.rmdir(name)
        except ValueError as err:
            output_msg(_(err.args))
        finally:
            output_msg(_(">{0}".format(str(self.parent.curr_obj))))
            contents = [{'name': o.name, 'type': o.type.name} for o in self.parent.curr_obj.readdir()]
            return Table(contents, [
                Table.Column('Name', 'name'),
                Table.Column('Type', 'type'),
            ])


@description(_("Provides access to CLI filebrowser"))
class FilebrowserNamespace(Namespace):
    """
    The filebrowser namespace provides commands for accessing local and remote filesystems.
    """
    def __init__(self, name, context):
        super(FilebrowserNamespace, self).__init__(name)
        self.context = context
        self.curr_obj = None
        self.remote_logpass = {'username': '', 'password': ''}

    def commands(self):
        return {
            'open': OpenCommand(self),
            'set_remote_logpass': SetRemoteLogpassCommand(self),
            'chdir': ChangeDirCommand(self),
            'mkdir': MakeDirCommand(self),
            'rmdir': RemoveDirCommand(self),
        }


def _init(context):
    context.attach_namespace('/', FilebrowserNamespace('filebrowser', context))
