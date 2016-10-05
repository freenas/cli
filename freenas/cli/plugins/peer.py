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
from datetime import datetime
from freenas.cli.namespace import (
    Command, CommandException, EntityNamespace, TaskBasedSaveMixin,
    EntitySubscriberBasedLoadMixin, BaseVariantMixin, description
)
from freenas.cli.complete import RpcComplete
from freenas.cli.output import ValueType, Sequence, Table
from freenas.utils import first_or_default, query as q

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description(_("Generate FreeNAS peer one-time authentication token"))
class FreeNASPeerGetAuthTokenCommand(Command):
    """
    Usage: create_token

    Example: create_token

    Creates an authentication token which is valid for 5 minutes.
    This token can be used on other FreeNAS machine to set up a FreeNAS peer.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        return Sequence(
            'One time authentication code:',
            context.call_sync('peer.freenas.create_auth_code')
        )


@description(_("Invalidate selected FreeNAS peer one-time authentication token"))
class FreeNASPeerInvalidateTokenCommand(Command):
    """
    Usage: invalidate_token token=<token>

    Example: invalidate_token token=123456
             invalidate_token 123456
             invalidate_token 12****
             invalidate_token 12

    Invalidates selected FreeNAS peer one-time authentication token.
    You have to enter at least two first digits of a valid token.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("Command invalidate_token requires more arguments."))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for invalidate_token."))

        if len(args) == 1 and not kwargs.get('token'):
            kwargs['token'] = args.pop(0)

        if 'token' not in kwargs:
            raise CommandException(_('Please specify a valid token'))
        else:
            token = str(kwargs.pop('token'))

        try:
            if token.index('*') < 2:
                raise CommandException(_('You have to enter at least first two digits of a valid token.'))
        except ValueError:
            pass

        match = first_or_default(
            lambda c: c['code'][:2] == token[:2],
            context.call_sync('peer.freenas.get_auth_codes')
        )
        if not match:
            return Sequence(
                'No matching code found. You might have entered wrong token, or it has already expired.'
            )
        else:
            if match['code'] == token:
                token = match

            context.call_sync('peer.freenas.invalidate_code', token)

    def complete(self, context, **kwargs):
        return [
            RpcComplete('token=', 'peer.freenas.get_auth_codes', lambda c: c['code'])
        ]


