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
        self.primary_key_name = 'name'

        self.skeleton_entity = {
            'name': None,
            'realname': None
        }

        self.add_property(
            descr='Boot Environment ID',
            name='name',
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

        self.primary_key = self.get_mapping('name')

        self.entity_commands = lambda this: {
            'activate': ActivateBootEnvCommand(this),
        }

    def get_one(self, name):
        return self.context.connection.call_sync(
            self.query_call,
            [('id', '=', name)],
            {'single': True})

    def delete(self, name):
        self.context.submit_task('boot.environments.delete', name)

    def save(self, this, new=False):
        if new:
            self.context.submit_task('boot.environments.create',
                                     this.entity['id'])
            return
        else:
            if this.entity['id'] != this.orig_entity['id']:
                self.context.submit_task('boot.environments.rename',
                                         this.orig_entity['id'],
                                         this.entity['id'],
                                         callback=lambda s:
                                         self.post_save(this, s))
            return

    def post_save(self, this, status):
        if status == 'FINISHED':
            this.modified = False
            this.saved = True


@description("Activates a boot environment")
class ActivateBootEnvCommand(Command):
    """
    Usage: activate

    Activates the current boot environment
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('boot.environments.activate',
                            self.parent.entity['id'])


def _init(context):
    context.attach_namespace('/', BootEnvironmentNamespace('bootenv', context))

