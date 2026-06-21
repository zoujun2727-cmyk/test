# HyperLogLog

A from-scratch, dependency-free implementation of **HyperLogLog**, the
probabilistic algorithm for counting distinct elements in a stream using a
fixed, tiny amount of memory.

## The problem

How many *distinct* values are in a stream? The exact answer requires
remembering every value you've seen — `O(n)` memory. For a stream of a billion
distinct 16-byte IDs, that's tens of gigabytes just to hold a set.

HyperLogLog answers the same question with a small, bounded error using a fixed
amount of memory that does **not** grow with the stream. The implementation
here uses `2**p` one-byte registers — 16 KB at the default `p=14` — to count
into the billions.

## The intuition

1. **Hash everything.** Map each element to a uniformly random 64-bit string.
   Duplicates collapse to the same hash, so only distinct elements matter.

2. **Watch the leading zeros.** In random bitstrings, a hash starting with `k`
   zeros occurs with probability `2**-(k+1)`. So if the longest leading-zero run
   you've ever seen is `k`, you've probably seen on the order of `2**k` distinct
   hashes. That single number is a (very noisy) cardinality estimate.

3. **Average many estimators.** One estimator has huge variance. HyperLogLog
   uses the first `p` bits of each hash to pick one of `m = 2**p` registers, and
   the rest of the hash to update that register's max leading-zero count.
   Combining the registers with a **harmonic mean** and a bias-correction
   constant `alpha` crushes the variance.

The relative error is approximately `1.04 / sqrt(m)`. At `p=14`,
`m = 16384`, giving a standard error of about **0.81%**.

A **small-range correction** (linear counting) kicks in when many registers are
still empty, which is where the raw estimator is least accurate.

## Why it's elegant

Each register stores a *maximum*, so two HyperLogLogs over different shards of
data merge by taking the element-wise max of their registers. This makes the
structure trivially **parallelizable and distributable**: count shards
independently on separate machines, then merge the sketches — no need to ever
see the union of the raw data. The `merge()` method demonstrates this.

## Usage

```python
from hyperloglog import HyperLogLog

hll = HyperLogLog(p=14)
for event in stream:
    hll.add(event)         # accepts str, bytes, or any repr-able object

print(hll.count())         # estimated distinct count
print(len(hll))            # same thing

# Distributed counting: merge independent sketches.
a.merge(b)
```

## Results

Running `python3 hyperloglog.py` (default `p=14`, ~16 KB of registers):

| true      | estimate  | error  |
| --------- | --------- | ------ |
| 100       | 100       | 0.00%  |
| 1,000     | 1,004     | 0.40%  |
| 10,000    | 10,024    | 0.24%  |
| 100,000   | 98,583    | 1.42%  |
| 1,000,000 | 992,542   | 0.75%  |

A million distinct items counted to within 1% — using a constant 16 KB,
no matter how large the stream grows.

## Tuning

`p` controls the space/accuracy trade-off:

| `p` | registers (`m`) | memory  | std. error |
| --- | --------------- | ------- | ---------- |
| 10  | 1,024           | 1 KB    | ~3.25%     |
| 12  | 4,096           | 4 KB    | ~1.62%     |
| 14  | 16,384          | 16 KB   | ~0.81%     |
| 16  | 65,536          | 64 KB   | ~0.41%     |
