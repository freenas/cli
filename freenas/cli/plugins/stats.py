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
from freenas.cli.namespace import (
    Namespace, EntityNamespace, TaskBasedSaveMixin,
    RpcBasedLoadMixin, description
)
from freenas.cli.output import ValueType

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class StatisticNamespaceBase(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(StatisticNamespaceBase, self).__init__(name, context)

        self.primary_key_name = 'short_name'
        self.save_key_name = 'name'
        self.allow_create = False
        self.update_task = 'stat.alert_update'

        self.add_property(
            descr='Name',
            name='name',
            usage=_("""\
            Read-only name assigned by the operating system."""),
            get='short_name',
            usersetable=False,
            list=True)

        self.add_property(
            descr='Value',
            name='value',
            usage=_("""\
            Read-only value assigned by the operating system."""),
            get='normalized_value',
            type=ValueType.NUMBER,
            usersetable=False,
            list=True)

        self.add_property(
            descr='Unit',
            name='unit',
            usage=_("""\
            Read-only unit name assigned by the operating system."""),
            get='unit',
            usersetable=False,
            list=True)

        self.add_property(
            descr='Value too high alert level',
            name='alert_high',
            get='alerts.normalized_alert_high',
            set='alerts.alert_high',
            list=False,
            type=ValueType.NUMBER)

        self.add_property(
            descr='Value too high alert activity',
            name='alert_high_enabled',
            get='alerts.alert_high_enabled',
            set='alerts.alert_high_enabled',
            list=False,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Value too low alert level',
            name='alert_low',
            get='alerts.normalized_alert_low',
            set='alerts.alert_low',
            list=False,
            type=ValueType.NUMBER)

        self.add_property(
            descr='Value too low alert activity',
            name='alert_low_enabled',
            get='alerts.alert_low_enabled',
            set='alerts.alert_low_enabled',
            list=False,
            type=ValueType.BOOLEAN)

        self.primary_key = self.get_mapping('name')


@description(_("View CPUs statistics and set alert levels"))
class CpuStatisticNamespace(StatisticNamespaceBase):
    """
    The cpu statistic namespace provides ability to view values
    and set alert levels on related statistics.
    """
    def __init__(self, name, context):
        super(CpuStatisticNamespace, self).__init__(name, context)

        self.query_call = 'stat.cpu.query'


@description(_("View disks statistics and set alert levels"))
class DiskStatisticNamespace(StatisticNamespaceBase):
    """
    The disk statistic namespace provides ability to view values
    and set alert levels on related statistics.
    """
    def __init__(self, name, context):
        super(DiskStatisticNamespace, self).__init__(name, context)

        self.query_call = 'stat.disk.query'


@description(_("View network statistics and set alert levels"))
class NetworkStatisticNamespace(StatisticNamespaceBase):
    """
    The network statistic namespace provides ability to view values
    and set alert levels on related statistics.
    """
    def __init__(self, name, context):
        super(NetworkStatisticNamespace, self).__init__(name, context)

        self.query_call = 'stat.network.query'


@description(_("View system statistics and set alert levels"))
class SystemStatisticNamespace(StatisticNamespaceBase):
    """
    The system statistic namespace provides ability to view values
    and set alert levels on related statistics.
    """
    def __init__(self, name, context):
        super(SystemStatisticNamespace, self).__init__(name, context)

        self.query_call = 'stat.system.query'


@description(_("View system statistics and set alert levels"))
class StatisticNamespace(Namespace):
    """
    The statistic namespace is used to view system statistics
    and to configure which threshholds result in an alert.
    """
    def __init__(self, name, context):
        super(StatisticNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            CpuStatisticNamespace('cpu', self.context),
            DiskStatisticNamespace('disk', self.context),
            NetworkStatisticNamespace('network', self.context),
            SystemStatisticNamespace('system', self.context)
        ]


def _init(context):
    context.attach_namespace('/', StatisticNamespace('statistic', context))
