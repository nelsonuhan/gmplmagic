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


class GLPKResult(object):
    def __init__(self):
        self.status = None
        self.objval = None
        self.solution = None

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
        # Helper function: print log
        def print_log():
            temp_log_file.seek(0)
            for line in temp_log_file:
                # Don't print GLPK log lines regarding which files
                # the model and data are being read from
                if not (line.startswith('Reading model section') or
                        line.startswith('Reading data section')):
                    # Replace the temporary model file name
                    # with something more human-readable
                    line = line.replace(
                        temp_model_file.name + ':',
                        "Model '{0}' line ".format(model_name)
                    )

                    # Replace the temporary data file name
                    # with something more human-readable
                    line = line.replace(
                        temp_data_file.name + ':',
                        "Data '{0}' line ".format(data_name)
                    )

                    print(line, end='')

        # Helper function: close temporary files
        def close_temp_files():
            temp_model_file.close()
            temp_log_file.close()
            temp_out_file.close()

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

        # Get glpk store from user namespace
        try:
            glpk_store = ip.user_ns['_glpk_store']
        except KeyError:
            print('Model and data storage is missing.'
                  'Try storing your model and data again.')
            return

        # Terminal hook helper function
        env.term_on = True
        env.term_hook = lambda output: temp_log_file.write(output)

        # Create temporary files for model, log, and out files
        temp_model_file = NamedTemporaryFile(mode='w+t', suffix='.mod')
        temp_data_file = NamedTemporaryFile(mode='w+t', suffix='.dat')
        temp_log_file = NamedTemporaryFile(mode='w+t', suffix='.log')
        temp_out_file = NamedTemporaryFile(mode='w+t', suffix='.out')

        # Write temporary model file, seek to beginning
        # Check if model exists in glpk store
        try:
            temp_model_file.write(glpk_store.model[model_name])
        except KeyError:
            print("Model '{0}' does not exist.".format(model_name))
            close_temp_files()
            return
        temp_model_file.write('\n')
        temp_model_file.seek(0)

        # Write temporary data file, seek to beginning
        # Check if data exists in glpk store
        if data_name:
            try:
                temp_data_file.write(glpk_store.data[data_name])
            except KeyError:
                print("Data '{0}' does not exist.".format(data_name))
                close_temp_files()
                return
            temp_data_file.write('\n')
            temp_data_file.seek(0)

        # Load GMPL files into GLPK
        if data_name:
            gmp = (temp_model_file.name, temp_data_file.name, None)
        else:
            gmp = temp_model_file.name

        try:
            lp = LPX(gmp=gmp)
        except RuntimeError:
            print_log()
            close_temp_files()
            return

        # Give the model a name in GLPK
        lp.name = model_name + ' ' + data_name if data_name else model_name

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

        # Print log file to shell
        if not nolog:
            print_log()

        # Write temporary output file
        # Print temporary output file to shell
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
            result.status = lp.status

            # If we have an optimal or feasible solution:
            if result.status in ['opt', 'feas']:
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

    @line_magic
    def listmodels(self, line):
        # Get IPython shell
        ip = self.shell

        # Get glpk store
        glpk_store = ip.user_ns['_glpk_store']

        # Print models
        glpk_store.list_models()

    @line_magic
    def listdata(self, line):
        # Get IPython shell
        ip = self.shell

        # Get glpk store
        glpk_store = ip.user_ns['_glpk_store']

        # Print models
        glpk_store.list_data()

    @line_magic
    def clearmodels(self, line):
        # Get IPython shell
        ip = self.shell

        # Get glpk store
        glpk_store = ip.user_ns['_glpk_store']

        # Print models
        glpk_store.clear_models()

    @line_magic
    def cleardata(self, line):
        # Get IPython shell
        ip = self.shell

        # Get glpk store
        glpk_store = ip.user_ns['_glpk_store']

        # Print models
        glpk_store.clear_data()


def load_ipython_extension(ipython):
    # Inject JS for GMPL syntax highlighting
    raw_cell = (
        '''import IPython\n'''
        '''js = "IPython.CodeCell.config_defaults.highlight_modes'''
        '''['magic_mathprog'] = {'reg':['^%%model', '^%%data']};"\n'''
        '''IPython.core.display.display_javascript(js, raw=True)\n'''
    )
    ipython.run_cell(raw_cell)

    # Create glpk store in user namespace if it doesn't exist
    glpk_store_exists = ipython.ev("'_glpk_store' in globals()")
    if not glpk_store_exists:
        glpk_store = GLPKStore()
        ipython.user_ns['_glpk_store'] = glpk_store

    ipython.register_magics(GLPKMagics)
