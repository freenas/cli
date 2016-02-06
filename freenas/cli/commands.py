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

import os
import inspect
import sys
import select
import readline
import six
import gettext
import platform
import textwrap
import re
from datetime import datetime
from freenas.cli.parser import parse, unparse
from freenas.cli.complete import NullComplete, EnumComplete
from freenas.cli.namespace import (
    Command, PipeCommand, CommandException, description,
    SingleItemNamespace, Namespace
)
from freenas.cli.output import (
    Table, ValueType, output_msg, output_lock, output_less, format_value,
    Sequence, read_value, format_output
)
from freenas.cli.output import Object as output_obj
from freenas.cli.output import ProgressBar
from freenas.cli.descriptions.tasks import translate as translate_task
from freenas.cli.utils import (
    describe_task_state, parse_timedelta, SIGTSTPException, SIGTSTP_setter
)
from freenas.dispatcher.shell import ShellClient


if platform.system() != 'Windows':
    import tty
    import termios


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


def create_variable_completer(name, var):
    if var.type == ValueType.BOOLEAN:
        return EnumComplete(name + '=', ['yes', 'no'])

    if var.choices:
        return EnumComplete(name + '=', var.choices)

    return NullComplete(name + '=')


@description("Sets variable value")
class SetenvCommand(Command):

    """
    Set value of environment variable. Use printenv to display
    available variables and their current values.

    If the value contains any non-alphanumeric characters,
    enclose it between double quotes.

    Usage: setenv <variable>=<value>

    Example: setenv debug=yes
             setenv prompt="{path}>"
    """

    def run(self, context, args, kwargs, opargs):
        if args:
            raise CommandException(_(
                "Incorrect syntax {0}\n{1}".format(args, inspect.getdoc(self))
            ))
        if not kwargs:
            raise CommandException(_(
                'Please specify a variable to set.\n{0}'.format(inspect.getdoc(self))
            ))

        for k, v in list(kwargs.items()):
            context.variables.set(k, v)

    def complete(self, context):
        return [create_variable_completer(k, v) for k, v in context.variables.get_all()]


@description("Prints variable value")
class PrintenvCommand(Command):

    """
    Either print a list of all environment variables and their values
    or the value of the specified environment variable.

    Usage: printenv <variable>

    Example: printenv
             printenv timeout
    """

    def run(self, context, args, kwargs, opargs):
        if len(kwargs) > 0:
            raise CommandException(_("Invalid syntax {0}.\n{1}".format(kwargs, inspect.getdoc(self))))

        if len(args) == 0:
            var_dict_list = []
            for k, v in context.variables.get_all_printable():
                var_dict = {
                        'varname': k,
                        'vardescr': context.variables.variable_doc[k],
                        'varvalue': v,
                        }
                var_dict_list.append(var_dict)
            return Table(var_dict_list, [
                Table.Column('Variable', 'varname', ValueType.STRING),
                Table.Column('Description', 'vardescr', ValueType.STRING),
                Table.Column('Value', 'varvalue')])

        if len(args) == 1:
            try:
                return format_value(context.variables.variables[args[0]])
            except KeyError:
                raise CommandException(_("No such Environment Variable exists"))
        else:
            raise CommandException(_("Invalid syntax {0}.\n{1}".format(args, inspect.getdoc(self))))

    def complete(self, context):
        return [create_variable_completer(k, v) for k, v in context.variables.get_all()]


@description("Saves the Environment Variables to cli config file")
class SaveenvCommand(Command):

    """
    Save the current set of environment variables to either the specified filename
    or, when not specified, to "/.freenascli.conf". To start the CLI with the saved
    variables, type "cli -c filename" from either shell or an SSH session.
    
    Usage: saveenv
           saveenv <filename>

    Examples:
           saveenv
           saveenv /root/myclisave.conf
    """

    def run(self, context, args, kwargs, opargs):
        if len(args) == 0:
            context.variables.save()
            return "Environment Variables Saved to file: {0}".format(
                context.variables.save_to_file
            )
        if len(args) == 1:
            context.variables.save(args[0])
            return "Environment Variables Saved to file: {0}".format(args[0])
        if len(args) > 1:
            raise CommandException(_(
                "Incorrect syntax: {0}\n{1}".format(args, inspect.getdoc(self))
            ))


