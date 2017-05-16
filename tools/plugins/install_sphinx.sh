#!/bin/bash -x

set -e

pip3 install sphinx==1.5.6
pip3 install sphinx_rtd_theme
pip3 install sphinxcontrib-httpdomain
pip3 install sphinxcontrib-openapi

# Used by make_templated_docs
pip3 install Jinja2
