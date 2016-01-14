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

import gettext
import os
from freenas.cli.namespace import (
    EntityNamespace, Command, EntitySubscriberBasedLoadMixin, description
)
from freenas.cli.output import ValueType
from freenas.cli.utils import post_save
from freenas.utils import extend


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Provides information about installed disks")
class DisksNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The disk namespace lists the disks recognized by the system.
    Type 'show' for more details about the disks.
    Type the disk's name to manage that disk and type
    'help properties' for help on the available properties.
    """
    def __init__(self, name, context):
        super(DisksNamespace, self).__init__(name, context)

        self.entity_subscriber_name = 'disk'
        self.extra_query_params = [
            ('online', '=', True)
        ]

        self.add_property(
            descr='Path',
            name='path',
            get='path',
            set=None,
            list=True
        )

        self.add_property(
            descr='Name',
            name='name',
            get=lambda row: os.path.basename(row.get('path')),
            usage=_("""\
            Full path of disk device. Read-only value as
            assigned by operating system."""),
            set=None,
            list=True
        )

        self.add_property(
            descr='Disk description',
            name='description',
            get='status.description',
            usage=_("""\
            Name of disk device. Read-only value as
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
            descr='Online',
            name='online',
            get='online',
            set=None,
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Empty',
            name='empty',
            get='status.empty',
            set=None,
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Allocation',
            name='allocation',
            get=self.get_allocation,
            set=None,
            list=True
        )

        self.add_property(
            descr='Standby mode',
            name='standby_mode',
            get='standby_mode',
            type=ValueType.NUMBER,
            list=False
        )

        self.add_property(
            descr='Power management mode',
            name='apm_mode',
            get='apm_mode',
            type=ValueType.NUMBER,
            list=False
        )

        self.add_property(
            descr='Acoustic level',
            name='acoustic_level',
            get='acoustic_level',
            type=ValueType.STRING,
            list=False
        )

        self.add_property(
            descr='SMART',
            name='smart',
            get='smart',
            type=ValueType.BOOLEAN,
            list=False
        )

        self.add_property(
            descr='SMART options',
            name='smart_options',
            get='smart_options',
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
            ('path', '=', os.path.join('/dev', name)), *self.extra_query_params,
            single=True
        )

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

        return 'unknown'

    def save(self, this, new=False):
        self.context.submit_task(
            'disk.configure',
            this.entity['id'],
            this.get_diff(),
            callback=lambda s: post_save(this, s))


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
        context.submit_task('disk.format.gpt', self.parent.entity['path'], fstype)


@description("Erases all data on disk safely")
class EraseDiskCommand(Command):
    """
    Usage: erase
           erase wipe=quick
           erase wipe=zeros
           erase wipe=random

    Erases the partitions from the current disk and optionally wipes it.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        erase_data = str.upper(kwargs.pop('wipe', 'quick'))
        context.submit_task('disk.erase', self.parent.entity['path'], erase_data)


def _init(context):
    context.attach_namespace('/', DisksNamespace('disk', context))
