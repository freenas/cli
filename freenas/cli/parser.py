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

import six
import ply.lex as lex
import ply.yacc as yacc


def ASTObject(name, *args):
    def str(self):
        return "<{0} {1}>".format(
            self.__class__.__name__,
            ' '.join(["{0} '{1}'".format(i, getattr(self, i)) for i in args])
        )

    def init(self, *values, **kwargs):
        for idx, i in enumerate(values):
            setattr(self, args[idx], i)

        p = kwargs.get('p')
        if p:
            self.file = p.parser.filename
            self.line = p.lineno(1)
            self.column = p.lexpos(1)

    dct = {k: None for k in args}
    dct['__init__'] = init
    dct['__str__'] = str
    dct['__repr__'] = str
    return type(name, (), dct)


Comment = ASTObject('Comment', 'text')
Symbol = ASTObject('Symbol', 'name')
Set = ASTObject('Set', 'value')
UnaryExpr = ASTObject('UnaryExpr', 'expr', 'op')
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
    'MUL', 'DIV', 'BOOL', 'NULL', 'EOPEN', 'COPEN', 'LBRACE',
    'RBRACE', 'LBRACKET', 'RBRACKET', 'NEWLINE', 'COLON'
]


def t_COMMENT(t):
    r'\#.*'
    pass


def t_IPV4(t):
    r'\d+\.\d+\.\d+\.\d+'
    t.type = 'ATOM'
    return t


def t_SIZE(t):
    r'\d+[kKmMgGtT]B?'
    t.type = 'STRING'
    return t


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
    r'[0-9a-zA-Z_\/-\/][0-9a-zA-Z_\-\.\/#@\:]*'
    t.type = reserved.get(t.value, 'ATOM')
    return t


t_ignore = ' \t'
t_LBRACE = r'\{'
t_RBRACE = r'\}'
t_LBRACKET = r'\['
t_RBRACKET = r'\]'
t_PIPE = r'\|'
t_EOPEN = r'\$\('
t_COPEN = r'\$\{'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_ASSIGN = r'='
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
t_COLON = ':'


precedence = (
    ('left', 'MINUS', 'PLUS'),
    ('left', 'MUL', 'DIV'),
    ('left', 'AND', 'OR'),
    ('right', 'NOT'),
    ('left', 'REGEX'),
    ('left', 'GT', 'LT'),
    ('left', 'GE', 'LE'),
    ('left', 'EQ', 'NE'),
    ('left', 'INC', 'DEC')
)


def t_ESCAPENL(t):
    r'\\\s*[\n\#]'
    t.lexer.lineno += 1
    pass


def t_NEWLINE(t):
    r'[\n;]+'
    t.lexer.lineno += len(t.value)
    return t


def t_error(t):
    raise SyntaxError("Illegal character '%s'" % t.value[0])


def p_stmt_list(p):
    """
    stmt_list : stmt
    stmt_list : stmt NEWLINE
    stmt_list : stmt NEWLINE stmt_list
    """
    if len(p) in (2, 3):
        p[0] = [p[1]]
        return

    p[0] = [p[1]] + p[3]