@description("Spawns shell, enter \"!shell\" (example: \"!sh\")")
class ShellCommand(Command):

    """
    Launch current logged in user's login shell. Type "exit" to return to the CLI.
    If a command is specified, run the specified command then return to the CLI.
    If the full path to an installed shell is specifed, launch the specified shell.

    Usage: shell <command>

    Examples:
           shell /usr/local/bin/bash
           shell "tail /var/log/messages"
    """

    def __init__(self):
        super(ShellCommand, self).__init__()
        self.closed = False

    def run(self, context, args, kwargs, opargs):
        def read(data):
            sys.stdout.write(data.decode('utf8'))
            sys.stdout.flush()

        def close():
            self.closed = True

        self.closed = False
        name = args[0] if len(args) > 0 and len(args[0]) > 0 else '/bin/sh'
        token = context.call_sync('shell.spawn', name)
        shell = ShellClient(context.hostname, token)
        shell.on_data(read)
        shell.on_close(close)
        shell.open()

        fd = sys.stdin.fileno()

        if platform.system() != 'Windows':
            old_settings = termios.tcgetattr(fd)
            tty.setraw(fd)

        while not self.closed:
            r, w, x = select.select([fd], [], [], 0.1)
            if fd in r:
                ch = os.read(fd, 1)
                shell.write(ch)

        if platform.system() != 'Windows':
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


@description("Displays the active IP addresses from all configured network interface")
class ShowIpsCommand(Command):

    """
    Display the IP addresses from all configured and active network interfaces.

    Usage: showips
    """

    def run(self, context, args, kwargs, opargs):
        return Sequence(
            _("These are the active ips from all the configured network interfaces"),
            Table(
                [{'ip': x} for x in context.call_sync('network.config.get_my_ips')],
                [Table.Column(_("IP Addresses (ip)"), 'ip')]
            )
        )


@description("Displays the URLs to access the web GUI from")
class ShowUrlsCommand(Command):

    """
    Display the URL\(s\) for accessing the web GUI.

    Usage: showurls
    """

    def run(self, context, args, kwargs, opargs):
        my_ips = context.call_sync('network.config.get_my_ips')
        my_protocols = context.call_sync('system.ui.get_config')
        urls = []
        for proto in my_protocols['webui_protocol']:
            proto_port = my_protocols['webui_{0}_port'.format(proto.lower())]
            if proto_port is not None:
                if proto_port in [80, 443]:
                    for x in my_ips:
                        urls.append({'url': '{0}://{1}'.format(proto.lower(), x)})
                else:
                    for x in my_ips:
                        urls.append({'url': '{0}://{1}:{2}'.format(proto.lower(), x, proto_port)})
        return Sequence(
            _("You may try the following URLs to access the web user interface:"),
            Table(urls, [Table.Column(_('URLs (url)'), 'url')])
        )


@description("Logs in to the server")
class LoginCommand(Command):

    """
    Login to the CLI as the specified user.

    Usage: login <username> <password>
    """

    def run(self, context, args, kwargs, opargs):
        if len(args) < 2:
            raise CommandException("Not enough arguments provided.\n" +
                                   inspect.getdoc(self))
        context.connection.login_user(args[0], args[1])
        context.connection.subscribe_events('*')
        context.start_entity_subscribers()
        context.login_plugins()


@description("Exits the CLI, enter \"^D\" (ctrl+D)")
class ExitCommand(Command):

    """
    Exit the CLI. Note that the CLI will restart if this command is run from the
    local console. The keyboard shortcut for this command is (ctrl+d).

    Usage: exit
    """

    def run(self, context, args, kwargs, opargs):
        sys.exit(0)


@description("Specifies the current cli session's user")
class WhoamiCommand(Command):

    """
    Display the current CLI user.

    Usage: whoami
    """

    def run(self, context, args, kwargs, opargs):
        return context.user


