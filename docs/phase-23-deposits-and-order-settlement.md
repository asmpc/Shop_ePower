# PHASE 23 — Order Funds and Full-Shipment Settlement

Status: implementation in progress. The receipt-service foundation,
order-based invoice block, and pre-shipment fund-assignment and release
services are implemented. Staff money-operation interfaces, full-shipment
settlement, post-shipment assignment/removal, and manual money-out refunds
remain open. PHASE 23 is not complete.

## Completed Steps and Current Implementation Boundary

As of 2026-10-17:

- New orders record their owner's matching personal or legal customer
  account. Missing accounts reject checkout without implicit account
  creation. The nullable relation preserves old demonstration orders.
- Website and API checkout save `Order.payment_method` without creating a
  `Payment`, invoice, or ledger operation. Unsupported online checkout and
  on-receipt payment for shipping are rejected.
- `Payment.order` permits several payments per order. The atomic
  `record_manual_order_payment` service creates a confirmed receipt and one
  idempotent account credit through `Payment.deposit_transaction`. Receipt
  retries, conflicting keys, rollback, and staff permissions have tests.
  The staff website/API receipt-registration interface remains to be connected.
- Legacy `reset_payment_to_pending()` rejects a payment linked to a financial
  deposit. This protects the receipt; it does not implement removal of an
  order fund assignment. Legacy records are not credited implicitly.
- Active `FAILED` statuses, actions, controls, and API paths have been removed.
  Historical records and applied migrations are not rewritten.
- `create_invoice_for_order()` issues the full order amount without requiring
  a payment; the current issue workflow requires `PaymentMethod.INVOICE`.
  `Invoice.payment` is optional. `Invoice.order` permits document history,
  with a conditional database uniqueness constraint allowing only one
  `ISSUED` invoice per order.
- Managers and administrators can issue and cancel invoices on the website
  and through the API. Cancellation requires a reason and preserves its
  actor and time. Reissue retains the cancelled document and number and
  creates a new document with a new number. These document actions do not
  create receipts or change account balances or debt.
- Clients can read and download their own invoices by invoice ID without
  a payment; foreign documents are inaccessible. Staff order details show
  the current invoice and a history with cancellation details and PDF links.
  History uses pages of 20 and preserves the list-return context.
- The user reports the complete project test suite passing. Ruff and
  migration-drift checks pass; manual website invoice and history checks
  pass. No mass formatting was applied: intentional multiline layout is
  retained, while `ruff check` remains required.

As of 2026-10-18, the pre-shipment assignment milestone is implemented:

- `FUNDS_ASSIGNMENT` and `record_customer_funds_assignment()` decrease
  available funds without creating debt. `OrderFundAssignment` links the
  order, amount, and unique financial debit; `OrderFundAssignmentSource`
  records each deposit portion used. Database constraints require positive
  amounts and one source row per assignment/deposit pair.
- `assign_order_funds()` lets an active manager or administrator select an
  order and amount. It locks the order and account, validates account owner,
  type and currency, enforces available-funds and remaining-order limits,
  and atomically records the debit, assignment, and sources. Eligible deposit
  portions are selected FIFO by `created_at`, then `pk`; already used portions
  and reversed deposits are excluded. No debt is created before shipment.
- `cancel_order_fund_assignment()` releases one whole selected assignment
  with a required non-blank comment. An additional ledger `REVERSAL` records
  its reason, actor and time; the original assignment and source rows remain.
  Order/source-capacity calculations exclude reversed assignments, so released
  money can be assigned again without changing the receipt or other
  assignments. Identical retries return the original result; conflicting
  keys and a new-key second cancellation are rejected.
- Manager order cancellation and customer cancellation of their own `NEW`
  order release active assignments within the same transaction as status and
  stock changes. Failure rolls back the cancellation. Customer-triggered
  release uses the private internal helper after order permissions are
  checked; customers still cannot manually cancel an individual assignment.
  The financial history retains the initiating user and actor type.
