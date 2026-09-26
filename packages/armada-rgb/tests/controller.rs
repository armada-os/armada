use armada_rgb::{
    ChannelBackend, ColorCorrection, Controller, LightingBackend, LightingConfig, MulticolorBackend,
};
use std::fs;
use std::os::unix::fs::{symlink, PermissionsExt};
use std::path::PathBuf;
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

static NEXT: AtomicU64 = AtomicU64::new(0);

struct Fixture {
    root: PathBuf,
    backlight: PathBuf,
    config: PathBuf,
    leds: PathBuf,
    model: PathBuf,
    profiles: PathBuf,
}

impl Fixture {
    fn new() -> Self {
        let nonce: u128 = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root: PathBuf = std::env::temp_dir().join(format!(
            "rgb-test-{}-{nonce}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        let leds: PathBuf = root.join("leds");
        let backlight: PathBuf = root.join("backlight");
        fs::create_dir_all(&leds).unwrap();
        fs::create_dir_all(backlight.join("panel")).unwrap();
        fs::write(backlight.join("panel/brightness"), "50").unwrap();
        fs::write(backlight.join("panel/max_brightness"), "100").unwrap();

        let fixture = Self {
            config: root.join("etc/rgb.json"),
            backlight,
            leds,
            model: root.join("model"),
            profiles: root.join("profiles.json"),
            root,
        };
        fs::write(&fixture.model, b"Test Device\0").unwrap();
        fixture
    }

    fn controller(&self, targets: &[String]) -> Controller {
        let backend: MulticolorBackend =
            MulticolorBackend::new(self.leds.clone(), targets.to_vec());
        Controller::new(self.config.clone(), LightingBackend::Multicolor(backend))
    }

    fn target(&self, name: &str, order: &str, maximum: &str) {
        let path: PathBuf = self.leds.join(name);
        fs::create_dir_all(&path).unwrap();
        fs::write(path.join("multi_index"), order).unwrap();
        fs::write(path.join("max_brightness"), maximum).unwrap();
        fs::write(path.join("multi_intensity"), "unchanged\n").unwrap();
        fs::write(path.join("brightness"), "unchanged\n").unwrap();
    }

    fn channel_target(&self, name: &str, maximum: &str) {
        let path: PathBuf = self.leds.join(name);
        fs::create_dir_all(&path).unwrap();
        fs::write(path.join("max_brightness"), maximum).unwrap();
        fs::write(path.join("brightness"), "unchanged\n").unwrap();
    }

    fn value(&self, target: &str, attribute: &str) -> String {
        fs::read_to_string(self.leds.join(target).join(attribute))
            .unwrap()
            .lines()
            .next()
            .unwrap()
            .into()
    }

    fn command(&self, backend: &str, targets: &[&str], correction: Option<&str>) -> Command {
        let correction: Option<ColorCorrection> = correction.map(|value| value.parse().unwrap());
        let catalog = serde_json::json!({
            "version": 1,
            "profiles": [{
                "models": ["Test Device"],
                "backend": {
                    "type": backend,
                    "targets": targets,
                },
                "correction": correction,
            }],
        });
        fs::write(&self.profiles, serde_json::to_vec(&catalog).unwrap()).unwrap();

        let mut command = Command::new(env!("CARGO_BIN_EXE_armada-rgb"));
        command
            .env("ARMADA_RGB_CONFIG_PATH", &self.config)
            .env("ARMADA_RGB_SYSFS_ROOT", &self.leds)
            .env("ARMADA_BACKLIGHT_ROOT", &self.backlight)
            .env("ARMADA_RGB_MODEL_PATH", &self.model)
            .env("ARMADA_RGB_PROFILES_PATH", &self.profiles);
        command
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.root);
    }
}

fn enabled(color: &str, brightness: u8) -> LightingConfig {
    LightingConfig {
        version: 1,
        enabled: true,
        link_brightness: false,
        brightness,
        max_brightness: 25,
        color: color.into(),
        saturation: 100,
        correction: None,
    }
}

#[test]
fn defaults_and_config_round_trip() {
    let fixture: Fixture = Fixture::new();
    fixture.target("rgb:l1", "blue green red", "255");
    let controller: Controller = fixture.controller(&["rgb:l1".into()]);

    let defaults: LightingConfig = controller.get().unwrap();
    assert!(!defaults.enabled);
    assert_eq!(defaults.brightness, 25);

    let saved: LightingConfig = controller.set(enabled("abcdef", 40)).unwrap();
    assert_eq!(saved.color, "ABCDEF");
    assert_eq!(controller.get().unwrap(), saved);
    assert!(!fixture.config.with_extension("tmp").exists());
}

#[test]
fn thor_bgr_targets_do_not_touch_other_leds() {
    let fixture: Fixture = Fixture::new();
    let targets: Vec<String> = ["l1", "l2", "l3", "l4", "r1", "r2", "r3", "r4"]
        .map(|name| format!("rgb:{name}"))
        .into();
    for target in &targets {
        fixture.target(target, "blue green red", "255");
    }
    fixture.target("power-led", "red green blue", "511");
    let controller: Controller = fixture.controller(&targets);

    controller.set(enabled("FF8000", 25)).unwrap();

    for target in targets {
        assert_eq!(fixture.value(&target, "multi_intensity"), "0 55 255");
        assert_eq!(fixture.value(&target, "brightness"), "64");
    }
    assert_eq!(fixture.value("power-led", "brightness"), "unchanged");
}

#[test]
fn saturation_is_applied_to_multicolor_output() {
    let fixture: Fixture = Fixture::new();
    fixture.target("rgb:l1", "blue green red", "255");

    let output: std::process::Output = fixture
        .command("multicolor", &["rgb:l1"], None)
        .args([
            "set",
            "--color",
            "FF0000",
            "--saturation",
            "50",
            "--brightness",
            "100",
        ])
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(fixture.value("rgb:l1", "multi_intensity"), "55 55 255");
}

#[test]
fn linked_brightness_scales_output_without_changing_saved_config() {
    let fixture: Fixture = Fixture::new();
    fixture.target("rgb:l1", "blue green red", "255");

    let output: std::process::Output = fixture
        .command("multicolor", &["rgb:l1"], None)
        .args([
            "set",
            "--enabled",
            "true",
            "--link-brightness",
            "true",
            "--max-brightness",
            "50",
            "--color",
            "FF0000",
            "--brightness",
            "80",
        ])
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let saved: LightingConfig = serde_json::from_slice(&output.stdout).unwrap();
    assert!(saved.enabled);
    assert!(saved.link_brightness);
    assert_eq!(saved.max_brightness, 50);
    assert_eq!(saved.brightness, 80);
    assert_eq!(fixture.value("rgb:l1", "multi_intensity"), "0 0 255");
    assert_eq!(fixture.value("rgb:l1", "brightness"), "64");

    let output: std::process::Output = fixture
        .command("multicolor", &["rgb:l1"], None)
        .arg("get")
        .output()
        .unwrap();
    let persisted: LightingConfig = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(persisted, saved);
}

#[test]
fn odin3_channel_targets_do_not_touch_other_leds() {
    let fixture: Fixture = Fixture::new();
    let targets: Vec<String> = [
        "red=l:r1",
        "red=r:r1",
        "green=l:g1",
        "green=r:g1",
        "blue=l:b1",
        "blue=r:b1",
    ]
    .map(str::to_owned)
    .into();
    for target in ["l:r1", "r:r1", "l:g1", "r:g1", "l:b1", "r:b1"] {
        fixture.channel_target(target, "255");
    }
    fixture.channel_target("power-led", "255");
    let backend: ChannelBackend = ChannelBackend::new(fixture.leds.clone(), targets);
    let controller: Controller =
        Controller::new(fixture.config.clone(), LightingBackend::Channels(backend));

    controller.set(enabled("FF8000", 25)).unwrap();

    for target in ["l:r1", "r:r1"] {
        assert_eq!(fixture.value(target, "brightness"), "64");
    }
    for target in ["l:g1", "r:g1"] {
        assert_eq!(fixture.value(target, "brightness"), "14");
    }
    for target in ["l:b1", "r:b1"] {
        assert_eq!(fixture.value(target, "brightness"), "0");
    }
    assert_eq!(fixture.value("power-led", "brightness"), "unchanged");

    controller.off().unwrap();
    for target in ["l:r1", "r:r1", "l:g1", "r:g1", "l:b1", "r:b1"] {
        assert_eq!(fixture.value(target, "brightness"), "0");
    }
}

#[test]
fn cli_supports_channel_backend() {
    let fixture: Fixture = Fixture::new();
    for target in ["l:r1", "l:g1", "l:b1"] {
        fixture.channel_target(target, "255");
    }
    let output: std::process::Output = fixture
        .command(
            "channels",
            &["red=l:r1", "green=l:g1", "blue=l:b1"],
            Some("always:0,20,20"),
        )
        .args(["set", "--color", "00ffff", "--brightness", "100"])
        .output()
        .unwrap();

    assert!(output.status.success());
    assert_eq!(fixture.value("l:r1", "brightness"), "0");
    assert_eq!(fixture.value("l:g1", "brightness"), "154");
    assert_eq!(fixture.value("l:b1", "brightness"), "154");
}

#[test]
fn air_y_pro_profile_controls_both_aw20036_rings() {
    let fixture: Fixture = Fixture::new();
    fs::write(&fixture.model, b"MANGMI Air Y Pro\0").unwrap();
    fs::write(&fixture.profiles, include_bytes!("../profiles.json")).unwrap();

    for index in 0..16 {
        for color in ["red", "green", "blue"] {
            fixture.channel_target(&format!("{color}:indicator-{index}"), "255");
        }
    }

    let output: std::process::Output = Command::new(env!("CARGO_BIN_EXE_armada-rgb"))
        .env("ARMADA_RGB_CONFIG_PATH", &fixture.config)
        .env("ARMADA_RGB_SYSFS_ROOT", &fixture.leds)
        .env("ARMADA_RGB_MODEL_PATH", &fixture.model)
        .env("ARMADA_RGB_PROFILES_PATH", &fixture.profiles)
        .args(["set", "--color", "FF8000", "--brightness", "25"])
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    for index in 0..16 {
        assert_eq!(
            fixture.value(&format!("red:indicator-{index}"), "brightness"),
            "64"
        );
        assert_eq!(
            fixture.value(&format!("green:indicator-{index}"), "brightness"),
            "14"
        );
        assert_eq!(
            fixture.value(&format!("blue:indicator-{index}"), "brightness"),
            "0"
        );
    }
}

#[test]
fn correction_preserves_the_user_color() {
    let fixture: Fixture = Fixture::new();
    fixture.target("rgb:sticks", "red green blue", "255");
    let run = |color: &str, correction: Option<&str>| {
        let mut command: Command =
            fixture.command("multicolor", &["rgb:sticks"], Some("red:0,20,20"));
        command.args(["set", "--color", color, "--brightness", "100"]);
        if let Some(correction) = correction {
            command.args(["--correction", correction]);
        }
        command.output().unwrap()
    };

    let output: std::process::Output = run("FFFF00", None);
    let config: LightingConfig = serde_json::from_slice(&output.stdout).unwrap();
    assert!(output.status.success());
    assert_eq!(config.color, "FFFF00");
    assert_eq!(config.correction.unwrap().green, 20);
    assert_eq!(fixture.value("rgb:sticks", "multi_intensity"), "255 154 0");

    let output: std::process::Output = run("00FFFF", Some("red:10,30,40"));
    assert!(output.status.success());
    assert_eq!(fixture.value("rgb:sticks", "multi_intensity"), "0 255 255");

    let output: std::process::Output = run("FFFFFF", None);
    let config: LightingConfig = serde_json::from_slice(&output.stdout).unwrap();
    assert!(output.status.success());
    assert_eq!(config.correction.unwrap().green, 30);
}

#[test]
fn target_errors_happen_before_writes() {
    let fixture: Fixture = Fixture::new();
    fixture.target("rgb:l1", "blue green red", "255");
    let targets: Vec<String> = vec!["rgb:l1".into(), "rgb:missing".into()];
    let controller: Controller = fixture.controller(&targets);

    assert!(controller.set(enabled("FFFFFF", 25)).is_err());
    assert_eq!(fixture.value("rgb:l1", "brightness"), "unchanged");
    assert!(!fixture.config.exists());
}

#[test]
fn preflight_rejects_an_unwritable_target() {
    let fixture: Fixture = Fixture::new();
    fixture.target("rgb:l1", "blue green red", "255");
    fixture.target("rgb:r1", "blue green red", "255");
    fs::set_permissions(
        fixture.leds.join("rgb:r1/multi_intensity"),
        fs::Permissions::from_mode(0o444),
    )
    .unwrap();
    let targets: Vec<String> = vec!["rgb:l1".into(), "rgb:r1".into()];
    let controller: Controller = fixture.controller(&targets);

    assert!(controller.set(enabled("FF0000", 10)).is_err());
    assert_eq!(fixture.value("rgb:l1", "brightness"), "unchanged");
    assert!(!fixture.config.exists());
}

#[test]
fn partial_writes_leave_targets_off() {
    let fixture: Fixture = Fixture::new();
    fixture.target("rgb:l1", "blue green red", "255");
    fixture.target("rgb:r1", "blue green red", "255");
    let brightness: PathBuf = fixture.leds.join("rgb:r1/brightness");
    fs::remove_file(&brightness).unwrap();
    symlink("/dev/full", brightness).unwrap();
    let targets: Vec<String> = vec!["rgb:l1".into(), "rgb:r1".into()];
    let controller: Controller = fixture.controller(&targets);

    assert!(controller.set(enabled("FF0000", 10)).is_err());
    assert_eq!(fixture.value("rgb:l1", "brightness"), "0");
    assert!(!fixture.config.exists());
}

#[test]
fn off_is_persistent_and_only_needs_brightness() {
    let fixture: Fixture = Fixture::new();
    fixture.target("rgb:l1", "blue green red", "100");
    let controller: Controller = fixture.controller(&["rgb:l1".into()]);
    controller.set(enabled("00FF00", 30)).unwrap();

    fs::write(fixture.leds.join("rgb:l1/multi_index"), "not rgb").unwrap();
    fs::write(fixture.leds.join("rgb:l1/max_brightness"), "zero").unwrap();
    let config: LightingConfig = controller.off().unwrap();

    assert!(!config.enabled);
    assert!(!controller.get().unwrap().enabled);
    assert_eq!(fixture.value("rgb:l1", "brightness"), "0");
}

#[test]
fn unsupported_devices_are_ignored_during_boot() {
    let fixture: Fixture = Fixture::new();
    fixture.target("power-led", "red green blue", "511");
    let controller: Controller = Controller::new(
        fixture.config.clone(),
        LightingBackend::Unsupported("not configured".into()),
    );

    assert_eq!(controller.apply().unwrap(), Some("not configured".into()));
    assert!(controller.set(enabled("FFFFFF", 25)).is_err());
    assert_eq!(fixture.value("power-led", "brightness"), "unchanged");
}

#[test]
fn cli_sets_gets_and_turns_off() {
    let fixture: Fixture = Fixture::new();
    fixture.target("rgb:l1", "blue green red", "255");
    let run = |args: &[&str]| {
        fixture
            .command("multicolor", &["rgb:l1"], None)
            .args(args)
            .output()
            .unwrap()
    };

    let output: std::process::Output = run(&["set", "--color", "aa00ff", "--brightness", "7"]);
    assert!(output.status.success());
    let config: LightingConfig = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(config.color, "AA00FF");
    assert!(config.enabled);

    let output: std::process::Output = run(&["off"]);
    assert!(output.status.success());
    let config: LightingConfig = serde_json::from_slice(&output.stdout).unwrap();
    assert!(!config.enabled);

    let output: std::process::Output = run(&["get"]);
    let config: LightingConfig = serde_json::from_slice(&output.stdout).unwrap();
    assert!(!config.enabled);

    let output: std::process::Output = run(&["set", "--color", "FFFFFF", "--brightness", "101"]);
    assert!(!output.status.success());
}

#[test]
fn cli_reports_profile_support() {
    let fixture: Fixture = Fixture::new();
    let output: std::process::Output = fixture
        .command("multicolor", &["rgb:l1"], None)
        .arg("supported")
        .output()
        .unwrap();
    assert!(output.status.success());

    fs::write(&fixture.model, b"Unknown Device\0").unwrap();
    let output: std::process::Output = fixture
        .command("multicolor", &["rgb:l1"], None)
        .arg("supported")
        .output()
        .unwrap();
    assert!(!output.status.success());
}