@description("Provides help on commands")
class HelpCommand(Command):

    """
    Provide general usage information for current namespace. Alternately,
    provide usage information for specified command or for specified
    namespace.

    To see the available properties for the current or specified namespace,
    use 'help properties'.

    Usage: help
           help <command>
           help <namespace>
           <namespace> help properties

    Examples:
        help
        help printenv
        help account user show
        account group help properties
    """

    def run(self, context, args, kwargs, opargs):
        arg = args[:]
        obj = context.ml.get_relative_object(self.exec_path[-1], args)

        if len(arg) > 0:
            if "/" in arg:
                output_msg(textwrap.dedent("""\
                    Usage: /
                    / <namespace>
                    / <namespace> <command>

                    Allows you to navigate or execute commands starting \
                    from the root namespace"""))
                return
            elif ".." in arg:
                output_msg(textwrap.dedent("""\
                    Usage: ..

                    Goes up one level of namespace"""))
                return
            elif "-" in arg:
                output_msg(textwrap.dedent("""\
                    Usage: -

                    Goes back to the previous namespace"""))
                return
            elif "properties" in arg:
                # If the namespace has properties, display a list of the available properties
                if hasattr(obj, 'property_mappings'):
                    prop_dict_list = []
                    for prop in obj.property_mappings:
                        if prop.usage:
                            prop_usage = prop.usage
                        else:
                            if prop.enum:
                                prop_type = "enum [" + ", ".join(prop.enum) + "]"
                            else:
                                prop_type = str(prop.type).split('ValueType.')[-1].lower()
                            if not prop.set:
                                prop_usage = "{0}, read_only {1} value".format(prop.descr, prop_type)
                            else:
                                prop_usage = "{0}, accepts {1} values".format(prop.descr, prop_type)
                        prop_dict = {
                                'propname': prop.name,
                                'propusage': prop_usage
                        }
                        prop_dict_list.append(prop_dict)
                if len(prop_dict_list) > 0:
                    return Table(prop_dict_list, [
                        Table.Column('Property', 'propname', ValueType.STRING),
                        Table.Column('Usage', 'propusage', ValueType.STRING),
                        ])

        if isinstance(obj, Command) and obj.__doc__:
            command_name = obj.__class__.__name__
            if (
                hasattr(obj, 'parent') and
                hasattr(obj.parent, 'localdoc') and
                command_name in obj.parent.localdoc.keys()
               ):
                output_msg(textwrap.dedent(obj.parent.localdoc[command_name]))
            else:
                output_msg(inspect.getdoc(obj))

        if isinstance(obj, Namespace):
            # First listing the Current Namespace's commands
            cmd_dict_list = [
                {"cmd": "/", "description": "Go to the root namespace"},
                {"cmd": "..", "description": "Go up one namespace"},
                {"cmd": "-", "description": "Go back to previous namespace"}
            ]
            ns_cmds = obj.commands()
            for key, value in ns_cmds.items():
                if hasattr(value,'description') and value.description is not None:
                    description = value.description
                else:
                    description = obj.get_name()
                value_description = re.sub('<entity>',
                                           obj.get_name(), 
                                           description)
                cmd_dict = {
                    'cmd': key,
                    'description': value_description,
                }
                cmd_dict_list.append(cmd_dict)

            # Then listing the namespaces available from this namespace
            for nss in obj.namespaces():
                if not isinstance(nss, SingleItemNamespace):
                    if hasattr(nss,'description') and nss.description is not None:
                        description = value.description
                    else:
                        description = nss.name
                    namespace_dict = {
                        'cmd': nss.name,
                        'description': nss.description,
                    }
                    cmd_dict_list.append(namespace_dict)

            # Finally listing the builtin cmds
            builtin_cmd_dict_list = []
            for key, value in context.ml.builtin_commands.items():
                if hasattr(value,'description') and value.description is not None:
                    description = value.description
                else:
                    description = key
                builtin_cmd_dict = {
                    'cmd': key,
                    'description': description,
                }
                builtin_cmd_dict_list.append(builtin_cmd_dict)

            # Finally printing all this out in unix `LESS(1)` pager style
            output_seq = Sequence()
            if cmd_dict_list:
                output_seq.append(
                    Table(cmd_dict_list, [
                        Table.Column('Command', 'cmd', ValueType.STRING),
                        Table.Column('Description', 'description', ValueType.STRING)]))
            # Only display the help on builtin commands if in the RootNamespace
            if obj.__class__.__name__ == 'RootNamespace':
                output_seq.append(
                    Table(builtin_cmd_dict_list, [
                        Table.Column('Global Command', 'cmd', ValueType.STRING),
                        Table.Column('Description', 'description', ValueType.STRING)
                    ]))
            help_message = ""
            if obj.__doc__:
                help_message = inspect.getdoc(obj)
            elif isinstance(obj, SingleItemNamespace):
                help_message = obj.entity_doc()
            output_seq.append(help_message)
            return output_seq


