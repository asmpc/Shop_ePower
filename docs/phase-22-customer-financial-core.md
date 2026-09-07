# PHASE 22 — Customer Financial Core

## Document Status

- Phase: PHASE 22
- Status: Requirements and architecture design
- Implementation status: Not started

This document describes the business rules, architecture, implementation
plan, and testing strategy for the customer financial core.

It is intentionally detailed so that every architectural decision can be
understood, reviewed, and implemented incrementally.

---

## 1. Purpose

The purpose of PHASE 22 is to introduce a reliable financial foundation
for tracking settlements between Shop_ePower and individual customers.

The financial core must answer two independent questions:

- how much customer money is currently available for future purchases;
- how much the customer currently owes the store.

The system is not intended to replace accounting software. Its purpose is
to support online and offline sales workflows, provide a clear customer
balance, preserve financial history, and prepare the project for deposits,
partial payments, refunds, and order settlement.

Existing order and payment workflows must continue working while the new
financial domain is introduced incrementally.

---

## 2. Phase Scope

### 2.1 Included in PHASE 22

PHASE 22 includes:

- one personal financial account for every customer profile;
- one separate legal financial account for a customer with an activated
  legal profile;
- independent balances and transaction histories for personal and legal
  purchases;
- one base currency for each project deployment;
- separate tracking of available customer funds and customer debt;
- an immutable financial transaction history;
- reversible correction operations;
- audit information for every financial operation;
- atomic financial services;
- protection against duplicate financial operations;
- selectors for reading balances and transaction history;
- automated tests for models, services, constraints, and concurrency rules;
- documentation of integration boundaries with orders and payments.

### 2.2 Not Included in PHASE 22

PHASE 22 does not implement:

- allocation of payments between orders;
- partial and mixed order payments;
- automatic use of deposits for order settlement;
- end-to-end customer refund workflows;
- withdrawals;
- return and exchange workflows;
- shared financial accounts for multiple organization employees;
- multiple customer account currencies in one deployment;
- complete manager order editing;
- complete partial shipment workflow;
- invoice revision and reissue workflow;
- tax accounting or general bookkeeping.

These capabilities belong to later phases. However, the financial core must
be designed so that they can be added without rewriting its transaction
history.

---

## 3. Confirmed Business Rules

### 3.1 Account Ownership

A customer profile may have up to two independent financial accounts:

- one personal account;
- one legal account connected to the customer's legal profile.

The personal account is used when the customer purchases as an individual.
The legal account is used when the customer purchases on behalf of a legal
entity or an individual entrepreneur.

Personal and legal funds, debt, and transaction histories must never be mixed.

The current `LegalProfile` model allows no more than one legal profile for a
user. PHASE 22 therefore does not support multiple legal financial accounts
for one user.

Different users may provide the same company details. Matching company names,
tax identifiers, bank details, addresses, or other legal requisites must not
merge their financial accounts automatically.

A shared organization account with multiple employee access is not required
for the current business workflow.

### 3.2 Manager-Created Customers and Orders

A manager must eventually be able to create a customer and an order after
receiving a request by phone or through another offline channel.

The customer must later be able to obtain access to the corresponding
profile, review the order, and pay for it online.

Company details alone must never be sufficient to obtain access to another
customer profile.

This workflow is an integration requirement for future order management. Its
complete implementation is outside PHASE 22.

### 3.3 Base Currency

Each project deployment has exactly one base currency.

The initial deployment uses BYN. Other deployments may use another configured
base currency, such as RUB or USD.

Supplier prices may originate in different currencies, but customer financial
accounts are maintained only in the deployment base currency.

Every financial transaction must store its currency snapshot. Changing the
base currency for a database that already contains financial operations
requires an explicit migration procedure and must never silently reinterpret
historical amounts.

### 3.4 Available Funds and Debt

Available customer funds and customer debt are separate financial values.

They must not be replaced by a single net balance because both values may
exist at the same time and may have different business meanings.

A derived net position may be displayed for informational purposes, but it
must not replace the original values.

### 3.5 Debt Recognition

Creating or editing an order does not immediately create financial debt.

Before shipment, an unpaid order represents an amount to be paid, but this
amount remains part of the editable order workflow.

Customer debt is recognized when goods are actually shipped.

For a partial shipment, debt is recognized only for the shipped part. The
remaining unshipped part of the order may still be edited.

### 3.6 Order Editing and Shipment

Payment does not lock the order against editing.

The manager may edit the unshipped part of an order even when the order is
partially or fully paid.

Already shipped quantities and their commercial conditions must not be
rewritten. After complete shipment, the order is closed for ordinary editing.

Changes to shipped goods must be represented by later business operations,
such as returns or corrections.

### 3.7 Immutable Financial History

A financial transaction cannot be edited or deleted after creation.

An incorrect transaction must be corrected by creating a separate reversing
transaction. The reversal must reference the original transaction and record
who performed the correction, when it was performed, and why.

If an amount was recorded incorrectly, the process is:

1. preserve the original transaction;
2. create an equal reversing transaction;
3. create a new transaction with the correct amount when necessary.

This rule preserves a complete and explainable audit trail.

### 3.8 Account Creation and Lifecycle

A personal financial account is created explicitly as part of successful
customer registration.

Both API and template registration flows must call the same financial account
creation service. User creation and personal account creation must complete
inside one database transaction.

No Django signals are used.

A legal financial account is created only when the customer explicitly saves
a valid legal profile with `is_legal_entity=True`.

The existence of a `LegalProfile` row is not sufficient because the current
application may create an empty legal profile when the customer opens a
profile page.

Disabling legal purchasing or changing the user role must not delete an
existing financial account or its transaction history.

Existing customers receive personal financial accounts through an explicit
data migration. Staff and superusers must not receive customer financial
accounts from that migration.

## 4. Current System Analysis

PHASE 22 extends the existing architecture instead of replacing the order and
payment domains.

This section records the responsibilities and limitations of the current
models before the customer financial core is designed.

### 4.1 Order

`Order` belongs to one user through a protected foreign key. This matches the
business rule that financial ownership is based on the customer profile and
not on matching company details.

The model stores customer, company, delivery, total amount, and currency
snapshots. These values describe the commercial state of the order.

The current `OrderStatus` contains both payment-related and fulfillment-related
states:

- `NEW`;
- `PROCESSING`;
- `PAID`;
- `SHIPPED`;
- `COMPLETED`;
- `CANCELLED`.

A single status value cannot represent independent states at the same time.
For example, it cannot accurately describe an order that is partially paid
and partially shipped.

`Order.total_price` represents the current total price of the order. It does
not represent available customer funds, received payment, customer debt, or
an immutable financial fact.

The model currently declares `delivery_address` twice with identical field
options. The second declaration replaces the first one at Python class
construction time. This is a separate cleanup issue and is not part of the
financial domain design.

