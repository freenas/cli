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

import re
import copy
import icu
import inspect
from namespace import (
    EntityNamespace, Command, CommandException, SingleItemNamespace,
    RpcBasedLoadMixin, TaskBasedSaveMixin, description
    )
from output import Table, ValueType, output_tree, output_msg
from utils import post_save, iterate_vdevs
from fnutils import first_or_default, exclude, query


t = icu.Transliterator.createInstance("Any-Accents", icu.UTransDirection.FORWARD)
_ = t.transliterate


# Global lists/dicts for create command and other stuff
VOLUME_TYPES = ['disk', 'mirror', 'raidz1', 'raidz2', 'raidz3', 'auto']
DISKS_PER_TYPE = {
    'auto': 1,
    'disk':1,
    'mirror':2,
    'raidz1':3,
    'raidz2':4,
    'raidz3':5
}

def correct_disk_path(disk):
    if not re.match("^\/dev\/", disk):
        disk = "/dev/" + disk
    return disk


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
        if 'type' not in kwargs.keys():
            raise CommandException(_("Please specify a type of vdev, see 'help add_vdev' for more information"))
        typ = kwargs.pop('type')

        if typ not in ('disk', 'mirror', 'cache', 'log', 'raidz1', 'raidz2', 'raidz3'):
            raise CommandException(_("Invalid vdev type"))

        disks_per_type={'disk':1,
                        'cache':1,
                        'log':1,
                        'mirror':2,
                        'raidz1':3,
                        'raidz2':4,
                        'raidz3':5}

        if len(args) < disks_per_type[typ]:
            raise CommandException(_("Vdev of type {0} requires at least {1} disks".format(typ, disks_per_type[typ])))

            entity['topology']['data'].append({
                'type': 'mirror',
                'children': [{'type': 'disk', 'path': correct_disk_path(x)} for x in args]
            })

        if typ == 'disk':
            if len(args) != 1:
                raise CommandException(_("Disk vdev consist of single disk"))

            entity['topology']['data'].append({
                'type': 'disk',
                'path': correct_disk_path(args[0])
            })

        if typ == 'cache':
            if 'cache' not in entity:
                entity['topology']['cache'] = []

            entity['topology']['cache'].append({
                'type': 'disk',
                'path': correct_disk_path(args[0])
            })

        if typ == 'log':
            if len(args) != 1:
                raise CommandException(_("Log vdevs cannot be mirrored"))

            if 'log' not in entity:
                entity['topology']['log'] = []

            entity['topology']['log'].append({
                'type': 'disk',
                'path': correct_disk_path(args[0])
            })

        if typ.startswith('raidz'):
            entity['topology']['data'].append({
                'type': typ,
                'children': [{'type': 'disk', 'path': correct_disk_path(x)} for x in args]
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
        vdev_ident = correct_disk_path(kwargs.pop('vdev'))
        disk = correct_disk_path(args[0])

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
        context.submit_task('zfs.pool.offline_disk', self.parent.entity['name'], guid)


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
        context.submit_task('zfs.pool.online_disk', self.parent.entity['name'], guid)


@description("Finds volumes available to import")
class FindVolumesCommand(Command):
    """
    Usage: find

    Finds volumes that can be imported.
    """
    def run(self, context, args, kwargs, opargs):
        vols = context.call_sync('volumes.find')
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
        media = context.call_sync('volumes.find_media')
        return Table(media, [
            Table.Column('Path', 'path'),
            Table.Column('Label', 'label'),
            Table.Column('Size', 'size'),
            Table.Column('Filesystem type', 'fstype')
        ])


@description("Imports given volume")
class ImportVolumeCommand(Command):
    """
    Usage: import <name|id> [newname=<new-name>]

    Example: import tank

    Imports a detached volume.
    """
    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException('Not enough arguments passed')

        id = args[0]
        oldname = args[0]

        if not args[0].isdigit():
            vols = context.call_sync('volumes.find')
            vol = first_or_default(lambda v: v['name'] == args[0], vols)
            if not vol:
                raise CommandException('Importable volume {0} not found'.format(args[0]))

            id = vol['id']
            oldname = vol['name']

        context.submit_task('volume.import', id, kwargs.get('newname', oldname))


@description("Detaches given volume")
class DetachVolumeCommand(Command):
    """
    Usage: detach <name>

    Example: detach tank

    Detaches a volume.
    """
    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException('Not enough arguments passed')

        context.submit_task('volume.detach', args[0])


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

    Example: scrub tank

    Scrubs the volume
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('zfs.pool.scrub', self.parent.entity['name'])


@description("Datasets")
class DatasetsNamespace(EntityNamespace):
    def __init__(self, name, context, parent):
        super(DatasetsNamespace, self).__init__(name, context)
        self.parent = parent
        self.path = name
        self.required_props = ['name']
        
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <volume>/<dataset>
                   create <volume>/<dataset>/<dataset>
                
            Examples: create tank/foo
                      create tank/foo/bar
                   
            Creates a dataset.""")

        self.skeleton_entity = {
            'type': 'FILESYSTEM',
            'properties': {}
        }

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            list=True)

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            list=True)

        self.add_property(
            descr='Share type',
            name='share_type',
            get='share_type',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM')

        self.add_property(
            descr='Permissions type',
            name='permissions_type',
            get='permissions_type',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM')

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

        self.add_property(
            descr='Access time',
            name='atime',
            get='properties.atime.value',
            set='properties.atime.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM')

        self.add_property(
            descr='Deduplication',
            name='dedup',
            get='properties.dedup.value',
            set='properties.dedup.value',
            list=False)

        self.add_property(
            descr='Quota',
            name='refquota',
            get='properties.refquota.value',
            set='properties.refquota.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM')

        self.add_property(
            descr='Recrusive quota',
            name='quota',
            get='properties.quota.value',
            set='properties.quota.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM')

        self.add_property(
            descr='Space reservation',
            name='refreservation',
            get='properties.refreservation.value',
            set='properties.refreservation.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM')

        self.add_property(
            descr='Recrusive space reservation',
            name='reservation',
            get='properties.reservation.value',
            set='properties.reservation.value',
            list=False,
            condition=lambda o: o['type'] == 'FILESYSTEM')

        self.add_property(
            descr='Volume size',
            name='volsize',
            get='properties.volsize.value',
            set='properties.volsize.value',
            list=False,
            condition=lambda o: o['type'] == 'VOLUME')

        self.add_property(
            descr='Block size',
            name='blocksize',
            get='properties.volblocksize.value',
            set='properties.volblocksize.value',
            list=False,
            condition=lambda o: o['type'] == 'VOLUME')

        self.primary_key = self.get_mapping('name')

    def query(self, params, options):
        self.parent.load()
        return self.parent.entity['datasets']

    def get_one(self, name):
        self.parent.load()
        return first_or_default(lambda d: d['name'] == name, self.parent.entity['datasets'])

    def delete(self, name):
        self.context.submit_task('volume.dataset.delete', self.parent.entity['name'], name)

    def save(self, this, new=False):
        if new:
            newname = this.entity['name']
            newpath = '/'.join(newname.split('/')[:-1])
            validpath = False
            if len(newname.split('/')) < 2:
                raise CommandException(_("Please include a volume in the dataset's path"))
            for dataset in self.parent.entity['datasets']:
                if newpath in dataset['name']:
                    validpath = True
                    break
            if not validpath:
                raise CommandException(_(
                    "{0} is not a proper target for creating a new dataset on").format(newname))

            self.context.submit_task(
                'volume.dataset.create',
                self.parent.entity['name'],
                this.entity['name'],
                this.entity['type'],
                exclude(this.entity, 'name', 'type'),
                callback=lambda s: post_save(this, s)
            )
            return

        self.context.submit_task(
            'volume.dataset.update',
            self.parent.entity['name'],
            this.entity['name'],
            this.get_diff(),
            callback=lambda s: post_save(this, s)
        )


@description("Snapshots")
class SnapshotsNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(SnapshotsNamespace, self).__init__(name, context)
        self.parent = parent
        self.query_call = 'volumes.snapshots.query'
        self.primary_key_name = 'name'
        self.required_props = ['name', 'dataset']
        self.extra_query_params = [
            ('pool', '=', self.parent.name)
        ]

        self.skeleton_entity = {
            'recursive': False
        }

        self.add_property(
            descr='Snapshot name',
            name='name',
            get='id',
            set='id',
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

        self.primary_key = self.get_mapping('name')

    def save(self, this, new=False):
        if not new:
            raise CommandException('wut?')

        self.context.submit_task(
            'volume.snapshot.create',
            self.parent.name,
            this.entity['dataset'],
            this.entity['id'],
            this.entity['recursive'],
            callback=lambda s: post_save(this, s)
        )

    def delete(self, name):
        entity = self.get_one(name)
        self.context.submit_task(
            'volume.snapshot.delete',
            self.parent.name,
            entity['dataset'],
            entity['name']
        )


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

@description("Creates new volume")
class CreateVolumeCommand(Command):
    """
    Usage: create <name> type=<type> disks=<disks>

    Example: create tank disks=ada1,ada2
             create tank type=raidz2 disks=ada1,ada2,ada3,ada4

    The types available for pool creation are: auto, disk, mirror, raidz1, raidz2 and raidz3
    The "auto" setting is used if a type is not specified.
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
        if volume_type not in VOLUME_TYPES:
            raise CommandException(_(
                "Invalid volume type {0}.  Should be one of: {1}".format(volume_type, VOLUME_TYPES)
            ))

        if 'disks' not in kwargs:
            raise CommandException(_("Please specify one or more disks using the disks property"))
        else:
            disks = kwargs.pop('disks').split(',')
        

        if len(disks) < DISKS_PER_TYPE[volume_type]:
            raise CommandException(_("Volume type {0} requires at least {1} disks".format(volume_type, DISKS_PER_TYPE)))
        if len(disks) > 1 and volume_type == 'disk':
            raise CommandException(_("Cannot create a volume of type disk with multiple disks"))

        ns = SingleItemNamespace(None, self.parent)
        ns.orig_entity = query.wrap(copy.deepcopy(self.parent.skeleton_entity))
        ns.entity = query.wrap(copy.deepcopy(self.parent.skeleton_entity))

        all_disks = [disk["path"] for disk in context.call_sync("disks.query")]
        available_disks = context.call_sync('volumes.get_available_disks')
        if 'alldisks' in disks:
            disks = available_disks
        else:
            for disk in disks:
                disk = correct_disk_path(disk)
                if disk not in all_disks:
                    raise CommandException(_("Disk {0} does not exist.".format(disk)))
                if disk not in available_disks:
                    raise CommandException(_("Disk {0} is not available.".format(disk)))

        if volume_type == 'auto':
            context.submit_task('volume.create_auto', name, 'zfs', disks)
        else:
            ns.entity['name'] = name
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

            self.parent.save(ns, new=True)

    def complete(self, context, tokens):
        return ['name=', 'type=', 'disks=']


@description("Manage volumes")
class VolumesNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
    class ShowTopologyCommand(Command):
        def run(self, context, args, kwargs, opargs):
            pass

    def __init__(self, name, context):
        super(VolumesNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.save_key_name = 'name'
        self.create_task = 'volume.create'
        self.update_task = 'volume.update'
        self.delete_task = 'volume.destroy'

        self.skeleton_entity = {
            'type': 'zfs',
            'topology': {
                'data': []
            }
        }

        self.primary_key_name = 'name'
        self.query_call = 'volumes.query'

        self.add_property(
            descr='Volume name',
            name='name',
            get='name',
            list=True)

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
            list=True)

        self.add_property(
            descr='Last scrub time',
            name='last_scrub_time',
            get='scan.end_time',
            set=None
        )

        self.add_property(
            descr='Last scrub errors',
            name='last_scrub_errors',
            get='scan.errors',
            set=None
        )

        self.primary_key = self.get_mapping('name')
        self.extra_commands = {
            'find': FindVolumesCommand(),
            'find_media': FindMediaCommand(),
            'import': ImportVolumeCommand(),
            'detach': DetachVolumeCommand(),
        }

        self.entity_commands = lambda this: {
            'show_topology': ShowTopologyCommand(this),
            'show_disks': ShowDisksCommand(this),
            'scrub': ScrubCommand(this),
            'add_vdev': AddVdevCommand(this),
            'delete_vdev': DeleteVdevCommand(this),
            'offline': OfflineVdevCommand(this),
            'online': OnlineVdevCommand(this),
            'extend_vdev': ExtendVdevCommand(this)
        }

        self.entity_namespaces = lambda this: [
            DatasetsNamespace('dataset', self.context, this),
            SnapshotsNamespace('snapshot', self.context, this)
        ]

    def commands(self):
        cmds = super(VolumesNamespace, self).commands()
        cmds.update({'create': CreateVolumeCommand(self)})
        return cmds


def _init(context):
    context.attach_namespace('/', VolumesNamespace('volume', context))
