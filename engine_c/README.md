# Engine C (Rust)

This is a third, independent implementation of the measures, written in Rust. It is loaded into Python with PyO3.
When it is installed, an answer is shown only if A (numpy), B (DuckDB SQL) and C (Rust) all agree. They must agree on the values and on the dates.

## Build it (Windows)

1. Install Rust from https://rustup.rs. It is free and needs no card. The MSVC build tools come with Visual Studio Build Tools; the rustup installer offers them.
2. Run these from the project folder:

```
pip install maturin
cd engine_c
maturin develop --release
cd ..
python -m pytest -q
```

## Without it

Without engine C the app runs on A and B only. Every answer's detail says which engines checked it, for example `engines: A+B`.
Set `IMAP_REQUIRE_C=1` to make the app refuse to start without engine C.

## Tests

The Rust unit tests check:
- the calendar maths, across about 4,000 years of days;
- month clamping (for example 31 Mar minus one month gives 28 or 29 Feb);
- XIRR against a known answer;
- drawdown on a small example.

Run them with `cargo test --no-default-features`.
