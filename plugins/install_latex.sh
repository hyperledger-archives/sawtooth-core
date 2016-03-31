#!/bin/bash -x

set -e

if [ -f /etc/debian_version ]; then
    apt-get install -y -q \
        texlive-latex-base \
        texlive-latex-extra \
        texlive-latex-recommended \
        texlive-fonts-recommended
else
    echo "Skipping Latex installation on this platform."
fi

