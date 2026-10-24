# Exact frozen reference and scenario inputs

Archived 42 reference schedules and 198 dynamic scenarios
used by the completed original and enhancement studies. Files were copied
byte-for-byte from the executed caches and independently loaded and replayed.
The manifest binds dataset hashes, canonical IDs, byte hashes, original
cache paths and experiment-manifest content IDs. No optimization was run.

Eight additional historical cache filenames identify the same canonical
reference schedules. Restoration includes these aliases. The initial metadata
and failed fresh-cache regression report are preserved; the corrected
regression loads all 198 scenarios with every regeneration call forbidden.
Only cache-path metadata changed, not reference contents or scientific data.

On a fresh checkout run `python -m scripts.archive_frozen_inputs --restore`
before auditing historical experiments. Restoration never overwrites a
conflicting cache or silently regenerates references. An alternate empty
cache can be tested using `--cache-root results/.input_restore_smoke`.
