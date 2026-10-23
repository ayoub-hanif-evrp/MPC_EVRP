# Published SP/MP route-order audit

This is a separate read-only diagnostic for instances lacking SF/MF full-charge references. The published SP/MP files give node orders but not a charging-amount trace. A continuous-charge LP witness is sought, then every action is replayed through the common MP transition engine. A successful witness shows feasibility of that order under our model; it does not reproduce the paper's charging choices or replace the frozen `K_ref` construction used in final or robustness studies.

Published partial-route files inspected: 19; complete MP route-order witnesses: 19. All failures and details are in `partial_published_audit.csv`.
