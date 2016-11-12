import os
import glpk
import shutil
import uuid
import tempfile
from IPython.core.magic import Magics, magics_class, cell_magic, line_magic
from getopt import GetoptError


class GMPLStore(object):
    def __init__(self):
        self.model = {}
        self.data = {}

    def add_model(self, name, code):
        self.model[name] = code

    def add_data(self, name, code):
        self.data[name] = code

    def list_models(self):
        if self.model:
            for name in self.model.keys():
                print(name)
        else:
            print("No models stored.")

    def list_data(self):
        if self.data:
            for name in self.data.keys():
                print(name)
        else:
            print("No data stored.")

    def clear_models(self):
        self.model = {}

    def clear_data(self):
        self.data = {}

    def show_model(self, name):
        print(self.model[name])

    def show_data(self, name):
        print(self.data[name])


class GMPLResult(object):
    def __init__(self):
        self.status = None
        self.objval = None
        self.variables = None

    def __repr__(self):
        output_string = ''

        if self.status == 'opt':
            status_string = 'Solution found is optimal.'
        elif self.status == 'undef':
            status_string = 'Solution found is undefined.'
        elif self.status == 'feas':
            status_string = ('Solution found is feasible, '
                             'but not necessarily optimal.')
        elif self.status == 'infeas':
            status_string = 'Solution found is infeasible.'
        elif self.status == 'nofeas':
            status_string = 'Model is infeasible.'
        elif self.status == 'unbnd':
            status_string = 'Model is unbounded.'

        if self.status:
            output_string += "Status: {0}\n".format(status_string)

        if self.objval:
            output_string += "Objective value: {0}\n".format(self.objval)

        if self.variables:
            output_string += "Decision variables:\n"
            for var, val in self.variables.items():
                output_string += "    {0} = {1}\n".format(var, val)

        return output_string


