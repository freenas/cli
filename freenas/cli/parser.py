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


import ply.lex as lex
import ply.yacc as yacc


def ASTObject(name, *args):
    def str(self):
        return "<{0} {1}>".format(
            self.__class__.__name__,
            ' '.join(["{0} '{1}'".format(i, getattr(self, i)) for i in args])
        )

    def init(self, *values, line=None, column=None):
        for idx, i in enumerate(values):
            setattr(self, args[idx], i)

        self.line = line
        self.column = column

    dct = {k: None for k in args}
    dct['__init__'] = init
    dct['__str__'] = str
    dct['__repr__'] = str
    return type(name, (), dct)


Symbol = ASTObject('Symbol', 'name')
Set = ASTObject('Set', 'value')
BinaryExpr = ASTObject('BinaryExpr', 'left', 'op', 'right')
BinaryParameter = ASTObject('BinaryParameter', 'left', 'op', 'right')
Literal = ASTObject('Literal', 'value', 'type')
ExpressionExpansion = ASTObject('ExpressionExpansion', 'expr')
PipeExpr = ASTObject('PipeExpr', 'left', 'right')
FunctionCall = ASTObject('FunctionCall', 'name', 'args')
CommandCall = ASTObject('CommandCall', 'args')
Subscript = ASTObject('Subscript', 'expr', 'index')
IfStatement = ASTObject('IfStatement', 'expr', 'body', 'else_body')
AssignmentStatement = ASTObject('AssignmentStatement', 'name', 'expr')
ForStatement = ASTObject('ForStatement', 'var', 'expr', 'body')
WhileStatement = ASTObject('WhileStatement', 'expr', 'body')
UndefStatement = ASTObject('UndefStatement', 'name')
ReturnStatement = ASTObject('ReturnStatement', 'expr')
BreakStatement = ASTObject('BreakStatement')
FunctionDefinition = ASTObject('FunctionDefinition', 'name', 'args', 'body')


reserved = {
    'if': 'IF',
    'else': 'ELSE',
    'for': 'FOR',
    'while': 'WHILE',
    'in': 'IN',
    'function': 'FUNCTION',
    'return': 'RETURN',
    'break': 'BREAK',
    'and': 'AND',
    'or': 'OR',
    'not': 'NOT',
    'undef': 'UNDEF'
}


tokens = list(reserved.values()) + [
    'ATOM', 'NUMBER', 'HEXNUMBER', 'BINNUMBER', 'OCTNUMBER', 'STRING',
    'ASSIGN', 'LPAREN', 'RPAREN', 'EQ', 'NE', 'GT', 'GE', 'LT', 'LE',
    'REGEX', 'UP', 'PIPE', 'LIST', 'COMMA', 'INC', 'DEC', 'PLUS', 'MINUS',
    'MUL', 'DIV', 'BOOL', 'NULL', 'DOLLAR', 'EOPEN',
    'SEMICOLON', 'LBRACE', 'RBRACE', 'LBRACKET', 'RBRACKET'
]


def t_HEXNUMBER(t):
    r'0x[0-9a-fA-F]+'
    t.value = int(t.value, 16)
    return t


def t_OCTNUMBER(t):
    r'0o[0-7]+'
    t.value = int(t.value, 8)
    return t


def t_BINNUMBER(t):
    r'0b[01]+'
    t.value = int(t.value, 2)
    return t


def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t


def t_STRING(t):
    r'\"([^\\\n]|(\\.))*?\"'
    t.value = t.value[1:-1]
    return t


def t_BOOL(t):
    r'true|false'
    t.value = True if t.value == 'true' else False
    return t


def t_NULL(t):
    r'none'
    t.value = None
    return t


def t_ATOM(t):
    r'[0-9a-zA-Z_\/-\/][0-9a-zA-Z_\_\-\.\/#@\:]*'
    t.type = reserved.get(t.value, 'ATOM')
    return t


