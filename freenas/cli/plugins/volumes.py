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
import copy
import gettext
import six
from freenas.cli.namespace import (
    EntityNamespace, Command, CommandException, SingleItemNamespace,
    EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, description
)
from freenas.cli.complete import NullComplete, EnumComplete, EntitySubscriberComplete
from freenas.cli.output import Table, ValueType, output_tree, format_value, read_value, Sequence
from freenas.cli.utils import post_save, iterate_vdevs, to_list, correct_disk_path
from freenas.utils import first_or_default, extend, query


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


# Global lists/dicts for create command and other stuff
VDEV_TYPES = ['disk', 'mirror', 'raidz1', 'raidz2', 'raidz3', 'auto']
DISKS_PER_TYPE = {
    'auto': 1,
    'disk': 1,
    'mirror': 2,
    'raidz1': 3,
    'raidz2': 4,
    'raidz3': 5
}

VOLUME_LAYOUTS = {
    'auto': 'disk',
    'stripe': 'disk',
    'mirror': 'mirror',
    'raidz': 'raidz1',
    'raidz1': 'raidz1',
    'raidz2': 'raidz2',
    'raidz3': 'raidz3',
    'virtualization': 'mirror',
    'speed': 'mirror',
    'backup': 'raidz2',
    'safety': 'raidz2',
    'storage': 'raidz1',
}


@description("Adds new vdev to volume")
class AddVdevCommand(Command):
    """
    Usage: add_vdev type=<type> disks=<disk1>,<disk2>,<disk3> ...

    Example:
            add_vdev type=mirror disks=ada3,ada4

    Valid types are: mirror disk raidz1 raidz2 raidz3 cache log

    Adds a new vdev to volume
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        entity = self.parent.entity
        if 'type' not in kwargs:
            raise CommandException(_(
                "Please specify a type of vdev, see 'help add_vdev' for more information"
            ))

        disks_per_type = DISKS_PER_TYPE.copy()
        disks_per_type.pop('auto', None)
        disks_per_type.update({
            'log': 1,
            'cache': 1,
        })

        typ = kwargs.pop('type')

        if disks_per_type.get(typ) is None:
            raise CommandException(_("Invalid vdev type"))

        if 'disks' not in kwargs:
            raise CommandException(_("Please specify one or more disks using the disks property"))
        else:
            disks = check_disks(context, to_list(kwargs.pop('disks')))[0]

        if len(disks) < disks_per_type[typ]:
            raise CommandException(_(
                "Vdev of type {0} requires at least {1} disks".format(typ, disks_per_type[typ])
            ))

        if typ == 'mirror':
            entity['topology']['data'].append({
                'type': 'mirror',
                'children': [{'type': 'disk', 'path': correct_disk_path(x)} for x in disks]
            })

        if typ == 'disk':
            if len(disks) != 1:
                raise CommandException(_("Disk vdev consist of single disk"))

            entity['topology']['data'].append({
                'type': 'disk',
                'path': correct_disk_path(disks[0])
            })

        if typ == 'cache':
            if 'cache' not in entity:
                entity['topology']['cache'] = []

            entity['topology']['cache'].append({
                'type': 'disk',
                'path': correct_disk_path(disks[0])
            })

        if typ == 'log':
            if len(disks) != 1:
                raise CommandException(_("Log vdevs cannot be mirrored"))

            if 'log' not in entity:
                entity['topology']['log'] = []

            entity['topology']['log'].append({
                'type': 'disk',
                'path': correct_disk_path(disks[0])
            })

        if typ.startswith('raidz'):
            entity['topology']['data'].append({
                'type': typ,
                'children': [{'type': 'disk', 'path': correct_disk_path(x)} for x in disks]
            })

        self.parent.modified = True
        self.parent.save()


@description("Adds new disk to existing mirror or converts single disk stripe to a mirror")
class ExtendVdevCommand(Command):
    """
    Usage:
        extend_vdev vdev=<disk> <newdisk1> <newdisk2>

    Example:
        extend_vdev vdev=ada1 ada2

    Adds new disk to existing mirror or converts single disk stripe to a mirror
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if 'vdev' not in kwargs:
            raise CommandException(_("Please specify a vdev to mirror to."))
        vdev_ident = correct_disk_path(kwargs.pop('vdev'))
        if len(args) < 1:
            raise CommandException(_("Please specify a disk to add to the vdev."))
        elif len(args) > 1:
            raise CommandException(_("Invalid input: {0}".format(args)))

        disk = correct_disk_path(args[0])
        if disk not in context.call_sync('volume.get_available_disks'):
            raise CommandException(_("Disk {0} is not available".format(disk)))

        vdev = first_or_default(lambda v:
                                v['path'] == vdev_ident or
                                vdev_ident in [i['path'] for i in v['children']],
                                self.parent.entity['topology']['data']
                                )

        if vdev['type'] == 'disk':
            vdev['type'] = 'mirror'
            vdev['children'].append({
                'type': 'disk',
                'path': vdev_ident
                })

        vdev['children'].append({
            'type': 'disk',
            'path': disk
        })

        self.parent.modified = True
        self.parent.save()


