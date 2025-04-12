---
tags:
- floating-point-compression
---

Floating point compression with the [Patas] algorithm from DuckDB project.

[Patas]: https://github.com/duckdb/duckdb/pull/5044

It's based on the Chimp128 algorithm, but it's byte-aligned and only covers the
case where it refers to previous values (for Chimp128, flag bits `01`).

Patas is [a monkey](https://en.wikipedia.org/wiki/Common_patas_monkey).
