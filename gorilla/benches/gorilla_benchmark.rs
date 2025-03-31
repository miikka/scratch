use criterion::{black_box, criterion_group, criterion_main, Criterion};
use gorilla::{decode, encode};

pub fn criterion_benchmark(c: &mut Criterion) {
    let mut data = vec![];
    for i in 0..1024 {
        let i = i as f64;
        data.push(i + i.sin());
    }

    let encoded = encode(&data);
    let encoded_len = data.len();

    c.bench_function("encode", |b| b.iter(|| encode(black_box(&data))));
    c.bench_function("decode", |b| {
        b.iter(|| decode(black_box(&encoded), black_box(encoded_len)))
    });
}

criterion_group!(benches, criterion_benchmark);
criterion_main!(benches);
