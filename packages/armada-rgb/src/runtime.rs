use crate::{ChannelBackend, ColorCorrection, LightingBackend, MulticolorBackend};
use anyhow::{bail, Context, Result};
use serde::Deserialize;
use std::collections::HashSet;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

const CONFIG_PATH: &str = "/etc/armada/rgb.json";
const MODEL_PATH: &str = "/sys/firmware/devicetree/base/model";
const PROFILE_VERSION: u32 = 1;
const PROFILES_PATH: &str = "/usr/share/armada-rgb/profiles.json";
const SYSFS_ROOT: &str = "/sys/class/leds";

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ProfileCatalog {
    version: u32,
    profiles: Vec<DeviceProfile>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct DeviceProfile {
    models: Vec<String>,
    backend: BackendProfile,
    #[serde(default)]
    correction: Option<ColorCorrection>,
}

#[derive(Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
enum BackendProfile {
    Channels { targets: Vec<String> },
    Multicolor { targets: Vec<String> },
}

pub(crate) fn from_env() -> (PathBuf, LightingBackend) {
    let config_path: PathBuf = env::var_os("ARMADA_RGB_CONFIG_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|| CONFIG_PATH.into());
    let model_path: PathBuf = env::var_os("ARMADA_RGB_MODEL_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|| MODEL_PATH.into());
    let profiles_path: PathBuf = env::var_os("ARMADA_RGB_PROFILES_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|| PROFILES_PATH.into());
    let sysfs_root: PathBuf = env::var_os("ARMADA_RGB_SYSFS_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|| SYSFS_ROOT.into());

    let backend: LightingBackend = load_backend(&profiles_path, &model_path, sysfs_root)
        .unwrap_or_else(|error| LightingBackend::Unsupported(format!("{error:#}")));
    (config_path, backend)
}

fn load_backend(profiles_path: &Path, model_path: &Path, root: PathBuf) -> Result<LightingBackend> {
    let input: String = fs::read_to_string(profiles_path)
        .with_context(|| format!("read RGB profiles from {}", profiles_path.display()))?;
    let catalog: ProfileCatalog = parse_catalog(&input)?;
    let model: String = fs::read_to_string(model_path)
        .with_context(|| format!("read device model from {}", model_path.display()))?;
    let model: &str =
        model.trim_matches(|character: char| character == '\0' || character.is_whitespace());
    if model.is_empty() {
        bail!("device model is empty");
    }

    let profile: DeviceProfile = catalog
        .profiles
        .into_iter()
        .find(|profile| profile.models.iter().any(|candidate| candidate == model))
        .with_context(|| format!("device model '{model}' has no RGB profile"))?;
    profile
        .correction
        .as_ref()
        .map(ColorCorrection::validate)
        .transpose()?;

    match profile.backend {
        BackendProfile::Channels { targets } if !targets.is_empty() => {
            Ok(LightingBackend::Channels(
                ChannelBackend::new(root, targets).with_correction(profile.correction),
            ))
        }
        BackendProfile::Multicolor { targets } if !targets.is_empty() => {
            Ok(LightingBackend::Multicolor(
                MulticolorBackend::new(root, targets).with_correction(profile.correction),
            ))
        }
        BackendProfile::Channels { .. } | BackendProfile::Multicolor { .. } => {
            bail!("device profile has no RGB targets")
        }
    }
}

fn parse_catalog(input: &str) -> Result<ProfileCatalog> {
    let catalog: ProfileCatalog = serde_json::from_str(input).context("parse RGB profiles")?;
    if catalog.version != PROFILE_VERSION {
        bail!("unsupported RGB profile version {}", catalog.version);
    }

    let mut models: HashSet<&str> = HashSet::new();
    for profile in &catalog.profiles {
        if profile.models.is_empty() {
            bail!("RGB profile has no device models");
        }
        for model in &profile.models {
            if model.is_empty() {
                bail!("RGB profile has an empty device model");
            }
            if !models.insert(model) {
                bail!("duplicate RGB profile for device model '{model}'");
            }
        }
    }
    Ok(catalog)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn packaged_profiles_cover_current_devices() {
        let catalog: ProfileCatalog = parse_catalog(include_str!("../profiles.json")).unwrap();
        for model in [
            "AYN Odin 2",
            "AYN Odin 2 Portal",
            "AYN Thor",
            "AYN Thor Lite",
            "AYN Odin 3",
            "KONKR Pocket FIT Elite",
            "MANGMI Air Y Pro",
            "MANGMI Pocket Max",
            "Retroid Pocket 5",
            "Retroid Pocket 5 Visionox",
            "Retroid Pocket Flip2",
            "Retroid Pocket Flip2 Visionox",
            "Retroid Pocket 6",
            "Retroid Pocket 6 TOP-DPAD",
            "Retroid Pocket Nova",
        ] {
            assert!(catalog
                .profiles
                .iter()
                .any(|profile| profile.models.iter().any(|candidate| candidate == model)));
        }
    }

    #[test]
    fn validates_catalog_version_and_models() {
        assert!(parse_catalog(r#"{"version":2,"profiles":[]}"#).is_err());
        assert!(parse_catalog(
            r#"{"version":1,"profiles":[{"models":[],"backend":{"type":"multicolor","targets":["rgb:l1"]}}]}"#,
        )
        .is_err());
        assert!(parse_catalog(
            r#"{"version":1,"profiles":[{"models":["test"],"backend":{"type":"multicolor","targets":["rgb:l1"]}},{"models":["test"],"backend":{"type":"channels","targets":["red=l:r1"]}}]}"#,
        )
        .is_err());
    }
}
