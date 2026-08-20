# Synapse Apple Bridge

This is an **inspection-first experimental compatibility lab**, not a claim that Synapse OS runs macOS applications generally.

`inspect_app.sh App.app` resolves the bundle executable, parses a thin Mach-O header/load commands without running the application, and reports architecture plus dylib/framework dependencies. Apple proprietary frameworks are not bundled or emulated here.

`launch_app.sh` refuses `unsupported` bundles. `experimental` Mach-O launch attempts require the explicit `--allow-experimental` flag and report the real process exit status. A successful process spawn is not treated as proof of application compatibility.
