#+
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


import ply.lex as lex
import ply.yacc as yacc


class Symbol(object):
    def __init__(self, name):
        if name == "none":
            self.name = None
        else:
            self.name = name

    def __str__(self):
        return "<Symbol '{0}'>".format(self.name)

    def __repr__(self):
        return str(self)


class Set(object):
    def __init__(self, value):
        self.value = value
    
    def __str__(self):
        return "<Set '{0}'>".format(self.value)

    def __repr__(self):
        return str(self)


class BinaryExpr(object):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right

    def __str__(self):
        return "<BinaryExpr left '{0}' op '{1}' right '{2}'>".format(self.left, self.op, self.right)

    def __repr__(self):
        return str(self)


class Literal(object):
    def __init__(self, value, type):
        self.value = value
        self.type = type

    def __str__(self):
        return "<Literal '{0}' type '{1}>".format(self.value, self.type)

    def __repr__(self):
        return str(self)


class PipeExpr(object):
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def __str__(self):
        return "<PipeExpr left '{0}' right '{1}>".format(self.left, self.right)

    def __repr__(self):
        return str(self)


class CommandExpansion(object):
    def __init__(self, expr):
        self.expr = expr

    def __str__(self):
        return "<CommandExpansion '{0}'>".format(self.expr)

    def __repr__(self):
        return str(self)


tokens = [
    'ATOM', 'NUMBER', 'HEXNUMBER', 'BINNUMBER', 'OCTNUMBER', 'STRING',
    'ASSIGN', 'EOPEN', 'ECLOSE', 'EQ', 'NE', 'GT', 'GE', 'LT', 'LE',
    'REGEX', 'UP', 'PIPE', 'LIST', 'COMMA', 'INC', 'DEC'
]


def t_HEXNUMBER(t):
    r'0x[0-9a-fA-F]+$'
    t.value = int(t.value, 16)
    return t


def t_OCTNUMBER(t):
    r'0o[0-7]+$'
    t.value = int(t.value, 8)
    return t


def t_BINNUMBER(t):
    r'0b[01]+$'
    t.value = int(t.value, 2)
    return t


def t_NUMBER(t):
    r'\d+$'
    t.value = int(t.value)
    return t


def t_STRING(t):
    r'\"([^\\\n]|(\\.))*?\"'
    t.value = t.value[1:-1]
    return t


t_ignore = ' \t'
t_PIPE = r'\|'
t_EOPEN = r'\$\('
t_ECLOSE = r'\)'
t_ASSIGN = r'='
t_INC = r'=\+'
t_DEC = r'=-'
t_EQ = r'=='
t_NE = r'\!='
t_GT = r'>'
t_GE = r'>='
t_LT = r'<'
t_LE = r'<'
t_REGEX = r'~='
t_COMMA = r'\,'
t_UP = r'\.\.'
t_LIST = r'\?'
t_ATOM = r'[0-9a-zA-Z_\$\/-][0-9a-zA-Z_\_\-\.\/#@]*'


def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)


def p_stmt(p):
    """
    stmt : expr_list
    stmt : stmt PIPE expr_list
    """
    if len(p) == 2:
        p[0] = p[1]
        return

    p[0] = [PipeExpr(p[1], p[3])]


def p_expr_list(p):
    """
    expr_list : expr
    expr_list : expr expr_list
    """
    if len(p) == 2:
        p[0] = [p[1]]
        return

    p[0] = [p[1]] + p[2]


def p_expr(p):
    """
    expr : literal
    expr : symbol
    expr : binary
    expr : expansion
    expr : set
    """
    p[0] = p[1]


def p_expansion(p):
    """
    expansion : EOPEN expr_list ECLOSE
    """
    p[0] = CommandExpansion(p[2])


def p_literal(p):
    """
    literal : NUMBER
    literal : HEXNUMBER
    literal : BINNUMBER
    literal : OCTNUMBER
    literal : STRING
    """
    p[0] = Literal(p[1], type(p[1]))


def p_binary(p):
    """
    binary : ATOM ASSIGN expr
    binary : ATOM EQ expr
    binary : ATOM NE expr
    binary : ATOM GT expr
    binary : ATOM GE expr
    binary : ATOM LT expr
    binary : ATOM LE expr
    binary : ATOM REGEX expr
    binary : ATOM INC expr
    binary : ATOM DEC expr
    """
    p[0] = BinaryExpr(p[1], p[2], p[3])

def p_set(p):
    """
    set : ATOM COMMA set
    set : ATOM
    """
    if len(p) > 2:
        if isinstance(p[3], Set):
            right = p[3].value
        else:
            right = p[3].name
        p[0] = Set(p[1] + p[2] + right)
    else:
        p[0] = Symbol(p[1])

def p_symbol(p):
    """
    symbol : UP
    symbol : LIST
    """
    p[0] = Symbol(p[1])


def p_error(p):
    print "error: {0}".format(p)


lex.lex()
yacc.yacc()


def parse(s):
    return yacc.parse(s)
