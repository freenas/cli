# +
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


import icu
from freenas.cli.descriptions import tasks
from freenas.cli.namespace import EntityNamespace, RpcBasedLoadMixin, Command, description
from freenas.cli.output import ValueType

t = icu.Transliterator.createInstance("Any-Accents", icu.UTransDirection.FORWARD)
_ = t.transliterate


@description("Submits new task")
class SubmitCommand(Command):
    """
    Usage: submit <task>

    Submits a task to the dispatcher for execution

    Examples:
        submit update.check
    """
    def run(self, context, args, kwargs, opargs):
        name = args.pop(0)
        context.submit_task(name, *args)


@description("Aborts running task")
class AbortCommand(Command):
    """
    Usage: abort

    Submits a task to the dispatcher for execution

    Examples:
        submit update.check
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.call_sync('task.abort', self.parent.entity['id'])


@description("Manage tasks")
class TasksNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(TasksNamespace, self).__init__(name, context)

        self.allow_create = False
        self.allow_edit = False
        self.query_call = 'task.query'

        self.add_property(
            descr='ID',
            name='id',
            get='id',
            list=True,
        )

        self.add_property(
            descr='Started at',
            name='started_at',
            get='started_at',
            list=True,
        )

        self.add_property(
            descr='Finished at',
            name='finished_at',
            get='finished_at',
            list=True
        )

        self.add_property(
            descr='Description',
            name='description',
            get=self.describe_task,
        )

        self.add_property(
            descr='State',
            name='state',
            get=self.describe_state,
        )

        self.primary_key = self.get_mapping('id')
        self.entity_commands = lambda this: {
            'abort': AbortCommand(this)
        }

        self.extra_commands = {
            'submit': SubmitCommand()
        }

    def describe_state(self, task):
        if task['state'] == 'EXECUTING':
            if 'progress' not in task:
                return task['state']

            return '{0:2.0f}% ({1})'.format(
                task['progress.percentage'], task['progress.message'])

        return task['state']

    def describe_task(self, task):
        return tasks.translate(self.context, task['name'], task['args'])


def _init(context):
    context.attach_namespace('/', TasksNamespace('task', context))
