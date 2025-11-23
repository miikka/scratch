use std::{fs, path::PathBuf};

use anyhow::Result;
use cas::Store;
use clap::Parser;

#[derive(Parser, Debug)]
enum CasCli {
    Add(AddArgs),
}

#[derive(clap::Args, Debug)]
struct AddArgs {
    file_path: String,
}

fn add(args: &AddArgs) -> Result<()> {
    let data = fs::read(&args.file_path)?;
    let store = Store::new(&PathBuf::from("data"));

    let path = store.add(&data)?;
    println!("path: {:?}", path);

    Ok(())
}

fn main() -> Result<()> {
    let args = CasCli::parse();

    match args {
        CasCli::Add(args) => add(&args)?,
    };

    Ok(())
}
