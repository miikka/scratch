pub fn encode_single(input: u64) -> Vec<u8> {
    let mut x = input;
    let mut out = vec![];

    loop {
        let byte = x & 0b111_1111;
        x = x >> 7;
        if x > 0 {
            out.push((byte | 0b1000_0000) as u8);
        } else {
            out.push(byte as u8);
            break;
        }
    }

    out
}

pub fn decode_single(input: &[u8]) -> (u64, usize) {
    let mut out: u64 = 0;
    let mut count: usize = 0;

    for x in input {
        out = out | ((x & 0b111_1111) as u64) << (count * 7);
        count += 1;
        if x & 0b1000_0000 == 0 {
            break;
        }
    }

    (out, count)
}

// TODO(miikka) encode for &[u64] and corresponding decode
// TODO(miikka) decode_single should return an error if there's too little input

#[cfg(test)]
mod tests {
    use super::*;
    use hegel::TestCase;
    use hegel::generators as gs;

    #[test]
    fn test_encode_single() {
        assert_eq!(vec![0x80, 1], encode_single(128));
    }

    #[test]
    fn test_decode_single() {
        assert_eq!((128, 2), decode_single(&[0x80, 1]));
    }

    #[hegel::test]
    fn roundtrip(tc: TestCase) {
        let input = tc.draw(gs::integers::<u64>());
        let encoded = encode_single(input);
        let (decoded, _) = decode_single(&encoded);
        assert_eq!(decoded, input);
    }
}