@description("Removes vdev from volume")
class DeleteVdevCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if self.parent.saved:
            raise CommandException('Cannot delete vdev from existing volume')


@description("Offlines a disk in a volume")
class OfflineVdevCommand(Command):
    """
    Usage: offline <disk>

    Example: offline ada1

    Offlines a disk in a volume"
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) == 0:
            raise CommandException(_("Please specify a disk"))
        disk = args[0]
        volume = self.parent.entity

        disk = correct_disk_path(disk)

        vdevs = list(iterate_vdevs(volume['topology']))
        guid = None
        for vdev in vdevs:
            if vdev['path'] == disk:
                guid = vdev['guid']
                break

        if guid is None:
            raise CommandException(_("Disk {0} is not part of the volume.".format(disk)))
        context.submit_task(
            'volume.vdev.offline',
            self.parent.entity['id'],
            guid,
            callback=lambda s, t: post_save(self.parent, s, t)
        )


@description("Onlines a disk in a volume")
class OnlineVdevCommand(Command):
    """
    Usage: online <disk>

    Example: online ada1

    Onlines a disk in a volume"
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) == 0:
            raise CommandException(_("Please specify a disk"))
        disk = args[0]
        volume = self.parent.entity

        disk = correct_disk_path(disk)

        vdevs = list(iterate_vdevs(volume['topology']))
        guid = None
        for vdev in vdevs:
            if vdev['path'] == disk:
                guid = vdev['guid']
                break

        if guid is None:
            raise CommandException(_("Disk {0} is not part of the volume.".format(disk)))
        context.submit_task(
            'volume.vdev.online',
            self.parent.entity['id'],
            guid,
            callback=lambda s, t: post_save(self.parent, s, t)
        )


@description("Finds volumes available to import")
class FindVolumesCommand(Command):
    """
    Usage: find

    Finds volumes that can be imported.
    """
    def run(self, context, args, kwargs, opargs):
        vols = context.call_sync('volume.find')
        return Table(vols, [
            Table.Column('ID', 'id', vt=ValueType.STRING),
            Table.Column('Volume name', 'name'),
            Table.Column('Status', 'status')
        ])


@description("Finds connected media that can be used to import data from")
class FindMediaCommand(Command):
    """
    Usage: find_media
    """
    def run(self, context, args, kwargs, opargs):
        media = context.call_sync('volume.find_media')
        return Table(media, [
            Table.Column('Path', 'path'),
            Table.Column('Label', 'label'),
            Table.Column('Size', 'size'),
            Table.Column('Filesystem type', 'fstype')
        ])


