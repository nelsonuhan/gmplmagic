from IPython.core.magic import Magics, magics_class, cell_magic, line_magic
from tempfile import NamedTemporaryFile
from glpk import env, LPX
from getopt import GetoptError


class GLPKStore(object):
    def __init__(self):
        self.model = {}
        self.data = {}

    def add_model(self, name, code):
        self.model[name] = code

    def add_data(self, name, code):
        self.data[name] = code


class GLPKResult(object):
    def __init__(self):
        self.status = None
        self.objval = None
        self.solution = None

    def __repr__(self):
        output_string = ''

        if self.status:
            output_string += "Status: {0}\n".format(self.status)

        if self.objval:
            output_string += "Objective value: {0}\n".format(self.objval)

        if self.solution:
            output_string += "Decision variables:\n"
            for var, val in self.solution.items():
                output_string += "    {0} = {1}\n".format(var, val)

        return output_string


@magics_class
class GLPKMagics(Magics):
    @cell_magic
    def model(self, line, cell):
        '''
        %%model <name of model>
        '''
        # Get interactive shell
        ip = self.shell 

        # Get access to glpk store, create it if it doesn't exist
        glpk_store_exists = ip.ev("'_glpk_store' in globals()")
        if not glpk_store_exists: 
            glpk_store = GLPKStore()
            ip.user_ns['_glpk_store'] = glpk_store
        else:
            glpk_store = ip.user_ns['_glpk_store']

        # Get user's model name
        opts, args = self.parse_options(line, '', mode='list')
        if len(args) != 1:
            print("Usage: %%model <name of model>")
            return
        else:
            model_name = args[0]

        # Put user's model in glpk store
        # Add a new line to the end to avoid stupid GLPK warnings
        cell += '\n'
        glpk_store.add_model(model_name, cell)
        ip.user_ns['_glpk_store'] = glpk_store
        print("Model '{0}' stored.".format(model_name))

    @cell_magic
    def data(self, line, cell):
        '''
        %%data <name of data>
        '''
        # Get interactive shell
        ip = self.shell 

        # Get access to glpk store, create it if it doesn't exist
        glpk_store_exists = ip.ev("'_glpk_store' in globals()")
        if not glpk_store_exists: 
            glpk_store = GLPKStore()
            ip.user_ns['_glpk_store'] = glpk_store
        else:
            glpk_store = ip.user_ns['_glpk_store']

        # Get user's data name
        opts, args = self.parse_options(line, '', mode='list')
        if len(args) != 1:
            print("Usage: %%data <name of model>")
            return
        else:
            data_name = args[0]

        # Put user's data in glpk store
        glpk_store.add_data(data_name, cell)
        ip.user_ns['_glpk_store'] = glpk_store
        print("Data '{0}' stored.".format(data_name))

    @line_magic
    def solve(self, line):
        '''
        %solve <name of model> <name of data>

        Options:
            --nolog
            --result=
        '''
        # Helper function: print usage
        def print_usage():
            print("Usage: %%solve <name of model> <name of data>")
            print("  Options: --nolog --result=<name of result variable>")

        # Helper function: print log 
        def print_log():
            temp_log_file.seek(0)
            for line in temp_log_file:
                if not (line.startswith('Reading model section') or 
                        line.startswith('Reading data section')):
                    print(line, end='')

        # Helper function: close temporary files
        def close_temp_files():
            temp_model_file.close()
            temp_log_file.close()
            temp_out_file.close()

        # Parse arguments 
        # Get model name and data name
        # Get namespace variable names
        try:
            opts, args = self.parse_options(line, '', 'nolog', 'result=', 
                                            mode='list') 
        except GetoptError:
            print_usage()
            return

        if (len(args) == 0) or (len(args) > 2):
            print_usage() 
            return

        model_name = args[0]
        if len(args) == 2:
            data_name = args[1]
        else:
            data_name = None

        if 'result' in opts:
            result_name = opts['result']
        else:
            result_name = None

        if 'nolog' in opts:
            nolog = True
        else:
            nolog = False

        # Get IPython shell
        ip = self.shell

        # Get glpk store
        glpk_store = ip.user_ns['_glpk_store']

        # Terminal hook helper function
        env.term_on = True
        env.term_hook = lambda output: temp_log_file.write(output)

        # Create temporary files for model, log, and out files
        temp_model_file = NamedTemporaryFile(mode='w+t', suffix='.mod')
        temp_data_file = NamedTemporaryFile(mode='w+t', suffix='.dat')
        temp_log_file = NamedTemporaryFile(mode='w+t', suffix='.log')
        temp_out_file = NamedTemporaryFile(mode='w+t', suffix='.out')

        # Write temporary model file, seek to beginning
        temp_model_file.write(glpk_store.model[model_name])
        temp_model_file.write('\n')
        temp_model_file.seek(0)

        # Write temporary data file, seek to beginning
        if data_name:
            temp_data_file.write(glpk_store.data[data_name])
            temp_data_file.write('\n')
            temp_data_file.seek(0)

        # Load .mod file into GLPK
        try:
            if data_name:
                lp = LPX(gmp=(temp_model_file.name, temp_data_file.name, 
                              None)) 
            else:
                lp = LPX(gmp=temp_model_file.name)
        except RuntimeError:
            if not nolog:
                print_log()
            close_temp_files()
            return

        # Name the model
        if data_name:
            lp.name = '{0} {1}'.format(model_name, data_name)
        else:
            lp.name = model_name

        # Set message level of the solver
        #   GLP_MSG_OFF     0  /* no output */
        #   GLP_MSG_ERR     1  /* warning and error messages only */
        #   GLP_MSG_ON      2  /* normal output */
        #   GLP_MSG_ALL     3  /* full output */
        msg_lev = 3

        # Solve the .mod file using the simplex method
        lp.simplex(msg_lev=msg_lev)

        # If the model is a MIP, start branch-and-cut
        if lp.kind is int:
            # Solve the .mod file using the MIP solver
            try:
                lp.integer(msg_lev=msg_lev)
            except RuntimeError:
                print_log()
                return

        # Print log file
        if not nolog:
            print_log()

        # Write temporary output file
        if not nolog:
            if lp.kind is float:
                lp.write(sol=temp_out_file.name)
            elif lp.kind is int:
                lp.write(mip=temp_out_file.name)
            temp_out_file.seek(0)
            print("========================================" +
                  "========================================")
            for line in temp_out_file:
                print(line, end='')

        # Create GLPK output object if desired
        if result_name:
            result = GLPKResult()

            # Determine status
            if lp.status == 'opt':
                result.status = 'Solution found is optimal.'
            elif lp.status == 'undef':
                result.status = 'Solution found is undefined.'
            elif lp.status == 'feas':
                result.status = ('Solution found is feasible, ' +
                                 'but not necessarily optimal.')
            elif lp.status == 'infeas':
                result.status = 'Solution found is infeasible.'
            elif lp.status == 'nofeas':
                result.status = 'LP is infeasible.'
            elif lp.status == 'unbnd':
                result.status = 'LP is unbounded.'

            # Determine objective value
            result.objval = lp.obj.value

            # Determine solution
            result.solution = {}
            for col in lp.cols:
                result.solution[col.name] = col.primal

            # Put information in the user namespace, if desired
            ip.user_ns[result_name] = result

        # Close the temporary files
        close_temp_files()


def load_ipython_extension(ipython):
    # The `ipython` argument is the currently active `InteractiveShell`
    # instance, which can be used in any way. This allows you to register
    # new magics or aliases, for example.
    raw_cell = 'import IPython\n'
    raw_cell += '''js_mod = "IPython.CodeCell.config_defaults.highlight_modes['magic_mathprog'] = {'reg':['^%%model', '^%%data']};"\n'''
    raw_cell += 'IPython.core.display.display_javascript(js_mod, raw=True)\n'
    ipython.register_magics(GLPKMagics)
    ipython.run_cell(raw_cell)