@description(_("List valid FreeNAS authentication tokens"))
class FreeNASPeerListTokensCommand(Command):
    """
    Usage: list_tokens

    Example: list_tokens

    Lists valid FreeNAS authentication tokens.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        codes = list(context.call_sync('peer.freenas.get_auth_codes'))
        for c in codes:
            remaining_time = c['expires_at'] - datetime.now()
            remaining_time = int(remaining_time.total_seconds())
            if remaining_time < 0:
                c['lifetime'] = 'Expired {0} seconds ago'.format(abs(remaining_time))
            else:
                c['lifetime'] = 'Expires in {0} seconds'.format(remaining_time)

        return Table(
            codes, [
                Table.Column('Token', 'code', ValueType.STRING),
                Table.Column('Lifetime', 'lifetime', ValueType.STRING)
            ]
        )


class BasePeerNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, type_name, context):
        super(BasePeerNamespace, self).__init__(name, context)

        self.context = context
        self.type_name = type_name
        self.entity_subscriber_name = 'peer'
        self.extra_query_params = [('type', '=', type_name)]


@description(_("Manage FreeNAS peers"))
class FreeNASPeerNamespaceMixin(BaseVariantMixin):
    def add_properties(self):
        super(FreeNASPeerNamespaceMixin, self).add_properties()

        self.add_property(
            descr='Port',
            name='freenas_port',
            get='credentials.port',
            list=False,
            type=ValueType.NUMBER,
            usersetable=False,
            usage=_('SSH port used to reach a FreeNAS peer.'),
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Public key',
            name='freenas_pubkey',
            get='credentials.pubkey',
            list=False,
            usersetable=False,
            usage=_('Public SSH key of a FreeNAS peer.'),
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Host key',
            name='freenas_hostkey',
            get='credentials.hostkey',
            list=False,
            usersetable=False,
            usage=_('SSH host key of a FreeNAS peer.'),
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Peer address',
            name='freenas_address',
            get='credentials.address',
            usersetable=False,
            createsetable=True,
            list=False,
            usage=_('Address of a FreeNAS peer.'),
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Username',
            name='freenas_username',
            get=None,
            set='0.username',
            create_arg=True,
            list=False,
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Password',
            name='freenas_password',
            get=None,
            set='0.password',
            create_arg=True,
            list=False,
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Token',
            name='freenas_token',
            get=None,
            set='0.auth_code',
            create_arg=True,
            list=False,
            type=ValueType.NUMBER,
            condition=lambda o: o['type'] == 'freenas'
        )

    def commands(self):
        cmds = super(FreeNASPeerNamespaceMixin, self).commands()
        cmds.update({
            'create_token': FreeNASPeerGetAuthTokenCommand(self),
            'invalidate_token': FreeNASPeerInvalidateTokenCommand(self),
            'list_tokens': FreeNASPeerListTokensCommand(self)
        })
        return cmds


@description(_("Manage SSH peers"))
class SSHPeerNamespaceMixin(BaseVariantMixin):
    def add_properties(self):
        super(SSHPeerNamespaceMixin, self).add_properties()

        self.add_property(
            descr='Peer address',
            name='ssh_address',
            get='credentials.address',
            list=False,
            usage=_('Address of a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Username',
            name='ssh_username',
            get='credentials.username',
            list=False,
            usage=_('Username used to connect to a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Password',
            name='ssh_password',
            get='credentials.password',
            list=False,
            usage=_('Password used to connect to a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Port',
            name='ssh_port',
            get='credentials.port',
            list=False,
            type=ValueType.NUMBER,
            usage=_('SSH port used to connect to a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Private key',
            name='ssh_privkey',
            get='credentials.privkey',
            list=False,
            usage=_('Private SSH peer used to connect to SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Host key',
            name='ssh_hostkey',
            get='credentials.hostkey',
            list=False,
            usage=_('SSH host key of a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )


@description(_("Manage Amazon S3 peers"))
class AmazonS3NamespaceMixin(BaseVariantMixin):
    def add_properties(self):
        super(AmazonS3NamespaceMixin, self).add_properties()

        self.add_property(
            descr='Access key',
            name='s3_access_key',
            get='credentials.access_key',
            list=False,
            usage=_('Access key to Amazon S3.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )

        self.add_property(
            descr='Secret key',
            name='s3_secret_key',
            get='credentials.secret_key',
            list=False,
            usage=_('Secret key to Amazon S3.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )

        self.add_property(
            descr='Region',
            name='s3_region',
            get='credentials.region',
            list=False,
            usage=_('Region property used to connect to Amazon S3 peer.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )

        self.add_property(
            descr='Bucket',
            name='s3_bucket',
            get='credentials.bucket',
            list=False,
            usage=_('Bucket property used to connect to Amazon S3 peer.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )

        self.add_property(
            descr='Folder',
            name='s3_folder',
            get='credentials.folder',
            list=False,
            usage=_('Folder property used to connect to Amazon S3 peer.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )


@description(_("Manage Amazon S3 peers"))
class VMwareNamespaceMixin(BaseVariantMixin):
    def add_properties(self):
        super(VMwareNamespaceMixin, self).add_properties()

        self.add_property(
            descr='Address',
            name='vmware_address',
            get='credentials.address',
            list=False,
            usage=_('Address of a VMware ESXi instance'),
            condition=lambda o: o['type'] == 'vmware'
        )

        self.add_property(
            descr='Username',
            name='vmware_username',
            get='credentials.username',
            list=False,
            usage=_('User name'),
            condition=lambda o: o['type'] == 'vmware'
        )

        self.add_property(
            descr='Password',
            name='vmware_password',
            get='credentials.password',
            list=False,
            usage=_('Password'),
            condition=lambda o: o['type'] == 'vmware'
        )


@description("Configure and manage peers")
class PeerNamespace(
    EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, FreeNASPeerNamespaceMixin, SSHPeerNamespaceMixin,
    AmazonS3NamespaceMixin, VMwareNamespaceMixin, EntityNamespace
):
    """
    The peer namespace contains the namespaces
    for managing SSH, FreeNAS and Amazon S3
    peers.
    """
    def __init__(self, name, context):
        super(PeerNamespace, self).__init__(name, context)
        self.context = context
        self.entity_subscriber_name = 'peer'
        self.primary_key_name = 'name'
        self.create_task = 'peer.create'
        self.update_task = 'peer.update'
        self.delete_task = 'peer.delete'
        self.primary_key_name = 'name'

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> type=<type> [more properties...]

            Examples: create name=mypeer type=ssh address=freenas-2.local username=root \\
                      password=meh

            Creates a peer. For a list of properties, see 'help properties'.""")

        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set bucket=new_bucket
                      set access_key=new_access_key

            Sets a peer property.
            For a list of properties, see 'help properties'.""")

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified peer.""")

        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all peers. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        self.skeleton_entity = {
            'type': None,
            'credentials': {}
        }

        def set_type(o, v):
            q.set(o, 'type', v)
            q.set(o, 'credentials.type', '{0}-credentials'.format(v))

        self.add_property(
            descr='Peer Name',
            name='name',
            get='name',
            condition=lambda o: 'id' in o or o['type'] != 'freenas',
            usage=_('Name of a peer.')
        )

        self.add_property(
            descr='Peer Type',
            name='type',
            get='type',
            set=set_type,
            enum=['ssh', 'amazon-s3', 'freenas', 'vmware', 'dropbox'],
            usage=_('Type of a peer.')
        )

        self.add_property(
            descr='State',
            name='state',
            get='status.state',
            set=None,
            list=True,
            usage=_('Health status of a peer.')
        )

        super(PeerNamespace, self).add_properties()
        self.primary_key = self.get_mapping('name')


def _init(context):
    context.attach_namespace('/', PeerNamespace('peer', context))
    context.map_tasks('peer.*', PeerNamespace)
