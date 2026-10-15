//! Poll display brightness and reapply linked RGB brightness on changes.

use crate::{display_brightness, Controller};
use anyhow::Result;
use std::thread;
use std::time::Duration;

/// Keep the RGB LEDs in sync with the display while the system is running.
pub fn watch_brightness(controller: &Controller, interval: Duration) -> Result<()> {
    let mut previous_brightness: Option<u8> = None;
    let mut last_error: Option<String> = None;

    loop {
        let config = controller.get()?;

        // Exit the thread if RGB is disabled or linked brightness is not enabled, to avoid unnecessary polling.
        if !config.enabled || !config.link_brightness {
            return Ok(());
        }

        match display_brightness::screen_brightness_percent() {
            Ok(brightness) => {
                if let Some(result) = apply_if_changed(&mut previous_brightness, brightness, || {
                    controller.apply_if_linked()
                }) {
                    match result {
                        Ok(Some(reason)) => eprintln!("RGB unsupported: {reason}"),
                        Ok(None) => {}
                        Err(error) => eprintln!("RGB brightness apply failed: {error:#}"),
                    }
                }
                last_error = None;
            }
            Err(error) => {
                let message = format!("{error:#}");
                if last_error.as_deref() != Some(message.as_str()) {
                    eprintln!("screen brightness watcher: {message}");
                    last_error = Some(message);
                }
            }
        }

        thread::sleep(interval);
    }
}

fn apply_if_changed<F>(
    previous_brightness: &mut Option<u8>,
    brightness: u8,
    apply: F,
) -> Option<Result<Option<String>>>
where
    F: FnOnce() -> Result<Option<String>>,
{
    if *previous_brightness == Some(brightness) {
        return None;
    }

    let result: Result<Option<String>> = apply();
    if result.is_ok() {
        *previous_brightness = Some(brightness);
    }
    Some(result)
}

#[cfg(test)]
mod tests {
    use super::apply_if_changed;
    use anyhow::anyhow;

    #[test]
    fn applies_on_first_brightness_read() {
        let mut previous_brightness: Option<u8> = None;
        let mut apply_count: u8 = 0;

        let result = apply_if_changed(&mut previous_brightness, 40, || {
            apply_count += 1;
            Ok(None)
        });

        assert!(matches!(result, Some(Ok(None))));
        assert_eq!(apply_count, 1);
        assert_eq!(previous_brightness, Some(40));
    }

    #[test]
    fn skips_when_brightness_is_unchanged() {
        let mut previous_brightness: Option<u8> = Some(40);

        let result = apply_if_changed(&mut previous_brightness, 40, || {
            panic!("unchanged brightness should not be applied")
        });

        assert!(result.is_none());
        assert_eq!(previous_brightness, Some(40));
    }

    #[test]
    fn applies_when_brightness_changes() {
        let mut previous_brightness: Option<u8> = Some(40);
        let result = apply_if_changed(&mut previous_brightness, 60, || Ok(None));

        assert!(matches!(result, Some(Ok(None))));
        assert_eq!(previous_brightness, Some(60));
    }

    #[test]
    fn remembers_unsupported_result_as_handled() {
        let mut previous_brightness: Option<u8> = None;
        let result = apply_if_changed(&mut previous_brightness, 40, || {
            Ok(Some("unsupported device".into()))
        });

        assert!(matches!(result, Some(Ok(Some(reason))) if reason == "unsupported device"));
        assert_eq!(previous_brightness, Some(40));
    }

    #[test]
    fn retries_after_apply_failure() {
        let mut previous_brightness: Option<u8> = None;

        let failed = apply_if_changed(&mut previous_brightness, 40, || {
            Err(anyhow!("transient failure"))
        });
        assert!(matches!(failed, Some(Err(_))));
        assert_eq!(previous_brightness, None);

        let retried = apply_if_changed(&mut previous_brightness, 40, || Ok(None));
        assert!(matches!(retried, Some(Ok(None))));
        assert_eq!(previous_brightness, Some(40));
    }
}
