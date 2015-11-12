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

from namespace import (
    Command,
    IndexCommand,
    Namespace,
    ConfigNamespace,
    EntityNamespace,
    RpcBasedLoadMixin,
    TaskBasedSaveMixin,
    description
)

from output import (
    output_msg,
    ValueType
)

from utils import post_save

@description("Configure and manage directory service")
class DirectoryServiceNamespace(Namespace):
    def __init__(self, name, context):
        super(DirectoryServiceNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            ActiveDirectoryNamespace('activedirectory', self.context),
            LDAPDirectoryNamespace('ldap', self.context)
        ]

class DirectoryServiceCommandBase(Command):
    def __init__(self, parent, enable=True):
        self.parent = parent
        self.enable = enable

    def run(self, context, args, kwargs, opargs):
        pass


@description("Enables a directory service")
class DirectoryServiceEnableCommand(DirectoryServiceCommandBase):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        context.submit_task('directoryservice.enable', ds_id,
            callback=lambda s: post_save(self.parent, s))


@description("Disables a directory service")
class DirectoryServiceDisableCommand(DirectoryServiceCommandBase):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        context.submit_task('directoryservice.disable', ds_id,
            callback=lambda s: post_save(self.parent, s))


@description("Displays cached domain controllers")
class DirectoryServiceShowDCCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        dcs = context.call_sync('directoryservices.get', ds_id, 'dcs')
        if dcs:
            for dc in dcs:
                output_msg(dc)


@description("Displays cached global catalogs")
class DirectoryServiceShowGCCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        gcs = context.call_sync('directoryservices.get', ds_id, 'gcs')
        if gcs:
            for gc in gcs:
                output_msg(gc)


@description("Displays cached Kerberos KDC servers")
class DirectoryServiceShowKDCCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        kdcs = context.call_sync('directoryservices.get', ds_id, 'kdcs')
        if kdcs:
            for kdc in kdcs:
                output_msg(kdc)


@description("Configures hostname for directory service")
class DirectoryServiceConfigureHostnameCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'hostname', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Configures hosts file for directory service")
class DirectoryServiceConfigureHostsCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'hosts', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Configures Kerberos for directory service")
class DirectoryServiceConfigureKerberosCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'kerberos', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Configures nsswitch for directory service")
class DirectoryServiceConfigureNSSWitchCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'nsswitch', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Configures openldap for directory service")
class DirectoryServiceConfigureOpenLDAPCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'openldap', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Configures nssldap for directory service")
class DirectoryServiceConfigureNSSLDAPCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'nssldap', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Configures sssd for directory service")
class DirectoryServiceConfigureSSSDCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'sssd', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Configures samba for directory service")
class DirectoryServiceConfigureSambaCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'samba', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Configures pam for directory service")
class DirectoryServiceConfigurePAMCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'pam', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Configures the system for Active Directory")
class DirectoryServiceConfigureActiveDirectoryCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        args = [ ds_id, 'activedirectory', self.enable ]

        context.submit_task('directoryservice.configure', args,
            callback=lambda s: post_save(self.parent, s))


@description("Obtains a Kerberos ticket")
class DirectoryServiceGetKerberosTicketCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        context.submit_task('directoryservice.kerberosticket', ds_id,
            callback=lambda s: post_save(self.parent, s))


@description("Joins an Active Directory domain")
class DirectoryServiceJoinActiveDirectoryCommand(DirectoryServiceCommandBase):
    def run(self, context, args, kwargs, opargs):
        ds_id = self.parent.entity['id']
        context.submit_task('directoryservice.join', ds_id,
            callback=lambda s: post_save(self.parent, s))


class BaseDirectoryServiceNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, type_name, context):
        super(BaseDirectoryServiceNamespace, self).__init__(name, context)

        self.type_name = type_name
        self.query_call = 'directoryservices.query'
        self.create_task = 'directoryservice.create'
        self.update_task = 'directoryservice.update'
        self.delete_task = 'directoryservice.delete'
        self.required_props = ['name']

        self.skeleton_entity = {
            'type': type_name,
            'properties': {}
        }

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.primary_key_name = 'name'
        self.save_key_name = 'name'

    def query(self, params, options):
        params.append(('type', '=', self.type_name))
        return self.context.call_sync('directoryservices.query', params)


