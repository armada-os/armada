export type ControllerInfo = {
  eControllerType: number;
  nControllerIndex: number;
  unUniqueID: number;
  unVendorID: number;
  unProductID: number;
  strSerialNumber: string;
};

type Unregisterable = {
  unregister?: () => void;
};

const STEAM_CONTROLLER_TYPES: Record<string, number> = {
  "deck-uhid": 4,
  xb360: 31,
  ds5: 45,
};

let layout = "xbox";
let builtInControllerIndex: number | null = null;
let controllerType = "deck-uhid";
let controllers: ControllerInfo[] = [];
let awaitingControllerRecreation = false;

function controllerSignature(controller: ControllerInfo) {
  return [
    controller.nControllerIndex,
    controller.eControllerType,
    controller.unUniqueID,
    controller.unVendorID,
    controller.unProductID,
    controller.strSerialNumber,
  ].join(":");
}

function matchesControllerType(controller: ControllerInfo, type: string) {
  return controller.eControllerType === STEAM_CONTROLLER_TYPES[type];
}

export function selectBuiltInController(
  nextControllers: ControllerInfo[],
  previousControllers: ControllerInfo[],
  type: string,
  currentIndex: number | null,
  awaitNewController: boolean,
) {
  const candidates = nextControllers
    .filter((controller) => matchesControllerType(controller, type))
    .sort((a, b) => a.nControllerIndex - b.nControllerIndex);
  if (currentIndex !== null && candidates.some((controller) => controller.nControllerIndex === currentIndex)) {
    return currentIndex;
  }
  if (!awaitNewController) {
    return candidates[0]?.nControllerIndex ?? null;
  }
  const previous = new Set(previousControllers.map(controllerSignature));
  return candidates.find((controller) => !previous.has(controllerSignature(controller)))?.nControllerIndex ?? null;
}

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

export function beginSteamControllerTypeChange(value: string) {
  controllerType = value in STEAM_CONTROLLER_TYPES ? value : "deck-uhid";
  builtInControllerIndex = null;
  awaitingControllerRecreation = true;
}

export function restoreSteamControllerType(value: string) {
  controllerType = value in STEAM_CONTROLLER_TYPES ? value : "deck-uhid";
  builtInControllerIndex = selectBuiltInController(
    controllers,
    [],
    controllerType,
    null,
    false,
  );
  awaitingControllerRecreation = false;
  apply();
}

export function registerSteamButtonLayout(value: string, type: string) {
  applySteamButtonLayout(value);
  controllerType = type in STEAM_CONTROLLER_TYPES ? type : "deck-uhid";
  const input = window.SteamClient?.Input;
  if (!input?.RegisterForControllerListChanges) return () => {};

  const registrations: Unregisterable[] = [];
  const controllerList = input.RegisterForControllerListChanges((nextControllers: ControllerInfo[]) => {
    const selected = selectBuiltInController(
      nextControllers,
      controllers,
      controllerType,
      builtInControllerIndex,
      awaitingControllerRecreation,
    );
    controllers = nextControllers;
    builtInControllerIndex = selected;
    if (selected !== null) {
      awaitingControllerRecreation = false;
    }
    apply();
  });
  registrations.push(controllerList);

  return () => {
    for (const registration of registrations) {
      registration?.unregister?.();
    }
    builtInControllerIndex = null;
    controllers = [];
    awaitingControllerRecreation = false;
  };
}
