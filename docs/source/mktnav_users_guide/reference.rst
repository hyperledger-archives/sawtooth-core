*********
Reference
*********

UI Elements
===============

Persisent Elements
------------------

- `Menu Bar`_
- `Sidebar`_

Informational Pages
-------------------

- `Dashboard`_
- `Open Offers`_
- `Blockchain History`_
- `Portfolio`_

Forms
-----

- `Create Asset`_
- `Create Holding`_
- `Create Offer`_
- `Execute Exchange`_
- `Transfer Assets`_

Menu Bar
========

The menu bar appears at the top of every Marketplace Navigator screen, and can be used to navigate to many Marketplace features.

.. image:: images/ref_menu_bar.*

======  =================  =========================================================================
Item    Description        Note
======  =================  =========================================================================
A       Brand              Goes to personal `Dashboard`_
B       Current Block      Goes to `Blockchain History`_, shows block count and id of latest block
C       Create Offer       Click to `Create Offer`_
D       Username           Displays menu dropdown, shows signed in user's name
E       Dashboard          Goes to personal `Dashboard`_
F       Portfolio          Goes to personal `Portfolio`_
G       Transfer Assets    Click to `Transfer Assets`_
H       Sign out           Signs out of Marketplace Navigator
======  =================  =========================================================================

Sidebar
=======

This sidebar appears on most Marketplace Navigator screens, and displays the *Assets* in the marketplace, as well as a the currently selected user's *Holdings*.

.. image:: images/ref_sidebar.*

======  ====================  =============================================
Item    Description           Note
======  ====================  =============================================
A       Asset list            All assets in the marketplace
B       Create Asset          Click to `Create Asset`_
C       Holding list          Currently selected user's holdings
D       Create Holding        Click to `Create Holding`_
E       Individual asset      Click to narrow holdings to just this asset
F       Individual holding    Click to narrow offers to match holding
======  ====================  =============================================

Dashboard
=========

This dashboard showcases the latest *Offers* and *Exchanges* for the currently selected user (usually the signed in user).

.. image:: images/ref_dashboard.*

======  ====================  ==================================
Item    Description           Action
======  ====================  ==================================
A       Latest Open Offers    Goes to `Open Offers`_
B       Username              Goes to this user's `Dashboard`_
C       Latest Exchanges      Views all exchanges
======  ====================  ==================================

Open Offers
===========

Displays all currently open *Offers* (unless filtered by the `Sidebar`_), and allows those offers to be accepted. Reached from the `Dashboard`_.

.. image:: images/ref_offers.*

======  =============  ==============================================
Item    Description    Note
======  =============  ==============================================
A       Offer list     All offers, filtered by `Sidebar`_ selection
B       Username       Goes to this user's `Dashboard`_
C       Accept         Click to `Execute Exchange`_
======  =============  ==============================================

Blockchain History
==================

Displays current block state, and a list of all previous transactions. Reached from the `Menu Bar`_.

.. image:: images/ref_block_history.*

======  ========================  ============================================
Item    Description               Note
======  ========================  ============================================
A       Block State               Information about the blockchain
"       Block Id                  Id of the most recent block
"       Block Number              Number of blocks in blockchain
"       Block Size                Total number of items stored on blockchain
B       Transaction list          Info about every transaction so far
C       Individual transaction    Click to show `Transaction Detail`_
D       Page navigation           Navigates pages of ten transactions each
======  ========================  ============================================

Transaction Detail
------------------

.. image:: images/ref_transaction.*

======  ================  ===========================================================
Item    Description       Note
======  ================  ===========================================================
A       Transaction Id
B       Block Id          The block containing this transaction
C       Dependencies      Clickable id's of other transactions this is dependent on
D       Update Type       The type of update sent to the blockchain
======  ================  ===========================================================

Portfolio
=========

A summary of the user's financial information. Reached from the `Menu Bar`_.

.. image:: images/ref_portfolio.*

======  ==================  =====================================
Item    Description         Note
======  ==================  =====================================
A       Holdings list       All of the user's holdings
B       Latest offers       Most recent offers made by the user
C       Recent Exchanges    Most recent exchanges user executed
======  ==================  =====================================