@description("Sends the user to the top level")
class TopCommand(Command):

    """
    Go back to the root of the command tree.

    Usage: top
    """

    def run(self, context, args, kwargs, opargs):
        context.ml.path = [context.root_ns]


@description("Clears the cli stdout")
class ClearCommand(Command):

    """
    Clear the screen.

    Usage: clear
    """

    def run(self, context, args, kwargs, opargs):
        output_lock.acquire()
        os.system('cls' if os.name == 'nt' else 'clear')
        output_lock.release()


@description("Shows the CLI command history")
class HistoryCommand(Command):
    """
    List the commands previously executed in this CLI instance.
    Optionally, provide a number to specify the number of lines,
    from the last line of history, to display.

    Usage: history <number>

    Example: history
             history 10

    """

    def run(self, context, args, kwargs, opargs):
        desired_range = None
        if args:
            if len(args) != 1:
                raise CommandException(_(
                    "Invalid Syntax for history command.\n{0}".format(inspect.getdoc(self))
                ))
            try:
                desired_range = int(args[0])
            except ValueError:
                raise CommandException(_("Please specify an integer for the history range"))
        histroy_range = readline.get_current_history_length()
        if desired_range is not None and desired_range < histroy_range:
            histroy_range = desired_range + 1
        return Table(
            [{'cmd': readline.get_history_item(i)} for i in range(1, histroy_range)],
            [Table.Column('Command History', 'cmd', ValueType.STRING)]
        )


@description("Imports a script for parsing")
class SourceCommand(Command):
    """
    Run specified file\(s\), where each file contains a list
    of CLI commands. When creating the source file, separate
    each CLI command with a semicolon \";\" or place each
    CLI command on its own line. If multiple files are
    specified, they are run in the order given. If a CLI
    command fails, the source operation aborts.

    Usage: source </path/filename>
           source </path/filename1> </path/filename2> </path/filename3>
    """

    def run(self, context, args, kwargs, opargs):
        if len(args) == 0:
            raise CommandException(_("Please provide a filename.\n") +
                                   inspect.getdoc(self))
        else:
            for arg in args:
                if os.path.isfile(arg):
                    try:
                        with open(arg, 'r') as f:
                            ast = parse(f.read(), arg)
                            context.eval_block(ast)
                    except UnicodeDecodeError as e:
                        raise CommandException(_(
                            "Incorrect filetype, cannot parse file: {0}".format(str(e))
                        ))
                else:
                    raise CommandException(_("File {0} does not exist.".format(arg)))


@description("Dumps namespace configuration to a series of CLI commands")
class DumpCommand(Command):
    """
    Diplay configuration of specified namespace or, when not specified,
    the current namespace. Optionally, specify the name of the file to
    send the output to.

    Usage: <namespace> dump
           <namespace> dump <filename>

    Examples:
    update dump
    dump | less
    dump /root/mydumpfile.cli
    """

    def run(self, context, args, kwargs, opargs):
        ns = self.exec_path[-1]
        if len(args) > 1:
            raise CommandException(_('Invalid syntax: {0}.\n{1}'.format(args, inspect.getdoc(self))))
        result = []
        if getattr(ns, 'serialize'):
            try:
                for i in ns.serialize():
                    result.append(unparse(i))
            except NotImplementedError:
                return

        contents = '\n'.join(result)
        if len(args) == 1:
            filename = args[0]
            try:
                with open(filename, 'w') as f:
                    f.write(contents)
            except IOError:
                raise CommandException(_('Error writing to file {0}'.format(filename)))
            return _('Configuration successfully dumped to file {0}'.format(filename))
        else:
            return contents


@description("Prints the provided message to the output")
class EchoCommand(Command):

    """
    Write any specified operands, separated by single blank
    (' ') characters and followed by a newline ('\\n') character, to the
    standard output. It also has the ability to expand and substitute
    variables in place using the '${variable_name}' syntax.
  
    Usage: echo <string_to_display>

    Examples:
    echo Have a nice Day!
    output: Have a nice Day!

    echo Hello the current cli session timeout is $timeout seconds
    output: Hello the current cli session timeout is 10 seconds

    echo Hi there, you are using ${language}lang
    output Hi there, you are using Clang
    """

    def run(sef, context, args, kwargs, opargs):
        if len(args) == 0:
            return ""
        else:
            echo_seq = []
            for i, item in enumerate(args):
                if not (
                    isinstance(item, (Table, output_obj, dict, Sequence, list)) or
                    i == 0 or
                    isinstance(args[i-1], (Table, output_obj, dict, Sequence, list))
                ):
                    echo_seq[-1] = ' '.join([echo_seq[-1], str(item)])
                else:
                    echo_seq.append(item)
            return Sequence(*echo_seq)