- The user reports 31 assignment-service tests, the existing cancellation
  and manager-workflow modules, and scoped Ruff checks passing. Model tests
  and migration-drift checks also passed during this milestone. The last
  reported full-project run remains 720 tests on 2026-10-17; a fresh complete
  regression for this block has not yet been reported. Checks are user-run.

These are service-layer capabilities, not new staff receipt/assignment forms
or API actions. New migration files must be applied separately to the running
database before using the new records there. Full-shipment records and debt,
post-shipment assignment/removal, customer balances, pre-shipment item
editing, safe receipt correction, and actual manual refunds remain open.

## Goal and Boundaries

Build the smallest reliable link between an order, confirmed customer funds,
full shipment, and any remaining debt. Preserve the immutable account ledger
and atomic balance services from PHASE 22. The result must be demonstrable
with test data before the minimal 1C integration in PHASE 24 and the
internet-facing test pilot in PHASE 25.

Do not replace the existing `Payment` and invoice workflows in one step.
The model may allow later partial shipments, but a partial-shipment action
and UI are out of scope now. Complex mixed-payment checkout, automatic
selection of orders/amounts to pay, goods-return logistics, and a real payment
provider are deferred. Separate office and bank receipts for one order, pre-shipment
fund assignment, and actual manual cash/bank refunds are in scope. Only
provider-driven online withdrawals/refunds are deferred, not all refunds.
This does not introduce a new post-shipment goods-return workflow.

## Clarification of 2026-10-15: Order Payment and Manual Refunds

- Receipt registration and assigning funds as payment for an order are
  separate actions. `Payment` records a receipt; its `PAID` status alone
  does not mean the order has been paid. Derive order settlement from active
  fund assignments, not just the sum of related receipts.
- Fulfillment and settlement remain independent. Removing payment from a
  shipped order does not change `COMPLETED`. Preserve other assignments
  and the remaining amount when one assignment is removed.
- Both managers and administrators may explicitly assign available funds
  before or after shipment. Before shipment, assigning 100 BYN from an
  available 100 leaves freely available funds at zero and debt at zero.
  Those funds cannot simultaneously be assigned to another order.
- Removing an order payment assignment requires a non-blank comment and
  preserves its reason, actor, time, amount, order link, and append-only
  history. Before shipment, it restores the available 100 and leaves debt
  at zero. The actual receipt and its account credit remain unchanged.
- The removal action is the same whether the employee selected the wrong
  order or later discovered a fictitious receipt. Correct the receipt
  separately after undoing dependent assignments; never restore an entire
  old balance snapshot or modify unrelated receipts.
- Within existing cancellation permissions, cancelling an order releases
  assigned funds for reuse and blocks new assignments. It does not prove
  cash was paid out or a bank refund occurred.
- PHASE 23 includes actual manual office-cash and bank-transfer refunds.
  Staff separately confirm the real payout and record its amount, method,
  reason, actor, time, and funding link. The money-out operation, available
  balance decrease, and history are atomic and idempotent. Do not refund
  more than the funds available for that refund or erase the original receipt.
- Remove active `FAILED` paths rather than using failure as a cancellation
  lock. Check the order's cancelled state to reject new payment assignments.
  Preserve historical data and applied migrations; agree any demonstration
  data cleanup separately.
- Shipment accounts for assigned prepayment exactly once. Assigned 100 with
  zero freely available, followed by shipment of 100, must not deduct 100
  again or leave debt on a fully covered order. An obligation arises only
  at shipment; do not create fictitious debt before it.
- Existing `allocate_customer_funds()` decreases both available funds and
  debt and cannot implement pre-shipment assignment. Existing
  `record_customer_refund()` increases available funds and is not a real
  payout. Define correct public financial operations instead of writing
  balance fields directly.

## Confirmed Business Rules

- Clarified on 2026-10-14: choosing a payment method at checkout is not
  evidence that money has been received. Checkout stores that preference on
  the order but creates no `Payment`, account credit, or customer debt.
  An order awaiting payment does not require a pending receipt record or a
  new fulfillment status.
