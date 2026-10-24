# Methodological references consulted

- [Desaulniers et al. (2016)](https://doi.org/10.1287/opre.2016.1535)
  defines the static benchmark and charging variants used as the physical source.
- [Keskin and Catay (2016), author manuscript](https://research.sabanciuniv.edu/26033/1/WP_EVRPTW-Partial_Recharge_KeskinCatay.pdf)
  studies partial charging with ALNS. Its charging-aware repair ideas motivate
  feasibility probes; its reported gains are not evidence for this implementation.
- [Ropke and Pisinger (2006)](https://doi.org/10.1287/trsc.1050.0135)
  provides the adaptive removal/insertion framework underlying ALNS.
- [Bent and Van Hentenryck (2007)](https://www.ijcai.org/Abstract/07/293)
  studies waiting and relocation with online stochastic requests. The repository's
  bounded depot-wait policies do not reproduce that stochastic algorithm.
- [Wang, Sun and Huang (2024)](https://www.sciencedirect.com/science/article/pii/S0360835224002432)
  motivates time-window compatibility and efficient insertion in dynamic routing.
  Its multi-depot model is different from the fixed physical benchmark here.
- [Erdelic et al. (2026)](https://doi.org/10.1016/j.cie.2025.111758)
  combines ALNS with charging-station placement and caching in a time-dependent
  setting. Its travel and charging assumptions are not imported into this study.

These works guide mechanisms to investigate; they do not imply that any tested
repository enhancement is beneficial. All empirical claims in this package
come from the recorded, audited experiments.
