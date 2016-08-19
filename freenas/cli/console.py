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

import sys
import tty
import curses
import termios
from freenas.dispatcher.shell import VMConsoleClient


class Console(object):
    def __init__(self, context, id, name):
        self.context = context
        self.id = id
        self.name = name
        self.conn = None
        self.stdscr = None

    def on_data(self, data):
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

    def connect(self):
        token = self.context.call_sync('containerd.management.request_console', self.id)
        self.conn = VMConsoleClient(self.context.hostname, token)
        self.conn.on_data(self.on_data)
        self.conn.open()

    def start(self):
        # process escape characters using runtime
        eseq = bytes(self.context.variables.get('vm.console_interrupt'), 'utf-8').decode('unicode_escape')
        esbytes = bytes(eseq, 'utf-8')
        eslen = len(esbytes)
        esidx = 0   # stack pointer for sequence match...

        stdin_fd = sys.stdin.fileno()
        old_stdin_settings = termios.tcgetattr(stdin_fd)
        try:
            tty.setraw(stdin_fd)
            self.connect()
            while True:
                ch = sys.stdin.read(1)
                bch = bytes(ch, 'utf-8')[0]

                if esbytes[esidx] == bch:
                    esidx += 1
                    if esidx == eslen:
                        self.conn.close()
                        break
                elif esidx > 0:
                    # reset stack pointer...no match
                    # BW: possibly write out characters up to this point if sequence not matched?
                    #     or maybe we write the chars all along?
                    esidx = 0
                else:
                    self.conn.write(ch)
        finally:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_stdin_settings)
            curses.wrapper(lambda x: x)
