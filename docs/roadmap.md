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

PHASES 1--19 established the project foundation: - modular Django
architecture; - catalog and inventory; - order lifecycle; - payment and
invoice workflow; - chat; - Docker; - GitHub Actions CI; - engineering
documentation.

------------------------------------------------------------------------

# Current Phase

## PHASE 20 --- Dependency Management Modernization

-   Poetry migration
-   pyproject.toml
-   poetry.lock
-   dependency cleanup
-   Docker update
-   CI update
-   documentation update
-   regression testing

------------------------------------------------------------------------

# Future Roadmap

## PHASE 21 --- Test Infrastructure Refactoring

-   unified helpers
-   reusable fixtures
-   reusable assertions
-   API helpers
-   remove duplicated helpers
-   standardized test structure

## PHASE 22 --- Customer Financial Core

-   Customer Account
-   Financial Ledger
-   Account Transactions
-   immutable balance history
-   audit trail
-   atomic financial operations

## PHASE 23 --- Deposits & Order Settlement

-   deposits
-   advance payments
-   partial payments
-   mixed payments
-   order payment allocation
-   refund to customer balance

## PHASE 24 --- Returns & Reverse Logistics

-   return requests
-   warehouse inspection
-   stock recovery
-   write-off workflow
-   exchange workflow
-   refund processing

## PHASE 25 --- Withdrawals & Financial Operations

-   withdrawal requests
-   balance reservation
-   approval workflow
-   reconciliation

## PHASE 26 --- Developer Environment

## PHASE 27 --- Git Professional

## PHASE 28 --- Production Deployment

## PHASE 29 --- CI/CD & Release Automation

## PHASE 30 --- Performance & Redis Cache

## PHASE 31 --- WebSockets & Real-Time Features

## PHASE 32 --- Invoice Revisions

## PHASE 33 --- 1C & Supplier Integrations

## PHASE 34 --- Internationalization

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
-   Observability & Monitoring
-   Business Analytics
-   Loyalty Program
-   Marketplace Features
