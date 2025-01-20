import ply.lex as lex

reserved = { 'lambda': 'LAMBDA', 'fv': 'FV', 'alpha': 'ALPHA' }

tokens = ['NUMBER', 'LPAREN', 'RPAREN', 'OP', 'NAME', 'EQUALS', 'LBRACKET', 'RBRACKET', 'SEMI', 'COMMA'] + list(reserved.values())

t_LPAREN = r'\('
t_RPAREN = r'\)'
t_OP = r'\+ | - | \* | /'
t_SEMI = r';'
t_COMMA = r','
t_EQUALS = r'='
t_LBRACKET = r'\['
t_RBRACKET = r'\]'

def t_NAME(t):
  r'[a-zA-Z][_a-zA-Z0-9]*'
  t.type = reserved.get(t.value.lower(),'NAME')
  return t

def t_NUMBER(t):
  r'[0-9]+(\.[0-9]*)?'
  t.value = float(t.value)
  return t

# Ignored characters
t_ignore = " \r\n\t"
t_ignore_COMMENT = r'\#.*'

def t_error(t):
  print("Illegal character '%s'" % t.value[0])
  raise Exception('LEXER ERROR')

lexer = lex.lex()
