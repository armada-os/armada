import { findModuleExport } from "@decky/ui";

export class CompatToolsRequest {
  appid?: number;

  serializeBinary(): Uint8Array {
    if (this.appid === undefined) return new Uint8Array();
    let value = this.appid >>> 0;
    const bytes = [8]; // appid: uint32, field 1
    while (value > 127) {
      bytes.push((value & 127) | 128);
      value >>>= 7;
    }
    bytes.push(value);
    return new Uint8Array(bytes);
  }
}

export class CompatToolsResponse {
  tools: Array<{ name?: string; display_name?: string; is_incompatible?: boolean }> = [];

  static deserializeBinaryFromReader(message: CompatToolsResponse, reader: any): void {
    while (reader.nextField()) {
      if (reader.isEndGroup()) break;
      if (reader.getFieldNumber() !== 1) {
        // Armada's default policy requires concrete tool IDs, not Steam aliases.
        reader.skipField();
        continue;
      }
      const tool: CompatToolsResponse["tools"][number] = {};
      reader.readMessage(tool, (entry: typeof tool, fields: any) => {
        while (fields.nextField()) {
          if (fields.isEndGroup()) break;
          switch (fields.getFieldNumber()) {
            case 1: entry.name = fields.readString(); break;
            case 2: entry.display_name = fields.readString(); break;
            case 6: entry.is_incompatible = fields.readBool(); break;
            default: fields.skipField();
          }
        }
      });
      message.tools.push(tool);
    }
  }
}

let transportStore: any;
let messageClass: any;

function compatTransport(): any {
  if (!transportStore) {
    // The minified getter has no stable signature; the module's diagnostic does.
    let require: any;
    window.webpackChunksteamui?.push([
      [Symbol("armada-compat-transport")], {}, (loader: any) => { require = loader; },
    ]);
    const id = Object.keys(require?.m || {}).find((key) =>
      require.m[key].toString().includes("Multiple attempts to set a default WebUI transport"),
    );
    if (id) {
      for (const value of Object.values(require(id))) {
        if (typeof value !== "function") continue;
        let candidate;
        try { candidate = value(); } catch { continue; }
        if (typeof candidate?.GetDefaultTransport === "function") {
          transportStore = candidate;
          break;
        }
      }
    }
  }
  messageClass ||= findModuleExport((value: any) =>
    typeof value?.Init === "function"
    && typeof value?.InitFromObject === "function"
    && typeof value?.prototype?.SetBodyFields === "function",
  );
  const transport = transportStore?.GetDefaultTransport();
  if (!transport?.SendMsg || !messageClass) {
    throw new Error("Steam compatibility tool discovery is unavailable");
  }
  return transport;
}

export async function getCompatManagerTools(appid?: number): Promise<CompatToolsResponse> {
  // Steam can dereference a missing Proton alias before its post-login services initialize.
  await (window as any).App.WaitForServicesInitialized();
  const transport = compatTransport();
  const request = messageClass.Init(CompatToolsRequest);
  request.Body().appid = appid;
  const response = await transport.SendMsg(
    "CompatManager.GetCompatTools#1", request, CompatToolsResponse,
    // Steam's CompatManager privilege level (1), executing in clientdll (2).
    { ePrivilege: 1, eClientExecutionSite: 2 },
  );
  if (!response.BSuccess()) {
    throw new Error(`Steam compatibility tool discovery failed (${response.GetEResult()})`);
  }
  return response.Body();
}
