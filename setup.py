from setuptools import setup

setup(name='gmplmagic',
      version='0.1',
      description='GMPL/MathProg magics for IPython/Jupyter',
      url='http://nelson.uhan.me',
      author='Nelson Uhan',
      author_email='nelson@uhan.me',
      packages=['gmplmagic'],
      install_requires=['glpk>=0.4.2', 'ipython'],
)
