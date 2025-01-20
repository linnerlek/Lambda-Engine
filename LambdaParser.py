import ply.yacc as yacc
from LambdaLexer import tokens

def p_exprStart_1(p):
  'exprStart : expr SEMI'
  p[0] = p[1]

def p_exprStart_2(p):
  'exprStart : expr LBRACKET NAME EQUALS expr RBRACKET SEMI'
  p[0] = ['subst', p[1], p[3].upper(), p[5]]

def p_exprStart_3(p):
  'exprStart : FV LBRACKET expr RBRACKET SEMI'
  p[0] = ['freevars', p[3]]

def p_exprStart_4(p):
  'exprStart : ALPHA LBRACKET expr COMMA NAME RBRACKET SEMI'
  p[0] = ['alpha', p[3], p[5].upper()]

def p_expr_1(p):
  'expr : NUMBER'
  p[0] = ['num', p[1]]

def p_expr_2(p):
  'expr : NAME'
  p[0] = ['name', p[1].upper()]

def p_expr_3(p):
  'expr : LPAREN expr expr RPAREN'
  if p[2][0] == 'lambda':
    p[0] = ['apply', p[2], p[3], True] # beta-reduction possible
  else:
    p[0] = ['apply', p[2], p[3], False] # beta-reduction not possible

def p_expr_4(p):
  'expr : LPAREN LAMBDA NAME expr RPAREN'
  p[0] = ['lambda', p[3].upper(), p[4]]

def p_expr_5(p):
  'expr : LPAREN OP expr expr RPAREN'
  p[0] = [p[2], p[3], p[4]]

def p_error(p):
  print("Syntax error in input!")

parser = yacc.yacc()

