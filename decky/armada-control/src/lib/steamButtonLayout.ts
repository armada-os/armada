type ControllerInfo = {
  nControllerIndex: number;
};

type Unregisterable = {
  unregister?: () => void;
};

let layout = "xbox";
let builtInControllerIndex: number | null = null;

function apply() {
  if (builtInControllerIndex === null) return;
  window.SteamClient?.Settings?.SetUseNintendoButtonLayout?.(
    builtInControllerIndex,
    layout === "nintendo",
  );
}

export function applySteamButtonLayout(value: string) {
  layout = value === "nintendo" ? "nintendo" : "xbox";
  apply();
}

export function registerSteamButtonLayout(value: string) {
  applySteamButtonLayout(value);
  const input = window.SteamClient?.Input;
  if (!input?.RegisterForControllerListChanges) return () => {};

  const registrations: Unregisterable[] = [];
  const controllerList = input.RegisterForControllerListChanges((controllers: ControllerInfo[]) => {
    const indexes = controllers
      .map((controller) => controller.nControllerIndex)
      .filter((index) => Number.isInteger(index) && index >= 0)
      .sort((a, b) => a - b);
    if (builtInControllerIndex !== null && indexes.includes(builtInControllerIndex)) {
      apply();
      return;
    }
    // InputPlumber creates the built-in virtual controller before Steam starts,
    // so it owns the first stable controller index.
    builtInControllerIndex = indexes[0] ?? null;
    apply();
  });
  registrations.push(controllerList);

  return () => {
    for (const registration of registrations) {
      registration?.unregister?.();
    }
    builtInControllerIndex = null;
  };
}
