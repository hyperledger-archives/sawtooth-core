# Contributing to Distributed Ledger

This document covers how to report issues and contribute code.

## Topics

* [Reporting Issues](#reporting-issues)
* [Contributing Code](#contributing-code)

# Reporting Issues

This is a great way to contribute. Before reporting an issue, please review current
open issues to see if there are any matches. If there is a match, comment with a +1, or "Also seeing this issue".
If any environment details differ, please add those with your comment to the matching issue.

When reporting an issue, details are key. Include the following:
- OS version
- Distributed Ledger version
- Environment details (virtual, physical, etc.)
- Steps to reproduce
- Actual results
- Expected results

## Notes on GitHub Usage
It's worth noting that we don't use all the native GitHub features for issue management. For instance, it's uncommon
 for us to assign issues to the developer who will address it. Here are notes on what we do use.

### Issue Labels
Distributed Ledger maintainers have a set of labels we'll use to keep up with issues that are organized:

<img src="http://i.imgur.com/epDE8RO.jpg"  alt="GitHub Tagging Strategy" width="500">

* **bug** - the classic definition of missing or misbehaving code from existing functionality (this includes malfunctioning tests)
* **feature request** - any new functionality or improvements/enhancements to existing functionality. Note that we use a
 single term for this (instead of both feature & enhancement labels) since it's prioritized in identical ways during sprint planning
* **question** - discussions related to Distribute Ledger, its administration or other details that do not outline how to address the request
* **RFC** - short for [request for comment](https://en.wikipedia.org/wiki/Request_for_Comments). These are discussions of
 Distributed Ledger features requests that include detailed opinions of implementation that are up for discussion

We also add contextual notes we'll use to provide more information regarding an issue:

  * **in progress** - we're taking action (right now). It's best not to develop your own solution to an issue in this state. Comments are welcome
  * **help wanted** - A useful flag to show this issue would benefit from community support. Please comment or, if it's not in progress, say you'd like to take on the request
  * **on hold** - An idea that gained momentum but has not yet been put into a maintainer's queue to complete. Used to inform any trackers of this status
  * **tracked** - This issue is in the JIRA backlog for the team working on Distributed Ledger
  * **duplicate** - Used to tag issues which are identical to other issues _OR_ which are resolved by the same fix of another issue (either case)
  * **wontfix** - The universal sign that we won't fix this issue. This tag is important to use as we separate out the nice-to-have
   features from our strategic direction

# Contributing Code

Distributed Ledger is Apache 2.0 licensed and accepts contributions via GitHub pull requests.

Before contributing any code, note that you will be asked to sign-off on the
[Developer Certificate of Origin](http://developercertificate.org/).
Please review the document and ensure you can sign-off on it.

Fork the repository and make your changes in a feature branch. Please add a prefix to the branch name (XXXX-) where
XXX is the Github bug or issue number.

Please include unit and integration test changes.

Please ensure the unit and integration tests run successfully. Both are run with `nose2`,
  but integration tests are run if the environment variable ENABLE_INTEGRATION_TESTS is set.

### Commit Guidelines

Commits should have logical groupings. A bug fix should be a single commit. A new feature
should be a single commit.

Commit messages should be clear on what is being fixed or added to the code base. If a
commit is addressing an open issue, please start the commit message with "Fix: #XXX" or
"Feature: #XXX". This will help make the generated changelog for each release easy to read
with what commits were fixes and what commits were features.

### Pull Request Guidelines

Pull requests can contain a single commit or multiple commits. The most important part is that _**a single commit maps to a single fix**_. Here are a few scenarios:
*  If a pull request adds a feature but also fixes two bugs, then the pull request should have three commits, one commit each for the feature and two bug fixes
* If a PR is opened with 5 commits that was work involved to fix a single issue, it should be rebased to a single commit
* If a PR is opened with 5 commits, with the first three to fix one issue and the second two to fix a separate issue, then it should be rebased to two commits, one for each issue

Your pull request should be rebased against the current master branch. Please do not merge
the current master branch in with your topic branch, nor use the Update Branch button provided
by GitHub on the pull request page.

### Sign your work

**Please ensure your commit messages end with the "Signed-off-by:" tag followed
  by your name and email address to certify the origin of the contribution. Do not use pseudonyms.**
  (Please see the -s and --signoff flags on [git commit](https://git-scm.com/docs/git-commit))

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
660 York Street, Suite 102,
San Francisco, CA 94110 USA

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

### Merge Approval

The maintainers of the repo utilize a "Looks Good To Me" (LGTM) message in the pull request.
After one or more maintainer states LGTM, we will merge. If you have questions or comments on your code,
feel free to correct these in your branch through new commits.