t_ignore = ' \t'
t_SEMICOLON = r';'
t_LBRACE = r'\{'
t_RBRACE = r'\}'
t_LBRACKET = r'\['
t_RBRACKET = r'\]'
t_PIPE = r'\|'
t_EOPEN = r'\$\('
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_ASSIGN = r'='
t_DOLLAR = '\$'
t_INC = r'=\+'
t_DEC = r'=-'
t_EQ = r'=='
t_NE = r'\!='
t_GT = r'>'
t_GE = r'>='
t_LT = r'<'
t_LE = r'<'
t_PLUS = r'\+'
t_MINUS = r'-'
t_MUL = r'\*'
t_DIV = r'\/'
t_REGEX = r'~='
t_COMMA = r'\,'
t_UP = r'\.\.'
t_LIST = r'\?'


def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)


def p_stmt_list(p):
    """
    stmt_list : stmt
    stmt_list : stmt SEMICOLON
    stmt_list : stmt SEMICOLON stmt_list
    """
    if len(p) in (2, 3):
        p[0] = [p[1]]
        return

    p[0] = [p[1]] + p[3]


def p_stmt(p):
    """
    stmt : if_stmt
    stmt : for_stmt
    stmt : while_stmt
    stmt : assignment_stmt
    stmt : function_definition_stmt
    stmt : return_stmt
    stmt : break_stmt
    stmt : undef_stmt
    stmt : expr
    stmt : command
    """
    p[0] = p[1]


def p_block(p):
    """
    block : LBRACE stmt_list RBRACE
    """
    p[0] = p[2]


def p_if_stmt(p):
    """
    if_stmt : IF LPAREN expr RPAREN block
    if_stmt : IF LPAREN expr RPAREN block ELSE block
    """
    p[0] = IfStatement(p[3], p[5], p[7] if len(p) == 8 else [], line=p.lineno(1), column=p.lexpos(1))


def p_for_stmt(p):
    """
    for_stmt : FOR LPAREN ATOM IN expr RPAREN block
    """
    p[0] = ForStatement(p[3], p[5], p[7], line=p.lineno(1), column=p.lexpos(1))


def p_while_stmt(p):
    """
    while_stmt : WHILE LPAREN expr RPAREN block
    """
    p[0] = WhileStatement(p[3], p[5], line=p.lineno(1), column=p.lexpos(1))


def p_assignment_stmt(p):
    """
    assignment_stmt : ATOM ASSIGN expr
    assignment_stmt : ATOM ASSIGN command
    """
    p[0] = AssignmentStatement(p[1], p[3], line=p.lineno(1), column=p.lexpos(1))


def p_function_definition_stmt(p):
    """
    function_definition_stmt : FUNCTION ATOM LPAREN function_argument_list RPAREN block
    """
    p[0] = FunctionDefinition(p[2], p[4], p[6], line=p.lineno(1), column=p.lexpos(1))


def p_function_argument_list(p):
    """
    function_argument_list :
    function_argument_list : ATOM
    function_argument_list : ATOM function_argument_list
    """
    if len(p) == 1:
        p[0] = []

    if len(p) == 2:
        p[0] = [p[1]]

    if len(p) > 2:
        p[0] = [p[1]] + p[2]


def p_return_stmt(p):
    """
    return_stmt : RETURN
    return_stmt : RETURN expr
    """
    p[0] = ReturnStatement(p[2], line=p.lineno(1), column=p.lexpos(1))


def p_break_stmt(p):
    """
    break_stmt : BREAK
    """
    p[0] = BreakStatement(line=p.lineno(1), column=p.lexpos(1))


def p_undef_stmt(p):
    """
    undef_stmt : UNDEF ATOM
    """
    p[0] = UndefStatement(p[2], line=p.lineno(1), column=p.lexpos(1))


def p_expr_list(p):
    """
    expr_list : expr
    expr_list : expr COMMA expr_list
    """
    if len(p) == 2:
        p[0] = [p[1]]
        return

    p[0] = [p[1]] + p[3]