### 4.2 OrderItem

`OrderItem` stores:

- the related product;
- a product name snapshot;
- unit price;
- ordered quantity;
- total price;
- currency snapshot.

The model contains one quantity and one unit price for the entire order item.
It does not store shipped quantity.

This structure cannot independently represent a position where part of the
quantity has already been shipped and the remaining part is later edited at a
different price.

The model also does not enforce the relationship between `quantity`,
`unit_price`, and `total_price`. Services that edit order items must maintain
this relationship explicitly.

### 4.3 OrderStockReservation

`OrderStockReservation` connects an order item to a supplier product and stores
the reserved quantity.

One order item may have multiple stock reservations, which allows its quantity
to be supplied from different sources.

A stock reservation is not evidence of shipment. The model itself does not
store:

- shipped quantity;
- reservation status;
- release timestamp;
- shipment timestamp.

The existing reservation lifecycle may be implemented by services, but the
reservation record must not be treated as a shipment record.

### 4.4 Payment

`Payment` is connected to `Order` through a one-to-one relationship. Therefore,
the current database structure allows no more than one payment record for an
order.

`create_payment_for_order()` creates a payment for the complete current order
total and copies the order currency.

This model is suitable for the current single-payment workflow, but it cannot
represent multiple independent payments such as:

- an advance payment;
- a later partial payment;
- a final settlement payment.

A payment must currently belong to an order. It cannot represent customer
funds received before an order is selected.

The `Payment` status describes the lifecycle of the payment attempt. A payment
with an amount of 100 in the `PENDING` or `FAILED` state is not evidence that
the store received 100.

The current payment services update the payment status without directly
updating the order status.

An administrator can reset any non-pending payment to `PENDING`, including a
previously paid payment. Future financial integration must not interpret every
transition to `PAID` as a new receipt of money.

### 4.5 PaymentHistory

`PaymentHistory` records:

- the related payment;
- old and new statuses;
- an optional comment;
- the user who made the change;
- the creation time.

It is a status change history, not a financial ledger.

It does not store the payment amount or currency at the time of the status
change. It also does not independently represent the receipt, allocation,
refund, or reversal of money.

The relationship uses cascading deletion. If a payment is deleted through an
allowed deletion path, its status history is deleted with it.

`PaymentHistory` should retain its existing responsibility. It must not become
the source of truth for customer account balances.

### 4.6 Invoice

`Invoice` has one-to-one relationships with both `Order` and `Payment`.

The invoice stores seller details, buyer details, amount, and currency as
snapshots. This preserves the parties and total amount that existed when the
invoice was issued.

A cancelled invoice remains connected to its order and payment. The current
model and validators therefore do not allow a replacement invoice for the same
order and payment.

The generated PDF uses two different data sources:

- parties and total amount are read from the invoice snapshot;
- item names, quantities, and prices are read from the current order items.

If order items are changed after invoice creation, a newly generated PDF may
show current item lines together with the old invoice total.

Invoice item snapshots and invoice revisions are outside PHASE 22, but future
order editing must not ignore this dependency.

### 4.7 Atomicity and Duplicate Processing

The reviewed payment services perform payment status updates and
`PaymentHistory` creation as separate database operations.

The reviewed API actions do not use an explicit `transaction.atomic()` block
or `select_for_update()` row lock. `ATOMIC_REQUESTS` is not configured in the
project settings.

A status check performed on an already loaded payment object does not by
itself protect against two concurrent requests reading the same `PENDING`
state.

The mock payment success and failure endpoints:

- are accessible through the payment transaction identifier;
- do not require authentication;
- do not restrict the request to the POST method;
- do not treat a repeated callback as an idempotent success.

These endpoints belong to the mock provider and are not replaced during
PHASE 22. The findings must be addressed before integration with a real
payment provider.

### 4.8 Architectural Conclusion

The existing models have valid and distinct responsibilities:

- `Order` describes the commercial order;
- `OrderItem` describes its current positions;
- `OrderStockReservation` describes reserved supplier stock;
- `Payment` describes the current payment attempt;
- `PaymentHistory` describes payment status changes;
- `Invoice` describes an issued payment document.

None of these models should be reinterpreted as the customer financial
account.

PHASE 22 introduces a separate financial domain that records customer funds,
customer debt, immutable operations, and reversals. Existing domains will be
integrated with it incrementally in later phases.

## 5. Balance Storage Strategy

A customer financial system must preserve the complete history of operations
and also return the current state efficiently.

There are three common approaches to balance storage.

### 5.1 Stored Balance Without a Ledger

The first approach stores only the current values on the customer account:

```text
available_balance = 500.00
debt_balance = 300.00
```

Every operation directly increases or decreases these fields.

This approach is simple and fast, but it cannot explain how the current values
were produced. If a value is changed incorrectly, the original history is
lost.

This approach does not satisfy the audit and immutability requirements of
PHASE 22 and is rejected.

### 5.2 Ledger-Only Calculation

The second approach stores only immutable transactions. The current values are
calculated by summing all transaction changes whenever a balance is requested.

Conceptually:

```text
current available funds = sum of all available balance changes
current debt = sum of all debt balance changes
```

This approach provides a strong historical source of truth and avoids storing
the same result in two places.

However, balance calculation becomes more expensive as the transaction history
grows. It also makes operations that require the current state more difficult.
For example, spending customer funds requires calculating and validating the
available amount while protecting the calculation from concurrent requests.

The ledger-only approach is valid, but it is not selected for the current
project because balances will be read frequently by customers, managers, order
services, and payment services.

### 5.3 Ledger With Current Balance Projection

The selected approach combines:

- an immutable transaction ledger;
- current balance fields stored on the customer financial account.

The ledger is the source of historical truth. It explains every change and can
be used to verify or rebuild the current state.

The account balance fields are a current projection of that history. They
provide fast access without recalculating the complete ledger for every
request.

Both the immutable transaction and the current account values must be updated
inside the same database transaction.

If either operation fails, the complete database transaction must roll back.

### 5.4 Separate Financial Values

The account stores two separate non-negative values:

```text
available_balance
debt_balance
```

`available_balance` represents customer money held by the store and available
for later settlement.

`debt_balance` represents financial obligations already recognized after
shipment and not yet settled.

These values are not automatically combined into one stored net balance.

A net position may be calculated for display:

```text
net_position = available_balance - debt_balance
```

The net position is derived information and is not the source of truth.

### 5.5 Example

The following example demonstrates why both values must remain separate.

| Operation | Available change | Debt change | Available after | Debt after |
|---|---:|---:|---:|---:|
| Initial state | 0.00 | 0.00 | 0.00 | 0.00 |
| Customer deposits 500 BYN | +500.00 | 0.00 | 500.00 | 0.00 |
| Goods worth 800 BYN are shipped | 0.00 | +800.00 | 500.00 | 800.00 |
| 500 BYN is allocated to the shipment | -500.00 | -500.00 | 0.00 | 300.00 |