@description("Imports given volume")
class ImportVolumeCommand(Command):
    """
    Usage: import <name|id> [newname=<new-name>] key=<key> password=<password> disks=<disks>

    Example: import mypool
             import mypool key="dasfer34tadsf23d/adf" password=abcd disks=da1,da2

    Imports a detached volume.
    When importing encrypted volume key and disks or key, password and disks must be provided.
    """
    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException('Not enough arguments passed')

        id = args[0]
        oldname = args[0]

        if 'key' in kwargs:
            if 'disks' not in kwargs:
                raise CommandException('You have to provide list of disks when importing an encrypted volume')

            disks = kwargs['disks']
            if isinstance(disks, str):
                disks = [disks]

            correct_disks = []
            for dname in disks:
                correct_disks.append(correct_disk_path(dname))

            encryption = {'key': kwargs['key'],
                          'disks': correct_disks}
            password = kwargs.get('password', None)
        else:
            encryption = {}
            password = None

            if not args[0].isdigit():
                vols = context.call_sync('volume.find')
                vol = first_or_default(lambda v: v['name'] == args[0], vols)
                if not vol:
                    raise CommandException('Importable volume {0} not found'.format(args[0]))

                id = vol['id']
                oldname = vol['name']

        context.submit_task('volume.import', id, kwargs.get('newname', oldname), {}, encryption, password)


@description("Imports items from a given volume")
class ImportFromVolumeCommand(Command):
    """
    Usage: import <all\containers\shares\system>

    Imports a detached volume.
    When importing encrypted volume key and disks or key, password and disks must be provided.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException('Not enough arguments passed')

        scope = args[0]

        if scope not in ['all', 'containers', 'shares', 'system']:
            raise CommandException('Import scope must be one of all\containers\shares\system')

        context.submit_task('volume.autoimport', self.parent.entity['id'], scope)


@description("Detaches given volume")
class DetachVolumeCommand(Command):
    """
    Usage: detach

    Example: detach mypool

    Detaches a volume.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        result = context.call_task_sync('volume.export', self.parent.name)
        if result.get('result', None) is not None:
            return Sequence("Detached volume {0} was encrypted!".format(args[0]),
                            "You must save user key listed below to be able to import volume in the future",
                            str(result['result']))


@description("Unlocks encrypted volume")
class UnlockVolumeCommand(Command):
    """
    Usage: unlock

    Example: unlock

    Unlocks an encrypted volume.
    If your volume is password protected you have to provide it's password
    first by typing:

    password <password>
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if self.parent.entity.get('providers_presence', 'ALL') == 'ALL':
            raise CommandException('Volume is already fully unlocked')
        password = self.parent.password
        name = self.parent.entity['id']
        context.submit_task('volume.unlock', name, password, callback=lambda s, t: post_save(self.parent, s, t))


@description("Locks encrypted volume")
class LockVolumeCommand(Command):
    """
    Usage: lock

    Example: lock

    Locks an encrypted volume.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if self.parent.entity.get('providers_presence', 'NONE') == 'NONE':
            raise CommandException('Volume is already fully locked')
        name = self.parent.entity['id']
        context.submit_task('volume.lock', name, callback=lambda s, t: post_save(self.parent, s, t))


@description("Generates new user key for encrypted volume")
class RekeyVolumeCommand(Command):
    """
    Usage: rekey password=<password>

    Example: rekey
             rekey password=new_password

    Generates a new user key for an encrypted volume.
    Your volume must be unlocked to perform this operation.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if self.parent.entity.get('providers_presence', 'NONE') != 'ALL':
            raise CommandException('You must unlock your volume first')
        password = kwargs.get('password', None)
        name = self.parent.entity['id']
        context.submit_task('volume.rekey', name, password)


@description("Creates an encrypted file containing copy of metadatas of all disks related to an encrypted volume")
class BackupVolumeMasterKeyCommand(Command):
    """
    Usage: backup_key path=<path_to_output_file>

    Example: backup_key path="/mnt/mypool/some/directory"

    Creates an encrypted file containing copy of metadata of all disks related
    to an encrypted volume.
    Your volume must be unlocked to perform this operation.

    Command is writing to file selected by user and then returns automatically
    generated password protecting this file.
    Remember, or write down your backup password to a secure location.

    WARNING! The metadata can be used to decrypt the data on your pool,
             even if you change the password or rekey. The metadata backup
             should be stored on secure media, with limited or controlled
             access. iXsystems takes no responsibility for loss of data
             should you lose your master key, nor for unauthorized access
             should some 3rd party obtain access to it.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if self.parent.entity.get('providers_presence', 'NONE') != 'ALL':
            raise CommandException('You must unlock your volume first')

        path = kwargs.get('path', None)
        if path is None:
            raise CommandException('You must provide an output path for a backup file')

        name = self.parent.entity['id']
        result = context.call_task_sync('volume.keys.backup', name, path)
        return Sequence("Backup password:",
                        str(result['result']))


