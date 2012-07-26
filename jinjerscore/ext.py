import os
from jinja2 import nodes
from jinja2.ext import Extension


class JinjerscoreExtension(Extension):
    # a set of names that trigger the extension.
    tags = set(['jinjerscore'])

    def __init__(self, environment):
        super(JinjerscoreExtension, self).__init__(environment)
        environment.extend(
            generate_underscore=False,
            underscore_base_path=None,
        )

    def parse(self, parser):
        lineno = parser.stream.next().lineno
        # The next expression is the relative path of the file we'd like to generate
        args = [parser.parse_expression()]
        body = parser.parse_statements(['name:endjinjerscore'], drop_needle=True)
        if self.environment.generate_underscore:
            return nodes.CallBlock(self.call_method('_generate_underscore', args),
                                   [], [], body).set_lineno(lineno)
        else:
            return body

    def _generate_underscore(self, path, caller):
        rv = caller()
        with open(os.path.join(self.environment.underscore_base_path, path), 'w') as f:
            f.write(rv)
        return rv
