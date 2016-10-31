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

import copy
import gettext
import six
from freenas.cli.namespace import (
    EntityNamespace, Command, CommandException, SingleItemNamespace,
    EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, description
)
from freenas.cli.complete import NullComplete, EnumComplete, EntitySubscriberComplete
from freenas.cli.output import Table, ValueType, output_tree, format_value, read_value, Sequence
from freenas.cli.utils import TaskPromise, EntityPromise, post_save, iterate_vdevs, vdev_by_path, mirror_by_path
from freenas.cli.utils import to_list, correct_disk_path, get_related, set_related, get_item_stub
from freenas.utils import query as q

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
                    password=<password>

    Example:
            add_vdev type=mirror disks=ada3,ada4
            add_vdev type=mirror disks=ada3,ada4 password=secret

    Valid types are: mirror disk raidz1 raidz2 raidz3 cache log
    If volume is encrypted by password you have to provide
    the current valid password to this command.

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

        password = kwargs.get('password')
        password_encrypted = self.parent.entity.get('password_encrypted', False)
        if password_encrypted and not password:
            raise CommandException('Volume is password encrypted. You have to provide a password.')
        if password and not password_encrypted:
            raise CommandException('Volume is not encrypted by password.')

        if password_encrypted:
            password_prop = self.parent.get_mapping('password')
            password_prop.do_set(self.parent.update_args, password, self.parent.entity)

        disks_per_type = DISKS_PER_TYPE.copy()
        disks_per_type.pop('auto', None)
        disks_per_type.update({
            'log': 1,
            'cache': 1,
            'spare': 1
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

        if typ in ('log', 'spare'):
            if len(disks) != 1:
                raise CommandException(_("Log or spare vdevs cannot be mirrored"))

            if 'log' not in entity:
                entity['topology'][typ] = []

            entity['topology'][typ].append({
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

    def complete(self, context, **kwargs):
        return [
            EnumComplete('type=', ['mirror', 'disk', 'raidz1', 'raidz2', 'raidz3', 'cache', 'log']),
            EntitySubscriberComplete('disks=', 'disk', lambda d: d['name'], ['auto'], list=True),
            NullComplete('password=')
        ]


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

        vdev = mirror_by_path(self.parent.entity['topology'], vdev_ident)

        if not vdev:
            raise CommandException('Cannot find vdev for disk {0}'.format(vdev_ident))

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


@description("Replaces a disk in a pool")
class ReplaceCommand(Command):
    """
    Usage:
        replace <olddisk> <newdisk>

    Example:
        extend_vdev ada1 ada2

    Replaces <olddisk> with <newdisk> in a volume. If <newdisk> is a spare of current volume,
    it will be removed from the spares list.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) != 2:
            raise CommandException("Please specify old and new disk names as positional arguments")

        old_disk = correct_disk_path(args[0])
        new_disk = correct_disk_path(args[1])
        vdev = vdev_by_path(self.parent.entity['topology'], old_disk)

        if not vdev:
            raise CommandException('Cannot find vdev for disk {0}'.format(old_disk))

        tid = context.submit_task('volume.vdev.replace', self.parent.entity['id'], vdev['guid'], new_disk)
        return TaskPromise(context, tid)


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

    Offlines a disk in a volume.
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

        tid = context.submit_task(
            'volume.vdev.offline',
            self.parent.entity['id'],
            guid,
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)


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

        tid = context.submit_task(
            'volume.vdev.online',
            self.parent.entity['id'],
            guid,
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)


@description("Finds volumes available to import")
class FindVolumesCommand(Command):
    """
    Usage: find

    Examples:
            find

    Finds volumes that can be imported.
    """
    def run(self, context, args, kwargs, opargs):
        vols = context.call_sync('volume.find', timeout=300)
        return Table(vols, [
            Table.Column('ID', 'id', vt=ValueType.STRING),
            Table.Column('Volume name', 'name'),
            Table.Column('Status', 'status')
        ])


@description("Finds connected media that can be used to import data from")
class FindMediaCommand(Command):
    """
    Usage: find_media

    Examples:
            find_media

    Finds media that can be used to import data from.
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
    When importing encrypted volume key and/or password and disks must be provided.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException('Not enough arguments passed')

        id = str(args[0])

        if 'key' in kwargs or 'password' in kwargs:
            if 'disks' not in kwargs:
                raise CommandException('You have to provide list of disks when importing an encrypted volume')

            disks = kwargs['disks']
            if isinstance(disks, str):
                disks = [disks]

            correct_disks = []
            for dname in disks:
                correct_disks.append(correct_disk_path(dname))

            password = kwargs.get('password')
            encryption = {
                'key': kwargs.get('key'),
                'disks': correct_disks
            }
        else:
            encryption = {}
            password = None

        ns = get_item_stub(context, self.parent, None)

        tid = context.submit_task(
            'volume.import',
            id,
            kwargs.get('newname', None),
            {},
            encryption,
            password,
            callback=lambda s, t: post_save(ns, s, t)
        )

        return EntityPromise(context, tid, ns)


@description("Imports items from a given volume")
class ImportFromVolumeCommand(Command):
    """
    Usage: import <all\vms\shares\system>

    Examples:
            import all
            import vms

    Imports services from a volume.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException('Not enough arguments passed')

        scope = args[0]

        if scope not in ['all', 'vms', 'shares', 'system']:
            raise CommandException('Import scope must be one of all \ vms \ shares \ system')

        tid = context.submit_task('volume.autoimport', self.parent.entity['id'], scope)
        return TaskPromise(context, tid)


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
        tid = context.submit_task('volume.export', self.parent.entity['id'])
        return TaskPromise(context, tid)


@description("Upgrades  given volume")
class UpgradeVolumeCommand(Command):
    """
    Usage: upgrade

    Examples: upgrade

    Upgrades a volume.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task('volume.upgrade', self.parent.entity['id'])
        return TaskPromise(context, tid)


@description("Unlocks encrypted volume")
class UnlockVolumeCommand(Command):
    """
    Usage: unlock password=<password>

    Example: unlock
             unlock password=secret

    Unlocks an encrypted volume.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if self.parent.entity.get('providers_presence', 'ALL') == 'ALL':
            raise CommandException('Volume is already fully unlocked')
        password = kwargs.get('password')
        password_encrypted = self.parent.entity.get('password_encrypted', False)
        if password_encrypted and not password:
            raise CommandException('Volume is password encrypted. You have to provide a password.')
        if password and not password_encrypted:
            raise CommandException('Volume is not encrypted by password.')

        name = self.parent.entity['id']
        tid = context.submit_task('volume.unlock', name, password, callback=lambda s, t: post_save(self.parent, s, t))
        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            NullComplete('password=')
        ]


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
        tid = context.submit_task('volume.lock', name, callback=lambda s, t: post_save(self.parent, s, t))
        return TaskPromise(context, tid)


@description("Generates new user key for encrypted volume")
class RekeyVolumeCommand(Command):
    """
    Usage: rekey key_encrypted=<key_encrypted> password=<password>

    Example: rekey
             rekey key_encrypted=yes
             rekey key_encrypted=yes password=new_password
             rekey password=new_password
             rekey key_encrypted=no password=new_password

    Generates a new user key for an encrypted volume.
    Your volume must be unlocked to perform this operation.
    Rekey command with no arguments defaults to key_encrypted=yes.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if self.parent.entity.get('providers_presence', 'NONE') != 'ALL':
            raise CommandException('You must unlock your volume first')
        password = kwargs.get('password', None)
        key_encrypted = read_value(kwargs.pop('key_encrypted', 'yes'), ValueType.BOOLEAN)
        name = self.parent.entity['id']
        tid = context.submit_task('volume.rekey', name, key_encrypted, password)
        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EnumComplete('key_encrypted=', ['yes', 'no']),
            NullComplete('password=')
        ]


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

    def complete(self, context, **kwargs):
        return [
            NullComplete('path=')
        ]


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
        tid = context.submit_task('volume.keys.restore', name, password, path)
        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            NullComplete('path='),
            NullComplete('password=')
        ]


@description("Shows volume topology")
class ShowTopologyCommand(Command):
    """
    Usage: show_topology

    Example: show_topology

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

    Examples: show_disks

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
        tid = context.submit_task('volume.scrub', self.parent.entity['id'])
        return TaskPromise(context, tid)


@description("Creates snapshot of a dataset")
class SnapshotCommand(Command):
    """
    Usage: snapshot <snapshot name>
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException('Snapshot name must be provided')

        name = str(args[0])
        tid = context.submit_task('volume.snapshot.create', {
            'id': '{0}@{1}'.format(self.parent.entity['id'], name)
        })

        return TaskPromise(context, tid)


@description("Replicates dataset to another system")
class ReplicateCommand(Command):
    """
    Usage: replicate peer=<peer> remote_dataset=<remote_dataset>
           dry_run=<yes/no> recursive=<yes/no> follow_delete=<yes/no>
           encrypt=<encrypt> compress=<fast/default/best> throttle=<throttle>

    Example: replicate peer=10.20.0.2 remote_dataset=mypool
             replicate peer=freenas-2.local remote_dataset=mypool encrypt=AES128
             replicate peer=10.20.0.2 remote_dataset=mypool throttle=10MiB

    Replicate a dataset to a remote dataset.
    Currently available encryption methods are AES128, AES192 and AES256.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        peer = kwargs.pop('peer')
        remote_dataset = kwargs.pop('remote_dataset')
        dry_run = read_value(kwargs.pop('dry_run', 'no'), ValueType.BOOLEAN)
        recursive = read_value(kwargs.pop('recursive', 'no'), ValueType.BOOLEAN)
        follow_delete = read_value(kwargs.pop('follow_delete', 'no'), ValueType.BOOLEAN)
        compress = kwargs.pop('compress', None)
        encrypt = kwargs.pop('encrypt', None)
        throttle = kwargs.pop('throttle', None)
        transport_plugins = []

        if not remote_dataset:
            raise CommandException(_('Remote dataset must be specified'))

        peer = context.entity_subscribers['peer'].query(('name', '=', peer), single=True)
        if not peer:
            raise CommandException('Peer {0} unknown'.format(peer))

        if compress:
            if compress not in ['fast', 'default', 'best']:
                raise CommandException('Compression level must be selected as one of: fast, default, best')

            transport_plugins.append({
                '%type': 'compress-replication-transport-option',
                'level': compress.upper()
            })

        if throttle:
            if not isinstance(throttle, int):
                raise CommandException('Throttle must be a number representing maximum transfer per second')

            transport_plugins.append({
                '%type': 'throttle-replication-transport-option',
                'buffer_size': throttle
            })

        if encrypt:
            if encrypt not in ['AES128', 'AES192', 'AES256']:
                raise CommandException('Encryption type must be selected as one of: AES128, AES192, AES256')

            transport_plugins.append({
                '%type': 'encrypt-replication-transport-option',
                'type': encrypt
            })

        args = (
            'replication.replicate_dataset',
            self.parent.entity['name'],
            {
                'peer': peer['id'],
                'remote_dataset': remote_dataset,
                'recursive': recursive,
                'followdelete': follow_delete
            },
            transport_plugins,
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
                    result['result'][0], [
                        Table.Column('Action type', 'type', ValueType.STRING, 20),
                        Table.Column('Description', describe, ValueType.STRING)
                    ]
                ),
                "Estimated replication stream size: {0}".format(format_value(
                    result['result'][1],
                    ValueType.SIZE)
                )
            )

        else:
            tid = context.submit_task(*args)
            return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete('peer=', 'peer', lambda o: o['name'] if o['type'] == 'freenas' else None),
            NullComplete('remote_dataset='),
            EnumComplete('dry_run=', ['yes', 'no']),
            EnumComplete('recursive=', ['yes', 'no']),
            EnumComplete('follow_delete=', ['yes', 'no']),
            EnumComplete('encrypt=', ['AES128', 'AES192', 'AES256']),
            EnumComplete('compress=', ['fast', 'default', 'best']),
            NullComplete('throttle=')
        ]


class OpenFilesCommand(Command):
    """
    Usage: open_files

    Examples: open_files

    Shows the files currently open.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        files = context.call_sync('filesystem.get_open_files', self.parent.entity['mountpoint'])
        return Table(files, [
            Table.Column('Process name', 'process_name'),
            Table.Column('PID', 'pid', ValueType.NUMBER),
            Table.Column('File path', 'path')
        ])


@description("Mounts readonly dataset under selected system path")
class PeekCommand(Command):
    """
    Usage: peek path=<path>

    Example: peek path=/path/to/my/temporary/mountpoint

    Mounts readonly dataset under selected system path.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        path = kwargs.get('path')
        if not path:
            raise CommandException('You have to specify path to your mountpoint')

        tid = context.submit_task(
            'volume.dataset.temporary.mount',
            self.parent.entity['id'],
            path,
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            NullComplete('path=')
        ]


@description("Unmounts readonly dataset")
class UnpeekCommand(Command):
    """
    Usage: unpeek

    Example: unpeek

    Unmounts readonly dataset.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task(
            'volume.dataset.temporary.umount',
            self.parent.entity['id'],
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)


@description("Datasets")
class DatasetsNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent=None):
        super(DatasetsNamespace, self).__init__(name, context)
        self.parent = parent
        self.path = name
        self.entity_subscriber_name = 'volume.dataset'
        self.create_task = 'volume.dataset.create'
        self.update_task = 'volume.dataset.update'
        self.required_props = ['name']
        self.conditional_required_props = self.get_conditional_required_props

        if self.parent and self.parent.entity:
            self.extra_query_params = [
                ('volume', '=', self.parent.entity.get('id'))
            ]

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <volume>/<dataset>
                   create name=<volume>/<dataset>
                   create <volume>/<dataset>/<dataset>

            Examples: create mypool/mydataset
                      create mypool/mydataset/somedataset
                      create mypool/mydataset dedup="sha512,verify" compression=gzip-4

            Creates a dataset.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Examples: delete

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
            'volume': self.parent.entity.get('id') if self.parent.entity else None,
            'temp_mountpoint': None,
            'properties': {}
        }

        self.add_property(
            descr='Name',
            name='name',
            get='id',
            list=True,
            usage=_("The name of the dataset.")
        )

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            list=True,
            enum=['FILESYSTEM', 'VOLUME'],
            usage=_("The type of dataset (can be either FILESYSTEM which is a basic ZFS dataset or a VOLUME which is a ZVOL")
        )

        self.add_property(
            descr='Permissions type',
            name='permissions_type',
            get='permissions_type',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM',
            usage=_("Type of permissions (can be either standard PERM or ACL)") 
        )

        self.add_property(
            descr='Owner',
            name='owner',
            get='permissions.user',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM',
            usage=_("User that is the owner of the dataset.")
        )

        self.add_property(
            descr='Group',
            name='group',
            get='permissions.group',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM',
            usage=_("Group that has ownership permissions for the dataset.")
        )

        self.add_property(
            descr='Compression',
            name='compression',
            get='properties.compression.parsed',
            set='properties.compression.parsed',
            list=True,
            enum=[
                'on', 'off', 'gzip', 'gzip-1', 'gzip-2', 'gzip-3', 'gzip-4', 'gzip-5',
                'gzip-6', 'gzip-7', 'gzip-8', 'gzip-9', 'lzjb', 'lz4', 'zle'
            ],
            usage=_("Type of compression, (i.e. gzip, lz4, etc.)")
        )

        self.add_property(
            descr='Used',
            name='used',
            get='properties.used.value',
            set=None,
            list=True,
            usage=_("Amount of space is used on the dataset.")
        )

        self.add_property(
            descr='Available',
            name='available',
            get='properties.available.value',
            set=None,
            list=True,
            usage=_("Amount of space is available on the dataset.")
        )

        self.add_property(
            descr='Access time',
            name='atime',
            get='properties.atime.parsed',
            list=False,
            type=ValueType.BOOLEAN,
            condition=lambda o: o['type'] == 'FILESYSTEM',
            usage=_("Last time the dataset was accessed.")
        )

        self.add_property(
            descr='Deduplication',
            name='dedup',
            get='properties.dedup.parsed',
            list=False,
            enum=[
                'on', 'off', 'verify', 'sha256', 'sha256,verify',
                'sha512', 'sha512,verify', 'skein', 'skein,verify', 'edonr,verify'
            ],
            usage=_("Type of deduplication, use 'off' for none.")
        )

        self.add_property(
            descr='Quota',
            name='refquota',
            get='properties.refquota.parsed',
            list=False,
            type=ValueType.SIZE,
            condition=lambda o: o['type'] == 'FILESYSTEM',
            usage=_("Size quota for dataset")
        )

        self.add_property(
            descr='Recursive quota',
            name='quota',
            get='properties.quota.parsed',
            list=False,
            type=ValueType.SIZE,
            condition=lambda o: o['type'] == 'FILESYSTEM',
            usage=_("Size quota for the child datasets")
        )

        self.add_property(
            descr='Space reservation',
            name='refreservation',
            get='properties.refreservation.parsed',
            list=False,
            type=ValueType.SIZE,
            condition=lambda o: o['type'] == 'FILESYSTEM',
            usage=_("Amount of space reserved for this dataset")
        )

        self.add_property(
            descr='Recursive space reservation',
            name='reservation',
            get='properties.reservation.parsed',
            list=False,
            type=ValueType.SIZE,
            condition=lambda o: o['type'] == 'FILESYSTEM',
            usage=_("Amount of space reserved for the child datasets")
        )

        self.add_property(
            descr='Volume size',
            name='volsize',
            get='volsize',
            set='volsize',
            list=False,
            type=ValueType.SIZE,
            condition=lambda o: o['type'] == 'VOLUME',
            usage=_("Size of the volume.")
        )

        self.add_property(
            descr='Block size',
            name='blocksize',
            get='properties.volblocksize.parsed',
            list=False,
            condition=lambda o: o['type'] == 'VOLUME',
            usage=_("Blocksize for the volume.")
        )

        self.add_property(
            descr='Mounted',
            name='mounted',
            get='mounted',
            list=True,
            type=ValueType.BOOLEAN,
            usage=_("Tells if the volume is mounted or not.")
        )

        self.add_property(
            descr='Temporary mountpoint',
            name='temp_mount',
            get='temp_mountpoint',
            list=False,
            usersetable=False,
            condition=lambda o: o['temp_mountpoint'],
            usage=_("Shows the mountpoint if a volume is currently mounted to one")
        )

        self.add_property(
            descr='Last replicated by',
            name='last_replicated_by',
            get='last_replicated_by',
            set=None,
            list=False
        )

        self.add_property(
            descr='Last replicated at',
            name='last_replicated_at',
            get='last_replicated_at',
            set=None,
            list=False,
            type=ValueType.TIME
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = self.get_entity_commands
        self.entity_namespaces = lambda this: [
            VMwareDatasetsNamespace('vmware_snapshots', self.context, this)
        ]

    def get_conditional_required_props(self, obj):
        ret = []
        if obj.get('type') == 'VOLUME':
            ret = ['volsize']
        return ret

    def delete(self, this, kwargs):
        return self.context.submit_task(
            'volume.dataset.delete',
            this.entity['id']
        )

    def save(self, this, new=False):
        if new:
            newname = this.entity['id']
            if len(newname.split('/')) < 2:
                raise CommandException(_("Please specify name as a relative path starting from the dataset's parent volume."))

        return super(DatasetsNamespace, self).save(this, new)

    def get_entity_commands(self, this):
        this.load()
        commands = {
            'snapshot': SnapshotCommand(this),
            'replicate': ReplicateCommand(this),
            'open_files': OpenFilesCommand(this)
        }

        if this.entity:
            if q.get(this.entity, 'properties.readonly.parsed'):
                if this.entity['mounted']:
                    commands['unpeek'] = UnpeekCommand(this)
                else:
                    commands['peek'] = PeekCommand(this)

        if getattr(self, 'is_docgen_instance', False):
            commands['unpeek'] = UnpeekCommand(this)
            commands['peek'] = PeekCommand(this)

        return commands


class RollbackCommand(Command):
    """
    Usage: rollback force=<force>

    Example: rollback
             rollback force=yes

    Returns filesystem to the state saved in selected snapshot.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        force = kwargs.get('force', False)
        tid = context.submit_task(
            'volume.snapshot.rollback',
            self.parent.entity['id'],
            force
        )

        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EnumComplete('force=', ['yes', 'no'])
        ]


class CloneCommand(Command):
    """
    Usage: clone new_name=<new_name>

    Example: clone new_name=my_new_dataset

    Creates a clone of snapshot in new dataset.
    New dataset must belong to the same pool as snapshot.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        new_name = kwargs.get('new_name')
        if not new_name:
            raise CommandException('Name of clone have to be specified')

        ns = get_item_stub(context, self.parent.parent, new_name)

        tid = context.submit_task(
            'volume.snapshot.clone',
            self.parent.entity['id'],
            new_name,
            callback=lambda s, t: post_save(ns, s, t)
        )

        return EntityPromise(context, tid, ns)

    def complete(self, context, **kwargs):
        return [
            NullComplete('new_name=')
        ]


@description("Snapshots")
class SnapshotsNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent=None):
        super(SnapshotsNamespace, self).__init__(name, context)
        self.parent = parent
        self.entity_subscriber_name = 'volume.snapshot'
        self.create_task = 'volume.snapshot.create'
        self.update_task = 'volume.snapshot.update'
        self.delete_task = 'volume.snapshot.delete'
        self.primary_key_name = 'id'
        self.required_props = ['name']
        self.large = True

        if parent and parent.entity:
            self.extra_query_params = [
                ('volume', '=', self.parent.entity.get('id'))
            ]

        self.add_property(
            descr='Snapshot name',
            name='name',
            get='id',
            list=True,
            usage=_("ID of the snapshot.")
        )

        self.add_property(
            descr='Dataset name',
            name='dataset',
            get='dataset',
            list=True,
            usage=_("Name of the dataset.")
        )

        self.add_property(
            descr='Recursive',
            name='recursive',
            get=None,
            set='0',
            list=False,
            type=ValueType.BOOLEAN,
            usage=_("Boolean that sets whether or not the snapshots are recursive."),
            create_arg=True
        )

        self.add_property(
            descr='Replicable',
            name='replicable',
            get='replicable',
            list=False,
            type=ValueType.BOOLEAN,
            usage=_("Boolean that sets whether or not the snapshots are replicable.")
        )

        self.add_property(
            descr='Lifetime',
            name='lifetime',
            get='lifetime',
            list=False,
            type=ValueType.NUMBER,
            usage=_("Lifetime of the snapshot.")
        )

        self.add_property(
            descr='Compression',
            name='compression',
            get='properties.compression.parsed',
            set='properties.compression.parsed',
            list=True,
            usage=_("Type of compression, (i.e. gzip, lz4, etc.)")
        )

        self.add_property(
            descr='Used',
            name='used',
            get='properties.used.parsed',
            set=None,
            type=ValueType.SIZE,
            list=True,
            usage=_("Amount of space used on the dataset.")
        )

        self.add_property(
            descr='Available',
            name='available',
            get='properties.available.parsed',
            set=None,
            type=ValueType.SIZE,
            list=True,
            usage=_("Amount of space is available on the dataset.")
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda this: {
            'rollback': RollbackCommand(this),
            'clone': CloneCommand(this)
        }

    def delete(self, this, kwargs):
        return self.context.submit_task(
            self.delete_task,
            this.entity[self.save_key_name],
            read_value(kwargs.get('recursive', 'no'), ValueType.BOOLEAN)
        )


@description("Filesystem contents")
class FilesystemNamespace(EntityNamespace):
    def __init__(self, name, context, parent):
        super(FilesystemNamespace, self).__init__(name, context)
        self.parent = parent

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            usage=_("The name of the file.")
        )


