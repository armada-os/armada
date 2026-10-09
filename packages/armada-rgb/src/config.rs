use crate::LightingConfig;
use anyhow::{Context, Result};
use std::fs;
use std::path::{Path, PathBuf};

pub(crate) fn load(path: &Path) -> Result<LightingConfig> {
    let input: String = match fs::read_to_string(path) {
        Ok(input) => input,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(LightingConfig::default())
        }
        Err(error) => return Err(error).context("read RGB config"),
    };

    let config: LightingConfig = serde_json::from_str(&input).context("parse RGB config")?;
    config.validate()
}

pub(crate) fn save(path: &Path, config: &LightingConfig) -> Result<()> {
    let directory: &Path = path.parent().context("config path has no parent")?;
    let temporary: PathBuf = path.with_extension("tmp");
    let mut contents: Vec<u8> = serde_json::to_vec_pretty(config)?;
    contents.push(b'\n');

    fs::create_dir_all(directory).context("create config directory")?;
    fs::write(&temporary, contents).context("write temporary RGB config")?;
    fs::rename(temporary, path).context("replace RGB config")
}
