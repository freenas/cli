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
from freenas.cli.namespace import EntityNamespace, Command, EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin
from freenas.cli.namespace import description
from freenas.cli.complete import RpcComplete, EnumComplete
from freenas.cli.output import ValueType
from freenas.cli.utils import EntityPromise, get_item_stub, post_save


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
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        ns = get_item_stub(context, self.parent, None)
        tid = context.submit_task(
            'alert.send',
            args[0],
            kwargs.get('priority', 'WARNING'),
            callback=lambda s, t: post_save(ns, s, t)
        )

        return EntityPromise(context, tid, ns)

    def complete(self, context, **kwargs):
        return [EnumComplete('priority=', ('INFO', 'WARNING', 'CRITICAL'))]


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
            'send': SendAlertCommand(self),
            'dismiss_all': DismissAllAlertsCommand()
        }

    def namespaces(self):
        yield AlertFilterNamespace('filter', self.context)
        yield AlertEmitterNamespace('emitter', self.context)
        for ns in super(AlertNamespace, self).namespaces():
            yield ns

    def serialize(self):
        raise NotImplementedError()


class AlertFilterNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(AlertFilterNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'alert.filter'
        self.primary_key_name = 'index'
        self.default_sort = 'index'
        self.create_task = 'alert.filter.create'
        self.update_task = 'alert.filter.update'
        self.delete_task = 'alert.filter.delete'
        self.required_props = ['emitter']
        self.skeleton_entity = {
            'predicates': [],
            'parameters': {
                '%type': 'alert-emitter-email'
            }
        }

        self.add_property(
            descr='Index',
            name='index',
            get='index',
            list=True,
            type=ValueType.NUMBER,
            usage=_("Alert filter index")
        )

        self.add_property(
            descr='Class',
            name='class',
            get='clazz',
            list=True,
            complete=RpcComplete('class=', 'alert.get_alert_classes'),
            usage=_("Alert class to be matched")
        )

        self.add_property(
            descr='Emitter',
            name='emitter',
            get='emitter',
            list=True,
            enum=['email', 'pushbullet'],
            usage=_("Alert Filter's method of notification")
        )

        self.add_property(
            descr='Destination e-mail addresses',
            name='email',
            get='parameters.to',
            type=ValueType.SET,
            condition=lambda o: o.get('emitter') == 'email',
            usgae=_("Destination email address(es) if email is the chose notification (emitter) type")
        )

        self.add_property(
            descr='Predicates',
            name='predicates',
            get=self.get_predicates,
            type=ValueType.ARRAY,
            usage=_("Lists this Alert Filter's predicates")
        )

        self.primary_key = self.get_mapping('index')
        self.entity_commands = lambda this: {
            'predicate': SetPredicateCommand(this)
        }

    def get_predicates(self, obj):
        return ['{property} {operator} {value}'.format(**v) for v in obj['predicates']]


class AlertEmitterNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(AlertEmitterNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'alert.emitter'
        self.primary_key_name = 'name'
        self.update_task = 'alert.emitter.update'
        self.allow_create = False
        self.allow_delete = False

        self.add_property(
            descr='Emitter name',
            name='name',
            get='name',
            set=None
        )

        self.add_property(
            descr='Email address',
            name='email',
            usage=_("""\
            Use set or edit to set the from email address to be
            used when sending email notifications. When using set,
            enclose the email address between double quotes."""),
            get='config.from_address',
            condition=lambda o: o.get('name') == 'email',
            list=False
        )

        self.add_property(
            descr='Email server',
            name='server',
            usage=_("""\
            Use set or edit to set the hostname or IP address of
            the SMTP server. When using set, enclose the value
            between double quotes."""),
            get='config.server',
            condition=lambda o: o.get('name') == 'email',
            list=False
        )

        self.add_property(
            descr='SMTP port',
            name='port',
            usage=_("""\
            Use set or edit to set the number of the SMTP port.
            Typically set to 25, 465 (secure SMTP), or 587
            (submission)."""),
            get='config.port',
            type=ValueType.NUMBER,
            condition=lambda o: o.get('name') == 'email',
            list=False
        )

        self.add_property(
            descr='Authentication required',
            name='auth',
            usage=_("""\
            Can be set to yes or no. When set to yes,
            enables SMTP AUTH using PLAIN SASL and requires both
            'username' and 'password' to be set."""),
            get='config.auth',
            type=ValueType.BOOLEAN,
            condition=lambda o: o.get('name') == 'email',
            list=False
        )

        self.add_property(
            descr='Encryption type',
            name='encryption',
            usage=_("""\
            Use set or edit to set to PLAIN (no encryption),
            TLS, or SSL.."""),
            get='config.encryption',
            enum=['PLAIN', 'TLS', 'SSL'],
            condition=lambda o: o.get('name') == 'email',
            list=False
        )

        self.add_property(
            descr='Username for Authentication',
            name='username',
            usage=_("""\
            Use set or edit to set the username used by
            SMTP authentication. Requires 'auth' to be set
            to yes."""),
            get='config.user',
            condition=lambda o: o.get('name') == 'email',
            list=False
        )

        self.add_property(
            descr='Password for Authentication',
            name='password',
            usage=_("""\
            Use set to set the password used by
            SMTP authentication. Requires 'auth' to be set
            to yes. For security reasons, the password is
            not displayed by get or edit."""),
            type=ValueType.PASSWORD,
            condition=lambda o: o.get('name') == 'email',
            get='config.password',
            list=False
        )

        self.add_property(
            descr='Pushbullet API key',
            name='api_key',
            get='config.api_key',
            condition=lambda o: o.get('name') == 'pushbullet',
            list=False
        )

        self.primary_key = self.get_mapping('name')


def _init(context):
    context.attach_namespace('/', AlertNamespace('alert', context))
