# Changelog — TrueBeam Service Log (TB-Service-Logger)

All notable changes to this project are recorded here, newest first.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/): MAJOR.MINOR.PATCH, where a MINOR bump means new features and a PATCH bump means fixes only.

**How to keep this file up to date:** with every commit, add a one-line, plain-language entry under **Unreleased**. When you cut a release, rename **Unreleased** to the new version number and date, and start a new empty **Unreleased** section above it.

Entries marked **[Physics review]** change clinical workflow or what gets recorded, so a qualified medical physicist should review them before relying on the change. This software is not validated for clinical use.

## [Unreleased]

Merged to `main` and pushed after v1.4.4. Release downloads have not been rebuilt yet.

### Added
- Scheduled evening summary email sent from the host computer, with an on/off switch and a recipient list in folder settings.
- If no SMTP mail server is configured, the evening email is sent through classic Outlook running on the host.
- The evening email includes every table column plus the five most recent faults, under the title "UF TB MACHINE LOG".

### Changed
- **[Physics review]** Fault Reports columns are now Varian Suggested Solution, Resolution/Fix, Initials, and a new Status column (Open or Resolved, shown amber or green) in the app, Excel logs, table downloads, and the evening email. Faults show as Open until someone marks them Resolved.
- Larger text in the report tables and Excel logs. Excel logs print landscape, fitted to one page wide, with the header row repeated; the app has a Print (landscape) button.
- **[Physics review]** Every screenshot is now logged, and screenshots taken within the same five-minute window are grouped into one fault.
- The connection indicator shows a steady "connected" status instead of flashing while it scans.

### In progress (in the working folder, not committed yet)
- **[Physics review]** A draft Couch Shift Log tool (`couch_shift_log.py`, with a build script and tests) that records Vrt/Lng/Lat couch translations to a local CSV, keyed by de-identified session IDs.

## [1.4.4] - 2026-10-20
### Fixed
- Manual export works again.
- Each change to the log now records where it was saved and when.

## [1.4.3] - 2026-10-19
### Changed
- New Excel logs are saved on every report change, and the output settings are simpler.
### Fixed
- Shows the established monitoring status instead of an out-of-date Excel setup prompt.

## [1.4.2] - 2026-10-19
### Fixed
- Restored the verified folder-connection indicator and the fallback folder picker.

## [1.4.1] - 2026-10-19
### Changed
- Timestamped Excel logs are saved whenever entries are added.
- Folder setup is streamlined.

## [1.4.0] - 2026-10-18
### Changed
- The browser, Mac, and Windows packages all ship one shared HTML interface, and the build checks that the Windows interface is byte-for-byte identical.
### Fixed
- Fixed how the embedded renderer is packaged on Mac.

## [1.3.0] - 2026-10-17
### Changed
- Existing reports are reused instead of being duplicated, and imported fault entries are cleaned up using the timestamps in their filenames.
- Standalone executables are packaged with the same verified release workflow used for EMBRACE.

## [1.2.0-native-test.1] - 2026-10-16 (test build)
### Added
- Branded native desktop app (Qt) in place of the browser launcher.
### Fixed
- Avoided a startup delay caused by reverse DNS lookups.
- Kept the Mac OCR helper compatible with macOS 13 and later.

## [1.1.0-test.1] - 2026-10-16 (test build)
### Added
- First local TrueBeam service and fault report app, plus an offline standalone HTML version.
- **[Physics review]** Therapist fault intake, with offline import of PDF service reports and screenshots.
- Native Windows and Mac apps that remember folder paths.
- A styled two-sheet Excel workbook that saves automatically and is re-saved every minute while connected.
- Table downloads, sorting, branding, and a folder settings dialog.
- Direct editing in the table, links to screenshots, and description previews.
- Separate columns for Subject and Error Codes, with multiple error codes on separate lines.
- Mac and Windows app launchers for the HTML interface, with the UF Proton icon and default network settings.

### Changed
- Fault "status" became an editable Resolution field (first called "OUR SOLUTION").
- Worker initials have their own field, and existing export column order is kept.
- Notes were removed from fault entry and fault report exports.
- Compact error codes and engineer hours; empty cells show a hyphen.
- The service table is tighter, with engineer and hours separated and a single status.

### Fixed
- Diagnostic and database files now close cleanly on Windows.

[Unreleased]: https://github.com/Florida-Med-Physics/TB-Service-Logger/compare/v1.4.4...HEAD
[1.4.4]: https://github.com/Florida-Med-Physics/TB-Service-Logger/compare/v1.4.3...v1.4.4
[1.4.3]: https://github.com/Florida-Med-Physics/TB-Service-Logger/compare/v1.4.2...v1.4.3
[1.4.2]: https://github.com/Florida-Med-Physics/TB-Service-Logger/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/Florida-Med-Physics/TB-Service-Logger/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/Florida-Med-Physics/TB-Service-Logger/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/Florida-Med-Physics/TB-Service-Logger/compare/v1.2.0-native-test.1...v1.3.0
[1.2.0-native-test.1]: https://github.com/Florida-Med-Physics/TB-Service-Logger/compare/v1.1.0-test.1...v1.2.0-native-test.1
[1.1.0-test.1]: https://github.com/Florida-Med-Physics/TB-Service-Logger/releases/tag/v1.1.0-test.1
