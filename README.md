# GMPL Magic: GMPL/MathProg Magics for IPython/Jupyter

## Usage

Take a look at these [example notebooks](https://github.com/nelsonuhan/gmplmagicexamples) for details on how to use GMPL Magic &mdash; no installation required, thanks to [Binder](http://mybinder.org)!

## Dependencies

GMPL Magic has been tested with 

* Jupyter 4.2.0 
* Python 3.5.2
* MetaKernel 0.14
* PyGLPK 0.4.2, available from [@bradfordboyle](https://github.com/bradfordboyle/pyglpk)
* GLPK 4.60

## Installation

First, install PyGLPK - note that the version on PyPI is outdated:

```
pip install https://github.com/bradfordboyle/pyglpk/zipball/master
```

Note that PyGLPK depends on an existing installation of GLPK. For example, on macOS, this can be accomplished by:

```
brew update
brew tap homebrew/science
brew install glpk
```

(I will eventually include instructions on how to install GLPK on other operating systems.)

Then, install GMPL Magic:

```
pip install gmplmagic
```

To use these magics in a Jupyter notebook:

```
%load_ext glpkmagic
```
