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
    EntityNamespace, Command, CommandException, EntitySubscriberBasedLoadMixin,
    TaskBasedSaveMixin, BaseVariantMixin, description
)
from freenas.cli.complete import EnumComplete, EntitySubscriberComplete, NullComplete
from freenas.cli.utils import TaskPromise, get_related, set_related
from freenas.utils import query as q


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class BackupSSHPropertiesMixin(BaseVariantMixin):
    def add_properties(self):
        super(BackupSSHPropertiesMixin, self).add_properties()

        self.add_property(
            descr='Peer',
            name='ssh_peer',
            usage=_("Peer name. Must match a peer of type ssh"),
            get=lambda o: get_related(self.context, 'peer', o, 'properties.peer'),
            set=lambda o, v: set_related(self.context, 'peer', o, 'properties.peer', v),
            list=False,
            condition=lambda o: o['provider'] == 'ssh',
            enum=lambda: self.query([], {'subscriber': 'peer', 'select': 'name'}),
        )

        self.add_property(
            descr='Directory',
            name='ssh_directory',
            usage=_("""\
            Name of existing directory to save the backups to."""),
            get='properties.directory',
            list=False,
            condition=lambda o: o['provider'] == 'ssh'
        )


class BackupS3PropertiesMixin(BaseVariantMixin):
    def add_properties(self):
        super(BackupS3PropertiesMixin, self).add_properties()

        self.add_property(
            descr='Peer',
            name='s3_peer',
            usage=_("Peer name. Must match a peer of type s3"),
            get=lambda o: get_related(self.context, 'peer', o, 'properties.peer'),
            set=lambda o, v: set_related(self.context, 'peer', o, 'properties.peer', v),
            list=False,
            condition=lambda o: o['provider'] == 's3'
        )

        self.add_property(
            descr='Bucket',
            name='s3_bucket',
            usage=_("""\
            Enclose the valid hostname label between double quotes.
            This assumes you have already created a bucket."""),
            get='properties.bucket',
            list=False,
            condition=lambda o: o['provider'] == 's3'
        )

        self.add_property(
            descr='Folder',
            name='s3_folder',
            usage=_("""\
            The name of the folder within the bucket to backup to."""),
            get='properties.folder',
            list=False,
            condition=lambda o: o['provider'] == 's3'
        )


@description("Backup Snapshots")
class BackupNamespace(
    TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin,
    BackupSSHPropertiesMixin, BackupS3PropertiesMixin, EntityNamespace
):
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
        self.skeleton_entity = {
            'name': None,
            'provider': None
        }

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
            list=True,
            enum=['ssh', 's3']
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

        self.add_properties()
        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda this: {
            'sync': BackupSyncCommand(this),
            'query': BackupQueryCommand(this),
            'restore': BackupRestoreCommand(this)
        }


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
            if result['state'] != 'FINISHED':
                raise CommandException('Failed to query backup: {0}'.format(q.get(result, 'error.message')))

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
            tid = context.submit_task('backup.sync', self.parent.entity['id'], snapshot)
            return TaskPromise(context, tid)

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
        if result['state'] != 'FINISHED':
            raise CommandException('Failed to query backup: {0}'.format(q.get(result, 'error.message')))

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
        if not kwargs:
            raise CommandException(_("Restore requires more arguments. For help see 'help restore'"))

        dataset = kwargs.pop('dataset', None)
        if not dataset:
            raise CommandException(_("Please specify the target dataset. For help see 'help restore'"))

        snapshot = kwargs.pop('snapshot', None)

        tid = context.submit_task('backup.restore', self.parent.entity['id'], dataset, snapshot)
        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete('dataset=', 'volume.dataset'),
            NullComplete('snapshot=')
        ]


def _init(context):
    context.attach_namespace('/', BackupNamespace('backup', context))
