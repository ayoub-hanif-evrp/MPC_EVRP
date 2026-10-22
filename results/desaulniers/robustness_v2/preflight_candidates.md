# Prospective robustness candidate eligibility

Checked only unused instance identity, published SF/MF physical replay, and reference-derived eligibility for target DoD 0.75. No optimizer results were inspected. The original robustness-v2 protocol remains preserved because all of its selected instances were ineligible at DoD 0.75.

| Family | Size | Instance | Eligible requests | Required at DoD 0.75 | Status |
| --- | ---: | --- | ---: | ---: | --- |
| C1 | 100 | c102_21_100 | 69 | 75 | ineligible |
| C1 | 100 | c103_21_100 | none | not tested | no SF/MF route |
| C1 | 100 | c104_21_100 | none | not tested | no SF/MF route |
| C1 | 100 | c105_21_100 | 91 | 75 | eligible |
| C1 | 100 | c106_21_100 | 90 | 75 | eligible |
| C1 | 100 | c107_21_100 | 90 | 75 | eligible |
| C1 | 100 | c108_21_100 | 89 | 75 | eligible |
| C2 | 50 | c202_21_50 | 36 | 38 | ineligible |
| C2 | 50 | c203_21_50 | 21 | 38 | ineligible |
| C2 | 50 | c204_21_50 | 11 | 38 | ineligible |
| C2 | 50 | c205_21_50 | 46 | 38 | eligible |
| C2 | 50 | c206_21_50 | 46 | 38 | eligible |
| C2 | 50 | c207_21_50 | 46 | 38 | eligible |
| R1 | 100 | r102_21_100 | 67 | 75 | ineligible |
| R1 | 100 | r103_21_100 | none | not tested | no SF/MF route |
| R1 | 100 | r104_21_100 | none | not tested | no SF/MF route |
| R1 | 100 | r105_21_100 | 90 | 75 | eligible |
| R1 | 100 | r106_21_100 | 69 | 75 | ineligible |
| R1 | 100 | r107_21_100 | 45 | 75 | ineligible |
| R1 | 100 | r108_21_100 | none | not tested | no SF/MF route |
| R1 | 100 | r109_21_100 | none | not tested | no SF/MF route |
| R1 | 100 | r110_21_100 | none | not tested | no SF/MF route |
| R1 | 100 | r111_21_100 | none | not tested | no SF/MF route |
| R2 | 50 | r202_21_50 | 31 | 38 | ineligible |
| R2 | 50 | r203_21_50 | 19 | 38 | ineligible |
| R2 | 50 | r204_21_50 | none | not tested | no SF/MF route |
| R2 | 50 | r205_21_50 | 45 | 38 | eligible |
| R2 | 50 | r206_21_50 | none | not tested | no SF/MF route |
| R2 | 50 | r207_21_50 | none | not tested | no SF/MF route |
| R2 | 50 | r208_21_50 | none | not tested | no SF/MF route |
| R2 | 50 | r209_21_50 | none | not tested | no SF/MF route |
| R2 | 50 | r210_21_50 | none | not tested | no SF/MF route |
| RC1 | 25 | rc102_21_25 | 17 | 19 | ineligible |
| RC1 | 25 | rc103_21_25 | 10 | 19 | ineligible |
| RC1 | 25 | rc104_21_25 | 4 | 19 | ineligible |
| RC1 | 25 | rc105_21_25 | 22 | 19 | eligible |
| RC1 | 25 | rc106_21_25 | 20 | 19 | eligible |
| RC1 | 25 | rc107_21_25 | 21 | 19 | eligible |
| RC2 | 25 | rc202_21_25 | 17 | 19 | ineligible |
| RC2 | 25 | rc203_21_25 | 9 | 19 | ineligible |
| RC2 | 25 | rc204_21_25 | 8 | 19 | ineligible |
| RC2 | 25 | rc205_21_25 | 20 | 19 | eligible |
| RC2 | 25 | rc206_21_25 | 21 | 19 | eligible |
| RC2 | 25 | rc207_21_25 | 22 | 19 | eligible |

Lexicographically first eligible unused candidate per family-size slot, without optimizer outcomes:

- C1 (100): c105_21_100
- C2 (50): c205_21_50
- R1 (100): r105_21_100
- R2 (50): r205_21_50
- RC1 (25): rc105_21_25
- RC2 (25): rc205_21_25
