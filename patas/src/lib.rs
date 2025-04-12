use bytes::{Buf, BufMut, Bytes, BytesMut};

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
    let mut buf = BytesMut::new();

    if input.len() == 0 {
        return buf.into();
    }

    buf.put_f64(input[0]);

    let mut ringbuf: [u64; 128] = [0; 128];
    let mut lookup: [u8; 16384] = [u8::MAX; 16384];

    let prev_bits = input[0].to_bits();
    ringbuf[0] = prev_bits;
    lookup[(prev_bits & 0x3FFF) as usize] = 0;

    let mut index = 1;
    for curr in input[1..].iter() {
        let curr_bits = curr.to_bits();
        let lookup_index = lookup[(curr_bits & 0x3FFF) as usize];

        let best_index = if lookup_index < u8::MAX {
            lookup_index
        } else {
            ringbuf
                .iter()
                .enumerate()
                .filter(|(i, _)| (*i as u8) < index)
                .max_by_key(|(_, val)| count_trailing(curr_bits ^ *val))
                .unwrap()
                .0 as u8
        };
        let best_bits = ringbuf[best_index as usize];

        let xor = curr_bits ^ best_bits;

        let (trailing, meaningful_bytes) = if xor == 0 {
            (0, 0)
        } else {
            let trailing = count_trailing(xor);
            let leading = count_leading(xor);
            let meaningful_bytes = (64 - trailing - leading).div_ceil(8);
            (trailing, meaningful_bytes - 1)
        };

        let ref_index = index - best_index;
        let header: u16 = ((ref_index as u16) << 9)
            | ((meaningful_bytes as u16) << 6)
            | (trailing & 0b111111) as u16;
        buf.put_u16(header);

        println!("header = {:0b}", header);

        println!(
            "best_index = {} ref_index = {} meaningful_bytes = {} trailing = {}",
            best_index, ref_index, meaningful_bytes, trailing
        );

        println!("xor = {:064b}", xor);

        if xor != 0 {
            let meaningful = xor >> trailing;
            for i in 0..(meaningful_bytes + 1) {
                let value = (meaningful >> ((meaningful_bytes - i) * 8)) & 0xFF;
                buf.put_u8(value as u8);
            }
        }

        ringbuf[(index % 128) as usize] = curr_bits;
        lookup[(curr_bits & 0x3FFF) as usize] = index % 128;
        index += 1;
    }

    buf.into()
}

pub fn decode(input: &[u8], count: usize) -> Vec<f64> {
    // TODO(miikka) How to use Bytes-like interface without copying the data?
    let mut buf = Bytes::copy_from_slice(input);
    let mut result: Vec<f64> = vec![];

    let first = buf.get_f64();
    result.push(first);

    let mut ringbuf: [u64; 128] = [0; 128];
    let first_bits = first.to_bits();
    ringbuf[0] = first_bits;

    for index in 1..count {
        let header = buf.get_u16();

        println!("header = {:0b}", header);

        let ref_index = (header >> 9) as usize;
        let best_index = index - ref_index;

        assert!(
            best_index < index,
            "best_index {} greater or equal to the index {}",
            best_index,
            index
        );

        let meaningful_bytes = (header >> 6) & 0b111;
        let trailing = header & 0b111111;

        let xor = if trailing == 0 && meaningful_bytes == 0 {
            0
        } else {
            let mut meaningful: u64 = 0;
            for _ in 0..(meaningful_bytes + 1) {
                meaningful = meaningful << 8 | (buf.get_u8() as u64);
            }
            meaningful << trailing
        };

        println!(
            "best_index = {} ref_index = {} meaningful_bytes = {} trailing = {}",
            best_index, ref_index, meaningful_bytes, trailing
        );
        println!("xor = {:064b}", xor);

        let best_bits = ringbuf[best_index as usize];
        let curr_bits = best_bits ^ xor;
        let curr = f64::from_bits(curr_bits);

        ringbuf[index % 128] = curr_bits;
        result.push(curr);
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

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
