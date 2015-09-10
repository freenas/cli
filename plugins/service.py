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
from namespace import ConfigNamespace, EntityNamespace, RpcBasedLoadMixin, Command, description
from output import ValueType


@description("Start/stop/restart/reload a service")
class ServiceManageCommand(Command):
    """
    Usage: start, stop, restart, reload

    start - starts a service
    stop - stops a service
    restart - restarts a service
    reload - gracefully restarts a service
    """
    def __init__(self, parent, action):
        self.parent = parent
        self.action = action

    @property
    def description(self):
        return '{0}s service'.format(self.action.title())

    def run(self, context, args, kwargs, opargs):
        context.submit_task('service.manage', self.parent.primary_key, self.action)


@description("Configure and manage services")
class ServicesNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(ServicesNamespace, self).__init__(name, context)
        self.query_call = 'services.query'

        self.primary_key_name = 'name'
        self.add_property(
            descr='Service name',
            name='name',
            get='name',
            set=None,
            list=True
        )

        self.add_property(
            descr='State',
            name='state',
            get='state',
            set=None,
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.allow_edit = False
        self.allow_creation = False
        self.entity_namespaces = lambda this: [
            ServiceConfigNamespace('config', context, this)
        ]
        self.entity_commands = lambda this: {
            'start': ServiceManageCommand(this, 'start'),
            'stop': ServiceManageCommand(this, 'stop'),
            'restart': ServiceManageCommand(this, 'restart'),
            'reload': ServiceManageCommand(this, 'reload')
        }


class ServiceConfigNamespace(ConfigNamespace):
    def __init__(self, name, context, parent):
        super(ServiceConfigNamespace, self).__init__(name, context)
        self.parent = parent

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.get_properties(parent.name)

    def load(self):
        self.entity = self.context.call_sync('services.get_service_config', self.parent.entity['name'])
        self.orig_entity = copy.deepcopy(self.entity)

    def save(self):
        def post_save():
            self.modified = False
            
        return self.context.submit_task(
            'service.configure',
            self.parent.entity['name'],
            self.get_diff(),
            callback=lambda s: post_save())

    def get_properties(self, name):
        if name == "sshd":
            self.add_property(
                descr='sftp log facility',
                name='sftp_log_facility',
                get='sftp_log_facility',
                type=ValueType.STRING
            )
            self.add_property(
                descr='Allow public key authentication',
                name='allow_pubkey_auth',
                get='allow_pubkey_auth',
                type=ValueType.BOOLEAN
            )
            self.add_property(
                descr='Enable compression',
                name='compression',
                get='compression',
                type=ValueType.BOOLEAN
            )
            self.add_property(
                descr='Allow password authentication',
                name='allow_password_auth',
                get='allow_password_auth',
                type=ValueType.BOOLEAN
            )
            self.add_property(
                descr='Allow port forwarding',
                name='allow_port_forwarding',
                get='allow_port_forwarding',
                type=ValueType.BOOLEAN
            )
            self.add_property(
                descr='Permit root login',
                name='permit_root_login',
                get='permit_root_login',
                type=ValueType.BOOLEAN
            )
            self.add_property(
                descr='sftp log level',
                name='sftp_log_level',
                get='sftp_log_level',
                type=ValueType.STRING
            )
            self.add_property(
                descr='Port',
                name='port',
                get='port',
                type=ValueType.NUMBER
            )
        elif name == "nginx":
            self.add_property(
                descr='Redirect http to https',
                name='http.redirect_https',
                get='http.redirect_https',
                type=ValueType.BOOLEAN
            )
            self.add_property(
                descr='Enable http',
                name='http.enable',
                get='http.enable',
                type=ValueType.BOOLEAN
            )
            self.add_property(
                descr='http port',
                name='http.port',
                get='http.port',
                type=ValueType.NUMBER
            )
            self.add_property(
                descr='Enable https',
                name='https.enable',
                get='https.enable',
                type=ValueType.BOOLEAN
            )
            self.add_property(
                descr='https port',
                name='https.port',
                get='https.port',
                type=ValueType.NUMBER
            )
            self.add_property(
                descr='Https certificate',
                name='https.certificate',
                get='https.certificate',
                type=ValueType.STRING
            )
            self.add_property(
                descr='Listen on IP',
                name='listen',
                get='listen',
                list=True,
                type=ValueType.SET
            )
        elif name == "ftp":
            self.add_property(
                descr='ftp port',
                name='port',
                get='port',
                type=ValueType.NUMBER
            )
        elif name == "afp":
            self.add_property(
                descr='Share Home Directory',
                name='homedir_enable',
                get='homedir_enable',
                type=ValueType.BOOLEAN
                )
            self.add_property(
                descr='Home Directory Path',
                name='homedir_path',
                get='homedir_path',
                type=ValueType.STRING
                )
            self.add_property(
                descr='Home Directory Name',
                name='homedir_name',
                get='homedir_name',
                type=ValueType.STRING
                )
            self.add_property(
                descr='Auxiliary Parameters',
                name='auxiliary',
                get='auxiliary',
                type=ValueType.STRING
                )
            self.add_property(
                descr='Connections limit',
                name='connections_limit',
                get='connections_limit',
                type=ValueType.NUMBER
                )
            self.add_property(
                descr='Guest user',
                name='guest_user',
                get='guest_user',
                type=ValueType.STRING
                )
            self.add_property(
                descr='Enable guest user',
                name='guest_enable',
                get='guest_enable',
                type=ValueType.BOOLEAN
                )
            self.add_property(
                descr='Bind Addresses',
                name='bind_addresses',
                get='bind_addresses',
                list=True,
                type=ValueType.SET
                )
            self.add_property(
                descr='Database Path',
                name='dbpath',
                get='dbpath',
                type=ValueType.STRING
                )


def _init(context):
    context.attach_namespace('/', ServicesNamespace('services', context))