@description("Configure VMware datastore mappings")
class VMwareDatasetsNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent=None):
        super(VMwareDatasetsNamespace, self).__init__(name, context)
        self.parent = parent
        self.entity_subscriber_name = 'vmware.dataset'
        self.create_task = 'vmware.dataset.create'
        self.update_task = 'vmware.dataset.update'
        self.delete_task = 'vmware.dataset.delete'
        self.primary_key_name = 'name'

        if self.parent and self.parent.entity:
            self.skeleton_entity = {
                'dataset': self.parent.entity.get('id')
            }

        self.add_property(
            descr='Mapping name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='Datastore name',
            name='datastore',
            get='datastore',
            list=True
        )

        self.add_property(
            descr='VMware peer',
            name='peer',
            get=lambda o: get_related(self.context, 'peer', o, 'peer'),
            set=lambda o, v: set_related(self.context, 'peer', o, 'peer', v),
            list=True
        )

        self.add_property(
            descr='VM filtering',
            name='vm_filter_op',
            get='vm_filter_op',
            list=False,
            enum=['NONE', 'INCLUDE', 'EXCLUDE']
        )

        self.add_property(
            descr='VM filter entries',
            name='vm_filter_entries',
            get='vm_filter__entries',
            list=False,
            type=ValueType.SET
        )

        self.primary_key = self.get_mapping('name')


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
        return 'auto', cache_disks, log_disks
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
    Usage: create <name> disks=<disks> layout=<layout> key_encryption=<key_encryption>
            password=<password> cache=<disks> log=<disks> auto_unlock=<auto_unlock>

    Example: create mypool disks=ada1,ada2
             create mypool disks=ada1,ada2 key_encryption=yes
             create mypool disks=ada1,ada2 key_encryption=yes password=1234
             create mypool disks=auto key_encryption=yes auto_unlock=yes
             create mypool disks=ada1,ada2 password=1234
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
            # However, do not allow user to specify name as both implicit and explicit parameter as this suggests a mistake
            if 'name' in kwargs:
                raise CommandException(_("Both implicit and explicit 'name' parameters are specified."))
            else:
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

        key_encryption = read_value(kwargs.pop('key_encryption', False), ValueType.BOOLEAN)
        password = kwargs.get('password')
        auto_unlock = None
        if 'auto_unlock' in kwargs:
            auto_unlock = read_value(kwargs.pop('auto_unlock', False), ValueType.BOOLEAN)
        if auto_unlock and (not key_encryption or password):
            raise CommandException(_(
                'Automatic volume unlock can be selected for volumes using only key based encryption.'
            ))

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

        ns = SingleItemNamespace(name, self.parent, context)
        ns.orig_entity = copy.deepcopy(self.parent.skeleton_entity)
        ns.entity = copy.deepcopy(self.parent.skeleton_entity)
        ns.entity['id'] = name

        disks, cache_disks, log_disks = check_disks(context, disks, cache_disks, log_disks)

        if disks != 'auto':
            if len(disks) < DISKS_PER_TYPE[volume_type]:
                raise CommandException(_("Volume type {0} requires at least {1} disks".format(
                    volume_type,
                    DISKS_PER_TYPE[volume_type]
                )))
            if len(disks) > 1 and volume_type == 'disk':
                raise CommandException(_("Cannot create a volume of type disk with multiple disks"))

        if volume_type == 'auto':
            layout = kwargs.pop('layout', 'auto')
            if layout not in VOLUME_LAYOUTS:
                raise CommandException(_(
                    "Invalid layout {0}.  Should be one of: {1}".format(layout, list(VOLUME_LAYOUTS.keys()))
                ))
            else:
                if disks != 'auto' and len(disks) < DISKS_PER_TYPE[VOLUME_LAYOUTS[layout]]:
                    raise CommandException(_("Volume layout {0} requires at least {1} disks".format(layout, DISKS_PER_TYPE[VOLUME_LAYOUTS[layout]])))

            tid = context.submit_task(
                'volume.create_auto',
                name,
                'zfs',
                layout,
                disks,
                cache_disks,
                log_disks,
                key_encryption,
                password,
                auto_unlock,
                callback=lambda s, t: post_save(ns, s, t)
            )

            return EntityPromise(context, tid, ns)
        elif volume_type == 'custom':
            if not isinstance(kwargs.get('topology'), dict):
                raise CommandException(_("Volume topology needs to be passed as 'topology' parameter"))

            ns.entity['topology'] = kwargs['topology']
        else:
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

        ns.entity['key_encrypted'] = key_encryption
        ns.entity['password_encrypted'] = True if password else False
        ns.entity['auto_unlock'] = auto_unlock

        tid = context.submit_task(
            self.parent.create_task,
            ns.entity,
            password,
            callback=lambda s, t: post_save(ns, s, t)
        )

        return EntityPromise(context, tid, ns)

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
            EnumComplete('layout=', VOLUME_LAYOUTS.keys()),
            EnumComplete('type=', VOLUME_LAYOUTS.keys()),
            EnumComplete('key_encryption=', ['yes', 'no']),
            EnumComplete('auto_unlock=', ['yes', 'no']),
            NullComplete('password='),
            EntitySubscriberComplete('disks=', 'disk', lambda d: d['name'], ['auto'], list=True),
            EntitySubscriberComplete('cache=', 'disk', lambda d: d['name'], ['auto'], list=True),
            EntitySubscriberComplete('log=', 'disk', lambda d: d['name'], ['auto'], list=True),
        ]


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
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Examples: delete

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
            list=True,
            usage=_("The name of the volume.")
        )

        self.add_property(
            descr='Volume GUID',
            name='guid',
            get='guid',
            list=False,
            usage=_("The GUID of the volume.")
        )

        self.add_property(
            descr='Encrypted by key',
            name='key_encrypted',
            get='key_encrypted',
            type=ValueType.BOOLEAN,
            set=None,
            usage=_("Flag that tells whether or not the volume is encrypted with a key.")
        )

        self.add_property(
            descr='Encrypted by password',
            name='password_encrypted',
            get='password_encrypted',
            type=ValueType.BOOLEAN,
            set=None,
            usage=_("Flag that tells whether or not the volume is encrypted with a password.")
        )

        self.add_property(
            descr='Automatic unlock',
            name='auto_unlock',
            get='auto_unlock',
            type=ValueType.BOOLEAN,
            condition=lambda o: o.get('key_encrypted') and not o.get('password_encrypted'),
            usage=_("Flag that tells whether or not the volume is set to automatically unlock.")
        )

        self.add_property(
            descr='Providers',
            name='providers',
            get='providers_presence',
            type=ValueType.STRING,
            set=None,
            usage=_("The provider of the volume if any.")
        )

        self.add_property(
            descr='Status',
            name='status',
            get='status',
            set=None,
            list=True,
            usage=_("The status of the volume.")    
        )

        self.add_property(
            descr='Mount point',
            name='mountpoint',
            get='mountpoint',
            set=None,
            list=True,
            usage=_("Displays the current mount point of the volume.")
        )

        self.add_property(
            descr='Last scrub time',
            name='last_scrub_time',
            get='scan.end_time',
            set=None,
            list=False,
            usage=_("Shows the last scrub time.")
        )

        self.add_property(
            descr='Last scrub errors',
            name='last_scrub_errors',
            get='scan.errors',
            set=None,
            list=False,
            usage=_("Shows the last scrub errors if any.")
        )

        self.add_property(
            descr='Total size',
            name='size',
            get='properties.size.parsed',
            set=None,
            type=ValueType.SIZE,
            list=False,
            usage=_("Shows the size of the volume.")
        )

        self.add_property(
            descr='Allocated',
            name='allocated',
            get='properties.allocated.parsed',
            set=None,
            type=ValueType.SIZE,
            list=False,
            usage=_("Shows the allocated size of the volume.")
        )

        self.add_property(
            descr='Free',
            name='free',
            get='properties.free.parsed',
            set=None,
            type=ValueType.SIZE,
            list=False,
            usage=_("Shows the amount of space free on the volume.")
        )

        self.add_property(
            descr='Capacity',
            name='capacity',
            get='properties.capacity.parsed',
            set=None,
            list=False,
            usage=_("Shows the capacity of the volume.")
        )

        self.add_property(
            descr='Fragmentation',
            name='fragmentation',
            get='properties.fragmentation.parsed',
            set=None,
            list=False,
            usage=_("Shows the volume's fragmentation.")
        )

        self.add_property(
            descr='Read errors',
            name='read_errors',
            get='root_vdev.stats.read_errors',
            set=None,
            type=ValueType.NUMBER,
            list=False,
            usage=_("Shows the number of read errors on the volume.")
        )

        self.add_property(
            descr='Write errors',
            name='write_errors',
            get='root_vdev.stats.write_errors',
            set=None,
            type=ValueType.NUMBER,
            list=False,
            usage=_("Shows the number of write errors on the volume.")
        )

        self.add_property(
            descr='Checksum errors',
            name='checksum_errors',
            get='root_vdev.stats.checksum_errors',
            set=None,
            type=ValueType.NUMBER,
            list=False,
            usage=_("Shows the number of checksum errors on the volume.")
        )

        self.add_property(
            descr='Password',
            name='password',
            get=None,
            set='0',
            update_arg=True,
            list=False,
            condition=lambda o: o.get('password_encrypted'),
            usage=_("Allows to provide password of encrypted volume when update operation does require it.")
        )

        self.primary_key = self.get_mapping('name')
        self.extra_commands = {
            'find': FindVolumesCommand(),
            'find_media': FindMediaCommand(),
            'import': ImportVolumeCommand(self),
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
            'replace': ReplaceCommand(this),
            'import': ImportFromVolumeCommand(this),
            'detach': DetachVolumeCommand(this),
            'upgrade': UpgradeVolumeCommand(this)
        }

        if this.entity is not None:
            if this.entity.get('key_encrypted') or this.entity.get('password_encrypted'):
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

        if getattr(self, 'is_docgen_instance', False):
            commands['unlock'] = UnlockVolumeCommand(this)
            commands['restore_key'] = RestoreVolumeMasterKeyCommand(this)
            commands['lock'] = LockVolumeCommand(this)
            commands['rekey'] = RekeyVolumeCommand(this)
            commands['backup_key'] = BackupVolumeMasterKeyCommand(this)
            commands['unlock'] = UnlockVolumeCommand(this)
            commands['lock'] = LockVolumeCommand(this)

        return commands


def _init(context):
    context.attach_namespace('/', VolumesNamespace('volume', context))
    context.map_tasks('volume.dataset.*', DatasetsNamespace)
    context.map_tasks('volume.snapshot.*', SnapshotsNamespace)
    context.map_tasks('volume.*', VolumesNamespace)
    context.map_tasks('vmware.dataset.*', VMwareDatasetsNamespace)
