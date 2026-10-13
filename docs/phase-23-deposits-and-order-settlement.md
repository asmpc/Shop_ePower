# PHASE 23 — Order Funds and Full-Shipment Settlement

Status: design draft; implementation has started with order-to-account linking.
Remaining business rules and model boundaries are being refined.

## Goal and Boundaries

Build the smallest reliable link between an order, confirmed customer funds,
full shipment, and any remaining debt. Preserve the immutable account ledger
and atomic balance services from PHASE 22. The result must be demonstrable
with test data before the minimal 1C integration in PHASE 24 and the
internet-facing test pilot in PHASE 25.

Do not replace the existing `Payment` and invoice workflows in one step.
The model may allow later partial shipments, but a partial-shipment action
and UI are out of scope now. Mixed payments, automatic allocation,
withdrawals, returns logistics, and a real payment provider are deferred.

## Confirmed Business Rules

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
  receipt funds the customer account; a later explicit staff allocation
  settles the shipment debt.
- The existing manager/administrator `Mark as paid` action is the manual
  confirmation point after office payment or verified bank receipt. It
  currently changes `Payment` to `PAID` and records payment history, but
  does not credit the customer financial account. PHASE 23 must connect
  this existing action to one idempotent account credit; do not add another
  confirmation button. `Mark as cancelled` and `Mark as failed` do not
  confirm receipt of money.
- Confirming receipt credits available customer funds but does not settle
  any order debt automatically. A manager or administrator explicitly
  chooses an unpaid shipped order and the amount to allocate, bounded by
  both available funds and that order's remaining debt.
- The customer must see their own personal and legal accounts separately
  in the website account area: currency, unallocated available funds
  (prepayment), and outstanding debt. This read-only view must not expose
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

## Business Flow to Model

1. After actual office payment or verified bank receipt, the authorized
   employee uses the existing `Mark as paid` action. Its confirmed `Payment`
   identifies the funding source and creates one idempotent account credit.
   This increases available funds only; no debt is settled yet. It may
   happen before or after shipment.
2. The `Complete order` action records the full shipment and an obligation
   for its value in the correct personal or legal customer account, then
   moves the order to `COMPLETED`. This increases debt only; available
   funds are not allocated automatically. A retry must not ship or charge
   twice.
   Before this action, a manager may revise the order items and total;
   previously received funds remain unchanged. An issued invoice must be
   cancelled before the edit and replaced afterward.
3. A manager or administrator explicitly allocates a chosen amount of
   available funds to a chosen shipped-order obligation. The allocation
   records which confirmed funding it uses and reduces both available
   funds and debt through PHASE 22 services. It cannot exceed either
   available funds or that order's remaining debt. Outstanding debt
   remains visible until settled.
   Partially paid shipped orders remain in the staff unpaid-orders list
   with their remaining amount; fully settled orders leave that list.
4. To reset an incorrectly confirmed `Payment` to `PENDING`, first undo
   every allocation depending on that funding, then reverse its account
   credit, then reset the payment status. Never reset the status while a
   dependent allocation or credit remains. Preserve an auditable trail and
   roll back a failed correction instead of leaving mismatched states.

Example: a confirmed payment of 100.00 adds 100.00 available funds; shipment
of an 80.00 order adds 80.00 debt. Until a manager allocates funds, both
balances remain visible. Allocating 50.00 leaves 50.00 available and 30.00
debt. These are separate steps even when payment precedes shipment.

For a 120.00 shipped order, two confirmed receipts of 100.00 and 20.00
create two funding records. The manager may allocate 100.00 first, leaving
20.00 order debt, and later allocate the remaining 20.00. The shipment is
still recorded only once.

An order initially totaling 100.00 may receive 60.00 before shipment. If
the manager changes its items and total to 120.00 before shipment, the
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

## Decisions to Confirm Before Schema Changes

- Which stable key links a manager-confirmed `Payment` in `PAID` state to its
  account credit without double crediting? Define what evidence of office
  payment or bank receipt is recorded.
- `Payment.order` is currently one-to-one, while `Invoice` also links to a
  payment and existing views assume `order.payment`. Decide the smallest
  migration to multiple payments per order, including invoice behavior and
  preserving existing order/payment pages. A confirmed payment must carry
  its actual received amount, not silently inherit a changed order total.
- `Invoice.order` is also currently one-to-one. Define the smallest way to
  preserve a cancelled invoice and issue its replacement for the same order,
  with no more than one active invoice at a time.
- Define how existing pre-PHASE-23 orders receive the correct account link
  during migration. New checkouts reject a missing account; decide separately
  how to handle old demonstration orders that have no account.
- Which item, price, tax, and delivery snapshots form the full shipment
  amount? How will the model permit partial quantities later?
- How are allocations linked to the specific funding they used, so all
  dependent allocations can be found and undone before that payment is
  reset? Define an auditable, safe correction flow and its atomic boundary.
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

1. Inspect the current `Order`, `Payment`, invoice, and finance service
   boundaries. Write numerical examples for payment before shipment,
   shipment before payment, multiple payments, retry, and correction;
   resolve the questions above before writing migrations.
2. Define a shipment record and the links among order, customer account,
   shipment debt transaction, funding transaction, and allocation. Make
   order-item quantities representable for future partial shipments, but
   implement only a full-shipment action now. Migrate the payment/order
   relationship to allow multiple payment records without breaking invoices
   or existing order and payment pages. Allow a cancelled invoice to be
   replaced while preserving its history.
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
5. Connect the existing `Mark as paid` action to one account credit without
   allocating it automatically. Add a separate, authorized manager/admin
   action to allocate an explicit amount to one shipped order. Test both
   payment-before-shipment and payment-after-shipment, partial allocation,
   multiple receipts, amount limits, retries, and the absence of implicit
   settlement.
6. Add the customer-facing, read-only account balances and test account
   ownership, separate personal/legal balances, available prepayment,
   debt, and currency.
7. Add the correction sequence: undo dependent allocations, reverse the
   payment's account credit, then reset `Payment` to `PENDING`. Test
   reversal guards, audit trail, rollback, and concurrency; integrate one
   existing payment path at a time without a wholesale rewrite.
8. Build the manager/administrator list of shipped orders with remaining
   debt. Show customer, order, shipment, and outstanding amount; paginate
   it and provide useful search or filters. Test unpaid, partly paid, and
   fully settled cases, including office and bank-transfer confirmation.
   Reconcile list amounts with account and shipment obligations.
9. Run the complete regression and document the narrow 1C exchange facts
   needed in PHASE 24. Do not begin internet deployment in this phase.

## Verification Gates

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
- `Mark as paid` credits available funds once but never allocates them by
  itself. Only an explicit staff action settles a selected order and amount.
  A payment reset with dependent allocations is rejected until those
  allocations and its credit are safely reversed in order.
- Customers see only their own account balances: unallocated prepayment and
  debt, separately for personal and legal accounts.
- Completing an order confirms exactly one full shipment and creates debt
  exactly once. The order may be complete while its debt remains unpaid.
  The staff order-level debt list agrees with the unpaid shipment obligations,
  and a confirmed office or bank-transfer receipt is required to settle them.
- Existing order, payment, invoice, and PHASE 22 tests remain green.
