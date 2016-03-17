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

import copy
import gettext
from freenas.cli.namespace import (
    ItemNamespace, EntityNamespace, Command, EntitySubscriberBasedLoadMixin,
    NestedObjectLoadMixin, NestedObjectSaveMixin, TaskBasedSaveMixin, CommandException, description
)
from freenas.cli.output import ValueType, Table


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("List or dismiss system alerts")
class BackupNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    """
    def __init__(self, name, context):
        super(BackupNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'backup'
        self.primary_key_name = 'name'
        self.create_task = 'backup.create'
        self.update_task = 'backup.update'
        self.delete_task = 'backup.delete'

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='Provider',
            name='provider',
            get='provider',
            list=True
        )

        self.add_property(
            descr='Name',
            name='dataset',
            get='dataset',
            list=True
        )

        self.add_property(
            descr='Recursive',
            name='recursive',
            get='recursive',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Compression',
            name='compression',
            get='compression',
            list=True,
            enum=['NONE', 'GZIP']
        )

        def get_entity_namespaces(this):
            PROVIDERS = {
                'ssh': BackupSSHPropertiesNamespace,
                's3': BackupS3PropertiesNamespace
            }

            this.load()
            if this.entity and this.entity.get('provider'):
                return [PROVIDERS[this.entity['provider']]('properties', self.context, this)]

            return []

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = get_entity_namespaces


class BackupBasePropertiesNamespace(ItemNamespace):
    def __init__(self, name, context, parent):
        super(BackupBasePropertiesNamespace, self).__init__(name)
        self.context = context
        self.parent = parent

    def load(self):
        self.entity = self.parent.entity['properties']
        self.orig_entity = copy.deepcopy(self.entity)

    def save(self):
        return self.parent.save()


class BackupSSHPropertiesNamespace(BackupBasePropertiesNamespace):
    def __init__(self, name, context, parent):
        super(BackupSSHPropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Hostname',
            name='hostname',
            get='hostport'
        )

        self.add_property(
            descr='Username',
            name='username',
            get='username'
        )

        self.add_property(
            descr='Password',
            name='password',
            get=None,
            set='password'
        )

        self.add_property(
            descr='Directory',
            name='directory',
            get='directory'
        )


class BackupS3PropertiesNamespace(BackupBasePropertiesNamespace):
    def __init__(self, name, context, parent):
        super(BackupS3PropertiesNamespace, self).__init__(name, context, parent)


def _init(context):
    context.attach_namespace('/', BackupNamespace('backup', context))
