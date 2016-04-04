from IPython.core.magic import Magics, magics_class, cell_magic
from tempfile import NamedTemporaryFile
from glpk import env, LPX
from getopt import GetoptError


class GLPKOutput(object):
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
    def gmpl(self, line, cell):
        # Print log helper function
        def print_log():
            temp_log_file.seek(0)
            for line in temp_log_file:
                if (line.startswith('Reading model section') or 
                        line.startswith('Reading data section')):
                    pass
                else:
                    print(line, end="")

        # Close temporary files
        def close_temp_files():
            temp_model_file.close()
            temp_log_file.close()
            temp_out_file.close()

        # Parse arguments and store namespace variable names
        try:
            opts, args = self.parse_options(line, '', 'hidelog', 'output=') 
        except GetoptError:
            print("Invalid arguments to %%gmpl")
            return

        if 'output' in opts:
            output_varname = opts['output']
        else:
            output_varname = None

        if 'hidelog' in opts:
            hidelog = True
        else:
            hidelog = False

        # Get hook to underlying IPython shell
        ip = self.shell

        # Terminal hook helper function
        env.term_on = True
        env.term_hook = lambda output: temp_log_file.write(output)

        # Create temporary files for model, log, and out files
        temp_model_file = NamedTemporaryFile(mode='w+t', suffix='.mod')
        temp_log_file = NamedTemporaryFile(mode='w+t', suffix='.log')
        temp_out_file = NamedTemporaryFile(mode='w+t', suffix='.out')

        # Write temporary model file, seek to beginning
        temp_model_file.write(cell)
        temp_model_file.write('\n')
        temp_model_file.seek(0)

        # Load .mod file into GLPK
        try:
            lp = LPX(gmp=temp_model_file.name)
        except RuntimeError:
            if not hidelog:
                print_log()
            close_temp_files()
            return

        # Name the model
        lp.name = 'glpk_magic_model'

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
            lp.integer(msg_lev=msg_lev)

        # Print log file
        if not hidelog:
            print_log()

        # Write temporary output file
        if not hidelog:
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
        if output_varname:
            output = GLPKOutput()

            # Determine status
            if lp.status == 'opt':
                output.status = 'Solution found is optimal.'
            elif lp.status == 'undef':
                output.status = 'Solution found is undefined.'
            elif lp.status == 'feas':
                output.status = ('Solution found is feasible, ' +
                                 'but not necessarily optimal.')
            elif lp.status == 'infeas':
                output.status = 'Solution found is infeasible.'
            elif lp.status == 'nofeas':
                output.status = 'LP is infeasible.'
            elif lp.status == 'unbnd':
                output.status = 'LP is unbounded.'

            # Determine objective value
            output.objval = lp.obj.value

            # Determine solution
            output.solution = {}
            for col in lp.cols:
                output.solution[col.name] = col.primal

            # Put information in the user namespace, if desired
            if output_varname:
                ip.user_ns[output_varname] = output

        # Close the temporary files
        close_temp_files()


def load_ipython_extension(ipython):
    # The `ipython` argument is the currently active `InteractiveShell`
    # instance, which can be used in any way. This allows you to register
    # new magics or aliases, for example.
    raw_cell = 'import IPython\n'
    raw_cell += '''js = "IPython.CodeCell.config_defaults.highlight_modes['magic_mathprog'] = {'reg':['^%%gmpl']};"\n'''
    raw_cell += 'IPython.core.display.display_javascript(js, raw=True)\n'
    ipython.register_magics(GLPKMagics)
    ipython.run_cell(raw_cell)
