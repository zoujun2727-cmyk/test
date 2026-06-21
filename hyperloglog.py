"""HyperLogLog: probabilistic cardinality estimation.

HyperLogLog estimates the number of *distinct* elements in a stream using a
fixed, tiny amount of memory (here: 2**p counters of one byte each), regardless
of how many elements pass through. It trades exact answers for a small,
tunable error in exchange for enormous memory savings -- counting billions of
distinct items in a few kilobytes.

The core intuition:

  Hash each element to a uniformly random bitstring. In a stream of distinct
  elements, the rarest event observed -- the longest run of leading zeros in
  any hash -- tells you roughly how many distinct elements you've seen. Seeing
  a hash that starts with k zeros happens with probability 2**-(k+1), so
  observing a maximum run of k zeros suggests on the order of 2**k distinct
  values.

  A single estimator like that is wildly noisy, so HyperLogLog splits the hash:
  the first p bits choose one of m = 2**p "registers", and the remaining bits
  feed that register's leading-zero count. Averaging across m registers (with a
  harmonic mean and a bias-correction constant) collapses the variance. The
  relative error is about 1.04 / sqrt(m).

This module has no third-party dependencies; it uses Python's built-in hashlib.
"""

from __future__ import annotations

import hashlib
import math


class HyperLogLog:
    """A HyperLogLog cardinality estimator.

    Args:
        p: Precision. The number of registers is m = 2**p. Larger p means more
           memory (2**p bytes) and lower error (~1.04 / sqrt(2**p)). Must be in
           [4, 16]. p=14 -> 16384 registers, ~0.81% standard error.
    """

    def __init__(self, p: int = 14) -> None:
        if not 4 <= p <= 16:
            raise ValueError("p must be between 4 and 16")
        self.p = p
        self.m = 1 << p
        self.registers = bytearray(self.m)
        self.alpha = self._alpha(self.m)

    @staticmethod
    def _alpha(m: int) -> float:
        """Bias-correction constant for the harmonic-mean estimator."""
        if m == 16:
            return 0.673
        if m == 32:
            return 0.697
        if m == 64:
            return 0.709
        return 0.7213 / (1.0 + 1.079 / m)

    def _hash64(self, data: bytes) -> int:
        """Map an element to a uniform 64-bit integer."""
        digest = hashlib.sha1(data).digest()[:8]
        return int.from_bytes(digest, "big")

    def add(self, element) -> None:
        """Add an element to the estimator."""
        if isinstance(element, bytes):
            data = element
        elif isinstance(element, str):
            data = element.encode("utf-8")
        else:
            data = repr(element).encode("utf-8")

        x = self._hash64(data)
        # Top p bits select the register.
        idx = x >> (64 - self.p)
        # Remaining (64 - p) bits: count leading zeros, +1, for the rank.
        remaining = x & ((1 << (64 - self.p)) - 1)
        rank = (64 - self.p) - remaining.bit_length() + 1
        if rank > self.registers[idx]:
            self.registers[idx] = rank

    def count(self) -> int:
        """Return the estimated number of distinct elements added."""
        # Raw harmonic-mean estimate.
        inv_sum = 0.0
        zeros = 0
        for reg in self.registers:
            inv_sum += 1.0 / (1 << reg)
            if reg == 0:
                zeros += 1

        estimate = self.alpha * self.m * self.m / inv_sum

        # Small-range correction: when many registers are still empty,
        # linear counting is far more accurate.
        if estimate <= 2.5 * self.m and zeros != 0:
            estimate = self.m * math.log(self.m / zeros)

        return int(round(estimate))

    def merge(self, other: "HyperLogLog") -> None:
        """Merge another HyperLogLog into this one (must share precision p).

        Because each register holds a max, merging is just an element-wise max.
        This is what makes HyperLogLog trivially parallelizable: count shards
        independently, then combine.
        """
        if self.p != other.p:
            raise ValueError("cannot merge HyperLogLogs with different precision")
        for i in range(self.m):
            if other.registers[i] > self.registers[i]:
                self.registers[i] = other.registers[i]

    def __len__(self) -> int:
        return self.count()


if __name__ == "__main__":
    import random

    print(f"{'true':>10} {'estimate':>10} {'error %':>8}")
    print("-" * 30)
    for true_n in (100, 1_000, 10_000, 100_000, 1_000_000):
        hll = HyperLogLog(p=14)
        for i in range(true_n):
            hll.add(f"item-{i}")
        est = hll.count()
        err = abs(est - true_n) / true_n * 100
        print(f"{true_n:>10} {est:>10} {err:>7.2f}%")

    # Demonstrate mergeability: two disjoint halves merge into the whole.
    a, b = HyperLogLog(p=14), HyperLogLog(p=14)
    for i in range(50_000):
        a.add(f"x-{i}")
    for i in range(50_000, 100_000):
        b.add(f"x-{i}")
    a.merge(b)
    print(f"\nmerged estimate (true 100000): {a.count()}")
