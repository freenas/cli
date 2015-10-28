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
import icu
import inspect
from namespace import (
    EntityNamespace, Command, CommandException,
    RpcBasedLoadMixin, TaskBasedSaveMixin, description
    )
from output import Table, ValueType, output_tree, output_msg
from utils import post_save, iterate_vdevs
from fnutils import first_or_default, exclude


t = icu.Transliterator.createInstance("Any-Accents", icu.UTransDirection.FORWARD)
_ = t.transliterate


@description("Adds new vdev to volume")
class AddVdevCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        entity = self.parent.entity
        typ = kwargs.pop('type')

        if typ not in ('stripe', 'mirror', 'cache', 'log', 'raidz1', 'raidz2', 'raidz3'):
            raise CommandException(_("Invalid vdev type"))

        if typ == 'stripe':
            if len(args) != 1:
                raise CommandException(_("Stripe vdev consist of single disk"))

            entity['topology']['data'].append({
                'type': 'disk',
                'path': args[0]
            })

        if typ == 'mirror':
            if len(args) < 2:
                raise CommandException(_("Mirrored vdev requires at least two disks"))

            entity['topology']['data'].append({
                'type': 'mirror',
                'children': [{'type': 'disk', 'path': x} for x in args]
            })

        if typ == 'cache':
            if 'cache' not in entity:
                entity['topology']['cache'] = []

            entity['topology']['cache'].append({
                'type': 'disk',
                'path': args[0]
            })

        if typ == 'log':
            if len(args) != 1:
                raise CommandException(_("Log vdevs cannot be mirrored"))

            if 'log' not in entity:
                entity['topology']['log'] = []

            entity['topology']['log'].append({
                'type': 'disk',
                'path': args[0]
            })

        if typ.startswith('raidz'):
            entity['topology']['data'].append({
                'type': typ,
                'path': [{'type': 'disk', 'path': x} for x in args]
            })


@description("Removes vdev from volume")
class DeleteVdevCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if self.parent.saved:
            raise CommandException('Cannot delete vdev from existing volume')


@description("Creates new volume in simple way")
class VolumeCreateCommand(Command):
    """
    Usage: create_auto <volume> <disk> [...]
           create_auto <volume> alldisks

    Examples: create_auto tank ada1 ada2
              create_auto tank alldisks

    Creates a new volume in a simple way.
    """
    def run(self, context, args, kwargs, opargs):
        if not args:
            output_msg("create_auto requires more arguments.\n" +
                       inspect.getdoc(self))
            return
        name = args.pop(0)
        disks = args
        if len(disks) == 0:
            output_msg("create_auto requires more arguments.\n" +
                       inspect.getdoc(self))
            return

        # The all_disks below is a temporary fix, use this after "select" is working
        # all_disks = context.call_sync('disks.query', [], {"select":"path"})
        all_disks = [disk["path"] for disk in context.call_sync("disks.query")]
        available_disks = context.call_sync('volumes.get_available_disks')
        if 'alldisks' in disks:
            disks = available_disks
        else:
            for disk in disks:
                if not re.match("^\/dev\/", disk):
                    disk = "/dev/" + disk
                if disk not in all_disks:
                    output_msg("Disk " + disk + " does not exist.")
                    return
                if disk not in available_disks:
                    output_msg("Disk " + disk + " is not usable.")
                    return

        context.submit_task('volume.create_auto', name, 'zfs', disks)


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
            list=False)

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
            'create_auto': VolumeCreateCommand(),
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
            'delete_vdev': DeleteVdevCommand(this)
        }

        self.entity_namespaces = lambda this: [
            DatasetsNamespace('dataset', self.context, this),
            SnapshotsNamespace('snapshot', self.context, this)
        ]


def _init(context):
    context.attach_namespace('/', VolumesNamespace('volume', context))
