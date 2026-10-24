# Service-loss evidence and failed enhancements

The first-visible development ALNS probe examined 33 missed customers: 18 had
no ready EV, six were selected in a soft plan, one had a validated top-three
insertion, and eight had no bounded insertion witness. Full decision timelines
record 11 later losses of soft-plan ownership. These observations do not prove
the preceding action caused eventual service loss.

Three instrumented development runs recorded complete root states, executing
actions, retained and discarded suffixes, insertion-screen results, decoding
outcomes, fully scored candidates and selected fleet routes. Over two million
events were captured without truncation. No recorded fully scored ALNS
candidate dominated the selected objective at these roots.

Five missed-customer plan drops occurred during optimization; four exchanged
one planned customer for another at equal immediate coverage. Two-second
original-decoder insertion/ejection probes, selective charge-amount LP probes
along existing station orders, and five-second small-route reordering probes
found no additional service-preserving witness at those five final roots.
Failure under these bounded neighborhoods is not a global infeasibility proof.

The bounded reserve pilot regressed ALNS by four customers over its three
selected cases. Stable V3's initial pilot gained one customer on one
100-customer case and lost one on another. The broader screen determines its
acceptance. These failures support reporting a limit of the tested mechanisms,
not claiming that every missed customer is physically impossible online.

A separate synthetic reproducer confirmed optimizer-initialization timeout
crashes in ALNS, HGS and ACS. Runtime corrections and their tests are documented
with the source changes; they are reliability fixes, not evidence of improved
customer service in the completed historical campaigns.