def p_stmt_list_2(p):
    """
    stmt_list : NEWLINE stmt_list
    """
    p[0] = p[2]


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
    stmt : command
    stmt : call
    """
    p[0] = p[1]


def p_block(p):
    """
    block : LBRACE stmt_list RBRACE
    """
    p[0] = p[2]


def p_block_2(p):
    """
    block : LBRACE NEWLINE stmt_list RBRACE
    """
    p[0] = p[3]


def p_if_stmt(p):
    """
    if_stmt : IF LPAREN expr RPAREN block
    if_stmt : IF LPAREN expr RPAREN block ELSE block
    """
    p[0] = IfStatement(p[3], p[5], p[7] if len(p) == 8 else [], p=p)


def p_for_stmt_1(p):
    """
    for_stmt : FOR LPAREN ATOM IN expr RPAREN block
    """
    p[0] = ForStatement(p[3], p[5], p[7], p=p)


def p_for_stmt_2(p):
    """
    for_stmt : FOR LPAREN ATOM COMMA ATOM IN expr RPAREN block
    """
    p[0] = ForStatement((p[3], p[5]), p[7], p[9], p=p)


def p_while_stmt(p):
    """
    while_stmt : WHILE LPAREN expr RPAREN block
    """
    p[0] = WhileStatement(p[3], p[5], p=p)


def p_assignment_stmt(p):
    """
    assignment_stmt : ATOM ASSIGN expr
    assignment_stmt : subscript ASSIGN expr
    """
    p[0] = AssignmentStatement(p[1], p[3], p=p)


def p_function_definition_stmt_1(p):
    """
    function_definition_stmt : FUNCTION ATOM LPAREN RPAREN block
    """
    p[0] = FunctionDefinition(p[2], [], p[5], p=p)


def p_function_definition_stmt_2(p):
    """
    function_definition_stmt : FUNCTION ATOM LPAREN function_argument_list RPAREN block
    """
    p[0] = FunctionDefinition(p[2], p[4], p[6], p=p)


def p_function_definition_stmt_3(p):
    """
    function_definition_stmt : FUNCTION ATOM LPAREN RPAREN NEWLINE block
    """
    p[0] = FunctionDefinition(p[2], [], p[6], p=p)


def p_function_definition_stmt_4(p):
    """
    function_definition_stmt : FUNCTION ATOM LPAREN function_argument_list RPAREN NEWLINE block
    """
    p[0] = FunctionDefinition(p[2], p[4], p[7], p=p)


def p_function_argument_list(p):
    """
    function_argument_list : ATOM
    function_argument_list : ATOM function_argument_list
    """
    if len(p) == 2:
        p[0] = [p[1]]

    if len(p) > 2:
        p[0] = [p[1]] + p[2]


def p_return_stmt(p):
    """
    return_stmt : RETURN
    return_stmt : RETURN expr
    """
    p[0] = ReturnStatement(p[2], p=p)


def p_break_stmt(p):
    """
    break_stmt : BREAK
    """
    p[0] = BreakStatement(p=p)


def p_undef_stmt(p):
    """
    undef_stmt : UNDEF ATOM
    """
    p[0] = UndefStatement(p[2], p=p)


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
    expr : symbol
    expr : literal
    expr : array_literal
    expr : dict_literal
    expr : unary_expr
    expr : binary_expr
    expr : call
    expr : subscript
    expr : expr_expansion
    expr : LPAREN expr RPAREN
    expr : COPEN expr RBRACE
    """
    if len(p) == 4:
        p[0] = p[2]
        return

    p[0] = p[1]


def p_expr_expansion(p):
    """
    expr_expansion : EOPEN command RPAREN
    """
    p[0] = p[2]


def p_array_literal(p):
    """
    array_literal : LBRACKET RBRACKET
    array_literal : LBRACKET expr_list RBRACKET
    """
    if len(p) == 3:
        p[0] = Literal([], list)
        return

    p[0] = Literal(p[2], list)


def p_dict_literal_1(p):
    """
    dict_literal : LBRACE RBRACE
    """
    p[0] = Literal(dict(), dict)


def p_dict_literal_2(p):
    """
    dict_literal : LBRACE dict_pair_list RBRACE
    """
    p[0] = Literal(dict(p[2]), dict)


def p_dict_pair_list(p):
    """
    dict_pair_list : dict_pair
    dict_pair_list : dict_pair COMMA dict_pair_list
    """
    if len(p) == 2:
        p[0] = [p[1]]
        return

    p[0] = [p[1]] + p[3]


def p_dict_pair(p):
    """
    dict_pair : STRING COLON expr
    """
    p[0] = (p[1], p[3])


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
    p[0] = Literal(p[1], type(p[1]), p=p)


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
    p[0] = FunctionCall(p[1], p[3] if len(p) == 5 else [], p=p)


def p_subscript(p):
    """
    subscript : expr LBRACKET expr RBRACKET
    """
    p[0] = Subscript(p[1], p[3], p=p)


def p_unary_expr(p):
    """
    unary_expr : NOT expr
    """
    p[0] = UnaryExpr(p[2], p[1], p=p)


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
    p[0] = BinaryExpr(p[1], p[2], p[3], p=p)


def p_command_1(p):
    """
    command : command_item
    command : command_item parameter_list
    """
    if len(p) == 2:
        p[0] = CommandCall([p[1]], p=p)
        return

    p[0] = CommandCall([p[1]] + p[2], p=p)


def p_command_2(p):
    """
    command : command_item PIPE command
    command : command_item parameter_list PIPE command
    """
    if len(p) == 4:
        p[0] = PipeExpr(CommandCall([p[1]], p=p), p[3], p=p)
        return

    p[0] = PipeExpr(CommandCall([p[1]] + p[2], p=p), p[4], p=p)


