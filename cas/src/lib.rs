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

// TODO(miikka) Implement a metadata store for listing the contents

// TODO(miikka) Implement Display for Key
impl Key {
    pub fn from_hex_str(hex: &str) -> Result<Self, CasError> {
        let hash = blake3::Hash::from_hex(hex)?;
        Ok(Self(hash))
    }

    pub fn to_hex_str(&self) -> String {
        self.0.to_string()
    }

    fn to_path(&self) -> PathBuf {
        let hex_str = self.0.to_string();
        PathBuf::from(&hex_str[0..2]).join(hex_str)
    }
}

impl Store {
    // TODO(miikka) The first parameter should accept Path, &str, etc.
    pub fn new(path: &Path) -> Self {
        Store {
            path: PathBuf::from(path),
        }
    }

    pub fn add(&self, data: &[u8]) -> Result<Key, CasError> {
        // 0 = use zstd's default level
        // TODO(miikka) Should not compress short strings!
        let compressed = zstd::stream::encode_all(data, 0)?;

        // Should the files have some sort of metadata? Or does that belong to the metadata store?
        let key = blake3::hash(&compressed);
        let key_hex = key.to_hex();
        let key_str: &str = &key_hex;
        let key_prefix = &key_hex[0..2];
        let data_dir = self.path.join(key_prefix);
        fs::create_dir_all(&data_dir)?;
        let data_path = data_dir.join(key_str);

        // Not exactly atomic or safe
        if !data_path.exists() {
            let mut file = File::create(&data_path)?;
            file.write_all(&compressed)?;
        }

        Ok(Key(key))
    }

    // TODO(miikka) Create a variant of get that allows copying the output directly to a writer
    pub fn get(&self, key: &Key) -> Result<Vec<u8>, CasError> {
        let data_path = self.path.join(key.to_path());
        let file = File::open(data_path)?;
        let data = zstd::stream::decode_all(file)?;
        Ok(data)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // TODO(miikka) Oh to do this sans IO

    fn get_test_store() -> Store {
        let store_id: u64 = rand::random();
        let store_name = format!("test_data/{}", store_id);
        println!("store directory: {:04}", store_name);
        Store::new(&PathBuf::from(store_name))
    }

    #[test]
    fn test_add_get() {
        let store = get_test_store();
        let bytes = "kissa2".as_bytes();
        let key = store.add(bytes).unwrap();
        let bytes2 = store.get(&key).unwrap();
        println!("key={:?}", key);
        assert_eq!(bytes, bytes2);
    }

    #[test]
    fn test_get_empty() {
        let key =
            Key::from_hex_str("871f68ab569985d7003ac89c71d7120d991f69a3064389f149efc299f12a0513")
                .unwrap();
        let store = get_test_store();
        let result = store.get(&key);
        assert!(result.is_err());
    }
}
