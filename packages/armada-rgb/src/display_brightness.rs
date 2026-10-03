//! Helpers for deriving RGB settings from display brightness.

use anyhow::{bail, Context, Result};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

const BACKLIGHT_ROOT: &str = "/sys/class/backlight";

/// Read the selected display backlight as a percentage of its sysfs range.
///
/// `ARMADA_PRIMARY_BACKLIGHT` selects the device on systems with multiple
/// backlights. `ARMADA_BACKLIGHT_ROOT` allows the sysfs root to be overridden
/// for development with a fixture; production defaults to `/sys/class/backlight`.
pub(crate) fn screen_brightness_percent() -> Result<u8> {
    let root: PathBuf = env::var_os("ARMADA_BACKLIGHT_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(BACKLIGHT_ROOT));
    let backlight: PathBuf = select_backlight(&root)?;
    let brightness: u32 = read_value(&backlight.join("brightness"))?;
    let maximum: u32 = read_value(&backlight.join("max_brightness"))?;

    if maximum == 0 {
        bail!("backlight maximum brightness is zero");
    }

    // Round to the nearest whole percent and clamp any out-of-range driver value.
    let percent: u64 = (u64::from(brightness) * 100 + u64::from(maximum) / 2) / u64::from(maximum);
    Ok(percent.min(100) as u8)
}

/// Scale the configured RGB brightness ceiling by screen brightness.
pub(crate) fn linked_brightness(screen_percent: u8, max_brightness: u8) -> u8 {
    let screen_percent: u16 = u16::from(screen_percent.min(100));
    let max_brightness: u16 = u16::from(max_brightness.min(100));
    let scaled: u16 = (screen_percent * max_brightness + 50) / 100;
    scaled.clamp(1, 100) as u8
}

fn select_backlight(root: &Path) -> Result<PathBuf> {
    if let Ok(name) = env::var("ARMADA_PRIMARY_BACKLIGHT") {
        if !name.is_empty() {
            let path: PathBuf = root.join(&name);
            if path.is_dir() {
                return Ok(path);
            }
            bail!(
                "configured primary backlight '{}' was not found",
                path.display()
            );
        }
    }

    let mut devices: Vec<PathBuf> = fs::read_dir(root)
        .with_context(|| format!("list backlights in {}", root.display()))?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.is_dir())
        .collect();
    devices.sort();

    match devices.len() {
        0 => bail!("no backlight devices found in {}", root.display()),
        1 => Ok(devices.remove(0)),
        _ => bail!(
            "multiple backlight devices found in {}; set ARMADA_PRIMARY_BACKLIGHT",
            root.display()
        ),
    }
}

fn read_value(path: &Path) -> Result<u32> {
    let value: String = fs::read_to_string(path)
        .with_context(|| format!("read backlight value from {}", path.display()))?;
    value
        .trim()
        .parse::<u32>()
        .with_context(|| format!("parse backlight value from {}", path.display()))
}
