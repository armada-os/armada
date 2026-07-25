import { getHdrRuntimeState } from "../backend";
import { HdrRuntimeStateCoordinator } from "./hdrRuntimeStateCoordinator";

export const hdrRuntimeState = new HdrRuntimeStateCoordinator({
  read: getHdrRuntimeState,
});
