//! Command line interface for RGB lighting.

use anyhow::Result;
use armada_rgb::{watch_brightness, ColorCorrection, Controller, LightingConfig};
use clap::{Parser, Subcommand};
use std::time::Duration;

#[derive(Parser)]
#[command(version, about)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Check whether this device has a lighting profile.
    Supported,
    /// Show the saved lighting configuration.
    Get,
    /// Set a solid color and brightness.
    Set {
        /// Whether the RGB lighting is enabled.
        #[arg(long, action = clap::ArgAction::Set)]
        enabled: Option<bool>,
        /// Link RGB brightness to screen brightness.
        #[arg(long, action = clap::ArgAction::Set)]
        link_brightness: Option<bool>,
        /// Maximum RGB brightness while screen linking is enabled.
        #[arg(long)]
        max_brightness: Option<u8>,
        #[arg(long)]
        color: String,
        #[arg(long)]
        saturation: Option<u8>,
        #[arg(long)]
        brightness: u8,
        /// RGB correction trigger and channel reductions.
        #[arg(long, value_name = "TRIGGER:RED,GREEN,BLUE")]
        correction: Option<ColorCorrection>,
    },
    /// Turn the stick lights off and save that state.
    Off,
    /// Apply the saved configuration.
    Apply,
    /// Watch display brightness and reapply linked RGB brightness when it changes.
    Watch {
        /// Polling interval in milliseconds.
        #[arg(long, default_value_t = 200)]
        interval_ms: u64,
    },
}

fn main() -> Result<()> {
    let cli: Cli = Cli::parse();
    let controller: Controller = Controller::from_env();

    match cli.command {
        Command::Supported => {
            if !controller.is_supported() {
                std::process::exit(1);
            }
        }
        Command::Get => {
            let config: LightingConfig = controller.get()?;
            println!("{}", serde_json::to_string_pretty(&config)?);
        }
        Command::Set {
            enabled,
            link_brightness,
            max_brightness,
            color,
            saturation,
            brightness,
            correction,
        } => {
            let mut config: LightingConfig = controller.get()?;
            config.enabled = enabled.unwrap_or(true);
            if let Some(link_brightness) = link_brightness {
                config.link_brightness = link_brightness;
            }
            if let Some(max_brightness) = max_brightness {
                config.max_brightness = max_brightness;
            }
            config.color = color;

            if let Some(saturation) = saturation {
                config.saturation = saturation;
            }

            config.brightness = brightness;

            if let Some(correction) = correction {
                config.correction = Some(correction);
            }
            let config: LightingConfig = controller.set(config)?;
            println!("{}", serde_json::to_string_pretty(&config)?);
        }
        Command::Off => {
            let config: LightingConfig = controller.off()?;
            println!("{}", serde_json::to_string_pretty(&config)?);
        }
        Command::Apply => {
            if let Some(reason) = controller.apply()? {
                eprintln!("RGB unsupported: {reason}");
            }
        }
        Command::Watch { interval_ms } => {
            if interval_ms == 0 {
                anyhow::bail!("watch polling interval must be greater than zero");
            }
            if controller.is_supported() {
                let config = controller.get()?;
                if config.enabled && config.link_brightness {
                    watch_brightness(&controller, Duration::from_millis(interval_ms))?;
                }
            }
        }
    }
    Ok(())
}
