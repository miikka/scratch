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
    #[error("unknown error")]
    Unknown,
}

// TODO(miikka) Create a type for the store keys and return that from `add`
// TODO(miikka) Create a `get` function
// TODO(miikka) Create some basic tests with add+get

impl Store {
    pub fn new(path: &Path) -> Self {
        Store {
            path: PathBuf::from(path),
        }
    }

    pub fn add(&self, data: &[u8]) -> Result<PathBuf, CasError> {
        let key = blake3::hash(data).to_hex();
        let key_str: &str = &key;
        let key_prefix = &key[0..2];
        let data_dir = self.path.join(key_prefix);
        fs::create_dir_all(&data_dir)?;
        let data_path = data_dir.join(key_str);

        // Not exactly atomic or safe
        if !data_path.exists() {
            let mut file = File::create(&data_path)?;
            file.write_all(data)?;
        }

        Ok(data_path)
    }
}