- An actual office payment creates `Payment` only when an authorized
  manager or administrator records and confirms the received amount.
  Verified bank receipts follow the same rule. In one atomic operation,
  create `Payment` directly in `PAID`, record exactly one account-ledger
  credit, and increase the customer's unallocated available balance.
  Either all changes are saved or none are saved; a retry must not create
  another payment or credit. Debt settlement remains a separate staff action.
- Event boundaries are explicit:

  | Event | Create `Payment`? |
  |---|---|
  | Customer places an order and selects office payment | No |
  | Employee issues an `Invoice` | No: it is a document requesting payment |
  | Employee confirms money actually received in the office | Yes |
  | Employee confirms a verified bank receipt | Yes |
  | Employee assigns already received funds to an order before or after shipment | No: this is a separate financial operation |

  For a 100 BYN order, an actual office receipt of 40 BYN creates one
  `Payment` for 40 BYN. A later bank receipt of 60 BYN creates a second
  `Payment` for 60 BYN. Before the money arrives, there are no payments.
- `CustomerAccount` stores the customer's available prepayment and debt;
  `Invoice` is an optional document requesting payment; `Payment` records an
  actual confirmed receipt. An invoice is not required for every order and
  must be issued from the order without requiring a fictitious payment.
- Order placement and invoicing do not create customer debt. Debt arises only
  after shipment is confirmed, for the shipped value.
- In the current business workflow, `Complete order` means full shipment of
  the order. Today the button only changes status; PHASE 23 must make the
  action record that shipment and its debt exactly once, atomically with the
  transition to `COMPLETED`. An unpaid order may still be `COMPLETED`.
- `OrderStatus.SHIPPED` is declared but currently unused. It is reserved for
  a future delivery flow where goods have been dispatched but not received.
  Receiving that delivery must not create debt a second time.
- Use an explicit shipment identity and an order-item quantity foundation
  so later partial shipments can be represented without multiplying order
  statuses. Do not implement partial shipment in this phase.
- One order may receive several separate `Payment` records, each confirmed
  for the amount actually received and credited exactly once. Full shipment
  remains a single action in this phase. For example, a 120.00 order may
  receive 100.00 first and 20.00 later; neither receipt automatically
  allocates funds to its debt.
- Managers and administrators need a separate website view of outstanding
  shipment debt. Its primary operational view must be a
  list of shipped orders with an unpaid amount, showing the customer,
  shipment, and remaining amount for each order. A customer summary may
  complement this view, but must not replace the order-level list. Limit
  and paginate it; do not load settled shipment history by default.
- Initially, actual payment is accepted only in the office or by bank
  transfer. Selecting a payment method, issuing an invoice, or marking an
  order `COMPLETED` does not prove that money was received. A confirmed
  receipt funds the customer account; a separate explicit staff assignment
  pays the order before shipment or settles its debt afterward.
- Manual receipt recording accepts the actual received amount, rather than
  confirming a pending payment automatically prepared for the order total.
  Do not carry over the old pending-payment buttons without reconsidering
  their meaning. Office and bank receipts use one explicit registration
  step that creates a confirmed receipt, not a `PENDING` draft followed by
  a later transition to `PAID`. Legacy pending and mock records must never
  be treated as received money implicitly.
- Confirming receipt credits available customer funds but never assigns
  them to an order automatically. A manager or administrator selects an
  order and explicit amount, bounded by freely available funds and the
  remaining amount to pay. After shipment, respect that order's remaining
  debt as well. Before shipment, assignment must not create debt.
- After staff explicitly select the order and amount, choose its funding
  sources automatically FIFO within that same account and currency. Use
  only unused portions of non-reversed deposits, including usage by other
  orders. Deposits of 40 and 60 funding an assignment of 70 contribute 40
  and 30; the second deposit retains 30. This source selection is not
  automatic order assignment or automatic debt settlement.
- Cancel only a whole selected assignment in this phase. To correct an
  assignment of 70 to 50, cancel the 70 and create a new assignment of 50.
  Do not edit or delete the original assignment or its source rows. A
  separate linked reversal is the cancellation history; no additional
  cancellation table is required for the pre-shipment service.