After shipment but before allocation, the customer simultaneously has 500 BYN
of available funds and 800 BYN of debt.

Replacing these values with a single net value of -300 BYN would hide the fact
that an advance payment still exists and has not yet been allocated.

The generic atomic allocation operation is implemented as part of PHASE 22.

Connecting allocations to particular payments, orders, shipments, and
automatic settlement policies belongs to PHASE 23.

### 5.6 Consistency Rule

The application must never update account balance fields directly from views,
admin actions, signals, or unrelated domain services.

All balance changes must pass through dedicated financial services.

A financial service must:

1. start a database transaction;
2. lock the financial account row;
3. validate the requested operation;
4. calculate the new balance values;
5. reject a result that violates balance rules;
6. create the immutable financial transaction;
7. update the current account projection;
8. commit both changes together.

This serialization prevents two concurrent requests from spending or changing
the same balance based on an outdated value.

### 5.7 Reconciliation

Because the current balance is stored as a projection, the system must be able
to verify it against the transaction ledger.

A reconciliation operation recalculates expected balances from all immutable
transactions and compares them with the current account values.

Reconciliation is a diagnostic and recovery mechanism. It must not silently
rewrite the financial history.

Any inconsistency must be reported and investigated before the account
projection is corrected through an explicit controlled procedure.

### 5.8 Selected Decision

PHASE 22 uses an immutable ledger with a stored current balance projection.

This decision provides:

- explainable financial history;
- efficient balance reads;
- atomic validation and updates;
- support for future payment allocation;
- a recovery path through reconciliation;
- incremental integration with the existing project.

The design remains an internal customer settlement system. It does not
introduce a chart of accounts, accounting entries, taxation rules, or other
general accounting software responsibilities.

## 6. Finance Domain and Customer Account

### 6.1 Separate Finance Domain

PHASE 22 introduces a new Django application:

```text
shop_epower.finance
```

The domain responsibilities are separated as follows:

```text
accounts — customer identity, roles, profiles, and legal details
orders   — products requested and shipped to the customer
payments — payment attempts, providers, statuses, and invoices
finance  — customer funds, debt, immutable entries, and reversals
```

The finance application is not a separate microservice. It is an independent
business domain inside the existing Django project.

Payment, order, and profile models must not update financial balances directly.
They interact with the finance domain through explicit services.

No Django signals are used.

### 6.2 Customer Account Relationship

A user may own more than one financial account:

```text
User
 ├── PERSONAL CustomerAccount
 └── LEGAL CustomerAccount
          │
          └── LegalProfile
```

The current business rules and `LegalProfile` model allow:

- exactly one personal account for a registered customer;
- no more than one legal account for the same customer.

The relationship between `User` and `CustomerAccount` is therefore a foreign
key, not a one-to-one field.

Database constraints prevent two accounts of the same type from being created
for one user.

### 6.3 Account Types

The initial account types are:

```text
PERSONAL
LEGAL
```

`PERSONAL` is used when the customer purchases as an individual.

`LEGAL` is used when the customer purchases on behalf of a legal entity or an
individual entrepreneur represented by the customer's `LegalProfile`.

The account type is immutable after account creation.

### 6.4 Proposed CustomerAccount Fields

| Field | Purpose |
|---|---|
| `user` | Customer profile that owns the account |
| `account_type` | Personal or legal purchasing context |
| `legal_profile` | Legal identity used by a legal account |
| `currency` | Deployment base currency fixed for the account |
| `available_balance` | Current unused customer funds |
| `debt_balance` | Current recognized customer debt |
| `status` | Whether the account may be used for new business operations |
| `legal_tax_id_snapshot` | Legal identity identifier preserved by the account |
| `created_at` | Account creation time |
| `updated_at` | Last update time of the current account projection |

Money fields use decimal values with two fractional digits. Binary floating
point values are never used for financial amounts.

### 6.5 Personal Account Rules

A personal account:

- belongs to a user with the `CLIENT` role at creation time;
- has `account_type=PERSONAL`;
- has no related `LegalProfile`;
- has no legal tax identifier snapshot;
- starts with zero available funds;
- starts with zero debt;
- uses the current deployment base currency.

A personal account is created explicitly during successful customer
registration.

API registration and template registration call the same account creation
service. User and account creation must complete in one database transaction.

Existing clients receive personal accounts through an explicit data migration.
Staff and superusers are excluded from automatic migration.

### 6.6 Legal Account Rules

A legal account:

- belongs to the same user as its `LegalProfile`;
- has `account_type=LEGAL`;
- requires a related `LegalProfile`;
- requires `LegalProfile.is_legal_entity=True`;
- requires all business-mandatory legal details;
- stores the legal tax identifier as an identity snapshot;
- starts with zero available funds;
- starts with zero debt;
- uses the same deployment base currency as the personal account.

The existence of an empty `LegalProfile` does not create a legal financial
account.

The legal account is created explicitly when a valid legal profile is
activated. Profile saving and legal account creation must complete in one
database transaction.

Matching legal details owned by different users do not merge accounts.

### 6.7 Identity and Legal Profile Changes

A legal account represents one legal purchasing identity.

Ordinary updates such as a corrected company name, address, bank name, or bank
account do not create a new financial account.

Replacing the legal tax identifier after financial operations exist would
reinterpret the existing history as belonging to another legal identity.
This is not allowed.

A request to use another legal identity requires a separate future workflow.

The current `LegalProfile` model supports only one legal identity per user.
Therefore, multiple legal identities and multiple legal financial accounts for
one user are outside PHASE 22.

### 6.8 Account Statuses

The initial account statuses are:

- `ACTIVE`;
- `INACTIVE`.

An active account may be selected for new customer orders and ordinary
financial operations.

An inactive account is preserved for:

- financial history;
- reconciliation;
- existing debt settlement;
- required refunds;
- reversals and corrections.

Deactivation must not delete the account or its transactions.

Account status changes must be performed through an explicit service and
recorded in immutable status history.

### 6.9 Database Constraints

The `CustomerAccount` model should enforce the following database constraints:

- the combination of `user` and `account_type` must be unique;
- `available_balance` must not be negative;
- `debt_balance` must not be negative;
- a legal profile must not be connected to more than one financial account;
- a personal account must not reference a legal profile;
- a legal account must reference a legal profile;
- a personal account must not contain a legal tax identifier snapshot;
- a legal account must contain a legal tax identifier snapshot.

Some rules cannot be reliably expressed as a single-row database constraint
and must be enforced by services:

- the legal profile and financial account must belong to the same user;
- only an eligible customer may receive a customer account;
- account currency must equal the deployment base currency;
- account type must not change after account creation;
- legal identity replacement must follow the established identity rules.

Database constraints and service validation complement each other. Neither
layer replaces the other.

