from setuptools import setup

setup(name='glpkmagic',
      version='0.1',
      description='IPython magic commands for GLPK',
      author='Nelson Uhan',
      author_email='nelson@uhan.me',
      packages=['glpkmagic'],
      install_requires=[
          'ipython'
      ],
      zip_safe=False)