@description("Restores metadata of all disks related to an encrypted volume from a backup file")
class RestoreVolumeMasterKeyCommand(Command):
    """
    Usage: restore_key path=<path_to_input_file> password=<password>

    Example: restore_key path="/mnt/mypool/some/directory" password=abcd-asda-fdsd-cxbvs

    Restores metadata of all disks related to an encrypted volume
    from a backup file.

    Your volume must locked to perform this operation.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if self.parent.entity.get('providers_presence', 'ALL') != 'NONE':
            raise CommandException('You must lock your volume first')

        path = kwargs.get('path', None)
        if path is None:
            raise CommandException('You must provide an input path containing a backup file')

        password = kwargs.get('password', None)
        if password is None:
            raise CommandException('You must provide a password protecting a backup file')

        name = self.parent.entity['id']
        context.submit_task('volume.keys.restore', name, password, path)


@description("Shows volume topology")
class ShowTopologyCommand(Command):
    """
    Usage: show_topology

    Shows the volume topology.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        def print_vdev(vdev):
            if vdev['type'] == 'disk':
                return '{0} (disk)'.format(vdev['path'])
            else:
                return vdev['type']

        volume = self.parent.entity
        tree = [x for x in [{'type': k_v[0], 'children': k_v[1]} for k_v in list(volume['topology'].items())] if len(x['children']) > 0]
        output_tree(tree, 'children', print_vdev)


@description("Shows volume disks status")
class ShowDisksCommand(Command):
    """
    Usage: show_disks

    Shows disk status for the volume.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        volume = self.parent.entity
        result = list(iterate_vdevs(volume['topology']))
        return Table(result, [
            Table.Column('Name', 'path'),
            Table.Column('Status', 'status')
        ])


@description("Scrubs volume")
class ScrubCommand(Command):
    """
    Usage: scrub <name>

    Example: scrub mypool

    Scrubs the volume
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('volume.scrub', self.parent.entity['id'])


@description("Replicates dataset to another system")
class ReplicateCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        remote = kwargs.pop('remote')
        remote_dataset = kwargs.pop('remote_dataset')
        bandwidth = kwargs.pop('bandwidth_limit', None)
        dry_run = kwargs.pop('dry_run', False)
        recursive = kwargs.pop('recursive', False)
        follow_delete = kwargs.pop('follow_delete', False)

        args = (
            'replication.replicate_dataset',
            self.parent.parent.parent.entity['id'],
            self.parent.entity['name'],
            {
                'remote': remote,
                'remote_dataset': remote_dataset,
                'bandwidth_limit': bandwidth,
                'recursive': recursive,
                'followdelete': follow_delete
            },
            dry_run
        )

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

            result = context.call_task_sync(*args)
            return Sequence(
                Table(
                    result['result'], [
                        Table.Column('Action type', 'type', ValueType.STRING),
                        Table.Column('Description', describe, ValueType.STRING)
                    ]
                ),
                "Estimated replication stream size: {0}".format(format_value(
                    sum(a.get('send_size', 0) for a in result['result']),
                    ValueType.SIZE)
                )
            )

        else:
            context.submit_task(*args)


