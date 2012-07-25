from jinja2 import nodes
from jinja2.parser import Parser, _compare_operators


class JinjerscoreParser(Parser):
    def parse_compare(self):
        # This will generate a tree of Compare nodes when "true" compare operators
        # are mixed with in/not in, or when multiple in/not in operators are used in
        # the same expression. This differs from the canonical implementation,
        # which generates a flat list of operands for a single Compare node in this case.
        # We do this for Underscore's syntactic needs - see
        # jinjerscore.compiler.JinjerscoreGenerator.visit_Compare
        lineno = self.stream.current.lineno
        expr = self.parse_add()
        ops = []
        is_compare = self.stream.current.type in _compare_operators
        while 1:
            token_type = self.stream.current.type
            if token_type in _compare_operators:
                next(self.stream)
                ops.append(nodes.Operand(token_type, self.parse_add()))
                is_compare = True
            elif self.stream.skip_if('name:in'):
                if is_compare:
                    expr = nodes.Compare(expr, ops, lineno=lineno)
                expr = nodes.Compare(expr, [nodes.Operand('in', self.parse_add())], lineno=lineno)
                ops = []
                is_compare = False
            elif self.stream.current.test('name:not') and self.stream.look().test('name:in'):
                if is_compare:
                    expr = nodes.Compare(expr, ops, lineno=lineno)
                self.stream.skip(2)
                expr = nodes.Compare(expr, [nodes.Operand('notin', self.parse_add())], lineno=lineno)
                ops = []
                is_compare = False
            else:
                break
            lineno = self.stream.current.lineno
        if not ops:
            return expr
        return nodes.Compare(expr, ops, lineno=lineno)