def p_expr(p):
    """
    expr : literal
    expr : binary_expr
    expr : set
    expr : call
    expr : subscript
    expr : EOPEN command RPAREN
    expr : LPAREN expr RPAREN
    """
    if len(p) == 4:
        p[0] = p[2]
        return

    p[0] = p[1]


def p_literal(p):
    """
    literal : NUMBER
    literal : HEXNUMBER
    literal : BINNUMBER
    literal : OCTNUMBER
    literal : STRING
    literal : BOOL
    literal : NULL
    """
    p[0] = Literal(p[1], type(p[1]), line=p.lineno(1), column=p.lexpos(1))


def p_symbol(p):
    """
    symbol : ATOM

    """
    p[0] = Symbol(p[1])


def p_call(p):
    """
    call : ATOM LPAREN RPAREN
    call : ATOM LPAREN expr_list RPAREN
    """
    p[0] = FunctionCall(p[1], p[3] if len(p) == 5 else [], line=p.lineno(1), column=p.lexpos(1))


def p_subscript(p):
    """
    subscript : expr LBRACKET expr RBRACKET
    """
    p[0] = Subscript(p[1], p[3], line=p.lineno(1), column=p.lexpos(1))


def p_binary_expr(p):
    """
    binary_expr : expr EQ expr
    binary_expr : expr NE expr
    binary_expr : expr GT expr
    binary_expr : expr GE expr
    binary_expr : expr LT expr
    binary_expr : expr LE expr
    binary_expr : expr PLUS expr
    binary_expr : expr MINUS expr
    binary_expr : expr MUL expr
    binary_expr : expr DIV expr
    binary_expr : expr REGEX expr
    binary_expr : expr AND expr
    binary_expr : expr OR expr
    binary_expr : expr NOT expr
    """
    p[0] = BinaryExpr(p[1], p[2], p[3], line=p.lineno(1), column=p.lexpos(1))


def p_command(p):
    """
    command : parameter_list
    command : parameter_list PIPE command
    """
    if len(p) == 4:
        p[0] = PipeExpr(CommandCall(p[1]), p[3], line=p.lineno(1), column=p.lexpos(1))
        return

    p[0] = CommandCall(p[1], line=p.lineno(1), column=p.lexpos(1))


def p_parameter_list(p):
    """
    parameter_list :
    parameter_list : parameter
    parameter_list : parameter parameter_list
    """
    if len(p) == 1:
        p[0] = []

    if len(p) == 2:
        p[0] = [p[1]]

    if len(p) > 2:
        p[0] = [p[1]] + p[2]


def p_parameter(p):
    """
    parameter : symbol
    parameter : unary_parameter
    parameter : binary_parameter
    """
    p[0] = p[1]


def p_unary_parameter(p):
    """
    unary_parameter : literal
    unary_parameter : EOPEN expr RPAREN
    """
    if len(p) == 4:
        p[0] = ExpressionExpansion(p[2], line=p.lineno(1), column=p.lexpos(1))
        return

    p[0] = p[1]


def p_binary_parameter(p):
    """
    binary_parameter : ATOM ASSIGN parameter
    binary_parameter : ATOM EQ parameter
    binary_parameter : ATOM NE parameter
    binary_parameter : ATOM GT parameter
    binary_parameter : ATOM GE parameter
    binary_parameter : ATOM LT parameter
    binary_parameter : ATOM LE parameter
    binary_parameter : ATOM REGEX parameter
    binary_parameter : ATOM INC parameter
    binary_parameter : ATOM DEC parameter
    """
    p[0] = BinaryParameter(p[1], p[2], p[3], line=p.lineno(1), column=p.lexpos(1))


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


def p_error(p):
    print("error: {0}".format(p))


lex.lex()
yacc.yacc(debug=False)


def parse(s):
    return yacc.parse(s)
