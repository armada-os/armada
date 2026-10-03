//! RGB lighting support for Armada devices.

mod backend;
mod config;
mod controller;
mod correction;
mod display_brightness;
mod rgb_saturation;
mod runtime;
mod state;
mod watcher;

pub use backend::{ChannelBackend, LightingBackend, MulticolorBackend};
pub use controller::Controller;
pub use correction::ColorCorrection;
pub use state::LightingConfig;
pub use watcher::watch_brightness;
