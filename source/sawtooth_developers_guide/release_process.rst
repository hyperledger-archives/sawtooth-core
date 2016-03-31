***************
Release Process
***************

This section contains the release processed used for the software contained
in the following git repositories:

- mktplace
- sawtooth
- sawtooth-validator

Versioning
==========

The projects use semantic versioning as documented at http://semver.org/ for
official releases.

Definition of Public API
------------------------

The public API for these projects include:

- Any provided Python API which is intended to be used by software outside
  of its git repository.  This includes the Python API provided by sawtooth
  and used by sawtooth-validator, for example.
- Plugin interfaces implemented by external plugins.
- CLI options and parseable output.  Since scripts are likely to be written
  against the CLI tools, any changes in options or output which is likely to
  be parsed in scripts is considered an API change.
- For interactive CLI commands, the script API.  For CLI commands which are
  scriptable by providing a script file, changes which impact what is available
  to the script file are API changes.
- Any protocol changes for the validator (HTTP, UDP, etc.)
- The block chain structure.

Version
-------

The primary version follows semantic versioning (MAJOR.MINOR.PATCH) and
is specified in the setup.py file.

When building with Jenkins or when the VERSION environment variable is set
to AUTO or AUTO_STRICT, the version number will also include information
about the git commit being built.  The format is MAJOR.MINOR.PATCH-gitCOMMITN-COMMITID.  COMMITN is the number of commits since the previous annotated tag, and COMMITID is the git commit id being built.  In addition, if the working
directory is not clean, then "-dirty" is appended to the version.

Release Process
---------------

The following procedure should be followed when making an official release:

#. Make sure you have the current upstream master branch.  Create a
   working branch off of it (this will be pushed to upstream master later).
#. Determine if the major or minor version needs to be incremented.  Use
   the definition above for Public API combined with the information on
   http://semver.org/ to make this determination.  If an update is needed,
   make that change and commit the change.  For the first line of the
   commit message use "Updated version to MAJOR.MINOR.0".  Substitute real
   values for MAJOR and MINOR as appropriate.  In the remainder of the commit
   message, provide some detail about why the bump in MAJOR or MINOR was
   needed.
#. Tag the repository with the version specified in setup.py using the
   following command (substituting correct values for MAJOR, MINOR, and
   PATCH):

   .. code-block:: console

      % git tag -a vMAJOR.MINOR.PATCH -m "vMAJOR.MINOR.PATCH"

#. Verify that the software can be built when VERSION=AUTO_STRICT is provided:

   .. code-block:: console

      % VERSION=AUTO_STRICT python setup.py build

#. Increment the PATCH portion of the version in setup.py.  This will set
   the version to the next version.  Commit the change with the commit
   message "Updated version to MAJOR.MINOR.PATCH".  Substitute real
   values for MAJOR, MINOR, and PATCH as appropriate.  No additional detail
   in the commit message is necessary when incrementing PATCH.
#. Verify that the software can be built when VERSION=AUTO_STRICT is provided:

   .. code-block:: console

      % VERSION=AUTO_STRICT python setup.py build

#. Push both the branch and tag directly to the upstream repository.

   .. code-block:: console

      % git push upstream vMAJOR.MINOR.PATCH master

   .. caution::

      Since Jenkins uses VERSION=AUTO_STRICT when building, it is
      important that you push both the tag and master at the same
      time.

#. Verify that the Jenkins build does not fail.

