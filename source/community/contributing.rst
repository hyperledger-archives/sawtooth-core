------------
Contributing
------------

==================
Ways to Contribute
==================

Contributions by the community help grow and optimize the capabilities of
Sawtooth Lake, and are the most effective method of having a positive impact on
the project.

**Different ways you can contribute**

* Bugs or Issues (issues or defects found when working with Sawtooth Lake)
* Core Features & Enhancements (expanded capabilities or optimization)
* Arcade Features (games that demonstrate Sawtooth Lake such as Go and Checkers)
* New or Enhanced Documentation (improve existing documentation or create new)
* Testing Events and Results (functional, performance or scalability)

**Unassigned JIRA Issues**

More specific items can be found in :ref:`jira`.  Any JIRA items which are
unassigned are probably still open.  If in doubt, ask on :ref:`slack` about
the particular JIRA issue.

==============
Commit Process
==============

Distributed Ledger is Apache 2.0 licensed and accepts contributions via GitHub
pull requests. When contributing code please do the following:

* Fork the repository and make your changes in a feature branch.
* Please include unit and integration test changes.
* Please ensure the unit and integration tests run successfully. Both are run
  with `nose2`, but integration tests are only run if the environment variable
  ENABLE_INTEGRATION_TESTS is set.
* Please ensure that lint passes by running './bin/run_lint'.  The command
  should produce no output if there are no lint errors.

**Pull Request Guidelines**

Pull requests can contain a single commit or multiple commits.  The most
important part is that a single commit maps to a single fix or enhancement.

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

**Signed-off-by**

Commits must include Signed-off-by in the commit message (git commit -s).
This indicates that you agree the commit satisifies the DCO:
http://developercertificate.org/.
