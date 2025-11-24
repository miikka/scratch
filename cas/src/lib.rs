use std::{
    fs::{self, File},
    io::Write,
    path::{Path, PathBuf},
};

use thiserror::Error;

#[derive(Clone, Debug)]
pub struct Store {
    path: PathBuf,
}

#[derive(Error, Debug)]
pub enum CasError {
    #[error("io error")]
    IoError(#[from] std::io::Error),
    #[error("hex error")]
    HexError(#[from] blake3::HexError),
    #[error("unknown error")]
    Unknown,
}

#[derive(Clone, Debug)]
pub struct Key(blake3::Hash);

impl Key {
    pub fn from_hex_str(hex: &str) -> Result<Self, CasError> {
        let hash = blake3::Hash::from_hex(hex)?;
        Ok(Self(hash))
    }

    fn to_path(&self) -> PathBuf {
        let hex_str = self.0.to_string();
        PathBuf::from(&hex_str[0..2]).join(hex_str)
    }
}

// TODO(miikka) Compress the data before adding

impl Store {
    pub fn new(path: &Path) -> Self {
        Store {
            path: PathBuf::from(path),
        }
    }

    pub fn add(&self, data: &[u8]) -> Result<Key, CasError> {
        let key = blake3::hash(data);
        let key_hex = key.to_hex();
        let key_str: &str = &key_hex;
        let key_prefix = &key_hex[0..2];
        let data_dir = self.path.join(key_prefix);
        fs::create_dir_all(&data_dir)?;
        let data_path = data_dir.join(key_str);

        // Not exactly atomic or safe
        if !data_path.exists() {
            let mut file = File::create(&data_path)?;
            file.write_all(data)?;
        }

        Ok(Key(key))
    }

    pub fn get(&self, key: &Key) -> Result<Vec<u8>, CasError> {
        let data_path = self.path.join(key.to_path());
        let data = fs::read(data_path)?;
        Ok(data)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // TODO(miikka) Oh to do this sans IO
    // TODO(miikka) Do the tests with an empty temp test directory

    #[test]
    fn test_add_get() {
        let store = Store::new(&PathBuf::from("test_data"));
        let bytes = "kissa2".as_bytes();
        let key = store.add(bytes).unwrap();
        let bytes2 = store.get(&key).unwrap();
        assert_eq!(bytes, bytes2);
    }
}
