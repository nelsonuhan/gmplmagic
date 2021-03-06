import setuptools

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except (IOError, ImportError):
    long_description = ''

setuptools.setup(
    name='gmplmagic',
    version='0.1.4',
    description='GMPL/MathProg magics for IPython/Jupyter',
    long_description=long_description,
    url='https://github.com/nelsonuhan/gmplmagic',
    author='Nelson Uhan',
    author_email='nelson@uhan.me',
    license='GNU GPLv3',
    packages=['gmplmagic'],
    install_requires=['glpk>=0.4.2', 'ipython'],
)
