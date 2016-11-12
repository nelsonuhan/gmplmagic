from setuptools import setup

setup(name='gmplmagic',
      version='0.1.1',
      description='GMPL/MathProg magics for IPython/Jupyter',
      url='https://github.com/nelsonuhan/gmplmagic',
      author='Nelson Uhan',
      author_email='nelson@uhan.me',
      license='GNU GPLv3',
      packages=['gmplmagic'],
      install_requires=['glpk>=0.4.2', 'ipython'],
)
