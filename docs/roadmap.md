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

During learning, the user edits application code and runs checks. Run only
the new test at each small TDD step, then the relevant module when a related
behavior is complete. Explain any additional targeted regression checks.
Keep shared test preconditions in `setUp()` to avoid duplicating fixtures.

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
settled. Initially, payments occur only in the office or by bank transfer.
Clarified on 2026-10-14: checkout records the customer's payment preference
on the order but creates no `Payment`. An order awaiting payment is not a
pending money receipt, and this distinction requires no new shipment status.
An authorized employee records an actual receipt and its amount; the manual
confirmation creates a `PAID` payment and one idempotent account credit
atomically. An invoice is issued from the order independently of receipts.
Selecting office payment at checkout creates no payment; confirming money
actually received in the office creates one. These are separate test cases.
Invoice issuance and allocation create no `Payment`; an invoice is optional.
Receipt confirmation never marks an order paid or settles debt automatically.
Clarified on 2026-10-15: a manager or administrator separately assigns
available funds to an order, including before shipment. Assigning 100 from
an available balance of 100 leaves zero freely available and zero debt before
shipment. Resetting that order payment releases the 100 for reuse without
voiding the actual receipt. A non-blank reason, actor, time, and append-only
history are required. Fulfillment and order payment state remain independent;
an unpaid shipped order remains `COMPLETED`. Shipment must account for
previously assigned funds once, without deducting them a second time.
Cancelled orders reject new payment assignments and release assigned funds
to the customer's available balance; cancellation does not prove a payout.
Manual actual refunds of office cash and bank-transfer receipts are required
in PHASE 23. An authorized employee separately confirms the real money-out
event, records its amount and reason, and decreases available funds atomically
with its history. Funds retained on the balance remain reusable. Only
provider-driven online withdrawals/refunds are deferred.
Correcting a fictitious receipt is separate: undo its dependent assignments
before reversing its credit. Do not use order-payment reset to reverse a
real receipt. Remove active `FAILED` payment paths, controls, and API actions;
use order cancellation to block payment, not a fictitious failure status.
Preserve historical records and applied migrations. Customers see their own
available funds, order-assigned prepayment, and debt without double counting,
separately for personal and legal accounts.
Each order is bound at creation to its owner's matching personal or legal
account; later financial operations use that recorded account.
One order may receive several confirmed payments while full shipment happens
only once. An issued invoice records the full order total at issue time;
partial receipts are separate payments and do not rewrite the invoice amount.
Payments may reference the invoice they were made against, while office
receipts may have no invoice. Historical links survive invoice replacement.
PHASE 23 includes manager edits to order items before shipment,
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
not build a partial-shipment UI in this phase. Adapt receipt and invoice
workflows incrementally while preserving historical data and audit records.
Do not convert legacy pending payments into received money implicitly.
Completed foundation and invoice block (2026-10-17): HTML and API checkout
save `Order.payment_method` without creating a payment. Manual online-method
confirmation is not enabled. The atomic `record_manual_order_payment` service
records an actual office or bank receipt with one idempotent account credit;
its website/API registration interface remains to be connected. `Payment.order`
allows several payments, and the transitional `deposit_transaction` link
prevents legacy reset-to-pending from undoing a credited receipt. Legacy
records are not credited implicitly. Active `FAILED` paths have been removed.
`Invoice.payment` is optional and `Invoice.order` allows document history,
with a database constraint permitting only one issued invoice per order.
Managers and administrators can issue and cancel invoices on the website and
through the API. Cancellation requires a reason and preserves its actor,
time, and document number; replacement creates a new document and number.
Clients can read and download their own invoices without a payment. Staff
order details show invoice history in pages of 20 with PDF links and preserved
list-return context. These document actions create neither receipts nor debt.
The user reports the full project test suite passing; Ruff checks and migration
drift checks pass. Manual website invoice and history checks also pass.
Pre-shipment assignment milestone (2026-10-18): `OrderFundAssignment` and
`OrderFundAssignmentSource` retain the order/debit link and each deposit
portion used. Active staff explicitly choose the order and amount; the
service selects eligible unused deposit portions FIFO within the same
account and currency. Available funds decrease without creating debt.
Whole selected assignments can be released with a required comment and a
linked ledger reversal; original assignments/sources remain in history and
released funds are reusable. Historical reversed assignments do not consume
the order amount or deposit capacity. A same-key retry is idempotent, while
conflicts and a different-key second cancellation are rejected.
Authorized manager order cancellation and customer cancellation of their own
new order automatically release active assignments atomically with status
and stock changes. Customers still cannot manually cancel assignments.
The user reports the assignment-service and existing cancellation/workflow
modules and scoped Ruff checks passing. The subsequent full run passed
760 tests on 2026-10-19, before the new shipment-foundation changes.
Staff receipt/assignment interfaces, post-shipment assignment/removal,
shipment obligations, receipt correction and manual payout remain open.
Shipment foundation (2026-10-19): `OrderShipment`, `OrderShipmentItem` and the
debt-only `FUNDS_APPLICATION` finance primitive are implemented; the user reports
their module tests and scoped Ruff checks passing. The separate
`OrderFundApplication` is implemented; its three model tests and scoped Ruff
checks pass. At that checkpoint, completion was not yet connected to the
financial workflow. The implemented service and its connection were verified
on 2026-10-20 below.
Scope decision (2026-10-19): preserve one shipment per order and add explicit
confirmation before `Complete order`. No shipment correction/reopening,
replacement shipment or shipment-reversal interface is included in PHASE 23.
Server permissions, validation, atomicity and retry safety remain required.
Goods returns remain deferred; agreed money correction/refund actions are
separate and do not reopen shipment.
Full-shipment milestone (2026-10-20): `complete_order_shipment()` atomically
creates the shipment, item snapshots, full debt and application of active
prepayment, then completes the order. Authorized retries return the existing
result. The existing website/API status actions delegate to it; the website
asks for confirmation and unauthorized completion POSTs receive 403.
The user reports 19 service tests, related modules, scoped Ruff, migration-drift
checks and a full **796-test** run passing. Runtime migrations were applied;
manual unpaid-order completion created the full debt with unchanged available
funds. Independent concurrent-workflow coverage remains open.
Next: extend assignment/removal after shipment with debt reconciliation while
keeping `COMPLETED`; then connect receipt/assignment forms, customer balances
and the shipped-unpaid order list. Follow with safe receipt correction/manual
cash-bank refunds, invoice snapshots and pre-shipment editing, then concurrency,
full regression and the minimal 1C exchange contract. These are the six execution
milestones in the phase plan; PHASE 23 is not yet complete.
See the [model diagrams and settlement example](phase-23-deposits-and-order-settlement.md#order-funds-models)
and the [README model map](../README.md#order-funds-models).
Existing debt allocation cannot be reused before an order has debt. Funding
source traceability does not yet implement dependency-safe receipt correction.
The detailed phase plan and local Russian copy record the current boundary.
Application code, tests, and migrations remain user-edited and user-run.
The exit goal is a testable order-to-money flow
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
-   broader refund processing connected to product returns; manual actual
    office cash and bank-transfer refunds are already required in PHASE 23
-   provider-driven online withdrawal/refund requests and automation
-   advanced balance-reservation workflows; basic order prepayment
    assignment and release are already required in PHASE 23
-   approval workflow
-   reconciliation
-   partial-shipment UI and advanced allocation rules
-   complex mixed-payment checkout and external-provider integration;
    separate office and bank receipts for one order remain in PHASE 23

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