### 6.10 Account Lifecycle

The initial account lifecycle is:

```text
Customer registration
        │
        ▼
Create PERSONAL account
        │
        ▼
      ACTIVE
        │
        ├── ordinary financial operations
        │
        └── deactivation
                │
                ▼
             INACTIVE
                │
                ├── history and reconciliation
                ├── existing debt settlement
                ├── required refunds
                └── reversals and corrections
```

The legal account lifecycle begins separately:

```text
Create or update LegalProfile
        │
        ▼
Validate legal profile activation
        │
        ▼
Create LEGAL account
        │
        ▼
      ACTIVE
```

Personal and legal accounts have independent statuses. Deactivating one account
must not automatically deactivate the other.

Account creation and status changes are explicit service operations. They must
not be hidden in model `save()` methods, selectors, properties, or Django
signals.

## 7. Immutable Account Transactions

### 7.1 Purpose

`AccountTransaction` represents one immutable financial operation performed on
a `CustomerAccount`.

It must not be confused with a database transaction:

- `AccountTransaction` is a stored business record;
- `transaction.atomic()` is a technical database boundary used by services.

The transaction ledger is the historical source of truth. The balances stored
on `CustomerAccount` are the current projection of that history.

### 7.2 One Operation and Two Balance Components

A single financial operation may change:

- only the available balance;
- only the debt balance;
- both balances at the same time.

Examples:

| Operation | Available delta | Debt delta |
|---|---:|---:|
| Customer deposit | +500.00 | 0.00 |
| Shipment creates debt | 0.00 | +800.00 |
| Available funds are allocated to debt | -500.00 | -500.00 |
| Reversal | exact opposite | exact opposite |

The deltas are signed values. Positive values increase a balance and negative
values decrease it.

This is a customer financial subledger. It is not intended to replace
double-entry accounting software.

### 7.3 Transaction Types

The initial transaction types are:

- `DEPOSIT` — customer funds are added to the available balance;
- `DEBT_INCREASE` — a shipment creates customer debt;
- `ALLOCATION` — available customer funds are applied to existing debt;
- `REFUND` — funds are returned to the customer's available balance;
- `REVERSAL` — an earlier transaction is reversed.

The list may be extended in later phases, for example with withdrawal
operations.

A correction is not represented by editing the original transaction. The
original transaction is reversed and, when necessary, a new correct transaction
is created.

### 7.4 Proposed AccountTransaction Fields

The model should contain:

- `account` — the affected `CustomerAccount`;
- `operation_type` — the business type of the operation;
- `available_delta` — signed change of available funds;
- `debt_delta` — signed change of customer debt;
- `available_balance_after` — available balance after the operation;
- `debt_balance_after` — debt balance after the operation;
- `currency_snapshot` — the account currency at the time of the operation;
- `operation_key` — a unique idempotency key for the business command;
- `reversal_of` — the original transaction when this is a reversal;
- `comment` — an explanation or business reason;
- `actor_type` — customer, manager, administrator, or system;
- `created_by` — the authenticated user who initiated the operation, when
  applicable;
- `created_at` — creation timestamp.

Money fields must use `DecimalField`. Binary floating-point values must never
be used for financial amounts.

`created_by` may be empty for automatic system operations. When it contains a
user, deletion of that user must not destroy the financial audit trail.

### 7.5 Resulting Balance Snapshots

Every transaction stores the balances resulting from that operation.

For example:

```text
previous available balance + available_delta
    = available_balance_after

previous debt balance + debt_delta
    = debt_balance_after
```

These snapshots make transaction history easier to inspect and reconcile.

The ledger can still be reconstructed by summing transaction deltas. The
result must match the current balances stored on `CustomerAccount`.

### 7.6 Idempotency

Every retryable financial command must have a stable `operation_key`.

If the same command is received more than once, the finance service must find
the existing transaction and must not apply its balance changes again.

For example, repeated payment-provider callbacks must not credit the customer
balance multiple times.

The key must identify the original business operation. A new random key
generated for every retry does not provide idempotency.

Database uniqueness on `operation_key` provides the final protection against
concurrent duplicate requests.

### 7.7 Reversal Rules

A reversal:

- never modifies the original transaction;
- belongs to the same customer account;
- uses the same currency;
- contains the exact opposite deltas;
- references the original transaction through `reversal_of`;
- includes the reason for the correction;
- may be created only once for the original transaction.

A reversal transaction must not itself be reversed. If the original business
effect must be restored, a new explicit financial operation is created.

Dependent operations must be reversed in reverse order.

For example, if deposited funds were already allocated to debt, the allocation
must be reversed before the deposit can be reversed. Otherwise the available
balance could become negative.

### 7.8 Database and Service Constraints

The database should enforce constraints that can be checked inside one row:

- `available_balance_after` cannot be negative;
- `debt_balance_after` cannot be negative;
- both deltas cannot be zero at the same time;
- `operation_key` must be unique;
- only one reversal may reference an original transaction.

Rules involving other rows must be enforced by the finance service:

- transaction currency must match account currency;
- reversal deltas must be exact opposites;
- the original transaction must not already be reversed;
- a reversal cannot reference another reversal;
- operation type must correspond to the permitted delta directions;
- inactive accounts cannot receive ordinary new operations.

Inactive accounts may still accept operations required to settle existing debt,
perform reconciliation, or correct historical records.

### 7.9 Atomic Balance Update

Every balance-changing finance service must perform the following sequence:

```text
Business command
       │
       ▼
Start database transaction
       │
       ▼
Lock CustomerAccount row
       │
       ▼
Check operation key and business rules
       │
       ▼
Calculate new balances
       │
       ▼
Create immutable AccountTransaction
       │
       ▼
Update CustomerAccount projection
       │
       ▼
Commit database transaction
```

The account must be locked with `select_for_update()` inside
`transaction.atomic()`.

This prevents two concurrent requests from reading the same old balance and
overwriting each other's results.

The transaction record and the updated account balances must either both be
saved or both be rolled back.

### 7.10 Immutability Boundary

Application services must not provide update or delete operations for financial
transactions.

The Django admin interface for transactions must be read-only. It may allow
inspection and filtering, but not editing or deletion.

Application-level restrictions do not protect against direct database access.
Database permissions and operational procedures remain part of production
security.

### 7.11 References to Orders and Payments

The core ledger must not use a weak generic reference consisting only of a
model name and an arbitrary object identifier.

Later integration phases will introduce explicit records connecting financial
transactions with:

- deposits;
- payments;
- orders;
- shipments;
- settlements;
- refunds.

This preserves database relationships and keeps the financial core independent
from unfinished order-settlement workflows.

## 8. Finance Service Boundary

### 8.1 Purpose of the Service Layer

All financial state changes must be performed through explicit finance
services.

Views, API endpoints, admin actions, Celery tasks, payment services, and order
services must never modify account balances directly.

