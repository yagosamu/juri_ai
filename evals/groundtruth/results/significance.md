# Retrieval significance

Pre-registered analysis for the retrieval comparison. The five pairs (in the order below), the metrics, the views, the seed, the resample and permutation counts and the multiplicity correction are this module's own constants; they were fixed before it first ran and were not changed after seeing any result. The commit history of `evals/groundtruth/significance.py` is the public record of when they were set.

Seed: 20260917. Bootstrap resamples: 10000. Sign-flip permutations: 10000. Alpha: 0.05.

## Intervals, full (n=59)

| config | recall@1 (95% CI) | recall@10 (95% CI) | mrr (95% CI) |
|---|---|---|---|
| production | 0.373 [0.254, 0.492] | 0.915 [0.831, 0.983] | 0.594 [0.506, 0.679] |
| chunk1500 | 0.712 [0.593, 0.831] | 0.932 [0.864, 0.983] | 0.811 [0.727, 0.890] |
| chunk800 | 0.627 [0.508, 0.746] | 0.915 [0.831, 0.983] | 0.729 [0.632, 0.820] |
| hybrid | 0.695 [0.576, 0.814] | 0.966 [0.915, 1.000] | 0.806 [0.727, 0.881] |
| rerank | 0.881 [0.797, 0.949] | 0.966 [0.915, 1.000] | 0.921 [0.856, 0.975] |

## Intervals, no-leakage (n=20)

| config | recall@1 (95% CI) | recall@10 (95% CI) | mrr (95% CI) |
|---|---|---|---|
| production | 0.400 [0.200, 0.600] | 0.750 [0.550, 0.900] | 0.575 [0.400, 0.750] |
| chunk1500 | 0.650 [0.450, 0.850] | 0.900 [0.750, 1.000] | 0.742 [0.575, 0.892] |
| chunk800 | 0.650 [0.450, 0.850] | 0.900 [0.750, 1.000] | 0.729 [0.554, 0.887] |
| hybrid | 0.500 [0.300, 0.700] | 0.900 [0.750, 1.000] | 0.667 [0.508, 0.817] |
| rerank | 0.750 [0.550, 0.900] | 0.900 [0.750, 1.000] | 0.817 [0.658, 0.950] |

## Comparisons, full (n=59)

| pair | metric | first | second | b, c or difference interval | raw p | Holm p |
|---|---|---|---|---|---|---|
| chunk1500 vs production | recall@1 | 0.712 | 0.373 | b=23, c=3 | 0.0001 | 0.0004 |
| chunk800 vs chunk1500 | recall@1 | 0.627 | 0.712 | b=6, c=11 | 0.3323 | 0.6646 |
| hybrid vs chunk1500 | recall@1 | 0.695 | 0.712 | b=4, c=5 | 1.0000 | 1.0000 |
| rerank vs chunk1500 | recall@1 | 0.881 | 0.712 | b=13, c=3 | 0.0213 | 0.0638 |
| hybrid vs rerank | recall@1 | 0.695 | 0.881 | b=2, c=13 | 0.0074 | 0.0295 |
| chunk1500 vs production | recall@10 | 0.932 | 0.915 | b=3, c=2 | 1.0000 | 1.0000 |
| chunk800 vs chunk1500 | recall@10 | 0.915 | 0.932 | b=1, c=2 | 1.0000 | 1.0000 |
| hybrid vs chunk1500 | recall@10 | 0.966 | 0.932 | b=2, c=0 | 0.5000 | 1.0000 |
| rerank vs chunk1500 | recall@10 | 0.966 | 0.932 | b=2, c=0 | 0.5000 | 1.0000 |
| hybrid vs rerank | recall@10 | 0.966 | 0.966 | b=0, c=0 | 1.0000 | 1.0000 |
| chunk1500 vs production | mrr | 0.811 | 0.594 | diff=0.216 [0.119, 0.314] | 0.0002 | 0.0010 |
| chunk800 vs chunk1500 | mrr | 0.729 | 0.811 | diff=-0.082 [-0.172, 0.004] | 0.0794 | 0.1588 |
| hybrid vs chunk1500 | mrr | 0.806 | 0.811 | diff=-0.004 [-0.065, 0.052] | 0.8755 | 0.8755 |
| rerank vs chunk1500 | mrr | 0.921 | 0.811 | diff=0.110 [0.035, 0.192] | 0.0072 | 0.0216 |
| hybrid vs rerank | mrr | 0.806 | 0.921 | diff=-0.114 [-0.188, -0.047] | 0.0015 | 0.0060 |

## Comparisons, no-leakage (n=20)

| pair | metric | first | second | b, c or difference interval | raw p | Holm p |
|---|---|---|---|---|---|---|
| chunk1500 vs production | recall@1 | 0.650 | 0.400 | b=5, c=0 | 0.0625 | 0.3125 |
| chunk800 vs chunk1500 | recall@1 | 0.650 | 0.650 | b=2, c=2 | 1.0000 | 1.0000 |
| hybrid vs chunk1500 | recall@1 | 0.500 | 0.650 | b=1, c=4 | 0.3750 | 1.0000 |
| rerank vs chunk1500 | recall@1 | 0.750 | 0.650 | b=4, c=2 | 0.6875 | 1.0000 |
| hybrid vs rerank | recall@1 | 0.500 | 0.750 | b=1, c=6 | 0.1250 | 0.5000 |
| chunk1500 vs production | recall@10 | 0.900 | 0.750 | b=3, c=0 | 0.2500 | 1.0000 |
| chunk800 vs chunk1500 | recall@10 | 0.900 | 0.900 | b=0, c=0 | 1.0000 | 1.0000 |
| hybrid vs chunk1500 | recall@10 | 0.900 | 0.900 | b=0, c=0 | 1.0000 | 1.0000 |
| rerank vs chunk1500 | recall@10 | 0.900 | 0.900 | b=0, c=0 | 1.0000 | 1.0000 |
| hybrid vs rerank | recall@10 | 0.900 | 0.900 | b=0, c=0 | 1.0000 | 1.0000 |
| chunk1500 vs production | mrr | 0.742 | 0.575 | diff=0.167 [0.029, 0.329] | 0.0468 | 0.2025 |
| chunk800 vs chunk1500 | mrr | 0.729 | 0.742 | diff=-0.013 [-0.146, 0.133] | 0.8666 | 0.8888 |
| hybrid vs chunk1500 | mrr | 0.667 | 0.742 | diff=-0.075 [-0.200, 0.050] | 0.2963 | 0.8888 |
| rerank vs chunk1500 | mrr | 0.817 | 0.742 | diff=0.075 [-0.071, 0.213] | 0.3540 | 0.8888 |
| hybrid vs rerank | mrr | 0.667 | 0.817 | diff=-0.150 [-0.292, -0.017] | 0.0405 | 0.2025 |

How to read a difference interval that crosses zero: when the 95% interval for a mean difference includes zero, the data do not rule out no difference between the two configs at that confidence level, even if the point estimate favors one side. A raw or Holm-adjusted p-value above alpha carries the same reading for the paired tests above.