@magics_class
class GMPLMagics(Magics):
    @cell_magic
    def model(self, line, cell):
        '''
        %%model <name of model>
        '''
        # Get interactive shell
        ip = self.shell

        # Get access to gmpl store, create it if it doesn't exist
        gmpl_store_exists = ip.ev("'_gmpl_store' in globals()")
        if not gmpl_store_exists:
            gmpl_store = GMPLStore()
            ip.user_ns['_gmpl_store'] = gmpl_store
        else:
            gmpl_store = ip.user_ns['_gmpl_store']

        # Get user's model name
        opts, args = self.parse_options(line, '', mode='list')
        if len(args) != 1:
            print("Usage: %%model <name of model>")
            return
        else:
            model_name = args[0]

        # Put user's model in gmpl store
        # Add a new line to the end to avoid stupid GLPK warnings
        cell += '\n'
        gmpl_store.add_model(model_name, cell)
        ip.user_ns['_gmpl_store'] = gmpl_store
        print("Model '{0}' stored.".format(model_name))

    @cell_magic
    def data(self, line, cell):
        '''
        %%data <name of data>
        '''
        # Get interactive shell
        ip = self.shell

        # Get access to gmpl store, create it if it doesn't exist
        gmpl_store_exists = ip.ev("'_gmpl_store' in globals()")
        if not gmpl_store_exists:
            gmpl_store = GMPLStore()
            ip.user_ns['_gmpl_store'] = gmpl_store
        else:
            gmpl_store = ip.user_ns['_gmpl_store']

        # Get user's data name
        opts, args = self.parse_options(line, '', mode='list')
        if len(args) != 1:
            print("Usage: %%data <name of model>")
            return
        else:
            data_name = args[0]

        # Put user's data in gmpl store
        gmpl_store.add_data(data_name, cell)
        ip.user_ns['_gmpl_store'] = gmpl_store
        print("Data '{0}' stored.".format(data_name))

    @line_magic
    def solve(self, line):
        '''
        %solve <name of model> <name of data>

        Options:
            --nolog
            --result=
        '''
        # Parse arguments
        # Get model name and data name
        # Get namespace variable names
        args_ok = True
        try:
            opts, args = self.parse_options(line, '', 'nolog', 'result=',
                                            'simplexpresolve', mode='list')
        except GetoptError:
            args_ok = False

        if (not args_ok) or (len(args) == 0) or (len(args) > 2):
            print("Usage: %%solve [options] <name of model> [name of data]")
            print("  Options:")
            print("    --nolog")
            print("    --result=<name of result variable>")
            print("    --simplexpresolve")
            return

        model_name = args[0]
        data_name = args[1] if len(args) == 2 else None
        result_name = opts['result'] if 'result' in opts else None

        # Assume nolog only applies if everything is successful
        # Otherwise, always print the log
        nolog = 'nolog' in opts

        simplexpresolve = 'simplexpresolve' in opts

        # Get IPython shell
        ip = self.shell

        # Get gmpl store from user namespace
        try:
            gmpl_store = ip.user_ns['_gmpl_store']
        except KeyError:
            print('Model and data storage is missing.'
                  'Try storing your model and data again.')
            return

        # Terminal hook helper function
        glpk.env.term_on = True
        glpk.env.term_hook = lambda output: log_file.write(output)

        # Create temporary directory
        temp_dir = tempfile.mkdtemp()

        # Create base_name
        base_name = uuid.uuid4().hex

        # Create output file name
        out_file_name = os.path.join(temp_dir, base_name + '.out')

        # Create log file
        log_file_name = os.path.join(temp_dir, base_name + '.log')
        log_file = open(log_file_name, 'w')

        # Create model file
        # Check if model exists in gmpl store
        model_file_name = os.path.join(temp_dir, base_name + '.mod')
        model_file = open(model_file_name, 'w')
        try:
            model_file.write(gmpl_store.model[model_name])
            model_file.write('\n')
        except KeyError:
            print("Model '{0}' does not exist.".format(model_name))
            return
        finally:
            model_file.close()

        # Create data file, if data is specified
        # Check if data exists in gmpl store
        if data_name:
            data_file_name = os.path.join(temp_dir, base_name + '.dat')
            data_file = open(data_file_name, 'w')
            try:
                data_file.write(gmpl_store.data[data_name])
                data_file.write('\n')
            except KeyError:
                print("Data '{0}' does not exist.".format(data_name))
                return
            finally:
                data_file.close()
        else:
            data_file_name = None

        # Load .mod and .dat files into GLPK
        try:
            lp = glpk.LPX(gmp=(model_file_name, data_file_name, None))
        except RuntimeError:
            pass
        else:
            # Give the model a name in GLPK
            if data_name:
                lp.name = '({0}, {1})'.format(model_name, data_name)
            else:
                lp.name = model_name

            # Set message level of the solver
            msg_lev = lp.MSG_ALL

            # Solve the model using the appropriate method
            if lp.kind is float:
                # LP: simplex method
                # Turn off presolve to get information about infeasibility
                #   and unboundedness
                lp.simplex(msg_lev=msg_lev, presolve=simplexpresolve)
            else:
                # MIP: branch-and-cut
                lp.integer(msg_lev=msg_lev, presolve=True)

            # Write output file
            out_file = open(out_file_name, 'w')
            if lp.kind is float:
                lp.write(sol=out_file_name)
            elif lp.kind is int:
                lp.write(mip=out_file_name)
            out_file.close()

            # Create GLPK output object if desired
            if result_name:
                result = GMPLResult()

                # Determine status
                result.status = lp.status

                # If we have an optimal or feasible solution:
                if result.status in ['opt', 'feas']:
                    # Determine objective value
                    result.objval = lp.obj.value

                    # Determine solution
                    result.variables = {}
                    for col in lp.cols:
                        result.variables[col.name] = col.primal

                # Put information in the user namespace, if desired
                ip.user_ns[result_name] = result

        finally:
            # Close log file
            log_file.close()

        # Print log file to shell
        if not nolog:
            log_file = open(log_file_name, 'r')
            log_text = ''
            for line in log_file:
                # Don't print GLPK log lines regarding which files
                # the model and data are being read from
                if not (line.startswith('Reading model section') or
                        line.startswith('Reading data section') or
                        line.startswith('Writing basic solution') or
                        line.startswith('Writing MIP solution')):
                    # Replace the temporary model file name
                    # with something more human-readable
                    line = line.replace(model_file_name + ':', "Model: Line ")
                    try:
                        line = line.replace(data_file_name + ':', "Data: Line ")
                    except TypeError:   # if data_file_name is None
                        pass
                    log_text += line
            log_file.close()
            print(log_text.rstrip())

        # Read output file to shell
        if not nolog:
            try:
                out_file = open(out_file_name, 'r')
            except FileNotFoundError:
                pass
            else:
                print("========================================" +
                      "========================================")
                out_text = ''
                for line in out_file:
                    out_text += line
                out_file.close()
                print(out_text)

        # Remove the temporary files
        shutil.rmtree(temp_dir)

    @line_magic
    def listmodels(self, line):
        # Get IPython shell
        ip = self.shell

        # Get glpk store
        gmpl_store = ip.user_ns['_gmpl_store']

        # Print models
        gmpl_store.list_models()

    @line_magic
    def listdata(self, line):
        # Get IPython shell
        ip = self.shell

        # Get gmpl store
        gmpl_store = ip.user_ns['_gmpl_store']

        # Print models
        gmpl_store.list_data()

    @line_magic
    def clearmodels(self, line):
        # Get IPython shell
        ip = self.shell

        # Get gmpl store
        gmpl_store = ip.user_ns['_gmpl_store']

        # Print models
        gmpl_store.clear_models()

    @line_magic
    def cleardata(self, line):
        # Get IPython shell
        ip = self.shell

        # Get gmpl store
        gmpl_store = ip.user_ns['_gmpl_store']

        # Print models
        gmpl_store.clear_data()

    @line_magic
    def showmodel(self, line):
        '''
        %showmodel <name of model>
        '''
        # Parse arguments
        # Get model name
        args_ok = True
        try:
            opts, args = self.parse_options(line, '')
        except GetoptError:
            args_ok = False

        args = args.split()

        if (not args_ok) or (len(args) == 0) or (len(args) > 1):
            print("Usage: %%showmodel <name of model>")
            return

        # Get IPython shell
        ip = self.shell

        # Get gmpl store
        gmpl_store = ip.user_ns['_gmpl_store']

        # Print model
        gmpl_store.show_model(args[0])

    @line_magic
    def showdata(self, line):
        '''
        %showdata <name of model>
        '''
        # Parse arguments
        # Get model name
        args_ok = True
        try:
            opts, args = self.parse_options(line, '')
        except GetoptError:
            args_ok = False

        args = args.split()

        if (not args_ok) or (len(args) == 0) or (len(args) > 1):
            print("Usage: %%showdata <name of model>")
            return

        # Get IPython shell
        ip = self.shell

        # Get gmpl store
        gmpl_store = ip.user_ns['_gmpl_store']

        # Print model
        gmpl_store.show_data(args[0])