@description("Shows pending tasks")
class PendingCommand(Command):
    """
    Usage: pending

    Shows a list of currently pending tasks.
    """
    def run(self, context, args, kwargs, opargs):
        pending = list(filter(
            lambda t: t['session'] == context.session_id,
            context.pending_tasks.values()
        ))

        return Table(pending, [
            Table.Column('Task ID', 'id'),
            Table.Column('Task description', lambda t: translate_task(context, t['name'], t['args'])),
            Table.Column('Task status', describe_task_state)
        ])


@description("Waits for a task to complete and shows task progress")
class WaitCommand(Command):
    """
    Usage: wait
           wait <task id>

    """
    def run(self, context, args, kwargs, opargs):
        if args:
            try:
                tid = int(args[0])
            except ValueError:
                raise CommandException('Task id argument must be an integer')
        else:
            tid = None
            try:
                tid = context.global_env.find('_last_task_id').value
            except KeyError:
                pass
        if tid is None:
            raise CommandException(_(
                    'No recently submitted tasks (which are still active) found'
            ))

        def update(progress, task):
            message = task['progress']['message'] if 'progress' in task else task['state']
            percentage = task['progress']['percentage'] if 'progress' in task else 0
            progress.update(percentage=percentage, message=message)

        try:
            task = context.entity_subscribers['task'].query(('id', '=', tid), single=True)
            if task['state'] in ('FINISHED', 'FAILED', 'ABORTED'):
                return _("The task with id: {0} ended in {1} state".format(tid, task['state']))

            # lets set the SIGTSTP (Ctrl+Z) handler
            SIGTSTP_setter(set_flag=True)
            output_msg(_("Hit Ctrl+C to terminate task if needed"))
            output_msg(_("To background running task press 'Ctrl+Z'"))
            context.ml.skip_prompt_print = True

            progress = ProgressBar()
            update(progress, task)
            for op, old, new in context.entity_subscribers['task'].listen(tid):
                update(progress, new)

                if new['state'] == 'FINISHED':
                    progress.finish()
                    break

                if new['state'] == 'FAILED':
                    six.print_()
                    break

                if new['state'] == 'ABORTED':
                    six.print_()
                    break
        except KeyboardInterrupt:
            six.print_()
            output_msg(_("User requested task termination. Sending abort signal sent"))
            context.call_sync('task.abort', tid)
        except SIGTSTPException:
                # The User backgrounded the task by sending SIGTSTP (Ctrl+Z)
                six.print_()
                output_msg(_("Task {0} will continue to run in the background.".format(tid)))
                output_msg(_("To bring it back to the foreground execute 'wait {0}'".format(tid)))
                output_msg(_("Use the 'pending' command to see pending tasks (of this session)"))
        finally:
            context.ml.skip_prompt_print = False
            # Now that we are done with the task unset the Ctrl+Z handler
            # lets set the SIGTSTP (Ctrl+Z) handler
            SIGTSTP_setter(set_flag=False)



@description("Allows the user to scroll through output")
class MorePipeCommand(PipeCommand):

    """
    Allow paging and scrolling through long outputs of text.
    It has an alias of 'less' i.e. 'more' and 'less' do the same thing.

    Usage: <command> | more
           <command> | less

    Examples: task show | more
              account user show | more
              system advanced show | less
    """

    def __init__(self):
        self.must_be_last = True

    def run(self, context, args, kwargs, opargs, input=None):
        output_less(lambda x: format_output(input, file=x))
        return None


def map_opargs(opargs, context):
    ns = context.pipe_cwd
    mapped_opargs = []
    for k, o, v in opargs:
        if ns.has_property(k):
            mapping = ns.get_mapping(k)
            mapped_opargs.append((mapping.name, o, read_value(v, mapping.type)))
        else:
            raise CommandException(_(
                'Property {0} not found, valid properties are: {1}'.format(
                    k,
                    ','.join([x.name for x in ns.property_mappings if x.list])
                )
            ))
    return mapped_opargs


