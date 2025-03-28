use bytes::{BufMut, Bytes, BytesMut};

pub struct Bitwrite {
    buf: BytesMut,
    bitbuf: u8,
    bitcount: u8,
}

impl Bitwrite {
    pub fn new(buf: BytesMut) -> Self {
        Bitwrite {
            buf,
            bitbuf: 0,
            bitcount: 0,
        }
    }

    pub fn put_bit(&mut self, value: u8) {
        self.bitbuf = self.bitbuf | (value << (7 - self.bitcount));
        self.bitcount += 1;
        if self.bitcount == 8 {
            self.buf.put_u8(self.bitbuf);
            self.bitcount = 0;
            self.bitbuf = 0;
        }
    }

    pub fn put_u64_lowest_bits(&mut self, value: u64, count: u8) {
        for i in 0..count {
            let bit = ((value >> (count - i - 1)) & 1) as u8;
            self.put_bit(bit);
        }
    }

    pub fn put_f64(&mut self, value: f64) {
        self.put_u64_lowest_bits(value.to_bits(), 64);
    }

    pub fn to_bytes(mut self) -> Bytes {
        self.buf.put_u8(self.bitbuf);
        self.buf.split().into()
    }
}

pub struct Bitread<'a> {
    buf: &'a [u8],
    bytep: usize,
    bitp: u8,
}

impl<'a> Bitread<'a> {
    pub fn new(buf: &'a [u8]) -> Self {
        Bitread {
            buf,
            bytep: 0,
            bitp: 0,
        }
    }

    pub fn read_bit(&mut self) -> u8 {
        let result = self.buf[self.bytep] >> (7 - self.bitp) & 1;
        self.bitp += 1;
        if self.bitp == 8 {
            self.bytep += 1;
            self.bitp = 0;
        }
        result
    }

    pub fn read_u64_lowest_bits(&mut self, count: u8) -> u64 {
        let mut bits: u64 = 0;
        for _ in 0..count {
            bits = (bits << 1) | (self.read_bit() as u64);
        }
        bits
    }

    pub fn read_f64(&mut self) -> f64 {
        f64::from_bits(self.read_u64_lowest_bits(64))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bitstream_write_read_bits() {
        let buf = BytesMut::with_capacity(1024);
        let mut stream = Bitwrite::new(buf);
        let write_bits = [1, 0, 1, 1, 0, 0, 1, 0];

        for bit in write_bits {
            stream.put_bit(bit);
        }

        let bytes = stream.to_bytes();
        let mut r = Bitread::new(&bytes);

        let mut read_bits: Vec<u8> = vec![];
        for _ in 0..8 {
            read_bits.push(r.read_bit());
        }

        assert_eq!(&read_bits[..], write_bits);
    }

    #[test]
    fn bitstream_write_read_f64() {
        let buf = BytesMut::with_capacity(1024);
        let mut stream = Bitwrite::new(buf);
        let value = 123.456;

        stream.put_f64(value);

        let bytes = stream.to_bytes();

        println!("{:x?}", &bytes);

        let mut r = Bitread::new(&bytes);
        assert_eq!(r.read_f64(), value)
    }
}
