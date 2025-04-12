use bytes::{Bytes, BytesMut};

use crate::{
    bin_count_leading, bin_decode, bin_encode,
    bits::{Bitread, Bitwrite},
    count_leading, count_trailing,
};

pub fn encode(input: &[f64]) -> Bytes {
    let buf = BytesMut::new();

    if input.len() == 0 {
        return buf.into();
    }

    let mut stream = Bitwrite::new(buf);

    // We use the MAX values to signify that the slots has not been initialized
    let mut ringbuf: [u64; 128] = [u64::MAX; 128];
    let mut lookup: [usize; 16384] = [usize::MAX; 16384];

    let first = input[0];

    stream.put_f64(first);

    let mut prev_bits = first.to_bits();
    let mut prev_leading = count_leading(prev_bits);
    ringbuf[0] = prev_bits;

    // 0x3FFF = 16383 = 16384 - 1 = 2^14 - 1;
    lookup[(prev_bits & 0x3FFF) as usize] = 0;

    let mut index = 1;
    for curr in input[1..].iter() {
        let curr_bits = curr.to_bits();

        let lookup_index = lookup[(curr_bits & 0x3FFF) as usize];
        let best_index = if lookup_index != usize::MAX && index - lookup_index <= 128 {
            lookup_index % 128
        } else {
            ringbuf
                .iter()
                .filter(|x| **x != u64::MAX)
                .enumerate()
                .max_by_key(|(_, x)| count_trailing(**x))
                .unwrap()
                .0
        };
        let best_bits = ringbuf[best_index];
        let xor = curr_bits ^ best_bits;
        let trailing = count_trailing(xor);

        // log2(128) + log2(64) = 13
        if trailing > 13 {
            stream.put_bit(0);
            stream.put_u64_lowest_bits((index - best_index) as u64, 7);

            if xor == 0 {
                println!("control 00");
                println!("index = {} bits = {:064b}", index - best_index, best_bits);
                stream.put_bit(0);
            } else {
                println!("control 01");
                println!(
                    "index = {} rb = {} bits = {:064b}",
                    index - best_index,
                    best_index,
                    best_bits
                );
                stream.put_bit(1);
                let leading = bin_count_leading(xor);
                stream.put_u64_lowest_bits(bin_encode(leading) as u64, 3);
                let meaningful_count = 64 - leading - trailing;
                stream.put_u64_lowest_bits(meaningful_count as u64, 6);
                stream.put_u64_lowest_bits(xor >> trailing, meaningful_count);
                println!(
                    "leading = {} meaningful_count = {} trailing = {} xor = {:b}",
                    leading,
                    meaningful_count,
                    trailing,
                    xor >> trailing
                );
                prev_leading = leading;
            }
        } else {
            stream.put_bit(1);
            let xor = curr_bits ^ prev_bits;
            let leading = bin_count_leading(xor);
            if prev_leading == leading {
                println!("control 10");
                println!("xor = {:064b} leading = {}", xor, leading);
                stream.put_bit(0);
            } else {
                println!("control 11");
                stream.put_bit(1);
                stream.put_u64_lowest_bits(bin_encode(leading) as u64, 3);
            }
            stream.put_u64_lowest_bits(xor, 64 - leading);
            prev_leading = leading;
        }

        ringbuf[index % 128] = curr_bits;
        lookup[(curr_bits & 0x3FFF) as usize] = index;
        prev_bits = curr_bits;
        index += 1;
    }

    stream.to_bytes()
}

pub fn decode(input: &[u8], count: usize) -> Vec<f64> {
    let mut stream = Bitread::new(input);
    let mut result = vec![];

    let mut ringbuf: [u64; 128] = [u64::MAX; 128];
    let mut lookup: [usize; 16384] = [usize::MAX; 16384];

    let first = stream.read_f64();
    let first_bits = first.to_bits();
    result.push(first);
    ringbuf[0] = first_bits;
    lookup[(first_bits & 0x3FFF) as usize] = 0;

    let mut prev_bits = first_bits;
    let mut prev_leading = bin_count_leading(first_bits);

    for index in 1..count {
        if stream.read_bit() == 0 {
            let best_index = stream.read_u64_lowest_bits(7);
            let rb_index = (128 + index - best_index as usize) % 128;
            let best_bits = ringbuf[rb_index];
            assert!(
                best_bits != u64::MAX,
                "best bits uninitialized, best_index = {}",
                best_index
            );

            let curr_bits = if stream.read_bit() == 0 {
                println!("control 00");
                println!("index = {} bits = {:064b}", best_index, best_bits);
                best_bits
            } else {
                println!("control 01");
                println!(
                    "index = {} rb = {} bits = {:064b}",
                    best_index, rb_index, best_bits
                );
                let leading = bin_decode(stream.read_u64_lowest_bits(3) as u8);
                let meaningful_count = stream.read_u64_lowest_bits(6);
                let meaningful = stream.read_u64_lowest_bits(meaningful_count as u8);
                let trailing = 64 - leading - meaningful_count as u8;
                println!(
                    "leading = {} meaningful_count = {} trailing = {} xor = {:b}",
                    leading, meaningful_count, trailing, meaningful
                );
                prev_leading = leading;
                best_bits ^ (meaningful << trailing)
            };
            let curr = f64::from_bits(curr_bits);
            result.push(curr);

            prev_bits = curr_bits;
        } else {
            let xor = if stream.read_bit() == 0 {
                println!("control 10");
                stream.read_u64_lowest_bits(64 - prev_leading as u8)
            } else {
                println!("control 11");
                let leading = bin_decode(stream.read_u64_lowest_bits(3) as u8);
                prev_leading = leading;
                stream.read_u64_lowest_bits(64 - leading as u8)
            };
            println!("xor = {:064b} leading = {}", xor, prev_leading);
            let curr_bits = prev_bits ^ xor;
            let curr = f64::from_bits(curr_bits);
            result.push(curr);
            prev_bits = curr_bits;
        }

        ringbuf[index % 128] = prev_bits;
        lookup[(prev_bits & 0x3FFF) as usize] = index;
    }

    result
}

#[cfg(test)]
mod tests {
    use proptest::prelude::*;

    use super::*;

    #[test]
    fn test_write_read() {
        // let values = [1.1, 1.1, 2.2, 0.0, 3.3];
        let values = [-2.17807901754863e-309, -9.63389622320938e-309, 0.0];
        let bytes = encode(&values);
        println!("");
        let decoded = decode(&bytes, values.len());
        assert_eq!(values, &decoded[..]);
    }

    proptest! {
        // Leaving NaNs out of the generated values because prop_assert_eq believes NaN != NaN (as it should in general)
        #[test]
        fn prop_read_write(input in prop::collection::vec(prop::num::f64::POSITIVE | prop::num::f64::NEGATIVE | prop::num::f64::NORMAL | prop::num::f64::SUBNORMAL | prop::num::f64::ZERO, 1..1024)) {
            let bytes = encode(&input);
            let output = decode(&bytes, input.len());
            prop_assert_eq!(&input, &output);
        }
    }
}
