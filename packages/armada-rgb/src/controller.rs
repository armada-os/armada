use crate::{config, display_brightness, runtime, LightingBackend, LightingConfig};
use anyhow::Result;
use std::path::PathBuf;

pub struct Controller {
    config_path: PathBuf,
    backend: LightingBackend,
}

impl Controller {
    pub fn new(config_path: PathBuf, backend: LightingBackend) -> Self {
        Self {
            config_path,
            backend,
        }
    }

    pub fn from_env() -> Self {
        let (config_path, backend): (PathBuf, LightingBackend) = runtime::from_env();
        Self::new(config_path, backend)
    }

    pub fn get(&self) -> Result<LightingConfig> {
        let mut config: LightingConfig = config::load(&self.config_path)?;
        if config.correction.is_none() {
            config.correction = self.backend.default_correction();
        }
        Ok(config)
    }

    pub fn is_supported(&self) -> bool {
        self.backend.unsupported_reason().is_none()
    }

    pub fn set(&self, config: LightingConfig) -> Result<LightingConfig> {
        let mut config: LightingConfig = config.validate()?;
        if config.correction.is_none() {
            config.correction = self.backend.default_correction();
        }
        let applied_config: LightingConfig = Self::config_for_apply(&config)?;
        self.backend.apply(&applied_config)?;
        config::save(&self.config_path, &config)?;
        Ok(config)
    }

    pub fn off(&self) -> Result<LightingConfig> {
        let mut config: LightingConfig = self.get()?;
        config.enabled = false;
        self.set(config)
    }

    pub fn apply(&self) -> Result<Option<String>> {
        if let Some(reason) = self.backend.unsupported_reason() {
            return Ok(Some(reason.into()));
        }

        let config: LightingConfig = self.get()?;
        let applied_config: LightingConfig = Self::config_for_apply(&config)?;
        self.backend.apply(&applied_config)?;
        Ok(None)
    }

    pub fn apply_if_linked(&self) -> Result<Option<String>> {
        if let Some(reason) = self.backend.unsupported_reason() {
            return Ok(Some(reason.into()));
        }

        let config: LightingConfig = self.get()?;
        if !config.enabled || !config.link_brightness {
            return Ok(None);
        }

        let applied_config: LightingConfig = Self::config_for_apply(&config)?;
        self.backend.apply(&applied_config)?;
        Ok(None)
    }

    fn config_for_apply(config: &LightingConfig) -> Result<LightingConfig> {
        let mut applied_config: LightingConfig = config.clone();
        if config.enabled && config.link_brightness {
            let screen_percent: u8 = display_brightness::screen_brightness_percent()?;
            applied_config.brightness =
                display_brightness::linked_brightness(screen_percent, config.max_brightness);
        }
        Ok(applied_config)
    }
}
