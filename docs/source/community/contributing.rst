------------
Contributing
------------

==================
Ways to Contribute
==================

Contributions by the community help grow and optimize the capabilities of
Hyperledger Sawtooth, and are the most effective method of having a positive
impact on the project.

**Different ways you can contribute**

* Bugs or Issues (issues or defects found when working with Sawtooth)
* Core Features & Enhancements (expanded capabilities or optimization)
* Arcade Features (games that demonstrate Sawtooth such as Tic-Tac-Toe
  and Battleship)
* New or Enhanced Documentation (improve existing documentation or create new)
* Testing Events and Results (functional, performance or scalability)

**Unassigned JIRA Issues**

More specific items can be found in :ref:`jira`.  Any JIRA items which are
unassigned are probably still open.  If in doubt, ask on :ref:`chat` about
the particular JIRA issue.

==============
Commit Process
==============

Hyperledger Sawtooth is Apache 2.0 licensed and accepts contributions
via `GitHub <https://github.com/hyperledger/sawtooth-core>`_
pull requests. When contributing code please do the following:

* Fork the repository and make your changes in a feature branch.
* Please include unit and integration tests for any new features and updates
  to existing tests.
* Please ensure the unit and integration tests run successfully. Both are run
  with `./bin/run_tests`.
* Please ensure that lint passes by running './bin/run_lint -s master'.
  On success, the command produces no output.

**Pull Request Guidelines**

Pull requests can contain a single commit or multiple commits. The most
important part is that **a single commit maps to a single fix or enhancement**.

Here are a few scenarios:

* If a pull request adds a feature but also fixes two bugs, then the pull
  request should have three commits, one commit each for the feature and two
  bug fixes
* If a PR is opened with 5 commits that was work involved to fix a single issue,
  it should be rebased to a single commit
* If a PR is opened with 5 commits, with the first three to fix one issue and
  the second two to fix a separate issue, then it should be rebased to two
  commits, one for each issue

Your pull request should be rebased against the current master branch. Please do
not merge the current master branch in with your topic branch, nor use the
Update Branch button provided by GitHub on the pull request page.

**Commit Messages**

Commit messages should follow common Git conventions, such as the imperative
mood, separate subject lines, and a line-length of 72 characters. These rules
are well documented by Chris Beam in
`his blog post <https://chris.beams.io/posts/git-commit/#seven-rules>`_ on the
subject.

**Signed-off-by**

Commits must include Signed-off-by in the commit message (``git commit -s``).
This indicates that you agree the commit satisfies the
`Developer Certificate of Origin (DCO) <http://developercertificate.org/>`_.

**Important GitHub Requirements**

PLEASE NOTE: Pull requests can only be merged after they have passed all
status checks.

These checks are:

* The build must pass on Jenkins
* The PR must be approved by at least two reviewers and there cannot be
  outstanding changes requested

**Integrating GitHub Commits with JIRA**

You can link JIRA issues to your Hyperledger Sawtooth GitHub commits to integrate
the developer's activity with the associated issue. JIRA uses the issue key to
associate the commit with the issue, so the commit can be summarized in the
development panel for the JIRA issue.

When you make a commit, add the JIRA issue key to the end of the commit message.
Alternatively, you can add the JIRA issue key to the branch name. Either method
should integrate your commit with the JIRA issue it references.
