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
from freenas.cli.output import Sequence, Object, ValueType, Table, format_value, read_value
from freenas.cli.namespace import (
    ItemNamespace, EntityNamespace, Command, EntitySubscriberBasedLoadMixin,
    TaskBasedSaveMixin, NestedEntityMixin, description
)
from freenas.cli.complete import EnumComplete
from freenas.cli.utils import get_related, set_related


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Backup Snapshots")
class BackupNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The backup namespace provides commands for configuring backups to an SSH
    server or Amazon S3.
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
            usage=_("""\
            Mandatory, alphanumeric name for the backup task."""),
            list=True
        )

        self.add_property(
            descr='Provider',
            name='provider',
            get='provider',
            usage=_("""\
            Mandatory. Supported values are "ssh" or "s3"."""),
            list=True
        )

        self.add_property(
            descr='Name',
            name='dataset',
            get='dataset',
            usage=_("""\
            Mandatory. Name of dataset to backup."""),
            list=True
        )

        self.add_property(
            descr='Recursive',
            name='recursive',
            get='recursive',
            usage=_("""\
            Can be set to true or false, where the default is true.
            Indicates whether or not child datasets are also backed up."""),
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Compression',
            name='compression',
            get='compression',
            usage=_("""\
            Indicates whether or not to compress the backup. Can be set to NONE
            or GZIP."""),
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

            if getattr(self, 'is_docgen_instance', False):
                return [namespace('<entity=={0}>properties'.format(name), self.context, this) for name, namespace in
                    PROVIDERS.items()]

            return []

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = get_entity_namespaces
        self.entity_commands = lambda this: {
            'sync': BackupSyncCommand(this),
            'query': BackupQueryCommand(this),
            'restore': BackupRestoreCommand(this)
        }


class BackupBasePropertiesNamespace(NestedEntityMixin, ItemNamespace):
    def __init__(self, name, context, parent):
        super(BackupBasePropertiesNamespace, self).__init__(name, context)
        self.context = context
        self.parent = parent
        self.parent_entity_path = 'properties'


class BackupSSHPropertiesNamespace(BackupBasePropertiesNamespace):
    def __init__(self, name, context, parent):
        super(BackupSSHPropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Peer',
            name='peer',
            usage=_("Peer name. Must match a peer of type ssh"),
            get=lambda o: get_related(self.context, 'peer', o, 'peer'),
            set=lambda o, v: set_related(self.context, 'peer', o, 'peer', v)
        )

        self.add_property(
            descr='Directory',
            name='directory',
            usage=_("""\
            Name of existing directory to save the backups to."""),
            get='directory'
        )


class BackupS3PropertiesNamespace(BackupBasePropertiesNamespace):
    def __init__(self, name, context, parent):
        super(BackupS3PropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Peer',
            name='peer',
            usage=_("Peer name. Must match a peer of type s3"),
            get=lambda o: get_related(self.context, 'peer', o, 'peer'),
            set=lambda o, v: set_related(self.context, 'peer', o, 'peer', v)
        )

        self.add_property(
            descr='Bucket',
            name='bucket',
            usage=_("""\
            Enclose the valid hostname label between double quotes.
            This assumes you have already created a bucket."""),
            get='bucket'
        )

        self.add_property(
            descr='Folder',
            name='folder',
            usage=_("""\
            The name of the folder within the bucket to backup to."""),
            get='folder'
        )


class BackupSyncCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        incremental = read_value(kwargs.pop('incrementasl', 'yes'), ValueType.BOOLEAN)
        snapshot = read_value(kwargs.pop('snapshot', 'yes'), ValueType.BOOLEAN)
        dry_run = read_value(kwargs.pop('dry_run', 'no'), ValueType.BOOLEAN)

        if dry_run:
            def describe(row):
                if row['type'] == 'SEND_STREAM':
                    return '{localfs}@{snapshot} -> {remotefs}@{snapshot} ({incr})'.format(
                        incr='incremental' if row.get('incremental') else 'full',
                        **row
                    )

                if row['type'] == 'DELETE_SNAPSHOTS':
                    return 'reinitialize remote dataset {remotefs}'.format(**row)

                if row['type'] == 'DELETE_DATASET':
                    return 'delete remote dataset {remotefs} (because it has been deleted locally)'.format(**row)

            result = context.call_task_sync('backup.sync', self.parent.entity['id'], snapshot, True)
            return Sequence(
                Table(
                    result['result'], [
                        Table.Column('Action type', 'type', ValueType.STRING),
                        Table.Column('Description', describe, ValueType.STRING)
                    ]
                ),
                "Estimated backup stream size: {0}".format(format_value(
                    sum(a.get('send_size', 0) for a in result['result']),
                    ValueType.SIZE)
                )
            )
        else:
            context.submit_task('backup.sync', self.parent.entity['id'], snapshot)

    def complete(self, context, **kwargs):
        return [
            EnumComplete('snapshot=', ['yes', 'no']),
            EnumComplete('dry_run=', ['yes', 'no'])
        ]


class BackupQueryCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        result = context.call_task_sync('backup.query', self.parent.entity['id'])
        manifest = result['result']
        return Sequence(
            Object(
                Object.Item('Hostname', 'hostname', manifest['hostname']),
                Object.Item('Dataset', 'dataset', manifest['dataset']),
            ),
            Table(
                manifest['snapshots'], [
                    Table.Column('Snapshot name', 'name', ValueType.STRING),
                    Table.Column('Incremental', 'incremental', ValueType.BOOLEAN),
                    Table.Column('Created at', 'created_at', ValueType.TIME)
                ]
            )
        )


class BackupRestoreCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        dataset = kwargs.pop('dataset', None)
        snapshot = kwargs.pop('snapshot', None)

        context.submit_task('backup.restore', self.parent.entity['id'], dataset, snapshot)


def _init(context):
    context.attach_namespace('/', BackupNamespace('backup', context))
