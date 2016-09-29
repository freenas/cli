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
import os
from freenas.cli.namespace import (
    EntityNamespace, Command, EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, description
)
from freenas.cli.output import ValueType, Table
from freenas.cli.utils import TaskPromise
from freenas.utils import extend, query as q


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Provides information about installed disks")
class DisksNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """
    The disk namespace lists the disks recognized by the system.
    Type 'show' for more details about the disks.
    Type the disk's name to manage that disk and type
    'help properties' for help on the available properties.
    """
    def __init__(self, name, context):
        super(DisksNamespace, self).__init__(name, context)

        self.entity_subscriber_name = 'disk'
        self.primary_key_name = 'name'
        self.update_task = 'disk.update'
        self.extra_query_params = [
            ('online', '=', True)
        ]

        def get_enclosure(disk):
            enc_id = q.get(disk, 'status.enclosure')
            if not enc_id:
                return

            enclosure = context.entity_subscribers['disk.enclosure'].get(enc_id)
            if not enclosure:
                return

            return '{description} ({name})'.format(**enclosure)

        self.add_property(
            descr='Path',
            name='path',
            get='path',
            usage=_("""\
            Full path of disk device. Read-only value is
            assigned by operating system."""),
            set=None,
            list=True
        )

        self.add_property(
            descr='Name',
            name='name',
            get=lambda row: os.path.basename(row.get('path')),
            usage=_("""\
            Name of disk device. Read-only value is
            assigned by operating system."""),
            set=None,
            list=True
        )

        self.add_property(
            descr='Disk description',
            name='description',
            get='status.description',
            usage=_("""\
            Description of disk device. Read-only value is
            assigned by operating system."""),
            set=None,
            list=False
        )

        self.add_property(
            descr='Size',
            name='mediasize',
            get='mediasize',
            usage=_("""\
            Size of disk as reported by the operating
            system. This is a read-only value."""),
            set=None,
            list=True,
            type=ValueType.SIZE
        )

        self.add_property(
            descr='Serial number',
            name='serial',
            get='serial',
            set=None,
            usage=_("""\
            Serial number as reported by the device. This is
            a read-only value."""),
            list=False,
            type=ValueType.STRING
        )

        self.add_property(
            descr='Enclosure',
            name='enclosure',
            get=get_enclosure,
            set=None,
            usage=_("""\
            Name of enclosure containing the disk (if any). This is a read-only value."""),
            list=False,
            type=ValueType.STRING
        )

        self.add_property(
            descr='Online',
            name='online',
            get='online',
            set=None,
            usage=_("""\
            Indicates whether or not the device is online.
            This is a read-only value."""),
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Empty',
            name='empty',
            get='status.empty',
            set=None,
            usage=_("""\
            Indicates whether or not the device has been
            formatted. This is a read-only value."""),
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Allocation',
            name='allocation',
            get=self.get_allocation,
            set=None,
            usage=_("""\
            Indicates whether or not the device is being
            used for storage or for the boot device. This
            is a read-only value."""),
            list=True
        )

        self.add_property(
            descr='Standby mode',
            name='standby_mode',
            get='standby_mode',
            usage=_("""\
            Integer that indicates the time of inactivity
            (in minutes) before the drive enters standby
            mode in order to conserve energy. A value of 0
            disables standby mode."""),
            type=ValueType.NUMBER,
            list=False
        )

        self.add_property(
            descr='Power management mode',
            name='apm_mode',
            get='apm_mode',
            usage=_("""\
            Integer that indicates the power management mode
            as described in ataidle(8). A value of 0
            disables power management."""),
            type=ValueType.NUMBER,
            list=False
        )

        self.add_property(
            descr='Acoustic level',
            name='acoustic_level',
            get='acoustic_level',
            usage=_("""\
            Can be set on disks that understand AAM.
            Possible values are DISABLED, MINIMUM,
            MEDIUM, or MAXIMUM."""),
            type=ValueType.STRING,
            list=False
        )

        self.add_property(
            descr='SMART',
            name='smart',
            get='smart',
            usage=_("""\
            Values are yes or no. Can only be set to yes if
            the disk is S.M.A.R.T. capable."""),
            type=ValueType.BOOLEAN,
            list=False
        )

        self.add_property(
            descr='SMART status',
            name='status.smart_status',
            get='status.smart_status',
            list=True
        )

        self.add_property(
            descr='SMART options',
            name='smart_options',
            get='smart_options',
            usage=_("""\
            Additional options from smartctl(8). When
            setting options, place entire options string
            between double quotes and use a space to
            separate multiple options. Can only set options
            if the disk is S.M.A.R.T. capable."""),
            type=ValueType.STRING,
            list=False
        )

        self.primary_key = self.get_mapping('name')
        self.allow_create = False
        self.entity_commands = lambda this: {
            'format': FormatDiskCommand(this),
            'erase': EraseDiskCommand(this)
        }

    def query(self, params, options):
        ret = super(DisksNamespace, self).query(params, options)
        disks = [d['path'] for d in ret]
        allocations = self.context.call_sync('volume.get_disks_allocation', disks)

        return [extend(d, {
                'allocation': allocations.get(d['path']) if d['online'] else None
            }) for d in ret]

    def get_one(self, name):
        ret = self.context.entity_subscribers[self.entity_subscriber_name].query(
            ('name', '=', name), *self.extra_query_params,
            single=True
        )

        if not ret:
            return None

        ret['allocation'] = self.context.call_sync(
            'volume.get_disks_allocation',
            [ret['path']]
        ).get(ret['path'])

        return ret

    def get_allocation(self, entity):
        disp = entity.get('allocation')

        if disp is None:
            return 'unallocated'

        if disp['type'] == 'BOOT':
            return 'boot device'

        if disp['type'] == 'VOLUME':
            return 'part of volume {0}'.format(disp['name'])

        if disp['type'] == 'EXPORTED_VOLUME':
            return 'part of exported volume {0}'.format(disp['name'])

        return 'unknown'

    def namespaces(self, name=None):
        return list(super(DisksNamespace, self).namespaces()) + [
            EnclosureNamespace('enclosure', self.context)
        ]


class EnclosureNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(EnclosureNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'disk.enclosure'
        self.primary_key_name = 'name'
        self.allow_create = False
        self.allow_edit = False

        self.add_property(
            descr='Enclosure name',
            name='name',
            get='name',
            set=None,
            list=True
        )

        self.add_property(
            descr='Enclosure ID',
            name='id',
            get='id',
            set=None,
            list=True
        )

        self.add_property(
            descr='Description',
            name='description',
            get='description',
            set=None,
            list=True
        )

        self.add_property(
            descr='Status',
            name='status',
            get='status',
            set=None,
            list=True,
            type=ValueType.SET
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda this: {
            'devices': EnclosureDevicesCommand(this)
        }


@description("Shows enclosure contents")
class EnclosureDevicesCommand(Command):
    """
    Usage: devices
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        devices = sorted(self.parent.entity['devices'], key=lambda d: d['index'])
        return Table(devices, [
            Table.Column('Index', 'index', display_width_percentage=10),
            Table.Column('Disk name', 'disk_name', display_width_percentage=20),
            Table.Column('Slot description', 'name'),
            Table.Column('Slot status', 'status')
        ])



@description("Formats given disk")
class FormatDiskCommand(Command):
    """
    Usage: format

    Formats the current disk.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        fstype = kwargs.pop('fstype', 'freebsd-zfs')
        tid = context.submit_task('disk.format.gpt', self.parent.entity['id'], fstype)
        return TaskPromise(context, tid)


@description("Erases all data on disk safely")
class EraseDiskCommand(Command):
    """
    Usage: erase
           erase wipe=quick
           erase wipe=zeros
           erase wipe=random

    Erases the partitions from the current disk and optionally wipes it. This
    operation can only be performed if the disk is 'unallocated'.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        erase_data = str.upper(kwargs.pop('wipe', 'quick'))
        tid = context.submit_task('disk.erase', self.parent.entity['id'], erase_data)
        return TaskPromise(context, tid)


def _init(context):
    context.attach_namespace('/', DisksNamespace('disk', context))
    context.map_tasks('disk.*', DisksNamespace)