def load_ipython_extension(ipython):
    # Inject JS for GMPL syntax highlighting
    js_code = '''
        CodeMirror.defineMode('mathprog', function() {
        function wordRegexp(words) {
          return new RegExp("^(?:" + words.join("|") + ")\\\\b", "i");
        }

        var symbolicNames = new RegExp('^[_A-Za-z\xa1-\uffff][_A-Za-z0-9\xa1-\uffff]*');
        var delimiters = new RegExp('^(\\\\+|\\\\-|\\\\*|/|\\\\*\\\\*|\\\\^|&|<|<=|=|==|>=|>|<>|!=|\\\\:=|\\\\:|!|<<|<-)');
        var keywords = wordRegexp(['abs', 'and', 'atan', 'binary', 'by', 'card',
          'ceil', 'check', 'cos', 'cross', 'cross', 'data', 'default', 'diff',
          'dimen', 'display', 'div', 'else', 'end', 'exists', 'exp', 'floor',
          'for', 'forall', 'if', 'integer', 'inter', 'Irand224', 'length',
          'less', 'log', 'log10', 'max', 'maximize', 'min', 'minimize', 'mod',
          'Normal', 'Normal01', 'not', 'or', 'param', 'printf', 'prod', 'round',
          'set', 'setof', 'sin', 'solve', 'sqrt', 'subj to', 'subject to',
          'substr', 'sum', 'symbolic', 'symdiff', 'then', 'tr', 'trunc',
          'Uniform', 'Uniform01', 'union', 'var', 'within', 'table', 'out',
          'gmtime', 'str2time', 'time2str']);

        function tokenIndex(stream, state) {
          if (stream.eatWhile(/[^}]/)) {
            state.tokenize = tokenBase;
            return 'def';
          };
          stream.skipToEnd();
          return 'def';
        }

        function tokenSubscript(stream, state) {
          if (stream.eatWhile(/[^\]]/)) {
            state.tokenize = tokenBase;
            return 'def';
          };
          stream.skipToEnd();
          return 'def';
        }

        function tokenComment(stream, state) {
          if (stream.match(/^.*\*\//)) {
            state.tokenize = tokenBase;
            return 'comment';
          };
          stream.skipToEnd();
          return 'comment';
        }

        function tokenBase(stream, state) {
          // whitespace
          if (stream.eatSpace()) {
            return null;
          }

          // single-line comments
          if (stream.match(/^#/)) {
            stream.skipToEnd();
            return 'comment';
          }

          // block comments
          if (stream.match(/\/\*/)) {
            state.tokenize = tokenComment;
            return tokenComment(stream, state);
          }

          // numberic literals
          if (stream.match(/^[0-9\.+-]/, false)) {
            if (stream.match(/^[+-]?0x[0-9a-fA-F]+[ij]?/)) {
              stream.tokenize = tokenBase;
              return 'number'; };
            if (stream.match(/^[+-]?\d*\.\d+([EeDd][+-]?\d+)?[ij]?/)) { return 'number'; };
            if (stream.match(/^[+-]?\d+([EeDd][+-]?\d+)?[ij]?/)) { return 'number'; };
          }

          // string literals
          if (stream.match(/^[\'\"].*[\'\"]/)) {
            return 'string';
          };

          // keywords
          if (stream.match(keywords)) {
            return 'keyword';
            console.log('keyword matched');
          };

          // indexing expressions
          if (stream.match(/^{/)) {
            state.tokenize = tokenIndex;
            return null;
          };

          // subscripts
          if (stream.match(/^\[/)) {
            state.tokenize = tokenSubscript;
            return null;
          };

          // symbolic names (variables, sets, params)
          if (stream.match(symbolicNames)) {
            return 'variable';
          };

          // delimiters
          if (stream.match(delimiters)) {
            return 'operator';
          };

          // Handle non-detected items
          stream.next();
          return null;
        };

        return {
          startState: function() {
            return {
              tokenize: tokenBase
            };
          },

          token: function(stream, state) {
            return state.tokenize(stream, state);
          }
        };
        });
        IPython.CodeCell.config_defaults.highlight_modes['magic_mathprog'] = {'reg':['^%%model', '^%%data']};
    '''

    ipython.run_cell_magic('javascript', '', js_code)

    # Create gmpl store in user namespace if it doesn't exist
    gmpl_store_exists = ipython.ev("'_gmpl_store' in globals()")
    if not gmpl_store_exists:
        gmpl_store = GMPLStore()
        ipython.user_ns['_gmpl_store'] = gmpl_store

    ipython.register_magics(GMPLMagics)
