%
% sphinxhowto.cls for Sphinx (http://sphinx-doc.org/)
%

\NeedsTeXFormat{LaTeX2e}[1995/12/01]
\ProvidesClass{sphinxhowto}[2009/06/02 Document class (Sphinx HOWTO)]

% 'oneside' option overriding the 'twoside' default
\newif\if@oneside
\DeclareOption{oneside}{\@onesidetrue}
% Pass remaining document options to the parent class.
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{\sphinxdocclass}}
\ProcessOptions\relax

% Default to two-side document
\if@oneside
% nothing to do (oneside is the default)
\else
\PassOptionsToClass{twoside}{\sphinxdocclass}
\fi

\LoadClass{\sphinxdocclass}

% Set some sane defaults for section numbering depth and TOC depth.  You can
% reset these counters in your preamble.
%
\setcounter{secnumdepth}{2}

% Change the title page to look a bit better, and fit in with the fncychap
% ``Bjarne'' style a bit better.
%
\renewcommand{\maketitle}{
  \rule{\textwidth}{1pt}
  \ifsphinxpdfoutput
    \begingroup
    % These \defs are required to deal with multi-line authors; it
    % changes \\ to ', ' (comma-space), making it pass muster for
    % generating document info in the PDF file.
    \def\\{, }
    \def\and{and }
    \pdfinfo{
      /Author (\@author)
      /Title (\@title)
    }
    \endgroup
  \fi
  \begin{flushright}
    \sphinxlogo%
    {\rm\Huge\py@HeaderFamily \@title} \par
    \vspace{25pt}
    {\Large\py@HeaderFamily
      \begin{tabular}[t]{c}
        \@author
      \end{tabular}} \par
    \vspace{25pt}
    \@date \par
    \py@authoraddress \par
    \vspace{25pt}
    \begin{center}
      \large{INTEL CONFIDENTIAL} \par
    \parbox{.8\textwidth}{%
      Copyright 2016 Intel Corporation. This document contains trade secrets
and proprietary information of Intel Corporation or its suppliers and
licensors, and is protected by worldwide copyright and trade secret laws and
treaty provisions. No part of the Material may be used, copied, reproduced,
modified, published, uploaded, posted, transmitted, distributed, or disclosed
in any way without Intel's prior express written permission.
    }%
    \end{center}
    \vspace{25pt}
  \end{flushright}
  \@thanks
  \setcounter{footnote}{0}
  \let\thanks\relax\let\maketitle\relax
  %\gdef\@thanks{}\gdef\@author{}\gdef\@title{}
}

\let\py@OldTableofcontents=\tableofcontents
\renewcommand{\tableofcontents}{
  \begingroup
    \parskip = 0mm
    \py@OldTableofcontents
  \endgroup
  \rule{\textwidth}{1pt}
  \vspace{12pt}
}  

\@ifundefined{fancyhf}{
  \pagestyle{plain}}{
  \pagestyle{normal}}		% start this way; change for
\pagenumbering{arabic}		% ToC & chapters

\thispagestyle{empty}

% Fix the bibliography environment to add an entry to the Table of
% Contents.
% For an article document class this environment is a section,
% so no page break before it.
\let\py@OldThebibliography=\thebibliography
\renewcommand{\thebibliography}[1]{
  \phantomsection
  \py@OldThebibliography{1}
  \addcontentsline{toc}{section}{\bibname}
}

% Same for the indices.
% The memoir class already does this, so we don't duplicate it in that case.
%
\@ifclassloaded{memoir}{}{
  \let\py@OldTheindex=\theindex
  \renewcommand{\theindex}{
    \phantomsection
    \py@OldTheindex
    \addcontentsline{toc}{section}{\indexname}
  }
}