- Only assignments whose financial debit has no reversal consume the
  remaining order amount or a deposit's unused portion. Historical sources
  remain traceable but must not keep released money unavailable.
- Customers cannot manually assign or remove order funds. Cancelling their
  own `NEW` order may automatically release its active assignments after
  checking ownership, active user, and current order status. This permission
  does not expose the private release helper through a view or API action.
- The customer must see their own personal and legal accounts separately
  in the website account area: currency, unallocated available funds
  (prepayment), order-assigned prepayment, and outstanding debt without
  double counting. This read-only view must not expose
  another customer's balances or create accounts implicitly.
- Bind each order to one specific `CustomerAccount` when the order is created.
  A personal order uses its owner's personal account; a legal-entity order
  uses that owner's legal account. Payment credits, shipment debt, and
  allocations use the account recorded on the order, not a later inference
  from the user's current profile or role. Reject an account owned by
  another user or of the wrong type; never silently reassign an existing
  order to another account.
- At checkout, require the matching account to exist. If it is missing,
  reject order creation with a clear error and leave the cart, stock, and
  order data unchanged. Do not create or repair an account implicitly during
  checkout; fix the missing registration/profile workflow separately.
- PHASE 23 includes manager editing of order items before full shipment,
  including when part of the price has already been received. Confirmed
  `Payment` amounts and account credits represent actual receipts and must
  not be rewritten when the order total changes. No order-item editing is
  allowed after shipment is recorded.
- The manager coordinates a proposed edit with the customer outside the
  website, using an available communication channel, before saving it.
  Saving the edit means the manager takes responsibility for that agreement.
  Do not add an online customer-approval step, pending-change state, or
  approval workflow in PHASE 23. If the customer disagrees, existing
  pre-shipment cancellation rules apply; a new order can then be placed.
- If an invoice was issued, the manager must explicitly cancel it before
  editing the order and issue a new invoice for the revised total afterward.
  Never silently change an issued invoice. Updating order items must also
  keep the order total and stock reservations consistent.
- An additional quantity of a product is a new order item with the current
  validated selling-price snapshot and its own stock reservations, even if
  the product already appears in the order. Existing item prices, quantities,
  and reservations are not silently extended or repriced. Separate price
  batches of the same product remain visible as separate lines.
- Before the manager adds a new order line, recalculate the customer-facing
  selling price from current supplier pricing using the project's pricing
  rules, show the result, and require explicit confirmation. Do not accept
  the new line at a stale catalog price. If the confirmed price changes
  before saving, require confirmation again; existing lines stay unchanged.
- To reduce or remove a quantity, the manager explicitly selects the order
  line/price batch to change. The system must not choose between older and
  newer price batches automatically. Recalculate the total and adjust only
  the selected line's reservations, without repricing the other lines.
- Within the selected line, release stock reservations in the reverse order
  of their original allocation: supplier stock before own warehouse stock.
  For a line reserved as four own-stock units and three supplier units,
  reducing quantity by two releases two supplier units.
- Every manager edit to order items requires a non-blank reason. Record a
  separate append-only order-change history entry for each successful edit:
  who made it, when, why, which item/price batch was added, reduced, or
  removed, the before/after quantity and price snapshot, and the before/after
  order total. Preserve enough detail to explain the reservation change.
  A rejected or rolled-back edit must leave neither a history entry nor a
  partial change to the order total or stock reservations.
- The customer-facing order page shows the updated items, quantities, prices,
  and total, with a visible indication that the order was changed. The
  manager's reason and internal order-change history are available only to
  managers and administrators; never expose them in the customer UI or API.
- An issued invoice records the full order total at issue time.
  Partial receipts are separate Payment records and do not rewrite
  the invoice amount.
- Both managers and administrators may issue and cancel invoices. An issued
  invoice blocks another issue for that order until explicitly cancelled.
  Cancellation preserves the document, number, required reason, actor,
  and time; a replacement has its own number. Keep at most one `ISSUED`
  invoice per order, enforced by the database. Invoice creation and
  cancellation do not record receipt or settle an order.
