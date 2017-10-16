..
   Copyright 2017 Intel Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

***********
Permissions
***********

As mentioned in the :doc:`introduction <introduction>`, Seth supports a
permissioned network model in which the set of actions allowed by individual
accounts (contract or external) can be controlled. The supported permissions
and the actions they correspond to are as follows:

root
  Change permissions of other accounts

send
  Transfer value from an owned account to another account (not currently used)

call
  Execute a deployed contract

contract
  Deploy new contracts from an owned account

account
  Create new external accounts; this only has an effect when applied to global
  permissions and disabling it prevents new external accounts from being created

all
  Shorthand for "all permissions". This is not an actual permission, but can
  be used when setting permissions with ``seth``.

Each permission can be set to either allow or deny the action for individual
accounts. If a permission is not set, the permission defaults to the permission
set at the global permissions address. If the permission is not set at the
global permissions address, the permission is allowed.

Permission Inheritance
======================

When a new account is created, its permissions are inherited from the creating
account according to the following rules:

- If the account is a new external account, its permissions are inherited from
  the global permissions address. If no permissions are set at the global
  permissions address, all permissions are enabled for the new account.
- If the account is a new contract account, its permissions are inherited from
  the creating account, with the exception of the "root" permission, which is
  set to deny.

Managing Permissions
====================
If you have been following along with this guide, you should own two accounts at
this point: an external account and a contract account. To inspect the
permissions on one of these accounts, run::

    $ seth show account {account-address}

If you inspect the permissions of your external account (the first account you
created), you should see output similar to::

    Perms  : +root,+send,+call,+contract,+account

You should have all permissions enabled because this is a new network and no
permissions have been set at the global permissions address.

If you inspect the permissions of your contract account (created when you ran
``seth contract create``), you should see output similar to::

    Perms  : -root,+send,+call,+contract,+account

This is because the contract inherited all permissions from the creating
account, except for root.

Permissions of individual accounts may be modified by any account that has the
"root" permission. As such, it is important to limit the number of accounts
that have "root". You can control the permissions of other accounts with ``seth
permissions set``. For example, we can update the contract account's
permissions so that it cannot create new contracts with::

    $ seth permissions set {alias} --address {contract-address} --permissions="-root,+send,+call,-contract,+account"

In place of ``{alias}`` you should insert the alias of the key you used to
create your first account and in place of ``{contract-address}`` you should
insert the address of the contract you created.

When specifying permissions on the command line, use a comma-separated list of
"prefixed" permissions from the list above. Permissions must be prefixed with a
plus ("+") or minus ("-") to indicated allowed and denied respectively.
Permissions that are omitted from the list will be left unset and default to
those set at the global permissions address.

"all" may be used as a special keyword to refer to all permissions. Duplicates
are allowed and items that come later in the list override earlier items.

Examples::

    -all,+contract,+call      Disable all permissions except contract creation or calling
    +account,+send,-contract  Enable account creation and sending value and disable contract creation
    +all,-root                Enable all permissions except setting permissions

Securing the Network
====================

When a new Sawtooth network running Seth is created, by default the network is
open and all permissions are allowed by all accounts. This includes the "root"
permission. In a new deployment, the first action should be to create a new
external account with a well protected private key and then set the permissions
at the global permissions address.

If you have been following along with this guide, you can update the global
permissions address of your development network to disable all permissions with::

    $ seth permissions set {alias} --address global --permissions="-all"

When updating permissions with ``seth`` the string "global" is expanded to the
global permissions address, which is usually all zeros.