The allowed dependency direction is:

```text
View / API / Task / Integration
              │
              ▼
     Public finance service
              │
              ▼
 Internal transaction function
              │
        ┌─────┴─────┐
        ▼           ▼
CustomerAccount  AccountTransaction
```

Finance services receive domain objects and primitive values. They must not
receive Django `request` objects.

The finance domain must not use Django signals.

### 8.2 Public Account Lifecycle Services

The initial public lifecycle services should be:

```python
create_personal_customer_account(
    *,
    user,
)

create_legal_customer_account(
    *,
    legal_profile,
)

change_customer_account_status(
    *,
    account,
    new_status,
    reason,
    changed_by=None,
)
```

These names describe business actions rather than direct model operations.

#### Personal Account Creation

`create_personal_customer_account()` must:

- accept a registered customer;
- verify that the user is allowed to have a customer account;
- create an account with type `PERSONAL`;
- use the current project base currency;
- initialize both balances with zero;
- return the existing personal account when the same valid request is repeated.

The service must be idempotent because a repeated registration-related command
must not create a second personal account.

Both API and template registration flows must explicitly call the same account
creation service.

User creation and personal account creation must belong to one database
transaction:

```text
Start database transaction
        │
        ├── create User
        │
        ├── create PERSONAL CustomerAccount
        │
        ▼
Commit both objects
```

If account creation fails, user registration must also be rolled back.

No account is created through a model signal.

#### Legal Account Creation

`create_legal_customer_account()` must:

- accept a `LegalProfile`;
- verify that `is_legal_entity` is enabled;
- verify that all required legal details are complete;
- verify that the profile belongs to an eligible customer;
- create an account with type `LEGAL`;
- reference the legal profile;
- store the legal tax identifier snapshot;
- use the current project base currency;
- initialize both balances with zero;
- return the existing legal account when the same valid request is repeated.

The mere existence of a `LegalProfile` row is not sufficient. An empty profile
created while opening a profile page must not create a legal financial account.

A repeated request with a different legal identity must not silently reuse the
existing account.

### 8.3 Account Status Change Audit

Account status changes are operational events, not monetary transactions.

They must not be represented by an `AccountTransaction` with zero deltas.
Instead, PHASE 22 should introduce an immutable
`CustomerAccountStatusHistory` model.

The proposed fields are:

- `account`;
- `old_status`;
- `new_status`;
- `reason`;
- `changed_by`;
- `created_at`.

Changing an account status and creating its history record must happen inside
one database transaction.

The status history must not be edited or deleted through application services
or the Django admin interface.

An inactive account remains available for:

- history inspection;
- reconciliation;
- payment of existing debt;
- required refunds;
- reversals and corrections.

Its status prevents operations that create new ordinary business activity, such
as using the account for a new order.

Status permissions must be checked according to the operation type. The system
must not reject every operation merely because the account is inactive.

### 8.4 Public Monetary Services

The initial public monetary services should be:

```python
record_customer_deposit(
    *,
    account,
    amount,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
)

record_customer_debt(
    *,
    account,
    amount,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
)

allocate_customer_funds(
    *,
    account,
    amount,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
)

record_customer_refund(
    *,
    account,
    amount,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
)

reverse_customer_transaction(
    *,
    original_transaction,
    operation_key,
    actor_type,
    created_by=None,
    comment,
)
```

Every `amount` accepted by a public service must be greater than zero.

Callers must not pass signed amounts. The service determines the correct delta
directions from the selected business operation.

Examples:

```text
record_customer_deposit(500.00)
    available_delta = +500.00
    debt_delta = 0.00

record_customer_debt(800.00)
    available_delta = 0.00
    debt_delta = +800.00

allocate_customer_funds(500.00)
    available_delta = -500.00
    debt_delta = -500.00
```

This prevents callers from constructing arbitrary or contradictory balance
changes.

### 8.5 Private Transaction Application Function

The public services should use one private internal function:

```python
_apply_account_transaction(
    *,
    account,
    operation_type,
    available_delta,
    debt_delta,
    operation_key,
    actor_type,
    created_by=None,
    comment="",
    reversal_of=None,
)
```

The leading underscore indicates that this function is internal to the finance
domain.

It must not be imported by views, API modules, order services, payment
services, or other applications.

The private function is responsible for the shared technical sequence:

1. start `transaction.atomic()`;
2. reload and lock the account with `select_for_update()`;
3. process the idempotency key;
4. validate account status and currency;
5. calculate the resulting balances;
6. reject negative resulting balances;
7. create the immutable `AccountTransaction`;
8. update the `CustomerAccount` balance projection;
9. commit both changes.

The account received from the caller may contain stale balance values.
Therefore, the function must reload the account from the database after
acquiring the lock.

### 8.6 Allocation Rules

`allocate_customer_funds()` applies available funds to existing debt.

The requested amount must not exceed either:

- the current available balance;
- the current debt balance.

The service therefore validates:

```text
amount <= available_balance
amount <= debt_balance
```

A partial allocation is allowed.

Example:

```text
available balance: 500.00
debt balance:      800.00
allocation:        300.00

result:
available balance: 200.00
debt balance:      500.00
```

Automatic allocation policies belong to later integration phases. The PHASE 22
core service performs only the explicit amount requested by its caller.

### 8.7 Idempotent Service Behaviour

When an operation with the supplied `operation_key` already exists, the service
must compare the existing transaction with the requested operation.

If the account, operation type, amount, and other significant values match, the
service returns the existing transaction without changing balances again.

If the same key is reused for different operation data, the service must raise
a validation error.

```text
Same key + same operation
    → return existing transaction

Same key + different operation
    → validation error
```

The caller must provide a stable business key.

Generating a new random key inside the finance service for every call would not
protect against retries.

Database uniqueness remains necessary because two identical requests may
arrive concurrently before either request sees the other transaction.

### 8.8 Actor Rules

`actor_type` records the type of initiator at the time of the operation.

The initial actor types are:

- `CUSTOMER`;
- `MANAGER`;
- `ADMIN`;
- `SYSTEM`.

For human operations, `created_by` must contain the user who initiated the
action.

For automatic operations, `actor_type` is `SYSTEM` and `created_by` may be
empty.

The service must not derive historical actor information only from the user's
current role because that role may change later.

A payment-provider callback is treated as a system operation. Provider-specific
identifiers will be connected through explicit integration models in later
phases.

### 8.9 Reversal Service

`reverse_customer_transaction()` is the only public service allowed to create
a `REVERSAL` transaction.

It must:

- lock the affected account;
- lock or safely validate the original transaction;
- verify that the original transaction has not already been reversed;
- reject an attempt to reverse another reversal;
- use the exact opposite deltas;
- use the same account and currency;
- require a non-empty comment;
- ensure that resulting balances remain non-negative;
- create the reversal and update the account atomically.