Create Asset
============

A form for creating new *Assets* and *AssetTypes* for the marketplace. Reached from the `Sidebar`_.

.. image:: images/ref_create_asset.*

======  ===================  =========================================================
Item    Description          Note
======  ===================  =========================================================
A       Asset name           Must begin with a *"/"*, for example: *"/currency/usd"*
B       Asset description    Optional
C       Type dropdown        Selects from existing asset types
D       Add Type             Displays Create Asset Type pop-up
E       Type name            Must begin with a *"/"*
F       Type description     Optional
G       Type options         Select whether asset type should be *"restricted"*
H       Discard              Closes pop-up
I       Asset options        Select what options should be used with this asset
"       Restricted           Only creator can create non-empty holdings
"       Consumable           Asset must be spent to be exchanged (i.e. non-infinite)
"       Divisible            Can exist in fractional form
J       Submit               Creates asset
K       Reset                Clears form
======  ===================  =========================================================

Create Holding
==============

A form for creating a new *Holding* designed to contain a particular *Asset*. May be created empty, or with some quantity of the asset (if asset is unrestricted, or the logged-in participant created it). Reached from the `Sidebar`_.

.. image:: images/ref_create_holding.*

======  =============  =============================================================
Item    Description    Note
======  =============  =============================================================
A       Name           Must begin with a *"/"*, for example: *"/accounts/savings"*
B       Description    Optional
C       Asset          Selects which kind of asset to hold
D       Count          The amount of the asset to be created with the holding
E       Submit         Creates holding
F       Reset          Clears form
======  =============  =============================================================

Create Offer
============

A form for creating new sell *Offers*. User must already have a *Holding* both in the *Asset* they expect to receive in payment, and the asset which they will pay out. The input holding may be empty. Reached from the `Menu Bar`_.

.. image:: images/ref_create_offer.*

======  =====================  ===========================================================
Item    Description            Note
======  =====================  ===========================================================
A       Name                   Must begin with a *"/"*, for example: *"/orders/cookies"*
B       Description            Optional
C       Input                  Selects which holding will receive payments
D       Input amount           The amount of the input asset expected
E       Output                 Selects which holding payouts will be drawn from
F       Output amount          With the input amount, creates an exchange ratio
G       Minimum amount         The least input assets that will be accepted
H       Maximum amount         The most inputs
I       Offer repeatability    Unlimited, once ever, or once per participant
J       Submit                 Creates offer
K       Reset                  Clears form
======  =====================  ===========================================================

Execute Exchange
================

A form for responding to and executing an *Offer*, or chain of offers. Reachable from `Open Offers`_.

.. image:: images/ref_exchange.*

======  ===================  ======================================================================
Item    Description          Note
======  ===================  ======================================================================
A       Initial Holding      Selects holding from which payments will be drawn
B       Add offer            Adds a new offer to the start of an arbitrage chain
C       Input holding        Holding from which an exchange will be drawn, including final amount
D       Output holding       Holding to which an exchange will go, including final amount
E       Add offer            Adds a new offer to the end of an arbitrage chain
F       Output Holding       Selects holding to which final payouts will go
G       Exchange quantity    Number of times to exchange (based on ratio)
H       Accept               Executes exchange
I       Cancel               Returns to `Open Offers`_
======  ===================  ======================================================================

Transfer Assets
===============

A form for transfering a single kind of *Asset* from one *Holding* to another. Always a one way transfer, it can be between a user's own holdings, or to a different *Participant*. Reached from the `Menu Bar`_

.. image:: images/ref_transfer_asset.*

======  =============  =================================================================
Item    Description    Note
======  =============  =================================================================
A       Source         Selects the holding from which to draw the asset
B       Participant    Selects the user who will receive the asset, defaults to *Self*
C       Destination    Selects the holding to send the asset to
D       Amount         The quantity of the asset to transfer
E       Transfer       Executes the transfer
F       Cancel         Returns to `Portfolio`_
======  =============  =================================================================
