#
# Copyright 2015 iXsystems, Inc.
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
    EntityNamespace, Command, EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, description
)
from freenas.cli.output import ValueType
from freenas.cli.utils import TaskPromise


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Dismisses the current alert")
class DismissAlertCommand(Command):
    """
    Usage: dismiss

    Examples:
        dismiss

    Dismisses the current alert
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        alert_id = self.parent.entity['id']
        context.call_sync(
            'alert.dismiss',
            alert_id)
        curr_ns = context.ml.path[-1]
        if curr_ns.get_name() == alert_id and isinstance(curr_ns.parent, AlertNamespace):
            context.ml.cd_up()


@description("Dismisses all alerts at once")
class DismissAllAlertsCommand(Command):
    """
    Usage: dismiss_all

    Examples:
        dismiss_all

    Dismisses all alerts at once
    """
    def run(self, context, args, kwargs, opargs):
        context.call_sync('alert.dismiss_all')


@description("Sends user-defined alert")
class SendAlertCommand(Command):
    """
    Usage: send <message> [priority=INFO|WARNING|CRITICAL]

    Examples:
        send "@everyone our system will go down on Friday, the 13th at noon" priority=WARNING

    Sends user-defined alert
    """
    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task('alert.send', args[0], kwargs.get('priority'))
        return TaskPromise(context, tid)


@description("Set predicates for alert filter")
class SetPredicateCommand(Command):
    """
    Usage: predicate <property> <op> <value> ...

    Examples:
        predicate severity>WARNING
        predicate active==yes

    Sets predicate for alert filter.
    Properties can be one of [class|type|subtype|target|description|severity|active|dismissed]
    Op (operator) can be one of [==, !=, <=, >=, >, <, ~]
    Value is either a string, integer, or boolean
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        self.parent.entity['predicates'].clear()

        for l, o, r in opargs:
            self.parent.entity['predicates'].append({
                'property': l,
                'operator': o,
                'value': r
            })

        self.parent.save()


@description("List or dismiss system alerts")
class AlertNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The alert namespace provides commands for listing and dismissing
    system alerts.
    """
    def __init__(self, name, context):
        super(AlertNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'alert'
        self.primary_key_name = 'id'
        self.extra_query_params = [('active', '=', True)]
        self.allow_edit = False
        self.allow_create = False
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists alerts, optionally doing filtering and sorting.

            Examples:
                show
                show | search severity == WARNING
                show | sort id""")

        self.add_property(
            descr='ID',
            name='id',
            get='id',
            set=None,
            list=True,
            usage=_("Alert ID (read only)")
        )

        self.add_property(
            descr='Timestamp',
            name='timestamp',
            get='created_at',
            set=None,
            list=True,
            type=ValueType.TIME,
            usage=_("The time at which the alert was created (read only)")
        )

        self.add_property(
            descr='Severity',
            name='severity',
            get='severity',
            list=True,
            set=None,
            usage=_("Specifies the severity level of the alert (read only)")
        )

        self.add_property(
            descr='Message',
            name='description',
            get='description',
            list=True,
            set=None,
            usage=_("Description of this alert (read only)")
        )

        self.add_property(
            descr='Dismissed',
            name='dismissed',
            get='dismissed',
            list=True,
            type=ValueType.BOOLEAN,
            usage=_("Flag that controls whether the alert is dismissed")
        )

        self.primary_key = self.get_mapping('id')

        self.entity_commands = lambda this: {
            'dismiss': DismissAlertCommand(this),
        }

        self.extra_commands = {
            'send': SendAlertCommand(),
            'dismiss_all': DismissAllAlertsCommand()
        }

    def namespaces(self):
        yield AlertFilterNamespace('filter', self.context)
        for ns in super(AlertNamespace, self).namespaces():
            yield ns

    def serialize(self):
        raise NotImplementedError()


class AlertFilterNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(AlertFilterNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'alert.filter'
        self.create_task = 'alert.filter.create'
        self.update_task = 'alert.filter.update'
        self.delete_task = 'alert.filter.delete'
        self.skeleton_entity = {
            'predicates': [],
            'parameters': {
                '%type': 'alert-emitter-email'
            }
        }

        self.add_property(
            descr='Name',
            name='name',
            get='id',
            list=True,
            usage=_("Alert Filter name")
        )

        self.add_property(
            descr='Emitter',
            name='emitter',
            get='emitter',
            list=True,
            enum=['EMAIL'],
            usage=_("Alert Filter's method of notification (currently only EMAIL is allowed)")
        )

        self.add_property(
            descr='Destination e-mail addresses',
            name='email',
            get='parameters.addresses',
            type=ValueType.SET,
            condition=lambda o: o.get('emitter') == 'EMAIL',
            usgae=_("Destination email address(es) if EMAIL is the chose notification (emitter) type")
        )

        self.add_property(
            descr='Predicates',
            name='predicates',
            get=self.get_predicates,
            type=ValueType.ARRAY,
            usage=_("Lists this Alert Filter's predicates")
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda this: {
            'predicate': SetPredicateCommand(this)
        }

    def get_predicates(self, obj):
        return ['{property} {operator} {value}'.format(**v) for v in obj['predicates']]


def _init(context):
    context.attach_namespace('/', AlertNamespace('alert', context))
