import { DialogBody, DialogButton, DialogFooter, ModalRoot, showModal } from "@decky/ui";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { startVpnImport, stopVpnImport, vpnImportStatus } from "../backend";

function VpnImportModal({ closeModal }: { closeModal?: () => void }) {
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");
  const [savedProfile, setSavedProfile] = useState("");

  useEffect(() => {
    let cancelled = false;
    startVpnImport("1")
      .then((r) => { if (!cancelled) setUrl(r.url); })
      .catch((e) => { if (!cancelled) setErr(String(e)); });
    const timer = window.setInterval(async () => {
      try {
        const s = await vpnImportStatus();
        if (!cancelled && s.received) setSavedProfile(s.profile || "?");
      } catch (e) {
        // ignore transient poll errors
      }
    }, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      stopVpnImport().catch(() => {});
    };
  }, []);

  const close = () => closeModal?.();

  return (
    <ModalRoot onCancel={close}>
      <DialogBody>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "18px", fontWeight: 600, marginBottom: "12px" }}>Import VPN config</div>
          {err ? (
            <div style={{ color: "#e24b4a" }}>{err}</div>
          ) : url ? (
            <>
              <div style={{ background: "#ffffff", padding: "12px", display: "inline-block", borderRadius: "8px" }}>
                <QRCodeSVG value={url} size={190} />
              </div>
              <div style={{ marginTop: "14px", fontSize: "13px", opacity: 0.7 }}>
                Open this on your computer or phone (same Wi-Fi), paste your vless:// link or config, then pick Profile 1 or 2:
              </div>
              <div style={{ marginTop: "6px", fontFamily: "monospace", fontSize: "16px", color: "#3b8ade" }}>{url}</div>
              {savedProfile ? (
                <div style={{ marginTop: "16px", color: "#5dcaa5", fontWeight: 500 }}>Config saved to Profile {savedProfile}.</div>
              ) : (
                <div style={{ marginTop: "16px", opacity: 0.6 }}>Waiting for your config...</div>
              )}
            </>
          ) : (
            <div style={{ opacity: 0.6 }}>Starting server...</div>
          )}
        </div>
      </DialogBody>
      <DialogFooter>
        <DialogButton onClick={close}>{savedProfile ? "Done" : "Cancel"}</DialogButton>
      </DialogFooter>
    </ModalRoot>
  );
}

export function openVpnImport() {
  showModal(<VpnImportModal />);
}