@description("Active Directory settings")
class ActiveDirectoryNamespace(BaseDirectoryServiceNamespace):
    def __init__(self, name, context):
        super(ActiveDirectoryNamespace, self).__init__(name, 'activedirectory', context)
        self.config_call = "activedirectory.get_config"

        self.add_property(
            descr='Domain',
            name='domain',
            get='domain',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Bind Name',
            name='binddn',
            get='binddn',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Bind Password',
            name='bindpw',
            get='bindpw',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Domain Controller',
            name='dchost',
            get='dchost',
            type=ValueType.STRING,
            list=False
        )

        self.add_property(
            descr='Global Catalog',
            name='gchost',
            get='gchost',
            type=ValueType.STRING,
            list=False
        )

        self.add_property(
            descr='Kerberos KDC',
            name='kdchost',
            get='kdchost',
            type=ValueType.STRING,
            list=False
        )

        self.add_property(
            descr='Site Name',
            name='site',
            get='site',
            type=ValueType.STRING,
            list=False
        )

        self.primary_key = self.get_mapping('name')
        self.primary_key_name = 'name'
        self.save_key_name = 'name'

        # XXX Most of these are for debugging, remove when 
        # XXX everything works
        # XXX Perhaps they can be conditional ?
        self.entity_commands = lambda this: {
            'enable': DirectoryServiceEnableCommand(this),
            'disable': DirectoryServiceDisableCommand(this),
            'show_dcs': DirectoryServiceShowDCCommand(this),
            'show_gcs': DirectoryServiceShowGCCommand(this),
            'show_kdcs': DirectoryServiceShowKDCCommand(this),
        }
"""
            'configure_hostname': DirectoryServiceConfigureHostnameCommand(this, True),
            'unconfigure_hostname': DirectoryServiceConfigureHostnameCommand(this, False),
            'configure_hosts': DirectoryServiceConfigureHostsCommand(this, True),
            'unconfigure_hosts': DirectoryServiceConfigureHostsCommand(this, False),
            'configure_kerberos': DirectoryServiceConfigureKerberosCommand(this, True),
            'unconfigure_kerberos': DirectoryServiceConfigureKerberosCommand(this, False),
            'configure_nsswitch': DirectoryServiceConfigureNSSWitchCommand(this, True),
            'unconfigure_nsswitch': DirectoryServiceConfigureNSSWitchCommand(this, False),
            'configure_openldap': DirectoryServiceConfigureOpenLDAPCommand(this, True),
            'unconfigure_openldap': DirectoryServiceConfigureOpenLDAPCommand(this, False),
            'configure_nssldap': DirectoryServiceConfigureNSSLDAPCommand(this, True),
            'unconfigure_nssldap': DirectoryServiceConfigureNSSLDAPCommand(this, False),
            'configure_sssd': DirectoryServiceConfigureSSSDCommand(this, True),
            'unconfigure_sssd': DirectoryServiceConfigureSSSDCommand(this, False),
            'configure_samba': DirectoryServiceConfigureSambaCommand(this, True),
            'unconfigure_samba': DirectoryServiceConfigureSambaCommand(this, False),
            'configure_pam': DirectoryServiceConfigurePAMCommand(this, True),
            'unconfigure_pam': DirectoryServiceConfigurePAMCommand(this, False),
            'configure_activedirectory': DirectoryServiceConfigureActiveDirectoryCommand(this, True),
            'unconfigure_activedirectory': DirectoryServiceConfigureActiveDirectoryCommand(this, False),
            'get_kerberos_ticket': DirectoryServiceGetKerberosTicketCommand(this),
            'join_activedirectory': DirectoryServiceJoinActiveDirectoryCommand(this),
        }
"""


@description("LDAP directory settings")
class LDAPDirectoryNamespace(BaseDirectoryServiceNamespace):
    def __init__(self, name, context):
        super(LDAPDirectoryNamespace, self).__init__(name, 'ldap', context)
        self.config_call = "ldap.get_config"

        self.add_property(
            descr='Domain',
            name='domain',
            get='domain',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Bind Name',
            name='binddn',
            get='binddn',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Bind Password',
            name='bindpw',
            get='bindpw',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Host Name',
            name='host',
            get='host',
            type=ValueType.STRING,
            list=False
        )

        self.add_property(
            descr='Kerberos KDC',
            name='kdchost',
            get='kdchost',
            type=ValueType.STRING,
            list=False
        )

        self.primary_key = self.get_mapping('name')
        self.primary_key_name = 'name'
        self.save_key_name = 'name'

        self.entity_commands = lambda this: {
            'enable': DirectoryServiceEnableCommand(this),
            'disable': DirectoryServiceDisableCommand(this)
        }


def _init(context):
    context.attach_namespace('/', DirectoryServiceNamespace('directoryservice', context))