@description("Datasets")
class DatasetsNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(DatasetsNamespace, self).__init__(name, context)
        self.parent = parent
        self.path = name
        self.entity_subscriber_name = 'volume.dataset'
        self.required_props = ['name']

        if self.parent.entity:
            self.extra_query_params = [('volume', '=', self.parent.entity['id'])]

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <volume>/<dataset>
                   create <volume>/<dataset>/<dataset>

            Examples: create mypool/mydataset
                      create mypool/mydataset/somedataset

            Creates a dataset.""")

        self.localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete <volume>/<dataset>

            Example: delete mypool/mydataset
                     delete mypool/mydataset/somedataset

            Deletes a dataset.""")

        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists datasets, optionally doing filtering and sorting.

            Examples:
                show
                show | search name ~= mypool
                show | search compression == lz4 | sort name""")

        self.skeleton_entity = {
            'type': 'FILESYSTEM',
            'properties': {}
        }

        self.add_property(
            descr='Name',
            name='name',
            get='id',
            list=True
        )

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            list=True
        )

        self.add_property(
            descr='Permissions type',
            name='permissions_type',
            get='permissions_type',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM'
        )

        self.add_property(
            descr='Owner',
            name='owner',
            get='permissions.user',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM'
        )

        self.add_property(
            descr='Group',
            name='group',
            get='permissions.group',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM'
        )

        self.add_property(
            descr='Compression',
            name='compression',
            get='properties.compression.value',
            set='properties.compression.value',
            list=True
        )

        self.add_property(
            descr='Used',
            name='used',
            get='properties.used.value',
            set=None,
            list=True
        )

        self.add_property(
            descr='Available',
            name='available',
            get='properties.available.value',
            set=None,
            list=True
        )

        self.add_property(
            descr='Access time',
            name='atime',
            get='properties.atime.value',
            set='properties.atime.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM'
        )

        self.add_property(
            descr='Deduplication',
            name='dedup',
            get='properties.dedup.value',
            set='properties.dedup.value',
            list=False
        )

        self.add_property(
            descr='Quota',
            name='refquota',
            get='properties.refquota.value',
            set='properties.refquota.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM'
        )

        self.add_property(
            descr='Recursive quota',
            name='quota',
            get='properties.quota.value',
            set='properties.quota.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM'
        )

        self.add_property(
            descr='Space reservation',
            name='refreservation',
            get='properties.refreservation.value',
            set='properties.refreservation.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM'
        )

        self.add_property(
            descr='Recursive space reservation',
            name='reservation',
            get='properties.reservation.value',
            set='properties.reservation.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM'
        )

        self.add_property(
            descr='Volume size',
            name='volsize',
            get='volsize',
            set='volsize',
            list=False,
            type=ValueType.SIZE,
            condition=lambda o: o['type'] == 'VOLUME'
        )

        self.add_property(
            descr='Block size',
            name='blocksize',
            get='properties.volblocksize.value',
            set='properties.volblocksize.value',
            list=False,
            condition=lambda o: o['type'] == 'VOLUME'
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda this: {
            'replicate': ReplicateCommand(this)
        }

    def delete(self, this, kwargs):
        self.context.submit_task(
            'volume.dataset.delete',
            this.entity['id']
        )

    def save(self, this, new=False):
        if new:
            newname = this.entity['id']
            if len(newname.split('/')) < 2:
                raise CommandException(_("Please include a volume in the dataset's path"))

            self.context.submit_task(
                'volume.dataset.create',
                extend(this.entity, {'volume': self.parent.entity['id']}),
                callback=lambda s, t: post_save(this, s, t)
            )
            return

        self.context.submit_task(
            'volume.dataset.update',
            this.orig_entity['id'],
            this.get_diff(),
            callback=lambda s, t: post_save(this, s, t)
        )


@description("Snapshots")
class SnapshotsNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(SnapshotsNamespace, self).__init__(name, context)
        self.parent = parent
        self.entity_subscriber_name = 'volume.snapshot'
        self.create_task = 'volume.snapshot.create'
        self.update_task = 'volume.snapshot.update'
        self.delete_task = 'volume.snapshot.delete'
        self.primary_key_name = 'id'
        self.required_props = ['name', 'dataset']
        self.extra_query_params = [
            ('volume', '=', self.parent.name)
        ]

        self.skeleton_entity = {
            'volume': self.parent.name,
            'recursive': False
        }

        self.add_property(
            descr='Snapshot id',
            name='id',
            get='id',
            set='id',
            list=True)

        self.add_property(
            descr='Snapshot name',
            name='name',
            get='name',
            set='name',
            list=True)

        self.add_property(
            descr='Dataset name',
            name='dataset',
            get='dataset',
            list=True)

        self.add_property(
            descr='Recursive',
            name='recursive',
            get=None,
            set='recursive',
            list=False,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Replicable',
            name='replicable',
            get='replicable',
            list=False
        )

        self.add_property(
            descr='Lifetime',
            name='lifetime',
            get='lifetime',
            list=False,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Compression',
            name='compression',
            get='properties.compression.value',
            set='properties.compression.value',
            list=True)

        self.add_property(
            descr='Used',
            name='used',
            get='properties.used.value',
            set=None,
            list=True)

        self.add_property(
            descr='Available',
            name='available',
            get='properties.available.value',
            set=None,
            list=True)

        self.primary_key = self.get_mapping('id')


@description("Filesystem contents")
class FilesystemNamespace(EntityNamespace):
    def __init__(self, name, context, parent):
        super(FilesystemNamespace, self).__init__(name, context)
        self.parent = parent

        self.add_property(
            descr='Name',
            name='name',
            get='name'
        )


def check_disks(context, disks, cache_disks=None, log_disks=None):
    all_disks = [disk["path"] for disk in context.call_sync("disk.query")]
    available_disks = context.call_sync('volume.get_available_disks')
    if cache_disks is not None:
        for disk in cache_disks:
            disk = correct_disk_path(disk)
            if disk not in all_disks:
                raise CommandException(_("Disk {0} does not exist.".format(disk)))
            if disk in available_disks:
                available_disks.remove(disk)
            else:
                raise CommandException(_("Disk {0} is not available.".format(disk)))
    if log_disks is not None:
        for disk in log_disks:
            disk = correct_disk_path(disk)
            if disk not in all_disks:
                raise CommandException(_("Disk {0} does not exist.".format(disk)))
            if disk in available_disks:
                available_disks.remove(disk)
            else:
                raise CommandException(_("Disk {0} is not available.".format(disk)))
    if 'auto' in disks:
        return available_disks, cache_disks, log_disks
    else:
        for disk in disks:
            disk = correct_disk_path(disk)
            if disk not in all_disks:
                raise CommandException(_("Disk {0} does not exist.".format(disk)))
            if disk not in available_disks:
                raise CommandException(_("Disk {0} is not available.".format(disk)))
    return disks, cache_disks, log_disks


@description("Creates new volume")
class CreateVolumeCommand(Command):
    """
    Usage: create <name> disks=<disks> layout=<layout> encryption=<encryption>
            password=<password> cache=<disks> log=<disks>

    Example: create mypool disks=ada1,ada2
             create mypool disks=ada1,ada2 encryption=yes
             create mypool disks=ada1,ada2 encryption=yes password=1234
             create mypool disks=auto layout=virtualization
             create mypool disks=ada1,ada2 cache=ada3 log=ada4
             create mypool disks=auto cache=ada3 log=ada4

    Creating a volume requires some number of disks and an optional layout
    preset. The 'layout' preset allows the following values: stripe, mirror,
    raidz1, raidz2, raidz3, speed, storage, backup, safety, and virtualization.
    If you do not specify a layout then one will be chosen for you (typically a
    stripe of mirrors).  If you wish to use all unused disks for your pool then
    you may specify 'auto' for disks, otherwise you should specify the disks to
    be used individually.

    For more advanced pool topologies, create a volume with a single vdev
    using the 'type' option with one of the following options: disk, mirror, raidz1,
    raidz2 or raidz3.  You may then use the 'volume add_vdev' command to build on 
    this topology.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("create requires more arguments, see 'help create' for more information"))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for create, see 'help create' for more information"))

        # This magic below make either `create foo` or `create name=foo` work
        if len(args) == 1:
            kwargs[self.parent.primary_key.name] = args.pop(0)

        if 'name' not in kwargs:
            raise CommandException(_('Please specify a name for your pool'))
        else:
            name = kwargs.pop('name')

        volume_type = kwargs.pop('type', 'auto')
        if volume_type not in VDEV_TYPES:
            raise CommandException(_(
                "Invalid volume type {0}.  Should be one of: {1}".format(volume_type, VDEV_TYPES)
            ))

        if 'disks' not in kwargs:
            raise CommandException(_("Please specify one or more disks using the disks property"))
        else:
            disks = kwargs.pop('disks')
            if isinstance(disks, six.string_types):
                disks = [disks]

        if read_value(kwargs.pop('encryption', False), ValueType.BOOLEAN) is True:
            encryption = {'encryption': True}
            password = kwargs.get('password', None)
        else:
            encryption = {'encryption': False}
            password = None

        cache_disks = kwargs.pop('cache', [])
        log_disks = kwargs.pop('log', [])
        if cache_disks is None:
            cache_disks = []
        if log_disks is None:
            log_disks = []
        if isinstance(cache_disks, six.string_types):
            cache_disks = [cache_disks]
        if isinstance(log_disks, six.string_types):
            log_disks = [log_disks]

        ns = SingleItemNamespace(None, self.parent)
        ns.orig_entity = query.wrap(copy.deepcopy(self.parent.skeleton_entity))
        ns.entity = query.wrap(copy.deepcopy(self.parent.skeleton_entity))

        disks, cache_disks, log_disks = check_disks(context, disks, cache_disks, log_disks)

        if len(disks) < DISKS_PER_TYPE[volume_type]:
            raise CommandException(_("Volume type {0} requires at least {1} disks".format(volume_type,
                                                                                          DISKS_PER_TYPE[volume_type])))
        if len(disks) > 1 and volume_type == 'disk':
            raise CommandException(_("Cannot create a volume of type disk with multiple disks"))

        if volume_type == 'auto':
            layout = kwargs.pop('layout', 'auto')
            if layout not in VOLUME_LAYOUTS:
                raise CommandException(_(
                    "Invalid layout {0}.  Should be one of: {1}".format(layout, list(VOLUME_LAYOUTS.keys()))
                ))
            else:
                if len(disks) < DISKS_PER_TYPE[VOLUME_LAYOUTS[layout]]:
                    raise CommandException(_("Volume layout {0} requires at least {1} disks".format(layout, DISKS_PER_TYPE[VOLUME_LAYOUTS[layout]])))

            context.submit_task('volume.create_auto', name, 'zfs', layout, disks, cache_disks, log_disks, encryption['encryption'], password)
        else:
            ns.entity['id'] = name
            ns.entity['topology'] = {}
            ns.entity['topology']['data'] = []
            if volume_type == 'disk':
                ns.entity['topology']['data'].append(
                    {'type': 'disk', 'path': correct_disk_path(disks[0])})
            else:
                ns.entity['topology']['data'].append({
                    'type': volume_type,
                    'children': [{'type': 'disk', 'path': correct_disk_path(disk)} for disk in disks]
                })
            ns.entity['params'] = encryption
            if len(cache_disks) > 0:
                if 'cache' not in ns.entity:
                    ns.entity['topology']['cache'] = []

                for disk in cache_disks:
                    ns.entity['topology']['cache'].append({
                        'type': 'disk',
                        'path': correct_disk_path(disk)
                    })

            if len(log_disks) > 0:
                if 'log' not in ns.entity:
                    ns.entity['topology']['log'] = []

                if len(log_disks) > 1:
                    ns.entity['topology']['log'].append({
                        'type': 'mirror',
                        'children': [{'type': 'disk', 'path': correct_disk_path(disk)} for disk in log_disks]
                    })
                else:
                    ns.entity['topology']['log'].append({
                        'type': 'disk',
                        'path': correct_disk_path(log_disks[0])
                    })

            context.submit_task(
                self.parent.create_task,
                ns.entity,
                password,
                callback=lambda s, t: post_save(ns, s, t))

    def complete(self, context):
        return [
            NullComplete('name='),
            EnumComplete('layout=', VOLUME_LAYOUTS.keys()),
            EnumComplete('type=', VOLUME_LAYOUTS.keys()),
            EnumComplete('encryption=', ['yes', 'no']),
            NullComplete('password='),
            EntitySubscriberComplete('disks=', 'disk', lambda d: os.path.basename(d['path']), ['auto'], list=True),
            EntitySubscriberComplete('cache=', 'disk', lambda d: os.path.basename(d['path']), ['auto'], list=True),
            EntitySubscriberComplete('log=', 'disk', lambda d: os.path.basename(d['path']), ['auto'], list=True),
        ]


