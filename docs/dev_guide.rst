***************
Developer Guide
***************

The following sections will help you change
how Nengo builds and simulates brain models.
If you make Nengo do something cool,
we hope that you'll consider contributing
to Nengo development!

Let's start off with some basics
in case you missed them in the README.

How to Build Nengo
==================

.. code-block:: bash

   git clone git@github.com:ctn-waterloo/nengo-temp.git
   cd nengo-temp
   python setup.py develop

How to Build the Documentation
==============================

Note that you can only build the documentation after
you've built the branch that you're using to build the
documentation.

The documentation is built with Sphinx and has a few requirements 
(Pandoc, Numpydoc and the Nengo-Sphinx-theme).

.. code-block:: bash

   # install the sphinx theme
   git clone git@github.com:ctn-waterloo/nengo-temp.git
   cd nengo-temp
   python setup.py develop
   # install numpydoc
   pip install numpydoc

How you install Pandoc (requirement of Sphinx) and
Sphinx depends on your operating system,
so no instructions will be included here.

After you've installed all the requirements,
execute from the root directory of ``nengo-temp``
to build the documentation
which will probably take a few minutes.

.. code-block:: bash

   mkdir ./docs/build
   sphinx-build -b html ./docs ./docs/build

Now you're ready to code and look-up docs!

.. toctree::
   :maxdepth: 2

   dev_introduction
   dev_api
   nef_minimal
   simulators
   contributing