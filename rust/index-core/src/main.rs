use std::env;
use std::path::Path;

use neuron_index_core::{discover_files, parse_csv_set};

fn escape_json(value: &str) -> String {
    value
        .replace('\\', "\\\\")
        .replace('"', "\\\"")
        .replace('\n', "\\n")
        .replace('\r', "\\r")
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 6 || args[1] != "discover" {
        eprintln!(
            "usage: neuron-index-core discover <root> <max_bytes> <supported_ext_csv> <skip_dir_csv>"
        );
        std::process::exit(2);
    }

    let root = Path::new(&args[2]);
    let max_bytes = args[3].parse::<u64>().unwrap_or(u64::MAX);
    let supported = parse_csv_set(&args[4]);
    let skip = parse_csv_set(&args[5]);

    for file in discover_files(root, &supported, &skip, max_bytes) {
        println!(
            "{{\"path\":\"{}\",\"size\":{},\"extension\":\"{}\"}}",
            escape_json(&file.path.to_string_lossy()),
            file.size,
            escape_json(&file.extension)
        );
    }
}