def p_command_item_1(p):
    """
    command_item : LIST
    command_item : NUMBER
    """
    p[0] = Symbol(p[1], p=p)


def p_command_item_2(p):
    """
    command_item : UP
    command_item : symbol
    """
    p[0] = p[1]


def p_command_item_3(p):
    """
    command_item : COPEN expr RBRACE
    """
    p[0] = ExpressionExpansion(p[2], p=p)


def p_parameter_list(p):
    """
    parameter_list : parameter
    parameter_list : parameter parameter_list
    """
    if len(p) == 2:
        p[0] = [p[1]]

    if len(p) > 2:
        p[0] = [p[1]] + p[2]


def p_parameter(p):
    """
    parameter : set_parameter
    parameter : binary_parameter
    """
    p[0] = p[1]


def p_set_parameter(p):
    """
    set_parameter : unary_parameter
    set_parameter : unary_parameter COMMA set_parameter
    """
    if len(p) == 4:
        if isinstance(p[3], list):
            p[0] = [p[1]] + p[3]
        else:
            p[0] = [p[1], p[3]]
        return

    p[0] = p[1]


def p_unary_parameter(p):
    """
    unary_parameter : symbol
    unary_parameter : literal
    unary_parameter : array_literal
    unary_parameter : dict_literal
    unary_parameter : COPEN expr RBRACE
    """
    if len(p) == 4:
        p[0] = ExpressionExpansion(p[2], p=p)
        return

    p[0] = p[1]


def p_unary_parameter_1(p):
    """
    unary_parameter : LIST
    """
    p[0] = Symbol(p[1])


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
    p[0] = BinaryParameter(p[1], p[2], p[3], p=p)


def p_error(p):
    raise SyntaxError(str(p))


lexer = lex.lex()
parser = yacc.yacc(debug=False)


def parse(s, filename):
    lexer.lineno = 1
    parser.filename = filename
    return parser.parse(s, lexer=lexer)


def unparse(token, indent=0):
    def ind(s):
        return '\t' * indent + s

    if isinstance(token, list):
        return '\n'.join(ind(unparse(i)) for i in token)

    if isinstance(token, Comment):
        return '# ' + token.text

    if isinstance(token, Literal):
        if token.value is None:
            return 'none'

        if token.type is str:
            return '"{0}"'.format(token.value)

        if token.type is bool:
            return 'true' if token.value else 'false'

        if token.type is int:
            return str(token.value)

        if issubclass(token.type, list):
            return '[' + ', '.join(unparse(Literal(i, type(i))) for i in token.value) + ']'

        if issubclass(token.type, dict):
            return '{' + ', '.join('{0}: {1}'.format(
                unparse(Literal(k, type(k))),
                unparse(Literal(v, type(v)))
            ) for k, v in token.value.items()) + '}'

        return str(token.value)

    if isinstance(token, BinaryParameter):
        return ind(''.join([token.left.value, token.op, unparse(token.right)]))

    if isinstance(token, Symbol):
        return ind(token.name)

    if isinstance(token, CommandCall):
        return ind(' '.join(unparse(i) for i in token.args))

    if isinstance(token, Subscript):
        return ind('{0}[{1}]'.format(unparse(token.expr), unparse(token.index)))

    if isinstance(token, AssignmentStatement):
        if isinstance(token.name, six.string_types):
            lhs = token.name
        else:
            lhs = unparse(token.name)

        return ind('{0} = {1}'.format(lhs, unparse(token.expr)))

    if isinstance(token, BinaryExpr):
        return ind(' '.join([unparse(token.left), token.op, unparse(token.right)]))

    if isinstance(token, IfStatement):
        lines = [ind('if ({0}) {{'.format(unparse(token.expr)))]
        for i in token.body:
            lines.append(unparse(i, indent + 1))

        lines.append(ind('}'))
        return '\n'.join(lines)

    if isinstance(token, WhileStatement):
        lines = [ind('while ({0}) {{'.format(unparse(token.expr)))]
        for i in token.body:
            lines.append(unparse(i, indent + 1))

        lines.append(ind('}'))
        return '\n'.join(lines)

    if isinstance(token, FunctionDefinition):
        lines = [ind('function {0}({1}) {{'.format(token.name, ', '.join(token.args)))]
        for i in token.body:
            lines.append(unparse(i, indent + 1))

        lines.append(ind('}'))
        return '\n'.join(lines)

    return ''
