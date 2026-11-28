"""What makes this engine one plugin rather than another. Each plugin's
package calls configure() once at import, before anything else runs."""


class Profile:
    # Both required from configure().
    name = None  # logs, staging folders, the default state folder
    env = None  # prefix of the environment overrides tests use
    # The catalog in use: active() returns {"apps", "categories", "revision"};
    # an optional opened() runs when the panel asks for the catalog.
    source = None
    # Install types the plugin handles itself, by name. Each handler offers
    # installed_info(app), launch_command(app), install(app, cancel,
    # on_download) and uninstall(app).
    kinds = {}
    extra_apps = staticmethod(lambda: [])  # apps from outside the catalog
    hidden_ids = frozenset()  # never offered, retired or acted on
    reserved_categories = ()  # filled by the plugin itself, shown when the catalog lists them
    after_install = None  # setup run after every install or update
    base_overrides = ()  # Flatpak overrides every install gets
    payload_extra = None  # extra per-app fields for the panel


profile = Profile()


def configure(**settings):
    for key, value in settings.items():
        if not hasattr(Profile, key):
            raise AttributeError(key)
        setattr(profile, key, value)