- A payment may reference the invoice it was made against.
  Office receipts may have no invoice. Existing payment-to-invoice
  references survive invoice cancellation or replacement.

## Business Flow to Model

1. After actual office payment or verified bank receipt, an authorized
   employee enters the received amount and confirms receipt registration.
   In one atomic operation, create `Payment` directly in `PAID` and one
   idempotent account credit, updating the available balance. This increases
   available funds only; no debt is settled yet. It may happen before or
   after shipment. No pre-existing pending payment is required.
2. A manager or administrator explicitly assigns funds to a selected order.
   Before shipment, freely available funds decrease by the assigned amount,
   but debt remains zero. Record the funding source, order, and amount to
   prevent double use. After shipment, assignment settles that order's debt.
   Do not use the existing debt-allocation operation before shipment.
3. The `Complete order` action records the full shipment and its obligation
   in the correct personal or legal customer account, then moves the order
   to `COMPLETED`. Account for already assigned prepayment exactly once,
   without deducting freely available funds again. The uncovered amount
   becomes outstanding debt; without assignments, the full amount is owed.
   Do not automatically select free funds for a new assignment. A retry
   must not duplicate shipment, obligation, or application of prepayment.
   Before this action, a manager may revise the order items and total;
   previously received funds remain unchanged. An issued invoice must be
   cancelled before the edit and replaced afterward.
   Later explicit assignment of available funds settles the remaining
   obligation, bounded by both available funds and that order's debt.
   Partially paid shipped orders remain in the staff unpaid-orders list
   with their remaining amount; fully settled orders leave that list.
4. Removing an order payment assignment releases its funds and recalculates
   settlement using the remaining assignments. After shipment, restore the
   corresponding debt while keeping `COMPLETED`; before shipment, debt
   stays zero. Preserve the real `Payment` and credit. A non-blank comment
   and append-only audit history are required.
5. To correct an incorrectly recorded receipt, first undo every assignment
   depending on that funding, then reverse its account credit. Decide the
   resulting receipt status and correction UI separately: the old return
   to `PENDING` is not automatically appropriate for the new meaning of
   `Payment`. Preserve an auditable trail and roll back a failed correction
   instead of leaving mismatched states.
6. Cancelling an order releases its assigned funds to the available balance,
   blocks new assignments, and does not pay money out automatically.
   Existing restrictions on post-shipment cancellation remain in force.
7. An actual cash payout or bank refund is recorded separately by staff.
   Decrease available funds by its amount and retain the real payout and
   audit history without duplicates. This manual refund is required now;
   provider-driven online withdrawal integration is deferred.

Example without pre-shipment assignment: a confirmed receipt of 100.00 adds
100.00 available funds; shipment of an 80.00 order adds 80.00 debt.
Until a manager allocates funds, both
balances remain visible. Allocating 50.00 leaves 50.00 available and 30.00
debt. These are separate steps even when payment precedes shipment.

For a 120.00 shipped order, two confirmed receipts of 100.00 and 20.00
create two funding records. The manager may allocate 100.00 first, leaving
20.00 order debt, and later allocate the remaining 20.00. The shipment is
still recorded only once.

Pre-shipment assignment example: receipt of 100.00 creates available funds
of 100.00. Assigning all 100.00 to the order leaves freely available funds
at zero and debt at zero. Shipment of 100.00 accounts for that assignment
once and leaves no unpaid debt; it must not deduct another 100.00.

Manual refund example: after assigning the received 100.00 before shipment,
cancelling the order restores available funds to 100.00 but does not pay the
customer. A separately confirmed cash or bank refund of 100.00 then leaves
available funds at zero, preserving both the original receipt and refund.

An order initially totaling 100.00 may receive an unassigned 60.00 before
shipment. If the manager changes its items and total to 120.00 before
shipment, the
confirmed 60.00 stays as available funds and debt stays zero. Full shipment
then creates 120.00 debt; allocating 60.00 leaves 60.00 debt. No old payment
amount or issued invoice is silently rewritten.

