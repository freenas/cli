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
    EntitySubscriberBasedLoadMixin, CreateEntityCommand, description
)
from freenas.cli.complete import NullComplete, RpcComplete
from freenas.cli.output import ValueType, Sequence, Table
from freenas.cli.utils import EntityPromise
from freenas.utils import first_or_default, query as q

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description(_("Exchange keys with remote host and create known FreeNAS peer entry at both sides"))
class CreateFreeNASPeerCommand(CreateEntityCommand):
    """
    Usage: create name=<name> address=<address> username=<username>
                  password=<password> token=<token>

    Example: create address=freenas-2.local username=root password=secret
             create address=10.0.0.1 username=my_username password=secret
             create address=my_username@10.0.0.1 password=secret
             create address=my_username@10.0.0.1 password=secret port=1234
             create address=freenas-2.local token=123456

    Exchange keys with remote host and create known FreeNAS host entry
    at both sides.

    FreeNAS peer name always equals to the remote host name.

    User name and password are used only once to authorize key exchange.
    Default SSH port is 22.

    Peer creation using authentication tokens have two steps:
    before issuing actual 'create' command, one has to generate
    a temporary token on remote machine via 'get_token' command.

    User used for pairing purposes must belong to 'wheel' group at remote host.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("Create requires more arguments, see 'help create' for more information"))
        if len(args) > 0:
            raise CommandException(_("Wrong syntax for create, see 'help create' for more information"))

        if 'address' not in kwargs:
            raise CommandException(_('Please specify an address of your remote'))
        else:
            address = kwargs.pop('address')

        port = kwargs.pop('port', 22)

        token = kwargs.get('token')

        if token:
            tid = context.submit_task(
                self.parent.create_task,
                {
                    'type': 'freenas',
                    'credentials': {
                        'port': port,
                        'type': 'freenas-auth',
                        'address': address,
                        'auth_code': token
                    }
                }
            )
        else:
            split_address = address.split('@')
            if len(split_address) == 2:
                kwargs['username'] = split_address[0]
                address = split_address[1]

            if 'username' not in kwargs:
                raise CommandException(_('Please specify a valid user name'))
            else:
                username = kwargs.pop('username')

            if 'password' not in kwargs:
                raise CommandException(_('Please specify a valid password'))
            else:
                password = kwargs.pop('password')

            tid = context.submit_task(
                self.parent.create_task,
                {
                    'type': 'freenas',
                    'credentials': {
                        'username': username,
                        'password': password,
                        'port': port,
                        'type': 'freenas-auth',
                        'address': address
                    }
                }
            )

        return EntityPromise(context, tid, self.parent)

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
            NullComplete('address='),
            NullComplete('username='),
            NullComplete('password='),
            NullComplete('port='),
            NullComplete('token=')
        ]


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
class FreeNASPeerNamespaceMixin(object):
    """
    The FreeNAS peer namespace provides commands for listing and managing FreeNAS peers.
    """
    def add_properties(self):
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified FreeNAS peer.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all FreeNAS peers. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Port',
            name='port',
            get='credentials.port',
            list=False,
            type=ValueType.NUMBER,
            usersetable=False,
            usage=_('SSH port used to reach a FreeNAS peer.'),
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Public key',
            name='pubkey',
            get='credentials.pubkey',
            list=False,
            usersetable=False,
            usage=_('Public SSH key of a FreeNAS peer.'),
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Host key',
            name='hostkey',
            get='credentials.hostkey',
            list=False,
            usersetable=False,
            usage=_('SSH host key of a FreeNAS peer.'),
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Peer address',
            name='address',
            get='credentials.address',
            usersetable=False,
            createsetable=True,
            usage=_('Address of a FreeNAS peer.'),
            condition=lambda o: o['type'] == 'freenas'
        )

        self.add_property(
            descr='Username',
            name='username',
            get=None,
            set='0.username',
            create_arg=True
        )

        self.add_property(
            descr='Password',
            name='password',
            get=None,
            set='0.password',
            create_arg=True
        )

        self.add_property(
            descr='Token',
            name='token',
            get=None,
            set='0.auth_code',
            create_arg=True
        )

    def commands(self):
        cmds = super(FreeNASPeerNamespaceMixin, self).commands()
        cmds.update({
            #'create': CreateFreeNASPeerCommand(self),
            'create_token': FreeNASPeerGetAuthTokenCommand(self),
            'invalidate_token': FreeNASPeerInvalidateTokenCommand(self),
            'list_tokens': FreeNASPeerListTokensCommand(self)
        })
        return cmds


@description(_("Manage SSH peers"))
class SSHPeerNamespaceMixin(object):
    """
    The SSH peer namespace provides commands for listing and managing SSH peers.
    """
    def add_properties(self):
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> address=<address> username=<username>
                   password=<password> port=<port> privkey=<privkey> hostkey=<hostkey>

            Examples: create name=mypeer address=anotherhost.local username=myuser
                             password=secret
                      create name=mypeer address=192.168.0.105 username=myuser
                             hostkey="hostkey" privkey="privkey"

            Creates a SSH peer. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set password=new_secret
                      set username=new_user

            Sets a SSH peer property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified SSH peer.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all SSH peers. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Peer address',
            name='address',
            get='credentials.address',
            usage=_('Address of a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Username',
            name='username',
            get='credentials.username',
            list=False,
            usage=_('Username used to connect to a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Password',
            name='password',
            get='credentials.password',
            list=False,
            usage=_('Password used to connect to a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Port',
            name='port',
            get='credentials.port',
            list=False,
            type=ValueType.NUMBER,
            usage=_('SSH port used to connect to a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Private key',
            name='privkey',
            get='credentials.privkey',
            list=False,
            usage=_('Private SSH peer used to connect to SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )

        self.add_property(
            descr='Host key',
            name='hostkey',
            get='credentials.hostkey',
            list=False,
            usage=_('SSH host key of a SSH peer.'),
            condition=lambda o: o['type'] == 'ssh'
        )


@description(_("Manage Amazon S3 peers"))
class AmazonS3NamespaceMixin(object):
    """
    The Amazon S3 peer namespace provides commands for listing and managing Amazon S3 peers.
    """
    def add_properties(self):
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> address=<address> username=<username>
                   password=<password> port=<port> privkey=<privkey> hostkey=<hostkey>

            Examples: create name=mypeer access_key=my_access_key
                             secret_key=my_secret_key bucket=my_bucket region=my_region
                             folder=my_folder

            Creates a Amazon S3 peer. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set bucket=new_bucket
                      set access_key=new_access_key

            Sets a Amazon S3 peer property.
            For a list of properties, see 'help properties'.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified SSH peer.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all Amazon S3 peers. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Access key',
            name='access_key',
            get='credentials.access_key',
            list=False,
            usage=_('Access key to Amazon S3.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )

        self.add_property(
            descr='Secret key',
            name='secret_key',
            get='credentials.secret_key',
            list=False,
            usage=_('Secret key to Amazon S3.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )

        self.add_property(
            descr='Region',
            name='region',
            get='credentials.region',
            list=False,
            usage=_('Region property used to connect to Amazon S3 peer.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )

        self.add_property(
            descr='Bucket',
            name='bucket',
            get='credentials.bucket',
            list=False,
            usage=_('Bucket property used to connect to Amazon S3 peer.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )

        self.add_property(
            descr='Folder',
            name='folder',
            get='credentials.folder',
            list=False,
            usage=_('Folder property used to connect to Amazon S3 peer.'),
            condition=lambda o: o['type'] == 'amazon-s3'
        )


@description("Configure and manage peers")
class PeerNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, FreeNASPeerNamespaceMixin, SSHPeerNamespaceMixin, AmazonS3NamespaceMixin, EntityNamespace):
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
            usersetable=False,
            list=True,
            usage=_('Health status of a peer.')
        )

        super(PeerNamespace, self).add_properties()
        self.primary_key = self.get_mapping('name')


def _init(context):
    context.attach_namespace('/', PeerNamespace('peer', context))
    context.map_tasks('peer.*', PeerNamespace)
