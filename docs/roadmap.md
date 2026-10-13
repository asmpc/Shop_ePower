# Shop_ePower Roadmap

## Project Vision

Shop_ePower is evolving from a diploma e-commerce project into a
complete business platform for wholesale and retail sales.

The long-term goal is to build a modular trading system that includes
catalog management, inventory, order processing, customer financial
accounts, payment workflows, returns, logistics, reporting, and external
integrations.

The project evolves through small, tested and documented iterations.

------------------------------------------------------------------------

# Design Principles

These principles guide every architectural decision.

## Business First

Business processes drive architecture. Technology serves business
requirements, not the other way around.

## Evolution over Revolution ⭐

Working parts of the system are never rewritten simply because a
"better" design exists.

The architecture evolves incrementally: - preserve backward
compatibility whenever practical; - extend existing domains instead of
replacing them; - introduce new capabilities through new services and
models; - prefer gradual migration over large rewrites.

This principle allows the project to remain stable while continuously
growing.

## Test Driven Development

New functionality is accompanied by automated tests. Regression
protection is considered part of every feature.

## Clean Architecture

Business logic belongs in services and domain layers rather than views
or templates.

## Domain Separation

Accounts, Catalog, Orders, Payments, Chat, Inventory and future
Financial modules remain clearly separated.

## Documentation First

Architecture, roadmap and deployment documentation evolve together with
the code.

## CI Before Merge

Every significant change should successfully pass automated quality
checks.

## One Logical Sprint = One Commit

Each completed logical sprint ends with a clean, meaningful Git commit.

------------------------------------------------------------------------

# Completed Phases

PHASES 1--19 established the project foundation: modular Django
architecture, catalog and inventory, order lifecycle, payment and
invoice workflow, chat, Docker, GitHub Actions CI, and engineering
documentation.

PHASE 20 modernized dependency management with Poetry, updated
Docker and CI integration, and aligned project documentation.

PHASE 21 standardized test infrastructure: centralized domain helpers,
removed duplication, unified fixture naming and test imports, and
introduced Ruff quality checks. Regression testing passed.

PHASE 22 established the customer financial core: personal and legal
accounts, an immutable transaction ledger, atomic balance services,
account lifecycle and audit history, read-only staff finance pages,
and bounded customer and staff lists. The complete test suite, Ruff,
Django checks, and migration-state check passed at phase closure.

------------------------------------------------------------------------

# Current Phase

## PHASE 23 --- Order Funds & Full-Shipment Settlement

Status: implementation started; remaining architecture decisions are being refined.

Completed first step (2026-10-13): new orders record their owner's matching
personal or legal customer account. Checkout rejects a missing account.
The nullable relation preserves existing demonstration orders without
automatically assigning accounts. The full suite of 685 tests passed.

Connect an order, its confirmed payment or customer funds, its full shipment,
and any remaining debt through explicit, idempotent records. In the current
workflow, `Complete order` is intended to confirm full shipment. Introduce
a shipment record so this action can create debt once, without treating
the order status alone as a financial event. Managers and administrators
need a bounded, paginated list of shipped orders with unpaid balances, with
customer and shipment details. Partly paid orders remain visible until fully
settled. Initially, payments occur only in the office or by bank transfer;
choosing a method or completing an order does not confirm receipt of money.
The existing `Mark as paid` action credits available funds once but never
settles debt automatically. A manager or administrator explicitly allocates
funds to a shipped order. Corrections undo dependent allocations before
reversing the credit and resetting payment status. Customers see their own
unallocated prepayment and debt, separately for personal and legal accounts.
Each order is bound at creation to its owner's matching personal or legal
account; later financial operations use that recorded account.
One order may receive several confirmed payments while full shipment happens
only once. PHASE 23 includes manager edits to order items before shipment,
even after partial payment: confirmed receipts stay unchanged. An issued
invoice must be explicitly cancelled before the edit and replaced afterward;
the order total and stock reservations must remain consistent. Post-shipment
item edits are deferred. Every successful pre-shipment edit requires a reason
and an append-only record of who changed what, when, and how the order total
changed. The manager agrees the edit with the customer outside the website;
PHASE 23 adds no in-app customer approval workflow.
Adding more of an existing product creates a separate order line with a
validated current selling-price snapshot and its own reservations; the
original price batch stays unchanged. Recalculate and show the new selling
price to the manager for confirmation before adding the line.
For reductions, the manager selects the exact order line/price batch;
the system does not pick which price or reservations to remove.

Design the shipment model so partial shipments can be added later, but do
not build a partial-shipment UI in this phase. Keep the existing payment and
invoice workflows working. The exit goal is a testable order-to-money flow
ready for a minimal 1C exchange, not every future finance feature.

See [the PHASE 23 design draft](phase-23-deposits-and-order-settlement.md).

------------------------------------------------------------------------

# Priority Path to the Online Test Pilot

## PHASE 24 --- Minimal 1C Integration

- confirm the customer's 1C configuration, exchange method, data ownership,
  and the smallest useful set of exchanged objects;
- use test data and an agreed exchange contract, with idempotent imports,
  validation, error reporting, and a repeatable reconciliation check;
- integrate only the order, shipment, and money facts required for the
  internet pilot; defer broader ERP and supplier workflows.

## PHASE 25 --- Controlled Online Pilot

- deploy a clearly labelled test environment reachable over the internet;
- allow demonstration and testing without real sales or live payments;
- prepare access control, HTTPS, backups, logging, and a rollback path;
- verify the full order-to-money-to-1C test scenario before inviting users.

------------------------------------------------------------------------

# Deferred After the Online Test Pilot

The following work remains in the roadmap but is not a prerequisite for
the test pilot. Its order and phase numbers will be decided from pilot
feedback and real business needs. Safety requirements for the pilot itself
remain in PHASE 25 and are not deferred.

## Business Capabilities

-   return requests
-   warehouse inspection
-   stock recovery
-   write-off workflow
-   exchange workflow
-   refund processing
-   withdrawal requests
-   balance reservation
-   approval workflow
-   reconciliation
-   partial-shipment UI and advanced allocation rules
-   mixed payments and external-provider integration

## Engineering and Growth

-   developer environment improvements;
-   advanced Git practices;
-   production deployment for real sales, distinct from the test pilot;
-   expanded CI/CD and release automation;
-   performance work and Redis caching when measurements justify it;
-   WebSockets and real-time features;
-   invoice revisions;
-   expanded 1C and supplier integrations beyond the minimal exchange;
-   internationalization.

------------------------------------------------------------------------

# Long-Term Vision

Shop_ePower should eventually become a complete business platform
capable of supporting:

-   customer financial accounts;
-   warehouse management;
-   reverse logistics;
-   ERP integrations;
-   real-time communication;
-   international deployment;
-   scalable architecture for future growth.

------------------------------------------------------------------------

# Continuous Backlog

These initiatives are intentionally not tied to a specific phase and
will be implemented when appropriate:

-   Security Hardening
-   Audit staff-only pages that return HTTP 200 with an empty queryset to
    unauthorized users; deny access explicitly instead.
-   Observability & Monitoring
-   Business Analytics
-   Loyalty Program
-   Marketplace Features