If an order already contains seven units of one product at 100.00 each,
reserved as four from own stock and three from a supplier, adding five more
after the selling price changes to 130.00 creates a second order item at
130.00 with its own current-source reservations. The first seven stay at
100.00. The item total is 7 × 100.00 + 5 × 130.00 = 1,350.00 before any
separately charged delivery. Do not assume a changed supplier purchase price
has already refreshed the customer-facing catalog price: validate the price
used for the new line before accepting the edit.

The links explain *why* a balance changed. Account balances alone do not
identify the source of funds or the order being settled.

## Remaining Decisions Before Further Financial Migrations

- Receipt registration already uses a stable `operation_key` and linked
  account credit. What additional evidence of office payment or bank
  receipt should be stored when connecting the staff interface?
- Which final status and permissions are required to correct a receipt after
  safely reversing its credit? Preserve legacy `PENDING` and mock scenarios
  without fictitious credits; do not assume a reset-to-`PENDING` workflow.
- Extend the implemented assignment/source records to application of
  prepayment at shipment and removal after shipment. Preserve the verified
  pre-shipment behavior: available 100 -> assign 100 -> zero available/zero
  debt -> release back to 100. Do not substitute debt allocation or receipt
  totals for assignments or deduct prepayment twice.
- Define actual manual cash/bank refund records, funding links, permitted
  methods, staff permissions, amount, mandatory reason, and retry key.
  Choose a public money-out operation rather than the positive-delta
  `record_customer_refund()` service.
- Before order-item editing, define invoice-item snapshots: a historical
  PDF must not start showing revised order lines. The current PDF reads
  `Order.items`; preserving the document number and amount is insufficient.
- Separately verify concurrent invoice issuance and number allocation.
  The one-issued-invoice constraint does not solve all numbering races.
- Decide how to prepare old demonstration orders without an account for
  future financial scenarios and when to make the relation mandatory in
  the database. They currently retain an empty transitional relation;
  new checkouts reject a missing account without implicit assignment.
- Which item, price, tax, and delivery snapshots form the full shipment
  amount? How will the model permit partial quantities later?
- Use `OrderFundAssignmentSource` to find active assignments dependent on a
  receipt before correcting it. Define the correction's atomic boundary,
  receipt status, and dependency guards, including post-shipment effects.
  Source traceability alone does not implement safe receipt correction.
- Add independent concurrency coverage for assignment, release, and order
  cancellation on a shared account. Account locks and sequential service
  tests are not a substitute for verifying concurrent financial workflows.
- What correction is allowed if full shipment was recorded in error?
- Define the smallest append-only order-change history model and how to
  capture the manager's confirmed price and reservation changes. Implement
  reverse reservation release within the selected line, including
  multiple supplier reservations. Never silently rewrite a recorded shipment
  or financial history.
- How should the order-level debt list present multiple shipments or
  payments when these are introduced later? Keep personal and legal account
  balances visibly separate. An optional customer summary must drill down
  to individual unpaid shipped orders.

Record the chosen rules with numerical examples and expected account deltas
before writing migrations.

## Incremental TDD Work Plan

As of 2026-10-18, checkout without payments, the atomic receipt service,
removal of active `FAILED`, website/API invoicing and history, pre-shipment
assignment with FIFO sources, whole-assignment release, and release on
authorized order cancellation are implemented. Document and commit this
service-layer milestone without declaring the whole phase complete.
Before further financial migrations, define shipment settlement and use of
existing assignments with numerical examples. Connect the implemented
receipt and assignment services to staff interfaces and implement the
remaining flows by TDD.
Assignment removal, fictitious-receipt correction, and actual payout remain
different actions. Validate mandatory reasons in services, not only forms.
Do not defer manual office/bank refunds together with online withdrawals.
The user edits application code, tests, and migrations and runs all checks.
Run only the new test during each small TDD step; run the relevant module at
a completed behavior milestone. If a change crosses permission boundaries,
explain why a small additional regression set is needed. Put shared test
preconditions in `setUp()` and keep scenario-specific data in each test.

