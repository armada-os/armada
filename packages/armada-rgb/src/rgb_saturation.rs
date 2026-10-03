//! Helpers for adjusting RGB saturation through HSV conversion.

/// Replace the saturation of an RGB color while preserving its hue and value.
pub(crate) fn rgb_after_saturation(rgb: [u8; 3], saturation: u8) -> [u8; 3] {
    // Read the color's hue and brightness before replacing its saturation.
    let (hue, original_saturation, value): (f32, f32, f32) = rgb_to_hsv(rgb);

    // Gray colors have no meaningful hue, so leave them unchanged.
    if original_saturation == 0.0 {
        return rgb;
    }

    // Keep the hue and brightness, but use the slider's saturation value.
    hsv_to_rgb(hue, f32::from(saturation.min(100)), value)
}

fn rgb_to_hsv([red, green, blue]: [u8; 3]) -> (f32, f32, f32) {
    // Convert RGB's 0-255 range into HSV's 0.0-1.0 range.
    let red: f32 = f32::from(red) / 255.0;
    let green: f32 = f32::from(green) / 255.0;
    let blue: f32 = f32::from(blue) / 255.0;
    let maximum: f32 = red.max(green).max(blue);
    let minimum: f32 = red.min(green).min(blue);
    let delta: f32 = maximum - minimum;

    // If all channels are equal, the color is gray and has no hue.
    if delta == 0.0 {
        return (0.0, 0.0, maximum);
    }

    // Saturation is the size of the color range relative to its brightness.
    let saturation: f32 = delta / maximum;

    // Work out which RGB channel is brightest to determine the hue section.
    let mut hue: f32 = if maximum == red {
        (green - blue) / delta
    } else if maximum == green {
        2.0 + (blue - red) / delta
    } else {
        4.0 + (red - green) / delta
    };

    // Convert the hue section into degrees from 0 to 360.
    hue = (hue / 6.0).rem_euclid(1.0) * 360.0;
    (hue, saturation, maximum)
}

fn hsv_to_rgb(hue: f32, saturation: f32, value: f32) -> [u8; 3] {
    // Clamp the inputs and convert saturation from a percentage to 0.0-1.0.
    let saturation: f32 = (saturation / 100.0).clamp(0.0, 1.0);
    let value: f32 = value.clamp(0.0, 1.0);
    // Divide the hue wheel into six 60-degree RGB transition sections.
    let hue: f32 = hue.rem_euclid(360.0) / 60.0;

    // Calculate how much color there is and how much the changing channel contributes.
    let chroma: f32 = value * saturation;
    let intermediate: f32 = chroma * (1.0 - ((hue % 2.0) - 1.0).abs());
    // Shift the color upward so its final brightness matches the requested value.
    let match_value: f32 = value - chroma;

    // Select the RGB arrangement for this hue section.
    let (red, green, blue): (f32, f32, f32) = match hue {
        h if h < 1.0 => (chroma, intermediate, 0.0),
        h if h < 2.0 => (intermediate, chroma, 0.0),
        h if h < 3.0 => (0.0, chroma, intermediate),
        h if h < 4.0 => (0.0, intermediate, chroma),
        h if h < 5.0 => (intermediate, 0.0, chroma),
        _ => (chroma, 0.0, intermediate),
    };

    // Convert normalized RGB channels back to rounded 0-255 values.
    let to_channel = |channel: f32| -> u8 { ((channel + match_value) * 255.0).round() as u8 };

    [to_channel(red), to_channel(green), to_channel(blue)]
}

#[cfg(test)]
mod tests {
    use super::rgb_after_saturation;

    #[test]
    fn preserves_full_saturation() {
        assert_eq!(rgb_after_saturation([255, 165, 0], 100), [255, 165, 0]);
    }

    #[test]
    fn desaturates_red_halfway() {
        assert_eq!(rgb_after_saturation([255, 0, 0], 50), [255, 128, 128]);
    }

    #[test]
    fn desaturates_each_hue_sector_halfway() {
        let cases: [([u8; 3], [u8; 3]); 5] = [
            ([0, 255, 0], [128, 255, 128]),
            ([0, 0, 255], [128, 128, 255]),
            ([255, 255, 0], [255, 255, 128]),
            ([0, 255, 255], [128, 255, 255]),
            ([255, 0, 255], [255, 128, 255]),
        ];

        for (input, expected) in cases {
            assert_eq!(rgb_after_saturation(input, 50), expected);
        }
    }

    #[test]
    fn fully_desaturates_full_value_colors_to_white() {
        for input in [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 165, 0]] {
            assert_eq!(rgb_after_saturation(input, 0), [255, 255, 255]);
        }
    }

    #[test]
    fn preserves_value_when_desaturating_a_dim_color() {
        assert_eq!(rgb_after_saturation([100, 50, 25], 50), [100, 67, 50]);
        assert_eq!(rgb_after_saturation([100, 50, 25], 0), [100, 100, 100]);
    }

    #[test]
    fn leaves_grayscale_colors_unchanged() {
        assert_eq!(rgb_after_saturation([130, 130, 130], 50), [130, 130, 130]);
        assert_eq!(rgb_after_saturation([0, 0, 0], 50), [0, 0, 0]);
    }

    #[test]
    fn clamps_saturation_above_one_hundred() {
        assert_eq!(rgb_after_saturation([255, 165, 0], 255), [255, 165, 0]);
    }
}
