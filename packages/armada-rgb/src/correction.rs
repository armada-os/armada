use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::str::FromStr;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct ColorCorrection {
    pub trigger: String,
    pub red: u8,
    pub green: u8,
    pub blue: u8,
}

impl ColorCorrection {
    pub(crate) fn validate(&self) -> Result<()> {
        if !matches!(self.trigger.as_str(), "always" | "red" | "green" | "blue") {
            bail!("invalid RGB correction trigger '{}'", self.trigger);
        }
        for (channel, reduction) in [
            ("red", self.red),
            ("green", self.green),
            ("blue", self.blue),
        ] {
            if reduction > 100 {
                bail!("{channel} correction must be between 0 and 100");
            }
        }
        Ok(())
    }

    pub(crate) fn apply(&self, [red, green, blue]: [u8; 3]) -> [u8; 3] {
        let triggered: bool = match self.trigger.as_str() {
            "always" => true,
            "red" => red > 0,
            "green" => green > 0,
            "blue" => blue > 0,
            _ => unreachable!("validated correction trigger"),
        };
        if !triggered {
            return [red, green, blue];
        }

        [
            reduce(red, self.red),
            reduce(green, self.green),
            reduce(blue, self.blue),
        ]
    }
}

impl FromStr for ColorCorrection {
    type Err = anyhow::Error;

    fn from_str(value: &str) -> Result<Self> {
        let (trigger, reductions): (&str, &str) = value
            .split_once(':')
            .context("RGB correction must contain a trigger and reductions")?;
        let channels: Vec<&str> = reductions.split(',').collect();
        if channels.len() != 3 {
            bail!("RGB correction must contain red, green, and blue reductions");
        }

        let correction: Self = Self {
            trigger: trigger.into(),
            red: channels[0].parse().context("invalid red correction")?,
            green: channels[1].parse().context("invalid green correction")?,
            blue: channels[2].parse().context("invalid blue correction")?,
        };
        correction.validate()?;
        Ok(correction)
    }
}

fn reduce(value: u8, reduction: u8) -> u8 {
    let retained: u16 = u16::from(100 - reduction);
    ((u16::from(value) * retained + 50) / 100) as u8
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn corrects_all_channels() {
        let correction: ColorCorrection = "always:10,20,30".parse().unwrap();
        assert_eq!(correction.apply([255, 255, 255]), [230, 204, 179]);
    }

    #[test]
    fn only_corrects_matching_colors() {
        let correction: ColorCorrection = "red:0,20,20".parse().unwrap();

        assert_eq!(correction.apply([255, 255, 0]), [255, 204, 0]);
        assert_eq!(correction.apply([255, 0, 255]), [255, 0, 204]);
        assert_eq!(correction.apply([255, 255, 255]), [255, 204, 204]);
        assert_eq!(correction.apply([0, 255, 255]), [0, 255, 255]);
    }

    #[test]
    fn validates_correction() {
        assert!("purple:0,20,20".parse::<ColorCorrection>().is_err());
        assert!("red:0,20".parse::<ColorCorrection>().is_err());
        assert!("red:0,20,101".parse::<ColorCorrection>().is_err());
    }
}