1. Inspect the current `Order`, `Payment`, invoice, and finance service
   boundaries. Write numerical examples for payment before shipment,
   shipment before payment, multiple payments, retry, and correction;
   resolve the remaining shipment/correction questions before new migrations.
   Preserve the implemented assignment and source records.
2. Define a shipment record and the links among order, customer account,
   shipment debt transaction, funding transaction, and allocation. Make
   order-item quantities representable for future partial shipments, but
   implement only a full-shipment action now. Multiple payments and invoice
   replacement with retained history are already implemented; preserve
   historical links while adding the remaining financial records.
3. By TDD, add manager editing of order items before shipment. Recalculate
   the order total and adjust stock reservations atomically; keep confirmed
   payments and account balances unchanged. Require explicit cancellation
   of an issued invoice before editing, then permit a replacement invoice.
   Add later quantities as new price-snapshot lines with separate
   reservations, even for the same product. Recalculate and display the
   current selling price before adding, and require confirmation of that
   exact price. Require the manager to select a specific line for quantity
   reduction and enter a reason for every edit. Record the actor, time,
   reason, selected line, before/after values, and order total in an
   append-only history entry within the same atomic operation. Reject edits
   after shipment.
4. By TDD, make `Complete order` record one full shipment and its debt
   atomically and idempotently. Preserve the existing user-facing workflow.
5. Connect staff interfaces to the implemented receipt service: atomic
   `Payment` in `PAID` and one idempotent account credit, without automatic
   assignment. Connect a separate manager/admin action to the implemented
   pre-shipment assignment and whole-release services. Extend domain logic
   for assignment/removal after shipment with debt reconciliation, a required
   reason and history, preserving the actual receipt. Test payment
   before/after shipment, partial assignment, multiple receipts, amount
   limits, retries, and absence of implicit settlement. Preserve automatic
   release within authorized order cancellation.
6. Add the customer-facing, read-only account balances and test account
   ownership, separate personal/legal balances, freely available and
   order-assigned prepayment, debt, currency, and no double counting.
7. After agreeing on the resulting receipt status, add the correction
   sequence: undo dependent allocations, reverse the receipt's account
   credit, and record the correction without losing history. Test reversal
   guards, audit trail, rollback, and concurrency; integrate one existing
   payment path at a time without a wholesale rewrite.
8. Build the manager/administrator list of shipped orders with remaining
   debt. Show customer, order, shipment, and outstanding amount; paginate
   it and provide useful search or filters. Test unpaid, partly paid, and
   fully settled cases, including office and bank-transfer confirmation.
   Reconcile list amounts with account and shipment obligations.
9. By TDD, add actual manual office-cash and bank-transfer refunds: staff
   confirmation, an outgoing ledger operation, available-balance decrease,
   required reason, audit history, and protection against retries and
   excess amounts. Do not substitute assignment removal or reversal of a
   fictitious receipt for a real payout.
10. Run the complete regression and document the narrow 1C exchange facts
   needed in PHASE 24. Do not begin internet deployment in this phase.

## Verification Gates

- Before shipment, assigning an available 100 leaves freely available funds
  at zero and debt at zero. Another order cannot use the same money.
  Removing that assignment restores 100 without reversing the real receipt.
- FIFO source portions are bounded by their active use across all orders
  of the same account. Reversed deposits are excluded; reversed assignments
  no longer consume order/deposit capacity, but their history is retained.
- Whole-assignment cancellation is idempotent for the same request and key;
  a different-key second cancellation is rejected without another credit.
  Correcting an amount requires cancellation followed by a new assignment.
- Shipment accounts for assigned prepayment once: a fully covered order has
  neither a second deduction nor an outstanding unpaid debt.
- Fulfillment and settlement remain independent. Removing payment from a
  shipped order restores the corresponding debt but retains `COMPLETED`.
  Other assignments remain intact.
- Managers and administrators may remove an assignment only with a non-blank
  reason and append-only history containing actor, time, amount, and order.