The caller does not provide reversal deltas. They are calculated exclusively
from the original transaction.

### 8.10 Read Operations and Selectors

Read operations belong to selectors rather than balance-changing services.

The initial selectors should include:

```python
get_customer_accounts(
    *,
    user,
)

get_personal_customer_account(
    *,
    user,
)

get_legal_customer_account(
    *,
    user,
)

get_account_transactions(
    *,
    account,
)

get_account_transaction_by_operation_key(
    *,
    operation_key,
)
```

Selectors must not create accounts, repair balances, or perform other hidden
writes.

A missing account must be handled explicitly by the caller. Read operations
must not use `get_or_create()`.

### 8.11 Integration Services

Other domains must call public finance services rather than modifying finance
models.

Future integrations will follow this direction:

```text
Registration service
    └── create_personal_customer_account()

Legal profile activation service
    └── create_legal_customer_account()

Shipment service
    └── record_customer_debt()

Payment confirmation service
    └── record_customer_deposit()

Settlement service
    └── allocate_customer_funds()

Refund service
    └── record_customer_refund()
```

A higher-level workflow may combine several financial operations inside one
outer database transaction.

For example, payment confirmation may record a deposit and then allocate some
or all of the received funds to existing debt. These remain separate immutable
ledger entries even when they are committed as one business workflow.

### 8.12 Error Handling

Finance services should raise domain validation errors, using Django
`ValidationError` during the initial implementation.

Views are responsible for converting these errors into:

- form errors;
- user messages;
- appropriate REST API responses.

Finance services must not return HTTP responses and must not depend on Django
REST Framework exceptions.

### 8.13 Testing Responsibilities

Service tests must verify:

- successful account creation;
- repeated account creation is idempotent;
- legal account validation;
- account locking and atomic balance updates;
- every operation type and its delta directions;
- prevention of negative balances;
- allocation limits;
- transaction creation and resulting balance snapshots;
- repeated operation keys;
- conflicting reuse of an operation key;
- successful reversal;
- prevention of duplicate reversal;
- reversal ordering constraints;
- rollback when transaction creation or account update fails;
- inactive account rules;
- creation of account status history;
- absence of signal-based account creation.

## 9. Project Structure and Implementation Plan

### 9.1 New Finance Application

PHASE 22 introduces a separate Django application:

```text
src/shop_epower/finance/
├── __init__.py
├── apps.py
├── admin.py
├── migrations/
│   └── __init__.py
├── models/
│   ├── __init__.py
│   ├── customer_account.py
│   ├── account_transaction.py
│   └── customer_account_status_history.py
├── selectors/
│   ├── __init__.py
│   ├── accounts.py
│   └── transactions.py
├── services/
│   ├── __init__.py
│   ├── accounts.py
│   └── transactions.py
└── tests/
    ├── __init__.py
    ├── helpers.py
    ├── test_customer_account_models.py
    ├── test_account_transaction_models.py
    ├── test_account_status_history_models.py
    ├── test_account_services.py
    ├── test_transaction_services.py
    ├── test_selectors.py
    └── test_admin.py
```

No `signals.py` module should be created.

The initial financial core does not require customer-facing views, URL routes,
forms, templates, or API endpoints. These interfaces will be added only when a
business workflow needs them.

### 9.2 File Responsibilities

#### Models

The `models` package contains persistence structures and database-level
constraints.

It must not contain:

- registration orchestration;
- payment confirmation workflows;
- shipment processing;
- automatic account creation;
- hidden balance changes in overridden `save()` methods.

#### Services

The `services` package contains explicit state-changing business operations.

Only services may:

- create customer accounts;
- change account status;
- create account transactions;
- update balance projections;
- create reversals.

#### Selectors

The `selectors` package contains read-only queries.

Selectors must not:

- create missing accounts;
- repair balances;
- create history records;
- change account status;
- perform settlement.

#### Admin

The Django admin interface provides operational inspection.

Financial transactions and status history must be read-only. Account balances
must not be editable directly through admin forms.

#### Tests

Finance test helpers may create the initial objects required by a test, but
they must not bypass the public finance services when a test is verifying
business behaviour.

Direct model creation is acceptable in isolated model tests where the purpose
is to verify fields or database constraints.

### 9.3 Model Relationship Overview

```text
User
 │
 ├── PERSONAL CustomerAccount
 │          │
 │          ├── AccountTransaction
 │          └── CustomerAccountStatusHistory
 │
 └── LegalProfile
            │
            └── LEGAL CustomerAccount
                       │
                       ├── AccountTransaction
                       └── CustomerAccountStatusHistory
```

The relationship from `User` to `CustomerAccount` is a foreign-key
relationship with a uniqueness constraint on:

```text
(user, account_type)
```

This allows one personal and one legal account for the same user while
preventing duplicate accounts of either type.

### 9.4 Deletion Policies

Financial records must use protective deletion policies.

The intended rules are:

- a user with a financial account cannot be physically deleted;
- a legal profile connected to a legal account cannot be physically deleted;
- an account with transaction history cannot be physically deleted;
- a transaction referenced by a reversal cannot be deleted;
- a human actor referenced by financial history must remain identifiable.

Application workflows should deactivate customer accounts and users instead of
deleting them.

Foreign keys from financial records should normally use `PROTECT`.

Nullable `created_by` fields remain available for automatic system operations,
but a referenced human actor must not silently disappear from the audit trail.

### 9.5 Money Precision

Financial account and transaction amounts should use:

```python
max_digits=18
decimal_places=2
```

Existing order and payment models use smaller limits, but a customer account
may accumulate values from many orders and payments.

Using greater precision for the financial core reduces the risk of reaching the
database limit as transaction history grows.

The supported deployment currencies currently use two decimal places. A future
requirement for currencies with different minor-unit rules would require a
separate design decision.

### 9.6 Migration Strategy

The finance application requires at least two migrations.

#### Schema Migration

The first migration creates:

- `CustomerAccount`;
- `AccountTransaction`;
- `CustomerAccountStatusHistory`;
- indexes;
- uniqueness constraints;
- non-negative balance constraints;
- personal and legal account consistency constraints.

This migration must not create accounts for existing users.

#### Existing Customer Data Migration

A separate data migration creates accounts for existing eligible customers.

For every existing customer:

- create one personal account;
- use the configured base currency;
- initialize available balance with zero;
- initialize debt balance with zero;
- set the account to `ACTIVE` when the user is active;
- otherwise set it to `INACTIVE`.

Managers, administrators, staff users, and superusers must not receive
customer accounts automatically.

For an existing legal profile, create a legal account only when:

- the related user is an eligible customer;
- `is_legal_entity` is enabled;
- company name is present;
- tax identifier is present;
- legal address is present.

Incomplete legal profiles must be skipped rather than converted into partially
valid financial accounts.

