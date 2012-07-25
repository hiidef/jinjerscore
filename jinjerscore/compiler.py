from itertools import chain
from jinja2 import nodes
from jinja2.compiler import CodeGenerator, operators, find_undeclared
from jinja2.utils import concat, is_python_keyword


js_non_output_nodes = set([nodes.Call])


def generate(node, environment, name, filename, stream=None, defer_init=False):
    """Generate the python source for a node tree."""
    if not isinstance(node, nodes.Template):
        raise TypeError('Can\'t compile non template nodes')
    generator = JinjerscoreGenerator(environment, name, filename, stream, defer_init)
    generator.visit(node)
    if stream is None:
        return generator.stream.getvalue()


class JinjerscoreGenerator(CodeGenerator):

    def __init__(self, *args, **kwargs):
        super(JinjerscoreGenerator, self).__init__(*args, **kwargs)
        self._js_indentation = 0
        self._js_new_lines = 0

    def signature(self, node, frame, extra_kwargs=None, python_call=False):
        for i, arg in enumerate(node.args):
            if i != 0 or python_call:
                self.write(', ')
            self.visit(arg, frame)

        if not python_call:
            return

        # if any of the given keyword arguments is a python keyword
        # we have to make sure that no invalid call is created.
        kwarg_workaround = False
        for kwarg in chain((x.key for x in node.kwargs), extra_kwargs or ()):
            if is_python_keyword(kwarg):
                kwarg_workaround = True
                break

        if not kwarg_workaround:
            for kwarg in node.kwargs:
                self.write(', ')
                self.visit(kwarg, frame)
            if extra_kwargs is not None:
                for key, value in extra_kwargs.iteritems():
                    self.write(', %s=%s' % (key, value))
        if node.dyn_args:
            self.write(', *')
            self.visit(node.dyn_args, frame)

        if kwarg_workaround:
            if node.dyn_kwargs is not None:
                self.write(', **dict({')
            else:
                self.write(', **{')
            for kwarg in node.kwargs:
                self.write('%r: ' % kwarg.key)
                self.visit(kwarg.value, frame)
                self.write(', ')
            if extra_kwargs is not None:
                for key, value in extra_kwargs.iteritems():
                    self.write('%r: %s, ' % (key, value))
            if node.dyn_kwargs is not None:
                self.write('}, **')
                self.visit(node.dyn_kwargs, frame)
                self.write(')')
            else:
                self.write('}')

        elif node.dyn_kwargs is not None:
            self.write(', **')
            self.visit(node.dyn_kwargs, frame)

    def indent_js(self):
        self._js_indentation += 1

    def outdent_js(self, step=1):
        self._js_indentation -= step

    def writeline_js(self, x, node=None, extra=0, js_extra=0, whitespace=False, output=False, end=False):
        """Combination of newline and write."""
        self.newline(node, extra)
        self.newline_js(js_extra)
        if whitespace:
            js_str = 'yield u"%s%s' % (
                '\\n' * self._js_new_lines,
                '    ' * self._js_indentation,
            )
            self._js_new_lines = 0
        else:
            js_str = 'yield u"'
        self.write(js_str)
        self.write_js_stmt(x, node, output, end, end)

    def write_js_stmt(self, x, node=None, output=False, end=False, end_quote=False):
        self.write('<%')
        if output:
            self.write('=')
        x = ' ' + x
        if end:
            self.write_js_stmt_end(x, node, end_quote)
        else:
            self.write(x)

    def write_js_stmt_end(self, x, node=None, end_quote=False):
        self.write(x + ' %>')
        if end_quote:
            self.write('"')

    def newline_js(self, extra=0):
        """Add one or more newlines before the next write."""
        self._js_new_lines = max(self._js_new_lines, 1 + extra)

    # -- Statement Visitors

    def visit_For(self, node, frame):
        # when calculating the nodes for the inner frame we have to exclude
        # the iterator contents from it
        for name in node.find_all(nodes.Name):
            if name.ctx == 'store' and name.name == 'loop':
                self.fail('Can\'t assign to special loop variable '
                          'in for-loop target', name.lineno)

        # We rename the special loop variables, to distinguish them
        # from recursive loop() calls
        for var in node.find_all(nodes.Getattr):
            for name in var.find_all(nodes.Name):
                if name.ctx == 'load':
                    name.name = 'l_loop'

        if node.else_:
            iteration_indicator = self.temporary_identifier()

        special_loop = 'l_loop' in find_undeclared(node.iter_child_nodes(only=('body',)), ('l_loop',))

        if node.recursive:
            self.writeline_js('var loop = function(iter) {', node, whitespace=True, end=True)
            self.indent_js()
        if node.else_:
            self.writeline_js('var %s = 1' % iteration_indicator, node, whitespace=True, end=True)

        # If we're accessing the special loop variables and there's a filter test on the loop,
        # we need to do the filtering beforehand
        if special_loop and node.test is not None:
            filtered_var = self.temporary_identifier()
            self.writeline_js('var %s = _.filter(' % filtered_var, node, whitespace=True)
            if node.recursive:
                self.write('iter')
            else:
                self.visit(node.iter, frame)
            self.write(', function(item) { return ')
            self.visit(node.test, frame)
            self.write_js_stmt_end(' })', end_quote=True)
        self.writeline_js('_.each(', node, whitespace=True)
        if special_loop and node.test is not None:
            self.write(filtered_var)
        elif node.recursive:
            self.write('iter')
        else:
            self.visit(node.iter, frame)
        self.write(', ')
        self.write('function(')
        self.visit(node.target, frame)
        self.write_js_stmt_end(', index0, iter) {', end_quote=True)
        self.indent_js()

        # If we don't access the special loop variables inside this loop, then any filtering of the
        # collection becomes a continue
        if not special_loop and node.test is not None:
            self.writeline_js('if(!(', node, whitespace=True)
            self.visit(node.test, frame)
            self.write_js_stmt_end(')) { continue; }', end_quote=True)
        if special_loop:
            self.writeline_js('var l_loop = {index0: index0, index: index0 + 1, first: index0 == 0, length: iter.length}', node, whitespace=True, end=True)
            self.writeline_js('l_loop.revindex = iter.length - l_loop.index0', node, whitespace=True, end=True)
            self.writeline_js('l_loop.revindex0 = l_loop.revindex - 1', node, whitespace=True, end=True)
            self.writeline_js('l_loop.last = l_loop.revindex0 == 0', node, whitespace=True, end=True)
            self.writeline_js('l_loop.cycle = function() { return arguments.length ? arguments[index0 % arguments.length] : \'\' }}', whitespace=True, end=True)
        for body_node in node.body:
            self.visit(body_node, frame)
        if node.else_:
            self.writeline_js('%s = 0' % iteration_indicator, node, whitespace=True, end=True)

        self.outdent_js()
        self.writeline_js('})', node, whitespace=True, end=True)
        if node.else_:
            self.writeline_js('if(%s) {' % iteration_indicator, node, whitespace=True, end=True)
            self.indent_js()
            for else_node in node.else_:
                self.visit(else_node, frame)
            self.outdent_js()
            self.writeline_js('}', node, whitespace=True, end=True)
        if node.recursive:
            self.outdent_js()
            self.writeline_js('}', end=True, whitespace=True)
            self.writeline_js('loop(', node, whitespace=True)
            self.visit(node.iter, frame)
            self.write_js_stmt_end(')', end_quote=True)

    def visit_If(self, node, frame):
        if_frame = frame.soft()
        self.writeline_js('if(', node)
        self.visit(node.test, if_frame)
        self.write_js_stmt_end(') {', end_quote=True)
        self.indent_js()
        self.blockvisit(node.body, if_frame)
        self.outdent_js()
        self.writeline_js('}', whitespace=True)
        if node.else_:
            self.write_js_stmt_end('else {', end_quote=True)
            self.indent_js()
            self.blockvisit(node.else_, if_frame)
            self.writeline_js('}', whitespace=True)
        self.write_js_stmt_end('', end_quote=True)

    def visit_Output(self, node, frame):
        # if we have a known extends statement, we don't output anything
        # if we are in a require_output_check section
        if self.has_known_extends and frame.require_output_check:
            return

        if self.environment.finalize:
            finalize = lambda x: unicode(self.environment.finalize(x))
        else:
            finalize = unicode

        # if we are inside a frame that requires output checking, we do so
        outdent_later = False
        if frame.require_output_check:
            self.writeline('if parent_template is None:')
            self.indent()
            outdent_later = True

        # try to evaluate as many chunks as possible into a static
        # string at compile time.
        body = []
        for child in node.nodes:
            try:
                const = child.as_const(frame.eval_ctx)
            except nodes.Impossible:
                body.append(child)
                continue
            # the frame can't be volatile here, becaus otherwise the
            # as_const() function would raise an Impossible exception
            # at that point.
            try:
                if frame.eval_ctx.autoescape:
                    if hasattr(const, '__html__'):
                        const = const.__html__()
                    else:
                        const = escape(const)
                const = finalize(const)
            except Exception:
                # if something goes wrong here we evaluate the node
                # at runtime for easier debugging
                body.append(child)
                continue
            if body and isinstance(body[-1], list):
                body[-1].append(const)
            else:
                body.append([const])

        # if we have less than 3 nodes or a buffer we yield or extend/append
        if len(body) < 3 or frame.buffer is not None:
            if frame.buffer is not None:
                # for one item we append, for more we extend
                if len(body) == 1:
                    self.writeline('%s.append(' % frame.buffer)
                else:
                    self.writeline('%s.extend((' % frame.buffer)
                self.indent()
            for item in body:
                if isinstance(item, list):
                    val = repr(concat(item))
                    if frame.buffer is None:
                        self.writeline('yield ' + val)
                    else:
                        self.writeline(val + ', ')
                else:
                    if frame.buffer is None:
                        self.writeline('yield ', item)
                    else:
                        self.newline(item)
                    self.write('u"<%')
                    if item.__class__ not in js_non_output_nodes:
                        self.write('=')
                    self.write(' ')
                    self.visit(item, frame)
                    self.write(' %>"')
                    if frame.buffer is not None:
                        self.write(', ')
            if frame.buffer is not None:
                # close the open parentheses
                self.outdent()
                self.writeline(len(body) == 1 and ')' or '))')

        # otherwise we create a format string as this is faster in that case
        else:
            format = []
            arguments = []
            for item in body:
                if isinstance(item, list):
                    format.append(concat(item).replace('%', '%%'))
                else:
                    format.append('%s')
                    arguments.append(item)
            self.writeline('yield ')
            self.write(repr(concat(format)) + ' % (')
            idx = -1
            self.indent()
            for i, argument in enumerate(arguments):
                self.newline(argument)
                self.write('u"<%')
                if argument.__class__ not in js_non_output_nodes:
                    self.write('=')
                self.write(' ')
                self.visit(argument, frame)
                self.write(' %>",')
            self.outdent()
            self.writeline(')')

        if outdent_later:
            self.outdent()

    def visit_Assign(self, node, frame):
        self.newline(node)
        if frame.toplevel:
            assignment_frame = frame.copy()
            assignment_frame.toplevel_assignments = set()
        else:
            assignment_frame = frame
        self.writeline_js('var ')
        self.visit(node.target, assignment_frame)
        self.write(' = ')
        self.visit(node.node, frame)
        self.write_js_stmt_end('', end_quote=True)

    # -- Expression Visitors

    def visit_Name(self, node, frame):
        self.write(node.name)

    def visit_List(self, node, frame):
        self.write('[')
        for idx, item in enumerate(node.items):
            if idx and idx != len(node.items) - 1:
                self.write(', ')
            self.visit(item, frame)
        self.write(']')

    visit_Tuple = visit_List

    # These two helper functions are copied and pasted from jinja2.compiler,
    # because they are del'd after they are used there.
    def binop(operator, interceptable=True):
        def visitor(self, node, frame):
            if self.environment.sandboxed and \
               operator in self.environment.intercepted_binops:
                # TODO: Sandboxed environments have not yet been taken into account
                self.write('environment.call_binop(context, %r, ' % operator)
                self.visit(node.left, frame)
                self.write(', ')
                self.visit(node.right, frame)
            else:
                self.write('(')
                self.visit(node.left, frame)
                self.write(' %s ' % operator)
                self.visit(node.right, frame)
            self.write(')')
        return visitor

    def uaop(operator, interceptable=True):
        def visitor(self, node, frame):
            if self.environment.sandboxed and \
               operator in self.environment.intercepted_unops:
                # TODO: Sandboxed environments have not yet been taken into account
                self.write('environment.call_unop(context, %r, ' % operator)
                self.visit(node.node, frame)
            else:
                self.write('(' + operator)
                self.visit(node.node, frame)
            self.write(')')
        return visitor

    visit_And = binop('&&', interceptable=False)
    visit_Or = binop('||', interceptable=False)
    visit_Not = uaop('!', interceptable=False)
    del binop, uaop

    def visit_FloorDiv(self, node, frame):
        if self.environment.sandboxed and operator in self.environment.intercepted_binops:
            # TODO: Sandboxed environments have not yet been taken into account
            self.write('environment.call_binop(context, %r, ' % operator)
            self.visit(node.left, frame)
            self.write(', ')
            self.visit(node.right, frame)
        else:
            self.write('~~(')
            self.visit(node.left, frame)
            self.write(' / ')
            self.visit(node.right, frame)
        self.write(')')

    def visit_Pow(self, node, frame):
        if self.environment.sandboxed and operator in self.environment.intercepted_binops:
            # TODO: Sandboxed environments have not yet been taken into account
            self.write('environment.call_binop(context, %r, ' % operator)
            self.visit(node.left, frame)
            self.write(', ')
            self.visit(node.right, frame)
        else:
            self.write('Math.pow(')
            self.visit(node.left, frame)
            self.write(', ')
            self.visit(node.right, frame)
        self.write(')')

    def visit_Concat(self, node, frame):
        self.write('[')
        for i, arg in enumerate(node.nodes):
            self.visit(arg, frame)
            if i < len(node.nodes) - 1:
                self.write(', ')
        self.write('].join(\'\')')

    def visit_Compare(self, node, frame):
        # since underscore's in/not in semantics differ syntactically
        # from python/jinja, we need to special case these. My gut says
        # the correct way to do this would be to add special Node types
        # for in and not in comparisons, but Jinja prohibits adding
        # custom node types, and I don't want to cross Armin by working
        # around that.
        if node.ops[0].op not in ['in', 'notin']:
            self.visit(node.expr, frame)
        for op in node.ops:
            if op.op in ['in', 'notin']:
                if op.op == 'notin':
                    self.write('!')
                self.write('(_.indexOf(')
                self.visit(op, frame)
                self.write(', ')
                self.visit(node.expr, frame)
                self.write(') != -1)')
            else:
                self.visit(op, frame)

    def visit_Operand(self, node, frame):
        if node.op not in ['in', 'notin']:
            self.write(' %s ' % operators[node.op])
        self.visit(node.expr, frame)

    def visit_Getattr(self, node, frame):
        self.visit(node.node, frame)
        self.write('[%r]' % node.attr)

    def visit_Getitem(self, node, frame):
        if isinstance(node.arg, nodes.Slice):
            # The third 'step' argument to python-style slicing
            # needs to be implemented with a _.filter that wraps
            # the result of the sequential slice. As a result, we
            # have the 'step' logic here, rather than in visit_Slice
            if node.arg.step is not None:
                self.write('_.filter(')
            self.visit(node.node, frame)
            self.write('.slice(')
            self.visit(node.arg, frame)
            self.write(')')
            if node.arg.step is not None:
                self.write(', function(item, idx) { return idx % ')
                self.visit(node.arg.step, frame)
                self.write(' })')
        else:
            self.visit(node.node, frame)
            self.write('[')
            self.visit(node.arg, frame)
            self.write(']')

    def visit_Slice(self, node, frame):
        if node.start is not None:
            self.visit(node.start, frame)
        else:
            self.write('0')
        if node.stop is not None:
            self.write(', ')
            self.visit(node.stop, frame)

    # def visit_Filter(self, node, frame):
    #     self.write(self.filters[node.name] + '(')
    #     func = self.environment.filters.get(node.name)
    #     if func is None:
    #         self.fail('no filter named %r' % node.name, node.lineno)
    #     if getattr(func, 'contextfilter', False):
    #         self.write('context, ')
    #     elif getattr(func, 'evalcontextfilter', False):
    #         self.write('context.eval_ctx, ')
    #     elif getattr(func, 'environmentfilter', False):
    #         self.write('environment, ')

    #     # if the filter node is None we are inside a filter block
    #     # and want to write to the current buffer
    #     if node.node is not None:
    #         self.visit(node.node, frame)
    #     elif frame.eval_ctx.volatile:
    #         self.write('(context.eval_ctx.autoescape and'
    #                    ' Markup(concat(%s)) or concat(%s))' %
    #                    (frame.buffer, frame.buffer))
    #     elif frame.eval_ctx.autoescape:
    #         self.write('Markup(concat(%s))' % frame.buffer)
    #     else:
    #         self.write('concat(%s)' % frame.buffer)
    #     self.signature(node, frame)
    #     self.write(')')

    # def visit_Test(self, node, frame):
    #     self.write(self.tests[node.name] + '(')
    #     if node.name not in self.environment.tests:
    #         self.fail('no test named %r' % node.name, node.lineno)
    #     self.visit(node.node, frame)
    #     self.signature(node, frame)
    #     self.write(')')

    def visit_CondExpr(self, node, frame):
        def write_expr2():
            if node.expr2 is not None:
                return self.visit(node.expr2, frame)
            self.write('throw "the ternary expression on %s evaluated to false and '
                       'no else section was defined."' % self.position(node))
        self.write('(')
        self.visit(node.test, frame)
        self.write(' ? ')
        self.visit(node.expr1, frame)
        self.write(' : ')
        write_expr2()
        self.write(')')

    def visit_Call(self, node, frame, forward_caller=False):
        python_call = isinstance(node.node, nodes.ExtensionAttribute)
        if python_call:
            if self.environment.sandboxed:
                self.write('environment.call(context, ')
            else:
                self.write('context.call(')
        self.visit(node.node, frame)
        extra_kwargs = forward_caller and {'caller': 'caller'} or None
        if not python_call:
            self.write('(')
        self.signature(node, frame, extra_kwargs, python_call)
        self.write(')')

    # def visit_Keyword(self, node, frame):
    #     self.write(node.key + '=')
    #     self.visit(node.value, frame)

    # # -- Unused nodes for extensions

    # def visit_MarkSafe(self, node, frame):
    #     self.write('Markup(')
    #     self.visit(node.expr, frame)
    #     self.write(')')

    # def visit_MarkSafeIfAutoescape(self, node, frame):
    #     self.write('(context.eval_ctx.autoescape and Markup or identity)(')
    #     self.visit(node.expr, frame)
    #     self.write(')')

    # def visit_EnvironmentAttribute(self, node, frame):
    #     self.write('environment.' + node.name)

    # def visit_ExtensionAttribute(self, node, frame):
    #     self.write('environment.extensions[%r].%s' % (node.identifier, node.name))

    # def visit_ImportedName(self, node, frame):
    #     self.write(self.import_aliases[node.importname])

    # def visit_InternalName(self, node, frame):
    #     self.write(node.name)

    # def visit_ContextReference(self, node, frame):
    #     self.write('context')

    # def visit_Continue(self, node, frame):
    #     self.writeline('continue', node)

    # def visit_Break(self, node, frame):
    #     self.writeline('break', node)

    # def visit_Scope(self, node, frame):
    #     scope_frame = frame.inner()
    #     scope_frame.inspect(node.iter_child_nodes())
    #     aliases = self.push_scope(scope_frame)
    #     self.pull_locals(scope_frame)
    #     self.blockvisit(node.body, scope_frame)
    #     self.pop_scope(aliases, scope_frame)

    # def visit_EvalContextModifier(self, node, frame):
    #     for keyword in node.options:
    #         self.writeline('context.eval_ctx.%s = ' % keyword.key)
    #         self.visit(keyword.value, frame)
    #         try:
    #             val = keyword.value.as_const(frame.eval_ctx)
    #         except nodes.Impossible:
    #             frame.eval_ctx.volatile = True
    #         else:
    #             setattr(frame.eval_ctx, keyword.key, val)

    # def visit_ScopedEvalContextModifier(self, node, frame):
    #     old_ctx_name = self.temporary_identifier()
    #     safed_ctx = frame.eval_ctx.save()
    #     self.writeline('%s = context.eval_ctx.save()' % old_ctx_name)
    #     self.visit_EvalContextModifier(node, frame)
    #     for child in node.body:
    #         self.visit(child, frame)
    #     frame.eval_ctx.revert(safed_ctx)
    #     self.writeline('context.eval_ctx.revert(%s)' % old_ctx_name)