- Order cancellation releases assigned funds for reuse and blocks new
  assignments; it does not automatically refund cash or a bank receipt.
- Customer order cancellation keeps its owner/`NEW` checks and records the
  initiating user in financial history without allowing manual assignment
  cancellation. A release failure rolls back order cancellation and related
  transactional changes for both customer and staff paths.
- Real manual cash/bank refunds are atomic, idempotent money-out operations,
  bounded by refundable available funds, with required reasons and history.
  They are not the positive-delta `record_customer_refund()` operation.
- Active `FAILED` paths are absent; historical records and applied
  migrations remain preserved.
- Checkout through the website or API saves the selected payment preference
  but creates no `Payment`, receipt transaction, or account credit. An order
  awaiting payment does not require a pending receipt record.
- Office-payment selection and actual office receipt registration have
  separate tests: the former creates no payment or invoice; the latter
  creates `Payment` directly in `PAID` for the amount received, exactly one
  ledger credit, and the corresponding available-balance increase.
- Failed receipt registration rolls back the payment, credit, and balance;
  retrying it duplicates none of them. Bank receipts follow the same rule.
- An `Invoice` may be issued before any receipt without a fictitious payment.
  Issuance and allocation do not create `Payment` records.
- Both staff roles may issue and cancel Invoice through the website and API.
  A required cancellation reason, actor, time, and original document number
  survive reissue. A replacement has a distinct identity and number; the
  database permits only one issued invoice per order.
- Client invoice data/PDF access checks order ownership without requiring
  a payment. Staff history is paginated and preserves list-return context.
- Before enabling order-item edits, preserve historical invoice item
  snapshots so re-downloading a cancelled document cannot rewrite its contents.
- No view, admin action, signal, or unrelated service writes balances
  directly.
- Idempotency, uniqueness, non-negative balances, and account ownership
  remain enforced.
- Order, full shipment, source of customer funds, allocation, and remaining
  obligation can be traced without double counting.
- Multiple confirmed payments may fund one order; each receipt is credited
  once, and one full shipment can be settled in separate manual allocations.
- Pre-shipment item edits preserve confirmed receipts and balances, keep
  stock reservations and order totals consistent, and require cancellation
  before replacing an issued invoice. Post-shipment edits are rejected.
- Adding the same product later never extends an old-price order item:
  existing prices stay fixed, while the new quantity uses a validated
  current selling price and separate supplier/stock reservations.
- Reducing quantity changes only the price batch selected by the manager;
  other batches keep their prices and reservations.
- Missing reasons reject order edits without changing data. Each successful
  edit creates exactly one order-change history entry; a failed atomic edit
  creates none and leaves totals and reservations unchanged.
- Customer views and APIs show the revised order but do not expose the
  manager's reason or internal change-history entries.
- Manager edits do not wait for an in-app customer approval. Existing
  cancellation permissions remain in force; this rule does not permit
  cancellation or item edits after shipment.
- Checkout without the matching personal or legal account fails clearly and
  atomically; it does not create an account as a side effect.
- Failed writes roll back ledger and linkage changes; concurrent requests
  cannot allocate the same available funds twice.
- A reversal cannot silently invalidate a dependent allocation.
- Recording an actual receipt credits available funds once but never
  allocates them by itself. Only an explicit staff action settles a selected
  order and amount. Correcting a receipt with dependent allocations is
  rejected until those allocations and its credit are safely reversed in
  order.
- Customers see only their own account balances: freely available funds,
  order-assigned prepayment, and debt without double counting, separately
  for personal and legal accounts.
- Completing an order confirms exactly one full shipment and creates debt
  exactly once. The order may be complete while its debt remains unpaid.
  The staff order-level debt list agrees with the unpaid shipment obligations,
  and a confirmed office or bank-transfer receipt is required to settle them.
- Agreed order, payment, invoice, and PHASE 22 scenarios remain covered by
  green tests. Old expectations of an automatically created pending payment
  at checkout are updated to the newly agreed business rule.