The data migration must use Django historical migration models. It must not
import the current finance services or current application model classes.

Running the migration logic against the same data more than once must not
create duplicate accounts.

The reverse data migration should not silently delete financial accounts. A
no-operation reverse function is safer than automatic deletion of potentially
used financial records.

### 9.7 Required Database Indexes

The initial schema should provide indexes for frequent financial queries:

- transactions by account and creation order;
- transactions by operation type;
- transactions by actor type;
- account status history by account and creation order;
- accounts by user and status.

`operation_key` already receives a unique database index through its uniqueness
constraint.

Indexes should support actual selectors and audit queries. Additional indexes
must not be added without a concrete query requirement.

### 9.8 Implementation Sprints

PHASE 22 should be implemented through small logical sprints.

#### Mandatory TDD Cycle

Every implementation sprint must follow the project's TDD workflow.

The sprint lists below describe scope, not the chronological order in which
production code and tests are written.

For every new behaviour:

1. define one observable business rule;
2. write the focused automated test first;
3. run the focused test and confirm that it fails for the expected reason;
4. implement only the minimum production code required by that test;
5. run the focused test again and confirm that it passes;
6. refactor the implementation while keeping the test green;
7. run the related domain test suite;
8. continue with the next behaviour.

The initial failing state is the `RED` stage. The minimum passing
implementation is the `GREEN` stage. Cleanup performed while preserving the
passing behaviour is the `REFACTOR` stage.

Before every sprint commit:

- run all tests directly related to the changed domain;
- run tests for integrated domains affected by the change;
- run the complete project test suite;
- run Ruff;
- run Django system checks;
- run `git diff --check`;
- inspect the complete staged diff.

A sprint is committed only when all required checks pass. The temporary RED
state remains local and is not committed as the completed sprint.

Database migrations are also developed under this process. Model behaviour and
constraints are first expressed by tests, migrations are generated and
inspected, and the tests must pass against the migrated test database.

If implementation reveals that an approved requirement is incorrect or
incomplete, development stops and the architecture document is updated before
the implementation continues.

#### Sprint 1 — Architecture Documentation

- finish the PHASE 22 requirements;
- confirm model responsibilities;
- confirm service contracts;
- confirm migration and integration strategy;
- review the document for contradictions.

Expected result: documentation-only commit.

#### Sprint 2 — Finance Application and Models

- create the `finance` application;
- register it in Django settings;
- implement model enums;
- implement `CustomerAccount`;
- implement `AccountTransaction`;
- implement `CustomerAccountStatusHistory`;
- add database constraints and indexes;
- create the initial schema migration;
- add model and constraint tests.

Expected result: the finance schema exists, but it is not yet connected to
registration, orders, payments, or shipments.

#### Sprint 3 — Account Lifecycle Services

- implement personal account creation;
- implement legal account creation;
- implement account activation and deactivation;
- implement immutable status history;
- add selectors for customer accounts;
- add service and selector tests.

Expected result: accounts can be managed only through explicit services.

#### Sprint 4 — Immutable Transaction Services

- implement the private atomic transaction function;
- implement account row locking;
- implement deposits;
- implement debt increases;
- implement allocations;
- implement refunds;
- implement reversals;
- implement idempotency checks;
- add rollback and service tests.

Expected result: the financial core can safely change balances and preserve an
immutable audit history.

#### Sprint 5 — Registration Integration

- introduce or update the shared customer registration service;
- wrap user and personal account creation in one database transaction;
- connect API registration to the shared service;
- connect template registration to the same service;
- verify that both flows create exactly one personal account;
- verify rollback when account creation fails.

Expected result: every newly registered customer receives one personal account
without using signals.

#### Sprint 6 — Legal Profile Integration

- centralize legal profile activation and update logic;
- call legal account creation explicitly after valid activation;
- ensure empty profiles do not create accounts;
- prevent silent legal identity replacement after financial activity exists;
- cover API and template profile workflows with tests.

Expected result: a valid legal profile produces one separate legal account.

#### Sprint 7 — Existing Customer Migration

- add the forward data migration;
- create personal accounts for existing customers;
- create legal accounts for complete existing legal profiles;
- skip ineligible users and incomplete profiles;
- test migration behaviour and duplicate protection.

Expected result: existing customer data conforms to the new account rules.

#### Sprint 8 — Read-Only Administration

- register finance models in Django admin;
- make transactions read-only;
- make status history read-only;
- prevent direct balance editing;
- add useful filters and search fields;
- add admin permission tests.

Expected result: finance data can be inspected without bypassing services.

#### Sprint 9 — Regression and Documentation

- run finance tests;
- run accounts tests;
- run the complete project test suite;
- run Ruff;
- run Django system checks;
- update current architecture documentation;
- update the roadmap;
- record postponed PHASE 23 integration work.

Expected result: PHASE 22 is complete and PHASE 23 may begin.

### 9.9 Testing Database Requirements

Ordinary model and service tests may use Django `TestCase`.

Tests that verify real concurrent account updates require
`TransactionTestCase`, separate database connections, and PostgreSQL.

A normal `TestCase` wraps every test in an outer transaction and may hide the
real behaviour of `select_for_update()`.

Concurrency tests must verify that:

- two operations cannot overwrite each other's balances;
- duplicate operation keys cannot create duplicate balance effects;
- every committed transaction has the correct resulting balance snapshot.

SQLite must not be treated as sufficient proof of PostgreSQL row-locking
behaviour.

### 9.10 Integration Boundary for PHASE 22

PHASE 22 creates the financial core and connects account creation to customer
registration and legal profile activation.

It does not yet:

- create debt from order shipment;
- allocate payments to orders;
- support partial payments;
- support deposits through a real provider;
- process withdrawals;
- process order refunds;
- replace the current `Payment` workflow;
- change invoice generation;
- redesign order statuses;
- implement partial shipment models.

Those integrations belong to later phases, primarily PHASE 23.

The PHASE 22 implementation must provide stable services that those later
workflows can call without redesigning the financial foundation.

## 10. Definition of Done, Risks, and Deferred Decisions

### 10.1 PHASE 22 Definition of Done

PHASE 22 is complete when all of the following conditions are satisfied.

#### Financial Models

- the `finance` Django application exists;
- `CustomerAccount` is implemented;
- `AccountTransaction` is implemented;
- `CustomerAccountStatusHistory` is implemented;
- database constraints and indexes are applied;
- financial money fields use exact decimal values;
- personal and legal balances remain independent;
- one user cannot have duplicate accounts of the same type.

#### Account Lifecycle

- a personal account is created explicitly during customer registration;
- API and template registration use the same business service;
- user and account creation are atomic;
- no Django signals are used;
- valid legal profile activation explicitly creates a legal account;
- opening an empty legal profile does not create a legal account;
- accounts are deactivated instead of deleted;
- account status changes have immutable audit history.

