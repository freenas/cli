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


import os
from namespace import Namespace, EntityNamespace, Command, RpcBasedLoadMixin, TaskBasedSaveMixin, description
from output import ValueType, output_msg, output_table, read_value
from fnutils import first_or_default


@description("Boot Environment Namespace")
class BootEnvironmentNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(BootEnvironmentNamespace, self).__init__(name, context)
        self.create_task = 'boot.environments.create'
        self.delete_task = 'boot.environments.delete'
        self.query_call = 'boot.environments.query'
        self.primary_key_name = 'id'

        self.skeleton_entry = {
            'id': None,
            'realname': None
        }

        self.add_property(
            descr='Boot Environment ID',
            name='id',
            get='id',
            set='id',
            list=True
            )
        
        self.add_property(
            descr='Boot Environment Name',
            name='realname',
            get='realname',
            list=True
            )

        self.add_property(
            descr='Active',
            name='active',
            get='active',
            list=True,
            type=ValueType.BOOLEAN
            )

        self.add_property(
            descr='On Reboot',
            name='onreboot',
            get='on_reboot',
            list=True,
            type=ValueType.BOOLEAN
            )

        self.add_property(
            descr='Mount point',
            name='mountpoint',
            get='mountpoint',
            list=True
            )

        self.add_property(
            descr='Space used',
            name='space',
            get='space',
            list=True
            )

        self.add_property(
            descr='Date created',
            name='created',
            get='created',
            list=True
            )

        self.primary_key = self.get_mapping('id')

        self.extra_commands = {
            'activate' : ActivateBootEnvCommand(),
            'rename' : RenameBootEnvCommand(),
        }

    def get_one(self, name):
            return self.context.connection.call_sync(
                    self.query_call,
                    'id',
                    {'single': True})

    def delete(self, name):
        self.context.submit_task('boot.environments.delete', name)

    def save(self, this, new=False):
        if new:
            self.context.submit_task('boot.environments.create', this.entity['id'])
            return


@description("Renames a boot environment")
class RenameBootEnvCommand(Command):
    """
    Usage: rename <newname>

    Example: rename steve
    """
    def run(self, context, args, kwargs, opargs):
        # to be implemented
        return


@description("Activates a boot environment")
class ActivateBootEnvCommand(Command):
    """
    Usage: activate

    Activates the current boot environment
    """
    def run(self, context, args, kwargs, opargs):
        # to be implemented
        return


def _init(context):
    context.attach_namespace('/', BootEnvironmentNamespace('bootenv', context))

