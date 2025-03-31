mod bits;

use bits::{Bitread, Bitwrite};
use bytes::{Bytes, BytesMut};

pub(crate) fn leading_zeros(x: u64) -> u8 {
    let mut count = 0;

    while count < 64 {
        if x >> (63 - count) != 0 {
            break;
        }
        count += 1;
    }

    count
}

pub(crate) fn trailing_zeros(x: u64) -> u8 {
    let mut count: u8 = 0;
    while count < 64 {
        if (x >> count) & 1 != 0 {
            break;
        }
        count += 1;
    }
    count
}

pub fn encode(input: &[f64]) -> Bytes {
    let buf = BytesMut::with_capacity(input.len() * 8);

    if input.len() == 0 {
        return buf.into();
    }

    let mut stream = Bitwrite::new(buf);

    stream.put_f64(input[0]);

    let mut prev_bits = input[0].to_bits();
    let mut prev_leading = 0;
    let mut prev_trailing = 0;

    for curr in input[1..].iter() {
        let curr_bits = curr.to_bits();
        let xor = prev_bits ^ curr_bits;
        if xor == 0 {
            stream.put_bit(0);
            // println!("control 0");
        } else {
            stream.put_bit(1);
            let leading = leading_zeros(xor);
            let trailing: u8 = trailing_zeros(xor);
            let meaningful = xor >> trailing;

            if leading >= prev_leading && trailing == prev_trailing {
                // println!("control 10");
                stream.put_bit(0);
                let meaningful_len = 64 - prev_leading - prev_trailing;
                stream.put_u64_lowest_bits(meaningful, meaningful_len);
            } else {
                // println!("control 11");
                stream.put_bit(1);

                stream.put_u64_lowest_bits(leading as u64, 5);

                let meaningful_len = 64 - leading - trailing;
                stream.put_u64_lowest_bits(meaningful_len as u64, 6);
                stream.put_u64_lowest_bits(meaningful, meaningful_len);

                // println!(
                //     "leading {} xor_length {} xor {:b}",
                //     leading, meaningful_len, meaningful
                // );

                prev_leading = leading;
                prev_trailing = trailing;
            }

            prev_bits = curr_bits;
        }
    }

    stream.to_bytes()
}

pub fn decode(input: &[u8], count: usize) -> Vec<f64> {
    let mut result = vec![];

    let mut stream = Bitread::new(input);

    let mut prev = stream.read_f64();
    result.push(prev);

    let mut prev_bits = prev.to_bits();
    let mut prev_leading = 0;
    let mut prev_trailing = 0;

    for _ in 1..count {
        if stream.read_bit() == 0 {
            // println!("control 0");
            result.push(prev)
        } else if stream.read_bit() == 0 {
            // println!("control 10");
            let xor = stream.read_u64_lowest_bits(64 - prev_leading - prev_trailing);
            let curr_bits = prev_bits ^ (xor << prev_trailing);
            let curr = f64::from_bits(curr_bits);
            result.push(curr);
            prev = curr;
            prev_bits = curr_bits;
        } else {
            // println!("control 11");
            let leading = stream.read_u64_lowest_bits(5) as u8;
            let mut xor_length = stream.read_u64_lowest_bits(6) as u8;

            if xor_length == 0 {
                xor_length = 64;
            }

            let xor = stream.read_u64_lowest_bits(xor_length);

            // println!(
            //     "leading {} xor_length {} xor {:b}",
            //     leading, xor_length, xor
            // );
            let trailing = 64 - leading - xor_length;
            let curr_bits = prev_bits ^ (xor << trailing);
            let curr = f64::from_bits(curr_bits);
            result.push(curr);
            prev = curr;
            prev_bits = curr_bits;
            prev_leading = leading;
            prev_trailing = trailing;
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use proptest::prelude::*;

    use super::*;

    #[test]
    fn test_leading_zeros() {
        assert_eq!(leading_zeros(0), 64);
        assert_eq!(leading_zeros(1), 63);
        assert_eq!(leading_zeros(0xFF_FF_FF_FF_FF_FF_FF_FF), 0);
        assert_eq!(leading_zeros(0x80_00_00_00_00_00_00_00), 0);
        assert_eq!(leading_zeros(0x01_00_00_00_00_00_00_00), 7);
    }

    #[test]
    fn test_trailing_zeros() {
        assert_eq!(trailing_zeros(0), 64);
        assert_eq!(trailing_zeros(1), 0);
        assert_eq!(trailing_zeros(0xFF_FF_FF_FF_FF_FF_FF_FF), 0);
        assert_eq!(trailing_zeros(0x80_00_00_00_00_00_00_00), 63);
        assert_eq!(trailing_zeros(0x01_00_00_00_00_00_00_00), 56);
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
