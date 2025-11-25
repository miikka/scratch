use std::{
    fs,
    io::{self, Write},
    path::PathBuf,
};

use anyhow::Result;
use cas::{Key, Store};
use clap::Parser;

#[derive(Parser, Debug)]
enum CasCli {
    Add(AddArgs),
    Get(GetArgs),
}

#[derive(clap::Args, Debug)]
struct AddArgs {
    file_path: String,
}

#[derive(clap::Args, Debug)]
struct GetArgs {
    key: String,
}

fn add(args: &AddArgs) -> Result<()> {
    let data = fs::read(&args.file_path)?;
    let store = Store::new(&PathBuf::from("data"));

    let key = store.add(&data)?;
    println!("{}", key.to_hex_str());

    Ok(())
}

fn get(args: &GetArgs) -> Result<()> {
    let store = Store::new(&PathBuf::from("data"));
    let key = Key::from_hex_str(&args.key)?;
    let data = store.get(&key)?;

    io::stdout().write(&data)?;

    Ok(())
}

fn main() -> Result<()> {
    let args = CasCli::parse();

    match args {
        CasCli::Add(args) => add(&args)?,
        CasCli::Get(args) => get(&args)?,
    };

    Ok(())
}
