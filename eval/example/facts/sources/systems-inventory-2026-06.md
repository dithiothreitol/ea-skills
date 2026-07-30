# Systems inventory extract, June 2026

Source: IT asset register export, reconciled with the infrastructure team on 2026-06-30.

| System | Role | Owner | Hosting |
|---|---|---|---|
| Order Portal | Customer-facing ordering web application | e-commerce team | Managed cloud |
| ERP Core | Order master data, invoicing, finance | finance systems team | On-premise |
| Warehouse Management System | Picking, packing and dispatch | logistics IT | On-premise |

## Notes from the infrastructure team

The ERP core runs on a dedicated application server in the primary data centre. That server
also hosts the PostgreSQL 16 database instance that the ERP depends on; the database is not
shared with any other system.

The order API is published by the ERP core and consumed by the order portal. It is the only
integration point between the two systems.

Order records are stored in the ERP database and represent the purchase orders that the
business works with. Retention is seven years for audit purposes.

Deployment of the warehouse management system is planned to move to the cloud, but no date
has been agreed and no budget has been approved.
