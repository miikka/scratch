mod bits;
pub mod chimp128;

use bits::{Bitread, Bitwrite};
use bytes::{Bytes, BytesMut};

/// Counts the trailing zeros in the binary representation of the given integer.
fn count_trailing(x: u64) -> u8 {
    if x == 0 {
        return 64;
    }

    let mut x = x;
    let mut count = 0;

    while x > 0 {
        if x & 1 == 1 {
            break;
        }

        count += 1;
        x >>= 1;
    }

    count
}

fn bin_count(count: u8) -> u8 {
    let bins = [0, 8, 12, 16, 18, 20, 22, 24];
    let mut prev = bins[0];

    for &bin in bins[1..].iter() {
        if count < bin {
            return prev;
        }
        prev = bin;
    }

    24
}

fn bin_count_leading(x: u64) -> u8 {
    bin_count(count_leading(x))
}

fn bin_encode(bin_count: u8) -> u8 {
    [0, 8, 12, 16, 18, 20, 22, 24]
        .iter()
        .position(|&r| r == bin_count)
        .unwrap() as u8
}

fn bin_decode(bin_index: u8) -> u8 {
    [0, 8, 12, 16, 18, 20, 22, 24][bin_index as usize]
}

/// Counst the leading zeros in the binary representation of the given integer.
fn count_leading(x: u64) -> u8 {
    if x == 0 {
        return 64;
    }

    let mut count = 0;
    let mut mask = 1 << 63;
    loop {
        if (x & mask) == mask {
            break;
        }
        mask >>= 1;
        count += 1;
    }

    count
}

pub fn encode(input: &[f64]) -> Bytes {
    let buf = BytesMut::new();

    if input.len() == 0 {
        return buf.into();
    }

    let mut stream = Bitwrite::new(buf);
    stream.put_f64(input[0]);

    let mut prev_bits = input[0].to_bits();
    let mut prev_leading = bin_count_leading(prev_bits);

    for curr in input[1..].iter() {
        let curr_bits = curr.to_bits();
        let xor = prev_bits ^ curr_bits;

        let trailing = count_trailing(xor);

        if trailing > 6 {
            stream.put_bit(0);

            if xor == 0 {
                // println!("control 00");
                stream.put_bit(0);
            } else {
                // println!("control 01");
                stream.put_bit(1);
                let leading = bin_count_leading(xor);
                let meaningful_count = 64 - trailing - leading;
                stream.put_u64_lowest_bits(bin_encode(leading) as u64, 3);
                stream.put_u64_lowest_bits(meaningful_count as u64, 6);
                stream.put_u64_lowest_bits(xor >> trailing, meaningful_count);

                prev_leading = leading;
            }
        } else {
            stream.put_bit(1);
            let leading = bin_count_leading(xor);
            if leading == prev_leading {
                // println!("control 10");
                // println!("leading = {:2} xor = {:064b}", leading, xor);
                stream.put_bit(0);
                stream.put_u64_lowest_bits(xor, 64 - leading);
            } else {
                // println!("control 11");
                // println!("leading = {:2} xor = {:064b}", leading, xor);
                stream.put_bit(1);
                stream.put_u64_lowest_bits(bin_encode(leading) as u64, 3);
                stream.put_u64_lowest_bits(xor, 64 - leading);
            }
            prev_leading = leading;
        }

        prev_bits = curr_bits;
    }

    stream.to_bytes()
}

pub fn decode(input: &[u8], count: usize) -> Vec<f64> {
    let mut result = vec![];
    let mut stream = Bitread::new(input);

    let first = stream.read_f64();
    result.push(first);

    let mut prev = first;
    let mut prev_bits = first.to_bits();
    let mut prev_leading = bin_count_leading(prev_bits);

    for _ in 1..count {
        if stream.read_bit() == 0 {
            if stream.read_bit() == 0 {
                // println!("control 00");
                result.push(prev);
            } else {
                // println!("control 01");
                let leading = bin_decode(stream.read_u64_lowest_bits(3) as u8);
                let meaningful_count = stream.read_u64_lowest_bits(6);
                let meaningful = stream.read_u64_lowest_bits(meaningful_count as u8);
                let trailing = 64 - leading - meaningful_count as u8;

                let curr_bits = prev_bits ^ (meaningful << trailing);
                let curr = f64::from_bits(curr_bits);
                result.push(curr);

                prev_bits = curr_bits;
                prev_leading = leading as u8;
                prev = curr;
            }
        } else {
            if stream.read_bit() == 0 {
                // println!("control 10");
                let xor = stream.read_u64_lowest_bits(64 - prev_leading);

                // println!("leading = {:2} xor = {:064b}", prev_leading, xor);

                let curr_bits = prev_bits ^ xor;
                let curr = f64::from_bits(curr_bits);
                result.push(curr);

                prev_bits = curr_bits;
                prev = curr;
            } else {
                // println!("control 11");
                let leading = bin_decode(stream.read_u64_lowest_bits(3) as u8);
                let xor = stream.read_u64_lowest_bits(64 - leading);
                // println!("leading = {:2} xor = {:064b}", leading, xor);
                let curr_bits = prev_bits ^ xor;
                let curr = f64::from_bits(curr_bits);
                result.push(curr);

                prev_bits = curr_bits;
                prev = curr;
                prev_leading = leading;
            }
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use proptest::prelude::*;

    use super::*;

    #[test]
    fn test_count_trailing() {
        assert_eq!(count_trailing(0), 64);
        assert_eq!(count_trailing(1), 0);
        assert_eq!(count_trailing(0xFF_FF_FF_FF_FF_FF_FF_FF), 0);
        assert_eq!(count_trailing(0x80_00_00_00_00_00_00_00), 63);
        assert_eq!(count_trailing(0x01_00_00_00_00_00_00_00), 56);
    }

    #[test]
    fn test_count_leading() {
        assert_eq!(count_leading(0), 64);
        assert_eq!(count_leading(1), 63);
        assert_eq!(count_leading(0xFF_FF_FF_FF_FF_FF_FF_FF), 0);
        assert_eq!(count_leading(0x80_00_00_00_00_00_00_00), 0);
        assert_eq!(count_leading(0x01_00_00_00_00_00_00_00), 7);
    }

    #[test]
    fn test_write_read() {
        let values = [1.1, 1.1, 2.2, 0.0, 3.3];
        let bytes = encode(&values);
        println!("");
        let decoded = decode(&bytes, values.len());
        assert_eq!(values, &decoded[..]);
    }

    proptest! {
        // Leaving NaNs out of the generated values because prop_assert_eq believes NaN != NaN (as it should in general)
        #[test]
        fn prop_read_write(input in prop::collection::vec(prop::num::f64::POSITIVE | prop::num::f64::NEGATIVE | prop::num::f64::NORMAL | prop::num::f64::SUBNORMAL | prop::num::f64::ZERO, 1..100)) {
            let bytes = encode(&input);
            let output = decode(&bytes, input.len());
            prop_assert_eq!(&input, &output);
        }
    }
}
