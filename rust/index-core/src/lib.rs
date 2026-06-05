use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileCandidate {
    pub path: PathBuf,
    pub size: u64,
    pub extension: String,
}

pub fn normalize_path(path: &Path) -> Option<PathBuf> {
    path.canonicalize().ok()
}

pub fn is_supported_file(path: &Path, supported_extensions: &HashSet<String>) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .map(|ext| supported_extensions.contains(&format!(".{}", ext.to_ascii_lowercase())))
        .unwrap_or(false)
}

pub fn should_skip_dir(path: &Path, skip_dirs: &HashSet<String>) -> bool {
    path.file_name()
        .and_then(|name| name.to_str())
        .map(|name| skip_dirs.contains(name))
        .unwrap_or(false)
}

pub fn discover_files(
    root: &Path,
    supported_extensions: &HashSet<String>,
    skip_dirs: &HashSet<String>,
    max_file_size_bytes: u64,
) -> Vec<FileCandidate> {
    let mut out = Vec::new();
    discover_into(root, supported_extensions, skip_dirs, max_file_size_bytes, &mut out);
    out
}

fn discover_into(
    root: &Path,
    supported_extensions: &HashSet<String>,
    skip_dirs: &HashSet<String>,
    max_file_size_bytes: u64,
    out: &mut Vec<FileCandidate>,
) {
    let entries = match fs::read_dir(root) {
        Ok(entries) => entries,
        Err(_) => return,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        let metadata = match entry.metadata() {
            Ok(metadata) => metadata,
            Err(_) => continue,
        };

        if metadata.is_dir() {
            if !should_skip_dir(&path, skip_dirs) {
                discover_into(&path, supported_extensions, skip_dirs, max_file_size_bytes, out);
            }
            continue;
        }

        if !metadata.is_file() || metadata.len() > max_file_size_bytes {
            continue;
        }

        if is_supported_file(&path, supported_extensions) {
            let extension = path
                .extension()
                .and_then(|ext| ext.to_str())
                .map(|ext| format!(".{}", ext.to_ascii_lowercase()))
                .unwrap_or_default();
            out.push(FileCandidate {
                path,
                size: metadata.len(),
                extension,
            });
        }
    }
}

pub fn parse_csv_set(value: &str) -> HashSet<String> {
    value
        .split(',')
        .map(str::trim)
        .filter(|item| !item.is_empty())
        .map(ToOwned::to_owned)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::sync::atomic::{AtomicU64, Ordering};

    static TEMP_COUNTER: AtomicU64 = AtomicU64::new(0);

    fn temp_root() -> PathBuf {
        let mut root = std::env::temp_dir();
        let counter = TEMP_COUNTER.fetch_add(1, Ordering::Relaxed);
        root.push(format!(
            "neuron_index_core_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
                + counter as u128
        ));
        fs::create_dir_all(&root).unwrap();
        root
    }

    #[test]
    fn discovers_supported_files_and_skips_dirs() {
        let root = temp_root();
        fs::write(root.join("keep.py"), "print('ok')").unwrap();
        fs::write(root.join("ignore.tmp"), "no").unwrap();
        fs::create_dir(root.join("__pycache__")).unwrap();
        fs::write(root.join("__pycache__").join("skip.py"), "skip").unwrap();

        let exts = parse_csv_set(".py,.md");
        let skip = parse_csv_set("__pycache__,node_modules");
        let files = discover_files(&root, &exts, &skip, 1024);

        fs::remove_dir_all(&root).unwrap();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0].extension, ".py");
        assert!(files[0].path.ends_with("keep.py"));
    }

    #[test]
    fn respects_max_file_size() {
        let root = temp_root();
        let mut file = fs::File::create(root.join("large.md")).unwrap();
        file.write_all(b"too large").unwrap();
        drop(file);

        let exts = parse_csv_set(".md");
        let skip = HashSet::new();
        let files = discover_files(&root, &exts, &skip, 3);

        fs::remove_dir_all(&root).unwrap();
        assert!(files.is_empty());
    }
}
