# Interview: Head of Operations, Aurora Foods

**Date:** 2026-07-15
**Interviewer:** EA team
**Participant:** Head of Operations
**Scope:** order-to-delivery flow, systems in daily use

---

**Q: Who are your customers and how do they place orders?**

Our customers are wholesalers and retail chains, never consumers directly. B2B customers
place orders through the online order portal, and a handful of the largest accounts still
send spreadsheets by e-mail that our service desk keys in manually.

**Q: Walk me through what happens after an order arrives.**

The order fulfilment process starts the moment an order lands in the portal. We check
stock, confirm the delivery window with the customer, then release the order to the
warehouse for picking. The purchase order document itself is what auditors ask for, so we
keep it for seven years.

**Q: Which systems are involved?**

Three matter. The order portal is where customers see prices and place orders. The ERP core
holds the master order records and does the invoicing. The warehouse management system runs
picking and dispatch on the floor.

The order portal does not hold stock levels itself; it calls an order API that the ERP
publishes. When that API is down, customers cannot order at all, which is our single worst
outage scenario.

**Q: What about the warehouse side?**

The warehouse management system supports the order fulfilment process directly. Pickers work
from its screens. It receives released orders from the ERP every few minutes.

**Q: Anything you would call a capability gap?**

Customer service is the weak spot. We can take an order and we can ship it, but answering
"where is my order" still means someone opening three systems.
