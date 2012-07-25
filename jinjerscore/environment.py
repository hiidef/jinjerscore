from jinja2.environment import Environment
from jinja2.utils import _encode_filename
from jinjerscore.compiler import generate
from jinjerscore.parser import JinjerscoreParser


class JinjerscoreEnvironment(Environment):
    def _parse(self, source, name, filename):
        return JinjerscoreParser(self, source, name, _encode_filename(filename)).parse()

    def _generate(self, source, name, filename, defer_init=False):
        return generate(source, self, name, filename, defer_init=defer_init)
