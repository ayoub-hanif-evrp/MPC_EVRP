# CPU backend decision and archived hybrid experiment

The complete hybrid acceleration experiment is preserved at the annotated Git
tag [`archive/hybrid-gpu-negative-v1`](https://github.com/ayoub-hanif-evrp/MPC_EVRP/tree/archive/hybrid-gpu-negative-v1),
which resolves to commit `cff13c21fa0947cbc988d80802a8a8b7301a74b7`.
That tag contains the original source, protocol, 53 raw worker records, manifests,
hashes, reports, and the recorded setup/reporting corrections. It was verified on
the remote before the active-tree cleanup.

The RTX A2000 was slower than compiled CPU on the actual insertion batches once
host/device transfer and synchronization were included. The completed development
study independently replayed 50 full scenarios from 25 matched pairs under the
five-second MPC limit. Compiled CPU screening improved aggregate pilot time but
lost one served customer for HGS and one for ACS on the 100-customer case. The
optional operational-quality/service-recovery policy produced no service gain
and lost one HGS customer on a 50-customer case. Neither policy was promoted.

The active repository therefore has no GPU execution or GPU-only launcher. The
Numba insertion screen remains an optional CPU-only implementation with an
original-Python fallback. The optional quality policy remains available for
controlled research, not as the publication default. Historical results belong
to the archived tag; they are not reinterpreted as independent paper evidence.