@description("Filters result set basing on specified conditions")
class SearchPipeCommand(PipeCommand):

    """
    Return an element in a list that matches the given key value.

    Usage: <command> | search <key> <op> <value> ...

    Example: account user show | search username==root
    """

    def run(self, context, args, kwargs, opargs, input=None):
        return input

    def serialize_filter(self, context, args, kwargs, opargs):
        mapped_opargs = map_opargs(opargs, context)

        if len(kwargs) > 0:
            raise CommandException(_(
                "Invalid syntax {0}.\n".format(kwargs) +
                inspect.getdoc(self)
            ))

        if len(args) > 0:
            raise CommandException(_(
                "Invalid syntax {0}.\n".format(args) +
                inspect.getdoc(self)
            ))

        return {"filter": mapped_opargs}


@description("Selects tasks started before or at time-delta")
class OlderThanPipeCommand(PipeCommand):
    def run(self, context, args, kwargs, opargs, input=None):
        return input

    def serialize_filter(self, context, args, kwargs, opargs):
        return {"filter": [
            ('started_at', '!=', None),
            ('started_at', '<=', datetime.now() - parse_timedelta(args[0]))
        ]}


@description("Selects tasks started at or since time-delta")
class NewerThanPipeCommand(PipeCommand):
    def run(self, context, args, kwargs, opargs, input=None):
        return input

    def serialize_filter(self, context, args, kwargs, opargs):
        print(args)
        return {"filter": [
            ('started_at', '!=', None),
            ('started_at', '>=', datetime.now() - parse_timedelta(args[0]))
        ]}


@description("Excludes certain results from result set basing on specified conditions")
class ExcludePipeCommand(PipeCommand):
    """
    Return all the elements of a list that do not match the given key value.

    Usage: <command> | exclude <key> <op> <value> ...

    Example: account user show | exclude username==root
    """
    def run(self, context, args, kwargs, opargs, input=None):
        return input

    def serialize_filter(self, context, args, kwargs, opargs):
        mapped_opargs = map_opargs(opargs, context)

        if len(kwargs) > 0:
            raise CommandException(_(
                "Invalid syntax {0}.\n".format(kwargs) +
                inspect.getdoc(self)
            ))

        if len(args) > 0:
            raise CommandException(_(
                "Invalid syntax {0}.\n".format(args) +
                inspect.getdoc(self)
            ))

        result = []
        for i in mapped_opargs:
            result.append(('nor', (i,)))

        return {"filter": result}


@description("Sorts result set")
class SortPipeCommand(PipeCommand):
    """
    Sort the elements of a list by the given key.

    Usage: <command> | sort <field> [<-field> ...]

    Example: account user show | sort name
    """
    def serialize_filter(self, context, args, kwargs, opargs):
        return {"params": {"sort": args}}


@description("Limits output to <n> items")
class LimitPipeCommand(PipeCommand):
    """
    Return only the n elements of a list.

    Usage: <command> | limit <n>

    Example: account user show | limit 10
    """
    def serialize_filter(self, context, args, kwargs, opargs):
        if len(args) == 0:
            raise CommandException(_("Please specify a number to limit."))
        if not isinstance(args[0], int) or len(args) > 1:
            raise CommandException(_(
                "Invalid syntax {0}.\n".format(args) +
                inspect.getdoc(self)
            ))
        return {"params": {"limit": args[0]}}


@description("Displays the output for a specific field")
class SelectPipeCommand(PipeCommand):
    """
    Return only the output of the specific field for a list.

    Usage: <command> | select <field>

    Example: account user show | select username
    """
    def run(self, context, args, kwargs, opargs, input=None):
        ns = context.pipe_cwd
        available_props = [x.name for x in ns.property_mappings if x.list]
        if len(args) == 0:
            raise CommandException(_(
                "Please specify a property field. Available properties are: {0}".format(
                    ','.join(available_props)
                )
            ))

        field = args[0]
        if ns.has_property(field):
            field = ns.get_mapping(field).get_name
        else:
            raise CommandException(_(
                "Please specify a property field. Available properties are: {0}".format(
                    ','.join(available_props)
                )
            ))

        if isinstance(input, Table):
            input.data = [{'result': x.get(field)} for x in input.data]
            input.columns = [Table.Column('Result', 'result')]

            return input
