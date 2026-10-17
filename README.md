# TrueBeam Service Log — native desktop application

Download the **native Windows or Mac application** from the [native desktop release](https://github.com/Florida-Med-Physics/TB-Service-Logger/releases/tag/v1.3.0).

The app opens directly in its own desktop window with the UF Proton icon. Its interface uses native Qt controls; it does not open a browser or load an HTML page.

- Windows: extract **TrueBeam-Service-Log-Windows-x64.zip**, then run **TrueBeam Service Log.exe** — this is one self-contained executable, packaged the same way as EMBRACE.
- Mac (Apple Silicon): extract **TrueBeam-Service-Log-macOS-arm64.zip**, then open **TrueBeam Service Log.app**.
- Service Reports and Fault Reports are separate tabs. Double-click values to view/edit, and attached PDFs/PNGs to open in the default viewer.
- Shared UFHPTI paths are preset. The first Windows instance hosts the shared log; keep it running for other staff. Without a shared drive, the app opens a local workspace.
- The app saves edits immediately. Background Excel feeds publish every minute without replacing an open workbook. **Export Report** writes a fresh standalone snapshot.
- Builds are unsigned; network deployment and automatic Excel refresh still need UFHPTI confirmation.

Older HTML/browser launchers and the earlier Tk interface remain in source for reference. Use the **Native** downloads above.

## Development

Install requirements-native.txt, then run python native_application.py --local.
Build on the destination OS with python build_native_application.py. This also smoke-tests the executable and creates the ZIP, using the same PyInstaller version, Windows one-file mode, Mac app-bundle mode, and build runners as EMBRACE.
Run python verify_native_application.py to verify the packaged native interface.


Older interfaces are documented in docs/legacy-interfaces.md for reference only.