@description("Allows to provide a password that protects an encrypted volume")
class SetPasswordCommand(Command):
    """
    Usage: password <password>

    Allows to provide a password that protects an encrypted volume.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        self.parent.password = args[0]


@description("Manage volumes, snapshots, replications, and scrubs")
class VolumesNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The volume namespace provides commands for managing volumes,
    datasets, snapshots, replications, and scrubs.
    """

    def __init__(self, name, context):
        super(VolumesNamespace, self).__init__(name, context)

        self.primary_key_name = 'id'
        self.save_key_name = 'id'
        self.entity_subscriber_name = 'volume'
        self.create_task = 'volume.create'
        self.update_task = 'volume.update'
        self.delete_task = 'volume.delete'
        self.localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete <volume>

            Example: delete mypool

            Deletes a volume.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists volumes, optionally doing filtering and sorting.

            Examples:
                show
                show | search name == mypool
                show | search status == ONLINE | sort name""")

        self.skeleton_entity = {
            'type': 'zfs',
            'topology': {
                'data': []
            }
        }

        self.add_property(
            descr='Volume name',
            name='name',
            get='id',
            list=True)

        self.add_property(
            descr='Encrypted',
            name='encrypted',
            get='encrypted',
            type=ValueType.BOOLEAN,
            set=None)

        self.add_property(
            descr='Providers',
            name='providers',
            get='providers_presence',
            type=ValueType.STRING,
            set=None)

        self.add_property(
            descr='Status',
            name='status',
            get='status',
            set=None,
            list=True)

        self.add_property(
            descr='Mount point',
            name='mountpoint',
            get='mountpoint',
            set=None,
            list=True)

        self.add_property(
            descr='Last scrub time',
            name='last_scrub_time',
            get='scan.end_time',
            set=None,
            list=False
        )

        self.add_property(
            descr='Last scrub errors',
            name='last_scrub_errors',
            get='scan.errors',
            set=None,
            list=False
        )

        self.primary_key = self.get_mapping('name')
        self.extra_commands = {
            'find': FindVolumesCommand(),
            'find_media': FindMediaCommand(),
            'import': ImportVolumeCommand(),
        }

        self.entity_commands = self.get_entity_commands
        self.entity_namespaces = lambda this: [
            DatasetsNamespace('dataset', self.context, this),
            SnapshotsNamespace('snapshot', self.context, this)
        ]

    def commands(self):
        cmds = super(VolumesNamespace, self).commands()
        cmds.update({'create': CreateVolumeCommand(self)})
        return cmds

    def get_entity_commands(self, this):
        this.load()
        commands = {
            'show_topology': ShowTopologyCommand(this),
            'show_disks': ShowDisksCommand(this),
            'scrub': ScrubCommand(this),
            'add_vdev': AddVdevCommand(this),
            'delete_vdev': DeleteVdevCommand(this),
            'offline': OfflineVdevCommand(this),
            'online': OnlineVdevCommand(this),
            'extend_vdev': ExtendVdevCommand(this),
            'import': ImportFromVolumeCommand(this),
            'detach': DetachVolumeCommand(this)
        }

        if this.entity is not None:
            if this.entity.get('encrypted', False) is True:
                commands['password'] = SetPasswordCommand(this)
                prov_presence = this.entity.get('providers_presence', 'NONE')
                if prov_presence == 'NONE':
                    commands['unlock'] = UnlockVolumeCommand(this)
                    commands['restore_key'] = RestoreVolumeMasterKeyCommand(this)
                elif prov_presence == 'ALL':
                    commands['lock'] = LockVolumeCommand(this)
                    commands['rekey'] = RekeyVolumeCommand(this)
                    commands['backup_key'] = BackupVolumeMasterKeyCommand(this)
                else:
                    commands['unlock'] = UnlockVolumeCommand(this)
                    commands['lock'] = LockVolumeCommand(this)

        return commands

    def save(self, this, new=False):
        if new:
            self.context.submit_task(
                self.create_task,
                this.entity,
                this.password,
                callback=lambda s, t: post_save(this, s, t))
            return

        self.context.submit_task(
            self.update_task,
            this.orig_entity[self.save_key_name],
            this.get_diff(),
            this.password,
            callback=lambda s, t: post_save(this, s, t))


def _init(context):
    context.attach_namespace('/', VolumesNamespace('volume', context))