#### Financial Operations

- balances can be changed only through public finance services;
- every balance change creates an immutable ledger transaction;
- current account balances and ledger history remain consistent;
- account rows are locked during balance updates;
- transaction creation and balance projection updates are atomic;
- resulting available and debt balances cannot be negative;
- available funds and debt remain separate values;
- repeated operation keys do not apply an operation twice;
- conflicting reuse of an operation key is rejected;
- corrections are performed through reversals;
- original financial transactions cannot be edited or deleted.

#### Existing Customers

- existing eligible customers receive personal accounts through a data
  migration;
- complete existing legal profiles receive separate legal accounts;
- incomplete legal profiles are skipped;
- staff users and superusers do not receive customer accounts automatically;
- repeated migration logic cannot create duplicate accounts.

#### Administration and Security

- finance transactions are read-only in Django admin;
- account status history is read-only in Django admin;
- account balances cannot be manually edited in Django admin;
- human actors remain identifiable in financial history;
- inactive accounts remain available for audit and required corrective
  operations.

#### Verification

- finance model tests pass;
- finance service tests pass;
- account registration tests pass;
- legal profile integration tests pass;
- migration tests pass;
- admin permission tests pass;
- PostgreSQL concurrency tests pass;
- the complete project test suite passes;
- Ruff checks pass;
- Django system checks pass;
- architecture and roadmap documentation are updated.

### 10.2 Main Implementation Risks

#### Concurrent Balance Updates

Two requests may try to change the same account simultaneously.

Mitigation:

- `transaction.atomic()`;
- `select_for_update()`;
- database constraints;
- PostgreSQL concurrency tests.

#### Duplicate External or Internal Commands

The same payment callback, task, or manager action may be processed more than
once.

Mitigation:

- stable `operation_key`;
- database uniqueness;
- comparison with the existing operation;
- idempotent service behaviour.

#### Ledger and Projection Divergence

An account balance may become inconsistent with its transaction history if one
part is saved without the other.

Mitigation:

- create the transaction and update the account inside one database
  transaction;
- prohibit direct balance updates;
- provide reconciliation checks;
- test rollback behaviour.

#### Stale Model Instances

A caller may pass an account object containing an outdated balance.

Mitigation:

- identify the account by primary key;
- reload it inside the atomic block;
- acquire a row lock before reading balances;
- never calculate from balance values supplied by the caller.

#### Empty Legal Profiles

The current application may create an empty `LegalProfile` when a customer
opens a profile page.

Mitigation:

- never use profile row existence as an activation condition;
- require `is_legal_entity`;
- validate required legal details;
- create the legal account only through an explicit service.

#### Legal Identity Replacement

Changing the tax identifier could make one financial account represent two
different legal identities.

Mitigation:

- preserve the original tax identifier snapshot;
- allow ordinary contact and bank-detail updates;
- reject tax identifier replacement after financial history exists;
- postpone multiple legal identities per user to a future phase.

#### Direct Administrative Changes

Manual editing in Django admin could bypass service rules and destroy
reconciliation.

Mitigation:

- make balances read-only;
- make ledger transactions read-only;
- make status history read-only;
- perform operational changes through explicit admin actions that call
  services.

#### Incorrect Migration of Existing Users

A data migration could create accounts for managers, administrators, or
incomplete legal profiles.

Mitigation:

- use explicit eligibility rules;
- separate schema and data migrations;
- test every included and excluded user category;
- preserve zero initial balances;
- prevent duplicate accounts with database constraints.

### 10.3 Explicitly Deferred Decisions

The following decisions are important but are not part of PHASE 22.

#### Order and Shipment Integration

PHASE 23 or a dedicated order workflow phase must define:

- the shipment model;
- partial shipment quantities;
- creation of debt for only the shipped portion;
- immutability of shipped order-item quantities and prices;
- editing rules for the unshipped order remainder;
- reversal of debt after shipment cancellation or return.

#### Payment Allocation

PHASE 23 must define:

- deposits not connected to a specific order;
- advance payments;
- partial payments;
- mixed payment methods;
- allocation of customer funds to one or more orders;
- allocation priority;
- release or reversal of allocations;
- payment of debt on inactive accounts.

#### Payment Model Evolution

The current `Payment` model has a one-to-one relationship with `Order`.

Later phases must decide how to support:

- multiple payment attempts;
- partial payments;
- combined payments;
- replaced or expired payment attempts;
- provider reconciliation.

The existing relationship is not changed during PHASE 22.

#### Invoice Revisions

Later work must define:

- invoice item snapshots;
- invoice revisions after order editing;
- cancellation and replacement of invoices;
- consistency between invoice totals and order items;
- partial shipment invoices.

#### Returns and Withdrawals

Later phases must define:

- refunds to available customer funds;
- refunds to an external payment method;
- withdrawal requests;
- balance reservation during withdrawal approval;
- reversal of withdrawals;
- return-related debt corrections.

#### Multiple Legal Identities

PHASE 22 supports one personal and one legal financial account per user because
the current `LegalProfile` relationship is one-to-one.

Support for several legal organizations owned by one user requires a separate
redesign of legal profiles and account ownership.

#### Shared Organization Accounts

Several users sharing one organization balance are outside the current
business requirements.

If this becomes necessary, the system will require:

- an organization entity independent from `User`;
- organization membership;
- employee permissions;
- shared account authorization;
- organization-level audit rules.

#### Multiple Customer Currencies

Every deployment has one base customer currency.

Supplier currencies may differ, but customer account balances are not split by
currency during PHASE 22.

Changing the deployment base currency must never reinterpret existing financial
history.

#### Real Payment Provider Security

Before integration with a real payment provider, the system must address:

- callback authentication;
- callback signatures;
- POST-only state-changing endpoints;
- replay protection;
- provider event idempotency;
- secure transaction identifiers;
- provider reconciliation.

#### Full Accounting

The finance domain is a customer settlement subledger.

It does not implement:

- double-entry bookkeeping;
- tax accounting;
- statutory accounting reports;
- a general ledger;
- replacement of external accounting software.

### 10.4 Final Architectural Invariants

The following rules must remain true throughout implementation:

1. A customer has one personal account and may have one separate legal account.
2. Personal and legal funds are never mixed.
3. Every account uses the deployment base currency.
4. Available funds and customer debt are separate non-negative values.
5. Debt is created from shipment, not merely from order creation.
6. Partial shipment creates debt only for the shipped portion.
7. Financial history is immutable.
8. Corrections use explicit reversal operations.
9. Current balances are updated only together with ledger transactions.
10. Concurrent operations lock the customer account.
11. Retryable operations use stable idempotency keys.
12. Accounts and financial history are deactivated or preserved, not deleted.
13. Registration and legal profile workflows call finance services explicitly.
14. Django signals are not used.
15. The financial domain supports trade workflows but does not replace
    accounting software.